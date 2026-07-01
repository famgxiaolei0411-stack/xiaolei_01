"""
导出 API
=========
Excel 导出与文件下载。
"""

import logging
import re
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
from services.document_classifier import classify_document
from services.excel_exporter import ExportData, ExcelExporter
from services.progress_state import get_progress, set_progress
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["导出"])


@router.post("/{project_id}/export", response_model=ExportResponse)
async def export_to_excel(
    project_id: int,
    options: ExportOptions = ExportOptions(),
    db: AsyncSession = Depends(get_db),
) -> ExportResponse:
    """导出项目数据（支持 Excel / JSON / Markdown）。"""
    fmt = getattr(options, "format", "excel") or "excel"

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
        filepath = _export_excel(project, feature_orms, testpoint_orms, testcase_orms, options)

    await update_project_status(db, project_id, "exported")
    await db.commit()

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
    """下载生成的 Excel 文件。"""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    file_path = (OUTPUT_DIR / filename).resolve()
    output_root = OUTPUT_DIR.resolve()
    if output_root not in file_path.parents and file_path != output_root:
        raise HTTPException(status_code=400, detail="无效的文件名")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    safe_project_name = "".join(
        c if c.isalnum() or c in "._- " else "_"
        for c in project.name
    )
    if safe_project_name and not file_path.name.startswith(f"{safe_project_name}_"):
        raise HTTPException(status_code=403, detail="无权下载该文件")

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


def _export_excel(project, feature_orms, testpoint_orms, testcase_orms, options):
    doc_type = classify_document(project.doc_content or "")
    testcase_mode = options.testcase_mode if options.testcase_mode != "auto" else doc_type.mode
    testcases = _orm_to_tc_dicts(testcase_orms)
    if testcase_mode == "api":
        testcases = _fill_api_endpoint_fields(testcases, project.doc_content or "")
    data = ExportData(
        project_name=project.name,
        features=_orm_to_feat_dicts(feature_orms) if options.include_features else [],
        testpoints=_orm_to_tp_dicts(testpoint_orms) if options.include_testpoints else [],
        testcases=testcases,
        testcase_mode=testcase_mode,
    )
    return ExcelExporter().export(data)


@router.get("/{project_id}/progress", response_model=MessageResponse)
async def get_project_progress(project_id: int) -> MessageResponse:
    """获取长任务当前进度。"""
    return MessageResponse(ok=True, message="获取成功", data=get_progress(project_id))


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
        for item in feats:
            lines.append(f"- **{item['name']}** [{item['priority']}] — {item['description']}")
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
        lines.append(f"- **优先级**: {tc['priority']} | **类型**: {tc.get('case_type', '-')}" )
        lines.append(f"- **前置条件**: {tc.get('precondition', '无')}")
        lines.append(f"- **步骤**:\n{steps_text}")
        lines.append(f"- **预期结果**: {tc.get('expected', '')}")
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def _orm_to_feat_dicts(orms):
    return [{
        "module": item.module,
        "name": item.name,
        "description": item.description,
        "priority": item.priority,
        "preconditions": item.preconditions,
        "business_rules": item.business_rules,
    } for item in orms]


def _orm_to_tp_dicts(orms):
    return [{
        "feature_name": item.feature_name,
        "category": item.category,
        "description": item.description,
        "expected_result": item.expected_result,
        "test_data": item.test_data or "",
        "priority": item.priority,
    } for item in orms]


def _orm_to_tc_dicts(orms):
    from backend.db.crud import orm_to_dict
    return [orm_to_dict(item) for item in orms]


def _fill_api_endpoint_fields(testcases: list[dict], doc_content: str) -> list[dict]:
    """从接口文档中回填历史用例缺失的 Method/URL 字段。"""
    endpoints = _extract_api_endpoints(doc_content)
    if not endpoints:
        return testcases

    for testcase in testcases:
        title = testcase.get("title", "") or ""
        module = testcase.get("testpoint_description", "") or ""
        search_text = f"{testcase.get('module', '')} {module} {title}"
        matched = next(
            (
                item for item in endpoints
                if item["name"] and item["name"] in search_text
            ),
            None,
        )
        if not matched:
            continue
        if not testcase.get("method"):
            testcase["method"] = matched["method"]
        if not testcase.get("url"):
            testcase["url"] = matched["url"]
    return testcases


def _extract_api_endpoints(doc_content: str) -> list[dict]:
    endpoints: list[dict] = []
    pattern = re.compile(r"(?m)^#{2,6}\s+(.+?)\s*$")
    matches = list(pattern.finditer(doc_content or ""))
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(doc_content)
        section = doc_content[start:end]
        url_match = re.search(r"\b(?:path|url)\s*:[\s*`]*(/[^\s*`]+)", section, re.IGNORECASE)
        method_match = re.search(
            r"\b(?:type|method|请求方法|请求方式)\s*:[\s*`]*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\b",
            section,
            re.IGNORECASE,
        )
        if url_match:
            endpoints.append({
                "name": name,
                "url": url_match.group(1).strip(),
                "method": method_match.group(1).upper() if method_match else "",
            })
    return endpoints


