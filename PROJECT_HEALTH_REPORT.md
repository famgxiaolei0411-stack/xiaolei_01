# AI Test Copilot 项目健康报告

日期：2026-07-01
角色：QA Lead

## 执行摘要

整体状态：已修复主要问题，当前项目健康。

默认本地质量门禁已经稳定且快速。显式开启集成测试时，真实 AI 集成测试也可以通过。

## 测试结果

### 默认 Pytest

命令：

```bash
pytest -q --durations=20
```

结果：

```text
124 passed, 10 skipped in 1.88s
```

Warning：无。

最慢测试：

- `tests/test_services/test_parser_service.py::TestDocxParser::test_parse_docx` - 0.11s
- `tests/test_services/test_parser_service.py::TestPdfParser::test_parse_pdf` - 0.08s
- 当前本地测试中没有需要处理的慢测试。

### 显式集成测试

命令：

```bash
RUN_INTEGRATION=1 pytest -q --durations=10
```

结果：

```text
133 passed, 1 skipped in 107.57s
```

最慢的集成测试均会调用真实 AI 服务：

- `test_generate_cases_structure_stable` - 33.84s
- `test_generate_login_cases` - 16.76s
- `test_generate_login_feature` - 13.60s
- `test_generate_registration_feature` - 12.87s
- `test_generate_to_dict_format` - 12.61s

## 覆盖率

当前环境未安装 `pytest-cov`，因此无法测量行覆盖率和分支覆盖率。

尝试执行命令：

```bash
pytest --cov=. --cov-report=term-missing -q
```

结果：

```text
pytest: error: unrecognized arguments: --cov=. --cov-report=term-missing
```

## 未测试或弱覆盖区域

通过静态模块扫描发现，以下模块缺少直接测试引用：

- `backend/main.py`
- `backend/api/documents.py`
- `backend/db/database.py`
- `backend/db/models.py`
- `backend/middleware/error_handler.py`
- `backend/models/schemas.py`
- `services/feature_extractor.py`
- `services/progress_state.py`
- `services/testcase_generator.py`
- `services/testpoint_generator.py`
- `services/parsers/docx_parser.py`
- `frontend/*`
- `prompts/*_v2.py`

其中部分模块可能已被间接覆盖，但直接回归测试仍然偏薄。

## 用户流程验证

已通过确定性的 QA 探针验证完整用户链路，使用本地 service 和 Fake AI：

```text
上传/解析文档
  -> 生成功能点
  -> 生成测试点
  -> 生成测试用例
  -> 生成质量评审
  -> 导出 Excel
```

结果：

```text
1 passed
```

已验证输出：

- 文档解析成功。
- 生成功能点 2 个。
- 生成测试点 12 个。
- 测试用例生成并完成归一化。
- 质量评审得分达到通过阈值。
- Excel 文件成功生成，且文件大小大于 0。

## 故障注入

### AI 失败

已有测试覆盖：

- `tests/test_services/test_feature_service.py`
- `tests/test_services/test_testpoint_service.py`
- `tests/test_services/test_testcase_service.py`
- `tests/test_api/test_auto_generate.py::test_auto_generate_rolls_back_when_testcase_generation_fails`

状态：通过。

### Skill 失败

已有测试覆盖：

- `tests/test_services/test_testpoint_service.py`
- `tests/test_services/test_testcase_service.py`
- `tests/test_services/test_quality_review.py`

状态：通过。Skill 失败时会降级为原始 prompt 或原始 review。

### 数据库 / 事务失败

回滚行为已有测试覆盖：

- `tests/test_api/test_auto_generate.py::test_auto_generate_rolls_back_when_testcase_generation_fails`
- `tests/test_api/test_batch_generate.py::test_batch_generate_rolls_back_project_when_testpoint_generation_fails`

状态：通过。

### 导出失败

已新增回归测试：

- `tests/test_api/test_auto_generate.py::test_auto_generate_rolls_back_when_export_fails`

状态：通过。导出失败时会回滚事务，不会提交。

## 问题分级

## Critical

未发现 Critical 问题。

