"""
API 客户端 — 封装对后端 FastAPI 的 HTTP 调用
================================================
"""

import json
import logging
from typing import Any

import httpx

from frontend.utils.constants import API_BASE

logger = logging.getLogger(__name__)

# ── 全局 HTTP 客户端 ──────────────────────────────
_client: httpx.Client | None = None


def get_client() -> httpx.Client:
    """获取全局 HTTP 客户端（复用连接）。

    Returns:
        httpx.Client 实例
    """
    global _client
    if _client is None:
        _client = httpx.Client(timeout=180.0)  # AI 调用可能较慢
    return _client


def _url(path: str) -> str:
    """构建完整 API URL。

    Args:
        path: API 路径（如 /projects/1/features/extract）

    Returns:
        完整 URL
    """
    return f"{API_BASE}{path}"


# ══════════════════════════════════════════════════════════
# 项目相关
# ══════════════════════════════════════════════════════════

def create_project(name: str = "") -> dict[str, Any]:
    """创建新项目。

    Args:
        name: 项目名称（空字符串则自动生成）

    Returns:
        项目信息字典
    """
    client = get_client()
    resp = client.post(_url("/projects/"), json={"name": name})
    resp.raise_for_status()
    return resp.json()


def list_projects() -> list[dict[str, Any]]:
    """获取项目列表。

    Returns:
        项目列表
    """
    client = get_client()
    resp = client.get(_url("/projects/"))
    resp.raise_for_status()
    return resp.json()


def get_project(project_id: int) -> dict[str, Any]:
    """获取项目详情。

    Args:
        project_id: 项目 ID

    Returns:
        项目详情
    """
    client = get_client()
    resp = client.get(_url(f"/projects/{project_id}"))
    resp.raise_for_status()
    return resp.json()


def delete_project(project_id: int) -> dict[str, Any]:
    """删除项目。

    Args:
        project_id: 项目 ID

    Returns:
        结果
    """
    client = get_client()
    resp = client.delete(_url(f"/projects/{project_id}"))
    resp.raise_for_status()
    return resp.json()


def get_projects_list() -> list[dict[str, Any]]:
    """获取所有项目列表（适配新接口）。

    Returns:
        项目列表
    """
    client = get_client()
    resp = client.get(_url("/projects/"))
    resp.raise_for_status()
    return resp.json()


# ══════════════════════════════════════════════════════════
# 文档相关
# ══════════════════════════════════════════════════════════

def upload_document(project_id: int, file_bytes: bytes, filename: str) -> dict[str, Any]:
    """上传并解析需求文档。

    Args:
        project_id: 项目 ID
        file_bytes: 文件内容（字节）
        filename: 原始文件名

    Returns:
        解析结果
    """
    client = get_client()
    files = {"file": (filename, file_bytes)}
    resp = client.post(
        _url(f"/projects/{project_id}/upload"),
        files=files,
    )
    resp.raise_for_status()
    return resp.json()


def get_document(project_id: int) -> dict[str, Any]:
    """获取项目文档内容。

    Args:
        project_id: 项目 ID

    Returns:
        文档内容
    """
    client = get_client()
    resp = client.get(_url(f"/projects/{project_id}/document"))
    resp.raise_for_status()
    return resp.json()


# ══════════════════════════════════════════════════════════
# 功能点相关
# ══════════════════════════════════════════════════════════

def extract_features(project_id: int) -> dict[str, Any]:
    """AI 提取功能点。

    Args:
        project_id: 项目 ID

    Returns:
        提取结果（含功能点列表）
    """
    client = get_client()
    resp = client.post(
        _url(f"/projects/{project_id}/features/extract"),
        timeout=300.0,  # 长文档可能耗时较长
    )
    resp.raise_for_status()
    return resp.json()


def list_features(project_id: int) -> dict[str, Any]:
    """获取功能点列表。

    Args:
        project_id: 项目 ID

    Returns:
        功能点列表
    """
    client = get_client()
    resp = client.get(_url(f"/projects/{project_id}/features"))
    resp.raise_for_status()
    return resp.json()


def add_feature(project_id: int, feature: dict[str, Any]) -> dict[str, Any]:
    """人工新增功能点。

    Args:
        project_id: 项目 ID
        feature: 功能点数据

    Returns:
        结果
    """
    client = get_client()
    resp = client.post(
        _url(f"/projects/{project_id}/features/add"),
        json=feature,
    )
    resp.raise_for_status()
    return resp.json()


