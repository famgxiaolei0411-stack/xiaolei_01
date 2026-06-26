"""
批量 API
=========
一次请求处理多个项目。
"""

import asyncio
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.crud import get_project
from backend.db.database import get_db
from backend.models.schemas import MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/batch", tags=["批量操作"])


class BatchGenerateRequest(BaseModel):
    """批量生成请求。"""

    project_ids: list[int] = Field(..., min_length=1, max_length=20, description="项目 ID 列表")


def _format_error(stage: str, exc: Exception) -> str:
    detail = str(exc).strip() or exc.__class__.__name__
    return f"{stage}: {detail}"


@router.post("/generate", response_model=MessageResponse)
async def batch_generate(
    body: BatchGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """批量一键生成：逐个项目执行完整流程。"""

    from backend.db.crud import (
        save_features,
        save_testcases,
        save_testpoints,
        update_project_status,
    )
    from services.ai_client import (
        AIConfigurationError,
        AIRequestError,
        AIResponseParseError,
        get_ai_client,
    )
    from services.document_classifier import classify_document
    from services.document_parser import DocumentParser
    from services.excel_exporter import ExportData, ExcelExporter
    from services.feature_service import FeatureService, FeatureValidationError
    from services.testcase_service import TestCaseService, TestCaseValidationError
    from services.case_type import infer_case_priority, infer_case_type, source_priorities_for_case
    from services.testpoint_service import TestPointService, TestPointValidationError

    results: list[dict] = []

    async def _process_one(pid: int) -> dict:
        try:
            project = await get_project(db, pid)
            if not project:
                return {"project_id": pid, "ok": False, "error": "项目不存在"}
            if not project.doc_content:
                return {"project_id": pid, "ok": False, "error": "请先上传需求文档"}

            try:
                ai_client = get_ai_client()
            except AIConfigurationError as exc:
                return {"project_id": pid, "ok": False, "error": str(exc)}

            parser = DocumentParser()
            chunks = parser._chunk_text(project.doc_content)
            doc_type = classify_document(project.doc_content)
            counts: dict[str, int] = {}

            feat_svc = FeatureService(ai_client)
            features: list[dict] = []
            seen: set[str] = set()
            feature_errors: list[str] = []

            await update_project_status(db, pid, "extracting")
            for chunk in chunks:
                try:
                    result = feat_svc.extract(chunk.content)
                    for item in result.features:
                        name = item.name.strip()
                        if name and name not in seen:
                            seen.add(name)
                            features.append({
                                "module": "未分类",
                                "name": name,
                                "description": item.description,
                                "priority": "P2",
                                "preconditions": [],
                                "business_rules": [],
                            })
                except (AIRequestError, AIResponseParseError, FeatureValidationError) as exc:
                    logger.warning("批量项目 %d 功能点提取失败: %s", pid, exc)
                    feature_errors.append(_format_error("功能点提取失败", exc))

            counts["features"] = len(features)
            if not features:
                detail = feature_errors[0] if feature_errors else "未能提取到功能点"
                raise RuntimeError(detail)

            await save_features(db, pid, features)
            await update_project_status(db, pid, "features_extracted")

            tp_svc = TestPointService(ai_client)
            all_tps: list[dict] = []
            tp_errors: list[str] = []

            await update_project_status(db, pid, "generating_testpoints")

            async def _gen_tp(feature: dict) -> tuple[list[dict], str | None]:
                loop = asyncio.get_running_loop()
                name = feature.get("name", "")
                desc = feature.get("description", "")
                try:
                    result = await loop.run_in_executor(None, lambda: tp_svc.generate(name, desc))
                    items = [{
                        "feature_name": result.feature_name,
                        "category": tp.category,
                        "description": tp.description,
                        "expected_result": tp.expected_result,
                        "test_data": tp.test_data,
                        "priority": tp.priority,
                    } for tp in result.test_points]
                    return items, None
                except (AIRequestError, AIResponseParseError, TestPointValidationError) as exc:
                    logger.warning("批量项目 %d 功能点 [%s] 测试点生成失败: %s", pid, name, exc)
                    return [], _format_error(f"测试点生成失败（{name}）", exc)

            for items, error in await asyncio.gather(*[_gen_tp(feature) for feature in features]):
                all_tps.extend(items)
                if error:
                    tp_errors.append(error)

            counts["testpoints"] = len(all_tps)
            if not all_tps:
                detail = tp_errors[0] if tp_errors else "未能生成测试点"
                raise RuntimeError(detail)

            await save_testpoints(db, pid, all_tps)
            await update_project_status(db, pid, "testpoints_generated")

            groups: dict[str, list[dict]] = {}
            for tp in all_tps:
                feature_name = tp.get("feature_name", "未分类")
                groups.setdefault(feature_name, []).append({
                    "category": tp.get("category", "功能测试"),
                    "description": tp.get("description", ""),
                    "expected_result": tp.get("expected_result", ""),
                    "test_data": tp.get("test_data", ""),
                    "priority": tp.get("priority", "P1"),
                })

            small = [(name, tps) for name, tps in groups.items() if len(tps) <= 3]
            merged = {name: tps for name, tps in groups.items() if len(tps) > 3}
            while small:
                batch = small[:5]
                small = small[5:]
                merged_name = "、".join(name for name, _ in batch) if len(batch) > 1 else batch[0][0]
                merged_items = []
                for _, tps in batch:
                    merged_items.extend(tps)
                merged[merged_name] = merged_items

            tc_svc = TestCaseService(ai_client)
            all_tcs: list[dict] = []
            tc_errors: list[str] = []

            await update_project_status(db, pid, "generating_testcases")

            async def _gen_tc(feature_name: str, test_points: list[dict]) -> tuple[list[dict], str | None]:
                loop = asyncio.get_running_loop()
                try:
                    cases = await loop.run_in_executor(
                        None,
                        lambda: tc_svc.generate(feature_name, test_points, doc_type.mode),
                    )
                    items = [{
                        "testpoint_description": feature_name,
                        "case_id": tc.id,
                        "title": tc.title,
                        "precondition": tc.precondition,
                        "steps": tc.steps,
                        "expected": tc.expected_result,
                        "body": (getattr(tc, "body", "") if doc_type.mode == "api" else getattr(tc, "test_data", "")) or "",
                        "method": getattr(tc, "method", "") if doc_type.mode == "api" else "",
                        "url": getattr(tc, "url", "") if doc_type.mode == "api" else "",
                        "headers": getattr(tc, "headers", "") if doc_type.mode == "api" else "",
                        "priority": infer_case_priority(tc.title, expected=tc.expected_result, steps=tc.steps, source_priorities=source_priorities_for_case(tc.title, expected=tc.expected_result, steps=tc.steps, testpoints=test_points), case_type=infer_case_type(tc.title, expected=tc.expected_result, steps=tc.steps, categories={tp.get("category", "") for tp in test_points})),
                        "case_type": infer_case_type(tc.title, expected=tc.expected_result, steps=tc.steps, categories={tp.get("category", "") for tp in test_points}),
                    } for tc in cases]
                    return items, None
                except (AIRequestError, AIResponseParseError, TestCaseValidationError) as exc:
                    logger.warning("批量项目 %d 功能点 [%s] 用例生成失败: %s", pid, feature_name, exc)
                    return [], _format_error(f"测试用例生成失败（{feature_name}）", exc)

            for items, error in await asyncio.gather(*[
                _gen_tc(feature_name, test_points)
                for feature_name, test_points in merged.items()
            ]):
                all_tcs.extend(items)
                if error:
                    tc_errors.append(error)

            counts["testcases"] = len(all_tcs)
            if not all_tcs:
                detail = tc_errors[0] if tc_errors else "未能生成测试用例"
                raise RuntimeError(detail)

            await save_testcases(db, pid, all_tcs)
            await update_project_status(db, pid, "testcases_generated")

            data = ExportData(
                project_name=project.name,
                features=features,
                testpoints=all_tps,
                testcases=all_tcs,
                testcase_mode=doc_type.mode,
            )
            filepath = ExcelExporter().export(data)
            await update_project_status(db, pid, "exported")
            await db.commit()

            return {
                "project_id": pid,
                "ok": True,
                "name": project.name,
                "counts": counts,
                "excel_file": filepath.name,
                "doc_type": doc_type.doc_type,
                "testcase_mode": doc_type.mode,
            }

        except Exception as exc:
            logger.error("批量处理项目 %d 失败: %s", pid, exc)
            await db.rollback()
            try:
                await update_project_status(db, pid, "parsed")
                await db.commit()
            except Exception:
                await db.rollback()
                logger.exception("批量处理失败后恢复项目状态失败: project_id=%d", pid)
            return {"project_id": pid, "ok": False, "error": str(exc) or "处理失败"}

    for pid in body.project_ids:
        results.append(await _process_one(pid))

    success = [item for item in results if item.get("ok")]
    failed = [item for item in results if not item.get("ok")]

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
