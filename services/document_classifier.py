"""
文档类型识别
============
根据文档内容判断更适合生成接口测试用例还是功能测试用例。
"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DocumentTypeResult:
    """文档类型识别结果。"""
    doc_type: str
    mode: str
    confidence: float
    reasons: list[str]


STRONG_API_PATTERNS = [
    (r"\b(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+/(?:[\w\-{}:.]+/?)+", 5, "包含 HTTP 方法和接口路径"),
    (r"\b(openapi|swagger)\b", 5, "包含 OpenAPI/Swagger"),
    (r"\b(path|url)\s*:[\s*`]*\/(?:[\w\-{}:.]+/?)+", 4, "包含 PATH/URL 接口路径"),
    (r"\btype\s*:[\s*`]*(get|post|put|delete|patch|head|options)\b", 4, "包含 Type 请求方法"),
    (r"(请求地址|接口地址|请求方式|请求方法|请求参数|响应参数|返回参数|响应示例|返回示例)", 4, "包含接口文档字段"),
    (r"(request-header|request-example|response-example|body-parameters|query-parameters|path-parameters|response-fields)", 4, "包含接口文档字段"),
]

WEAK_API_PATTERNS = [
    (r"\b(GET|POST|PUT|DELETE|PATCH)\b", 1, "包含 HTTP 方法"),
    (r"https?://[^\s)]+", 1, "包含 URL"),
    (r"(header|headers|body|payload|response|request|status\s*code)", 1, "包含请求/响应结构"),
    (r"\b(application/json|content-type|authorization|token)\b", 1, "包含接口头或认证信息"),
    (r'"\w+"\s*:\s*("[^"]*"|\d+|true|false|null|\{|\[)', 1, "包含 JSON 字段"),
]

REQUIREMENT_PATTERNS = [
    (r"(需求|功能|业务规则|用户可以|用户应|系统应|页面|按钮|流程|场景)", 3, "包含需求/业务描述"),
    (r"(前置条件|操作步骤|预期结果|验收标准|角色|权限)", 2, "包含功能验收字段"),
    (r"(用例标题|测试步骤|测试数据|模块/项目|用例编号)", 2, "包含功能用例字段"),
]


def classify_document(text: str) -> DocumentTypeResult:
    """识别文档类型。

    Args:
        text: 文档纯文本内容

    Returns:
        DocumentTypeResult，mode 为 api 或 functional。
    """
    sample = (text or "")[:20000]
    lower_sample = sample.lower()
    api_score = 0
    strong_api_score = 0
    req_score = 0
    reasons: list[str] = []

    for pattern, weight, reason in STRONG_API_PATTERNS:
        if re.search(pattern, lower_sample, re.IGNORECASE):
            api_score += weight
            strong_api_score += weight
            reasons.append(reason)

    for pattern, weight, reason in WEAK_API_PATTERNS:
        if re.search(pattern, lower_sample, re.IGNORECASE):
            api_score += weight
            reasons.append(reason)

    for pattern, weight, reason in REQUIREMENT_PATTERNS:
        if re.search(pattern, sample, re.IGNORECASE):
            req_score += weight
            reasons.append(reason)

    if strong_api_score >= 8 or (strong_api_score >= 4 and api_score >= max(5, req_score + 2)):
        confidence = min(0.95, 0.55 + (api_score - req_score) * 0.08)
        return DocumentTypeResult(
            doc_type="接口文档",
            mode="api",
            confidence=round(confidence, 2),
            reasons=reasons[:4] or ["检测到接口结构"],
        )

    confidence = min(0.9, 0.55 + max(req_score - api_score, 1) * 0.06)
    return DocumentTypeResult(
        doc_type="需求文档",
        mode="functional",
        confidence=round(confidence, 2),
        reasons=reasons[:4] or ["未检测到明显接口结构，按需求文档处理"],
    )
