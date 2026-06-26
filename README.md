# AI Test Copilot

AI Test Copilot 是一个本地运行的测试用例生成与评审工具。上传需求文档或接口文档后，系统会自动识别文档类型，并生成测试点、测试用例和可导出的结果文件。

## 功能

- 上传 TXT / Markdown / DOCX / PDF 文档
- 自动识别需求文档或接口文档，无需手动选择生成模式
- AI 提取功能点
- AI 生成测试点
- AI 生成测试用例并进行质量评审
- 自动识别用例类型：正向 / 逆向 / 边界
- 自动推断用例优先级：P0 / P1 / P2 / P3
- 支持人工编辑功能点、测试点、测试用例
- 导出 Excel / JSON / Markdown
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
6. 生成测试用例
7. 人工检查和编辑结果
8. 导出 Excel / JSON / Markdown

## 本地数据

项目默认使用 SQLite，本地数据和运行产物保存在项目目录：

- `aitest.db`：本地数据库
- `uploads/`：上传文件
- `outputs/`：导出文件
- `.run_logs/`：本地运行日志

这些运行数据不应该提交到 Git 仓库。

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
├── frontend/                # Streamlit 前端
├── services/                # 核心业务逻辑
├── prompts/                 # AI Prompt 模板
├── tests/                   # 测试套件
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

## License

MIT License
