#!/bin/bash
#Works better without loop

while true; do
  echo "Starting FFmpeg at $(date)"


ffmpeg -framerate 15 -f x11grab -video_size 1366x768 -i :1.0 \
-f pulse -i default \
-vf "scale=800:450,format=yuv420p" \
-c:v h264_nvenc -preset p3 -tune ll -profile:v baseline -level 3.0 \
-rc cbr -b:v 500k -maxrate 500k -bufsize 500k \
-g 30 -c:a aac -b:a 96k -ac 2 -ar 44100 \
-f mpegts "udp://192.168.29.202:8080?pkt_size=1316"

  echo "FFmpeg stopped. Restarting in 2 seconds..."
  sleep 2
done
