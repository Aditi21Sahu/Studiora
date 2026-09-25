import os
import re
import html
import logging
from typing import Tuple, List, Dict, Any, Optional
import requests
from app.config import settings

logger = logging.getLogger("studiora.transcript")

def _safe_log(msg: str):
    """Safely log messages to stdout without Unicode encoding issues."""
    try:
        print(msg, flush=True)
    except (UnicodeEncodeError, Exception):
        try:
            safe_msg = str(msg).encode('ascii', errors='backslashreplace').decode('ascii')
            print(safe_msg, flush=True)
        except Exception:
            pass

class TranscriptService:
    """
    Dedicated Service for YouTube Transcript Retrieval.

    Architecture:
    1. External Hosted Transcript API (Supadata AI):
       - Solves the Render cloud datacenter IP restriction where YouTube blocks automated requests.
       - Configured via environment variable YOUTUBE_TRANSCRIPT_API_KEY.
       - Free tier: 100 free requests/month with no credit card required (https://supadata.ai).
       - Supports auto-generated and manual captions in all languages.

    2. Seamless Local Development Fallback:
       - If YOUTUBE_TRANSCRIPT_API_KEY is not set or external quota is reached,
         gracefully falls back to local multi-strategy retrieval (youtube-transcript-api,
         direct Innertube Android client, yt-dlp subtitles, and Groq Whisper).
    """

    SUPADATA_TRANSCRIPT_URL = "https://api.supadata.ai/v1/transcript"
    REQUEST_TIMEOUT_SECONDS = 15

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        """Retrieve and validate the configured external transcript API key."""
        key = getattr(settings, "YOUTUBE_TRANSCRIPT_API_KEY", None) or os.getenv("YOUTUBE_TRANSCRIPT_API_KEY")
        if not key:
            return None
        cleaned = key.strip()
        # Ignore dummy placeholders
        if not cleaned or cleaned.startswith("your_") or "placeholder" in cleaned.lower():
            return None
        return cleaned

    @classmethod
    def fetch_from_external_api(cls, video_id: str, url: Optional[str] = None) -> Tuple[Optional[List[str]], Optional[str], bool, Optional[str]]:
        """
        Query external transcript service (Supadata API) to retrieve caption text segments.

        Returns:
            Tuple of (raw_snippets_list, language_code, is_generated_bool, error_message_or_None)
        """
        api_key = cls.get_api_key()
        if not api_key:
            _safe_log("[TranscriptService] YOUTUBE_TRANSCRIPT_API_KEY is not configured in environment.")
            return None, None, False, "External transcript API key not configured"

        # Safely log presence of environment variable without revealing the key
        masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
        _safe_log(f"[TranscriptService] External API Key verified in environment (length: {len(api_key)}, masked: {masked_key})")

        # Construct the canonical YouTube URL required by Supadata
        canonical_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else url
        if not canonical_url:
            return None, None, False, "No valid video URL or video ID provided"

        _safe_log(f"[TranscriptService] Querying Supadata: GET {cls.SUPADATA_TRANSCRIPT_URL}")
        _safe_log(f"[TranscriptService] Request Parameters: url={canonical_url}, text=false")
        logger.info("Calling Supadata transcript API with canonical URL: %s", canonical_url)

        headers = {
            "x-api-key": api_key,
            "User-Agent": "Studiora-Cloud/1.0"
        }

        # Supadata documentation explicitly requires the full media link in the 'url' parameter
        params = {
            "url": canonical_url,
            "text": "false"  # Retrieve structured JSON segments
        }

        try:
            response = requests.get(
                cls.SUPADATA_TRANSCRIPT_URL,
                headers=headers,
                params=params,
                timeout=cls.REQUEST_TIMEOUT_SECONDS
            )

            _safe_log(f"[TranscriptService] Supadata HTTP Status: {response.status_code}")

            # Check HTTP status
            if response.status_code in (200, 202):
                data = response.json() if response.content else {}

                # Handle async jobId if Supadata queues processing
                job_id = data.get("jobId")
                if job_id and not data.get("content"):
                    _safe_log(f"[TranscriptService] Supadata queued async job: {job_id}. Polling for completion...")
                    import time
                    job_url = f"https://api.supadata.ai/v1/transcript/{job_id}"
                    for attempt in range(6):  # Poll up to 6 times (~9 seconds)
                        time.sleep(1.5)
                        job_res = requests.get(job_url, headers=headers, timeout=cls.REQUEST_TIMEOUT_SECONDS)
                        if job_res.status_code == 200:
                            job_data = job_res.json()
                            if job_data.get("content") or job_data.get("text"):
                                data = job_data
                                break
                            elif job_data.get("status") in ("failed", "error"):
                                msg = f"Supadata async job failed: {job_data.get('error') or job_data.get('message')}"
                                _safe_log(f"[TranscriptService] {msg}")
                                return None, None, False, msg

                raw_snippets: List[str] = []

                # Format 1: data.content is a list of segment dicts [{"text": "...", "start": ...}]
                content = data.get("content")
                if isinstance(content, list):
                    for seg in content:
                        if isinstance(seg, dict):
                            t = seg.get("text")
                            if t and str(t).strip():
                                raw_snippets.append(str(t).strip())
                        elif isinstance(seg, str) and seg.strip():
                            raw_snippets.append(seg.strip())
                elif isinstance(content, str) and content.strip():
                    raw_snippets = [content.strip()]

                # Format 2: fallback to 'text' or 'transcript' field
                if not raw_snippets:
                    alt_text = data.get("text") or data.get("transcript")
                    if isinstance(alt_text, str) and alt_text.strip():
                        raw_snippets = [alt_text.strip()]

                lang = data.get("lang") or data.get("language") or "auto"
                is_gen = bool(data.get("is_generated", False) or data.get("ai_fallback", False))

                if raw_snippets:
                    _safe_log(f"[TranscriptService] Supadata SUCCESS: retrieved {len(raw_snippets)} segments (lang: {lang})")
                    return raw_snippets, lang, is_gen, None
                else:
                    msg = "External transcript API returned 200 OK but content was empty."
                    _safe_log(f"[TranscriptService] {msg} Safe Response: {response.text[:200]}")
                    logger.warning("[TranscriptService] %s Response: %s", msg, response.text[:200])
                    return None, lang, is_gen, msg

            elif response.status_code == 206:
                msg = f"External transcript API indicated no transcript tracks available (HTTP 206): {response.text[:200]}"
                _safe_log(f"[TranscriptService] {msg}")
                logger.info("[TranscriptService] HTTP 206: %s", response.text)
                return None, None, False, msg

            elif response.status_code == 400:
                msg = f"External transcript API returned HTTP 400 (Bad Request): {response.text[:200]}"
                _safe_log(f"[TranscriptService] ERROR: {msg}")
                logger.warning("[TranscriptService] HTTP 400: %s", response.text)
                return None, None, False, msg

            elif response.status_code in (401, 403):
                msg = f"External transcript API key unauthorized or invalid (HTTP {response.status_code}): {response.text[:200]}"
                _safe_log(f"[TranscriptService] ERROR: {msg}")
                logger.warning("[TranscriptService] HTTP %d: %s", response.status_code, response.text)
                return None, None, False, msg

            elif response.status_code == 429:
                msg = f"External transcript API monthly quota or rate limit exceeded (HTTP 429): {response.text[:200]}"
                _safe_log(f"[TranscriptService] ERROR: {msg}")
                logger.warning("[TranscriptService] HTTP 429: %s", response.text)
                return None, None, False, msg

            elif response.status_code == 404:
                msg = f"External transcript API: video or transcript not found (HTTP 404): {response.text[:200]}"
                _safe_log(f"[TranscriptService] {msg}")
                logger.info("[TranscriptService] HTTP 404: %s", response.text)
                return None, None, False, msg

            else:
                msg = f"External transcript API returned HTTP {response.status_code}: {response.text[:200]}"
                _safe_log(f"[TranscriptService] {msg}")
                logger.warning("[TranscriptService] %s", msg)
                return None, None, False, msg

        except requests.exceptions.Timeout:
            msg = f"External transcript API timed out after {cls.REQUEST_TIMEOUT_SECONDS}s."
            logger.warning("[TranscriptService] %s", msg)
            return None, None, False, msg
        except requests.exceptions.RequestException as req_err:
            msg = f"External transcript API request connection error: {str(req_err)}"
            logger.warning("[TranscriptService] %s", msg)
            return None, None, False, msg
        except Exception as e:
            msg = f"External transcript API unexpected error: {type(e).__name__}: {str(e)}"
            logger.error("[TranscriptService] %s", msg)
            return None, None, False, msg

    @classmethod
    def clean_transcript(cls, raw_snippets: List[str]) -> str:
        """
        Convert raw caption snippets into clean, educational plain text:
        - Decodes HTML entities (&amp;, &#39;, etc.)
        - Removes bracketed cues: [Music], [Applause], [Laughter]
        - Removes parenthesized cues: (applause), (cheering)
        - Removes music notes: (♪, ♫, #)
        - Removes HTML / VTT tags (<font>, <c>, etc.)
        - Removes standalone timestamps (00:00:01, 1:23)
        - Eliminates consecutive duplicate lines
        - Normalizes whitespace
        """
        if not raw_snippets:
            return ""

        cleaned_segments = []
        prev_line = ""

        for item in raw_snippets:
            if not item:
                continue
            text = html.unescape(str(item))
            # Remove bracketed and parenthesized sound cues
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
    def get_transcript(cls, url_or_video_id: str) -> Tuple[str, List[str], Dict[str, Any]]:
        """
        High-level transcript retrieval coordinator:
        1. Validates input and extracts video ID
        2. Tries External Transcript API (Supadata) if key is configured
        3. If key missing or external call fails, falls back gracefully to local YouTube strategies
        4. Cleans and joins text into coherent educational transcript
        Returns:
            Tuple of (cleaned_transcript_text, raw_snippets, metadata_dict)
        """
        from app.services.youtube_service import YouTubeService
        video_id = YouTubeService.extract_video_id(url_or_video_id) if ("youtube.com" in url_or_video_id or "youtu.be" in url_or_video_id) else url_or_video_id

        raw_snippets: List[str] = []
        strategy_used = None
        selected_lang = "unknown"
        is_gen = False
        err = None

        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        if cls.get_api_key():
            snippets, lang, gen, api_err = cls.fetch_from_external_api(video_id, canonical_url)
            if snippets:
                raw_snippets = snippets
                selected_lang = lang or "unknown"
                is_gen = gen
                strategy_used = "External Transcript API (Supadata)"
            else:
                err = api_err

        if not raw_snippets:
            # Fallback to local youtube_service strategies
            snippets, lang, gen, api_err = YouTubeService._fetch_via_transcript_api(video_id)
            if snippets:
                raw_snippets = snippets
                selected_lang = lang
                is_gen = gen
                strategy_used = "youtube-transcript-api"
            else:
                err = api_err

        if not raw_snippets:
            snippets, lang, gen, api_err = YouTubeService._fetch_via_innertube_android(video_id)
            if snippets:
                raw_snippets = snippets
                selected_lang = lang
                is_gen = gen
                strategy_used = "Innertube Android API"
            else:
                err = api_err

        if not raw_snippets:
            snippets, lang, gen, api_err = YouTubeService._fetch_via_ytdlp_subtitles(video_id)
            if snippets:
                raw_snippets = snippets
                selected_lang = lang
                is_gen = gen
                strategy_used = "yt-dlp timedtext stream"
            else:
                err = api_err

        if not raw_snippets:
            snippets, lang, gen, api_err = YouTubeService._fetch_via_audio_transcription(video_id)
            if snippets:
                raw_snippets = snippets
                selected_lang = lang
                is_gen = gen
                strategy_used = "yt-dlp audio + Groq Whisper STT"
            else:
                err = api_err

        if not raw_snippets:
            raise ValueError(f"Could not retrieve transcript for video {video_id}. Last error: {err}")

        cleaned_text = cls.clean_transcript(raw_snippets)
        meta = {
            "video_id": video_id,
            "language": selected_lang,
            "is_generated": is_gen,
            "strategy_used": strategy_used,
            "entry_count": len(raw_snippets),
            "character_count": len(cleaned_text),
            "word_count": len(cleaned_text.split())
        }
        return cleaned_text, raw_snippets, meta

transcript_service = TranscriptService()

