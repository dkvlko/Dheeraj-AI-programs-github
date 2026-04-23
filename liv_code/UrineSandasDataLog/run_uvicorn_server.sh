#!/usr/bin/env bash
#
source /home/dkvlko/python314_projects/venv_3.14/bin/activate

uvicorn webSocketRTC_HTML:app --host 0.0.0.0 --port 8000 --ssl-keyfile /home/dkvlko/live_code/sslcert/ubuntu_server.key --ssl-certfile /home/dkvlko/live_code/sslcert/ubuntu_server.crt


