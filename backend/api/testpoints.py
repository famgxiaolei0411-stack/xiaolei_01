"""
测试点 API
===========
AI 生成测试点、列表查询、修改、删除。

V2.0: 使用 TestPointService（逐功能点生成 + Pydantic 校验 + 自动重试）
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.crud import (
    delete_testpoint,
    get_features,
    get_project,
    get_testpoints,
    save_testpoints,
    update_project_status,
    update_testpoint,
    orm_to_dict,
)
from backend.db.database import get_db
from backend.models.schemas import (
    MessageResponse,
    TestPointCreate,
    TestPointUpdate,
)
from services.testpoint_service import TestPointService, TestPointValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["测试点"])


@router.post("/{project_id}/testpoints/generate", response_model=MessageResponse)
async def generate_testpoints(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """AI 自动生成测试点（V2 引擎）。

    逐功能点调用 TestPointService，每个功能点独立生成四维度测试点。
    优势：单次载荷小 → JSON 解析稳定 + Pydantic 校验 + 最多 3 次重试。

    Args:
        project_id: 项目 ID

    Returns:
        生成的测试点列表
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # ── 防重复提交 ──────────────────────────────
    if project.status in ("extracting", "generating_testpoints", "generating_testcases"):
        raise HTTPException(
            status_code=409,
            detail=f"项目正在处理中，请等待完成后再试",
        )

    feature_orms = await get_features(db, project_id)
    if not feature_orms:
        raise HTTPException(status_code=400, detail="请先提取功能点")

    await update_project_status(db, project_id, "generating_testpoints")
    await db.commit()  # commit 使状态对其他请求可见

    logger.info("V2 测试点生成: 项目=%s, 功能点数=%d", project_id, len(feature_orms))

    import asyncio

    service = TestPointService()
    all_testpoints: list[dict] = []
    errors: list[str] = []
    success_count = 0

    # 并发限制（12 个同时调用）
    semaphore = asyncio.Semaphore(12)

    async def _generate_one(f) -> tuple[str, list[dict] | None, str | None]:
        """为单个功能点生成测试点（在线程池中执行以避免阻塞）。"""
        async with semaphore:
            loop = asyncio.get_running_loop()
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda: service.generate(f.name, f.description or ""),
                )
                tps = []
                for tp in result.test_points:
                    tps.append({
                        "feature_name": result.feature_name,
                        "category": tp.category,
                        "description": tp.description,
                        "expected_result": tp.expected_result,
                        "test_data": tp.test_data,
                        "priority": tp.priority,
                    })
                logger.info("  功能点 [%s] → %d 个测试点", f.name, len(tps))
                return (f.name, tps, None)
            except TestPointValidationError as exc:
                logger.warning("  功能点 [%s] 校验失败: %s", f.name, exc.message[:120])
                return (f.name, None, f"{f.name}: {exc.message[:100]}")
            except Exception as exc:
                logger.error("  功能点 [%s] 生成异常: %s", f.name, exc)
                return (f.name, None, f"{f.name}: {exc}")

    # 并发执行
    tasks = [_generate_one(f) for f in feature_orms]
    results = await asyncio.gather(*tasks)

    for name, tps, err in results:
        if tps is not None:
            all_testpoints.extend(tps)
            success_count += 1
        if err:
            errors.append(err)

    if not all_testpoints:
        # 重置状态，防止卡在 processing 状态
        await update_project_status(db, project_id, "features_extracted")
        await db.commit()
        detail = "未能生成测试点"
        if errors:
            detail += f"（{len(errors)} 个功能点失败）"
        return MessageResponse(
            ok=True,
            message=detail,
            data={"testpoints": [], "errors": errors},
        )

    # ── 保存到数据库 ──────────────────────────────
    await save_testpoints(db, project_id, all_testpoints)
    await update_project_status(db, project_id, "testpoints_generated")

    logger.info(
        "测试点生成完成: %s 个测试点 / %d/%d 功能点成功",
        len(all_testpoints), success_count, len(feature_orms),
    )

    return MessageResponse(
        ok=True,
        message=(
            f"成功生成 {len(all_testpoints)} 个测试点"
            f"（{success_count}/{len(feature_orms)} 功能点）"
        ),
        data={
            "count": len(all_testpoints),
            "testpoints": all_testpoints,
            "success_features": success_count,
            "total_features": len(feature_orms),
            "errors": errors,
        },
    )


@router.get("/{project_id}/testpoints", response_model=MessageResponse)
async def list_testpoints(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """获取项目的测试点列表。

    Args:
        project_id: 项目 ID

    Returns:
        测试点列表
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    testpoints = await get_testpoints(db, project_id)
    return MessageResponse(
        ok=True,
        message=f"共 {len(testpoints)} 个测试点",
        data={
            "testpoints": [orm_to_dict(tp) for tp in testpoints]
        },
    )


@router.put(
    "/{project_id}/testpoints/{testpoint_id}",
    response_model=MessageResponse,
)
async def edit_testpoint(
    project_id: int,
    testpoint_id: int,
    update: TestPointUpdate,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """人工修改测试点。

    Args:
        project_id: 项目 ID
        testpoint_id: 测试点 ID
        update: 要更新的字段

    Returns:
        更新后的测试点
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    update_data = update.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")

    tp = await update_testpoint(db, project_id, testpoint_id, update_data)
    if not tp:
        raise HTTPException(status_code=404, detail="测试点不存在")

    return MessageResponse(
        ok=True,
        message="测试点已更新",
        data=orm_to_dict(tp),
    )


@router.post(
    "/{project_id}/testpoints/add",
    response_model=MessageResponse,
    status_code=201,
)
async def add_testpoint(
    project_id: int,
    testpoint: TestPointCreate,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """人工新增测试点。

    Args:
        project_id: 项目 ID
        testpoint: 测试点数据

    Returns:
        新建的测试点
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    from backend.db.crud import insert_testpoint
    new_tp = await insert_testpoint(
        db, project_id, testpoint.model_dump()
    )
    return MessageResponse(
        ok=True,
        message="测试点已添加",
        data={"id": new_tp.id},
    )


@router.delete(
    "/{project_id}/testpoints/{testpoint_id}",
    response_model=MessageResponse,
)
async def remove_testpoint(
    project_id: int,
    testpoint_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """删除测试点。

    Args:
        project_id: 项目 ID
        testpoint_id: 测试点 ID

    Returns:
        删除结果
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    success = await delete_testpoint(db, project_id, testpoint_id)
    if not success:
        raise HTTPException(status_code=404, detail="测试点不存在")

    return MessageResponse(ok=True, message="测试点已删除")
