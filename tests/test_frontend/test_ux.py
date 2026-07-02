from __future__ import annotations

import httpx

from frontend.utils import ux


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeStreamlit:
    def __init__(self):
        self.errors: list[str] = []
        self.codes: list[str] = []

    def error(self, message: str):
        self.errors.append(message)

    def expander(self, *args, **kwargs):
        return _Context()

    def code(self, message: str):
        self.codes.append(message)


def _http_error(status_code: int, payload: dict | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://testserver/api")
    response = httpx.Response(status_code, json=payload or {}, request=request)
    return httpx.HTTPStatusError("bad response", request=request, response=response)


def test_show_error_uses_http_detail_for_bad_request(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(ux, "st", fake_st)

    ux.show_error("加载数据", _http_error(400, {"detail": "项目数据不完整"}))

    assert fake_st.errors == ["❌ 项目数据不完整"]
    assert fake_st.codes


def test_show_error_hides_server_error_detail(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(ux, "st", fake_st)

    ux.show_error("加载数据", _http_error(500, {"detail": "stack trace"}))

    assert fake_st.errors == ["❌ 后端处理异常，请稍后重试"]


def test_show_error_handles_request_error(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(ux, "st", fake_st)
    request = httpx.Request("GET", "http://testserver/api")

    ux.show_error("测试点生成", httpx.RequestError("connection failed", request=request))

    assert fake_st.errors == ["❌ 无法连接后端服务，请确认 FastAPI 后端已启动"]


def test_show_error_handles_timeout_text(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(ux, "st", fake_st)

    ux.show_error("测试用例生成", Exception("request timed out"))

    assert fake_st.errors == ["❌ 请求超时，请稍后重试或检查网络连接"]


def test_show_error_uses_default_message_without_exception(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(ux, "st", fake_st)

    ux.show_error("Excel导出")

    assert fake_st.errors == ["❌ 导出失败，请确认已生成测试用例"]
    assert fake_st.codes == []
