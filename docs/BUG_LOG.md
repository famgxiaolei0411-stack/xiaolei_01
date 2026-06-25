# 🐛 Bug 记录库

> AI Test Copilot 项目问题追踪

---

## BUG-001: 后端 API Key 缓存导致 401 认证失败

| 字段 | 内容 |
|------|------|
| **标题** | 功能点提取失败，DeepSeek API 返回 401 Authentication Fails |
| **发现日期** | 2026-06-22 |
| **严重程度** | P0（核心功能不可用） |
| **影响范围** | 所有调用 DeepSeek API 的功能（功能点提取、测试点生成、测试用例生成） |

### 现象

1. 前端点击「开始提取功能点」后返回 "未能提取到功能点"
2. 后端日志显示 `HTTP/1.1 401 Authorization Required`
3. 错误信息：`Authentication Fails, Your api key is invalid`
4. 直接 Python 脚本调用 API 正常，但通过 FastAPI 接口调用失败

### 原因

1. 项目首次启动时 `.env` 文件中的 `DEEPSEEK_API_KEY` 为占位符 `sk-your-api-key-here`
2. uvicorn 启动时通过 `python-dotenv` 一次性加载 `.env` 到内存
3. 后来虽然更新了 `.env` 为真实 Key，并 touch `config.py` 触发热重载
4. 但 `config.py` 中的 `load_dotenv()` 使用了默认参数，不会覆盖已存在的环境变量
5. 因此旧进程始终使用占位符 Key

### 解决方案

1. **临时修复**：手动重启 uvicorn 进程
   ```bash
   taskkill //F //IM uvicorn.exe
   uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```
2. **根本修复**：在 `config.py` 中使用 `override=True` 强制覆盖环境变量
   ```python
   load_dotenv(PROJECT_ROOT / ".env", override=True)
   ```

### 修复版本

v1.0.0-MVP (2026-06-22)

---

## BUG-002: Streamlit 子目录运行时 ModuleNotFoundError

| 字段 | 内容 |
|------|------|
| **标题** | `ModuleNotFoundError: No module named 'frontend'` |
| **发现日期** | 2026-06-21 |
| **严重程度** | P0（前端无法启动） |
| **影响范围** | Streamlit 前端全部页面 |

### 现象

运行 `streamlit run frontend/app.py` 时报错：
```
ModuleNotFoundError: No module named 'frontend'
```

### 原因

- 所有前端文件使用绝对导入 `from frontend.xxx import yyy`
- Streamlit 从 `frontend/` 子目录运行脚本时，Python 的 `sys.path` 不包含项目根目录
- 因此 Python 找不到 `frontend` 这个包

### 解决方案

在所有前端文件（app.py + 5 个页面）顶部添加：
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

### 修复版本

v1.0.0-MVP (2026-06-21)

---

## BUG-003: Pydantic 模型与 pytest 测试类命名冲突

| 字段 | 内容 |
|------|------|
| **标题** | pytest 将服务类误识别为测试类，导致收集错误 |
| **发现日期** | 2026-06-21 |
| **严重程度** | P2（不影响功能，仅影响开发体验） |
| **影响范围** | 测试运行时的警告输出 |

### 现象

运行 pytest 时出现警告：
```
PytestCollectionWarning: cannot collect test class 'TestPointService' 
because it has a __init__ constructor
```
同时出现在 `TestScriptGenerator`、`TestExecutor`、`TestReport` 等服务类上。

### 原因

- pytest 默认收集所有以 `Test` 开头的类为测试类
- 服务类命名如 `TestPointService`、`TestScriptGenerator` 符合此规则
- 但这些类有 `__init__` 构造函数，pytest 无法收集，发出警告

### 解决方案

1. **快速方案**：在 `pyproject.toml` 或 `pytest.ini` 中配置过滤规则
2. **根本方案**：重命名服务类，避免 `Test` 前缀（如改为 `PointService`、`ScriptGenerator`）
   - 权衡：改动范围大，影响现有导入

### 修复版本

