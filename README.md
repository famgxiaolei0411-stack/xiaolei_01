# AI Test Copilot

AI Test Copilot 是一个本地运行的测试用例生成与评审工具。上传需求文档或接口文档后，系统会自动识别文档类型，并生成测试点、测试用例和可导出的结果文件。

## 功能

- 上传 TXT / Markdown / DOCX / PDF 文档
- 自动识别需求文档或接口文档，并支持手动切换接口测试 / 功能测试模式
- AI 提取功能点
- AI 生成测试点
- AI 生成测试用例并进行质量评审
- 内置测试工程 Skill：边界值分析、等价类划分、接口契约检查、优先级策略检查
- 自动识别用例类型：正向 / 逆向 / 边界
- 自动推断和评审用例优先级：P0 / P1 / P2 / P3 / P4
- 支持人工编辑功能点、测试点、测试用例
- 前端展示项目状态、流程进度、启用 Skill、质量评分和接口契约指标
- 测试点 / 测试用例 / 导出页支持表格搜索、筛选和统计信息
- 导出 Excel / JSON / Markdown，Excel 会按文档类型输出功能用例模板或接口用例模板
- 使用 SQLite，本地数据保存在项目目录

> 当前开源版本聚焦“文档到测试用例/导出”的本地工作流，不包含 RAG 知识库和自动化脚本执行能力。

## 环境要求

- Python 3.11+
- DeepSeek API Key 或 OpenAI API Key

## 默认端口

| 服务 | 默认地址 |
| --- | --- |
| 前端 Streamlit | http://127.0.0.1:8501 |
| 后端 FastAPI | http://127.0.0.1:8000 |
| 后端 API 文档 | http://127.0.0.1:8000/docs |

前端默认通过 `BACKEND_URL=http://127.0.0.1:8000` 连接后端。不要同时启动多个不同端口的后端，否则页面可能连接到旧服务。

## 快速开始

### 1. 下载项目

```bash
git clone https://github.com/famgxiaolei0411-stack/xiaolei_01.git
cd xiaolei_01
```

### 2. 创建虚拟环境

Windows:

```bat
python -m venv .venv
.venv\Scripts\activate
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置 API Key

Windows:

```bat
copy .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

编辑 `.env`，至少填写一个可用 Key：

```env
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
```

如果使用 OpenAI：

```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4o-mini
```

### 5. 一键启动

Windows:

```bat
start.bat
```

macOS / Linux:

```bash
chmod +x start.sh
./start.sh
```

启动后打开：

```text
http://127.0.0.1:8501
```

后端文档：

```text
http://127.0.0.1:8000/docs
```

## 手动启动

如果不使用一键脚本，可以打开两个终端。

终端 1，启动后端：

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

终端 2，启动前端。

Windows:

```bat
set BACKEND_URL=http://127.0.0.1:8000
streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501
```

macOS / Linux:

```bash
export BACKEND_URL=http://127.0.0.1:8000
streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501
```

## 使用流程

1. 在“上传文档”页面创建项目
2. 上传需求文档或接口文档
3. 系统自动识别文档类型
4. 提取功能点
5. 生成测试点
6. 生成测试用例，如果自动识别不符合预期，可手动选择“接口测试”或“功能测试”
7. 人工检查和编辑结果
8. 导出 Excel / JSON / Markdown，Excel 导出时也可手动选择测试用例表头模板

## Skill 机制

项目内置轻量级 Skill 机制，用于沉淀测试工程方法，而不是引入多 Agent 编排。

当前内置 Skill：

| Skill | 作用 | 接入阶段 |
| --- | --- | --- |
| BoundaryValueSkill | 补充边界值分析提示，强调最小值、最大值、临界值和越界值 | 测试点生成、测试用例生成 |
| EquivalencePartitionSkill | 补充等价类划分提示，强调有效等价类、无效等价类、输入类型和业务规则分类 | 测试点生成、测试用例生成 |
| ApiContractSkill | 本地检查接口用例的 method、url、响应断言等契约完整性 | 质量评审 |
| PriorityPolicySkill | 本地检查优先级缺失、非法值、P0 占比、高风险低优先级和 UI 类场景 P4 建议 | 质量评审 |

设计约束：

- Skill 不直接调用 AI
- Skill 不访问数据库
- Skill 不改变 API 入参、返回结构或数据库结构
- Prompt 类 Skill 只追加 prompt fragment
- Review 类 Skill 只追加 issues / suggestions / metrics
- Skill 失败时主流程降级，不影响生成和评审主链路

质量评审类 Skill 的结果会写入质量评审指标：

```text
review.metrics.skill_reviews.api_contract
review.metrics.skill_reviews.priority_policy
```

`PriorityPolicySkill` 的 P4 规则用于标识低风险 UI / 文案 / 布局 / 体验 / 可读性类检查。第一阶段只在质量评审中给出建议，不修改已有测试用例，也不影响原有评分和通过状态。