def update_feature(project_id: int, feature_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    """更新功能点。

    Args:
        project_id: 项目 ID
        feature_id: 功能点 ID
        updates: 要更新的字段

    Returns:
        更新后的功能点
    """
    client = get_client()
    resp = client.put(
        _url(f"/projects/{project_id}/features/{feature_id}"),
        json=updates,
    )
    resp.raise_for_status()
    return resp.json()


def remove_feature(project_id: int, feature_id: int) -> dict[str, Any]:
    """删除功能点。

    Args:
        project_id: 项目 ID
        feature_id: 功能点 ID

    Returns:
        结果
    """
    client = get_client()
    resp = client.delete(
        _url(f"/projects/{project_id}/features/{feature_id}")
    )
    resp.raise_for_status()
    return resp.json()


# ══════════════════════════════════════════════════════════
# 测试点相关
# ══════════════════════════════════════════════════════════

def generate_testpoints(project_id: int) -> dict[str, Any]:
    """AI 生成测试点。

    Args:
        project_id: 项目 ID

    Returns:
        生成结果
    """
    client = get_client()
    resp = client.post(
        _url(f"/projects/{project_id}/testpoints/generate"),
        timeout=600.0,
    )
    resp.raise_for_status()
    return resp.json()


def list_testpoints(project_id: int) -> dict[str, Any]:
    """获取测试点列表。"""
    client = get_client()
    resp = client.get(_url(f"/projects/{project_id}/testpoints"))
    resp.raise_for_status()
    return resp.json()


def add_testpoint(project_id: int, testpoint: dict[str, Any]) -> dict[str, Any]:
    """人工新增测试点。"""
    client = get_client()
    resp = client.post(
        _url(f"/projects/{project_id}/testpoints/add"),
        json=testpoint,
    )
    resp.raise_for_status()
    return resp.json()


def update_testpoint(project_id: int, testpoint_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    """更新测试点。"""
    client = get_client()
    resp = client.put(
        _url(f"/projects/{project_id}/testpoints/{testpoint_id}"),
        json=updates,
    )
    resp.raise_for_status()
    return resp.json()


def remove_testpoint(project_id: int, testpoint_id: int) -> dict[str, Any]:
    """删除测试点。"""
    client = get_client()
    resp = client.delete(
        _url(f"/projects/{project_id}/testpoints/{testpoint_id}")
    )
    resp.raise_for_status()
    return resp.json()


# ══════════════════════════════════════════════════════════
# 测试用例相关
# ══════════════════════════════════════════════════════════

def generate_testcases(project_id: int, mode: str = "api") -> dict[str, Any]:
    """AI 生成测试用例。

    Args:
        project_id: 项目 ID
        mode: api(接口测试) | functional(功能测试)

    Returns:
        生成结果
    """
    client = get_client()
    resp = client.post(
        _url(f"/projects/{project_id}/testcases/generate"),
        params={"mode": mode},
        timeout=600.0,
    )
    resp.raise_for_status()
    return resp.json()


def list_testcases(project_id: int) -> dict[str, Any]:
    """获取测试用例列表。"""
    client = get_client()
    resp = client.get(_url(f"/projects/{project_id}/testcases"))
    resp.raise_for_status()
    return resp.json()


def add_testcase(project_id: int, testcase: dict[str, Any]) -> dict[str, Any]:
    """人工新增测试用例。"""
    client = get_client()
    resp = client.post(
        _url(f"/projects/{project_id}/testcases/add"),
        json=testcase,
    )
    resp.raise_for_status()
    return resp.json()


def update_testcase(project_id: int, testcase_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    """更新测试用例。"""
    client = get_client()
    resp = client.put(
        _url(f"/projects/{project_id}/testcases/{testcase_id}"),
        json=updates,
    )
    resp.raise_for_status()
    return resp.json()


def remove_testcase(project_id: int, testcase_id: int) -> dict[str, Any]:
    """删除测试用例。"""
    client = get_client()
    resp = client.delete(
        _url(f"/projects/{project_id}/testcases/{testcase_id}")
    )
    resp.raise_for_status()
    return resp.json()


# ══════════════════════════════════════════════════════════
# 导出相关
# ══════════════════════════════════════════════════════════

def export_excel(project_id: int, fmt: str = "excel") -> dict[str, Any]:
    """导出（支持 Excel / JSON / Markdown）。

    Args:
        project_id: 项目 ID
        fmt: excel | json | md

    Returns:
        导出结果（含下载 URL）
    """
    client = get_client()
    resp = client.post(
        _url(f"/projects/{project_id}/export"),
        json={"format": fmt, "include_features": True, "include_testpoints": True},
    )
    resp.raise_for_status()
    return resp.json()


def auto_generate(project_id: int) -> dict[str, Any]:
    """一键生成全部内容。

    Args:
        project_id: 项目 ID

    Returns:
        生成结果汇总
    """
    client = get_client()
    resp = client.post(
        _url(f"/projects/{project_id}/auto-generate"),
        timeout=600.0,  # 一键生成可能很慢
    )
    resp.raise_for_status()
    return resp.json()


def get_download_url(download_path: str) -> str:
    """构建完整下载 URL。

    Args:
        download_path: API 返回的下载路径

    Returns:
        完整下载 URL
    """
    from frontend.utils.constants import BACKEND_URL
    return f"{BACKEND_URL}{download_path}"


# ══════════════════════════════════════════════════════════
# 批量操作
# ══════════════════════════════════════════════════════════

def batch_generate(project_ids: list[int]) -> dict[str, Any]:
    """批量一键生成多个项目。

    Args:
        project_ids: 项目 ID 列表

    Returns:
        批量结果
    """
    client = get_client()
    resp = client.post(
        _url("/batch/generate"),
        json={"project_ids": project_ids},
        timeout=900.0,
    )
    resp.raise_for_status()
    return resp.json()
