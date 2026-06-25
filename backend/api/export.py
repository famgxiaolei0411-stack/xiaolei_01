"""
导出 API
=========
Excel 导出与文件下载。
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.crud import (
    get_features,
    get_project,
    get_testcases,
    get_testpoints,
    save_features,
    save_testcases,
    save_testpoints,
    update_project_status,
)
from backend.db.database import get_db
from backend.models.schemas import ExportOptions, ExportResponse, MessageResponse
from services.excel_exporter import ExportData, ExcelExporter
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["导出"])


@router.post("/{project_id}/export", response_model=ExportResponse)
async def export_to_excel(
    project_id: int,
    options: ExportOptions = ExportOptions(),
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    """导出项目数据（支持 Excel / JSON / Markdown）。

    Args:
        project_id: 项目 ID
        options: 导出选项（format: excel|json|md，include_features/include_testpoints）

    Returns:
        下载信息
    """
    fmt = getattr(options, "format", "excel") or "excel"

    # ── 获取项目数据 ──────────────────────────────
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    feature_orms = await get_features(db, project_id)
    testpoint_orms = await get_testpoints(db, project_id)
    testcase_orms = await get_testcases(db, project_id)

    if fmt == "json":
        filepath = _export_json(project.name, feature_orms, testpoint_orms, testcase_orms, options)
    elif fmt == "md":
        filepath = _export_markdown(project.name, feature_orms, testpoint_orms, testcase_orms, options)
    else:
        filepath = _export_excel(project.name, feature_orms, testpoint_orms, testcase_orms, options)

    await update_project_status(db, project_id, "exported")

    return ExportResponse(
        download_url=f"/api/v1/projects/{project_id}/download/{filepath.name}",
        filename=filepath.name,
        file_size=filepath.stat().st_size,
    )


@router.get("/{project_id}/download/{filename}")
async def download_file(
    project_id: int,
    filename: str,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """下载生成的 Excel 文件。

    Args:
        project_id: 项目 ID
        filename: 文件名

    Returns:
        文件流
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 路径遍历防护：确保解析后的路径在 OUTPUT_DIR 内
    file_path = (OUTPUT_DIR / filename).resolve()
    if not str(file_path).startswith(str(OUTPUT_DIR.resolve())):
        raise HTTPException(status_code=400, detail="无效的文件名")

    # 根据格式返回正确的 media_type
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "xlsx"
    media_map = {
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json",
        "md": "text/markdown",
    }
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type=media_map.get(ext, "application/octet-stream"),
    )


# ══════════════════════════════════════════════════════════
# 导出辅助函数
# ══════════════════════════════════════════════════════════

def _export_excel(project_name, feature_orms, testpoint_orms, testcase_orms, options):
    data = ExportData(
        project_name=project_name,
        features=_orm_to_feat_dicts(feature_orms) if options.include_features else [],
        testpoints=_orm_to_tp_dicts(testpoint_orms) if options.include_testpoints else [],
        testcases=_orm_to_tc_dicts(testcase_orms),
    )
    return ExcelExporter().export(data)


def _export_json(project_name, feature_orms, testpoint_orms, testcase_orms, options):
    import json as _json
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in project_name)
    filename = f"{safe}_{ts}.json"
    filepath = OUTPUT_DIR / filename
    data = {
        "project": project_name,
        "export_time": ts,
        "testcases": _orm_to_tc_dicts(testcase_orms),
    }
    if options.include_features:
        data["features"] = _orm_to_feat_dicts(feature_orms)
    if options.include_testpoints:
        data["testpoints"] = _orm_to_tp_dicts(testpoint_orms)
    filepath.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return filepath


