"""Assembles a vertical slideshow video (scene images + narration audio)
into an MP4 with ffmpeg — the last step of VIDEO_ASSET generation. Uses the
static ffmpeg binary bundled by imageio-ffmpeg, so this never depends on
ffmpeg being installed on the host or in the Docker image.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


class VideoAssemblyError(Exception):
    pass


def _run(args: list[str], timeout_seconds: int) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=timeout_seconds)


def _audio_duration_seconds(ffmpeg_exe: str, audio_path: Path, timeout_seconds: int) -> float:
    proc = _run([ffmpeg_exe, "-i", str(audio_path), "-f", "null", "-"], timeout_seconds)
    match = _DURATION_RE.search(proc.stderr.decode("utf-8", errors="ignore"))
    if not match:
        raise VideoAssemblyError("could not read narration audio duration")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def assemble_slideshow(
    images: list[bytes],
    audio: bytes,
    *,
    width: int = 1080,
    height: int = 1920,
    timeout_seconds: int = 120,
) -> bytes:
    """Builds an MP4: each image shown for an equal slice of the narration's
    duration, letterboxed to (width, height), with the narration as the
    audio track. Raises VideoAssemblyError on any ffmpeg failure."""
    if not images:
        raise VideoAssemblyError("no scene images to assemble")

    ffmpeg_exe = get_ffmpeg_exe()

    with tempfile.TemporaryDirectory(prefix="rqt21-video-") as tmp:
        tmp_dir = Path(tmp)
        audio_path = tmp_dir / "narration.mp3"
        audio_path.write_bytes(audio)

        duration = _audio_duration_seconds(ffmpeg_exe, audio_path, timeout_seconds)
        per_scene = max(duration / len(images), 0.5)

        image_paths = []
        for i, content in enumerate(images):
            path = tmp_dir / f"scene_{i:03d}.png"
            path.write_bytes(content)
            image_paths.append(path)

        concat_path = tmp_dir / "concat.txt"
        lines = []
        for path in image_paths:
            lines.append(f"file '{path.as_posix()}'")
            lines.append(f"duration {per_scene:.3f}")
        # ffmpeg's concat demuxer ignores the last entry's duration unless
        # the final file is repeated once more without one.
        lines.append(f"file '{image_paths[-1].as_posix()}'")
        concat_path.write_text("\n".join(lines), encoding="utf-8")

        output_path = tmp_dir / "output.mp4"
        args = [
            ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-i", str(audio_path),
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p",
            "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart",
            str(output_path),
        ]
        proc = _run(args, timeout_seconds)
        if proc.returncode != 0 or not output_path.exists():
            raise VideoAssemblyError(f"ffmpeg assembly failed: {proc.stderr[-800:]!r}")

        return output_path.read_bytes()


def assemble_from_clips(
    clips: list[bytes],
    audio: bytes,
    *,
    width: int = 1080,
    height: int = 1920,
    timeout_seconds: int = 120,
) -> bytes:
    """Builds an MP4 from real video clips (one per scene, e.g. licensed
    stock footage) instead of stills: each clip is cropped/scaled to fill
    the frame and trimmed to an equal slice of the narration's duration,
    concatenated back to back, muted, and muxed with the narration as the
    only audio track. Raises VideoAssemblyError on any ffmpeg failure."""
    if not clips:
        raise VideoAssemblyError("no scene clips to assemble")

    ffmpeg_exe = get_ffmpeg_exe()

    with tempfile.TemporaryDirectory(prefix="rqt21-video-clips-") as tmp:
        tmp_dir = Path(tmp)
        audio_path = tmp_dir / "narration.mp3"
        audio_path.write_bytes(audio)

        duration = _audio_duration_seconds(ffmpeg_exe, audio_path, timeout_seconds)
        per_scene = max(duration / len(clips), 1.0)

        segment_paths = []
        for i, content in enumerate(clips):
            clip_path = tmp_dir / f"clip_{i:03d}.mp4"
            clip_path.write_bytes(content)
            segment_path = tmp_dir / f"segment_{i:03d}.mp4"
            # Loop the source clip if it's shorter than the slice it needs
            # to fill, crop/scale to fill (never letterbox real footage),
            # strip its original audio — narration is the only audio track.
            args = [
                ffmpeg_exe, "-y",
                "-stream_loop", "-1", "-i", str(clip_path),
                "-t", f"{per_scene:.3f}",
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},format=yuv420p",
                "-an", "-r", "25", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                str(segment_path),
            ]
            proc = _run(args, timeout_seconds)
            if proc.returncode != 0 or not segment_path.exists():
                raise VideoAssemblyError(f"ffmpeg clip normalization failed: {proc.stderr[-800:]!r}")
            segment_paths.append(segment_path)

        concat_path = tmp_dir / "concat.txt"
        concat_path.write_text(
            "\n".join(f"file '{p.as_posix()}'" for p in segment_paths), encoding="utf-8"
        )

        video_only_path = tmp_dir / "video_only.mp4"
        concat_args = [
            ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_path),
            "-c", "copy",
            str(video_only_path),
        ]
        proc = _run(concat_args, timeout_seconds)
        if proc.returncode != 0 or not video_only_path.exists():
            raise VideoAssemblyError(f"ffmpeg clip concat failed: {proc.stderr[-800:]!r}")

        output_path = tmp_dir / "output.mp4"
        mux_args = [
            ffmpeg_exe, "-y",
            "-i", str(video_only_path),
            "-i", str(audio_path),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-shortest", "-movflags", "+faststart",
            str(output_path),
        ]
        proc = _run(mux_args, timeout_seconds)
        if proc.returncode != 0 or not output_path.exists():
            raise VideoAssemblyError(f"ffmpeg audio mux failed: {proc.stderr[-800:]!r}")

        return output_path.read_bytes()
