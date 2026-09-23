import os
import re
import html
import logging
import traceback
from typing import Tuple, Dict, Any, Optional, List
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

logger = logging.getLogger("studiora.youtube")

def _safe_log(msg: str):
    try:
        print(msg, flush=True)
    except (UnicodeEncodeError, Exception):
        try:
            safe_msg = str(msg).encode('ascii', errors='backslashreplace').decode('ascii')
            print(safe_msg, flush=True)
        except Exception:
            pass

class YouTubeService:
    """Service to safely validate YouTube URLs, fetch public metadata, and extract clean transcripts."""

    @staticmethod
    def extract_video_id(url: str) -> str:
        """Validate and extract the exact 11-character video ID from any YouTube URL format."""
        if not url or not isinstance(url, str):
            raise ValueError("Please enter a valid YouTube URL.")

        clean_url = url.strip()
        patterns = [
            r'(?:v=|\/vi?\/)([0-9A-Za-z_-]{11})(?:[&?\/#]|$)',
            r'youtu\.be\/([0-9A-Za-z_-]{11})(?:[&?\/#]|$)',
            r'youtube\.com\/embed\/([0-9A-Za-z_-]{11})(?:[&?\/#]|$)',
            r'youtube\.com\/shorts\/([0-9A-Za-z_-]{11})(?:[&?\/#]|$)',
            r'youtube\.com\/live\/([0-9A-Za-z_-]{11})(?:[&?\/#]|$)',
        ]
        for pattern in patterns:
            match = re.search(pattern, clean_url)
            if match:
                return match.group(1)

        # Fallback for youtube domain URLs with 11-char ID
        if "youtube.com" in clean_url or "youtu.be" in clean_url:
            match = re.search(r'([0-9A-Za-z_-]{11})', clean_url)
            if match:
                return match.group(1)

        raise ValueError("Please enter a valid YouTube URL (e.g., https://www.youtube.com/watch?v=...).")

    @staticmethod
    def clean_transcript(raw_snippets: List[str]) -> str:
        """
        Convert raw caption snippets into clean, educational plain text:
        - Decodes HTML entities (&amp;, &#39;, etc.)
        - Removes bracketed sound descriptions [Music], [Applause], [Laughter]
        - Removes parenthesized cues (applause), (cheering)
        - Removes music notes (♪, ♫, #)
        - Removes HTML / VTT tags (<font>, <c>, etc.)
        - Removes timestamp cues (00:00:01, 1:23)
        - Removes consecutive repeating lines
        - Normalizes whitespace and line breaks
        """
        cleaned_segments = []
        prev_line = ""

        for item in raw_snippets:
            if not item:
                continue
            text = html.unescape(str(item))
            # Remove bracketed and parenthesized cues
            text = re.sub(r'\[.*?\]', '', text)
            text = re.sub(r'\(.*?\)', '', text)
            # Remove music notes and symbols
            text = re.sub(r'[♪♫#]+', '', text)
            # Remove HTML/XML/VTT tags
            text = re.sub(r'<[^>]+>', '', text)
            # Remove standalone timestamps like 00:00 or 00:00:00
            text = re.sub(r'^\s*\d{1,2}:\d{2}(?::\d{2})?\s*', '', text)
            # Normalize internal whitespace
            text = re.sub(r'\s+', ' ', text).strip()

            if text and text.lower() != prev_line.lower():
                cleaned_segments.append(text)
                prev_line = text

        full_text = ' '.join(cleaned_segments)
        return re.sub(r'\s+', ' ', full_text).strip()

    @classmethod
    def get_youtube_content_details(cls, url: str) -> Tuple[str, str, str, Dict[str, Any]]:
        """
        Process a YouTube URL end-to-end:
        1. Validate URL & extract video ID
        2. Retrieve video metadata (title, duration)
        3. Retrieve available transcript (manual or auto-generated, multilingual)
        4. Clean and validate extracted text
        Returns: (cleaned_transcript, video_title, duration_summary)
        Raises: ValueError with clear user-facing explanation
        """
        clean_url = url.strip() if url else ""
        video_id = cls.extract_video_id(clean_url)

        _safe_log("\n" + "=" * 50)
        _safe_log("YOUTUBE PROCESSING STARTED")
        _safe_log(f"YOUTUBE INPUT:\n{clean_url}")
        _safe_log(f"VIDEO ID:\n{video_id}")
        logger.info("Starting YouTube processing for URL: %s (video_id: %s)", clean_url, video_id)

        # 1. Fetch metadata via yt-dlp
        title = f"YouTube Video ({video_id})"
        duration_str = "YouTube Video"
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 15,
            'extract_flat': False
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                if info:
                    title = info.get('title') or title
                    dur = info.get('duration') or 0
                    mins = dur // 60
                    secs = dur % 60
                    duration_str = f"YouTube ({mins}m {secs}s)" if mins > 0 else f"YouTube ({secs}s)"
        except Exception as meta_err:
            logger.warning("yt-dlp metadata extraction warning for %s: %s", video_id, str(meta_err))
            # Continue to transcript retrieval even if yt-dlp metadata fails

        # 2. Retrieve transcript using YouTubeTranscriptApi
        _safe_log("TRANSCRIPT RETRIEVAL:\nattempting...")
        raw_snippets = []
        selected_lang = "unknown"
        is_gen = False

        try:
            ytt = YouTubeTranscriptApi()
            transcript_list = ytt.list(video_id)
            available_transcripts = list(transcript_list)

            logger.info("Found %d transcript track(s) for video %s: %s",
                        len(available_transcripts), video_id,
                        [(t.language_code, t.language, t.is_generated) for t in available_transcripts])

            target_transcript = None
            # Preference 1: Manual English
            target_transcript = next((t for t in available_transcripts if not t.is_generated and t.language_code.lower().startswith('en')), None)
            # Preference 2: Manual any language
            if not target_transcript:
                target_transcript = next((t for t in available_transcripts if not t.is_generated), None)
            # Preference 3: Auto-generated English
            if not target_transcript:
                target_transcript = next((t for t in available_transcripts if t.is_generated and t.language_code.lower().startswith('en')), None)
            # Preference 4: Auto-generated any language (e.g. Hindi 'hi')
            if not target_transcript:
                target_transcript = next((t for t in available_transcripts if t.is_generated), None)
            # Preference 5: Any available
            if not target_transcript and available_transcripts:
                target_transcript = available_transcripts[0]

            if target_transcript:
                selected_lang = f"{target_transcript.language} ({target_transcript.language_code})"
                is_gen = target_transcript.is_generated
                _safe_log(f"TRANSCRIPT RESULT:\nfound ({selected_lang})")

                # Fetch transcript data
                fetched_data = target_transcript.fetch()
                for item in fetched_data:
                    snippet_text = getattr(item, 'text', item.get('text') if isinstance(item, dict) else str(item))
                    if snippet_text and snippet_text.strip():
                        raw_snippets.append(snippet_text.strip())

        except Exception as ytt_err:
            logger.warning("YouTubeTranscriptApi error for %s: %s", video_id, str(ytt_err))
            _safe_log(f"YOUTUBE TRANSCRIPT ERROR:\n{ytt_err}")

        # 3. Fallback: yt-dlp subtitle download if Strategy 1 returned no snippets
        if not raw_snippets:
            _safe_log("TRANSCRIPT RETRIEVAL (Strategy 2):\nattempting yt-dlp subtitles...")
            try:
                temp_dir = os.path.join(os.path.dirname(__file__), "..", "..", "scratch")
                os.makedirs(temp_dir, exist_ok=True)
                sub_outtmpl = os.path.join(temp_dir, f"ytsub_{video_id}")
                ydl_sub_opts = {
                    'skip_download': True,
                    'writesubtitles': True,
                    'writeautomaticsub': True,
                    'subtitleslangs': ['en', 'hi', 'all'],
                    'outtmpl': sub_outtmpl,
                    'quiet': True,
                    'no_warnings': True
                }
                with yt_dlp.YoutubeDL(ydl_sub_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

                sub_files = [f for f in os.listdir(temp_dir) if f.startswith(f"ytsub_{video_id}")]
                if sub_files:
                    target_file = os.path.join(temp_dir, sub_files[0])
                    with open(target_file, "r", encoding="utf-8", errors="ignore") as sf:
                        lines = sf.readlines()
                    for line in lines:
                        l = line.strip()
                        if l and not l.isdigit() and '-->' not in l and not l.startswith('WEBVTT') and not l.startswith('Kind:') and not l.startswith('Language:'):
                            raw_snippets.append(l)
                    try:
                        os.remove(target_file)
                    except Exception:
                        pass
            except Exception as dl_err:
                logger.warning("yt-dlp subtitle fallback failed for %s: %s", video_id, str(dl_err))
                _safe_log(f"YOUTUBE TRANSCRIPT ERROR (Strategy 2):\n{dl_err}")

        # Check results
        if not raw_snippets:
            _safe_log("TRANSCRIPT RESULT:\nnot found")
            raise ValueError("This video does not have an accessible transcript. Please upload the video file instead.")

        _safe_log(f"ENTRY COUNT:\n{len(raw_snippets)}")
        sample_snippet = ' '.join(raw_snippets[:3])
        _safe_log(f"FIRST SAMPLE:\n{sample_snippet[:150]}...")

        # 4. Clean transcript
        cleaned_text = cls.clean_transcript(raw_snippets)
        char_count = len(cleaned_text)
        word_count = len(cleaned_text.split())
        _safe_log(f"CLEAN TEXT LENGTH:\n{char_count} characters ({word_count} words)")
        _safe_log("=" * 50 + "\n")

        # 5. Validation before Groq
        if char_count < 40 or word_count < 10:
            raise ValueError("Extracted transcript is insufficient or empty. Please upload the video file instead.")

        meta = {
            "language": selected_lang,
            "is_generated": is_gen,
            "entry_count": len(raw_snippets),
            "character_count": char_count,
            "word_count": word_count
        }

        return cleaned_text, title, duration_str, meta

    @classmethod
    def get_youtube_content(cls, url: str) -> Tuple[str, str, str]:
        """Convenience method returning (cleaned_transcript, video_title, duration_summary)."""
        text, title, duration, _ = cls.get_youtube_content_details(url)
        return text, title, duration

    @classmethod
    def test_transcript_diagnostics(cls, url: str) -> Dict[str, Any]:
        """Diagnostic method for the test endpoint."""
        try:
            video_id = cls.extract_video_id(url)
        except Exception as e:
            return {
                "success": False,
                "video_id": None,
                "error_type": "InvalidUrlError",
                "error_message": str(e)
            }

        try:
            clean_text, title, duration_str, meta = cls.get_youtube_content_details(url)
            return {
                "success": True,
                "video_id": video_id,
                "title": title,
                "duration": duration_str,
                "transcript_found": True,
                "language": meta.get("language", "unknown"),
                "entry_count": meta.get("entry_count", 0),
                "character_count": len(clean_text),
                "word_count": len(clean_text.split()),
                "sample": clean_text[:300]
            }
        except Exception as e:
            tb = traceback.format_exc()
            logger.error("Diagnostic error for %s:\n%s", video_id, tb)
            return {
                "success": False,
                "video_id": video_id,
                "error_type": type(e).__name__,
                "error_message": str(e)
            }

youtube_service = YouTubeService()
