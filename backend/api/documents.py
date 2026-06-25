"""
文档管理 API
=============
文档上传、解析、获取。
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.crud import (
    create_project,
    delete_project,
    get_project,
    list_projects as list_all_projects,
    set_document_content,
)
from backend.db.database import get_db
from backend.models.schemas import MessageResponse, ProjectCreate, ProjectResponse
from services.document_parser import DocumentParser
from config import SUPPORTED_EXTENSIONS, UPLOAD_DIR, MAX_UPLOAD_SIZE_MB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["文档管理"])

# ── 文档解析器（全局单例）─────────────────────────
_doc_parser = DocumentParser()


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_new_project(
    body: ProjectCreate = ProjectCreate(),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """创建新项目。传入 name 则使用自定义名称，否则自动生成。"""
    import datetime
    name = body.name.strip()
    if not name:
        name = f"项目_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    project = await create_project(db, name)
    return ProjectResponse.model_validate(project)


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    """获取所有项目列表（按创建时间倒序）。"""
    projects = await list_all_projects(db)
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project_by_id(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """获取单个项目详情。"""
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", response_model=MessageResponse)
async def remove_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """删除项目及其所有关联数据。

    Args:
        project_id: 项目 ID

    Returns:
        删除结果
    """
    success = await delete_project(db, project_id)
    if not success:
        raise HTTPException(status_code=404, detail="项目不存在")
    return MessageResponse(ok=True, message="项目已删除")


@router.post("/{project_id}/upload", response_model=MessageResponse)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """上传需求文档并自动解析。

    Args:
        project_id: 项目 ID
        file: 上传的文件（.txt / .md / .docx / .pdf）

    Returns:
        解析结果
    """
    # ── 校验项目存在 ──────────────────────────────
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # ── 校验文件格式 ──────────────────────────────
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，仅支持 {', '.join(SUPPORTED_EXTENSIONS)}",
        )

    # ── 空文件检查 ──────────────────────────────
    content_bytes = await file.read()
    if not content_bytes or len(content_bytes.strip()) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空，请上传有效文档")

    # 文件大小限制
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大，最大支持 {MAX_UPLOAD_SIZE_MB}MB",
        )

    save_path = UPLOAD_DIR / f"project_{project_id}{ext}"
    save_path.write_bytes(content_bytes)

    # ── 解析文档 ──────────────────────────────────
    try:
        parsed_doc = _doc_parser.parse(save_path)
    except Exception as exc:
        logger.error("文档解析失败: %s", exc)
        raise HTTPException(
            status_code=500, detail="文档解析失败，请检查文件格式是否正确"
        )

    # ── 保存到数据库 ──────────────────────────────
    await set_document_content(
        db, project_id, file.filename, parsed_doc.full_text
    )

    return MessageResponse(
        ok=True,
        message=f"文档上传并解析成功",
        data={
            "filename": file.filename,
            "char_count": parsed_doc.char_count,
            "chunks": len(parsed_doc.chunks),
            "page_count": parsed_doc.page_count,
        },
    )


@router.get("/{project_id}/document", response_model=MessageResponse)
async def get_document_content(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """获取项目的文档内容。

    Args:
        project_id: 项目 ID

    Returns:
        文档内容
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if not project.doc_content:
        raise HTTPException(status_code=404, detail="该项目尚未上传文档")

    # 只返回前 5000 字符用于预览
    preview = project.doc_content[:5000]

    return MessageResponse(
        ok=True,
        message="获取成功",
        data={
            "filename": project.doc_filename,
            "content_preview": preview,
            "char_count": len(project.doc_content),
            "full_content": project.doc_content,
        },
    )
