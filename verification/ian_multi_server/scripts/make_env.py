"""WP9 Phase 0: fresh environment from the released PyPI wheels of ten servers.

    python3 make_env.py <env-dir> --repo /mnt/d/ocean-mcp --out provenance.json

For each package: PyPI JSON for the pinned version -> wheel URL and digest;
download into its own new directory; check SHA-256 against PyPI; install all
wheels into one new uv venv; compare the installed module tree, file by file,
with the release tag's source tree (git archive, read-only on the repo).
Standard library and uv only.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import platform
import subprocess
import sys
import tarfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PACKAGES = {
    "nhc-mcp": "0.1.1",
    "coops-mcp": "0.1.1",
    "recon-mcp": "0.1.3",
    "ndbc-mcp": "0.1.2",
    "usgs-mcp": "0.1.2",
    "ww3-mcp": "0.1.3",
    "ofs-mcp": "0.1.3",
    "rtofs-mcp": "0.1.4",
    "goes-mcp": "0.1.3",
    "vdatum-mcp": "0.1.1",
}
UA = "ocean-mcp-verification"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def run(cmd: list[str], **kw) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


def tree_files(root: Path) -> dict:
    return {
        str(p.relative_to(root)): sha256_file(p)
        for p in sorted(root.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }


def tag_files(repo: Path, tag: str, subdir: str) -> dict:
    data = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", tag, subdir],
        check=True,
        capture_output=True,
    ).stdout
    out = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        for m in tf.getmembers():
            if m.isfile():
                rel = m.name[len(subdir) + 1 :]
                out[rel] = sha256_bytes(tf.extractfile(m).read())
    return dict(sorted(out.items()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("env_dir")
    ap.add_argument("--repo", required=True)
    ap.add_argument("--python", default="3.13.12")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    env = Path(a.env_dir).resolve()
    if env.exists():
        sys.exit(f"{env} exists")
    wroot = env.with_name(env.name + ".wheels")
    started = now()
    wheels = {}
    for pkg, ver in PACKAGES.items():
        murl = f"https://pypi.org/pypi/{pkg}/{ver}/json"
        meta = json.loads(get(murl))
        (w,) = [u for u in meta["urls"] if u["packagetype"] == "bdist_wheel"]
        d = wroot / pkg
        d.mkdir(parents=True)
        dest = d / w["filename"]
        dest.write_bytes(get(w["url"]))
        local = sha256_file(dest)
        if local != w["digests"]["sha256"]:
            sys.exit(f"{pkg}: {local} != {w['digests']['sha256']}")
        wheels[pkg] = {
            "version": ver,
            "wheel_filename": w["filename"],
            "wheel_url": w["url"],
            "pypi_upload_time": w["upload_time_iso_8601"],
            "pypi_sha256": w["digests"]["sha256"],
            "downloaded_sha256": local,
            "requires_dist": meta["info"]["requires_dist"],
            "local_path": str(dest),
        }
        time.sleep(0.5)
    run(["uv", "venv", "--python", a.python, str(env)])
    py = str(env / "bin" / "python")
    run(
        ["uv", "pip", "install", "--python", py, "--no-cache"]
        + [w["local_path"] for w in wheels.values()]
        + ["jsonschema"]
    )
    freeze = run(["uv", "pip", "freeze", "--python", py]).splitlines()
    site = Path(
        run(
            [py, "-c", "import sysconfig;print(sysconfig.get_paths()['purelib'])"]
        ).strip()
    )
    repo = Path(a.repo)
    src = {}
    for pkg, w in wheels.items():
        mod = pkg.replace("-", "_")
        tag = f"{pkg}-v{w['version']}"
        inst = tree_files(site / mod)
        tagged = tag_files(repo, tag, f"servers/{pkg}/src/{mod}")
        src[pkg] = {
            "tag": tag,
            "tag_commit": run(["git", "-C", str(repo), "rev-list", "-n1", tag]).strip(),
            "files_installed": len(inst),
            "files_in_tag": len(tagged),
            "identical_to_tag": inst == tagged,
            "differences": sorted(
                k for k in set(inst) | set(tagged) if inst.get(k) != tagged.get(k)
            ),
        }
    prov = {
        "created_by": "make_env.py (WP9 phase 0)",
        "started_at": started,
        "finished_at": now(),
        "env_dir": str(env),
        "python": run([py, "-c", "import sys;print(sys.version.split()[0])"]).strip(),
        "uv": run(["uv", "--version"]).strip(),
        "platform": platform.platform(),
        "wheels": wheels,
        "freeze": freeze,
        "installed_source_vs_tag": src,
    }
    Path(a.out).write_text(json.dumps(prov, indent=2) + "\n")
    for pkg, w in wheels.items():
        s = src[pkg]
        print(
            f"{pkg:11s} {w['version']:6s} {w['downloaded_sha256']} "
            f"tag={s['tag_commit'][:7]} identical={s['identical_to_tag']} {s['differences']}"
        )


if __name__ == "__main__":
    main()
