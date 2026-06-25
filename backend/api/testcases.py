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
    save_testcases,
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["测试用例"])


def _infer_case_type(title: str, testpoints: list[dict]) -> str:
    """从测试点分类推断用例类型。

    规则（优先级从高到低）：
    1. 测试点分类唯一时直接用
    2. 标题含失败/错误/异常等逆向场景 → 逆向
    3. 标题含边界/最大/最小等 → 边界
    4. 默认正向
    """
    import re
    categories = {tp.get("category", "") for tp in testpoints}

    # 唯一分类直接映射
    if categories == {"功能测试"}:
        return "正向"
    if categories == {"异常测试"} or categories == {"安全测试"}:
        return "逆向"
    if categories == {"边界值测试"}:
        return "边界"

    tl = title

    # 边界模式（最优先，避免被逆向关键词误匹配）
    if re.search(r'边界|最大值|最小值|极限值|上限|下限|临界|超长|溢出|空字符串|^零$|负数|零值', tl):
        return "边界"

    # 逆向模式：标题描述的是异常/错误/失败场景
    # 用正则避免误匹配"验证不出现错误"这类正向描述
    if re.search(r'(返回|提示|显示|抛出|响应).*(错误|失败|异常|无效|不存在|为空|拒绝|阻止|超时|过期|未授权|越权)', tl):
        return "逆向"
    if re.search(r'(错误|失败|异常).*(返回|提示|显示|响应)', tl):
        return "逆向"
    if re.search(r'(SQL注入|XSS|伪造|篡改|验证码失效|token失效|token过期|密码错误|用户名不存在|参数为空)', tl, re.IGNORECASE):
        return "逆向"

    # 正向模式：标题描述成功/正常场景
    if re.search(r'(成功|正常|正确|通过|返回|展示|跳转|显示|获取)', tl):
        return "正向"

    # 安全测试类 → 逆向
    if "安全测试" in categories:
        return "逆向"

    return "正向"


@router.post("/{project_id}/testcases/generate", response_model=MessageResponse)
async def generate_testcases(
    project_id: int,
    mode: str = "api",
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """AI 自动生成测试用例。mode: api(接口测试) / functional(功能测试)。"""
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
                    lambda: service.generate(feature_name, testpoints, mode),
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
                        "priority": "P1",
                        "case_type": _infer_case_type(tc.title, testpoints),
                        "method": getattr(tc, "method", "") or "",
                        "url": getattr(tc, "url", "") or "",
                        "headers": getattr(tc, "headers", "") or "",
                        "body": getattr(tc, "body", "") or "",
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

    # ── 保存到数据库 ──────────────────────────────
    await save_testcases(db, project_id, all_testcases)
    await update_project_status(db, project_id, "testcases_generated")

    logger.info(
        "测试用例生成完成: %s 条用例 / %d/%d 功能点成功",
        len(all_testcases), success_count, len(groups),
    )

    # ── 自评审 ──────────────────────────────────
    review = service.review(
        project.name if project else "未命名",
        all_testcases,
    ) if all_testcases else {"score": 0, "pass": False, "summary": "无", "issues": [], "suggestions": []}

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
        },
    )


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
    return MessageResponse(
        ok=True,
        message=f"共 {len(testcases)} 个测试用例",
        data={
            "testcases": [orm_to_dict(tc) for tc in testcases]
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

    tc = await update_testcase(db, testcase_id, update_data)
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

    success = await delete_testcase(db, testcase_id)
    if not success:
        raise HTTPException(status_code=404, detail="测试用例不存在")

    return MessageResponse(ok=True, message="测试用例已删除")
