# AI生成测试用例平台

AI Test Copilot 是一个本地运行的 AI 测试平台。上传需求文档或接口文档后，可以生成：

- 功能点
- 测试点
- 测试用例
- 质量评审
- Excel / JSON / Markdown 导出

内置测试工程 Skill：边界值分析、等价类划分、接口契约检查、优先级策略检查。

## 5 分钟体验

### 1. 准备 Python

安装 Python 3.11 或更高版本。

Windows 推荐安装后确认命令可用：

```bat
py -3 --version
```

macOS / Linux：

```bash
python3 --version
```

### 2. 下载并解压

下载 ZIP 后完整解压，进入包含这些文件的项目根目录：

```text
start.py
start.bat
start.sh
requirements.txt
frontend/
backend/
```

不要把 `requirements.txt`、`start.bat` 单独拖出来运行。

### 3. 一键启动

Windows：

```bat
start.bat
```

macOS / Linux：

```bash
chmod +x start.sh
./start.sh
```

也可以跨平台直接运行：

```bash
python start.py
```

启动脚本会自动完成：

- 创建 `.env`
- 创建 `.venv`
- 安装依赖
- 创建 `uploads/`、`outputs/`、`generated_tests/`
- 启动 FastAPI 后端
- 启动 Streamlit 前端
- 自动打开浏览器

打开地址：

```text
http://localhost:8501
```

后端文档：

```text
http://localhost:8000/docs
```

### 4. 配置 API Key

首次启动会自动从 `.env.example` 生成 `.env`。

编辑 `.env`，至少填一个 Key。

DeepSeek：

```env
AI_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-your-real-key
```

OpenAI：

```env
AI_PROVIDER=openai
OPENAI_API_KEY=sk-your-real-key
OPENAI_MODEL=gpt-4o-mini
```

### 5. 上传样例文档

项目根目录提供两个样例：

- `sample_prd.md`：需求文档样例
- `sample_api.yaml`：接口文档样例

进入「上传文档」页面后上传任意一个样例，然后体验：

```text
上传文档 -> 功能点 -> 测试点 -> 测试用例 -> 质量评审 -> 导出
```

## 如果依赖下载卡住

如果卡在 `Downloading streamlit / pyarrow / pandas`，先停止当前运行。

Windows 在项目根目录双击：

```bat
install_deps.bat
```

成功后再运行：

```bat
start.bat
```

脚本默认优先使用清华镜像：

```text
https://pypi.tuna.tsinghua.edu.cn/simple
```

也可以手动安装：

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 环境检查

运行：

```bash
python doctor.py
```

它会检查：

- Python 版本
- 必要文件
- `.env`
- 运行目录
- 核心依赖
- 端口占用

## Docker 运行

先准备 `.env`：

```bash
cp .env.example .env
```

编辑 `.env` 填入 API Key，然后运行：

```bash
docker compose up
```

访问：

```text
http://localhost:8501
```

## 常用命令

安装运行依赖：

```bash
pip install -r requirements.txt
```

安装测试依赖：

```bash
pip install -r requirements-dev.txt
```

运行测试：

```bash
pytest -q
```

手动启动后端：

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

手动启动前端：

```bash
python -m streamlit run frontend/app.py --server.address 127.0.0.1 --server.port 8501
```

## 默认端口

| 服务 | 地址 |
| --- | --- |
| Streamlit 前端 | http://localhost:8501 |
| FastAPI 后端 | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |

## 支持格式

支持上传：

- `.txt`
- `.md`
- `.yaml`
- `.yml`
- `.docx`
- `.pdf`

## 项目结构

```text
ai-test-copilot/
├── backend/                 # FastAPI 后端
├── frontend/                # Streamlit 前端
├── services/                # Service Layer
├── prompts/                 # Prompt Layer
├── skills/                  # 测试工程 Skill
├── tests/                   # pytest 测试
├── uploads/                 # 上传文件，首次启动自动创建
├── outputs/                 # 导出文件，首次启动自动创建
├── generated_tests/         # 生成产物，首次启动自动创建
├── sample_prd.md            # 需求文档样例
├── sample_api.yaml          # 接口文档样例
├── start.py                 # 跨平台启动器
├── start.bat                # Windows 启动
├── start.sh                 # macOS / Linux 启动
├── doctor.py                # 环境检查
├── docker-compose.yml       # Docker Compose
├── requirements.txt         # 运行依赖
├── requirements-dev.txt     # 测试依赖
├── .env.example             # 环境变量示例
└── README.md
```

## 本地数据

本项目默认使用 SQLite，本地运行会生成：

- `.env`
- `.venv/`
- `aitest.db`
- `uploads/`
- `outputs/`
- `generated_tests/`
- `.run_logs/`

这些文件不需要提交到 Git。

## 重置本地数据

Windows：

```bat
reset_local_data.bat
```

macOS / Linux：

```bash
chmod +x reset_local_data.sh
./reset_local_data.sh
```

## License

MIT License
