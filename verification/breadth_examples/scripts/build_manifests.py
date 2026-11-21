"""Write archive/MANIFEST.sha256 and results/SHA256SUMS (standard library only).

archive/MANIFEST.sha256: every file under archive/ except the manifest itself.
results/SHA256SUMS: every file under results/ (except SHA256SUMS) and figures/.
Paths are relative to the package folder, sorted; format as `sha256sum -c`.

    python3 -I scripts/build_manifests.py
"""

from __future__ import annotations

import hashlib
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]


def listing(folders: list[str], exclude: set[str]) -> str:
    """'<sha256>  <relative path>' lines for every file in the folders."""
    lines = []
    for folder in folders:
        for p in sorted((PACKAGE / folder).rglob("*")):
            rel = p.relative_to(PACKAGE).as_posix()
            if p.is_file() and rel not in exclude:
                lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {rel}")
    return "\n".join(sorted(lines, key=lambda s: s.split("  ", 1)[1])) + "\n"


def main() -> None:
    a = listing(["archive"], {"archive/MANIFEST.sha256"})
    (PACKAGE / "archive" / "MANIFEST.sha256").write_text(a)
    r = listing(["results", "figures"], {"results/SHA256SUMS"})
    (PACKAGE / "results" / "SHA256SUMS").write_text(r)
    print(f"archive: {a.count(chr(10))} files; outputs: {r.count(chr(10))} files")


if __name__ == "__main__":
    main()
