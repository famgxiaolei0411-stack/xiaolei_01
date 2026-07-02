"""
pytest 全局配置 & Fixtures
============================
提供测试所需的共享资源：测试客户端、数据库、临时文件等。
"""

import os

import pytest
import tempfile
from pathlib import Path


@pytest.fixture(scope="session")
def project_root() -> Path:
    """返回项目根目录路径。

    Returns:
        项目根目录的 Path 对象
    """
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def temp_dir() -> Path:
    """创建临时目录，测试结束后自动清理。

    Returns:
        临时目录的 Path 对象
    """
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def sample_txt_file(temp_dir: Path) -> Path:
    """创建示例 TXT 需求文档。

    Returns:
        示例 TXT 文件路径
    """
    content = """用户管理系统需求规格说明书

1. 用户注册
用户可以通过手机号或邮箱进行注册。
注册时需要填写用户名、密码、确认密码。
密码长度要求 8-20 位，包含大小写字母和数字。
注册成功后跳转到登录页面。

2. 用户登录
用户可以通过用户名+密码进行登录。
连续输错 5 次密码，账号锁定 30 分钟。
支持"记住我"功能，有效期 7 天。

3. 密码修改
登录用户可以修改自己的密码。
需要先输入原密码验证身份。
新密码不能与最近 3 次密码相同。
"""
    file_path = temp_dir / "test_requirements.txt"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def pytest_collection_modifyitems(config, items) -> None:
    """Skip real external-service tests unless explicitly enabled."""
    if os.getenv("RUN_INTEGRATION") == "1":
        return

    skip_integration = pytest.mark.skip(
        reason="integration tests are skipped by default; set RUN_INTEGRATION=1 to run"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
