import os
import re
import html
import uuid
import logging
import tempfile
import traceback
import urllib.parse
from typing import Tuple, Dict, Any, Optional, List

import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from app.ai.groq_service import groq_service

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
    """Service to safely validate YouTube URLs, fetch public metadata, and extract clean transcripts with multi-tier fallback."""

    @staticmethod
    def extract_video_id(url: str) -> str:
        """Validate and extract the exact 11-character video ID from any YouTube URL format."""
        if not url or not isinstance(url, str):
            raise ValueError("Please enter a valid YouTube URL.")

        clean_url = url.strip()

        # 1. URL parsing via urllib
        try:
            parsed = urllib.parse.urlparse(clean_url)
            hostname = (parsed.hostname or "").lower()

            if "youtube.com" in hostname or "youtu.be" in hostname:
                # youtu.be/VIDEO_ID
                if "youtu.be" in hostname:
                    path_parts = [p for p in parsed.path.split("/") if p]
                    if path_parts and len(path_parts[0]) == 11:
                        return path_parts[0]

                # Query param: ?v=VIDEO_ID
                query_params = urllib.parse.parse_qs(parsed.query)
                if "v" in query_params and query_params["v"]:
                    val = query_params["v"][0].strip()
                    if len(val) == 11:
                        return val

                # Path patterns: /embed/ID, /shorts/ID, /live/ID, /v/ID
                for prefix in ["/embed/", "/shorts/", "/live/", "/v/"]:
                    if prefix in parsed.path:
                        candidate = parsed.path.split(prefix)[1].split("/")[0].split("?")[0].split("&")[0]
                        if len(candidate) == 11:
                            return candidate
        except Exception:
            pass

        # 2. Comprehensive Regex Fallback Patterns
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
    def _fetch_via_transcript_api(cls, video_id: str) -> Tuple[List[str], str, bool, Optional[str]]:
        """
        Strategy 1: Direct transcript extraction via youtube-transcript-api.
        Compatible with BOTH youtube-transcript-api 0.6.3 (classmethod on Render)
        and 1.x (instance method).
        Supports manual English, auto English, and non-English with translation.
        """
        raw_snippets = []
        selected_lang = "unknown"
        is_gen = False
        strategy_err = None

        try:
            transcript_list = None
            if hasattr(YouTubeTranscriptApi, 'list_transcripts'):
                # Version 0.6.3 classmethod (Render deployment)
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            elif hasattr(YouTubeTranscriptApi, 'list'):
                # Version 1.x instance method
                transcript_list = YouTubeTranscriptApi().list(video_id)

            if transcript_list:
                available_transcripts = list(transcript_list)
                logger.info("Found %d transcript track(s) for video %s: %s",
                            len(available_transcripts), video_id,
                            [(getattr(t, 'language_code', ''), getattr(t, 'language', ''), getattr(t, 'is_generated', False)) for t in available_transcripts])

                target_transcript = None
                # Preference 1: Manual English
                target_transcript = next((t for t in available_transcripts if not getattr(t, 'is_generated', False) and getattr(t, 'language_code', '').lower().startswith('en')), None)
                # Preference 2: Auto-generated English
                if not target_transcript:
                    target_transcript = next((t for t in available_transcripts if getattr(t, 'is_generated', False) and getattr(t, 'language_code', '').lower().startswith('en')), None)
                # Preference 3: Manual any language
                if not target_transcript:
                    target_transcript = next((t for t in available_transcripts if not getattr(t, 'is_generated', False)), None)
                # Preference 4: Auto-generated any language
                if not target_transcript:
                    target_transcript = next((t for t in available_transcripts if getattr(t, 'is_generated', False)), None)
                # Preference 5: Any available track
                if not target_transcript and available_transcripts:
                    target_transcript = available_transcripts[0]

                if target_transcript:
                    lang_code = getattr(target_transcript, 'language_code', 'en')
                    lang_name = getattr(target_transcript, 'language', lang_code)
                    selected_lang = f"{lang_name} ({lang_code})"
                    is_gen = getattr(target_transcript, 'is_generated', False)

                    # Translate to English if non-English and translatable
                    fetched_data = None
                    if not lang_code.lower().startswith('en') and getattr(target_transcript, 'is_translatable', False):
                        try:
                            translated_t = target_transcript.translate('en')
                            fetched_data = translated_t.fetch()
                            selected_lang += " -> translated to English"
                        except Exception:
                            fetched_data = None

                    if fetched_data is None:
                        fetched_data = target_transcript.fetch()

                    for item in fetched_data:
                        text_val = getattr(item, 'text', item.get('text') if isinstance(item, dict) else str(item))
                        if text_val and text_val.strip():
                            raw_snippets.append(text_val.strip())

            # Fallback to direct get_transcript if list_transcripts didn't produce snippets
            if not raw_snippets and hasattr(YouTubeTranscriptApi, 'get_transcript'):
                try:
                    direct_data = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'en-GB'])
                except Exception:
                    direct_data = YouTubeTranscriptApi.get_transcript(video_id)
                for item in direct_data:
                    text_val = item.get('text', '') if isinstance(item, dict) else getattr(item, 'text', '')
                    if text_val and text_val.strip():
                        raw_snippets.append(text_val.strip())
                if raw_snippets:
                    selected_lang = "English / default"
                    is_gen = True

        except Exception as ytt_err:
            strategy_err = str(ytt_err)
            logger.warning("YouTubeTranscriptApi failed for %s: %s", video_id, strategy_err)

        return raw_snippets, selected_lang, is_gen, strategy_err

    @classmethod
    def _fetch_via_ytdlp_subtitles(cls, video_id: str, info: Optional[Dict[str, Any]] = None) -> Tuple[List[str], str, bool, Optional[str]]:
        """
        Strategy 2: Extract subtitle streams in-memory using yt-dlp signed timedtext endpoints.
        Bypasses cloud IP blocking and doesn't write temporary subtitle files to disk.
        """
        raw_snippets = []
        selected_lang = "unknown"
        is_gen = False
        strategy_err = None

        try:
            ydl_opts = {
                'skip_download': True,
                'quiet': True,
                'no_warnings': True,
                'socket_timeout': 15,
                'extract_flat': False
            }
            if not info:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)

            if not info:
                return [], selected_lang, is_gen, "Could not extract video metadata from yt-dlp"

            subtitles = info.get('subtitles') or {}
            auto_captions = info.get('automatic_captions') or {}

            chosen_track = None  # (lang, fmts, is_generated)

            # Preference 1: Manual English
            for lang, fmts in subtitles.items():
                if lang.lower().startswith('en'):
                    chosen_track = (lang, fmts, False)
                    break
            # Preference 2: Auto English
            if not chosen_track:
                for lang, fmts in auto_captions.items():
                    if lang.lower().startswith('en'):
                        chosen_track = (lang, fmts, True)
                        break
            # Preference 3: Manual any language
            if not chosen_track:
                for lang, fmts in subtitles.items():
                    chosen_track = (lang, fmts, False)
                    break
            # Preference 4: Auto any language
            if not chosen_track:
                for lang, fmts in auto_captions.items():
                    chosen_track = (lang, fmts, True)
                    break

            if not chosen_track:
                return [], selected_lang, is_gen, "No subtitle or caption tracks found in yt-dlp metadata"

            lang, fmts, is_gen = chosen_track
            selected_lang = lang

            # Prioritize format: json3, vtt, srv1, srv2, srv3, ttml
            target_fmt = next((f for f in fmts if f.get('ext') == 'json3'), None)
            if not target_fmt:
                target_fmt = next((f for f in fmts if f.get('ext') == 'vtt'), None)
            if not target_fmt and fmts:
                target_fmt = fmts[0]

            if not target_fmt or not target_fmt.get('url'):
                return [], selected_lang, is_gen, "No valid timedtext download URL found for subtitle track"

            sub_url = target_fmt['url']
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            resp = requests.get(sub_url, headers=headers, timeout=15)
            if resp.status_code == 200:
                if target_fmt.get('ext') == 'json3':
                    try:
                        data = resp.json()
                        for ev in data.get('events', []):
                            segs = ev.get('segs')
                            if segs:
                                t = ''.join(s.get('utf8', '') for s in segs if s.get('utf8'))
                                if t.strip():
                                    raw_snippets.append(t.strip())
                            elif 'utf8' in ev and ev.get('utf8'):
                                t = ev.get('utf8', '').strip()
                                if t:
                                    raw_snippets.append(t)
                    except Exception as je:
                        logger.warning("Failed parsing json3 subtitles: %s", str(je))

                # If json3 parsing yielded nothing or format was vtt/srv/text:
                if not raw_snippets and resp.text:
                    for line in resp.text.splitlines():
                        l = line.strip()
                        if (l and not l.isdigit() 
                                and '-->' not in l 
                                and not l.startswith('WEBVTT') 
                                and not l.startswith('Kind:') 
                                and not l.startswith('Language:')
                                and not l.startswith('<?xml')
                                and not l.startswith('<transcript>')):
                            raw_snippets.append(l)

        except Exception as yt_dl_err:
            strategy_err = str(yt_dl_err)
            logger.warning("yt-dlp subtitle stream extraction failed for %s: %s", video_id, strategy_err)

        return raw_snippets, selected_lang, is_gen, strategy_err

    @classmethod
    def _fetch_via_audio_transcription(cls, video_id: str) -> Tuple[List[str], str, bool, Optional[str]]:
        """
        Strategy 3: Download low-bitrate audio stream (<24MB) via yt-dlp and transcribe using Groq Whisper.
        Acts as the ultimate fallback when YouTube blocks all timedtext endpoints or video lacks captions.
        Strictly cleans up all temporary audio files.
        """
        raw_snippets = []
        selected_lang = "Transcribed with Groq Whisper"
        is_gen = True
        strategy_err = None

        if not getattr(groq_service, 'client', None):
            return [], "", False, "GROQ_API_KEY is not configured for Whisper speech-to-text fallback."

        temp_dir = tempfile.gettempdir()
        audio_base = os.path.join(temp_dir, f"studiora_yt_{video_id}_{uuid.uuid4().hex[:8]}")
        audio_template = f"{audio_base}.%(ext)s"
        downloaded_audio = None

        try:
            ydl_audio_opts = {
                'format': 'ba[ext=m4a]/ba[ext=mp3]/worstaudio/ba',
                'outtmpl': audio_template,
                'quiet': True,
                'no_warnings': True,
                'max_filesize': 24 * 1024 * 1024,  # Keep under Groq's 25 MB file limit
                'socket_timeout': 30,
            }
            with yt_dlp.YoutubeDL(ydl_audio_opts) as ydl:
                ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

            # Check potential files
            for ext in [".m4a", ".mp3", ".webm", ".opus", ".aac"]:
                cand = f"{audio_base}{ext}"
                if os.path.isfile(cand):
                    downloaded_audio = cand
                    break

            if not downloaded_audio:
                for fname in os.listdir(temp_dir):
                    if fname.startswith(os.path.basename(audio_base)):
                        cand = os.path.join(temp_dir, fname)
                        if os.path.isfile(cand) and os.path.getsize(cand) > 1000:
                            downloaded_audio = cand
                            break

            if downloaded_audio and os.path.isfile(downloaded_audio):
                whisper_text = groq_service.transcribe_audio(downloaded_audio)
                if whisper_text and whisper_text.strip():
                    raw_snippets.append(whisper_text.strip())

        except Exception as audio_err:
            strategy_err = str(audio_err)
            logger.warning("Audio transcription fallback failed for %s: %s", video_id, strategy_err)
        finally:
            # Strict cleanup
            if downloaded_audio and os.path.isfile(downloaded_audio):
                try:
                    os.remove(downloaded_audio)
                except Exception:
                    pass
            try:
                for fname in os.listdir(temp_dir):
                    if fname.startswith(os.path.basename(audio_base)):
                        try:
                            os.remove(os.path.join(temp_dir, fname))
                        except Exception:
                            pass
            except Exception:
                pass

        return raw_snippets, selected_lang, is_gen, strategy_err

    @classmethod
    def get_youtube_content_details(cls, url: str) -> Tuple[str, str, str, Dict[str, Any]]:
        """
        Process a YouTube URL end-to-end:
        1. Validate URL & extract video ID
        2. Retrieve video metadata (title, duration)
        3. Retrieve available transcript via 3-tier strategy (Transcript API -> yt-dlp Subtitles -> Groq Whisper)
        4. Clean and validate extracted text
        Returns: (cleaned_transcript, video_title, duration_summary, meta_dict)
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
        info = None
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 15,
            'extract_flat': False
        }
        meta_err_str = None
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
            meta_err_str = str(meta_err)
            logger.warning("yt-dlp metadata extraction warning for %s: %s", video_id, meta_err_str)

        # 2. Strategy 1: Direct extraction via youtube-transcript-api
        _safe_log("TRANSCRIPT RETRIEVAL (Strategy 1):\nattempting direct transcript API...")
        raw_snippets, selected_lang, is_gen, err1 = cls._fetch_via_transcript_api(video_id)
        strategy_used = "youtube-transcript-api" if raw_snippets else None

        # 3. Strategy 2: In-memory subtitle stream extraction via yt-dlp
        err2 = None
        if not raw_snippets:
            _safe_log("TRANSCRIPT RETRIEVAL (Strategy 2):\nattempting yt-dlp subtitle stream...")
            raw_snippets, selected_lang, is_gen, err2 = cls._fetch_via_ytdlp_subtitles(video_id, info=info)
            if raw_snippets:
                strategy_used = "yt-dlp timedtext stream"

        # 4. Strategy 3: Audio download + Groq Whisper Speech-to-Text
        err3 = None
        if not raw_snippets:
            _safe_log("TRANSCRIPT RETRIEVAL (Strategy 3):\nattempting audio stream download + Groq Whisper STT...")
            raw_snippets, selected_lang, is_gen, err3 = cls._fetch_via_audio_transcription(video_id)
            if raw_snippets:
                strategy_used = "yt-dlp audio + Groq Whisper STT"

        # 5. Differentiated Error Handling if all strategies fail
        if not raw_snippets:
            _safe_log("TRANSCRIPT RESULT:\nnot found across all strategies")
            combined_errors = " ".join(filter(None, [meta_err_str or "", err1 or "", err2 or "", err3 or ""])).lower()

            if any(k in combined_errors for k in ["private video", "video unavailable", "removed", "not available", "sign in if you've been granted access"]):
                raise ValueError("This YouTube video is unavailable, private, or restricted. Please check the URL or upload the video file directly.")
            elif any(k in combined_errors for k in ["bot", "429", "too many requests", "rate limit", "captcha", "blocking"]):
                raise ValueError("YouTube is currently restricting automatic access from cloud servers for this video. Please upload the video file directly.")
            elif any(k in combined_errors for k in ["transcriptsdisabled", "notranscriptfound", "no subtitle"]):
                raise ValueError("This video does not have accessible captions, and audio could not be processed automatically. Please upload the video file directly.")
            elif any(k in combined_errors for k in ["connection", "timed out", "timeout", "network"]):
                raise ValueError("Unable to connect to YouTube servers due to network timeout. Please verify your connection or upload the video file directly.")
            else:
                raise ValueError("This video does not have an accessible transcript. Please upload the video file instead.")

        _safe_log(f"TRANSCRIPT RESULT:\nfound via {strategy_used} ({selected_lang})")
        _safe_log(f"ENTRY COUNT:\n{len(raw_snippets)}")
        sample_snippet = ' '.join(raw_snippets[:3])
        _safe_log(f"FIRST SAMPLE:\n{sample_snippet[:150]}...")

        # 6. Clean transcript
        cleaned_text = cls.clean_transcript(raw_snippets)
        char_count = len(cleaned_text)
        word_count = len(cleaned_text.split())
        _safe_log(f"CLEAN TEXT LENGTH:\n{char_count} characters ({word_count} words)")
        _safe_log("=" * 50 + "\n")

        # 7. Validation before Groq
        if char_count < 20 or word_count < 5:
            raise ValueError("Extracted transcript is insufficient or empty. Please upload the video file instead.")

        meta = {
            "language": selected_lang,
            "is_generated": is_gen,
            "strategy_used": strategy_used,
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
