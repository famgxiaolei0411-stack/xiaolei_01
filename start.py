"""Cross-platform launcher for AI Test Copilot."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
REQUIREMENTS = ROOT / "requirements.txt"
RUNTIME_DIRS = ("uploads", "outputs", "generated_tests")
DEFAULT_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"


def main() -> int:
    parser = argparse.ArgumentParser(description="Start AI Test Copilot.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically.")
    parser.add_argument("--no-install", action="store_true", help="Skip dependency installation.")
    parser.add_argument("--host", default=os.getenv("BACKEND_HOST", "127.0.0.1"))
    parser.add_argument("--backend-port", type=int, default=int(os.getenv("BACKEND_PORT", "8000")))
    parser.add_argument("--frontend-port", type=int, default=int(os.getenv("STREAMLIT_PORT", "8501")))
    args = parser.parse_args()

    os.chdir(ROOT)
    ensure_project_layout()
    ensure_env_file()

    python = Path(sys.executable) if in_virtualenv() else venv_python()
    if not in_virtualenv():
        ensure_venv()
        python = venv_python()

    if not args.no_install:
        install_dependencies(python)

    connect_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host

    if port_in_use(connect_host, args.backend_port):
        print(f"[ERROR] Backend port {args.backend_port} is already in use.")
        return 1
    if port_in_use(connect_host, args.frontend_port):
        print(f"[ERROR] Frontend port {args.frontend_port} is already in use.")
        return 1

    backend_url = f"http://{connect_host}:{args.backend_port}"
    frontend_url = f"http://localhost:{args.frontend_port}"
    env = os.environ.copy()
    env["BACKEND_HOST"] = args.host
    env["BACKEND_PORT"] = str(args.backend_port)
    env["BACKEND_URL"] = backend_url
    env["STREAMLIT_PORT"] = str(args.frontend_port)

    print("[START] Backend:", backend_url)
    backend = subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "backend.main:app",
            "--host",
            args.host,
            "--port",
            str(args.backend_port),
        ],
        cwd=ROOT,
        env=env,
    )

    try:
        wait_for_port(connect_host, args.backend_port, timeout=30)
        print("[START] Frontend:", frontend_url)
        frontend = subprocess.Popen(
            [
                str(python),
                "-m",
                "streamlit",
                "run",
                "frontend/app.py",
                "--server.address",
                args.host,
                "--server.port",
                str(args.frontend_port),
            ],
            cwd=ROOT,
            env=env,
        )
        wait_for_port(connect_host, args.frontend_port, timeout=45)
        if not args.no_browser:
            webbrowser.open(frontend_url)
        print("[READY] AI Test Copilot is running.")
        print("[OPEN]", frontend_url)
        print("[DOCS]", f"{backend_url}/docs")
        print("Press Ctrl+C to stop.")
        while True:
            if backend.poll() is not None:
                return backend.returncode or 1
            if frontend.poll() is not None:
                return frontend.returncode or 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down...")
        return 0
    finally:
        terminate_process(backend)
        if "frontend" in locals():
            terminate_process(frontend)


def ensure_project_layout() -> None:
    if not REQUIREMENTS.exists():
        raise SystemExit("requirements.txt not found. Please run start.py from the project root.")
    for dirname in RUNTIME_DIRS:
        (ROOT / dirname).mkdir(parents=True, exist_ok=True)


def ensure_env_file() -> None:
    if ENV_FILE.exists():
        return
    if not ENV_EXAMPLE.exists():
        raise SystemExit(".env.example not found.")
    shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
    print("[INIT] Created .env from .env.example. Add your API key before generation.")


def in_virtualenv() -> bool:
    return sys.prefix != sys.base_prefix


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_venv() -> None:
    python = venv_python()
    if python.exists():
        return
    print("[INIT] Creating .venv ...")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=ROOT)


def install_dependencies(python: Path) -> None:
    mirror = os.getenv("PIP_MIRROR", DEFAULT_MIRROR)
    timeout = os.getenv("PIP_TIMEOUT", "60")
    retries = os.getenv("PIP_RETRIES", "5")
    print("[INIT] Installing dependencies. This may take a few minutes ...")
    pip_base = [str(python), "-m", "pip"]
    subprocess.check_call(
        pip_base + ["install", "--upgrade", "pip", "setuptools", "wheel", "-i", mirror, "--timeout", timeout, "--retries", retries],
        cwd=ROOT,
    )
    try:
        subprocess.check_call(
            pip_base + ["install", "-r", str(REQUIREMENTS), "-i", mirror, "--timeout", timeout, "--retries", retries],
            cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        print("[WARN] Mirror install failed. Retrying with default PyPI ...")
        subprocess.check_call(
            pip_base + ["install", "-r", str(REQUIREMENTS), "--timeout", timeout, "--retries", retries],
            cwd=ROOT,
        )


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


def wait_for_port(host: str, port: int, *, timeout: int) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_in_use(host, port):
            return
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {host}:{port}")


def terminate_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
