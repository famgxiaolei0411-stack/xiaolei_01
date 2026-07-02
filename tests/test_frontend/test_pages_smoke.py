from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _Column(_Context):
    def __init__(self, st):
        self._st = st

    def __getattr__(self, name):
        return getattr(self._st, name)


class _FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = {
            "project_id": 1,
            "project_name": "Smoke 项目",
            "project_status": "testcases_generated",
            "testcase_mode": "api",
        }

    def set_page_config(self, *args, **kwargs):
        return None

    def stop(self):
        return None

    def rerun(self):
        return None

    def container(self, *args, **kwargs):
        return _Context()

    def expander(self, *args, **kwargs):
        return _Context()

    def form(self, *args, **kwargs):
        return _Context()

    def spinner(self, *args, **kwargs):
        return _Context()

    def columns(self, spec):
        count = spec if isinstance(spec, int) else len(spec)
        return [_Column(self) for _ in range(count)]

    def button(self, *args, **kwargs):
        return False

    def form_submit_button(self, *args, **kwargs):
        return False

    def radio(self, *args, options=None, index=0, **kwargs):
        return list(options or [])[index]

    def selectbox(self, *args, **kwargs):
        options = kwargs.get("options")
        if options is None and len(args) > 1:
            options = args[1]
        values = list(options or [])
        index = kwargs.get("index", 0)
        return values[index] if values else ""

    def multiselect(self, *args, **kwargs):
        return []

    def text_input(self, *args, **kwargs):
        return kwargs.get("value", "")

    def text_area(self, *args, **kwargs):
        return kwargs.get("value", "")

    def dataframe(self, *args, **kwargs):
        return None

    def metric(self, *args, **kwargs):
        return None

    def markdown(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        return None

    def info(self, *args, **kwargs):
        return None

    def warning(self, *args, **kwargs):
        return None

    def success(self, *args, **kwargs):
        return None

    def error(self, *args, **kwargs):
        return None

    def write(self, *args, **kwargs):
        return None

    def title(self, *args, **kwargs):
        return None

    def subheader(self, *args, **kwargs):
        return None

    def code(self, *args, **kwargs):
        return None


def _ok(data):
    return {"data": data}


@pytest.fixture
def fake_frontend_runtime(monkeypatch):
    fake_st = _FakeStreamlit()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    from frontend.components import platform_widgets
    from frontend.components import sidebar
    from frontend.utils import api_client
    from frontend.utils import localize
    from frontend.utils import session
    from frontend.utils import ux

    monkeypatch.setattr(platform_widgets, "st", fake_st)
    monkeypatch.setattr(ux, "st", fake_st)
    monkeypatch.setattr(sidebar, "render_sidebar", lambda: None)
    monkeypatch.setattr(session, "init_session", lambda: None)
    monkeypatch.setattr(localize, "inject_localize", lambda: None)

    monkeypatch.setattr(
        api_client,
        "list_features",
        lambda project_id: _ok({"features": [{"name": "登录", "priority": "P0"}]}),
    )
    monkeypatch.setattr(
        api_client,
        "list_testpoints",
        lambda project_id: _ok(
            {
                "testpoints": [
                    {
                        "id": 1,
                        "feature_name": "登录",
                        "category": "边界",
                        "description": "密码长度边界",
                        "expected_result": "提示明确",
                        "test_data": "7/8/20/21",
                        "priority": "P0",
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        api_client,
        "list_testcases",
        lambda project_id: _ok(
            {
                "testcases": [
                    {
                        "id": 1,
                        "case_id": "TC-001",
                        "title": "登录接口成功",
                        "precondition": "",
                        "steps": ["发送请求"],
                        "expected": "返回 200",
                        "priority": "P0",
                        "case_type": "正向",
                        "method": "POST",
                        "url": "/api/login",
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        api_client,
        "get_document",
        lambda project_id: _ok({"doc_type": "接口文档", "testcase_mode": "api"}),
    )
    monkeypatch.setattr(api_client, "generate_testpoints", lambda project_id: _ok({"count": 1}))
    monkeypatch.setattr(api_client, "generate_testcases", lambda project_id, mode: _ok({"review": {}}))
    monkeypatch.setattr(api_client, "add_testpoint", lambda *args, **kwargs: _ok({}))
    monkeypatch.setattr(api_client, "update_testpoint", lambda *args, **kwargs: _ok({}))
    monkeypatch.setattr(api_client, "remove_testpoint", lambda *args, **kwargs: _ok({}))
    monkeypatch.setattr(api_client, "add_testcase", lambda *args, **kwargs: _ok({}))
    monkeypatch.setattr(api_client, "update_testcase", lambda *args, **kwargs: _ok({}))
    monkeypatch.setattr(api_client, "remove_testcase", lambda *args, **kwargs: _ok({}))
    monkeypatch.setattr(api_client, "export_excel", lambda *args, **kwargs: {"filename": "x.xlsx", "file_size": 10, "download_url": "/x"})
    monkeypatch.setattr(api_client, "get_download_url", lambda path: f"http://testserver{path}")

    return fake_st, api_client


def _import_page(project_root: Path, filename: str):
    path = project_root / "frontend" / "pages" / filename
    module_name = f"_smoke_{path.stem}_{id(path)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "filename",
    [
        "03_📋_测试点生成.py",
        "04_📝_测试用例生成.py",
        "05_📥_导出Excel.py",
    ],
)
def test_pages_import_without_backend_or_browser(project_root, fake_frontend_runtime, filename):
    _import_page(project_root, filename)


def test_testcase_page_import_survives_quality_review_failure(
    monkeypatch,
    project_root,
    fake_frontend_runtime,
):
    _fake_st, api_client = fake_frontend_runtime
    monkeypatch.setattr(
        api_client,
        "get_testcase_review",
        lambda project_id: (_ for _ in ()).throw(RuntimeError("review unavailable")),
    )

    _import_page(project_root, "04_📝_测试用例生成.py")


def test_export_page_import_survives_quality_review_failure(
    monkeypatch,
    project_root,
    fake_frontend_runtime,
):
    _fake_st, api_client = fake_frontend_runtime
    monkeypatch.setattr(
        api_client,
        "get_testcase_review",
        lambda project_id: (_ for _ in ()).throw(RuntimeError("review unavailable")),
    )

    _import_page(project_root, "05_📥_导出Excel.py")
