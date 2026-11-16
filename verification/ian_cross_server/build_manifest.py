"""Write manifest.json: versions and SHA-256 checksums for the WP2 archive. Standard library only.

    python3 build_manifest.py

Run after run_workflow.py, analyze.py and record_references.py. Rerun it after
any intentional change to an archived file; replay_offline.py checks every
checksum listed under ``files``.
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent  # the package sits in verification/

DATA_FILES = [
    "session_record.json",
    "results.json",
    "geometry_table.md",
    "env_provenance.json",
    "references.json",
    "tool_schemas.json",
    "wp0_manifest_snapshot.json",
]
SCRIPTS = [
    "make_env.py",
    "inspect_tools.py",
    "run_workflow.py",
    "analyze.py",
    "record_references.py",
    "build_manifest.py",
    "replay_offline.py",
]
WP0_MANIFEST = "verification_release_readiness/manifest.json"


def sha256(path: Path) -> str:
    """SHA-256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    """Output of a read-only git command in this checkout."""
    return subprocess.run(
        ["git", "-C", str(HERE), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> None:
    """Collect versions and checksums into manifest.json."""
    record = json.loads((HERE / "session_record.json").read_text())
    results = json.loads((HERE / "results.json").read_text())
    prov = json.loads((HERE / "env_provenance.json").read_text())
    refs = json.loads((HERE / "references.json").read_text())
    wp0 = json.loads((HERE / "wp0_manifest_snapshot.json").read_text())
    schemas = json.loads((HERE / "tool_schemas.json").read_text())

    wp0_pkgs = {p["name"]: p for p in wp0["packages"]}
    wp0_check = {}
    for name, w in prov["wheels"].items():
        p = wp0_pkgs[name]
        wp0_check[name] = {
            "wp0_version": p["version_installed"],
            "wp2_version": w["version"],
            "wp0_wheel_sha256": p["install_source"]["files_sha256"][
                w["wheel_filename"]
            ],
            "wp2_wheel_sha256": w["downloaded_sha256"],
            "wp0_tool_names": p["tool_names"],
            "same_version_and_wheel": p["version_installed"] == w["version"]
            and p["install_source"]["files_sha256"][w["wheel_filename"]]
            == w["downloaded_sha256"],
            "same_tool_names": sorted(p["tool_names"])
            == sorted(
                t["name"]
                for t in next(s for s in record["servers"] if s["name"] == name)[
                    "tools_list"
                ]
            ),
        }

    wp0_src = REPO.parent.parent.parent / WP0_MANIFEST  # main checkout, untracked
    manifest = {
        "manifest_for": "WP2 scripted two-server MCP workflow, Hurricane Ian (2022)",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "created_by": "build_manifest.py",
        "git": {
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "head_at_manifest_time": git("rev-parse", "HEAD"),
            "base_ref": "origin/main (local remote-tracking ref, not fetched)",
            "base_commit": git("rev-parse", "origin/main"),
        },
        "builder": {"python": sys.version.split()[0], "platform": platform.platform()},
        "packages": {
            name: {
                "version": w["version"],
                "wheel_url": w["wheel_url"],
                "wheel_sha256": w["downloaded_sha256"],
                "pypi_sha256": w["pypi_sha256"],
                "installed_source_identical_to_repo": prov["installed_source_vs_repo"][
                    name
                ]["identical"],
                "repo_commit_compared": prov["installed_source_vs_repo"][name][
                    "repo_commit"
                ],
            }
            for name, w in prov["wheels"].items()
        },
        "mcp_sdk_version": record["client"]["mcp_sdk_version"],
        "server_info_reported": {
            s["name"]: s["initialize_result"]["serverInfo"] for s in record["servers"]
        },
        "client_python": record["client"]["python_version"],
        "env_python": prov["python_actual"],
        "uv": prov["uv_version"],
        "environment_freeze": prov["freeze"],
        "session": {
            "started_at": record["session_started_at"],
            "finished_at": record["session_finished_at"],
            "server_processes": record["server_processes_before_first_call"],
            "tool_listing_matches_inspect_tools": all(
                schemas[s["name"]]["tools"] == s["tools_list"]
                for s in record["servers"]
            ),
        },
        "calls": [
            {
                k: c[k]
                for k in (
                    "seq",
                    "server",
                    "tool",
                    "started_at",
                    "text_sha256",
                    "result_sha256",
                )
            }
            for c in record["calls"]
        ],
        "saved_examples_compared": results["input_verification"][
            "comparison_with_saved"
        ]["files"],
        "references": {
            key: {
                k: v[k]
                for k in ("url", "retrieved_at_http_date", "last_modified", "sha256")
            }
            for key, v in refs.items()
            if isinstance(v, dict)
        },
        "wp0_manifest": {
            "path_in_main_checkout": WP0_MANIFEST,
            "tracked_in_git": False,
            "snapshot": "wp0_manifest_snapshot.json",
            "snapshot_sha256": sha256(HERE / "wp0_manifest_snapshot.json"),
            "original_sha256_now": sha256(wp0_src) if wp0_src.exists() else None,
            "generated_at_utc": wp0["generated_at_utc"],
            "agreement_with_wp2_environment": wp0_check,
        },
        "files": {name: sha256(HERE / name) for name in DATA_FILES + SCRIPTS},
    }
    (HERE / "manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n"
    )
    print(
        f"wrote manifest.json: {len(manifest['files'])} files, {len(manifest['calls'])} calls"
    )
    for name, c in wp0_check.items():
        print(
            f"{name}: WP0 agreement version+wheel={c['same_version_and_wheel']} tools={c['same_tool_names']}"
        )


if __name__ == "__main__":
    main()
