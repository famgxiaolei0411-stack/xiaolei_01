"""
AI Test Copilot — Prompt 模板库
================================
所有 AI Prompt 模板集中管理，与业务代码解耦。
非技术人员可以在此调整 prompt 而无需修改业务代码。
"""

from .feature_extraction import FEATURE_EXTRACTION_SYSTEM, FEATURE_EXTRACTION_USER
from .testpoint_generation import TESTPOINT_GENERATION_SYSTEM, TESTPOINT_GENERATION_USER
from .testcase_generation import TESTCASE_GENERATION_SYSTEM, TESTCASE_GENERATION_USER

__all__ = [
    "FEATURE_EXTRACTION_SYSTEM",
    "FEATURE_EXTRACTION_USER",
    "TESTPOINT_GENERATION_SYSTEM",
    "TESTPOINT_GENERATION_USER",
    "TESTCASE_GENERATION_SYSTEM",
    "TESTCASE_GENERATION_USER",
]
