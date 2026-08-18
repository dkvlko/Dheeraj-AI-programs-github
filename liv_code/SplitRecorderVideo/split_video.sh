#!/bin/bash

INPUT="2026-08-18_09-40-26.mp4"

ffmpeg -ss 00:00:00 -i "$INPUT" -t 00:40:45 -c copy "part_01.mp4"
ffmpeg -ss 00:40:45 -i "$INPUT" -t 00:39:33 -c copy "part_02.mp4"
ffmpeg -ss 01:20:18 -i "$INPUT" -t 00:41:40 -c copy "part_03.mp4"
ffmpeg -ss 02:01:58 -i "$INPUT" -t 00:40:34 -c copy "part_04.mp4"
ffmpeg -ss 02:42:32 -i "$INPUT" -t 00:38:58 -c copy "part_05.mp4"
ffmpeg -ss 03:21:30 -i "$INPUT" -t 00:43:10 -c copy "part_06.mp4"
ffmpeg -ss 04:04:40 -i "$INPUT" -t 00:52:20 -c copy "part_07.mp4"
