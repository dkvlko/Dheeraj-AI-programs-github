#!/bin/bash

while true; do
  echo "Starting FFmpeg at $(date)"

  ffmpeg -f x11grab -video_size 1366x768 -i :0.0 \
  -vf "scale=800:450,format=gray" -r 8 \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -fflags nobuffer -flags low_delay \
  -b:v 200k -maxrate 200k -bufsize 200k \
  -pix_fmt yuv420p -g 16 \
  -f mpegts tcp://0.0.0.0:8080?listen

  echo "FFmpeg stopped. Restarting in 2 seconds..."
  sleep 2
done
