
#!/usr/bin/env python3
"""
Standalone NetSpeed tester using rclone.
Runs one upload/download test and exits.
Intended to be invoked by cron every 2 hours.
"""

from __future__ import annotations
import csv
import os
import subprocess
import time
from pathlib import Path

BASE = Path("/home/dkvlko/Dheeraj-AI-programs-github/liv_code/BLOBS/NetSpeed")
BASE.mkdir(parents=True, exist_ok=True)

REMOTE = "onedrive:NetSpeedTest"   # <-- change
FILE_MB = 10

LOCAL_FILE = BASE / f"upload_test_{FILE_MB}MB.bin"
DOWNLOAD_FILE = BASE / "download_test.bin"
CSV_FILE = BASE / "history.csv"

def ensure_test_file():
    if LOCAL_FILE.exists() and LOCAL_FILE.stat().st_size == FILE_MB*1024*1024:
        return
    print("Creating test file...")
    with open(LOCAL_FILE, "wb") as f:
        remaining = FILE_MB * 1024 * 1024
        chunk = 1024 * 1024
        while remaining:
            n = min(chunk, remaining)
            f.write(os.urandom(n))
            remaining -= n

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)

def mbps(bytes_count, seconds):
    if seconds <= 0:
        return 0.0
    return bytes_count * 8 / seconds / 1_000_000

def upload():
    start = time.perf_counter_ns()
    p = run([
        "rclone","copy",str(LOCAL_FILE),REMOTE,
        "--transfers","1","--checkers","1"
    ])
    elapsed = (time.perf_counter_ns()-start)/1e9
    ok = p.returncode == 0
    return ok, elapsed

def download():
    if DOWNLOAD_FILE.exists():
        DOWNLOAD_FILE.unlink()
    start = time.perf_counter_ns()
    p = run([
        "rclone","copy",
        f"{REMOTE}/{LOCAL_FILE.name}",
        str(BASE),
        "--transfers","1","--checkers","1"
    ])
    elapsed = (time.perf_counter_ns()-start)/1e9
    ok = p.returncode == 0
    return ok, elapsed

def append_csv(row):
    new = not CSV_FILE.exists()
    with open(CSV_FILE,"a",newline="") as f:
        w=csv.writer(f)
        if new:
            w.writerow([
                "timestamp","upload_mbps","download_mbps",
                "upload_seconds","download_seconds","status"
            ])
        w.writerow(row)

def avg_last6():
    if not CSV_FILE.exists():
        return None
    vals=[]
    with open(CSV_FILE,newline="") as f:
        r=csv.DictReader(f)
        for row in r:
            if row["status"]=="SUCCESS":
                vals.append((float(row["upload_mbps"]),float(row["download_mbps"])))
    vals=vals[-6:]
    if not vals:
        return None
    up=sum(x for x,_ in vals)/len(vals)
    down=sum(y for _,y in vals)/len(vals)
    return up,down,len(vals)

def main():
    ensure_test_file()
    size=LOCAL_FILE.stat().st_size

    u_ok,u_sec=upload()
    d_ok,d_sec=(False,0.0)
    if u_ok:
        d_ok,d_sec=download()

    if d_ok and DOWNLOAD_FILE.exists():
        try:
            DOWNLOAD_FILE.unlink()
        except Exception:
            pass

    up=mbps(size,u_sec) if u_ok else 0.0
    down=mbps(size,d_sec) if d_ok else 0.0
    status="SUCCESS" if (u_ok and d_ok) else "FAILED"

    ts=time.strftime("%Y-%m-%d %H:%M:%S")
    append_csv([
        ts,
        f"{up:.2f}",
        f"{down:.2f}",
        f"{u_sec:.3f}",
        f"{d_sec:.3f}",
        status
    ])

    print("="*60)
    print("Timestamp :",ts)
    print("Status    :",status)
    print(f"Upload    : {up:.2f} Mbps ({u_sec:.3f}s)")
    print(f"Download  : {down:.2f} Mbps ({d_sec:.3f}s)")

    avg=avg_last6()
    if avg:
        au,ad,n=avg
        print(f"12-hour average ({n} successful tests)")
        print(f"Upload    : {au:.2f} Mbps")
        print(f"Download  : {ad:.2f} Mbps")
    print("="*60)

if __name__=="__main__":
    main()
