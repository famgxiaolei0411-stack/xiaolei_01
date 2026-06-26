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


def test_requirement_with_token_and_json_still_functional() -> None:
    text = """
    登录需求
    用户输入账号密码后点击登录按钮。
    页面需要保存 token 到本地缓存，并展示用户昵称。
    示例数据: {"username": "admin", "remember": true}
    验收标准:
    1. 登录成功后进入首页
    2. 密码错误时页面提示错误原因
    """

    result = classify_document(text)

    assert result.doc_type == "需求文档"
    assert result.mode == "functional"


def test_classify_markdown_api_document_with_path_type_fields() -> None:
    text = """
    # 客达天下接口文档
    - 系统基本路径：http://kdtx-test.itheima.net

    ### 生成验证码
    **PATH:** /api/captchaImage
    **Type:** GET
    **Response-example:**
    响应状态码：200
    响应数据：`{ "msg": "操作成功", "img": "...", "code": 200, "uuid": "xxxxxx"}`

    ### 登录
    **URL:** /api/login
    **Type:** POST
    **Request-header:**
    | 参数名称 | 参数值 | 是否必填 |
    | Content-Type | application/json | 是 |
    **Body-parameters:**
    username|string|用户名|True
    **Response-example:**
    `{ "msg": "操作成功", "code": 200, "token": "xxxxxx"}`
    """

    result = classify_document(text)

    assert result.doc_type == "接口文档"
    assert result.mode == "api"
