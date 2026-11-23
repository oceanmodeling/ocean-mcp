"""One ww3-mcp session; ww3_get_buoy_history(station, 2022, 5000, json) for each candidate.

Saves each full CallToolResult gzipped and prints COUNTS ONLY for the window
[2022-09-27 00:00, 2022-09-30 00:00] UTC (both ends included): rows in window,
non-null WVHT, WSPD, PRES; and whether the returned rows reach the window start.
"""
import asyncio, gzip, hashlib, json, sys, tempfile, time
from datetime import datetime, timezone
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

OUT = Path(__file__).resolve().parents[1] / "probes" / "ww3_hist"
W0, W1 = "2022-09-27 00:00", "2022-09-30 00:00"

def counts(text):
    try:
        d = json.loads(text)
    except json.JSONDecodeError:
        return {"status": "text", "message": text[:160]}
    obs = d["observations"]
    ts = [o["timestamp"] for o in obs]
    win = [o for o in obs if W0 <= o["timestamp"] <= W1]
    first = ts[0] if ts else None
    reach = "full" if first and first <= W0 else ("none" if not first or first > W1 else "partial")
    return {"status": "json", "rows_in_file": d["rows_in_file"], "returned": d["returned"],
            "first_returned": first, "window_reach": reach, "rows_in_window": len(win),
            "WVHT": sum(o.get("WVHT") is not None for o in win),
            "WSPD": sum(o.get("WSPD") is not None for o in win),
            "PRES": sum(o.get("PRES") is not None for o in win)}

async def main():
    cands = json.load(open(sys.argv[1]))
    params = StdioServerParameters(command=sys.executable, args=["-m", "ww3_mcp"], cwd=tempfile.mkdtemp())
    res_all = []
    with open(OUT / "server.stderr.log", "w") as err:
        async with stdio_client(params, errlog=err) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                for i, c in enumerate(cands):
                    if i: time.sleep(2.0)
                    args = {"station_id": c["id"], "year": 2022, "max_records": 5000, "response_format": "json"}
                    started = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                    res = await s.call_tool("ww3_get_buoy_history", args)
                    text = res.content[0].text if res.content else ""
                    rec = {"server": "ww3-mcp", "tool": "ww3_get_buoy_history", "arguments": args,
                           "started_at": started, "result": res.model_dump(mode="json")}
                    with gzip.open(OUT / f"{c['id']}.json.gz", "wt") as fh:
                        json.dump(rec, fh)
                    k = counts(text)
                    k.update(id=c["id"], min_dist_km=c["min_dist_km"], type=c["type"], has_met=c["has_met"],
                             isError=res.isError, text_sha256=hashlib.sha256(text.encode()).hexdigest())
                    res_all.append(k)
                    print(json.dumps(k), flush=True)
    json.dump(res_all, open(OUT / "counts.json", "w"), indent=1)

asyncio.run(main())
