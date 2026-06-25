"""
批量 API
=========
一次请求处理多个项目。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.crud import get_project, get_features, get_testpoints, get_testcases
from backend.db.database import get_db
from backend.models.schemas import MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/batch", tags=["批量操作"])


class BatchGenerateRequest(BaseModel):
    """批量生成请求。"""
    project_ids: list[int] = Field(..., min_length=1, max_length=20, description="项目 ID 列表")


@router.post("/generate", response_model=MessageResponse)
async def batch_generate(
    body: BatchGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """批量一键生成：对多个项目同时执行全流程。

    Args:
        body: {"project_ids": [1, 2, 3]}

    Returns:
        每个项目的处理结果
    """
    import asyncio
    from dataclasses import asdict
    from services.ai_client import get_ai_client
    from services.document_parser import DocumentParser, ParsedDocument
    from services.feature_service import FeatureService
    from services.testpoint_service import TestPointService
    from services.testcase_service import TestCaseService
    from services.excel_exporter import ExportData, ExcelExporter
    from backend.db.crud import (
        save_features, save_testpoints, save_testcases, update_project_status,
    )

    sem = asyncio.Semaphore(3)  # 最多 3 个项目并行
    results: list[dict] = []

    async def _process_one(pid: int) -> dict:
        async with sem:
            try:
                project = await get_project(db, pid)
                if not project:
                    return {"project_id": pid, "ok": False, "error": "项目不存在"}
                if not project.doc_content:
                    return {"project_id": pid, "ok": False, "error": "请先上传需求文档"}

                ai_client = get_ai_client()
                parser = DocumentParser()
                chunks = parser._chunk_text(project.doc_content)
                counts = {}

                # Step 1: 功能点
                feat_svc = FeatureService(ai_client)
                features: list[dict] = []
                seen = set()
                for chunk in chunks:
                    try:
                        r = feat_svc.extract(chunk.content)
                        for item in r.features:
                            n = item.name.strip()
                            if n and n not in seen:
                                seen.add(n)
                                features.append({
                                    "module": "未分类", "name": n,
                                    "description": item.description, "priority": "P2",
                                    "preconditions": [], "business_rules": [],
                                })
                    except Exception:
                        pass
                counts["features"] = len(features)
                if not features:
                    return {"project_id": pid, "ok": False, "error": "未能提取到功能点"}

                # Step 2: 测试点
                tp_svc = TestPointService(ai_client)
                all_tps: list[dict] = []
                async def _gen_tp(f):
                    loop = asyncio.get_running_loop()
                    try:
                        r = await loop.run_in_executor(
                            None, lambda: tp_svc.generate(f["name"], f.get("description", ""))
                        )
                        return [(r.feature_name, tp.category, tp.description,
                                 tp.expected_result, tp.test_data, tp.priority)
                                for tp in r.test_points]
                    except Exception:
                        return []

                tp_results = await asyncio.gather(*[_gen_tp(f) for f in features])
                for tps in tp_results:
                    for fn, cat, desc, exp, data, pri in tps:
                        all_tps.append({
                            "feature_name": fn, "category": cat, "description": desc,
                            "expected_result": exp, "test_data": data, "priority": pri,
                        })
                counts["testpoints"] = len(all_tps)
                if not all_tps:
                    return {"project_id": pid, "ok": False, "error": "未能生成测试点"}

                # Step 3: 测试用例（合并小功能点）
                groups: dict[str, list[dict]] = {}
                for tp in all_tps:
                    fn = tp.get("feature_name", "未分类")
                    groups.setdefault(fn, []).append({
                        "category": tp.get("category", "功能测试"),
                        "description": tp.get("description", ""),
                        "expected_result": tp.get("expected_result", ""),
                        "test_data": tp.get("test_data", ""),
                        "priority": tp.get("priority", "P1"),
                    })
                # 小组合并
                small = [(fn, tps) for fn, tps in groups.items() if len(tps) <= 3]
                merged = {fn: tps for fn, tps in groups.items() if len(tps) > 3}
                while small:
                    batch = small[:5]; small = small[5:]
                    mname = "、".join(fn for fn, _ in batch) if len(batch) > 1 else batch[0][0]
                    mtps = []
                    for fn, tps in batch:
                        for tp in tps:
                            mtps.append({**tp, "_source_feature": fn})
                    merged[mname] = mtps

                tc_svc = TestCaseService(ai_client)
                all_tcs: list[dict] = []
                async def _gen_tc(fn, tps):
                    loop = asyncio.get_running_loop()
                    try:
                        cases = await loop.run_in_executor(None, lambda: tc_svc.generate(fn, tps))
                        return [(fn, tc.id, tc.title, tc.precondition, tc.steps, tc.expected_result)
                                for tc in cases]
                    except Exception:
                        return []

                tc_items = list(merged.items())
                tc_results = await asyncio.gather(*[_gen_tc(fn, tps) for fn, tps in tc_items])
                for tcs in tc_results:
                    for fn, cid, title, precond, steps, expected in tcs:
                        all_tcs.append({
                            "testpoint_description": fn, "case_id": cid,
                            "title": title, "precondition": precond,
                            "steps": steps, "expected": expected,
                            "priority": "P1", "case_type": "正向",
                        })
                counts["testcases"] = len(all_tcs)

                # Step 4: 导出 Excel
                data = ExportData(
                    project_name=project.name,
                    features=features,
                    testpoints=all_tps,
                    testcases=all_tcs,
                )
                filepath = ExcelExporter().export(data)

                return {
                    "project_id": pid,
                    "ok": True,
                    "name": project.name,
                    "counts": counts,
                    "excel_file": filepath.name,
                }

            except Exception as exc:
                logger.error("批量处理项目 %d 失败: %s", pid, exc)
                return {"project_id": pid, "ok": False, "error": "处理失败"}

    tasks = [_process_one(pid) for pid in body.project_ids]
    results = await asyncio.gather(*tasks)

    success = [r for r in results if r.get("ok")]
    failed = [r for r in results if not r.get("ok")]

    return MessageResponse(
        ok=True,
        message=f"批量处理完成：{len(success)} 成功 / {len(failed)} 失败",
        data={
            "total": len(results),
            "success": len(success),
            "failed": len(failed),
            "results": results,
        },
    )