def _format_generation_error(stage: str, exc: Exception) -> str:
    detail = str(exc).strip() or exc.__class__.__name__
    return f"{stage}: {detail}"


@router.post("/{project_id}/auto-generate", response_model=MessageResponse)
async def auto_generate_all(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """一键自动生成全部内容：功能点 → 测试点 → 测试用例 → Excel。"""
    import asyncio as _asyncio

    from services.ai_client import (
        AIConfigurationError,
        AIRequestError,
        AIResponseParseError,
        get_ai_client,
    )
    from services.document_parser import DocumentParser, ParsedDocument
    from services.feature_service import FeatureService, FeatureValidationError
    from services.testpoint_service import TestPointService, TestPointValidationError
    from services.testcase_service import TestCaseService, TestCaseValidationError
    from services.case_type import infer_case_priority, infer_case_type, source_priorities_for_case
    from services.document_classifier import classify_document

    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.doc_content:
        raise HTTPException(status_code=400, detail="请先上传需求文档")

    try:
        ai_client = get_ai_client()
    except AIConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results: dict[str, int] = {}
    doc_type = classify_document(project.doc_content)
    set_progress(
        project_id, "classifying",
        f"已识别为{doc_type.doc_type}，准备按{'接口测试' if doc_type.mode == 'api' else '功能测试'}生成",
        1, 5,
        {"doc_type": doc_type.doc_type, "testcase_mode": doc_type.mode},
    )

    parser_inst = DocumentParser()
    parsed_doc = ParsedDocument(
        filename=project.doc_filename or "unknown",
        file_type=".txt",
        full_text=project.doc_content,
        char_count=len(project.doc_content),
        chunks=parser_inst._chunk_text(project.doc_content),
    )

    try:
        logger.info("[Auto] 开始提取功能点")
        set_progress(project_id, "extracting", "正在提取功能点", 1, 5)
        feat_service = FeatureService(ai_client)
        from backend.api.features import _infer_feature_module
        all_features: list[dict] = []
        seen: set[str] = set()
        feature_errors: list[str] = []
        is_api_doc = doc_type.mode == "api"

        for chunk in parsed_doc.chunks:
            try:
                result = feat_service.extract(chunk.content)
                for item in result.features:
                    name = item.name.strip()
                    if name and name not in seen:
                        seen.add(name)
                        module = "未分类"
                        if is_api_doc:
                            module = _infer_feature_module(
                                name,
                                item.description,
                                project.doc_content or "",
                            )
                        all_features.append({
                            "module": module,
                            "name": name,
                            "description": item.description,
                            "priority": "P2",
                            "preconditions": [],
                            "business_rules": [],
                        })
            except (AIRequestError, AIResponseParseError, FeatureValidationError) as exc:
                logger.warning("[Auto] chunk 功能点提取失败: %s", exc)
                feature_errors.append(_format_generation_error("功能点提取失败", exc))

        if not all_features:
            detail = feature_errors[0] if feature_errors else "未能提取到功能点"
            raise HTTPException(status_code=502, detail=detail)

        await save_features(db, project_id, all_features)
        results["features"] = len(all_features)
        await update_project_status(db, project_id, "features_extracted")
        logger.info("[Auto] 功能点提取完成: %d 个", len(all_features))
        set_progress(project_id, "generating_testpoints", f"功能点提取完成：{len(all_features)} 个，正在生成测试点", 2, 5)

        logger.info("[Auto] 开始生成测试点")
        tp_service = TestPointService(ai_client)
        all_testpoints: list[dict] = []
        tp_errors: list[str] = []
        sem = _asyncio.Semaphore(8)

        async def _gen_tp(feature: dict) -> tuple[list[dict], str | None]:
            async with sem:
                loop = _asyncio.get_running_loop()
                fname = feature.get("name", "")
                fdesc = feature.get("description", "")
                try:
                    result = await loop.run_in_executor(
                        None, lambda: tp_service.generate(fname, fdesc)
                    )
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
                    logger.warning("[Auto] 功能点 [%s] 测试点生成失败: %s", fname, exc)
                    return [], _format_generation_error(f"测试点生成失败（{fname}）", exc)

        tp_results = await _asyncio.gather(*[_gen_tp(feature) for feature in all_features])
        for items, error in tp_results:
            all_testpoints.extend(items)
            if error:
                tp_errors.append(error)

        if not all_testpoints:
            detail = tp_errors[0] if tp_errors else "未能生成测试点"
            raise HTTPException(status_code=502, detail=detail)

        await save_testpoints(db, project_id, all_testpoints)
        results["testpoints"] = len(all_testpoints)
        await update_project_status(db, project_id, "testpoints_generated")
        logger.info("[Auto] 测试点生成完成: %d 个", len(all_testpoints))
        set_progress(project_id, "generating_testcases", f"测试点生成完成：{len(all_testpoints)} 个，正在生成测试用例", 3, 5)

        logger.info("[Auto] 开始生成测试用例")
        groups: dict[str, list[dict]] = {}
        for tp in all_testpoints:
            feature_name = tp.get("feature_name", "未分类")
            groups.setdefault(feature_name, []).append({
                "category": tp.get("category", "功能测试"),
                "description": tp.get("description", ""),
                "expected_result": tp.get("expected_result", ""),
                "test_data": tp.get("test_data", ""),
                "priority": tp.get("priority", "P1"),
            })

        small = [(name, items) for name, items in groups.items() if len(items) <= 3]
        merged = {name: items for name, items in groups.items() if len(items) > 3}
        while small:
            batch = small[:5]
            small = small[5:]
            merged_name = "、".join(name for name, _ in batch) if len(batch) > 1 else batch[0][0]
            merged_items = []
            for name, items in batch:
                for item in items:
                    merged_items.append({**item, "_source_feature": name})
            merged[merged_name] = merged_items

        tc_service = TestCaseService(ai_client)
        all_testcases: list[dict] = []
        tc_errors: list[str] = []

        async def _gen_tc(feature_name: str, test_points: list[dict]) -> tuple[list[dict], str | None]:
            async with sem:
                loop = _asyncio.get_running_loop()
                try:
                    cases = await loop.run_in_executor(
                        None,
                        lambda: tc_service.generate(feature_name, test_points, doc_type.mode),
                    )
                    categories = {item.get("category", "") for item in test_points}

                    items = [{
                        "testpoint_description": feature_name,
                        "case_id": case.id,
                        "title": case.title,
                        "precondition": case.precondition,
                        "steps": case.steps,
                        "expected": case.expected_result,
                        "body": (getattr(case, "body", "") if doc_type.mode == "api" else getattr(case, "test_data", "")) or "",
                        "method": getattr(case, "method", "") if doc_type.mode == "api" else "",
                        "url": getattr(case, "url", "") if doc_type.mode == "api" else "",
                        "headers": getattr(case, "headers", "") if doc_type.mode == "api" else "",
                        "priority": infer_case_priority(case.title, expected=case.expected_result, steps=case.steps, source_priorities=source_priorities_for_case(case.title, expected=case.expected_result, steps=case.steps, testpoints=test_points), case_type=infer_case_type(case.title, expected=case.expected_result, steps=case.steps, categories=categories)),
                        "case_type": infer_case_type(case.title, expected=case.expected_result, steps=case.steps, categories=categories),
                    } for case in cases]
                    return items, None
                except (AIRequestError, AIResponseParseError, TestCaseValidationError) as exc:
                    logger.warning("[Auto] 功能点 [%s] 用例生成失败: %s", feature_name, exc)
                    return [], _format_generation_error(f"测试用例生成失败（{feature_name}）", exc)

        tc_results = await _asyncio.gather(*[
            _gen_tc(feature_name, test_points) for feature_name, test_points in merged.items()
        ])
        for items, error in tc_results:
            all_testcases.extend(items)
            if error:
                tc_errors.append(error)

        if not all_testcases:
            detail = tc_errors[0] if tc_errors else "未能生成测试用例"
            raise HTTPException(status_code=502, detail=detail)

        await save_testcases(db, project_id, all_testcases)
        results["testcases"] = len(all_testcases)
        await update_project_status(db, project_id, "testcases_generated")
        logger.info("[Auto] 测试用例生成完成: %d 条", len(all_testcases))
        set_progress(project_id, "exporting", f"测试用例生成完成：{len(all_testcases)} 条，正在导出 Excel", 4, 5)

        logger.info("[Auto] 开始导出 Excel")
        data = ExportData(
            project_name=project.name,
            features=[{
                "module": item.get("module", ""),
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "priority": item.get("priority", "P2"),
                "preconditions": item.get("preconditions", []),
                "business_rules": item.get("business_rules", []),
            } for item in all_features],
            testpoints=all_testpoints,
            testcases=all_testcases,
            testcase_mode=doc_type.mode,
        )
        filepath = ExcelExporter().export(data)
        await update_project_status(db, project_id, "exported")
        await db.commit()
        logger.info("[Auto] Excel 导出完成: %s", filepath)
        set_progress(
            project_id,
            "exported",
            "全流程完成",
            5,
            5,
            {"excel_file": filepath.name, "testcase_mode": doc_type.mode},
        )

        return MessageResponse(
            ok=True,
            message="一键生成完成",
            data={
                **results,
                "excel_file": filepath.name,
                "excel_size": filepath.stat().st_size,
                "doc_type": doc_type.doc_type,
                "testcase_mode": doc_type.mode,
                "confidence": doc_type.confidence,
            },
        )

    except HTTPException:
        await db.rollback()
        set_progress(project_id, "failed", "生成失败，请查看错误信息", 0, 5)
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("[Auto] 一键生成未预期失败: %s", exc)
        set_progress(project_id, "failed", "一键生成失败，请稍后重试", 0, 5)
        raise HTTPException(status_code=500, detail="一键生成失败，请稍后重试") from exc
