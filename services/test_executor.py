"""
测试执行器 — Pytest 执行 + Allure 报告生成
=============================================
封装 pytest 执行和 Allure 报告生成，实现一键执行+报告。

依赖：
- pytest (含 allure-pytest 插件)
- allure 命令行工具（生成 HTML 报告）

流程:
    测试脚本 → pytest --alluredir=allure-results → allure generate → allure-report
"""

import logging
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from config import (
    ALLURE_RESULTS_DIR,
    ALLURE_REPORT_DIR,
    GENERATED_TESTS_DIR,
    PYTEST_OPTIONS,
    PYTEST_TIMEOUT,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 数据结构
# ══════════════════════════════════════════════════════════

@dataclass
class TestResult:
    """单个测试结果。"""
    name: str
    outcome: str  # passed / failed / skipped / error
    duration: float = 0.0
    message: str = ""


@dataclass
class TestReport:
    """测试执行报告。

    Attributes:
        total: 总用例数
        passed: 通过数
        failed: 失败数
        skipped: 跳过数
        error: 错误数
        duration: 总耗时（秒）
        results: 详细结果列表
        allure_report_path: Allure HTML 报告路径
    """
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    error: int = 0
    duration: float = 0.0
    results: list[TestResult] = field(default_factory=list)
    allure_report_path: str = ""

    @property
    def pass_rate(self) -> float:
        """通过率（0~1）。"""
        return self.passed / self.total if self.total > 0 else 0.0

    @property
    def summary(self) -> str:
        """生成摘要字符串。"""
        return (
            f"总计: {self.total} | 通过: {self.passed} | "
            f"失败: {self.failed} | 跳过: {self.skipped} | "
            f"通过率: {self.pass_rate:.1%} | 耗时: {self.duration:.1f}s"
        )

    def to_dict(self) -> dict[str, Any]:
        """转为字典。"""
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "error": self.error,
            "duration": self.duration,
            "pass_rate": self.pass_rate,
            "allure_report": self.allure_report_path,
        }


# ══════════════════════════════════════════════════════════
# TestExecutor
# ══════════════════════════════════════════════════════════

