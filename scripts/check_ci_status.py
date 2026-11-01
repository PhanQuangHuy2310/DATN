import json
import sys
import urllib.request

commit = sys.argv[1] if len(sys.argv) > 1 else "HEAD"

if commit == "HEAD":
    import subprocess

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()

url = f"https://api.github.com/repos/PhanQuangHuy2310/DATN/commits/{commit}/check-runs"
req = urllib.request.Request(url, headers={"User-Agent": "EAS-CI-Checker"})

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        count = data.get("total_count", 0)
        print(f"Commit: {commit[:7]} | Total check runs: {count}")
        all_success = True
        for cr in data.get("check_runs", []):
            name = cr.get("name")
            status = cr.get("status")
            conclusion = cr.get("conclusion")
            html_url = cr.get("html_url")
            print(f"\n- {name}: status={status}, conclusion={conclusion}")
            print(f"  URL: {html_url}")
            output = cr.get("output") or {}
            title = output.get("title")
            summary = output.get("summary")
            text = output.get("text")
            if title:
                print(f"  Title: {title}")
            if summary:
                print(f"  Summary: {summary[:500]}")
            if text:
                print(f"  Text: {text[:1000]}")
            if status != "completed" or conclusion != "success":
                all_success = False
        print(f"\nALL_SUCCESS={all_success}")
        sys.exit(0 if all_success and count > 0 else 1)
except Exception as e:  # noqa: BLE001
    print(f"API Error: {e}")
    sys.exit(2)
