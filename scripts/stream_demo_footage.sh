#!/usr/bin/env bash
# scripts/stream_demo_footage.sh
# ──────────────────────────────
# Loop a local MP4/video file to RTSP URLs via ffmpeg for the live demo.
#
# PREREQUISITES:
# 1. Install ffmpeg:
#    - Windows (winget): winget install Gyan.FFmpeg
#    - Linux (Ubuntu/Debian): sudo apt update && sudo apt install -y ffmpeg
#    - macOS (Homebrew): brew install ffmpeg
#
# 2. Run an RTSP server locally:
#    We recommend MediaMTX (formerly rtsp-simple-server) - zero config, standalone binary:
#    Download: https://github.com/bluenviron/mediamtx/releases
#    - Windows: download mediamtx_v*_windows_amd64.zip, extract and run mediamtx.exe
#    - Linux: download mediamtx_v*_linux_amd64.tar.gz, tar -xvf ..., ./mediamtx
#    - macOS: brew install mediamtx && mediamtx
#
# USAGE:
#   bash scripts/stream_demo_footage.sh path/to/flood_clip.mp4 [demo_cam_1]
#
# Default RTSP URL: rtsp://localhost:8554/demo_cam_1

INPUT_VIDEO="${1:-}"
STREAM_NAME="${2:-demo_cam_1}"
RTSP_URL="rtsp://localhost:8554/${STREAM_NAME}"

if [ -z "$INPUT_VIDEO" ]; then
    echo "Usage: $0 <path_to_video.mp4> [stream_name]"
    echo "Example: $0 demo_clip.mp4 demo_cam_1"
    exit 1
fi

if [ ! -f "$INPUT_VIDEO" ]; then
    echo "Error: Video file '$INPUT_VIDEO' not found."
    exit 1
fi

echo "=================================================="
echo "Streaming $INPUT_VIDEO to $RTSP_URL"
echo "Press Ctrl+C to stop streaming"
echo "=================================================="

ffmpeg -re -stream_loop -1 -i "$INPUT_VIDEO" -c copy -f rtsp "$RTSP_URL"
