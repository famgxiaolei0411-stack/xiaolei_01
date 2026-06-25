"""
SQLAlchemy ORM 模型
=====================
定义数据库表结构。
"""

import json
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.db.database import Base


class ProjectORM(Base):
    """项目表。

    存储需求文档内容和处理状态。
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, comment="项目名称")
    doc_filename = Column(String(500), nullable=True, comment="上传的文档文件名")
    doc_content = Column(Text, nullable=True, comment="文档完整文本内容")
    status = Column(
        String(50),
        nullable=False,
        default="created",
        comment="处理状态: created/parsed/features_extracted/testpoints_generated/testcases_generated/exported",
    )
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    # ── 关联 ──────────────────────────────────────
    features = relationship(
        "FeatureORM", back_populates="project", cascade="all, delete-orphan"
    )
    testpoints = relationship(
        "TestPointORM", back_populates="project", cascade="all, delete-orphan"
    )
    testcases = relationship(
        "TestCaseORM", back_populates="project", cascade="all, delete-orphan"
    )


class FeatureORM(Base):
    """功能点表。"""
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    module = Column(String(200), nullable=False, comment="所属模块")
    name = Column(String(200), nullable=False, comment="功能点名称")
    description = Column(Text, nullable=True, comment="功能描述")
    priority = Column(String(10), nullable=False, default="P2", comment="优先级")
    preconditions_json = Column(
        Text, nullable=True, default="[]", comment="前置条件 (JSON)"
    )
    business_rules_json = Column(
        Text, nullable=True, default="[]", comment="业务规则 (JSON)"
    )
    created_at = Column(DateTime, default=datetime.utcnow)

    # ── 关联 ──────────────────────────────────────
    project = relationship("ProjectORM", back_populates="features")

    @property
    def preconditions(self) -> list[str]:
        """解析前置条件 JSON。"""
        try:
            return json.loads(self.preconditions_json or "[]")
        except (json.JSONDecodeError, TypeError) as exc:
            import logging
            logging.getLogger(__name__).warning(
                "FeatureORM id=%d preconditions JSON 解析失败: %s", self.id, exc
            )
            return []

    @preconditions.setter
    def preconditions(self, value: list[str]) -> None:
        self.preconditions_json = json.dumps(value, ensure_ascii=False)

    @property
    def business_rules(self) -> list[str]:
        """解析业务规则 JSON。"""
        try:
            return json.loads(self.business_rules_json or "[]")
        except (json.JSONDecodeError, TypeError) as exc:
            import logging
            logging.getLogger(__name__).warning(
                "FeatureORM id=%d business_rules JSON 解析失败: %s", self.id, exc
            )
            return []

    @business_rules.setter
    def business_rules(self, value: list[str]) -> None:
        self.business_rules_json = json.dumps(value, ensure_ascii=False)


class TestPointORM(Base):
    """测试点表。"""
    __tablename__ = "testpoints"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    feature_name = Column(String(200), nullable=False, comment="关联功能点名称")
    category = Column(String(50), nullable=False, default="功能测试", comment="测试类型")
    description = Column(Text, nullable=False, comment="测试点描述")
    expected_result = Column(Text, nullable=True, comment="预期结果")
    test_data = Column(Text, nullable=True, comment="建议测试数据")
    priority = Column(String(10), nullable=False, default="P1", comment="优先级")
    created_at = Column(DateTime, default=datetime.utcnow)

    # ── 关联 ──────────────────────────────────────
    project = relationship("ProjectORM", back_populates="testpoints")


class TestCaseORM(Base):
    """测试用例表。"""
    __tablename__ = "testcases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    testpoint_description = Column(Text, nullable=True, comment="关联测试点描述")
    case_id = Column(String(50), nullable=False, comment="用例编号")
    title = Column(String(500), nullable=False, comment="用例标题")
    precondition = Column(Text, nullable=True, comment="前置条件")
    steps_json = Column(Text, nullable=True, default="[]", comment="测试步骤 (JSON)")
    expected = Column(Text, nullable=True, comment="预期结果")
    priority = Column(String(10), nullable=False, default="P1", comment="优先级")
    case_type = Column(String(20), nullable=False, default="正向", comment="用例类型")
    method = Column(String(10), nullable=True, default="", comment="请求方法 (GET/POST/PUT/DELETE)")
    url = Column(String(500), nullable=True, default="", comment="请求URL")
    headers = Column(Text, nullable=True, default="", comment="请求头 JSON")
    body = Column(Text, nullable=True, default="", comment="请求体 JSON")
    created_at = Column(DateTime, default=datetime.utcnow)

    # ── 关联 ──────────────────────────────────────
    project = relationship("ProjectORM", back_populates="testcases")

    @property
    def steps(self) -> list[str]:
        """解析步骤 JSON。"""
        try:
            return json.loads(self.steps_json or "[]")
        except (json.JSONDecodeError, TypeError) as exc:
            import logging
            logging.getLogger(__name__).warning(
                "TestCaseORM id=%d steps JSON 解析失败: %s", self.id, exc
            )
            return []

    @steps.setter
    def steps(self, value: list[str]) -> None:
        self.steps_json = json.dumps(value, ensure_ascii=False)
