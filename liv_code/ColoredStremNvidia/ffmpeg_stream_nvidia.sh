#!/bin/bash

while true; do
  echo "Starting FFmpeg at $(date)"

ffmpeg -framerate 15 -f x11grab -video_size 1366x768 -i :1.0 \
-vf "scale=800:450" \
-c:v h264_nvenc -preset p3 -tune ll \
-rc cbr -b:v 450k -maxrate 450k -bufsize 450k \
-pix_fmt yuv420p -g 20 \
-fflags nobuffer -flags low_delay \
-f mpegts tcp://0.0.0.0:8080?listen

  echo "FFmpeg stopped. Restarting in 2 seconds..."
  sleep 2
done