def _export_markdown(project_name, feature_orms, testpoint_orms, testcase_orms, options):
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in project_name)
    filename = f"{safe}_{ts}.md"
    filepath = OUTPUT_DIR / filename

    lines = [f"# {project_name} — 测试用例", "", f"导出时间：{ts}", ""]

    if options.include_features:
        feats = _orm_to_feat_dicts(feature_orms)
        lines.append(f"## 功能点（{len(feats)} 个）")
        lines.append("")
        for f in feats:
            lines.append(f"- **{f['name']}** [{f['priority']}] — {f['description']}")
        lines.append("")

    if options.include_testpoints:
        tps = _orm_to_tp_dicts(testpoint_orms)
        lines.append(f"## 测试点（{len(tps)} 个）")
        lines.append("")
        for tp in tps:
            lines.append(f"- **[{tp['category']}]** {tp['description']} → {tp['expected_result']}")
        lines.append("")

    tcs = _orm_to_tc_dicts(testcase_orms)
    lines.append(f"## 测试用例（{len(tcs)} 条）")
    lines.append("")
    for tc in tcs:
        steps_text = "\n".join(f"   {i}. {s}" for i, s in enumerate(tc.get("steps", []), 1))
        lines.append(f"### {tc['case_id']} {tc['title']}")
        lines.append(f"- **优先级**: {tc['priority']} | **类型**: {tc.get('case_type','-')}")
        lines.append(f"- **前置条件**: {tc.get('precondition','无')}")
        lines.append(f"- **步骤**:\n{steps_text}")
        lines.append(f"- **预期结果**: {tc.get('expected','')}")
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def _orm_to_feat_dicts(orms):
    return [{"module": f.module, "name": f.name, "description": f.description,
             "priority": f.priority, "preconditions": f.preconditions,
             "business_rules": f.business_rules} for f in orms]


def _orm_to_tp_dicts(orms):
    return [{"feature_name": tp.feature_name, "category": tp.category,
             "description": tp.description, "expected_result": tp.expected_result,
             "test_data": tp.test_data or "", "priority": tp.priority} for tp in orms]


def _orm_to_tc_dicts(orms):
    from backend.db.crud import orm_to_dict
    return [orm_to_dict(tc) for tc in orms]


