"""
Pydantic 数据模型 — 请求体 / 响应体 / 内部实体
=================================================
所有 API 接受和返回的数据结构定义。
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════
# 项目 (Project)
# ══════════════════════════════════════════════════════════

class ProjectCreate(BaseModel):
    """创建项目请求。"""
    name: str = Field(default="", min_length=0, max_length=200, description="项目名称（空则自动生成）")


class ProjectResponse(BaseModel):
    """项目响应。"""
    id: int
    name: str
    doc_filename: str | None = None
    doc_content: str | None = None
    status: str = "created"  # created / parsed / features_extracted / testpoints_generated / testcases_generated / exported
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectStatus(BaseModel):
    """项目状态。"""
    id: int
    name: str
    status: str
    has_features: bool = False
    has_testpoints: bool = False
    has_testcases: bool = False


# ══════════════════════════════════════════════════════════
# 功能点 (Feature)
# ══════════════════════════════════════════════════════════

class FeatureCreate(BaseModel):
    """新增功能点请求。"""
    module: str = Field(..., description="所属模块")
    name: str = Field(..., description="功能点名称")
    description: str = Field("", description="功能描述")
    priority: Literal["P0", "P1", "P2", "P3"] = "P2"
    preconditions: list[str] = Field(default_factory=list, description="前置条件")
    business_rules: list[str] = Field(default_factory=list, description="业务规则")


class FeatureUpdate(BaseModel):
    """修改功能点请求（所有字段可选）。"""
    module: str | None = None
    name: str | None = None
    description: str | None = None
    priority: Literal["P0", "P1", "P2", "P3"] | None = None
    preconditions: list[str] | None = None
    business_rules: list[str] | None = None


class FeatureResponse(BaseModel):
    """功能点响应。"""
    id: int
    project_id: int
    module: str
    name: str
    description: str
    priority: str
    preconditions: list[str] = []
    business_rules: list[str] = []
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════
# 测试点 (TestPoint)
# ══════════════════════════════════════════════════════════

class TestPointCreate(BaseModel):
    """新增测试点请求。"""
    feature_name: str = Field(..., description="关联功能点名称")
    category: str = Field("功能测试", description="测试类型")
    description: str = Field(..., description="测试点描述")
    expected_result: str = Field("", description="预期结果")
    test_data: str = Field("", description="建议测试数据")
    priority: Literal["P0", "P1", "P2", "P3"] = "P1"


class TestPointUpdate(BaseModel):
    """修改测试点请求（所有字段可选）。"""
    feature_name: str | None = None
    category: str | None = None
    description: str | None = None
    expected_result: str | None = None
    test_data: str | None = None
    priority: Literal["P0", "P1", "P2", "P3"] | None = None


class TestPointResponse(BaseModel):
    """测试点响应。"""
    id: int
    project_id: int
    feature_name: str
    category: str
    description: str
    expected_result: str
    test_data: str
    priority: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════
# 测试用例 (TestCase)
# ══════════════════════════════════════════════════════════

class TestCaseCreate(BaseModel):
    """新增测试用例请求。"""
    testpoint_description: str = Field("", description="关联测试点描述")
    case_id: str = Field(..., description="用例编号")
    title: str = Field(..., description="用例标题")
    precondition: str = Field("", description="前置条件")
    steps: list[str] = Field(default_factory=list, description="测试步骤")
    expected: str = Field("", description="预期结果")
    priority: Literal["P0", "P1", "P2", "P3"] = "P1"
    case_type: str = Field("正向", description="用例类型（正向/逆向/边界）")


class TestCaseUpdate(BaseModel):
    """修改测试用例请求（所有字段可选）。"""
    testpoint_description: str | None = None
    case_id: str | None = None
    title: str | None = None
    precondition: str | None = None
    steps: list[str] | None = None
    expected: str | None = None
    priority: Literal["P0", "P1", "P2", "P3"] | None = None
    case_type: str | None = None


class TestCaseResponse(BaseModel):
    """测试用例响应。"""
    id: int
    project_id: int
    testpoint_description: str
    case_id: str
    title: str
    precondition: str
    steps: list[str]
    expected: str
    priority: str
    case_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════
# 导出 (Export)
# ══════════════════════════════════════════════════════════

class ExportOptions(BaseModel):
    """导出选项。"""
    include_features: bool = True
    include_testpoints: bool = True


class ExportResponse(BaseModel):
    """导出响应。"""
    download_url: str
    filename: str
    file_size: int


# ══════════════════════════════════════════════════════════
# 通用
# ══════════════════════════════════════════════════════════

class MessageResponse(BaseModel):
    """通用消息响应。"""
    ok: bool = True
    message: str = "操作成功"
    data: Any | None = None


class ErrorResponse(BaseModel):
    """错误响应。"""
    ok: bool = False
    message: str
    detail: str | None = None
