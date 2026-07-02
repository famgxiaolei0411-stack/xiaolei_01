"""Environment diagnostics for AI Test Copilot."""

from __future__ import annotations

import importlib.util
import os
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REQUIRED_FILES = [
    "requirements.txt",
    ".env.example",
    "frontend/app.py",
    "backend/main.py",
    "start.py",
]
RUNTIME_DIRS = ["uploads", "outputs", "generated_tests"]
PACKAGES = ["fastapi", "uvicorn", "streamlit", "sqlalchemy", "openai", "pydantic"]


def main() -> int:
    print("AI Test Copilot Doctor")
    print("=" * 28)
    failures = 0
    failures += check_python()
    failures += check_files()
    failures += check_env()
    failures += check_dirs()
    failures += check_packages()
    failures += check_ports()
    print("=" * 28)
    if failures:
        print(f"Doctor found {failures} issue(s).")
        return 1
    print("Doctor passed. You can run start.py or start.bat.")
    return 0


def ok(message: str) -> int:
    print("[OK]", message)
    return 0


def warn(message: str) -> int:
    print("[WARN]", message)
    return 0


def fail(message: str) -> int:
    print("[FAIL]", message)
    return 1


def check_python() -> int:
    version = sys.version_info
    if version >= (3, 11):
        return ok(f"Python {version.major}.{version.minor}.{version.micro}")
    return fail("Python 3.11+ is required.")


def check_files() -> int:
    failures = 0
    for relpath in REQUIRED_FILES:
        if (ROOT / relpath).exists():
            ok(f"Found {relpath}")
        else:
            failures += fail(f"Missing {relpath}")
    return failures


def check_env() -> int:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return warn(".env not found. start.py will create it from .env.example.")
    text = env_file.read_text(encoding="utf-8", errors="ignore")
    if "sk-your-api-key-here" in text and "sk-your-openai-key-here" in text:
        return warn(".env exists but API keys still look like placeholders.")
    return ok(".env found")


def check_dirs() -> int:
    for dirname in RUNTIME_DIRS:
        path = ROOT / dirname
        path.mkdir(parents=True, exist_ok=True)
        ok(f"Runtime directory ready: {dirname}/")
    return 0


def check_packages() -> int:
    missing = []
    for package in PACKAGES:
        if importlib.util.find_spec(package) is None:
            missing.append(package)
    if missing:
        return warn("Missing packages in current Python: " + ", ".join(missing))
    return ok("Runtime packages importable")


def check_ports() -> int:
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    backend_port = int(os.getenv("BACKEND_PORT", "8000"))
    frontend_port = int(os.getenv("STREAMLIT_PORT", "8501"))
    for port in (backend_port, frontend_port):
        if port_in_use(host, port):
            warn(f"Port {port} is already in use.")
        else:
            ok(f"Port {port} is free.")
    return 0


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


if __name__ == "__main__":
    raise SystemExit(main())
