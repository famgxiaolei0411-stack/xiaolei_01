"""
测试框架生成器 — 测试用例 → 分层 Pytest + Allure 自动化测试项目
=================================================================
参考 api-test-framework skill 的分层架构：
  config/ → api/ → utils/ → data/ → case/ → run.py

生成完整可运行的测试项目，而非单个脚本。
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config import GENERATED_TESTS_DIR

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 配置
# ══════════════════════════════════════════════════════════

@dataclass
class ScriptOptions:
    """测试框架生成选项。"""
    module_name: str = "通用模块"
    base_url: str = "http://localhost:8000"
    timeout: int = 30


# ══════════════════════════════════════════════════════════
# 模板 — config/settings.py
# ══════════════════════════════════════════════════════════

SETTINGS_TEMPLATE = '''"""
测试配置 — 集中管理环境参数
=============================
"""
import os


class Settings:
    """全局测试配置。"""
    BASE_URL = "{base_url}"
    TIMEOUT = {timeout}
    HEADERS = {{"Content-Type": "application/json"}}
    ENV = os.getenv("TEST_ENV", "test")

    @classmethod
    def get_base_url(cls):
        return cls.BASE_URL
'''

# ══════════════════════════════════════════════════════════
# 模板 — api/base_api.py
# ══════════════════════════════════════════════════════════

BASE_API_TEMPLATE = '''"""
API 基类 — 封装 HTTP 请求 + 日志 + Allure
===========================================
"""
import json
import logging

import allure
import requests

from config.settings import Settings

logger = logging.getLogger(__name__)


class BaseApi:
    """HTTP 请求基类，提供统一请求方法和 Allure 附件。"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(Settings.HEADERS)

    def _attach_request(self, method: str, url: str, headers: dict, body: str = ""):
        """将请求信息挂载到 Allure。"""
        msg = f"{{method}} {{url}}\\n{{body}}"
        allure.attach(msg, name="请求", attachment_type=allure.attachment_type.TEXT)

    def _attach_response(self, resp: requests.Response):
        """将响应信息挂载到 Allure。"""
        body = resp.text
        try:
            body = json.dumps(resp.json(), indent=2, ensure_ascii=False)
        except Exception:
            pass
        allure.attach(
            body,
            name=f"响应 {{resp.status_code}}",
            attachment_type=allure.attachment_type.TEXT,
        )

    def request(self, method: str, path: str, **kwargs):
        url = Settings.get_base_url() + path
        timeout = kwargs.pop("timeout", Settings.TIMEOUT)
        body_str = kwargs.get("json", kwargs.get("data", ""))
        if isinstance(body_str, dict):
            body_str = json.dumps(body_str, ensure_ascii=False)

        self._attach_request(method, url, Settings.HEADERS, body_str)
        logger.info("请求: %s %s", method, url)

        resp = self.session.request(method, url, timeout=timeout, **kwargs)

        self._attach_response(resp)
        logger.info("响应: %d (%d bytes)", resp.status_code, len(resp.text))
        return resp

    def get(self, path, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path, **kwargs):
        return self.request("POST", path, **kwargs)

    def put(self, path, **kwargs):
        return self.request("PUT", path, **kwargs)

    def delete(self, path, **kwargs):
        return self.request("DELETE", path, **kwargs)
'''

# ══════════════════════════════════════════════════════════
# 模板 — utils/assertion.py
# ══════════════════════════════════════════════════════════

ASSERTION_TEMPLATE = '''"""
自定义断言 — 统一错误格式
============================
"""