## Major

### 已修复：集成测试默认运行

问题：

真实 AI 集成测试会在普通 `pytest` 中运行，导致测试套件变慢，并受外部服务波动影响。

修复：

在 `tests/conftest.py` 中增加默认跳过 `integration` 测试的逻辑。现在只有显式设置环境变量时才运行：

```bash
RUN_INTEGRATION=1
```

验证：

- 默认 pytest：`124 passed, 10 skipped`
- 显式集成 pytest：`133 passed, 1 skipped`

### 已修复：异步 DB Mock 导致 RuntimeWarning

问题：

`db.add()` 是同步方法，但测试中使用了 session 级别的 `AsyncMock`，导致：

```text
RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited
```

修复：

在受影响测试中设置：

```python
db.add = MagicMock()
```

验证：

默认 pytest 已无 warning。

### 已修复：导出失败路径缺少直接回归测试

问题：

一键生成流程中，测试用例生成失败已有 rollback 覆盖，但 Excel 导出失败路径没有直接回归测试。

修复：

新增：

```text
test_auto_generate_rolls_back_when_export_fails
```

验证：

默认 pytest 通过，并确认导出失败时 rollback 且不会 commit。

### 已修复：真实 API 集成断言比 Schema 更严格

问题：

集成测试要求测试点描述不少于 10 个字符，但实际 Pydantic schema 要求不少于 5 个字符。真实 AI 返回合法的 7 字符描述时，测试失败。

修复：

将集成测试断言与 schema 对齐：

```python
len(description) >= 5
```

验证：

显式集成 pytest 通过。

## Minor

### 缺少覆盖率工具

影响：

当前无法获得客观的行覆盖率和分支覆盖率数据。

建议：

将 `pytest-cov` 加入测试依赖，并在完成基线测量后引入最低覆盖率门禁。

### 前端自动化覆盖较少

影响：

Streamlit 页面和前端 API client 的回归风险主要依赖人工验证，后端测试不一定能覆盖。

建议：

增加前端工具函数 smoke test；如果 UI 体验成为发布门禁，再增加 Playwright 或 Streamlit 层面的工作流测试。

### 部分旧 generator 模块覆盖偏弱

涉及模块：

- `services/testpoint_generator.py`
- `services/testcase_generator.py`
- `services/feature_extractor.py`

建议：

确认这些模块是否属于遗留路径。如果仍保留使用，应补测试；如果已被 V2 service 取代，应文档化或逐步废弃。

## Low

### 质量评审 Skill 失败时无日志

影响：

当前设计会在 Skill review 失败时降级为原始 review，但不会记录 warning。

建议：

如果后续需要线上可观测性，可增加 warning 日志。

### 默认 Skill Orchestrator 构建逻辑重复

影响：

`TestPointService` 和 `TestCaseService` 都构建了类似的默认 prompt Skill registry。

建议：

如果未来更多 service 接入 Skill，可抽取一个很小的 factory。当前重复规模尚可，不建议为了洁癖提前重构。

## 架构 Review

### 优点

- Skill 机制仍然保持插件化和纯函数倾向。
- Prompt Skill 与 service schema、API 返回结构隔离良好。
- `ApiContractSkill` 只参与质量评审，不影响 `score/pass`。
- Service Layer 仍然掌控主流程，Skill 只是增强能力，不替代主流程。
- 现有 Pydantic 校验仍是 LLM 输出的主要防线。

### 风险

- 真实 API 测试有价值，但天然慢且可能 flaky；默认跳过、显式运行是正确策略。
- API 路由层仍缺少更完整的端点级直接覆盖。
- 质量评审 metrics 正在增加；后续新增 Skill 应继续将指标命名空间限定在 `metrics["skill_reviews"]` 下。

## 最终状态

本次 QA 过程中发现的 Critical 和 Major 问题均已修复。

最终验证：

```text
pytest -q --durations=20
124 passed, 10 skipped in 1.88s

RUN_INTEGRATION=1 pytest -q --durations=10
133 passed, 1 skipped in 107.57s
```