暂不修复（警告不影响功能，V2 重构时统一处理）

---

## BUG-004: Windows GBK 编码导致终端输出乱码

| 字段 | 内容 |
|------|------|
| **标题** | 中文终端输出在 Windows GBK 编码下显示为乱码 |
| **发现日期** | 2026-06-21 |
| **严重程度** | P2（不影响功能，仅影响开发体验） |
| **影响范围** | 所有终端日志输出 |

### 现象

Python print 输出中文时，Windows 终端显示为乱码：
```
���ܵ���ȡʧ��
```

### 原因

- Windows 中文版终端默认使用 GBK 编码
- Python 3.x 默认使用 UTF-8
- 当 UTF-8 编码的中文输出到 GBK 终端时出现乱码

### 解决方案

1. **Git Bash 中**：设置 `export PYTHONIOENCODING=utf-8`
2. **PowerShell 中**：`chcp 65001` 切换到 UTF-8 编码
3. **代码中**：使用 `logging` 模块输出到文件（`encoding="utf-8"`）

### 修复版本

暂不修复（实际功能不受影响，仅终端显示问题）

---

---

## BUG-006: 测试点 / 测试用例列表缺少 id 字段导致 KeyError

| 字段 | 内容 |
|------|------|
| **标题** | 前端页面 `KeyError: 'id'`，测试点/测试用例列表渲染崩溃 |
| **发现日期** | 2026-06-22 |
| **严重程度** | P0（前端页面白屏） |
| **影响范围** | 测试点生成页面、测试用例生成页面 |

### 现象

```
KeyError: 'id'
Traceback:
File "frontend\pages\03_测试点生成.py", line 130, in render_testpoints_list
    tp_ids = [tp["id"] for tp in testpoints]
```

### 原因

`backend/db/crud.py` 中的 `orm_to_dict()` 函数在转换 `TestPointORM` 和 `TestCaseORM` 时遗漏了 `"id"` 字段，导致 API 返回的数据中不含 `id`。

```python
# 修复前
if isinstance(orm_obj, TestPointORM):
    return {
        "feature_name": orm_obj.feature_name,  # 缺少 "id"
        ...
    }

# 修复后
if isinstance(orm_obj, TestPointORM):
    return {
        "id": orm_obj.id,                      # 补上 id
        "feature_name": orm_obj.feature_name,
        ...
    }
```

### 解决方案

在 `orm_to_dict()` 的 `TestPointORM` 和 `TestCaseORM` 分支中补上 `"id": orm_obj.id`。

同时发现 uvicorn 热重载不可靠，需要手动重启进程才能加载修改后的代码。

### 修复版本

v1.0.0-MVP (2026-06-22)

---

## BUG-007: 页面切换后数据丢失

| 字段 | 内容 |
|------|------|
| **标题** | 左侧模块切换后上一个模块的数据消失，后续步骤提示缺少前置数据 |
| **发现日期** | 2026-06-22 |
| **严重程度** | P0（工作流断裂） |
| **影响范围** | 全部 5 个操作页面 |

### 现象

1. 在「功能点提取」页面成功提取功能点后
2. 切换到「测试点生成」页面，提示"请先提取功能点"
3. 切回「功能点提取」页面，已显示的功能点列表消失
4. 实际上数据已存入数据库，但页面没有重新加载

### 原因

两个根因叠加：

1. **缺少 `init_session()`**：各子页面（pages/）没有调用 `init_session()`，仅依赖 `app.py` 初始化。当用户刷新或从子页面直接进入时，`st.session_state` 中的 `project_id` 为 `None`。

2. **缺少自动数据刷新**：页面切换后没有从后端 API 重新拉取数据，仅依赖 `st.session_state` 中可能已过期的缓存。

### 解决方案

1. 所有 5 个页面添加 `init_session()` 调用
2. 创建统一侧边栏组件 `render_sidebar()`，显示工作流进度
3. 每个页面加载时从后端 API 实时拉取数据，而不是依赖 session_state
4. 自动检测当前步骤状态

