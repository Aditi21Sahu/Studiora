import os
import re
import shutil
import subprocess
import logging
from typing import Tuple
from app.ai.groq_service import groq_service
from app.services.youtube_service import youtube_service

logger = logging.getLogger(__name__)

def _get_ffmpeg_executable() -> str:
    """Locate the FFmpeg executable from system PATH or common installation directories."""
    path_from_env = shutil.which("ffmpeg")
    if path_from_env:
        return path_from_env

    # Common Windows locations including WinGet packages
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(local_app_data, r"Microsoft\WinGet\Packages\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe"),
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c

    return "ffmpeg"

class VideoService:
    """Service to process video files, audio extraction, Groq Whisper transcription, and YouTube transcripts."""

    @staticmethod
    def extract_youtube_video_id(url: str) -> str:
        return youtube_service.extract_video_id(url)

    @staticmethod
    def get_youtube_transcript(url: str) -> Tuple[str, str]:
        """Fetch transcript and duration summary using dedicated YouTube service."""
        text, title, duration_str = youtube_service.get_youtube_content(url)
        return text, duration_str

    @staticmethod
    def extract_audio_and_transcribe(video_path: str) -> Tuple[str, str]:
        """
        Extract audio from an uploaded video file using FFmpeg, and transcribe via Groq STT (Whisper).
        Returns: (transcript_text, file_summary)
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        ffmpeg_bin = _get_ffmpeg_executable()
        base, _ = os.path.splitext(video_path)
        audio_output = f"{base}_audio.mp3"

        try:
            # Extract high-efficiency mono speech audio (16kHz, 48kbps mono MP3)
            cmd = [
                ffmpeg_bin,
                "-y",  # overwrite output if exists
                "-i", video_path,
                "-vn",  # discard video stream
                "-acodec", "libmp3lame",
                "-ac", "1",  # mono channel
                "-ar", "16000",  # 16kHz speech sample rate
                "-b:a", "48k",  # 48kbps bitrate for fast upload within Groq 25MB limit
                audio_output
            ]
            logger.info("Running FFmpeg: %s", " ".join(cmd))
            process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

            # Send extracted audio to Groq Whisper STT
            logger.info("Transcribing audio with Groq Whisper...")
            transcript = groq_service.transcribe_audio(audio_output)
            
            # Clean transcript: normalize whitespaces, remove excessive line breaks
            cleaned_transcript = re.sub(r'\s+', ' ', transcript).strip()
            logger.info("Groq Whisper transcription succeeded (%d characters)", len(cleaned_transcript))

            # Calculate video file size
            file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            return cleaned_transcript, f"Video ({file_size_mb:.1f} MB)"

        except subprocess.CalledProcessError as e:
            err_msg = e.stderr.decode('utf-8', errors='ignore')
            logger.error("FFmpeg execution error: %s", err_msg)
            raise RuntimeError(f"Failed to extract audio track from video using FFmpeg: {err_msg[:200]}")
        except FileNotFoundError:
            logger.error("FFmpeg executable not found in PATH or standard directories.")
            raise RuntimeError("FFmpeg is not installed or not available in the system PATH.")
        finally:
            if os.path.exists(audio_output):
                try:
                    os.remove(audio_output)
                except Exception:
                    pass

video_service = VideoService()
