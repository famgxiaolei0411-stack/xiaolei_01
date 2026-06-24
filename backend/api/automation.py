"""
自动化测试 API
===============
生成 Pytest 脚本 → 执行测试 → 查看 Allure 报告。
"""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.crud import get_project, get_testcases
from backend.db.database import get_db
from backend.models.schemas import MessageResponse
from config import GENERATED_TESTS_DIR, ALLURE_REPORT_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["自动化测试"])


# ══════════════════════════════════════════════════════════
# 请求模型
# ══════════════════════════════════════════════════════════

class ScriptGenRequest(BaseModel):
    """测试脚本生成请求。"""
    module_name: str = Field(default="通用模块", max_length=200)
    base_url: str = Field(default="http://localhost:8000", max_length=500)


class TestRunRequest(BaseModel):
    """测试执行请求。"""
    project_dir: str = Field(..., min_length=1, max_length=500, description="测试框架项目目录路径")


# ══════════════════════════════════════════════════════════
# 端点
# ══════════════════════════════════════════════════════════

@router.post("/{project_id}/automation/generate-script", response_model=MessageResponse)
async def generate_test_script(
    project_id: int,
    options: ScriptGenRequest = ScriptGenRequest(),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """将已生成的测试用例转换为 Pytest + Allure 测试脚本。

    从数据库读取测试用例 → 生成可执行 .py 脚本 → 写入 generated_tests/

    Args:
        project_id: 项目 ID
        options: 模块名、base_url 等选项

    Returns:
        生成的脚本路径和用例数
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # ── 读取测试用例 ──────────────────────────────
    tc_orms = await get_testcases(db, project_id)
    if not tc_orms:
        raise HTTPException(status_code=400, detail="请先生成测试用例")

    # 转为字典列表
    from backend.db.crud import orm_to_dict
    testcases = [orm_to_dict(tc) for tc in tc_orms]

    try:
        from services.test_script_generator import TestFrameworkGenerator, ScriptOptions

        gen = TestFrameworkGenerator()
        gen_opts = ScriptOptions(
            module_name=options.module_name or project.name,
            base_url=options.base_url,
        )
        framework_dir = gen.generate(testcases, gen_opts)

        return MessageResponse(
            ok=True,
            message=f"测试框架生成成功",
            data={
                "project_dir": str(framework_dir),
                "project_name": framework_dir.name,
                "testcase_count": len(testcases),
                "module_name": gen_opts.module_name,
            },
        )
    except Exception as exc:
        logger.error("脚本生成失败: %s", exc)
        raise HTTPException(status_code=500, detail="测试脚本生成失败，请稍后重试")


@router.post("/{project_id}/automation/run", response_model=MessageResponse)
async def run_test(
    project_id: int,
    request: TestRunRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """执行生成的 pytest 测试脚本，产出 Allure 报告。

    Args:
        project_id: 项目 ID
        request: 测试文件名

    Returns:
        测试执行报告（统计 + Allure 路径）
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    project_dir = Path(request.project_dir)
    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"测试项目不存在: {request.project_dir}。请先生成框架。"
        )

    try:
        from services.test_executor import TestExecutor

        executor = TestExecutor()
        report = executor.run(project_dir)

        return MessageResponse(
            ok=True,
            message="测试执行完成",
            data={
                **report.to_dict(),
                "summary": report.summary,
                "project_dir": str(project_dir),
                "allure_report_url": f"/api/v1/projects/{project_id}/automation/report",
            },
        )
    except Exception as exc:
        logger.error("测试执行失败: %s", exc)
        raise HTTPException(status_code=500, detail="测试执行失败，请检查脚本是否正确")


