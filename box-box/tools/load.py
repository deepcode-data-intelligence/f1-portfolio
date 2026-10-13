"""Synthetic load generator for box-box (standard library only).

Usage: python3 load.py http://127.0.0.1:8081 <seconds_of_frames> <cars> <session> [frames_per_request]

Simulates <cars> x 10 tags at 60 Hz with smooth sine-based signals and prints throughput and
request latency as JSON. The signal is smoother than real telemetry; see docs/evidence.
"""
import json, math, sys, time, urllib.request

base = sys.argv[1]; seconds = float(sys.argv[2]); cars = int(sys.argv[3]); session = sys.argv[4]
frames_per_batch = int(sys.argv[5]) if len(sys.argv) > 5 else 6  # 6 frames = 100 ms per request
TAGS = ["SPEED", "THROTTLE", "BRAKE", "STEER", "GEAR", "RPM", "LAP_DISTANCE", "TYRE.FL.TEMP", "TYRE.FR.TEMP", "DRS"]
def value(tag, car, t):
    phase = car * 0.37
    if tag == "SPEED": return 200 + 100 * math.sin(t / 9 + phase)
    if tag == "THROTTLE": return max(0.0, math.sin(t / 9 + phase))
    if tag == "BRAKE": return max(0.0, -math.sin(t / 9 + phase))
    if tag == "STEER": return 0.3 * math.sin(t / 3 + phase)
    if tag == "GEAR": return float(int(4 + 4 * max(0, math.sin(t / 9 + phase))))
    if tag == "RPM": return 9000 + 3000 * math.sin(t / 9 + phase)
    if tag == "LAP_DISTANCE": return (t * 60.0) % 5300
    if tag.startswith("TYRE"): return 90 + 10 * math.sin(t / 30 + phase)
    return float(int(t) % 20 < 5)
t0 = time.time_ns(); frames = int(seconds * 60); offered = 0; accepted = 0; archived = 0; reqs = 0; lat = []
start = time.time()
for f0 in range(0, frames, frames_per_batch):
    samples = []
    for f in range(f0, min(frames, f0 + frames_per_batch)):
        t = f / 60.0; ts = t0 + int(t * 1e9)
        for car in range(cars):
            for tag in TAGS:
                samples.append({"session": session, "tag": f"SIM.CAR{car}.{tag}", "ts": ts, "value": value(tag, car, t),
                                "seq": f, "recv_ts": time.time_ns()})
    body = json.dumps({"samples": samples}).encode()
    req = urllib.request.Request(base + "/ingest", data=body, headers={"content-type": "application/json"})
    a = time.perf_counter()
    with urllib.request.urlopen(req) as r: rep = json.load(r)
    lat.append(time.perf_counter() - a)
    offered += rep["offered"]; accepted += rep["accepted"]; archived += rep["archived"]; reqs += 1
elapsed = time.time() - start
lat.sort()
print(json.dumps({"requests": reqs, "offered": offered, "accepted": accepted, "archived": archived,
                  "elapsed_s": round(elapsed, 2), "samples_per_s": int(offered / elapsed),
                  "req_ms_p50": round(lat[len(lat)//2]*1000, 1), "req_ms_p95": round(lat[int(len(lat)*0.95)]*1000, 1),
                  "req_ms_max": round(lat[-1]*1000, 1)}))