### 修复版本

v1.0.0-MVP (2026-06-22)

---

---

## BUG-008: auto-generate 接口 500 错误 — save_features 未导入

| 字段 | 内容 |
|------|------|
| **标题** | 一键生成接口报 500 Internal Server Error |
| **发现日期** | 2026-06-22 |
| **严重程度** | P0（核心功能不可用） |
| **影响范围** | 一键生成功能 |

### 现象

```
Server error '500 Internal Server Error' for url
'http://127.0.0.1:8000/api/v1/projects/1/auto-generate'
```

后端日志：
```
NameError: name 'save_features' is not defined
```

### 原因

`backend/api/export.py` 顶层 import 只导入了 `get_*` 函数，`auto_generate_all()` 中使用的 `save_features`、`save_testpoints`、`save_testcases` 未导入。

### 解决方案

顶层 import 补上三个缺失的 CRUD 函数：
```python
from backend.db.crud import (
    ...,
    save_features,
    save_testcases,
    save_testpoints,
)
```

### 修复版本

v1.0.0-MVP (2026-06-22)

---

## BUG-009: AI 返回 JSON 包裹在 markdown 代码块中解析失败

| 字段 | 内容 |
|------|------|
| **标题** | `chat_json()` 无法解析 LLM 返回的 markdown 包裹的 JSON |
| **发现日期** | 2026-06-22 |
| **严重程度** | P1（AI 生成功能间歇性失败） |
| **影响范围** | 测试点生成、测试用例生成 |

### 现象

测试点生成失败，返回 0 个测试点。日志显示：
```
无法解析 AI 返回的 JSON，原始内容: ```json
{...}
```
### 原因

1. 旧版解析逻辑仅处理 `"```"` 开头的情况，LLM 输出在代码块前有额外文字时无法提取
2. 正则搜索 `{...}` 只尝试一次，失败即抛出异常
3. 没有使用正则提取 ` ```json ... ``` ` 代码块内容

### 解决方案

重构 `chat_json()` 解析逻辑，三级策略：
1. 正则匹配 ` ```json ... ``` ` 代码块提取内容
2. 去掉开头/结尾 ` ``` ` 残留标记
3. 循环 2 次查找最外层 `{...}` / `[...]` 边界截取

### 修复版本

v1.0.0-MVP (2026-06-22)

---

---

## BUG-010: add_feature/add_testpoint/add_testcase 调用 save_* 导致数据丢失

| 字段 | 内容 |
|------|------|
| **标题** | `add_*` 端点调用 `save_*`（先 DELETE ALL 再 INSERT），导致已有数据全部丢失 |
| **发现日期** | 2026-06-22 |
| **严重程度** | P0（致命数据丢失） |
| **发现方式** | Code Review — 跨文件调用链追踪 |
| **影响范围** | 功能点新增、测试点新增、测试用例新增 |

### 现象

用户手动新增 1 条功能点 → 之前提取的 48 条功能点全部被删除，只剩刚添加的 1 条。

### 原因

`backend/db/crud.py` 中的 `save_features`/`save_testpoints`/`save_testcases` 设计为「全量替换」：
```python
await db.execute(delete(FeatureORM).where(FeatureORM.project_id == project_id))
# 然后插入新数据
```
但 `add_*` 端点调用时只传单条数据，变成「全量替换为单条」。

### 解决方案

新增 `insert_feature`/`insert_testpoint`/`insert_testcase` 函数（只 INSERT 不 DELETE），`add_*` 端点改用这些函数。

### 修复版本

v1.0.0-MVP (2026-06-22)

---

## BUG-011: temperature=0 被 falsy 值陷阱忽略

| 字段 | 内容 |
|------|------|
| **标题** | `chat(temperature=0)` 期望确定性输出，实际被替换为默认值 0.3 |
| **发现日期** | 2026-06-22 |
| **严重程度** | P1 |
| **发现方式** | Code Review — Python 语言陷阱扫描 |

### 现象

