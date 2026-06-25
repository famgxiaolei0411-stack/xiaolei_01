"""
功能点 API
===========
AI 提取功能点、列表查询、修改、删除。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.crud import (
    delete_feature,
    get_features,
    get_project,
    save_features,
    update_feature,
    update_project_status,
)
from backend.db.database import get_db
from backend.models.schemas import (
    FeatureCreate,
    FeatureResponse,
    FeatureUpdate,
    MessageResponse,
)
from services.document_parser import DocumentParser, ParsedDocument
from services.feature_service import FeatureService, FeatureValidationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["功能点"])


@router.post("/{project_id}/features/extract", response_model=MessageResponse)
async def extract_features(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """AI 自动提取功能点。

    流程:
    1. 从数据库获取文档内容
    2. 分块调用 AI 提取功能点
    3. 自动去重后保存到数据库

    Args:
        project_id: 项目 ID

    Returns:
        提取的功能点列表
    """
    # ── 获取项目文档 ──────────────────────────────
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not project.doc_content:
        raise HTTPException(
            status_code=400, detail="请先上传需求文档"
        )

    # ── 防重复提交 ──────────────────────────────
    if project.status in ("extracting", "generating_testpoints", "generating_testcases"):
        raise HTTPException(
            status_code=409,
            detail=f"项目正在处理中，请等待完成后再试",
        )
    await update_project_status(db, project_id, "extracting")
    await db.commit()  # commit 使状态对其他请求可见，防止并发重复提交

    # ── 分块文档 ──────────────────────────────────
    parser = DocumentParser()
    chunks = parser._chunk_text(project.doc_content)
    logger.info("V2 功能点提取: 项目=%s, 分块数=%d", project_id, len(chunks))

    # ── V2 AI 提取（5 并发逐块调用 + Pydantic 校验 + 重试）──
    import asyncio as _asyncio
    service = FeatureService()
    all_features: list[dict] = []
    seen_names: set[str] = set()
    _feat_sem = _asyncio.Semaphore(5)

    async def _extract_chunk(i: int, chunk) -> list[dict]:
        async with _feat_sem:
            loop = _asyncio.get_running_loop()
            try:
                result = await loop.run_in_executor(
                    None, lambda: service.extract(chunk.content)
                )
                items = []
                for item in result.features:
                    name = item.name.strip()
                    if name:
                        items.append({
                            "module": "未分类", "name": name,
                            "description": item.description, "priority": "P2",
                            "preconditions": [], "business_rules": [],
                        })
                logger.info("  Chunk %d/%d → %d 个功能点", i + 1, len(chunks), len(items))
                return items
            except FeatureValidationError as exc:
                logger.warning("  Chunk %d/%d 校验失败: %s", i + 1, len(chunks), exc.message[:120])
                return []
            except Exception as exc:
                logger.error("  Chunk %d/%d 提取异常: %s", i + 1, len(chunks), exc)
                return []

    _feat_results = await _asyncio.gather(*[
        _extract_chunk(i, c) for i, c in enumerate(chunks)
    ])
    for items in _feat_results:
        for item in items:
            if item["name"] not in seen_names:
                seen_names.add(item["name"])
                all_features.append(item)

    if not all_features:
        await update_project_status(db, project_id, "parsed")
        await db.commit()
        return MessageResponse(
            ok=True,
            message="未能提取到功能点，请检查文档内容是否清晰",
            data={"features": []},
        )

    # ── 保存到数据库 ──────────────────────────────
    await save_features(db, project_id, all_features)
    await update_project_status(db, project_id, "features_extracted")

    return MessageResponse(
        ok=True,
        message=f"成功提取 {len(all_features)} 个功能点",
        data={
            "count": len(all_features),
            "features": all_features,
        },
    )


@router.get("/{project_id}/features", response_model=MessageResponse)
async def list_features(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """获取项目的功能点列表。

    Args:
        project_id: 项目 ID

    Returns:
        功能点列表
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    features = await get_features(db, project_id)
    return MessageResponse(
        ok=True,
        message=f"共 {len(features)} 个功能点",
        data={
            "features": [
                {
                    "id": f.id,
                    "module": f.module,
                    "name": f.name,
                    "description": f.description,
                    "priority": f.priority,
                    "preconditions": f.preconditions,
                    "business_rules": f.business_rules,
                }
                for f in features
            ]
        },
    )


@router.put("/{project_id}/features/{feature_id}", response_model=MessageResponse)
async def edit_feature(
    project_id: int,
    feature_id: int,
    update: FeatureUpdate,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """人工修改功能点。

    Args:
        project_id: 项目 ID
        feature_id: 功能点 ID
        update: 要更新的字段

    Returns:
        更新后的功能点
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 只传非 None 的字段
    update_data = update.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="没有要更新的字段")

    feature = await update_feature(db, feature_id, update_data)
    if not feature:
        raise HTTPException(status_code=404, detail="功能点不存在")

    return MessageResponse(
        ok=True,
        message="功能点已更新",
        data={
            "id": feature.id,
            "module": feature.module,
            "name": feature.name,
            "description": feature.description,
            "priority": feature.priority,
            "preconditions": feature.preconditions,
            "business_rules": feature.business_rules,
        },
    )


@router.post(
    "/{project_id}/features/add", response_model=MessageResponse, status_code=201
)
async def add_feature(
    project_id: int,
    feature: FeatureCreate,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """人工新增功能点。

    Args:
        project_id: 项目 ID
        feature: 功能点数据

    Returns:
        新建的功能点
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    feature_data = feature.model_dump()
    from backend.db.crud import insert_feature
    new_feature = await insert_feature(db, project_id, feature_data)

    return MessageResponse(
        ok=True,
        message="功能点已添加",
        data={
            "id": new_feature.id,
        },
    )


@router.delete("/{project_id}/features/{feature_id}", response_model=MessageResponse)
async def remove_feature(
    project_id: int,
    feature_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """删除功能点。

    Args:
        project_id: 项目 ID
        feature_id: 功能点 ID

    Returns:
        删除结果
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    success = await delete_feature(db, feature_id)
    if not success:
        raise HTTPException(status_code=404, detail="功能点不存在")

    return MessageResponse(ok=True, message="功能点已删除")
