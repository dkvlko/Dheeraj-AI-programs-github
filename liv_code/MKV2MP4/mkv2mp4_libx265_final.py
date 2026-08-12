#!/usr/bin/env python3
from pathlib import Path
import subprocess, shutil, time

SOURCE_DIR=Path("/media/Elements/MegaDump")
OUTPUT_DIR=Path("/media/Elements/MegaDump_720p")
CRF="27"; PRESET="medium"; MIN_SAVING=10.0
LOG_FILE=OUTPUT_DIR/"conversion.log"

def log(m):
    t=time.strftime("%Y-%m-%d %H:%M:%S"); s=f"[{t}] {m}"
    print(s); LOG_FILE.parent.mkdir(parents=True,exist_ok=True)
    with LOG_FILE.open("a",encoding="utf-8") as f:f.write(s+"\n")

def human(n):
    n=float(n)
    for u in("B","KB","MB","GB","TB"):
        if n<1024 or u=="TB": return f"{n:.2f} {u}"
        n/=1024

def convert(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    cmd=["ffmpeg","-hide_banner","-y","-i",str(src),"-map","0","-vf","scale=-2:720,format=yuv420p","-c:v","libx265","-preset",PRESET,"-crf",CRF,"-c:a","copy","-sn","-map_metadata","0","-map_chapters","0","-movflags","+faststart",str(dst)]
    return subprocess.run(cmd).returncode==0

def main():
    if shutil.which("ffmpeg") is None: raise SystemExit("ffmpeg not found")
    OUTPUT_DIR.mkdir(parents=True,exist_ok=True)
    files=sorted(SOURCE_DIR.rglob("*.mkv"))
    log(f"Found {len(files)} MKV files")
    conv=skip=rej=0; tb=ta=0; st=time.time()
    for i,src in enumerate(files,1):
        rel=src.relative_to(SOURCE_DIR); dst=(OUTPUT_DIR/rel).with_suffix(".mp4"); tb+=src.stat().st_size
        if dst.exists() and dst.stat().st_size>0:
            skip+=1; ta+=dst.stat().st_size; log(f"[{i}/{len(files)}] SKIP {rel}"); continue
        if dst.exists(): dst.unlink()
        log(f"[{i}/{len(files)}] START {rel}")
        if not convert(src,dst) or not dst.exists():
            if dst.exists(): dst.unlink()
            rej+=1; log(f"FAILED {rel}"); continue
        old,new=src.stat().st_size,dst.stat().st_size
        saving=(old-new)*100/old
        if saving<MIN_SAVING:
            dst.unlink(missing_ok=True); rej+=1; log(f"REJECTED {rel} ({saving:.1f}% saving)"); continue
        src.unlink(); conv+=1; ta+=new
        log(f"ACCEPTED {rel} | {human(old)} -> {human(new)} | Saved {saving:.1f}%")
    log("="*70); log(f"Converted:{conv}"); log(f"Skipped:{skip}"); log(f"Rejected/Failed:{rej}")
    log(f"Original:{human(tb)}"); log(f"Output:{human(ta)}"); log(f"Elapsed:{(time.time()-st)/3600:.2f} h")
if __name__=="__main__": main()
