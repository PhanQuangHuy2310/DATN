"""Make the local Supabase (`supabase start`) an exact copy of the cloud project.

Copies, from the cloud project you have access to:
  * roles of the EAS schemas (attributes, search_path/timeout settings, grants);
  * schemas eas, eas_archive and every mock_* schema: tables, functions,
    triggers, RLS policies, privileges and all rows (audit chain included);
  * every object of the private Storage bucket(s), verified by SHA-256;
  * the project's SQL editor snippets (into supabase/snippets/, git-ignored).

Data never goes through git: each collaborator pulls it with their own access.

Requirements
  * Docker running and `supabase start` done in this repository.
  * Supabase CLI logged in (`supabase login`) with access to the project.
  * The cloud `service_role` key (Dashboard > Project Settings > API Keys >
    Legacy API keys) in the environment variable SUPABASE_CLOUD_SERVICE_KEY.
  * The root .env pointing the three EAS database URLs at the local database;
    their passwords become the passwords of the local login roles.

Usage
  python scripts/supabase_local_sync.py [--project-ref REF] [--skip-storage]

Only the LOCAL database is modified; the cloud is read only. The local app
schemas are dropped and rebuilt inside one transaction, so a failure leaves
them unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
# Inside the database container; owned by postgres, not a shared tmp dir.
SYNC_DIR = "/var/lib/postgresql/eas_sync"
APP_SCHEMAS = ("eas", "eas_archive")
DEFAULT_REF = "emnusiybdkpibtqsplta"


def run(cmd: list[str], **kw) -> str:
    exe = shutil.which(cmd[0]) or cmd[0]  # Windows: resolves supabase.cmd/.exe shims
    result = subprocess.run(
        [exe, *cmd[1:]],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        **kw,
    )
    if result.returncode != 0:
        tail = "\n".join((result.stderr or result.stdout).strip().splitlines()[-5:])
        raise SystemExit(f"Command failed: {' '.join(cmd[:4])} ...\n{tail}")
    return result.stdout


def env_file() -> dict[str, str]:
    values = {}
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"')
    return values


def local_status() -> dict[str, str]:
    out = run(["supabase", "status", "-o", "env"])
    return {
        k: v.strip('"')
        for k, v in (line.split("=", 1) for line in out.splitlines() if "=" in line)
    }


def is_app_schema(name: str) -> bool:
    return name in APP_SCHEMAS or name.startswith("mock_")


# ---------------------------------------------------------------- database
def dump_cloud(ref: str, work: Path) -> None:
    run(["supabase", "link", "--project-ref", ref, "--yes"])
    for args, name in (
        (["--role-only"], "roles.sql"),
        ([], "schema.sql"),
        (["--data-only", "--use-copy"], "data.sql"),
    ):
        print(f"  dumping {name} ...")
        run(["supabase", "db", "dump", "--linked", *args, "-f", str(work / name)])


def build_restore(work: Path, login_passwords: dict[str, str]) -> dict[str, int]:
    roles_sql = (work / "roles.sql").read_text(encoding="utf-8")
    created = re.findall(r'^CREATE ROLE "([^"]+)";', roles_sql, re.MULTILINE)
    statements = ["SET ROLE postgres;  -- the cloud roles were created by postgres"]
    for role in created:
        statements.append(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
            f'THEN CREATE ROLE "{role}"; END IF; END $$;'
        )
    lines = roles_sql.splitlines()
    statements += [line for line in lines if re.match(r'^GRANT "[^"]+" TO ', line)]
    statements.append(
        "RESET ROLE;  -- settings below may touch roles postgres does not manage"
    )
    statements += [
        line for line in lines if re.match(r'^ALTER ROLE "[^"]+" (SET|WITH) ', line)
    ]
    for role, password in login_passwords.items():
        statements.append(
            f"ALTER ROLE \"{role}\" PASSWORD '{password.replace(chr(39), chr(39) * 2)}';"
        )
    schemas = sorted(
        set(
            re.findall(
                r'^CREATE SCHEMA IF NOT EXISTS "([^"]+)"',
                (work / "schema.sql").read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        )
    )
    app = [s for s in schemas if is_app_schema(s)]
    statements.append(
        "DROP SCHEMA IF EXISTS " + ", ".join(f'"{s}"' for s in app) + " CASCADE;"
    )

    # Data of the app schemas only; auth/storage rows belong to the local stack.
    kept, rows, skip, current = [], {}, False, None
    for line in (
        (work / "data.sql").read_text(encoding="utf-8").splitlines(keepends=True)
    ):
        copy = re.match(r'^COPY "([^"]+)"\."([^"]+)"', line)
        if copy and not skip and current is None:
            if not is_app_schema(copy.group(1)):
                skip = True
                continue
            current = f"{copy.group(1)}.{copy.group(2)}"
            rows[current] = 0
        elif skip:
            skip = not line.startswith("\\.")
            continue
        elif current is not None:
            if line.startswith("\\."):
                current = None
            else:
                rows[current] += 1
        setval = re.match(r"^SELECT pg_catalog\.setval\('\"([^\"]+)\"\.", line)
        if setval and not is_app_schema(setval.group(1)):
            continue
        kept.append(line)
    (work / "data_app.sql").write_text("".join(kept), encoding="utf-8")
    (work / "restore.sql").write_text(
        "\\set ON_ERROR_STOP on\n"
        + "\n".join(statements)
        + f"\n\\i {SYNC_DIR}/schema.sql\n\\i {SYNC_DIR}/data_app.sql\n"
        + "SET ROLE eas_migration;\n"
        + "GRANT ALL ON SCHEMA eas_archive TO eas_migration;\n"
        + "GRANT ALL ON ALL TABLES IN SCHEMA eas_archive TO eas_migration;\n"
        + "RESET ROLE;\n",
        encoding="utf-8",
    )
    return rows


def restore_local(db_container: str, work: Path) -> None:
    run(["docker", "exec", db_container, "mkdir", "-p", SYNC_DIR])
    for name in ("schema.sql", "data_app.sql", "restore.sql"):
        run(["docker", "cp", str(work / name), f"{db_container}:{SYNC_DIR}/{name}"])
    run(
        [
            "docker",
            "exec",
            db_container,
            "psql",
            "-U",
            "supabase_admin",
            "-d",
            "postgres",
            "-q",
            "-1",
            "-f",
            f"{SYNC_DIR}/restore.sql",
        ]
    )
    run(["docker", "exec", db_container, "rm", "-rf", SYNC_DIR])


def local_counts(db_container: str, tables: list[str]) -> dict[str, int]:
    sql = " UNION ALL ".join(f"SELECT '{t}', count(*) FROM {t}" for t in tables)
    out = run(
        [
            "docker",
            "exec",
            db_container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "postgres",
            "-At",
            "-F",
            "|",
            "-c",
            sql,
        ]
    )
    return {k: int(v) for k, v in (line.split("|") for line in out.split())}


# ----------------------------------------------------------------- storage
def http(
    base: str,
    key: str,
    path: str,
    data: bytes | None = None,
    method: str | None = None,
    headers=None,
):
    auth = (
        {"apikey": key}
        if key.startswith("sb_")
        else {"apikey": key, "Authorization": f"Bearer {key}"}
    )
    req = urllib.request.Request(
        base + path, data=data, method=method, headers={**auth, **(headers or {})}
    )
    return urllib.request.urlopen(req, timeout=120)


def list_objects(
    base: str, key: str, bucket: str, prefix: str = ""
) -> dict[str, tuple[int | None, str]]:
    found, offset = {}, 0
    while True:
        body = json.dumps({"prefix": prefix, "limit": 1000, "offset": offset}).encode()
        items = json.load(
            http(
                base,
                key,
                f"/storage/v1/object/list/{bucket}",
                body,
                "POST",
                {"Content-Type": "application/json"},
            )
        )
        for item in items:
            if item.get("id") is None:
                found.update(
                    list_objects(base, key, bucket, f"{prefix}{item['name']}/")
                )
            else:
                meta = item.get("metadata") or {}
                found[f"{prefix}{item['name']}"] = (
                    meta.get("size"),
                    meta.get("mimetype") or "application/octet-stream",
                )
        if len(items) < 1000:
            return found
        offset += 1000


def sync_storage(cloud: tuple[str, str], local: tuple[str, str]) -> None:
    buckets = json.load(http(*cloud, "/storage/v1/bucket"))
    local_ids = {b["id"] for b in json.load(http(*local, "/storage/v1/bucket"))}
    for b in buckets:
        spec = {
            k: b.get(k) for k in ("public", "file_size_limit", "allowed_mime_types")
        }
        if b["id"] in local_ids:
            http(
                *local,
                f"/storage/v1/bucket/{b['id']}",
                json.dumps(spec).encode(),
                "PUT",
                {"Content-Type": "application/json"},
            ).read()
        else:
            http(
                *local,
                "/storage/v1/bucket",
                json.dumps({"id": b["id"], "name": b["name"], **spec}).encode(),
                "POST",
                {"Content-Type": "application/json"},
            ).read()
        src, dst = list_objects(*cloud, b["id"]), list_objects(*local, b["id"])
        for name, (size, mime) in sorted(src.items()):
            if dst.get(name, (None,))[0] != size:
                path = f"/storage/v1/object/{b['id']}/{urllib.parse.quote(name)}"
                data = http(*cloud, path).read()
                http(
                    *local,
                    path,
                    data,
                    "POST",
                    {"Content-Type": mime, "x-upsert": "true"},
                ).read()
        extra = sorted(set(dst) - set(src))
        for i in range(0, len(extra), 100):
            http(
                *local,
                f"/storage/v1/object/{b['id']}",
                json.dumps({"prefixes": extra[i : i + 100]}).encode(),
                "DELETE",
                {"Content-Type": "application/json"},
            ).read()
        dst = list_objects(*local, b["id"])
        bad = [
            n
            for n in src
            if n not in dst
            or hashlib.sha256(
                http(
                    *cloud, f"/storage/v1/object/{b['id']}/{urllib.parse.quote(n)}"
                ).read()
            ).digest()
            != hashlib.sha256(
                http(
                    *local, f"/storage/v1/object/{b['id']}/{urllib.parse.quote(n)}"
                ).read()
            ).digest()
        ]
        print(
            f"  bucket {b['id']}: {len(src)} objects, removed {len(extra)} local-only, SHA-256 mismatches {len(bad)}"
        )
        if bad or len(dst) != len(src):
            raise SystemExit(f"Storage copy incomplete for bucket {b['id']}: {bad[:5]}")


def sync_snippets(ref: str) -> None:
    listing = json.loads(
        run(["supabase", "snippets", "list", "--project-ref", ref, "-o", "json"])
    )
    folder = ROOT / "supabase" / "snippets"
    folder.mkdir(exist_ok=True)
    for snippet in listing.get("data", []):
        detail = json.loads(
            run(
                [
                    "supabase",
                    "snippets",
                    "download",
                    snippet["id"],
                    "--project-ref",
                    ref,
                ]
            )
        )
        name = re.sub(r'[\\/:*?"<>|]', "-", snippet["name"]).strip() or snippet["id"]
        (folder / f"{name}.sql").write_text(detail["content"]["sql"], encoding="utf-8")
    print(f"  snippets: {len(listing.get('data', []))} saved to supabase/snippets/")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--project-ref", default=DEFAULT_REF)
    parser.add_argument("--skip-storage", action="store_true")
    args = parser.parse_args()

    project_id = tomllib.loads(
        (ROOT / "supabase" / "config.toml").read_text(encoding="utf-8")
    )["project_id"]
    db_container = f"supabase_db_{project_id}"
    status = local_status()
    env = env_file()
    passwords = {}
    for key in (
        "EAS_API_DATABASE_URL",
        "EAS_WORKER_DATABASE_URL",
        "EAS_MOCK_DATABASE_URL",
    ):
        url = urllib.parse.urlsplit(env.get(key, ""))
        if url.hostname not in ("127.0.0.1", "localhost"):
            raise SystemExit(
                f"{key} in .env must point at the local database (127.0.0.1:{url.port or 'port'})."
            )
        passwords[urllib.parse.unquote(url.username)] = urllib.parse.unquote(
            url.password or ""
        )
    cloud_key = os.environ.get("SUPABASE_CLOUD_SERVICE_KEY", "")
    if not args.skip_storage and not cloud_key:
        raise SystemExit(
            "Set SUPABASE_CLOUD_SERVICE_KEY to the cloud service_role key (or pass --skip-storage)."
        )

    with tempfile.TemporaryDirectory(prefix="eas_sync_") as tmp:
        work = Path(tmp)
        print("1/4 Dumping the cloud database (read only) ...")
        dump_cloud(args.project_ref, work)
        expected = build_restore(work, passwords)
        print(
            f"2/4 Rebuilding local schemas ({len(expected)} tables, {sum(expected.values())} rows) ..."
        )
        restore_local(db_container, work)
        got = local_counts(db_container, list(expected))
        missing = {
            t: (expected[t], got.get(t)) for t in expected if got.get(t) != expected[t]
        }
        if missing:
            raise SystemExit(f"Row counts differ after restore: {missing}")
        print(
            f"  verified: every table has exactly the cloud row count ({sum(got.values())} rows)"
        )
    if not args.skip_storage:
        print("3/4 Copying Storage objects ...")
        sync_storage(
            (f"https://{args.project_ref}.supabase.co", cloud_key),
            (status["API_URL"], status.get("SECRET_KEY") or status["SERVICE_ROLE_KEY"]),
        )
    print("4/4 Downloading SQL editor snippets ...")
    sync_snippets(args.project_ref)
    subprocess.run(
        ["docker", "exec", "eas-redis-1", "redis-cli", "FLUSHDB"],
        capture_output=True,
        check=False,
    )  # drop app caches if running
    print("Done: the local Supabase now mirrors the cloud project.")


if __name__ == "__main__":
    main()
