"""vdatum_convert at Fort Myers (CO-OPS 8725520 position from the archived coops_get_station).
    python vdatum_probe.py <label> <seq>   seq: comma list of from>to:online, e.g. mllw>mhhw:0,mllw>navd88:1
Fresh PROJ_USER_WRITABLE_DIRECTORY per run. Saves full results; prints the text."""
import asyncio, json, os, sys, tempfile
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

OUT = Path(__file__).resolve().parents[1] / "probes" / "vdatum"
LAT, LON, Z = "26.647778", "-81.87111", "2.613"

async def main(label, seq):
    projdir = tempfile.mkdtemp(prefix="projcache-")
    env = {k: v for k, v in os.environ.items() if not k.startswith("PROJ")}
    env["PROJ_USER_WRITABLE_DIRECTORY"] = projdir
    params = StdioServerParameters(command=sys.executable, args=["-m", "vdatum_mcp"], cwd=tempfile.mkdtemp(), env=env)
    recs = []
    with open(OUT / f"{label}.stderr.log", "w") as err:
        async with stdio_client(params, errlog=err) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                for item in seq.split(","):
                    pair, on = item.split(":")
                    a, b = pair.split(">")
                    args = {"datum_from": a, "datum_to": b, "lat": LAT, "lon": LON, "z": Z, "online": on == "1"}
                    res = await s.call_tool("vdatum_convert", args)
                    text = res.content[0].text if res.content else ""
                    recs.append({"arguments": args, "result": res.model_dump(mode="json")})
                    print(f"--- {a}->{b} online={on == '1'} isError={res.isError}\n{text}\n")
    json.dump({"label": label, "proj_user_dir": projdir, "proj_dir_after": sorted(os.listdir(projdir)), "calls": recs},
              open(OUT / f"{label}.json", "w"), indent=1)
    print("PROJ user dir after:", sorted(os.listdir(projdir)))

asyncio.run(main(sys.argv[1], sys.argv[2]))
