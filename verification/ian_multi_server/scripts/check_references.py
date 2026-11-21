"""Check the HDOB format quotations used in DESIGN.md 7 against the archived NHC page.

The page (archive/references/abouthdobs_2007.shtml) was retrieved with curl on
2026-11-21 17:30:35 GMT from https://www.nhc.noaa.gov/abouthdobs_2007.shtml.
Tags are stripped, entities unescaped and whitespace (including no-break
spaces) collapsed; each quotation must then occur verbatim.

    python3 -I scripts/check_references.py   -> results/references_check.json
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import PACKAGE, dump, sha256_bytes  # noqa: E402

PAGE = PACKAGE / "archive" / "references" / "abouthdobs_2007.shtml"
PAGE_SHA256 = "3ad3a4e221296fb7889c495b962fd6aa1bdfe9ae21f1664bf03ffb4fef337eef"
URL = "https://www.nhc.noaa.gov/abouthdobs_2007.shtml"

QUOTES = {
    "observation_time": "Observation time, in hours, minutes and seconds (UTC). The observation time is the midpoint of the 30-s averaging interval used for the record's meteorological data.",
    "flight_level_wind": "Wind speed, in kt (30-s average). 999 indicates missing value.",
    "sfmr_wind": "Maximum 10-second average surface wind speed occurring within the encoding interval from the Stepped Frequency Microwave Radiometer (SFMR), in kt. 999 indicates missing value.",
    "sfmr_rain": "SFMR-derived rain rate, in mm hr-1, evaluated over the 10-s interval chosen for KKK . 999 indicates missing value.",
    "ff": "Quality control flags.",
    "first_column": "First column indicates status of positional variables as follows:",
    "pos_0": "0 All parameters of nominal accuracy",
    "pos_1": "1 Lat/lon questionable",
    "pos_2": "2 Geopotential altitude or static pressure questionable",
    "pos_3": "3 Both lat/lon and GA/PS questionable",
    "second_column": "Second column indicates status of meteorological variables as follows:",
    "met_1": "1 T or TD questionable",
    "met_2": "2 Flight-level winds questionable",
    "met_3": "3 SFMR parameter(s) questionable",
    "met_4": "4 T/TD and FL winds questionable",
    "met_5": "5 T/TD and SFMR questionable",
    "met_6": "6 FL winds and SFMR questionable",
    "met_9": "9 T/TD, FL winds, and SFMR questionable",
}


def page_text(raw: bytes) -> str:
    """Visible text of the page, whitespace collapsed."""
    t = raw.decode("utf-8", errors="replace")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", t)


def main() -> None:
    raw = PAGE.read_bytes()
    sha = sha256_bytes(raw)
    if sha != PAGE_SHA256:
        raise SystemExit(f"{PAGE}: SHA-256 {sha} != {PAGE_SHA256}")
    text = page_text(raw)
    found = {k: q in text for k, q in QUOTES.items()}
    dump(
        PACKAGE / "results" / "references_check.json",
        {
            "url": URL,
            "retrieved": "2026-11-21 17:30:35 GMT (curl; HTTP date header)",
            "sha256": sha,
            "quotations": {k: {"text": QUOTES[k], "found": found[k]} for k in QUOTES},
            "all_found": all(found.values()),
        },
    )
    missing = [k for k, v in found.items() if not v]
    if missing:
        raise SystemExit(f"quotations not found: {missing}")
    print(f"{len(QUOTES)} quotations found in the archived NHC HDOB page")


if __name__ == "__main__":
    main()
