"""Record checksums and verified quotations for the two documents cited outside MCP.

    python record_references.py --tcr <AL092022_Ian.pdf> --tcr-headers <headers.txt> \
        --coops-help <responseHelp.html> --coops-help-headers <headers.txt>

The files are downloaded beforehand with curl (commands in REPORT.md). This
script hashes them, takes the retrieval time from the HTTP ``Date`` header,
extracts the text (``pypdf`` for the PDF, tag stripping for the HTML) and
writes ``references.json`` only if every quoted passage is found on the
stated page, after whitespace is collapsed. The documents themselves are not
archived (the PDF is 7 MB); their URLs and SHA-256 are.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

TCR_URL = "https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf"
COOPS_HELP_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/responseHelp.html"

TCR_QUOTES = [
    (1, "Lisa Bucci, Laura Alaka, Andrew Hagen, Sandy Delgado, and Jack Beven"),
    (1, "12 March 2026"),
    (1, "Original report dated 2 April 2023."),
    (
        4,
        "made landfall on the barrier island of Cayo Costa, Florida, at 1905 UTC 28 September with an intensity of 130 kt.",
    ),
    (
        4,
        "at 2035 UTC, the center of Ian’s large eye made another landfall near Punta Gorda, Florida",
    ),
    (21, "28 / 1905 26.7 82.2 941 130 Landfall near Cayo Costa, Florida"),
    (9, "The NOS tide gauge near downtown Fort Myers measured 7.26 ft above MHHW"),
]

COOPS_QUOTES = [
    "(I) A flag that when set to 1 indicates that the water level value has been inferred",
    "(F) A flag that when set to 1 indicates that the flat tolerance limit was exceeded",
    "(R) A flag that when set to 1 indicates that the rate of change tolerance limit was exceeded",
    "(T) A flag that when set to 1 indicates that either the maximum or minimum expected water level height limit was exceeded",
    "(O) Count of number of 1 second samples that fall outside a 3-sigma band about the mean",
    "Quality Assurance/Quality Control level -- p = preliminary -- v = verified",
]


def squash(text: str) -> str:
    """Collapse all whitespace, and drop the stray spaces pypdf inserts inside words."""
    return re.sub(r"\s+", "", text)


def headers(path: Path) -> dict:
    """Lower-cased HTTP response headers saved by ``curl -D``."""
    out = {}
    for line in path.read_text().splitlines():
        if ":" in line and not line.startswith("HTTP/"):
            k, v = line.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def sha256(path: Path) -> str:
    """SHA-256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Verify the quotations and write references.json."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tcr", required=True, type=Path)
    ap.add_argument("--tcr-headers", required=True, type=Path)
    ap.add_argument("--coops-help", required=True, type=Path)
    ap.add_argument("--coops-help-headers", required=True, type=Path)
    ap.add_argument("--out", default=str(HERE / "references.json"))
    args = ap.parse_args()

    from pypdf import PdfReader

    pages = [p.extract_text() or "" for p in PdfReader(str(args.tcr)).pages]
    missing = []
    tcr_quotes = []
    for page, quote in TCR_QUOTES:
        found = squash(quote) in squash(pages[page - 1])
        tcr_quotes.append({"page": page, "text": quote, "found": found})
        if not found:
            missing.append(("TCR", page, quote))

    raw = args.coops_help.read_text()
    text = re.sub(r"<script.*?</script>|<style.*?</style>", "", raw, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    help_quotes = []
    for quote in COOPS_QUOTES:
        found = squash(quote) in squash(text)
        help_quotes.append({"text": quote, "found": found})
        if not found:
            missing.append(("CO-OPS help", None, quote))

    if missing:
        sys.exit(f"quotations not found: {missing}")

    th, ch = headers(args.tcr_headers), headers(args.coops_help_headers)
    refs = {
        "created_by": "record_references.py",
        "note": "Cited documents retrieved outside the MCP session. Not archived here; identified by URL and SHA-256.",
        "nhc_tropical_cyclone_report": {
            "citation": (
                "Bucci, L., Alaka, L., Hagen, A., Delgado, S., Beven, J. Tropical Cyclone Report: Hurricane Ian "
                "(AL092022), 23-30 September 2022. National Hurricane Center. Original report dated 2 April 2023; "
                "revised 12 March 2026."
            ),
            "url": TCR_URL,
            "retrieved_at_http_date": th.get("date"),
            "last_modified": th.get("last-modified"),
            "bytes": args.tcr.stat().st_size,
            "sha256": sha256(args.tcr),
            "pages": len(pages),
            "quotations_verified": tcr_quotes,
        },
        "coops_data_api_response_help": {
            "url": COOPS_HELP_URL,
            "retrieved_at_http_date": ch.get("date"),
            "last_modified": ch.get("last-modified"),
            "bytes": args.coops_help.stat().st_size,
            "sha256": sha256(args.coops_help),
            "quotations_verified": help_quotes,
        },
    }
    Path(args.out).write_text(json.dumps(refs, indent=1, ensure_ascii=False) + "\n")
    print(
        f"wrote {args.out}: {len(tcr_quotes)} TCR and {len(help_quotes)} CO-OPS quotations verified"
    )


if __name__ == "__main__":
    main()
