# 🧪 AI Test Copilot

**AI 驱动测试用例生成与自动化测试平台**

将需求文档自动转化为结构化测试用例，一键生成可执行的 Pytest 自动化测试框架。

---

## 🚀 快速开始

### 1. 环境准备

```bash
# Python 3.11+
python --version

# 进入项目
cd ai-test-copilot

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY=sk-xxx
```

### 2. 启动后端

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

访问 http://127.0.0.1:8000/docs 查看 API 文档。

### 3. 启动前端

```bash
streamlit run frontend/app.py
```

访问 http://localhost:8501 使用 Web 界面。

---

## 📖 项目结构

```
ai-test-copilot/
├── frontend/                  # Streamlit 前端
│   ├── app.py                 # 主入口
│   ├── pages/                 # 6 个操作页面
│   │   ├── 01_📄_上传文档.py
│   │   ├── 02_🔍_功能点提取.py
│   │   ├── 03_📋_测试点生成.py
│   │   ├── 04_📝_测试用例生成.py
│   │   ├── 05_📥_导出Excel.py
│   │   └── 07_🤖_自动化测试.py
│   ├── components/            # 可复用 UI 组件
│   └── utils/                 # API 客户端、Session、UX 工具
│
├── backend/                   # FastAPI 后端
│   ├── main.py                # 应用入口 & 限流中间件
│   ├── api/                   # RESTful API 路由
│   │   ├── documents.py       # 文档上传/解析
│   │   ├── features.py        # 功能点 CRUD (V2 引擎)
│   │   ├── testpoints.py      # 测试点 CRUD (V2 引擎)
│   │   ├── testcases.py       # 测试用例 CRUD (V2 引擎)
│   │   ├── export.py          # Excel 导出 & 一键生成
│   │   └── automation.py      # 自动化测试框架生成 & 执行
│   ├── models/                # Pydantic 数据模型
│   ├── db/                    # SQLAlchemy ORM + CRUD
│   └── middleware/            # 全局异常处理
│
├── services/                  # 核心业务逻辑
│   ├── ai_client.py           # DeepSeek API 封装 (JSON 自动修复)
│   ├── document_parser.py     # 多格式文档解析 + 分块
│   ├── parser_service.py      # 统一解析服务
│   ├── feature_service.py     # 功能点提取 (Pydantic 校验 + 重试)
│   ├── testpoint_service.py   # 测试点生成 (四维度覆盖校验)
│   ├── testcase_service.py    # 测试用例生成 (IEEE 829 校验)
│   ├── excel_exporter.py      # Excel 导出 (3 工作表 + 样式)
│   ├── testcase_exporter.py   # 增强 Excel 导出
│   ├── test_script_generator.py  # 分层测试框架生成
│   └── test_executor.py       # Pytest 执行 + Allure 报告
│
├── prompts/                   # AI Prompt 模板
│   ├── feature_extraction.py / feature_extraction_v2.py
│   ├── testpoint_generation.py / testpoint_generation_v2.py
│   └── testcase_generation.py / testcase_generation_v2.py
│
├── generated_tests/           # 生成的测试框架项目
├── allure-results/            # Allure 测试结果
├── allure-report/             # Allure HTML 报告
├── outputs/                   # 导出的 Excel 文件
├── uploads/                   # 上传的文档文件
├── tests/                     # 测试套件
│
├── requirements.txt
├── config.py                  # 全局配置
├── .env.example               # 环境变量示例
├── .gitignore
└── README.md
```

---

## 🔄 工作流

### 主流程：需求 → 测试用例 → Excel

```
上传需求文档 (.txt/.docx/.pdf/.md)
        │
        ▼
  功能点提取 (V2: Pydantic 校验 + 自动重试)
        │
        ▼
  测试点生成 (V2: 四维度覆盖 + 8 并发)
        │
        ▼
  测试用例生成 (V2: 小组合并 + 10 并发 + case_type 自动推断)
        │
        ▼
  Excel 导出 (8 列标准格式 + 优先级颜色)
```

### 自动化测试：用例 → 执行框架 → 报告

```
已生成的测试用例 (DB)
        │
        ▼
  生成分层测试框架 (config/api/utils/data/case/run.py)
        │
        ▼
  pytest 参数化执行 (428 条数据 → 428 个独立测试)
        │
        ▼
  Allure HTML 报告 (请求/响应自动附件)
```

---

## 🛠️ API 文档

Base URL: `http://127.0.0.1:8000/api/v1`

| Method | Endpoint | 说明 |
|--------|----------|------|
| `POST` | `/projects/` | 创建项目 |
| `GET` | `/projects/` | 项目列表 |
| `DELETE` | `/projects/{id}` | 删除项目（级联删除关联数据） |
| `POST` | `/projects/{id}/upload` | 上传需求文档 |
| `POST` | `/projects/{id}/features/extract` | AI 提取功能点 |
| `GET` | `/projects/{id}/features` | 获取功能点 |
| `PUT` | `/projects/{id}/features/{fid}` | 修改功能点 |
| `POST` | `/projects/{id}/features/add` | 新增功能点 |
| `DELETE` | `/projects/{id}/features/{fid}` | 删除功能点（级联删除测试点/用例） |
| `POST` | `/projects/{id}/testpoints/generate` | AI 生成测试点（8 并发） |
| `POST` | `/projects/{id}/testcases/generate` | AI 生成测试用例（10 并发 + 小组合并） |
| `POST` | `/projects/{id}/export` | 导出 Excel |
| `POST` | `/projects/{id}/auto-generate` | ⚡ 一键生成全部 |
| `GET` | `/projects/{id}/automation/scripts` | 列出已生成的测试框架 |
| `DELETE` | `/projects/{id}/automation/scripts?name=xxx` | 删除测试框架 |
| `GET` | `/projects/{id}/automation/files?name=xxx` | 查看框架文件列表 |
| `GET` | `/projects/{id}/automation/view?name=xxx&file=path` | 查看框架文件内容 |
| `POST` | `/projects/{id}/automation/generate-script` | 生成测试框架 |
| `POST` | `/projects/{id}/automation/run` | 执行测试 |
| `GET` | `/projects/{id}/automation/report` | 查看 Allure 报告 |
| `POST` | `/projects/{id}/automation/pipeline` | 🤖 一键管线（生成→执行→报告） |

---

## 🔧 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Streamlit 1.41 | Python 原生 Web UI |
| 后端 | FastAPI 0.115 | 高性能异步 REST API |
| AI | DeepSeek API | 兼容 OpenAI SDK |
| 数据 | Pydantic 2.10 + SQLAlchemy 2.0 | 数据校验 + ORM |
| 存储 | SQLite + aiosqlite | 轻量数据库 |
| Excel | openpyxl 3.1 | 格式化导出 |
| 自动化测试 | pytest + allure-pytest + requests | 框架生成 & 执行 & 报告 |
| 安全 | IP 限流 + 路径遍历防护 + CORS 白名单 | 多层防护 |

---

## 🧪 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行服务层测试
pytest tests/test_services/ -v
```

---

## 🗺️ 路线图

| 版本 | 功能 |
|------|------|
| **V2.0** ✅ | 功能点/测试点/用例生成 (Pydantic 校验+并发)、Excel 导出 (标准8列)、自动化测试框架生成 (分层架构)、Allure 报告、安全加固 (限流/路径防护/CORS) |
| **V3.0** 📋 | deepseek-reasoner 推理增强、多项目管理、CI/CD 集成 |

---

## 📄 许可

MIT License