@router.get("/{project_id}/automation/report", response_model=None)
async def view_allure_report(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """返回 Allure HTML 报告 index.html。

    Args:
        project_id: 项目 ID

    Returns:
        Allure 报告的 index.html 文件
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    index_path = ALLURE_REPORT_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Allure 报告不存在，请先执行测试",
        )

    return FileResponse(
        path=str(index_path),
        media_type="text/html",
    )


@router.post("/{project_id}/automation/pipeline", response_model=MessageResponse)
async def run_full_pipeline(
    project_id: int,
    options: ScriptGenRequest = ScriptGenRequest(),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """一键自动化测试管线：生成脚本 → 执行 → 报告。

    Args:
        project_id: 项目 ID
        options: 模块名、base_url

    Returns:
        完整的测试执行报告
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # ── 读取测试用例 ──────────────────────────────
    tc_orms = await get_testcases(db, project_id)
    if not tc_orms:
        raise HTTPException(status_code=400, detail="请先生成测试用例")

    from backend.db.crud import orm_to_dict
    testcases = [orm_to_dict(tc) for tc in tc_orms]

    try:
        from services.test_script_generator import TestFrameworkGenerator, ScriptOptions
        from services.test_executor import TestExecutor

        # ── Step 1: 生成框架 ──────────────────────
        gen = TestFrameworkGenerator()
        gen_opts = ScriptOptions(
            module_name=options.module_name or project.name,
            base_url=options.base_url,
        )
        framework_dir = gen.generate(testcases, gen_opts)

        # ── Step 2: 执行测试 ──────────────────────
        executor = TestExecutor()
        report = executor.run(framework_dir)

        return MessageResponse(
            ok=True,
            message="自动化测试管线执行完成",
            data={
                **report.to_dict(),
                "summary": report.summary,
                "project_dir": str(framework_dir),
                "testcase_count": len(testcases),
                "allure_report_url": f"/api/v1/projects/{project_id}/automation/report",
            },
        )
    except Exception as exc:
        logger.error("自动化测试管线失败: %s", exc)
        raise HTTPException(status_code=500, detail="自动化管线执行失败，请稍后重试")


@router.get("/{project_id}/automation/scripts", response_model=MessageResponse)
async def list_scripts(
    project_id: int,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """列出已生成的测试脚本。

    Args:
        project_id: 项目 ID

    Returns:
        脚本文件列表
    """
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    scripts = []
    if GENERATED_TESTS_DIR.exists():
        # 列出框架项目目录（包含 case/ 子目录的）
        for d in sorted(GENERATED_TESTS_DIR.iterdir()):
            if d.is_dir() and (d / "run.py").exists():
                stat = d.stat()
                # 统计用例数和文件数
                case_count = 0
                if (d / "case").exists():
                    case_count = len(list((d / "case").glob("test_*.py")))
                scripts.append({
                    "project_name": d.name,
                    "project_dir": str(d),
                    "case_files": case_count,
                    "modified": stat.st_mtime,
                })

    return MessageResponse(
        ok=True,
        message=f"共 {len(scripts)} 个测试框架",
        data={"scripts": scripts},
    )


@router.delete("/{project_id}/automation/scripts", response_model=MessageResponse)
async def delete_framework(
    project_id: int,
    name: str = "",
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """删除已生成的测试框架目录。

    Args:
        project_id: 项目 ID
        name: 框架项目目录名（query param）

    Returns:
        删除结果
    """
    project_name = name
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    framework_dir = (GENERATED_TESTS_DIR / project_name).resolve()
    if not str(framework_dir).startswith(str(GENERATED_TESTS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="无效的框架目录")
    if not framework_dir.exists():
        raise HTTPException(status_code=404, detail="框架目录不存在")

    import shutil
    shutil.rmtree(framework_dir)
    logger.info("删除测试框架: %s", framework_dir)

    return MessageResponse(ok=True, message=f"已删除 {project_name}")


@router.get("/{project_id}/automation/files", response_model=MessageResponse)
async def list_framework_files(
    project_id: int,
    name: str = "",
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """列出测试框架项目中的所有文件。

    Args:
        project_id: 项目 ID
        name: 框架项目目录名（query param）

    Returns:
        文件树列表
    """
    project_name = name
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    framework_dir = (GENERATED_TESTS_DIR / project_name).resolve()
    if not str(framework_dir).startswith(str(GENERATED_TESTS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="无效的框架目录")
    if not framework_dir.exists():
        raise HTTPException(status_code=404, detail="框架目录不存在")

    # 递归收集文件树
    files = []
    for f in sorted(framework_dir.rglob("*")):
        if f.is_file() and "__pycache__" not in f.parts:
            rel = str(f.relative_to(framework_dir)).replace("\\", "/")
            files.append({
                "path": rel,
                "name": f.name,
                "size": f.stat().st_size,
                "dir": str(f.parent.relative_to(framework_dir)).replace("\\", "/"),
            })

    return MessageResponse(
        ok=True,
        message=f"共 {len(files)} 个文件",
        data={"files": files, "project_name": project_name},
    )


@router.get("/{project_id}/automation/view", response_model=MessageResponse)
async def view_framework_file(
    project_id: int,
    name: str = "",
    file: str = "",
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """查看测试框架中的某个文件内容。

    Args:
        project_id: 项目 ID
        name: 框架项目目录名（query param）
        file: 文件相对路径（query param）

    Returns:
        文件内容
    """
    project_name = name
    project = await get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    framework_dir = (GENERATED_TESTS_DIR / project_name).resolve()
    if not str(framework_dir).startswith(str(GENERATED_TESTS_DIR.resolve())):
        raise HTTPException(status_code=400, detail="无效的框架目录")

    if not file:
        raise HTTPException(status_code=400, detail="请指定 file 参数")

    file_path = (framework_dir / file).resolve()
    if not str(file_path).startswith(str(framework_dir)):
        raise HTTPException(status_code=400, detail="无效的文件路径")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    content = file_path.read_text(encoding="utf-8", errors="replace")
    # 限制最大 100KB
    if len(content) > 100_000:
        content = content[:100_000] + "\n\n... (文件过大，已截断)"

    return MessageResponse(
        ok=True,
        message=f"文件: {file}",
        data={
            "path": file,
            "content": content,
            "size": file_path.stat().st_size,
            "language": _guess_language(file),
        },
    )


def _guess_language(path: str) -> str:
    """根据文件扩展名推断语言类型（用于前端语法高亮）。"""
    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    return {
        "py": "python", "json": "json", "txt": "text",
        "md": "markdown", "ini": "ini", "cfg": "ini",
        "yml": "yaml", "yaml": "yaml", "toml": "toml",
    }.get(ext, "text")
