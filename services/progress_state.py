"""
进度状态缓存
============
用于长任务在同一进程内向前端暴露当前阶段，不参与数据库事务。
"""

from datetime import datetime
from typing import Any

_PROGRESS: dict[int, dict[str, Any]] = {}


def set_progress(
    project_id: int,
    stage: str,
    message: str,
    step: int,
    total: int,
    data: dict[str, Any] | None = None,
) -> None:
    """记录项目当前处理进度。"""
    _PROGRESS[project_id] = {
        "stage": stage,
        "message": message,
        "step": step,
        "total": total,
        "percent": int(step / total * 100) if total else 0,
        "data": data or {},
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def get_progress(project_id: int) -> dict[str, Any]:
    """获取项目当前处理进度。"""
    return _PROGRESS.get(project_id, {
        "stage": "idle",
        "message": "暂无运行中的任务",
        "step": 0,
        "total": 0,
        "percent": 0,
        "data": {},
        "updated_at": "",
    })
