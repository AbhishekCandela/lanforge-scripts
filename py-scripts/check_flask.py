# server_5005.py
import argparse, json, time, csv
from collections import deque
from flask import Flask, request, jsonify

app = Flask(__name__)

# keep the last 200 payloads in memory
RECENT = deque(maxlen=200)

@app.get("/api/health")
def health():
    return jsonify({"ok": True, "ts": time.time(), "count": len(RECENT)}), 200

@app.post("/api/speedtest")
def ingest():
    try:
        payload = request.get_json(force=True) or {}
    except Exception as e:
        return jsonify({"stored": False, "error": f"bad json: {e}"}), 400

    # minimal normalization: strings only, tolerate missing fields
    rec = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ip": str(payload.get("ip") or ""),
        "hostname": str(payload.get("hostname") or ""),
        "serial": str(payload.get("serial") or ""),
        "device_id": str(payload.get("device_id") or ""),
        "download_mbps": str(payload.get("download_mbps") or ""),
        "upload_mbps": str(payload.get("upload_mbps") or ""),
        "idle_ms": str(payload.get("idle_ms") or ""),
        "download_latency_ms": str(payload.get("download_latency_ms") or ""),
        "upload_latency_ms": str(payload.get("upload_latency_ms") or ""),
        "_raw": payload,  # keep original just in case
    }

    RECENT.append(rec)

    # append to newline-delimited JSON log
    with open("ingest_log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # also maintain a simple CSV (created once with header)
    csv_exists = False
    try:
        with open("ingest_log.csv", "r", encoding="utf-8"):
            csv_exists = True
    except FileNotFoundError:
        pass

    with open("ingest_log.csv", "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not csv_exists:
            w.writerow(["ts","ip","hostname","serial","device_id",
                        "download_mbps","upload_mbps","idle_ms",
                        "download_latency_ms","upload_latency_ms"])
        w.writerow([rec["ts"],rec["ip"],rec["hostname"],rec["serial"],rec["device_id"],
                    rec["download_mbps"],rec["upload_mbps"],rec["idle_ms"],
                    rec["download_latency_ms"],rec["upload_latency_ms"]])

    return jsonify({"stored": True, "count": len(RECENT)}), 200

@app.get("/api/last")
def last():
    """Return the most recent record (or {})"""
    return jsonify(RECENT[-1] if RECENT else {}), 200

@app.get("/api/recent")
def recent():
    """Return up to the last N records (default 20)"""
    try:
        n = max(1, min(200, int(request.args.get("n", 20))))
    except Exception:
        n = 20
    return jsonify(list(RECENT)[-n:]), 200

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", default=5005, type=int)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug, use_reloader=False)

if __name__ == "__main__":
    main()
