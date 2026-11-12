#!/usr/bin/env python3
"""Live validation of replay rules 3, 4a, 4b (and 5 if a session used it) (DESIGN.md 5.2).

For each rule: one request with exactly the parameters stofs-mcp sends (application=stofs_mcp),
fetched live through phase0/noaa_fetch.py, compared byte for byte with what the WP5 launcher's
engine serves from the archive for the same URL. Writes run_log/rule_validation.json.
Usage: python -I validate_rules.py LABEL=URL [LABEL=URL ...]   (results are appended)
"""
import hashlib, json, sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PKG / "phase0"))
sys.path.insert(0, str(PKG / "replay"))
import noaa_fetch as nf  # noqa: E402
import wp5_launcher  # noqa: E402,F401  (patches the engine)
import ocean_replay_launcher as L  # noqa: E402

ARCH = [PKG / "data/archive" / a for a in ("models", "coops", "meta", "templates")]


def main() -> int:
    eng = L.Engine("replay", [L.Archive(p) for p in ARCH], None)
    rp = PKG / "run_log/rule_validation.json"
    out = json.loads(rp.read_text()) if rp.exists() else []
    for arg in sys.argv[1:]:
        rule, url = arg.split("=", 1)
        status, _, body, info = eng.replay("GET", url)
        r = nf.fetch(url, PKG / "data/raw/validation", phase="phase2", tag=f"validate_rule_{rule}")
        live = (PKG / r["path"]).read_bytes() if r.get("path") else b""
        out.append({"rule": rule, "url": url, "replay_rule": info.get("wp5_rule") or info.get("rule"),
                    "replay_status": status, "live_status": r["status"],
                    "replay_sha256": hashlib.sha256(body).hexdigest(), "live_sha256": r["sha256"],
                    "bytes": [len(body), len(live)], "identical": body == live and status == r["status"]})
        print(json.dumps(out[-1]))
    rp.write_text(json.dumps(out, indent=1) + "\n")
    return 0 if all(o["identical"] for o in out) else 1


if __name__ == "__main__":
    sys.exit(main())
