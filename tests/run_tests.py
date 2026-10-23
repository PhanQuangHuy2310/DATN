"""
Test Runner for Enterprise Approval System (EAS)

Chạy tất cả test suites trong thư mục tests/:
  python tests/run_tests.py
"""

import os
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def run_all_tests():
    print("=" * 70)
    print("ENTERPRISE APPROVAL SYSTEM (EAS) — TEST SUITE RUNNER")
    print("=" * 70)

    loader = unittest.TestLoader()
    start_dir = os.path.join(REPO_ROOT, "tests")
    suite = loader.discover(start_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print(f"KẾT QUẢ: Ran {result.testsRun} tests.")
    if result.wasSuccessful():
        print("TẤT CẢ CÁC BÀI TEST ĐỀU THÀNH CÔNG (PASS)!")
        return 0
    else:
        print(
            f"THẤT BẠI: {len(result.failures)} lỗi fail, {len(result.errors)} lỗi runtime error."
        )
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
