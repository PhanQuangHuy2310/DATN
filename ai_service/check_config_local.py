"""Validate AI settings before uvicorn creates a noisy child-process traceback."""
from __future__ import annotations


def field_errors(exc: BaseException) -> list[str]:
    """Only expose field/type; never print values from private .env files."""
    entries = getattr(exc, "errors", lambda: [])()
    if not entries:
        return [type(exc).__name__]
    return [f"{'.'.join(map(str, item.get('loc', ['unknown'])))} ({item.get('type', 'invalid')})"
            for item in entries]


def main() -> int:
    try:
        from config import get_settings
        get_settings()
    except Exception as exc:
        print("AI configuration invalid. Check ai_service/.env and root .env:")
        for field in field_errors(exc):
            print(f"  - {field}")
        print("For bool/int fields, place comments on a separate line (not after the value).")
        return 1
    print("AI configuration OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
