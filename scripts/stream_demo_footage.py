#!/usr/bin/env python3
"""
scripts/stream_demo_footage.py
──────────────────────────────
Loop a local MP4/video file to one or more RTSP URLs via ffmpeg.
Use this for the live demo so you never depend on real cameras or venue wifi.

PREREQUISITES
─────────────
1. Install ffmpeg (https://ffmpeg.org/download.html).
   On Windows (winget):   winget install Gyan.FFmpeg
   On Ubuntu/Debian:      sudo apt install ffmpeg
   On macOS (Homebrew):   brew install ffmpeg

2. Install mediamtx (the RTSP server). It is a single binary, no install needed.
   Download: https://github.com/bluenviron/mediamtx/releases  (formerly rtsp-simple-server)
   On Windows: download mediamtx_v*.zip, extract mediamtx.exe, run it.

   Default mediamtx config accepts streams at rtsp://localhost:8554/<any-path>.

USAGE
─────
# Terminal 1 – start the RTSP server
mediamtx          # (or mediamtx.exe on Windows)

# Terminal 2 – loop your flood footage
python scripts/stream_demo_footage.py --input path/to/flood_clip.mp4

# Terminal 3 – start the FloodSense backend (which reads the RTSP stream)
cd app/backend && uvicorn main:app --reload

NOTES
─────
- The script loops the input video indefinitely (-stream_loop -1).
- By default it creates 2 RTSP streams on demo_cam_1 and demo_cam_2
  (matching the entries in app/data/cameras.json).
- Pass --cameras to override the number of parallel streams.
- The streams use the same source clip; real deployment replaces each URL
  in cameras.json with a distinct camera's actual stream URL.
- There is NO code branching between demo mode and real mode in cctv_ingest.py.
  Only the URL in cameras.json differs.
"""
from __future__ import annotations

import argparse
import asyncio
import signal
import subprocess
import sys
from pathlib import Path


RTSP_BASE = "rtsp://localhost:8554"
DEMO_PATHS = ["demo_cam_1", "demo_cam_2", "demo_cam_3"]


def _ffmpeg_cmd(input_path: str, rtsp_url: str) -> list[str]:
    """Build the ffmpeg command to loop a file to an RTSP endpoint."""
    return [
        "ffmpeg",
        "-re",                       # read input at native frame rate
        "-stream_loop", "-1",        # loop indefinitely
        "-i", input_path,
        "-c", "copy",                # no re-encode – preserve quality, save CPU
        "-f", "rtsp",
        rtsp_url,
    ]


async def _run_stream(input_path: str, rtsp_url: str, cam_name: str) -> None:
    cmd = _ffmpeg_cmd(input_path, rtsp_url)
    print(f"[{cam_name}] Streaming → {rtsp_url}")
    print(f"  Command: {' '.join(cmd)}")
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, stderr = await proc.communicate()
        if proc.returncode and proc.returncode != 0:
            print(
                f"[{cam_name}] ffmpeg exited with code {proc.returncode}.\n"
                f"  Stderr: {stderr.decode(errors='replace')[-500:]}",
                file=sys.stderr,
            )
    except asyncio.CancelledError:
        proc.terminate()
        raise


async def main(args: argparse.Namespace) -> None:
    input_path = str(Path(args.input).resolve())
    if not Path(input_path).exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    n_cams = min(args.cameras, len(DEMO_PATHS))
    tasks = []
    for i in range(n_cams):
        cam_name = DEMO_PATHS[i]
        rtsp_url = f"{RTSP_BASE}/{cam_name}"
        tasks.append(asyncio.create_task(_run_stream(input_path, rtsp_url, cam_name)))

    print(
        f"\nStreaming '{args.input}' to {n_cams} RTSP endpoint(s).\n"
        "Keep this terminal open. Press Ctrl+C to stop.\n"
        "Make sure mediamtx is running in a separate terminal first!\n"
    )

    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    def _sig(*_):
        stop.set_result(None)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _sig)
        except NotImplementedError:
            pass  # Windows

    try:
        await asyncio.wait(
            tasks, return_when=asyncio.FIRST_EXCEPTION,
        )
    except KeyboardInterrupt:
        pass
    finally:
        for t in tasks:
            t.cancel()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Loop a local video file to RTSP for the FloodSense demo.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to local video file (MP4, AVI, etc.)",
    )
    parser.add_argument(
        "--cameras", "-c",
        type=int,
        default=2,
        help=f"Number of parallel RTSP streams to create (1–{len(DEMO_PATHS)}, default 2)",
    )
    asyncio.run(main(parser.parse_args()))
