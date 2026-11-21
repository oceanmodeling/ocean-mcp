"""Minimum great-circle distance from NDBC stations to Ian's best track, 27 Sep 00Z - 30 Sep 00Z 2022.

Track: archived nhc_get_best_track response (Ian package, call 1), linear in
time in lat/lon degrees, sampled every 5 min. Haversine, R = 6371.0088 km.
"""
import json, math, sys
from datetime import datetime, timedelta, timezone

R = 6371.0088
def hav(a, b, c, d):
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

def track(path):
    s = json.load(open(path))
    bt = json.loads(s["calls"][0]["result"]["content"][0]["text"])
    pts = []
    for p in bt["track_points"]:
        t = datetime.strptime(p["datetime"], "%Y%m%d %H%M UTC").replace(tzinfo=timezone.utc)
        pts.append((t, p["lat"], p["lon"]))
    return pts

def sample(pts, t0, t1, step=timedelta(minutes=5)):
    out, t = [], t0
    while t <= t1:
        for (ta, la, lo), (tb, lb, lob) in zip(pts, pts[1:]):
            if ta <= t <= tb:
                f = (t - ta) / (tb - ta) if tb > ta else 0.0
                out.append((t, la + f * (lb - la), lo + f * (lob - lo)))
                break
        t += step
    return out

if __name__ == "__main__":
    pts = track(sys.argv[1])
    t0 = datetime(2022, 9, 27, tzinfo=timezone.utc); t1 = datetime(2022, 9, 30, tzinfo=timezone.utc)
    samp = sample(pts, t0, t1)
    stations = {}
    for f in sys.argv[2:]:
        fc = json.loads(json.load(open(f))["result"]["content"][0]["text"])
        for ft in fc["features"]:
            p = ft["properties"]; lon, lat = ft["geometry"]["coordinates"]
            stations[p["id"]] = (p["name"], p["type"], p["has_met"], lat, lon)
    rows = []
    for sid, (name, typ, met, lat, lon) in stations.items():
        dmin, tmin = min((hav(la, lo, lat, lon), t) for t, la, lo in samp)
        rows.append((dmin, sid, name, typ, met, lat, lon, tmin))
    rows.sort()
    print(f"stations returned: {len(stations)}; within 300 km: {sum(r[0] <= 300 for r in rows)}")
    out = []
    for r in rows:
        if r[0] <= 300:
            out.append({"id": r[1], "name": r[2], "type": r[3], "has_met": r[4], "lat": r[5], "lon": r[6],
                        "min_dist_km": round(r[0], 1), "closest_time": r[7].strftime("%Y-%m-%d %H:%M")})
            print(f"{r[1]:7s} {r[0]:6.1f} km {r[7]:%d %H:%M} {str(r[3]):14s} met={r[4]!s:5s} {r[2]}")
    json.dump(out, open("probes/candidates_300km.json", "w"), indent=1)
