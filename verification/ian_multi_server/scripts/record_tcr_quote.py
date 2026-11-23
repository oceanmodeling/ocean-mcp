"""Verify the NHC Tropical Cyclone Report quotations on the peak flight-level and SFMR winds (AMENDMENTS.md A10, A12).

    python record_tcr_quote.py --tcr <AL092022_Ian.pdf> [--tcr-headers <curl -D headers>]

Method as verification/ian_cross_server/record_references.py:
- text extraction with pypdf, page by page;
- every whitespace character removed from both the page text and the quotation, which also
  drops the stray spaces pypdf inserts inside words;
- additionally, curly apostrophes and quotation marks are read as straight ones;
- each passage must be found on its stated page.

The PDF is not archived (about 7 MB), only its URL, size and SHA-256. The record is written
to archive/references/tcr_quote_check.json only if every passage is found; otherwise the
script prints the page text around the closest match and stops.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
TCR_URL = "https://www.nhc.noaa.gov/data/tcr/AL092022_Ian.pdf"
# SHA-256 of the PDF verified by verification/ian_cross_server (retrieved 2026-11-06)
IAN_PACKAGE_TCR_SHA256 = (
    "804d2a867917d4ab157e5b2b1e444d21d306379a08d07ffd7059d157a4b15fce"
)
QUOTES = [
    (
        5,
        "the maximum 10-second averaged flight-level winds reported in the hurricane's core were 160 kt from a NOAA aircraft at 750 mb",
    ),
    (5, "1013 UTC 28 September"),
    (
        5,
        "During the missions, the maximum 10-second averaged flight-level winds reported in the hurricane's core were 160 kt from a NOAA aircraft at 750 mb (an altitude of about 6800 ft) at 1013 UTC 28 September.",
    ),
    # SFMR comparison (AMENDMENTS.md A12)
    (
        5,
        "There were also multiple peak SFMR surface wind estimates from both Air Force and NOAA aircraft of 137-138 kt at 1030 UTC and 1013 UTC, respectively.",
    ),
    (
        5,
        "The SFMR data from the Air Force instrument was flagged as unreliable in the real-time products, but reprocessing in the post-storm analysis using an updated algorithm no longer flagged the peak values.",
    ),
]
STRAIGHT = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def squash(text: str) -> str:
    """Remove all whitespace and read curly quotation marks as straight ones."""
    return re.sub(r"\s+", "", text.translate(STRAIGHT))


def headers(path: Path | None) -> dict:
    """Lower-cased HTTP response headers saved by ``curl -D`` (empty if not given)."""
    if path is None:
        return {}
    out = {}
    for line in path.read_text().splitlines():
        if ":" in line and not line.startswith("HTTP/"):
            k, v = line.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tcr", required=True, type=Path)
    ap.add_argument("--tcr-headers", type=Path)
    ap.add_argument(
        "--out",
        default=str(PACKAGE / "archive" / "references" / "tcr_quote_check.json"),
    )
    args = ap.parse_args()
    from pypdf import PdfReader
    import pypdf

    raw = args.tcr.read_bytes()
    pages = [p.extract_text() or "" for p in PdfReader(str(args.tcr)).pages]
    results, missing = [], []
    for page, quote in QUOTES:
        found = squash(quote) in squash(pages[page - 1])
        on_pages = [i + 1 for i, t in enumerate(pages) if squash(quote) in squash(t)]
        results.append(
            {
                "page": page,
                "text": quote,
                "found_on_stated_page": found,
                "found_on_pages": on_pages,
            }
        )
        if not found:
            missing.append((page, quote, on_pages))
    if missing:
        for page, quote, on_pages in missing:
            key = squash(quote)[:25]
            t = squash(pages[page - 1])
            i = t.find(key[:12])
            print(f"NOT FOUND on p. {page}: {quote!r}; found on pages {on_pages}")
            print(
                f"  p. {page} around '{key[:12]}': {t[max(0, i - 80) : i + 260] if i >= 0 else '(fragment absent)'}"
            )
        sys.exit(1)
    sha = hashlib.sha256(raw).hexdigest()
    h = headers(args.tcr_headers)
    rec = {
        "created_by": "scripts/record_tcr_quote.py",
        "method": "pypdf text per page; all whitespace removed from page and quotation; curly quotation marks read as straight; passage must be on the stated page (as verification/ian_cross_server/record_references.py, plus the quotation-mark rule)",
        "pypdf_version": pypdf.__version__,
        "document": {
            "citation": "Bucci, L., Alaka, L., Hagen, A., Delgado, S., Beven, J. Tropical Cyclone Report: Hurricane Ian (AL092022), 23-30 September 2022. National Hurricane Center.",
            "url": TCR_URL,
            "local_file_name": args.tcr.name,
            "retrieved_at_http_date": h.get("date"),
            "last_modified": h.get("last-modified"),
            "bytes": len(raw),
            "sha256": sha,
            "pages": len(pages),
            "same_file_as_ian_cross_server_2026_11_06": sha == IAN_PACKAGE_TCR_SHA256,
            "archived": False,
        },
        "quotations_verified": results,
    }
    Path(args.out).write_text(
        json.dumps(rec, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.out}: {len(results)} passages verified; PDF sha256 {sha}")


if __name__ == "__main__":
    main()
