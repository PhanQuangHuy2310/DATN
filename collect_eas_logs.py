"""EAS Log and Diagnostic Collector.

Collects snapshots of local services, configuration, and diagnostics,
or watches live process logs (backend, frontend, ai, worker) with automated
secret redaction.

Usage:
    collect_logs.cmd
    collect_logs.cmd --include-sql
    collect_logs.cmd --watch backend
    collect_logs.cmd --watch frontend
    collect_logs.cmd --watch ai
    collect_logs.cmd --watch worker --allow-worker-write
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    with suppress(Exception):
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent
LOGS_DIR = ROOT_DIR / "logs"

# Regular expressions for redaction
REDACTION_PATTERNS = [
    (
        re.compile(
            r"(password|pwd|secret|key|token|auth)=([^\s&;'\"]+)", re.IGNORECASE
        ),
        r"\1=***REDACTED***",
    ),
    (
        re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
        r"\1***REDACTED_TOKEN***",
    ),
    (
        re.compile(r"postgres(?:ql)?://([^:]+):([^@]+)@", re.IGNORECASE),
        "postgres" + "ql://\\1:***@",
    ),
    (re.compile(r"sbp_[a-zA-Z0-9]{20,}", re.IGNORECASE), r"sbp_***REDACTED***"),
    (
        re.compile(
            r"eyJ[a-zA-Z0-9\-_]{20,}\.[a-zA-Z0-9\-_]{20,}\.[a-zA-Z0-9\-_]{20,}",
            re.IGNORECASE,
        ),
        r"***REDACTED_JWT***",
    ),
]


def redact(text: str) -> str:
    """Mask known sensitive patterns from log text."""
    result = text
    for pattern, repl in REDACTION_PATTERNS:
        result = pattern.sub(repl, result)
    return result


def find_python() -> str:
    """Find appropriate python interpreter (.venv or current sys.executable)."""
    venv_py = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    if venv_py.is_file():
        return str(venv_py)
    return sys.executable or "python"


def collect_snapshot(include_sql: bool = False) -> int:
    """Collect system snapshot and write to logs/eas_snapshot_YYYYMMDD_HHMMSS.log."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    timestamp = now_utc.strftime("%Y%m%d_%H%M%S")
    snapshot_path = LOGS_DIR / f"eas_snapshot_{timestamp}.log"

    py_exe = find_python()
    output_lines: list[str] = [
        f"=== EAS SNAPSHOT LOG [{now_utc.isoformat()}] ===",
        f"Directory: {ROOT_DIR}",
        f"Python: {py_exe}",
        "",
    ]

    print("[-] Đang thu thập trạng thái hệ thống...")

    # 1. Run check_eas_connections_local.py
    checker_script = ROOT_DIR / "check_eas_connections_local.py"
    if checker_script.is_file():
        try:
            res = subprocess.run(
                [py_exe, str(checker_script)],
                cwd=str(ROOT_DIR),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
                check=False,
            )
            output_lines.append("=== CHECK EAS CONNECTIONS OUTPUT ===")
            output_lines.append(redact(res.stdout or ""))
            if res.stderr:
                output_lines.append("--- STDERR ---")
                output_lines.append(redact(res.stderr))
        except (OSError, subprocess.SubprocessError) as exc:
            output_lines.append(
                f"[ERROR running check_eas_connections_local.py]: {exc}"
            )

    # 2. Run SQL diagnostics if requested
    if include_sql:
        print("[-] Đang thực thi chẩn đoán SQL READ ONLY...")
        diag_script = ROOT_DIR / "diagnose_eas_500.py"
        if diag_script.is_file():
            try:
                res = subprocess.run(
                    [py_exe, str(diag_script)],
                    cwd=str(ROOT_DIR),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                    check=False,
                )
                output_lines.append("\n=== SQL DIAGNOSTICS OUTPUT (READ ONLY) ===")
                output_lines.append(redact(res.stdout or ""))
                if res.stderr:
                    output_lines.append("--- STDERR ---")
                    output_lines.append(redact(res.stderr))
            except (OSError, subprocess.SubprocessError) as exc:
                output_lines.append(f"[ERROR running diagnose_eas_500.py]: {exc}")
        else:
            output_lines.append("\n[WARN] Không tìm thấy file diagnose_eas_500.py")

    final_content = "\n".join(output_lines)
    snapshot_path.write_text(final_content, encoding="utf-8")

    print(f"\n[OK] Đã lưu snapshot vào: {snapshot_path}")
    print(final_content)
    return 0


def watch_service(service: str, allow_worker_write: bool = False) -> int:
    """Launch service and tee stdout/stderr to console and log file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)
    timestamp = now_utc.strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"{service}_{timestamp}.log"

    py_exe = find_python()

    if service == "worker":
        if not allow_worker_write:
            print("[CẢNH BÁO] Worker có thể GHI vào DB nếu có công việc đang chờ.")
            print("Để khởi động Worker, vui lòng chạy kèm cờ --allow-worker-write:")
            print("    collect_logs.cmd --watch worker --allow-worker-write")
            return 1
        cmd = [py_exe, str(ROOT_DIR / "run_worker_local.py")]
        cwd = ROOT_DIR

    elif service == "backend":
        start_cmd = ROOT_DIR / "start_backend_local.cmd"
        if start_cmd.is_file():
            cmd = ["cmd.exe", "/c", str(start_cmd)]
        else:
            cmd = [py_exe, str(ROOT_DIR / "connect_database.py"), "--runserver"]
        cwd = ROOT_DIR

    elif service == "frontend":
        web_client_dir = ROOT_DIR / "web_client"
        cmd = ["cmd.exe", "/c", "npm run dev"]
        cwd = web_client_dir

    elif service == "ai":
        start_ai_cmd = ROOT_DIR / "start_ai_local.cmd"
        if start_ai_cmd.is_file():
            cmd = ["cmd.exe", "/c", str(start_ai_cmd)]
        else:
            cmd = [
                py_exe,
                "-m",
                "uvicorn",
                "ai_service.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8001",
            ]
        cwd = ROOT_DIR
    else:
        print(f"[ERROR] Service không hợp lệ: {service}")
        return 1

    print(f"[*] Đang khởi động service [{service}]...")
    print(f"[*] Log sẽ được ghi tại: {log_path}")
    print("[*] Nhấn Ctrl+C để dừng tiến trình.\n")

    with log_path.open("a", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        try:
            if proc.stdout:
                for line in iter(proc.stdout.readline, ""):
                    clean_line = redact(line)
                    sys.stdout.write(clean_line)
                    sys.stdout.flush()
                    log_file.write(clean_line)
                    log_file.flush()
            proc.wait()
            return proc.returncode
        except KeyboardInterrupt:
            print(f"\n[*] Đang dừng {service}...")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            print("[*] Tiến trình đã dừng.")
            return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="EAS Log and Diagnostics Collector")
    parser.add_argument(
        "--include-sql",
        action="store_true",
        help="Chạy chẩn đoán SQL READ ONLY (EAS-002, EAS-003)",
    )
    parser.add_argument(
        "--watch",
        choices=["backend", "frontend", "ai", "worker"],
        help="Khởi động và theo dõi stdout/stderr của một service",
    )
    parser.add_argument(
        "--allow-worker-write",
        action="store_true",
        help="Cho phép worker khởi động và ghi vào cơ sở dữ liệu",
    )

    args = parser.parse_args()

    if args.watch:
        return watch_service(args.watch, allow_worker_write=args.allow_worker_write)
    return collect_snapshot(include_sql=args.include_sql)


if __name__ == "__main__":
    sys.exit(main())