前端会在测试点、测试用例和导出页面展示已启用 Skill、质量评分和接口契约指标。

## 优先级策略

质量评审阶段会检查优先级策略一致性：

| Priority | 建议语义 |
| --- | --- |
| P0 | 阻塞级、核心链路、资金安全、权限安全、数据不可恢复风险 |
| P1 | 高风险核心功能 |
| P2 | 常规业务功能 |
| P3 | 低风险功能或边缘场景 |
| P4 | UI、文案、布局、体验、可读性等低风险检查 |

当前检查规则：

- 缺失 priority 会追加 warning
- 非法 priority 会追加 warning，合法值为 `P0 / P1 / P2 / P3 / P4`
- 登录、支付、权限、资金、订单、删除、数据丢失、接口不可用、认证、授权、安全等高风险场景，如果标为 `P3/P4`，会建议升为 `P0/P1`
- UI、界面、文案、布局、体验、可读性、颜色、样式、图标、按钮文案、提示语、占位符、对齐、展示、页面标题、间距、字体等低风险场景，如果标为 `P0/P1/P2`，会建议降为 `P4`
- 同时命中高风险和 UI 关键词时，高风险优先
- P0 占比过高会追加 warning

## Excel 模板

仓库内提供两份导出示例，便于查看字段格式：

- `docs/templates/functional_testcase_template.xlsx`：需求文档生成的功能测试用例模板
- `docs/templates/api_testcase_template.xlsx`：接口文档生成的接口测试用例模板

## 本地数据

项目默认使用 SQLite，本地数据和运行产物保存在项目目录：

- `aitest.db`：本地数据库
- `uploads/`：上传文件
- `outputs/`：导出文件
- `.run_logs/`：本地运行日志

这些运行数据不应该提交到 Git 仓库。

`docs/templates/` 下的文件是开源示例模板，可以提交到仓库；`outputs/` 下的文件是本地运行产物，不提交。

## 重置本地数据

重置会删除本地数据库、上传文件、导出文件和临时运行日志。

Windows:

```bat
reset_local_data.bat
```

macOS / Linux:

```bash
chmod +x reset_local_data.sh
./reset_local_data.sh
```

脚本会要求输入 `RESET` 后才会删除数据。

## 常见问题

### 前端显示“后端未连接”

确认后端是否启动：

```text
http://127.0.0.1:8000/health
```

如果你修改过后端端口，需要在启动前端前同步设置 `BACKEND_URL`，例如后端使用 8010：

Windows:

```bat
set BACKEND_URL=http://127.0.0.1:8010
```

macOS / Linux:

```bash
export BACKEND_URL=http://127.0.0.1:8010
```

### 页面提示“AI Key 未配置”

检查 `.env` 是否存在，并确认 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY` 已填写真实 Key，不要保留示例值。

也可以检查健康接口返回的 AI 配置状态：

```text
http://127.0.0.1:8000/health
```

### 端口被占用

先关闭已有的 FastAPI 或 Streamlit 进程，再运行 `start.bat` / `start.sh`。

如果必须换端口，请后端端口和前端 `BACKEND_URL` 一起改，避免前端连接到旧后端。

### 想重新开始测试

运行 `reset_local_data.bat` 或 `reset_local_data.sh`。

## 项目结构

```text
ai-test-copilot/
├── backend/                 # FastAPI 后端
├── frontend/                # Streamlit 前端与展示组件
│   ├── components/          # 侧边栏、平台化展示组件
│   ├── pages/               # 多页面工作流
│   └── utils/               # API client、session、UX 工具
├── services/                # 核心业务逻辑
├── prompts/                 # AI Prompt 模板
├── skills/                  # 可插拔测试工程 Skill
│   ├── core/                # Skill 基类、上下文、注册表、编排器、选择器
│   └── builtin/             # 内置 Skill 实现
├── tests/                   # 测试套件
│   ├── test_frontend/       # 前端组件、UX、页面 import smoke 测试
│   ├── test_services/       # Service 层测试
│   └── test_skills/         # Skill 基础设施与内置 Skill 测试
├── uploads/                 # 本地上传目录
├── outputs/                 # 本地导出目录
├── start.bat                # Windows 一键启动
├── start.sh                 # macOS / Linux 一键启动
├── reset_local_data.bat     # Windows 重置本地数据
├── reset_local_data.sh      # macOS / Linux 重置本地数据
├── requirements.txt
├── config.py
├── .env.example
└── README.md
```

## 测试

```bash
pytest -q
```

当前测试覆盖：

- Service 层核心流程
- Skill 注册、选择、编排和内置 Skill 行为
- 质量评审接口契约指标和优先级策略指标追加
- 前端平台化组件、统一错误提示和页面 import smoke

前端测试不会启动真实后端，也不会启动浏览器；通过 monkeypatch Streamlit 和 API client 验证页面导入与空数据 / 异常响应容错。

## License

MIT License
