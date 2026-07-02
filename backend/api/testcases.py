"""
测试用例 API
=============
AI 生成测试用例、列表查询、修改、删除。

V2.0: 使用 TestCaseService（按功能点分组生成 + Pydantic 校验 + 自动重试）
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.crud import (
    delete_testcase,
    get_project,
    get_testcases,
    get_testpoints,
    get_quality_review,
    save_testcases,
    save_quality_review,
    update_project_status,
    update_testcase,
    orm_to_dict,
)
from backend.db.database import get_db
from backend.models.schemas import (
    MessageResponse,
    TestCaseCreate,
    TestCaseUpdate,
)
from services.testcase_service import TestCaseService, TestCaseValidationError
from services.document_classifier import classify_document
from services.case_type import infer_case_priority, infer_case_type, source_priorities_for_case
from services.quality_review import build_quality_review, normalize_testcases

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["测试用例"])


@router.post("/{project_id}/testcases/generate", response_model=MessageResponse)
async def generate_testcases(
    project_id: int,
    mode: str = "auto",
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """AI 自动生成测试用例。mode: auto / api(接口测试) / functional(功能测试)。"""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # ── 防重复提交 ──────────────────────────────
    if project.status in ("extracting", "generating_testpoints", "generating_testcases"):
        raise HTTPException(
            status_code=409,
            detail=f"项目正在处理中，请等待完成后再试",
        )

    testpoint_orms = await get_testpoints(db, project_id)
    if not testpoint_orms:
        raise HTTPException(status_code=400, detail="请先生成测试点")

    doc_type = classify_document(project.doc_content or "")
    actual_mode = doc_type.mode if mode == "auto" else mode
    if actual_mode not in ("api", "functional"):
        raise HTTPException(status_code=400, detail="mode 仅支持 auto/api/functional")

    await update_project_status(db, project_id, "generating_testcases")
    await db.commit()  # commit 使状态对其他请求可见

    # ── 按功能点分组测试点 ──────────────────────────
    groups: dict[str, list[dict]] = {}
    for tp in testpoint_orms:
        fn = tp.feature_name or "未分类"
        groups.setdefault(fn, []).append({
            "category": tp.category,
            "description": tp.description,
            "expected_result": tp.expected_result or "",
            "test_data": tp.test_data or "",
            "priority": tp.priority or "P1",
        })

    # ── 效率优化：合并小功能点组批量调用 ──────────
    # ≤3 个测试点的组 5 个一批合并，减少 LLM 调用次数
    small_groups = [(fn, tps) for fn, tps in groups.items() if len(tps) <= 3]
    merged_groups = {fn: tps for fn, tps in groups.items() if len(tps) > 3}

    while small_groups:
        batch = small_groups[:5]
        small_groups = small_groups[5:]
        merged_name = "、".join(fn for fn, _ in batch) if len(batch) > 1 else batch[0][0]
        merged_tps = []
        for fn, tps in batch:
            for tp in tps:
                merged_tps.append({**tp, "_source_feature": fn})
        merged_groups[merged_name] = merged_tps

    original_count = len(groups)
    optimized_count = len(merged_groups)
    logger.info(
        "V2 测试用例生成: 项目=%s, 原始组数=%d → 优化后=%d (节省 %d 次调用)",
        project_id, original_count, optimized_count,
        original_count - optimized_count,
    )

    import asyncio

    service = TestCaseService()
    all_testcases: list[dict] = []
    errors: list[str] = []
    success_count = 0

    # 并发限制（15 个同时调用）
    semaphore = asyncio.Semaphore(15)

    async def _generate_one(feature_name: str, testpoints: list[dict]):
        """为单个功能点组/批次生成测试用例。"""
        async with semaphore:
            loop = asyncio.get_running_loop()
            try:
                cases = await loop.run_in_executor(
                    None,
                    lambda: service.generate(feature_name, testpoints, actual_mode),
                )
                # 合并批次时，testpoint_description 回溯到原始功能点
                source_map = {}
                for tp in testpoints:
                    src = tp.get("_source_feature", "")
                    if src:
                        source_map[tp["description"]] = src

                tcs = []
                for tc in cases:
                    # 尝试匹配回源功能点
                    desc = feature_name
                    for tp_desc, src_fn in source_map.items():
                        if tp_desc[:10] in tc.title or any(
                            tp_desc[:10] in s for s in tc.steps
                        ):
                            desc = src_fn
                            break
                    tcs.append({
                        "testpoint_description": desc,
                        "case_id": tc.id,
                        "title": tc.title,
                        "precondition": tc.precondition,
                        "steps": tc.steps,
                        "expected": tc.expected_result,
                        "priority": infer_case_priority(tc.title, expected=tc.expected_result, steps=tc.steps, source_priorities=source_priorities_for_case(tc.title, expected=tc.expected_result, steps=tc.steps, testpoints=testpoints), case_type=infer_case_type(tc.title, expected=tc.expected_result, steps=tc.steps, categories={tp.get("category", "") for tp in testpoints})),
                        "case_type": infer_case_type(tc.title, expected=tc.expected_result, steps=tc.steps, categories={tp.get("category", "") for tp in testpoints}),
                        "method": getattr(tc, "method", "") if actual_mode == "api" else "",
                        "url": getattr(tc, "url", "") if actual_mode == "api" else "",
                        "headers": getattr(tc, "headers", "") if actual_mode == "api" else "",
                        "body": (getattr(tc, "body", "") if actual_mode == "api" else getattr(tc, "test_data", "")) or "",
                    })
                logger.info(
                    "  [%s] → %d 条用例 (%d 测试点)",
                    feature_name[:60], len(tcs), len(testpoints),
                )
                return (feature_name, tcs, None)
            except TestCaseValidationError as exc:
                logger.warning("  [%s] 校验失败: %s", feature_name[:60], exc.message[:120])
                return (feature_name, None, f"{feature_name}: {exc.message[:100]}")
            except Exception as exc:
                logger.error("  [%s] 生成异常: %s", feature_name[:60], exc)
                return (feature_name, None, f"{feature_name}: {exc}")

    # 并发执行
    items = list(merged_groups.items())
    tasks = [_generate_one(fn, tps) for fn, tps in items]
    results = await asyncio.gather(*tasks)

    for name, tcs, err in results:
        if tcs is not None:
            all_testcases.extend(tcs)
            success_count += 1
        if err:
            errors.append(err)

    if not all_testcases:
        # 重置状态，防止卡在 processing 状态
        await update_project_status(db, project_id, "testpoints_generated")
        await db.commit()
        detail = "未能生成测试用例"
        if errors:
            detail += f"（{len(errors)} 个功能点失败）"
        return MessageResponse(
            ok=True,
            message=detail,
            data={"testcases": [], "errors": errors},
        )

    # ── 质量治理：去重、限量、重排编号、收敛 P0 ───────
    all_testcases, quality_metrics = normalize_testcases(
        all_testcases,
        mode=actual_mode,
    )
    review = build_quality_review(all_testcases)
    review["metrics"].update(quality_metrics)

    # ── 保存到数据库 ──────────────────────────────
    await save_testcases(db, project_id, all_testcases)
    await save_quality_review(db, project_id, review)
    await update_project_status(db, project_id, "testcases_generated")

    logger.info(
        "测试用例生成完成: %s 条用例 / %d/%d 功能点成功",
        len(all_testcases), success_count, len(groups),
    )

    logger.info("用例评审: 得分 %d, 通过=%s", review["score"], review["pass"])

    return MessageResponse(
        ok=True,
        message=(
            f"生成 {len(all_testcases)} 条用例 | "
            f"评审得分 {review['score']} 分{' ✅ 通过' if review['pass'] else ' ⚠️ 需改进'}"
        ),
        data={
            "count": len(all_testcases),
            "testcases": all_testcases,
            "success_features": success_count,
            "total_features": len(groups),
            "errors": errors,
            "review": review,
            "doc_type": doc_type.doc_type,
            "testcase_mode": actual_mode,
            "confidence": doc_type.confidence,
        },
    )


@router.get("/{project_id}/testcases/review", response_model=MessageResponse)
async def get_testcase_review(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """获取项目最新测试用例质量评审。"""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    review = await get_quality_review(db, project_id)
    if review:
        return MessageResponse(
            ok=True,
            message="获取成功",
            data={
                "score": review.score,
                "pass": review.passed,
                "summary": review.summary,
                "issues": review.issues,
                "suggestions": review.suggestions,
                "metrics": review.metrics,
                "created_at": review.created_at.isoformat() if review.created_at else "",
            },
        )

    testcases = [orm_to_dict(tc) for tc in await get_testcases(db, project_id)]
    generated_review = build_quality_review(testcases)
    await save_quality_review(db, project_id, generated_review)
    return MessageResponse(ok=True, message="已生成质量评审", data=generated_review)


@router.get("/{project_id}/testcases", response_model=MessageResponse)
async def list_testcases(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """获取项目的测试用例列表。

    Args:
        project_id: 项目 ID

    Returns:
        测试用例列表
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    testcases = await get_testcases(db, project_id)
    if testcases and project.status not in ("exporting", "exported"):
        await update_project_status(db, project_id, "testcases_generated")
        await db.commit()
    testcase_data = [orm_to_dict(tc) for tc in testcases]
    doc_type = classify_document(project.doc_content or "")
    if doc_type.mode == "api":
        from backend.api.export import _fill_api_endpoint_fields

        testcase_data = _fill_api_endpoint_fields(
            testcase_data,
            project.doc_content or "",
        )
    return MessageResponse(
        ok=True,
        message=f"共 {len(testcases)} 个测试用例",
        data={
            "testcases": testcase_data
        },
    )