```python
# ai_client.py line 85
temperature=temperature or self._temperature,
```
当 `temperature=0` 时（0 是 falsy），`0 or 0.3` = `0.3`，导致期望的确定性输出被忽略。

### 解决方案

改为 `temperature if temperature is not None else self._temperature`

### 修复版本

v1.0.0-MVP (2026-06-22)

---

## BUG-012: get_project() 前端调用 404

| 字段 | 内容 |
|------|------|
| **标题** | `api_client.get_project()` 调用 `GET /projects/{id}` 但后端无此路由 |
| **发现日期** | 2026-06-22 |
| **严重程度** | P2 |
| **发现方式** | Code Review — 跨文件调用链追踪 |

### 解决方案

在 `backend/api/documents.py` 添加 `GET /{project_id}` 路由。

### 修复版本

v1.0.0-MVP (2026-06-22)

---

## BUG-013: 一键生成下载链接硬编码 localhost

| 字段 | 内容 |
|------|------|
| **标题** | 页面 01 硬编码 `http://127.0.0.1:8000`，非默认端口时下载失效 |
| **发现日期** | 2026-06-22 |
| **严重程度** | P2 |

### 解决方案

改用 `frontend.utils.constants.BACKEND_URL` 变量。

### 修复版本

v1.0.0-MVP (2026-06-22)

---

## BUG-014: TestScriptGenerator 对整数 id 调用 .lower() 崩溃

| 字段 | 内容 |
|------|------|
| **标题** | 数据库返回的 `id` 为整数时，`case_id.lower()` 抛出 AttributeError |
| **发现日期** | 2026-06-22 |
| **严重程度** | P2 |

### 解决方案

`case_id = str(tc.get("id", "TC-000"))` 强制转字符串。

### 修复版本

v1.0.0-MVP (2026-06-22)

---

---

## 全面测试报告 (2026-06-22)

### 测试范围
- 用户角度测试：完整工作流（8 项）
- 异常场景测试：错误输入、空数据（7 项）
- 边界值测试：极限输入（4 项）
- 安全测试：注入、遍历（5 项）

### 测试结果：24 项测试，22 passed / 2 failed

| # | 测试项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | 创建项目 | ✅ | - |
| 2 | 项目列表 | ✅ | - |
| 3 | 项目详情 | ✅ | - |
| 4 | 不存在项目 | ✅ | 返回 404 |
| 5 | 上传 TXT | ✅ | - |
| 6 | 提取功能点 | ✅ | - |
| 7 | 获取功能点 | ✅ | - |
| 8 | 上传空白文档 | ✅ | 正确解析 |
| 9 | 不支持的格式 | ✅ | 返回 400 |
| 10 | 无文件上传 | ✅ | 返回 422 |
| 11 | 空项目提取 | ✅ | 返回 400 |
| 12 | 不存在项目操作 | ✅ | 返回 404 |
| 13 | 导出不存在项目 | ✅ | 返回 404 |
| 14 | 特殊字符项目名 | ✅ | - |
| 15 | 超大请求体 | ✅ | 返回 422 |
| 16 | SQL 注入 | ✅ | 类型校验拦截 |
| 17 | XSS 内容上传 | ✅ | 正常解析 |
| 18 | 超大文件 10MB | ✅ | - |
| 19 | 方法不允许 | ✅ | 返回 405 |
| 20 | 项目名参数忽略 | ⚠️ | 设计如此（自动生成） |
| 21 | 空名称创建 | ⚠️ | 设计如此（自动生成） |
| 22 | 路径遍历 | ⚠️ | 返回 404（类型校验拦截） |

### 已知未修复问题
- BUG-003: pytest 类名冲突警告
- BUG-004: Windows GBK 终端乱码
- 异常吞没：3 个 AI 生成器静默返回 []（需要结构性重构，V2 处理）

---

## 统计

| 版本 | 修复数 | 暂缓数 |
|------|--------|--------|
| v1.0.0-MVP | 13 | 1 |
| **合计** | **13** | **1** |