class Assertion:
    """断言工具类，提供语义化的验证方法。"""

    @staticmethod
    def status_code(resp, code=200):
        assert resp.status_code == code, (
            f"[状态码异常] 期望 {{code}}，实际 {{resp.status_code}}。"
            f"响应：{{resp.text[:500]}}"
        )

    @staticmethod
    def equal(expected, actual, msg=""):
        assert expected == actual, (
            f"[断言失败] 期望 {{expected}}，实际 {{actual}}。{{msg}}"
        )

    @staticmethod
    def in_text(expected, text, msg=""):
        assert expected in str(text), (
            f"[断言失败] 期望 '{{expected}}' 未在响应中找到。{{msg}}"
        )

    @staticmethod
    def not_empty(obj, msg=""):
        assert obj, f"[断言失败] 期望非空。{{msg}}"
'''

# ══════════════════════════════════════════════════════════
# 模板 — utils/logger.py
# ══════════════════════════════════════════════════════════

LOGGER_TEMPLATE = '''"""
日志配置
=========
"""
import logging
import sys
from pathlib import Path


def setup_logger(name: str = "api_test") -> logging.Logger:
    """初始化日志器：输出到控制台 + 文件。"""
    log_dir = Path(__file__).parent.parent / "report"
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(console)

    file_handler = logging.FileHandler(
        log_dir / "test.log", encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(file_handler)

    return logger
'''

# ══════════════════════════════════════════════════════════
# 模板 — utils/data_loader.py
# ══════════════════════════════════════════════════════════

DATA_LOADER_TEMPLATE = '''"""
测试数据加载器
===============
"""
import json
from pathlib import Path


def load_data(file_name: str) -> list[dict]:
    """从 data/ 目录加载 JSON 测试数据。"""
    data_path = Path(__file__).parent.parent / "data" / file_name
    with open(data_path, encoding="utf-8") as f:
        return json.load(f)
'''

# ══════════════════════════════════════════════════════════
# 模板 — case/conftest.py
# ══════════════════════════════════════════════════════════

CONFTEST_TEMPLATE = '''"""
pytest fixtures
================
"""
import sys
from pathlib import Path

import pytest

# 将项目根目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logger import setup_logger


@pytest.fixture(scope="session")
def logger():
    return setup_logger()
'''

# ══════════════════════════════════════════════════════════
# 模板 — case/test_xxx.py
# ══════════════════════════════════════════════════════════

TEST_CASE_TEMPLATE = '''"""
{module_name} — 自动化测试用例
================================
生成时间：{timestamp}
测试用例数：{case_count}
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import allure
import pytest

from api.base_api import BaseApi
from utils.assertion import Assertion as A
from utils.data_loader import load_data


@allure.feature("{module_name}")
class Test{module_name_ascii}:
    """{module_name} 接口自动化测试套件。"""

    def setup_method(self):
        self.api = BaseApi()

    @pytest.mark.parametrize("case", load_data("{data_file}"))
    def test_case(self, case):
        """{{case['title']}}"""
        case_id = case.get("id", "")
        title = case.get("title", "")
        method = case.get("method", "GET")
        path = case.get("path", "/")
        body = case.get("body", None)
        expected_code = case.get("expected_code", 200)
        expected_contains = case.get("expected_contains", "")

        with allure.step(f"{{case_id}}: {{title}}"):
            allure.dynamic.title(title)
            allure.dynamic.tag(case.get("priority", "P2"))
            allure.dynamic.tag(case.get("case_type", "正向"))
            allure.dynamic.description(case.get("precondition", ""))

            # 发送请求
            resp = self.api.request(method, path, json=body)

            # 断言
            A.status_code(resp, expected_code)
            if expected_contains:
                A.in_text(expected_contains, resp.text)
'''

# ══════════════════════════════════════════════════════════
# 模板 — pytest.ini
# ══════════════════════════════════════════════════════════

PYTEST_INI_TEMPLATE = '''[pytest]
testpaths = case
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -s -v --alluredir=../allure-results
'''

# ══════════════════════════════════════════════════════════
# 模板 — run.py
# ══════════════════════════════════════════════════════════

RUN_PY_TEMPLATE = '''"""
一键运行 — 执行测试 + 生成 Allure 报告
=========================================
"""
import os
import sys
import subprocess
from pathlib import Path

if __name__ == "__main__":
    project_root = Path(__file__).parent
    os.chdir(str(project_root))
    sys.path.insert(0, str(project_root))

    print("=" * 60)
    print("开始执行自动化测试...")
    print("=" * 60)

    # 执行 pytest
    exit_code = subprocess.run([sys.executable, "-m", "pytest"]).returncode

    # 生成 Allure 报告
    print("\\n" + "=" * 60)
    print("生成 Allure 报告...")
    subprocess.run(["allure", "generate", "../allure-results", "-o", "../allure-report", "--clean"])
    print(f"报告路径: {{project_root.parent / 'allure-report' / 'index.html'}}")
    print("=" * 60)

    sys.exit(exit_code)
'''

# ══════════════════════════════════════════════════════════
# TestFrameworkGenerator
# ══════════════════════════════════════════════════════════

class TestFrameworkGenerator:
    """测试框架生成器。

    将测试用例列表转换为完整的分层 Pytest + Allure 测试项目。

    Usage:
        gen = TestFrameworkGenerator()
        path = gen.generate(testcases, ScriptOptions(
            module_name="用户管理",
            base_url="http://localhost:8000",
        ))
        # → generated_tests/用户管理_20250101/
        #     ├── config/settings.py
        #     ├── api/base_api.py
        #     ├── utils/assertion.py, logger.py
        #     ├── data/用户管理.json
        #     ├── case/conftest.py, test_用户管理.py
        #     ├── requirements.txt
        #     ├── pytest.ini
        #     └── run.py
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self._output_dir = output_dir or GENERATED_TESTS_DIR
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        testcases: list[dict[str, Any]],
        options: ScriptOptions | None = None,
    ) -> Path:
        """生成完整的测试框架项目。

        Args:
            testcases: 测试用例列表
            options: 生成选项

        Returns:
            生成的框架根目录路径

        Raises:
            ValueError: testcases 为空
        """
        if not testcases:
            raise ValueError("测试用例列表不能为空")

        options = options or ScriptOptions()
        module_name = options.module_name
        safe_name = self._to_safe_name(module_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        root = self._output_dir / f"{safe_name}_{timestamp}"

        logger.info(
            "生成测试框架: 模块=%s, 用例数=%d", module_name, len(testcases)
        )

        # ── 创建目录结构 ──────────────────────────
        (root / "config").mkdir(parents=True, exist_ok=True)
        (root / "api").mkdir(parents=True, exist_ok=True)
        (root / "utils").mkdir(parents=True, exist_ok=True)
        (root / "data").mkdir(parents=True, exist_ok=True)
        (root / "case").mkdir(parents=True, exist_ok=True)
        (root / "report").mkdir(parents=True, exist_ok=True)

        # ── 生成文件 ──────────────────────────────
        self._write_init(root, "config")
        self._write_init(root, "api")
        self._write_init(root, "utils")
        self._write_init(root, "data")

        # config/settings.py
        (root / "config" / "settings.py").write_text(
            SETTINGS_TEMPLATE.format(
                base_url=options.base_url,
                timeout=options.timeout,
            ),
            encoding="utf-8",
        )

        # api/base_api.py
        (root / "api" / "base_api.py").write_text(
            BASE_API_TEMPLATE, encoding="utf-8"
        )

        # utils/assertion.py
        (root / "utils" / "assertion.py").write_text(
            ASSERTION_TEMPLATE, encoding="utf-8"
        )

        # utils/logger.py
        (root / "utils" / "logger.py").write_text(
            LOGGER_TEMPLATE, encoding="utf-8"
        )

        # utils/data_loader.py
        (root / "utils" / "data_loader.py").write_text(
            DATA_LOADER_TEMPLATE, encoding="utf-8"
        )

        # data/{module}.json — 测试数据
        data_file = f"{safe_name}.json"
        test_data = self._build_test_data(testcases, module_name)
        (root / "data" / data_file).write_text(
            json.dumps(test_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # case/conftest.py
        (root / "case" / "conftest.py").write_text(
            CONFTEST_TEMPLATE, encoding="utf-8"
        )

        # case/__init__.py
        self._write_init(root, "case")

        # case/test_{module}.py
        test_file = f"test_{safe_name}.py"
        module_ascii = self._to_ascii(module_name)
        (root / "case" / test_file).write_text(
            TEST_CASE_TEMPLATE.format(
                module_name=module_name,
                module_name_ascii=module_ascii,
                timestamp=timestamp,
                case_count=len(testcases),
                data_file=data_file,
            ),
            encoding="utf-8",
        )

        # requirements.txt
        (root / "requirements.txt").write_text(
            "pytest>=8.0.0\nrequests>=2.31.0\nallure-pytest>=2.13.0\n",
            encoding="utf-8",
        )

        # pytest.ini
        (root / "pytest.ini").write_text(
            PYTEST_INI_TEMPLATE, encoding="utf-8",
        )

        # run.py
        (root / "run.py").write_text(
            RUN_PY_TEMPLATE, encoding="utf-8",
        )

        logger.info("测试框架生成完成: %s", root)
        return root

    # ── 数据构建 ──────────────────────────────────

    def _build_test_data(
        self,
        testcases: list[dict[str, Any]],
        module_name: str,
    ) -> list[dict[str, Any]]:
        """将测试用例转换为 JSON 数据驱动格式。

        每条测试数据包含：method, path, body, expected_code, expected_contains
        """
        data: list[dict[str, Any]] = []
        for tc in testcases:
            case_id = tc.get("case_id", tc.get("id", "TC-001"))
            title = tc.get("title", "未命名")
            expected = tc.get("expected", tc.get("expected_result", ""))

            # 推断 HTTP method 和 path
            # 测试用例的 steps 中可能包含 HTTP 调用信息
            method, path = self._infer_request(title, module_name)

            item: dict[str, Any] = {
                "id": case_id,
                "title": title,
                "method": method,
                "path": path,
                "priority": tc.get("priority", "P2"),
                "case_type": tc.get("case_type", "正向"),
                "precondition": tc.get("precondition", "无"),
                "expected_code": 200 if tc.get("case_type", "正向") != "逆向" else 400,
                "expected_contains": expected[:100] if expected else "",
            }
            data.append(item)

        return data

    @staticmethod
    def _infer_request(title: str, module_name: str) -> tuple[str, str]:
        """从用例标题推断 HTTP 方法和路径。"""
        title_lower = title.lower()
        if any(w in title_lower for w in ["创建", "新增", "添加", "提交", "登录", "create", "add"]):
            return ("POST", f"/api/{module_name}")
        if any(w in title_lower for w in ["更新", "修改", "编辑", "update", "edit"]):
            return ("PUT", f"/api/{module_name}/1")
        if any(w in title_lower for w in ["删除", "移除", "delete", "remove"]):
            return ("DELETE", f"/api/{module_name}/1")
        return ("GET", f"/api/{module_name}")

    # ── 工具方法 ──────────────────────────────────

    @staticmethod
    def _write_init(root: Path, subdir: str) -> None:
        """写入空 __init__.py。"""
        (root / subdir / "__init__.py").write_text("", encoding="utf-8")

    @staticmethod
    def _to_safe_name(name: str) -> str:
        """转为安全的文件名（保留中文）。"""
        return "".join(c if c.isalnum() or c in "._- " else "_" for c in name).strip()[:50]

    @staticmethod
    def _to_ascii(name: str) -> str:
        """模块名转 ASCII Python 类名。"""
        import re
        result = "".join(c for c in name if c.isascii() and c.isalnum())
        if result:
            return result[:30]
        import hashlib
        return "Module" + hashlib.md5(name.encode()).hexdigest()[:8]
