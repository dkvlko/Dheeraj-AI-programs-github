#!/bin/bash

echo "SANDAS startup environment:"
echo "  DISPLAY=$DISPLAY"
echo "  XAUTHORITY=$XAUTHORITY"
echo "  XDG_SESSION_TYPE=$XDG_SESSION_TYPE"

exec /home/dkvlko/python314_projects/venv_3.14/bin/python \
    /home/dkvlko/Dheeraj-AI-programs-github/liv_code/SandasUrineServer/run_server.py
