from __future__ import annotations

import pandas as pd

from frontend.components import platform_widgets as widgets


class _Context:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class _Column(_Context):
    def __init__(self, selected: list | None = None):
        self.selected = selected or []

    def multiselect(self, *args, **kwargs):
        return self.selected


class _FakeStreamlit:
    def __init__(self, search: str = "", selected: list | None = None):
        self.search = search
        self.selected = selected or []
        self.messages: list[tuple[str, str]] = []

    def container(self, *args, **kwargs):
        return _Context()

    def columns(self, spec):
        count = spec if isinstance(spec, int) else len(spec)
        return [_Column(self.selected) for _ in range(count)]

    def text_input(self, *args, **kwargs):
        return self.search

    def caption(self, message="", *args, **kwargs):
        self.messages.append(("caption", str(message)))

    def warning(self, message="", *args, **kwargs):
        self.messages.append(("warning", str(message)))

    def info(self, message="", *args, **kwargs):
        self.messages.append(("info", str(message)))

    def success(self, message="", *args, **kwargs):
        self.messages.append(("success", str(message)))

    def markdown(self, message="", *args, **kwargs):
        self.messages.append(("markdown", str(message)))

    def metric(self, label, value, *args, **kwargs):
        self.messages.append(("metric", f"{label}:{value}"))

    def write(self, message="", *args, **kwargs):
        self.messages.append(("write", str(message)))


def test_filter_dataframe_skips_missing_search_and_filter_columns() -> None:
    df = pd.DataFrame(
        [
            {"标题": "登录成功", "优先级": "P0"},
            {"标题": "注册失败", "优先级": "P1"},
        ]
    )

    result = widgets.filter_dataframe(
        df,
        search="登录",
        search_columns=["标题", "不存在字段"],
        filters={"缺失字段": ["x"], "优先级": ["P0"]},
    )

    assert len(result) == 1
    assert result.iloc[0]["标题"] == "登录成功"


def test_filter_dataframe_tolerates_empty_dataframe() -> None:
    df = pd.DataFrame()

    result = widgets.filter_dataframe(
        df,
        search="anything",
        search_columns=["missing"],
        filters={"missing": ["value"]},
    )

    assert result.empty


def test_render_table_filters_tolerates_missing_filter_columns(monkeypatch) -> None:
    fake_st = _FakeStreamlit(search="登录")
    monkeypatch.setattr(widgets, "st", fake_st)
    df = pd.DataFrame(
        [
            {"标题": "登录成功", "优先级": "P0"},
            {"标题": "注册失败", "优先级": "P1"},
        ]
    )

    result = widgets.render_table_filters(
        df,
        key_prefix="unit",
        search_columns=["标题", "不存在字段"],
        filter_columns=["缺失字段"],
    )

    assert len(result) == 1
    assert result.iloc[0]["标题"] == "登录成功"
    assert any("当前显示 1 / 总计 2" in msg for _, msg in fake_st.messages)


def test_render_project_status_card_gracefully_handles_missing_project(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(widgets, "st", fake_st)

    widgets.render_project_status_card(project_id=None)

    assert ("warning", "未选择项目") in fake_st.messages


def test_render_api_contract_metrics_gracefully_handles_missing_data(monkeypatch) -> None:
    fake_st = _FakeStreamlit()
    monkeypatch.setattr(widgets, "st", fake_st)

    widgets.render_api_contract_metrics({})

    assert any("暂无接口契约检查指标" in msg for _, msg in fake_st.messages)


def test_format_file_size() -> None:
    assert widgets.format_file_size(None) == "0 B"
    assert widgets.format_file_size(2048) == "2.0 KB"
