"""
CRUD 操作封装
==============
所有数据库 CRUD 操作，与 API 路由解耦。
"""

import logging
from typing import Any, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import (
    FeatureORM,
    ProjectORM,
    TestCaseORM,
    TestPointORM,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 项目 CRUD
# ══════════════════════════════════════════════════════════

async def create_project(db: AsyncSession, name: str) -> ProjectORM:
    """创建新项目。

    Args:
        db: 数据库会话
        name: 项目名称

    Returns:
        新建的 ProjectORM 实例
    """
    project = ProjectORM(name=name)
    db.add(project)
    await db.flush()
    await db.refresh(project)
    logger.info("创建项目: id=%d, name=%s", project.id, name)
    return project


async def get_project(db: AsyncSession, project_id: int) -> ProjectORM | None:
    """根据 ID 获取项目。

    Args:
        db: 数据库会话
        project_id: 项目 ID

    Returns:
        ProjectORM 实例（不存在则返回 None）
    """
    result = await db.execute(
        select(ProjectORM).where(ProjectORM.id == project_id)
    )
    return result.scalar_one_or_none()


async def list_projects(db: AsyncSession) -> Sequence[ProjectORM]:
    """获取所有项目列表（按创建时间倒序）。

    Args:
        db: 数据库会话

    Returns:
        项目列表
    """
    result = await db.execute(
        select(ProjectORM).order_by(ProjectORM.created_at.desc())
    )
    return result.scalars().all()


async def update_project_status(
    db: AsyncSession, project_id: int, status: str
) -> None:
    """更新项目处理状态。

    Args:
        db: 数据库会话
        project_id: 项目 ID
        status: 新状态
    """
    project = await get_project(db, project_id)
    if project:
        project.status = status
        await db.flush()


async def set_document_content(
    db: AsyncSession, project_id: int, filename: str, content: str
) -> ProjectORM | None:
    """设置项目文档内容。

    重新上传文档时会清除旧的 AI 生成数据（功能点/测试点/测试用例），
    因为新文档内容可能完全不同，旧数据不再有效。

    Args:
        db: 数据库会话
        project_id: 项目 ID
        filename: 文档文件名
        content: 文档文本内容

    Returns:
        更新后的项目（不存在则返回 None）
    """
    project = await get_project(db, project_id)
    if not project:
        return None

    # ── 如果之前已有数据，清除旧 AI 生成结果 ──────
    if project.doc_content:
        tp_del = await db.execute(
            delete(TestPointORM).where(TestPointORM.project_id == project_id)
        )
        tc_del = await db.execute(
            delete(TestCaseORM).where(TestCaseORM.project_id == project_id)
        )
        feat_del = await db.execute(
            delete(FeatureORM).where(FeatureORM.project_id == project_id)
        )
        logger.info(
            "重新上传文档，清除旧数据: %d 功能点 + %d 测试点 + %d 测试用例",
            feat_del.rowcount, tp_del.rowcount, tc_del.rowcount,
        )

    project.doc_filename = filename
    project.doc_content = content
    project.status = "parsed"
    await db.flush()
    return project


async def delete_project(db: AsyncSession, project_id: int) -> bool:
    """删除项目（级联删除关联数据）。

    手动级联删除 features/testpoints/testcases（SQLite 外键不保证级联）。

    Args:
        db: 数据库会话
        project_id: 项目 ID

    Returns:
        是否成功删除
    """
    project = await get_project(db, project_id)
    if not project:
        return False

    # 级联删除
    fc = await db.execute(delete(FeatureORM).where(FeatureORM.project_id == project_id))
    tpc = await db.execute(delete(TestPointORM).where(TestPointORM.project_id == project_id))
    tcc = await db.execute(delete(TestCaseORM).where(TestCaseORM.project_id == project_id))
    await db.execute(delete(ProjectORM).where(ProjectORM.id == project_id))
    await db.flush()

    logger.info(
        "删除项目: id=%d, 级联删除 %d 功能点 + %d 测试点 + %d 测试用例",
        project_id, fc.rowcount, tpc.rowcount, tcc.rowcount,
    )
    return True


# ══════════════════════════════════════════════════════════
# 功能点 CRUD
# ══════════════════════════════════════════════════════════

async def save_features(
    db: AsyncSession,
    project_id: int,
    features: list[dict[str, Any]],
) -> list[FeatureORM]:
    """批量保存功能点（先删后插）。

    Args:
        db: 数据库会话
        project_id: 项目 ID
        features: 功能点字典列表

    Returns:
        保存的 FeatureORM 列表
    """
    # 删除旧数据
    await db.execute(
        delete(FeatureORM).where(FeatureORM.project_id == project_id)
    )

    # 批量插入新数据
    orm_objects: list[FeatureORM] = []
    for feat in features:
        orm_obj = FeatureORM(
            project_id=project_id,
            module=feat.get("module", "未分类"),
            name=feat.get("name", "未命名"),
            description=feat.get("description", ""),
            priority=feat.get("priority", "P2"),
        )
        orm_obj.preconditions = feat.get("preconditions", [])
        orm_obj.business_rules = feat.get("business_rules", [])
        db.add(orm_obj)
        orm_objects.append(orm_obj)

    await db.flush()
    logger.info(
        "保存功能点: project_id=%d, count=%d", project_id, len(orm_objects)
    )
    return orm_objects


async def insert_feature(
    db: AsyncSession,
    project_id: int,
    feature: dict[str, Any],
) -> FeatureORM:
    """插入单个功能点（不删除已有数据）。

    Args:
        db: 数据库会话
        project_id: 项目 ID
        feature: 功能点字典

    Returns:
        新建的 FeatureORM 实例
    """
    orm_obj = FeatureORM(
        project_id=project_id,
        module=feature.get("module", "未分类"),
        name=feature.get("name", "未命名"),
        description=feature.get("description", ""),
        priority=feature.get("priority", "P2"),
    )
    orm_obj.preconditions = feature.get("preconditions", [])
    orm_obj.business_rules = feature.get("business_rules", [])
    db.add(orm_obj)
    await db.flush()
    await db.refresh(orm_obj)
    logger.info("插入功能点: project_id=%d, name=%s", project_id, orm_obj.name)
    return orm_obj


async def get_features(
    db: AsyncSession, project_id: int
) -> Sequence[FeatureORM]:
    """获取项目的所有功能点。"""
    result = await db.execute(
        select(FeatureORM)
        .where(FeatureORM.project_id == project_id)
        .order_by(FeatureORM.id)
    )
    return result.scalars().all()


async def update_feature(
    db: AsyncSession, feature_id: int, updates: dict[str, Any]
) -> FeatureORM | None:
    """更新单个功能点。

    Args:
        db: 数据库会话
        feature_id: 功能点 ID
        updates: 要更新的字段字典

    Returns:
        更新后的功能点（ID 不存在则返回 None）
    """
    result = await db.execute(
        select(FeatureORM).where(FeatureORM.id == feature_id)
    )
    feature = result.scalar_one_or_none()

    if not feature:
        return None

    # ── 更新普通字段 ──────────────────────────────
    for field in ("module", "name", "description", "priority"):
        if field in updates and updates[field] is not None:
            setattr(feature, field, updates[field])

    # ── 更新 JSON 字段 ────────────────────────────
    if "preconditions" in updates and updates["preconditions"] is not None:
        feature.preconditions = updates["preconditions"]
    if "business_rules" in updates and updates["business_rules"] is not None:
        feature.business_rules = updates["business_rules"]

    await db.flush()
    await db.refresh(feature)
    return feature


async def delete_feature(db: AsyncSession, feature_id: int) -> bool:
    """删除单个功能点，并级联删除关联的测试点和测试用例。

    由于测试点和测试用例通过 feature_name/字符串引用功能点
    （非外键约束），需要手动级联清理。

    Args:
        db: 数据库会话
        feature_id: 功能点 ID

    Returns:
        是否成功删除
    """
    # ── 先查到功能点名称 ──────────────────────────
    result = await db.execute(
        select(FeatureORM).where(FeatureORM.id == feature_id)
    )
    feature = result.scalar_one_or_none()
    if not feature:
        return False

    feature_name = feature.name
    project_id = feature.project_id

    # ── 检查项目中是否还有其他同名功能点 ────────────
    dup_check = await db.execute(
        select(FeatureORM).where(
            FeatureORM.project_id == project_id,
            FeatureORM.name == feature_name,
            FeatureORM.id != feature_id,
        )
    )
    has_duplicate = dup_check.scalar_one_or_none() is not None

    # ── 删除功能点本身 ────────────────────────────
    await db.execute(
        delete(FeatureORM).where(FeatureORM.id == feature_id)
    )

    # ── 级联删除关联数据（仅当没有同名功能点时）─────
    if not has_duplicate:
        tp_result = await db.execute(
            delete(TestPointORM).where(
                TestPointORM.project_id == project_id,
                TestPointORM.feature_name == feature_name,
            )
        )
        tc_result = await db.execute(
            delete(TestCaseORM).where(
                TestCaseORM.project_id == project_id,
                TestCaseORM.testpoint_description == feature_name,
            )
        )
        logger.info(
            "删除功能点 [%s] (id=%d)，级联删除 %d 测试点 + %d 测试用例",
            feature_name, feature_id,
            tp_result.rowcount, tc_result.rowcount,
        )
    else:
        logger.info(
            "删除功能点 [%s] (id=%d)，存在同名功能点，跳过级联删除",
            feature_name, feature_id,
        )

    await db.flush()
    return True


# ══════════════════════════════════════════════════════════
# 测试点 CRUD
# ══════════════════════════════════════════════════════════

async def save_testpoints(
    db: AsyncSession,
    project_id: int,
    testpoints: list[dict[str, Any]],
) -> list[TestPointORM]:
    """批量保存测试点（先删后插）。"""
    await db.execute(
        delete(TestPointORM).where(TestPointORM.project_id == project_id)
    )

    orm_objects: list[TestPointORM] = []
    for tp in testpoints:
        orm_obj = TestPointORM(
            project_id=project_id,
            feature_name=tp.get("feature_name", ""),
            category=tp.get("category", "功能测试"),
            description=tp.get("description", ""),
            expected_result=tp.get("expected_result", ""),
            test_data=tp.get("test_data", ""),
            priority=tp.get("priority", "P1"),
        )
        db.add(orm_obj)
        orm_objects.append(orm_obj)

    await db.flush()
    logger.info(
        "保存测试点: project_id=%d, count=%d", project_id, len(orm_objects)
    )
    return orm_objects


async def insert_testpoint(
    db: AsyncSession,
    project_id: int,
    testpoint: dict[str, Any],
) -> TestPointORM:
    """插入单个测试点（不删除已有数据）。"""
    orm_obj = TestPointORM(
        project_id=project_id,
        feature_name=testpoint.get("feature_name", ""),
        category=testpoint.get("category", "功能测试"),
        description=testpoint.get("description", ""),
        expected_result=testpoint.get("expected_result", ""),
        test_data=testpoint.get("test_data", ""),
        priority=testpoint.get("priority", "P1"),
    )
    db.add(orm_obj)
    await db.flush()
    await db.refresh(orm_obj)
    return orm_obj


async def get_testpoints(
    db: AsyncSession, project_id: int
) -> Sequence[TestPointORM]:
    """获取项目的所有测试点。"""
    result = await db.execute(
        select(TestPointORM)
        .where(TestPointORM.project_id == project_id)
        .order_by(TestPointORM.id)
    )
    return result.scalars().all()


async def update_testpoint(
    db: AsyncSession, testpoint_id: int, updates: dict[str, Any]
) -> TestPointORM | None:
    """更新单个测试点。"""
    result = await db.execute(
        select(TestPointORM).where(TestPointORM.id == testpoint_id)
    )
    tp = result.scalar_one_or_none()

    if not tp:
        return None

    for field in (
        "feature_name", "category", "description",
        "expected_result", "test_data", "priority",
    ):
        if field in updates and updates[field] is not None:
            setattr(tp, field, updates[field])

    await db.flush()
    await db.refresh(tp)
    return tp


async def delete_testpoint(db: AsyncSession, testpoint_id: int) -> bool:
    """删除单个测试点。"""
    result = await db.execute(
        delete(TestPointORM).where(TestPointORM.id == testpoint_id)
    )
    return result.rowcount > 0


# ══════════════════════════════════════════════════════════
# 测试用例 CRUD
# ══════════════════════════════════════════════════════════

async def save_testcases(
    db: AsyncSession,
    project_id: int,
    testcases: list[dict[str, Any]],
) -> list[TestCaseORM]:
    """批量保存测试用例（先删后插）。"""
    await db.execute(
        delete(TestCaseORM).where(TestCaseORM.project_id == project_id)
    )

    orm_objects: list[TestCaseORM] = []
    for tc in testcases:
        orm_obj = TestCaseORM(
            project_id=project_id,
            testpoint_description=tc.get("testpoint_description", ""),
            case_id=tc.get("case_id", ""),
            title=tc.get("title", ""),
            precondition=tc.get("precondition", ""),
            expected=tc.get("expected", ""),
            priority=tc.get("priority", "P1"),
            case_type=tc.get("case_type", "正向"),
        )
        orm_obj.steps = tc.get("steps", [])
        db.add(orm_obj)
        orm_objects.append(orm_obj)

    await db.flush()
    logger.info(
        "保存测试用例: project_id=%d, count=%d", project_id, len(orm_objects)
    )
    return orm_objects


async def insert_testcase(
    db: AsyncSession,
    project_id: int,
    testcase: dict[str, Any],
) -> TestCaseORM:
    """插入单个测试用例（不删除已有数据）。"""
    orm_obj = TestCaseORM(
        project_id=project_id,
        testpoint_description=testcase.get("testpoint_description", ""),
        case_id=testcase.get("case_id", ""),
        title=testcase.get("title", ""),
        precondition=testcase.get("precondition", ""),
        expected=testcase.get("expected", ""),
        priority=testcase.get("priority", "P1"),
        case_type=testcase.get("case_type", "正向"),
    )
    orm_obj.steps = testcase.get("steps", [])
    db.add(orm_obj)
    await db.flush()
    await db.refresh(orm_obj)
    return orm_obj


async def get_testcases(
    db: AsyncSession, project_id: int
) -> Sequence[TestCaseORM]:
    """获取项目的所有测试用例。"""
    result = await db.execute(
        select(TestCaseORM)
        .where(TestCaseORM.project_id == project_id)
        .order_by(TestCaseORM.id)
    )
    return result.scalars().all()


async def update_testcase(
    db: AsyncSession, testcase_id: int, updates: dict[str, Any]
) -> TestCaseORM | None:
    """更新单个测试用例。"""
    result = await db.execute(
        select(TestCaseORM).where(TestCaseORM.id == testcase_id)
    )
    tc = result.scalar_one_or_none()

    if not tc:
        return None

    for field in (
        "testpoint_description", "case_id", "title",
        "precondition", "expected", "priority", "case_type",
    ):
        if field in updates and updates[field] is not None:
            setattr(tc, field, updates[field])

    if "steps" in updates and updates["steps"] is not None:
        tc.steps = updates["steps"]

    await db.flush()
    await db.refresh(tc)
    return tc


async def delete_testcase(db: AsyncSession, testcase_id: int) -> bool:
    """删除单个测试用例。"""
    result = await db.execute(
        delete(TestCaseORM).where(TestCaseORM.id == testcase_id)
    )
    return result.rowcount > 0


# ══════════════════════════════════════════════════════════
# 数据转换工具函数
# ══════════════════════════════════════════════════════════

def orm_to_dict(orm_obj: Any) -> dict[str, Any]:
    """将 ORM 实例转换为字典（方便传给 AI 服务）。

    Args:
        orm_obj: SQLAlchemy ORM 实例

    Returns:
        字典表示
    """
    if isinstance(orm_obj, FeatureORM):
        return {
            "module": orm_obj.module,
            "name": orm_obj.name,
            "description": orm_obj.description,
            "priority": orm_obj.priority,
            "preconditions": orm_obj.preconditions,
            "business_rules": orm_obj.business_rules,
        }
    if isinstance(orm_obj, TestPointORM):
        return {
            "id": orm_obj.id,
            "feature_name": orm_obj.feature_name,
            "category": orm_obj.category,
            "description": orm_obj.description,
            "expected_result": orm_obj.expected_result,
            "test_data": orm_obj.test_data,
            "priority": orm_obj.priority,
        }
    if isinstance(orm_obj, TestCaseORM):
        return {
            "id": orm_obj.id,
            "testpoint_description": orm_obj.testpoint_description,
            "case_id": orm_obj.case_id,
            "title": orm_obj.title,
            "precondition": orm_obj.precondition,
            "steps": orm_obj.steps,
            "expected": orm_obj.expected,
            "priority": orm_obj.priority,
            "case_type": orm_obj.case_type,
        }
    return {}
