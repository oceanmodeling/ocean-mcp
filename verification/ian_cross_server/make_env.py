"""Create a fresh environment holding the released PyPI wheels of nhc-mcp and coops-mcp.

    python3 make_env.py <env-dir> [--python 3.13.12] [--out env_provenance.json]

Steps, all recorded in the provenance file:

1. Ask the PyPI JSON API for the wheel URL and SHA-256 of each pinned release.
2. Download each wheel into its own new directory and check its SHA-256
   against the digest PyPI publishes. Stop on any mismatch.
3. Create a new virtual environment with ``uv venv`` and install the two
   wheels with ``uv pip install --no-cache`` (dependencies resolved from PyPI).
4. Record ``uv pip freeze`` and compare the installed package source with the
   server source in this repository checkout (file-by-file SHA-256).

Needs only the standard library and ``uv`` on PATH.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PACKAGES = {"nhc-mcp": "0.1.1", "coops-mcp": "0.1.1"}
MODULES = {"nhc-mcp": "nhc_mcp", "coops-mcp": "coops_mcp"}
USER_AGENT = "ocean-mcp-wp2-verification"
REPO_ROOT = Path(__file__).resolve().parents[2]  # the package sits in verification/


def now() -> str:
    """Current UTC time, ISO 8601 with seconds."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    """SHA-256 of a file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_digest(root: Path) -> dict:
    """Per-file SHA-256 of a source tree (``__pycache__`` excluded) and one digest over it."""
    files = {
        str(p.relative_to(root)): sha256_file(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }
    combined = hashlib.sha256(
        "".join(f"{k}\0{v}\n" for k, v in files.items()).encode()
    ).hexdigest()
    return {"files": files, "tree_sha256": combined}


def get_json(url: str) -> dict:
    """GET a JSON document."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def download(url: str, dest: Path) -> None:
    """GET a file to ``dest``."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
        fh.write(resp.read())


def run(cmd: list[str]) -> str:
    """Run a command, fail loudly, return stdout."""
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def main() -> None:
    """Build the environment and write the provenance file."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("env_dir")
    ap.add_argument("--python", default="3.13.12")
    ap.add_argument(
        "--out", default=str(Path(__file__).with_name("env_provenance.json"))
    )
    args = ap.parse_args()

    env_dir = Path(args.env_dir).resolve()
    if env_dir.exists():
        sys.exit(f"{env_dir} exists; choose a new directory for a fresh environment")
    wheel_root = env_dir.with_name(env_dir.name + ".wheels")
    started = now()

    wheels = {}
    for pkg, version in PACKAGES.items():
        meta_url = f"https://pypi.org/pypi/{pkg}/{version}/json"
        meta = get_json(meta_url)
        (whl,) = [u for u in meta["urls"] if u["packagetype"] == "bdist_wheel"]
        pkg_dir = wheel_root / pkg
        pkg_dir.mkdir(parents=True)
        dest = pkg_dir / whl["filename"]
        download(whl["url"], dest)
        local = sha256_file(dest)
        if local != whl["digests"]["sha256"]:
            sys.exit(
                f"{pkg}: wheel SHA-256 {local} != PyPI digest {whl['digests']['sha256']}"
            )
        wheels[pkg] = {
            "version": version,
            "pypi_metadata_url": meta_url,
            "wheel_url": whl["url"],
            "wheel_filename": whl["filename"],
            "pypi_upload_time": whl["upload_time_iso_8601"],
            "pypi_sha256": whl["digests"]["sha256"],
            "downloaded_sha256": local,
            "sha256_match": True,
            "requires_dist": meta["info"]["requires_dist"],
            "local_path": str(dest),
        }
        time.sleep(1.0)

    run(["uv", "venv", "--python", args.python, str(env_dir)])
    py = str(env_dir / "bin" / "python")
    run(
        ["uv", "pip", "install", "--python", py, "--no-cache"]
        + [w["local_path"] for w in wheels.values()]
    )
    freeze = run(["uv", "pip", "freeze", "--python", py]).splitlines()
    env_python = run([py, "-c", "import sys; print(sys.version.split()[0])"]).strip()
    site = Path(
        run(
            [py, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"]
        ).strip()
    )

    head = run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"]).strip()
    source_check = {}
    for pkg, module in MODULES.items():
        installed = tree_digest(site / module)
        repo = tree_digest(REPO_ROOT / "servers" / pkg / "src" / module)
        source_check[pkg] = {
            "installed_tree_sha256": installed["tree_sha256"],
            "repo_tree_sha256": repo["tree_sha256"],
            "repo_commit": head,
            "identical": installed["files"] == repo["files"],
            "files_compared": len(installed["files"]),
        }

    provenance = {
        "created_by": "make_env.py",
        "started_at": started,
        "finished_at": now(),
        "env_dir": str(env_dir),
        "python_requested": args.python,
        "python_actual": env_python,
        "uv_version": run(["uv", "--version"]).strip(),
        "builder_platform": platform.platform(),
        "wheels": wheels,
        "freeze": freeze,
        "installed_source_vs_repo": source_check,
    }
    Path(args.out).write_text(json.dumps(provenance, indent=2) + "\n")
    print(
        json.dumps(
            {k: provenance[k] for k in ("python_actual", "uv_version")}, indent=2
        )
    )
    for pkg, w in wheels.items():
        print(f"{pkg} {w['version']}: sha256 {w['downloaded_sha256']} matches PyPI")
    for pkg, c in source_check.items():
        print(f"{pkg}: installed source identical to repo {head[:7]}: {c['identical']}")


if __name__ == "__main__":
    main()
