#!/usr/bin/env bash
#
systemd-inhibit --why="Moodle Exam in progress" --who="Admin" --mode=block sleep 3h

