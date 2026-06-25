"""
文档类型识别测试
================
"""

from services.document_classifier import classify_document


def test_classify_api_document() -> None:
    text = """
    用户登录接口
    POST /api/v1/login
    Content-Type: application/json
    请求参数:
    {"username": "admin", "password": "123456"}
    响应示例:
    {"token": "xxx", "expires_in": 7200}
    """

    result = classify_document(text)

    assert result.doc_type == "接口文档"
    assert result.mode == "api"


def test_classify_requirement_document() -> None:
    text = """
    用户登录需求
    用户可以通过用户名和密码登录系统。
    连续输错 5 次密码后，账号锁定 30 分钟。
    登录成功后跳转到首页，页面右上角显示用户名。
    """

    result = classify_document(text)

    assert result.doc_type == "需求文档"
    assert result.mode == "functional"