@router.post("/{project_id}/auto-generate", response_model=MessageResponse)
async def auto_generate_all(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """一键自动生成全部内容：功能点 → 测试点 → 测试用例 → Excel。

    这是 MVP 的核心「一键生成」接口。

    Args:
        project_id: 项目 ID

    Returns:
        生成结果汇总
    """
    from services.ai_client import get_ai_client
    from services.document_parser import DocumentParser, ParsedDocument
    from services.feature_service import FeatureService
    from services.testpoint_service import TestPointService
    from services.testcase_service import TestCaseService
    from services.excel_exporter import ExportData

    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.doc_content:
        raise HTTPException(status_code=400, detail="请先上传需求文档")

    ai_client = get_ai_client()
    results: dict[str, int] = {}

    # ── Step 1: 解析文档 ──────────────────────────
    parser_inst = DocumentParser()
    parsed_doc = ParsedDocument(
        filename=project.doc_filename or "unknown",
        file_type=".txt",
        full_text=project.doc_content,
        char_count=len(project.doc_content),
        chunks=parser_inst._chunk_text(project.doc_content),
    )

    # ── Step 2: 提取功能点 (V2: Pydantic校验+重试) ──
    logger.info("[Auto] 开始提取功能点 (V2)...")
    feat_service = FeatureService(ai_client)
    all_features: list[dict] = []
    seen = set()
    for chunk in parsed_doc.chunks:
        try:
            result = feat_service.extract(chunk.content)
            for item in result.features:
                name = item.name.strip()
                if name and name not in seen:
                    seen.add(name)
                    all_features.append({
                        "module": "未分类", "name": name,
                        "description": item.description,
                        "priority": "P2", "preconditions": [], "business_rules": [],
                    })
        except Exception as exc:
            logger.warning("[Auto] chunk 提取失败: %s", exc)
    await save_features(db, project_id, all_features)
    results["features"] = len(all_features)
    await update_project_status(db, project_id, "features_extracted")
    await db.commit()
    logger.info("[Auto] 功能点提取完成: %d 个", len(all_features))

    if not all_features:
        raise HTTPException(status_code=400, detail="未能提取到功能点")

    # ── Step 3: 生成测试点 (V2: 5并发 + Pydantic校验 + 重试) ──
    logger.info("[Auto] 开始生成测试点 (V2 5并发)...")
    import asyncio as _asyncio

    tp_service = TestPointService()
    all_testpoints: list[dict] = []
    _sem = _asyncio.Semaphore(8)

    async def _gen_tp(f):
        async with _sem:
            loop = _asyncio.get_running_loop()
            fname = f.get("name", "")
            fdesc = f.get("description", "")
            try:
                r = await loop.run_in_executor(
                    None, lambda: tp_service.generate(fname, fdesc)
                )
                return [(r.feature_name, tp.category, tp.description,
                         tp.expected_result, tp.test_data, tp.priority)
                        for tp in r.test_points]
            except Exception as exc:
                logger.warning("[Auto] 功能点 [%s] 测试点生成失败: %s", fname, exc)
                return []

    _tp_results = await _asyncio.gather(*[_gen_tp(f) for f in all_features])
    for _tps in _tp_results:
        for _fn, _cat, _desc, _exp, _data, _pri in _tps:
            all_testpoints.append({
                "feature_name": _fn, "category": _cat, "description": _desc,
                "expected_result": _exp, "test_data": _data, "priority": _pri,
            })

    await save_testpoints(db, project_id, all_testpoints)
    results["testpoints"] = len(all_testpoints)
    await update_project_status(db, project_id, "testpoints_generated")
    await db.commit()  # 分步提交
    logger.info("[Auto] 测试点生成完成: %d 个", len(all_testpoints))

    if not all_testpoints:
        raise HTTPException(status_code=400, detail="未能生成测试点")

    # ── Step 4: 生成测试用例 (V2: 10并发 + 小组合并) ──
    logger.info("[Auto] 开始生成测试用例 (V2 10并发)...")
    _groups: dict[str, list[dict]] = {}
    for tp in all_testpoints:
        fn = tp.get("feature_name", "未分类")
        _groups.setdefault(fn, []).append({
            "category": tp.get("category", "功能测试"),
            "description": tp.get("description", ""),
            "expected_result": tp.get("expected_result", ""),
            "test_data": tp.get("test_data", ""),
            "priority": tp.get("priority", "P1"),
        })

    # 合并小功能点组（≤3 测试点）批量调用
    _small = [(fn, tps) for fn, tps in _groups.items() if len(tps) <= 3]
    _merged = {fn: tps for fn, tps in _groups.items() if len(tps) > 3}
    while _small:
        batch = _small[:5]; _small = _small[5:]
        _mname = "、".join(fn for fn, _ in batch) if len(batch) > 1 else batch[0][0]
        _mtps = []
        for fn, tps in batch:
            for tp in tps:
                _mtps.append({**tp, "_source_feature": fn})
        _merged[_mname] = _mtps
    _groups = _merged

    tc_service = TestCaseService()
    all_testcases: list[dict] = []

    async def _gen_tc(fn: str, tps: list[dict]):
        async with _sem:
            loop = _asyncio.get_running_loop()
            try:
                cases = await loop.run_in_executor(
                    None, lambda: tc_service.generate(fn, tps)
                )
                # 推断 case_type：用关联测试点的分类
                categories = {tp.get("category", "") for tp in tps}
                if categories == {"功能测试"}: ct = "正向"
                elif categories & {"异常测试", "安全测试"}: ct = "逆向"
                elif categories == {"边界值测试"}: ct = "边界"
                else: ct = "正向"
                return [(fn, tc.id, tc.title, tc.precondition, tc.steps,
                         tc.expected_result, ct) for tc in cases]
            except Exception as exc:
                logger.warning("[Auto] 功能点 [%s] 用例生成失败: %s", fn, exc)
                return []

    _tc_items = list(_groups.items())
    _tc_results = await _asyncio.gather(*[_gen_tc(fn, tps) for fn, tps in _tc_items])
    for _tcs in _tc_results:
        for _fn, _cid, _title, _precond, _steps, _expected, _ct in _tcs:
            all_testcases.append({
                "testpoint_description": _fn, "case_id": _cid,
                "title": _title, "precondition": _precond,
                "steps": _steps, "expected": _expected,
                "priority": "P1", "case_type": _ct,
            })

    await save_testcases(db, project_id, all_testcases)
    results["testcases"] = len(all_testcases)
    await update_project_status(db, project_id, "testcases_generated")
    await db.commit()  # 分步提交
    logger.info("[Auto] 测试用例生成完成: %d 条", len(all_testcases))

    # ── Step 5: 导出 Excel (统一使用 dict) ────────
    logger.info("[Auto] 开始导出 Excel...")
    data = ExportData(
        project_name=project.name,
        features=[{
            "module": f.get("module", ""), "name": f.get("name", ""),
            "description": f.get("description", ""), "priority": f.get("priority", "P2"),
            "preconditions": f.get("preconditions", []), "business_rules": f.get("business_rules", []),
        } for f in all_features],
        testpoints=all_testpoints,
        testcases=all_testcases,
    )
    excel_exporter = ExcelExporter()
    filepath = excel_exporter.export(data)
    await update_project_status(db, project_id, "exported")
    logger.info("[Auto] Excel 导出完成: %s", filepath)

    return MessageResponse(
        ok=True,
        message="一键生成完成",
        data={
            **results,
            "excel_file": filepath.name,
            "excel_size": filepath.stat().st_size,
        },
    )
