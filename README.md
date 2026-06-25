# AI Test Copilot

AI Test Copilot 是一个本地运行的测试用例生成与评审工具。上传需求文档或接口文档后，系统会自动识别文档类型，并生成测试点、测试用例和 Excel 文件。

## 功能

- 上传 TXT / Markdown / DOCX / PDF 文档
- 自动识别需求文档或接口文档
- AI 提取功能点
- AI 生成测试点
- AI 生成测试用例并进行质量评审
- 支持人工编辑功能点、测试点、测试用例
- 导出 Excel / JSON / Markdown
- 使用 SQLite，本地数据保存在项目目录

## 环境要求

- Python 3.11+
- DeepSeek API Key 或 OpenAI API Key

## 快速开始

### 1. 下载项目

```bash
git clone <your-repo-url>
cd ai-test-copilot
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

打开前端：

```text
http://127.0.0.1:8501
```

后端文档：

```text
http://127.0.0.1:8000/docs
```

## 手动启动

如果不使用一键脚本，可以打开两个终端。

终端 1:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

终端 2:

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
7. 导出 Excel

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

先确认后端是否启动：

```text
http://127.0.0.1:8000/health
```

如果后端端口不是 8000，需要启动前端前设置 `BACKEND_URL`。

### 页面提示“AI Key 未配置”

检查 `.env` 是否存在，并确认 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY` 已填写真实 Key，不要保留示例值。

### 端口被占用

可以手动换端口启动后端，例如：

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8001 --reload
```

然后启动前端前设置：

```bash
BACKEND_URL=http://127.0.0.1:8001
```

Windows 使用：

```bat
set BACKEND_URL=http://127.0.0.1:8001
```

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