class TestExecutor:
    """测试执行器。

    负责：
    1. 运行 pytest（集成 allure-pytest）
    2. 解析 pytest 输出
    3. 生成 Allure HTML 报告

    Usage:
        executor = TestExecutor()
        report = executor.run("test_user_login.py")
        print(report.summary)
        # 总计: 8 | 通过: 7 | 失败: 1 | 通过率: 87.5%
    """

    def __init__(
        self,
        test_dir: Path | None = None,
        allure_results: Path | None = None,
        allure_report: Path | None = None,
        pytest_options: str | None = None,
        timeout: int | None = None,
    ) -> None:
        """初始化执行器。

        Args:
            test_dir: 测试脚本目录
            allure_results: Allure 结果目录
            allure_report: Allure 报告目录
            pytest_options: pytest 额外参数
            timeout: 超时秒数
        """
        self._test_dir = test_dir or GENERATED_TESTS_DIR
        self._allure_results = allure_results or ALLURE_RESULTS_DIR
        self._allure_report = allure_report or ALLURE_REPORT_DIR
        self._pytest_options = pytest_options or PYTEST_OPTIONS
        self._timeout = timeout or PYTEST_TIMEOUT

        # 确保目录存在
        self._allure_results.mkdir(parents=True, exist_ok=True)
        self._allure_report.mkdir(parents=True, exist_ok=True)

    def run(self, project_dir: str | Path) -> TestReport:
        """执行测试框架项目并生成 Allure 报告。

        在新的分层框架结构中，pytest 从项目目录内运行：
        cd {project_dir} && pytest

        Args:
            project_dir: 测试框架项目目录路径

        Returns:
            TestReport — 包含执行统计和 Allure 报告路径

        Raises:
            FileNotFoundError: 项目目录不存在
            RuntimeError: pytest 执行失败
        """
        project_path = Path(project_dir).resolve()
        # 路径安全：确保在生成目录内
        if not str(project_path).startswith(str(GENERATED_TESTS_DIR.resolve())):
            raise ValueError(f"无效的测试项目路径: {project_dir}")
        if not project_path.exists():
            raise FileNotFoundError(f"测试项目不存在: {project_path}")

        # 检查新旧两种结构
        if (project_path / "case").exists():
            # 新分层框架：pytest 在项目根目录运行
            test_target = "case/"
            cwd = str(project_path)
        else:
            # 旧单文件模式：直接指定文件
            test_target = str(project_path)
            cwd = str(project_path.parent)

        logger.info("=" * 60)
        logger.info("开始执行测试: %s", project_path.name)
        logger.info("=" * 60)

        # ── Step 1: 执行 pytest ────────────────────
        pytest_output = self._run_pytest(test_target, cwd)
        report = self._parse_pytest_output(pytest_output)

        # ── Step 2: 生成 Allure 报告 ───────────────
        self._generate_allure_report()
        report.allure_report_path = str(self._allure_report / "index.html")

        logger.info("=" * 60)
        logger.info("测试执行完成: %s", report.summary)
        logger.info("Allure 报告: %s", report.allure_report_path)
        logger.info("=" * 60)

        return report

    def _resolve_test_path(self, test_file: str | Path) -> Path:
        """解析测试文件路径。

        Args:
            test_file: 文件名或路径

        Returns:
            绝对路径
        """
        path = Path(test_file)
        if not path.is_absolute():
            path = self._test_dir / path
        return path

    def _run_pytest(self, test_target: str, cwd: str) -> str:
        """执行 pytest 并捕获输出。

        Args:
            test_target: 测试目标（目录或文件路径）
            cwd: pytest 工作目录

        Returns:
            pytest 标准输出
        """
        cmd = [
            sys.executable, "-m", "pytest",
            test_target,
            f"--alluredir={self._allure_results}",
            "--tb=short",
            "-v",
        ]

        # 追加用户自定义选项
        if self._pytest_options:
            extra = self._pytest_options.split()
            cmd.extend(extra)

        logger.info("执行命令: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=cwd,
            )
            # pytest 即使有 failed 用例也返回非零 code，这不算执行失败
            output = result.stdout + "\n" + result.stderr
            return output

        except subprocess.TimeoutExpired as exc:
            logger.error("pytest 执行超时 (%ds)", self._timeout)
            raise RuntimeError(
                f"pytest 执行超时（{self._timeout}s）"
            ) from exc

        except FileNotFoundError as exc:
            raise RuntimeError(
                "pytest 未找到，请确认已安装: pip install pytest allure-pytest"
            ) from exc

    def _parse_pytest_output(self, output: str) -> TestReport:
        """解析 pytest 输出，提取统计信息。

        Args:
            output: pytest 的 stdout + stderr

        Returns:
            TestReport
        """
        report = TestReport()
        import re

        # ── 解析汇总行 ────────────────────────────
        # 示例: "8 passed, 1 failed, 2 skipped in 12.34s"
        summary_pattern = r'(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+skipped.*?in\s+([\d.]+)s'
        match = re.search(summary_pattern, output)
        if match:
            report.passed = int(match.group(1))
            report.failed = int(match.group(2))
            report.skipped = int(match.group(3))
            report.duration = float(match.group(4))

        # ── 简化的汇总行 ──────────────────────────
        if not match:
            # 尝试 "3 passed in 1.23s"
            simple = re.search(r'(\d+)\s+passed\s+in\s+([\d.]+)s', output)
            if simple:
                report.passed = int(simple.group(1))
                report.duration = float(simple.group(2))
            # "no tests ran"
            if 'no tests ran' in output.lower():
                logger.warning("没有测试被执行")

        report.total = report.passed + report.failed + report.skipped + report.error

        # ── 解析 PASSED/FAILED 测试 ───────────────
        for line in output.split("\n"):
            stripped = line.strip()
            if stripped.startswith("PASSED"):
                parts = stripped.split()
                if len(parts) >= 2:
                    report.results.append(TestResult(
                        name=parts[1] if len(parts) > 1 else parts[0],
                        outcome="passed",
                    ))
            elif stripped.startswith("FAILED"):
                parts = stripped.split()
                if len(parts) >= 2:
                    report.results.append(TestResult(
                        name=parts[1] if len(parts) > 1 else parts[0],
                        outcome="failed",
                        message=stripped[len(parts[0]):].strip(),
                    ))

        return report

    def _generate_allure_report(self) -> None:
        """生成 Allure HTML 报告。

        使用 allure 命令行工具:
            allure generate -o <report_dir> <results_dir>

        Raises:
            RuntimeWarning: allure 命令不可用
        """
        cmd = [
            "allure", "generate",
            str(self._allure_results),
            "-o", str(self._allure_report),
            "--clean",
        ]

        try:
            logger.info("生成 Allure 报告: %s", " ".join(cmd))
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                logger.info(
                    "Allure 报告已生成: %s",
                    self._allure_report / "index.html",
                )
            else:
                logger.warning(
                    "Allure 报告生成失败 (code=%d): %s",
                    result.returncode,
                    result.stderr[:200],
                )
        except FileNotFoundError:
            logger.warning(
                "allure 命令行工具未安装，跳过 HTML 报告生成。"
                "安装方法: https://docs.qameta.io/allure/"
            )
        except subprocess.TimeoutExpired:
            logger.warning("Allure 报告生成超时")


# ══════════════════════════════════════════════════════════
# 一键执行流程
# ══════════════════════════════════════════════════════════

def run_test_pipeline(
    testcases: list[dict[str, Any]],
    module_name: str = "通用模块",
    base_url: str = "http://localhost:8000",
) -> TestReport:
    """一键执行完整自动化测试管线。

    生成脚本 → pytest 执行 → Allure 报告

    Args:
        testcases: 测试用例列表
        module_name: 模块名称
        base_url: 被测系统 URL

    Returns:
        TestReport

    Example:
        report = run_test_pipeline(
            testcases=[{"id": "TC-001", "title": "...", "steps": [...], ...}],
            module_name="用户登录",
        )
        print(report.summary)
    """
    from services.test_script_generator import TestFrameworkGenerator, ScriptOptions

    # ── Step 1: 生成框架 ──────────────────────────
    gen = TestFrameworkGenerator()
    options = ScriptOptions(module_name=module_name, base_url=base_url)
    framework_dir = gen.generate(testcases, options)

    # ── Step 2: 执行测试 ──────────────────────────
    executor = TestExecutor()
    report = executor.run(framework_dir)

    return report
