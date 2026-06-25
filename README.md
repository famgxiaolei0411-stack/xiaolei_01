# 🧪 AI Test Copilot

**AI 驱动测试用例生成与评审平台**

将需求文档自动转化为结构化测试用例，从需求到 Excel 一键完成，生成后自动评审。

---

## 🚀 快速开始

### 1. 环境准备

```bash
# Python 3.11+
python --version

cd ai-test-copilot
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
│   ├── pages/                 # 5 个操作页面
│   │   ├── 01_📄_上传文档.py
│   │   ├── 02_🔍_功能点提取.py
│   │   ├── 03_📋_测试点生成.py
│   │   ├── 04_📝_测试用例生成.py
│   │   └── 05_📥_导出Excel.py
│   ├── components/            # 可复用 UI 组件
│   └── utils/                 # API 客户端、Session、UX 工具
│
├── backend/                   # FastAPI 后端
│   ├── main.py                # 应用入口 & 限流中间件
│   ├── api/                   # RESTful API 路由
│   │   ├── documents.py       # 文档上传/解析
│   │   ├── features.py        # 功能点 CRUD
│   │   ├── testpoints.py      # 测试点 CRUD
│   │   ├── testcases.py       # 测试用例生成+评审
│   │   └── export.py          # Excel 导出 & 一键生成
│   ├── models/                # Pydantic 数据模型
│   ├── db/                    # SQLAlchemy ORM + CRUD
│   └── middleware/            # 全局异常处理
│
├── services/                  # 核心业务逻辑
│   ├── ai_client.py           # DeepSeek API 封装 (JSON 自动修复)
│   ├── document_parser.py     # 多格式文档解析 + 分块
│   ├── feature_service.py     # 功能点提取 (Pydantic 校验 + 重试)
│   ├── testpoint_service.py   # 测试点生成 (四维度覆盖校验)
│   ├── testcase_service.py    # 测试用例生成+自评审 (IEEE 829 校验)
│   └── excel_exporter.py      # Excel 导出 (8 列标准格式 + 样式)
│
├── prompts/                   # AI Prompt 模板
│   ├── feature_extraction.py / feature_extraction_v2.py
│   ├── testpoint_generation.py / testpoint_generation_v2.py
│   └── testcase_generation.py / testcase_generation_v2.py
│
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

```
上传需求文档 (.txt/.docx/.pdf/.md)
        │
        ▼
  功能点提取 (Pydantic 校验 + 自动重试)
        │
        ▼
  测试点生成 (四维度覆盖 + 8 并发)
        │
        ▼
  测试用例生成 (小组合并 + 10 并发 + 自动评审)
        │
        ▼
  生成后自动评审 (本地检查 + AI 深度评审 → 评分/问题标记/改进建议)
        │
        ▼
  Excel 导出 (8 列标准格式 + 优先级颜色)
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
| `POST` | `/projects/{id}/testcases/generate` | AI 生成测试用例 + 自动评审 |
| `POST` | `/projects/{id}/export` | 导出 Excel |
| `POST` | `/projects/{id}/auto-generate` | ⚡ 一键生成全部（含评审） |

---

## 🔧 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Streamlit | Python 原生 Web UI |
| 后端 | FastAPI | 高性能异步 REST API |
| AI | DeepSeek API | 兼容 OpenAI SDK |
| 数据 | Pydantic + SQLAlchemy | 数据校验 + ORM |
| 存储 | SQLite + aiosqlite | 轻量数据库 |
| Excel | openpyxl | 格式化导出 |
| 安全 | IP 限流 + 路径遍历防护 + CORS 白名单 | 多层防护 |

---

## 🗺️ 路线图

| 版本 | 功能 |
|------|------|
| **V2.0** ✅ | 功能点/测试点/用例生成 (Pydantic 校验+并发)、生成后自动评审、Excel 导出 (标准8列)、安全加固 |

---

## 📄 许可

MIT License