@router.put(
    "/{project_id}/testcases/{testcase_id}",
    response_model=MessageResponse,
)
async def edit_testcase(
    project_id: int,
    testcase_id: int,
    update: TestCaseUpdate,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """人工修改测试用例。

    Args:
        project_id: 项目 ID
        testcase_id: 测试用例 ID
        update: 要更新的字段

    Returns:
        更新后的测试用例
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    update_data = update.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")

    tc = await update_testcase(db, project_id, testcase_id, update_data)
    if not tc:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    return MessageResponse(
        ok=True,
        message="测试用例已更新",
        data=orm_to_dict(tc),
    )


@router.post(
    "/{project_id}/testcases/add",
    response_model=MessageResponse,
    status_code=201,
)
async def add_testcase(
    project_id: int,
    testcase: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """人工新增测试用例。

    Args:
        project_id: 项目 ID
        testcase: 测试用例数据

    Returns:
        新建的测试用例
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    from backend.db.crud import insert_testcase
    new_tc = await insert_testcase(
        db, project_id, testcase.model_dump()
    )
    return MessageResponse(
        ok=True,
        message="测试用例已添加",
        data={"id": new_tc.id},
    )


@router.delete(
    "/{project_id}/testcases/{testcase_id}",
    response_model=MessageResponse,
)
async def remove_testcase(
    project_id: int,
    testcase_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """删除测试用例。

    Args:
        project_id: 项目 ID
        testcase_id: 测试用例 ID

    Returns:
        删除结果
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    success = await delete_testcase(db, project_id, testcase_id)
    if not success:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    return MessageResponse(ok=True, message="测试用例已删除")
