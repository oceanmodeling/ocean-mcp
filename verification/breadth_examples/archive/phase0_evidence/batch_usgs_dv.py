"""One usgs-mcp session: usgs_get_daily_values for main-stem gauges, 2022-09-27..29.
Prints COUNTS ONLY (values != -999999 and not null), qualifier codes, distance to landfall."""
import asyncio, gzip, json, math, re, sys, tempfile, time
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

P = Path(__file__).resolve().parents[1] / "probes"
OUT = P / "usgs_dv"
LANDFALL = (26.7, -82.2)  # NHC TCR, Cayo Costa, 19:05 UTC 28 Sep 2022
MAIN = re.compile(r"^(PEACE RIVER|PEACE RV|MYAKKA RIVER|CALOOSAHATCHEE)")

def hav(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin((p2-p1)/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(math.radians(d-b)/2)**2
    return 2*6371.0088*math.asin(math.sqrt(h))

def count(text):
    try:
        d = json.loads(text)
    except json.JSONDecodeError:
        return {"status": "text", "message": text[:150]}
    out = []
    for ts in d.get("value", {}).get("timeSeries", []):
        nodata = ts.get("variable", {}).get("noDataValue")
        for vs in ts.get("values", []):
            vals = vs.get("value", [])
            ok = [v for v in vals if v.get("value") not in (None, "") and float(v["value"]) != -999999 and (nodata is None or float(v["value"]) != nodata)]
            quals = sorted({q for v in vals for q in v.get("qualifiers", [])})
            out.append({"series": ts.get("name"), "n_values": len(vals), "n_valid": len(ok),
                        "dates": [v["dateTime"][:10] for v in vals], "qualifiers": quals})
    return {"status": "json", "series": out}

async def main():
    sites = {}
    for pc in ("00060", "00065"):
        for s in json.loads(json.load(open(P / f"usgs_find_sites_{pc}.json"))["result"]["content"][0]["text"]):
            if MAIN.match(s["station_nm"].upper()):
                e = sites.setdefault(s["site_no"], {"name": s["station_nm"], "lat": float(s["dec_lat_va"]), "lon": float(s["dec_long_va"]), "pcs": []})
                e["pcs"].append(pc)
    params = StdioServerParameters(command=sys.executable, args=["-m", "usgs_mcp"], cwd=tempfile.mkdtemp())
    rows = []
    with open(OUT / "server.stderr.log", "w") as err:
        async with stdio_client(params, errlog=err) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                first = True
                for site, e in sorted(sites.items(), key=lambda kv: hav(*LANDFALL, kv[1]["lat"], kv[1]["lon"])):
                    for pc in e["pcs"]:
                        if not first: time.sleep(2.0)
                        first = False
                        args = {"site_number": site, "start_date": "2022-09-27", "end_date": "2022-09-29", "parameter_code": pc, "response_format": "json"}
                        res = await s.call_tool("usgs_get_daily_values", args)
                        text = res.content[0].text if res.content else ""
                        with gzip.open(OUT / f"{site}_{pc}.json.gz", "wt") as fh:
                            json.dump({"tool": "usgs_get_daily_values", "arguments": args, "result": res.model_dump(mode="json")}, fh)
                        k = count(text)
                        k.update(site=site, pc=pc, name=e["name"], dist_landfall_km=round(hav(*LANDFALL, e["lat"], e["lon"]), 1), isError=res.isError)
                        rows.append(k)
                        if k["status"] == "json":
                            ser = "; ".join(f"n={x['n_values']} valid={x['n_valid']} q={x['qualifiers']} {x['dates'][0] if x['dates'] else ''}..{x['dates'][-1] if x['dates'] else ''}" for x in k["series"]) or "no series"
                        else:
                            ser = "TEXT: " + k["message"]
                        print(f"{site} {pc} {k['dist_landfall_km']:6.1f} km {e['name'][:48]:48s} {ser}", flush=True)
    json.dump(rows, open(OUT / "counts.json", "w"), indent=1)

asyncio.run(main())
