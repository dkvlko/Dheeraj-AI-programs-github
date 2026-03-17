ffmpeg -f x11grab -video_size 1366x768 -framerate 30 -i :0.0 \
-vaapi_device /dev/dri/renderD128 \
-vf 'format=nv12,hwupload' \
-c:v h264_vaapi \
-b:v 3M -maxrate 3M -bufsize 256k \
-g 30 \
-fflags nobuffer \
-flush_packets 1 \
-f mpegts udp://192.168.29.40:1234?pkt_size=1316