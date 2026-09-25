import os
import json
import logging
import re
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TEXT_MODELS = [
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "groq/compound",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

DEFAULT_STT_MODELS = [
    "whisper-large-v3-turbo",
    "whisper-large-v3"
]

class GroqService:
    """Centralized AI service powering STUDIORA using the official Groq SDK with automatic multi-model fallback."""

    def __init__(self):
        self.api_key = (settings.GROQ_API_KEY or "").strip()
        
        # Build prioritized list of candidate text models
        primary_text = (settings.GROQ_TEXT_MODEL or "openai/gpt-oss-120b").strip()
        self.candidate_text_models = [primary_text] + [m for m in DEFAULT_TEXT_MODELS if m != primary_text]

        # Build prioritized list of candidate STT models
        primary_stt = (settings.GROQ_STT_MODEL or "whisper-large-v3-turbo").strip()
        self.candidate_stt_models = [primary_stt] + [m for m in DEFAULT_STT_MODELS if m != primary_stt]

        self.client = None

        if self.api_key:
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key)
                logger.info("Groq client initialized with candidate models: %s", self.candidate_text_models)
            except Exception as e:
                logger.error("Failed to initialize Groq client: %s", str(e))
                self.client = None
        else:
            logger.warning("GROQ_API_KEY not configured. Running in educational fallback mode.")

    def _call_chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        response_format: Optional[Dict[str, str]] = None,
        max_tokens: Optional[int] = None
    ) -> Optional[str]:
        """Attempt chat completion across prioritized candidate models until one succeeds."""
        if not self.client:
            return None

        last_error = None
        for model_name in list(self.candidate_text_models):
            try:
                kwargs: Dict[str, Any] = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature
                }
                if response_format:
                    kwargs["response_format"] = response_format
                if max_tokens:
                    kwargs["max_tokens"] = max_tokens

                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                if content and content.strip():
                    # Move working model to front
                    if self.candidate_text_models[0] != model_name:
                        self.candidate_text_models.remove(model_name)
                        self.candidate_text_models.insert(0, model_name)
                    return content
            except Exception as e:
                logger.warning("Groq completion failed with model '%s': %s", model_name, str(e))
                last_error = e
                continue

        logger.error("All Groq text models failed. Last error: %s", str(last_error))
        return None

    def _extract_json(self, raw_response: str) -> Any:
        """Extract and parse clean JSON from markdown code fences or plain text."""
        cleaned = raw_response.strip()
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned, re.IGNORECASE)
        if json_match:
            cleaned = json_match.group(1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start_bracket = min([p for p in [cleaned.find('['), cleaned.find('{')] if p != -1], default=-1)
            end_bracket = max([cleaned.rfind(']'), cleaned.rfind('}')])
            if start_bracket != -1 and end_bracket != -1 and end_bracket > start_bracket:
                candidate = cleaned[start_bracket:end_bracket+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    pass
            logger.error("Failed to parse JSON from AI response: %s", raw_response[:200])
            raise

    def _flatten_json_to_prose(self, data: Any) -> str:
        """Recursively turn dicts/lists into clean human-readable sentences without JSON brackets or keys."""
        if isinstance(data, dict):
            parts = []
            for k, v in data.items():
                k_lower = k.lower()
                if k_lower in ["title", "name", "header"]:
                    parts.append(str(v))
                elif k_lower in ["summary", "description", "content", "explanation", "question", "text"]:
                    parts.append(str(v))
                elif isinstance(v, (dict, list)):
                    parts.append(self._flatten_json_to_prose(v))
                else:
                    parts.append(f"{v}")
            return "\n".join(p for p in parts if p)
        elif isinstance(data, list):
            return "\n".join(self._flatten_json_to_prose(item) for item in data if item)
        elif isinstance(data, str):
            return data
        return str(data)

    def _clean_text_for_quiz(self, text: str) -> str:
        """Strip raw JSON objects, markdown fences, and serialized dictionaries from text."""
        if not text:
            return ""
        # Remove code fences
        cleaned = re.sub(r'```(?:json)?[\s\S]*?```', ' ', text)
        trimmed = cleaned.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
            try:
                data = json.loads(trimmed)
                return self._flatten_json_to_prose(data)
            except Exception:
                pass
        return cleaned

    def _clean_option_text(self, val: Any) -> str:
        """Extract clean plain text from an option value that might be a dict, list, or JSON string."""
        if isinstance(val, (dict, list)):
            val = self._flatten_json_to_prose(val)
        val = str(val or "").strip()
        if (val.startswith("{") and val.endswith("}")) or (val.startswith("[") and val.endswith("]")):
            try:
                parsed = json.loads(val)
                val = self._flatten_json_to_prose(parsed)
            except Exception:
                val = re.sub(r'["{}\[\]]', '', val)
        # Strip leading letters like "A. ", "A) ", "(A) "
        val = re.sub(r'^\(?[A-Da-d]\)?[\.\:\-\s]+', '', val).strip()
        # Strip leftover JSON artifacts
        val = re.sub(r'^[{"\'\[\]\s]+', '', val)
        val = re.sub(r'[\}"\'\]\s]+$', '', val)
        return val if val else "Standard principle defined in the study material."

    def _normalize_quiz_questions(self, raw_data: Any, target_count: int) -> List[Dict[str, Any]]:
        """
        Normalize and validate generated quiz questions:
        - id: int (1, 2, 3...)
        - question: clean readable string
        - options: 4 distinct items [{"id": "A", "text": "plain text"}, ...]
        - correct_answer: "A" | "B" | "C" | "D"
        - explanation: clean readable string
        """
        if isinstance(raw_data, dict):
            for key in ["questions", "quiz", "data", "items"]:
                if key in raw_data and isinstance(raw_data[key], list):
                    raw_data = raw_data[key]
                    break
            if isinstance(raw_data, dict):
                raw_data = list(raw_data.values())

        if not isinstance(raw_data, list):
            return []

        clean_questions = []
        for item in raw_data:
            if not isinstance(item, dict):
                continue

            # Extract question text
            q_text = str(item.get("question") or item.get("prompt") or item.get("title") or "").strip()
            # If question text contains serialized JSON
            if (q_text.startswith("{") and q_text.endswith("}")) or (q_text.startswith("[") and q_text.endswith("]")):
                try:
                    q_text = self._flatten_json_to_prose(json.loads(q_text))
                except Exception:
                    q_text = re.sub(r'["{}\[\]]', '', q_text)
            q_text = re.sub(r'^[{"\'\[\]\s]+', '', q_text)
            q_text = re.sub(r'[\}"\'\]\s]+$', '', q_text).strip()
            if not q_text or len(q_text) < 5:
                continue

            # Extract options
            raw_options = item.get("options") or item.get("choices") or []
            normalized_options = []

            if isinstance(raw_options, dict):
                for letter in ["A", "B", "C", "D"]:
                    val = raw_options.get(letter) or raw_options.get(letter.lower()) or ""
                    normalized_options.append({"id": letter, "text": self._clean_option_text(val)})
            elif isinstance(raw_options, list):
                for opt_idx, opt in enumerate(raw_options[:4]):
                    letter = ["A", "B", "C", "D"][opt_idx]
                    if isinstance(opt, dict):
                        opt_text = opt.get("text") or opt.get("value") or opt.get("label") or opt.get("content") or ""
                        opt_id = str(opt.get("id") or letter).strip().upper()
                        if opt_id not in ["A", "B", "C", "D"]:
                            opt_id = letter
                        normalized_options.append({"id": opt_id, "text": self._clean_option_text(opt_text)})
                    else:
                        normalized_options.append({"id": letter, "text": self._clean_option_text(opt)})

            # Ensure we have 4 options labeled A, B, C, D
            existing_letters = [o["id"] for o in normalized_options]
            for letter in ["A", "B", "C", "D"]:
                if letter not in existing_letters:
                    normalized_options.append({
                        "id": letter,
                        "text": f"Alternative concept related to the topic ({letter})"
                    })

            # Sort by A, B, C, D and ensure exactly 4
            letter_order = {"A": 0, "B": 1, "C": 2, "D": 3}
            normalized_options = sorted(normalized_options[:4], key=lambda x: letter_order.get(x["id"], 9))
            for i, opt in enumerate(normalized_options):
                opt["id"] = ["A", "B", "C", "D"][i]

            # Correct answer validation
            raw_correct = str(item.get("correct_answer") or item.get("answer") or "").strip()
            matched_letter = None
            if len(raw_correct) == 1 and raw_correct.upper() in ["A", "B", "C", "D"]:
                matched_letter = raw_correct.upper()
            else:
                for opt in normalized_options:
                    if raw_correct and (raw_correct.lower() == opt["text"].lower() or raw_correct.lower() in opt["text"].lower()):
                        matched_letter = opt["id"]
                        break
                    elif opt["text"] and opt["text"].lower() in raw_correct.lower():
                        matched_letter = opt["id"]
                        break

            # If correct_answer does not exist in options (e.g. "E" or invalid), question is invalid and discarded
            if not matched_letter or matched_letter not in ["A", "B", "C", "D"]:
                logger.warning("Skipping invalid question: correct_answer '%s' does not match options A-D.", raw_correct)
                continue

            # Explanation normalization
            expl = str(item.get("explanation") or "").strip()
            expl = re.sub(r'^[{"\'\[\]\s]+', '', expl)
            expl = re.sub(r'[\}"\'\]\s]+$', '', expl).strip()
            if not expl or len(expl) < 10:
                correct_text = next((o["text"] for o in normalized_options if o["id"] == matched_letter), "the selected answer")
                expl = f"'{matched_letter}. {correct_text}' is the correct answer according to the study material."

            clean_questions.append({
                "id": len(clean_questions) + 1,
                "question": q_text,
                "options": normalized_options,
                "correct_answer": matched_letter,
                "explanation": expl
            })

            if len(clean_questions) >= target_count:
                break

        return clean_questions

    def generate_notes(self, text: str, title_hint: Optional[str] = None) -> Dict[str, Any]:
        """Generate structured study notes from document text using Groq with multi-model fallback."""
        truncated_text = text[:18000]

        system_prompt = (
            "You are an expert academic educator and pedagogical specialist for Studiora. "
            "Your goal is to turn study material into clear, simple, educational, and structured notes. "
            "The notes must be accurate to the source material, easy to revise, and logically organized. "
            "You MUST respond ONLY with a valid JSON object matching this exact schema:\n"
            "{\n"
            '  "title": "Clear concise title",\n'
            '  "summary": "2-3 sentence executive summary explaining the main topic and purpose",\n'
            '  "key_points": ["Key takeaway 1", "Key takeaway 2", "Key takeaway 3"],\n'
            '  "sections": [\n'
            '    {\n'
            '      "title": "Section Title",\n'
            '      "content": "Detailed educational paragraph explanation...",\n'
            '      "bullet_points": ["Important sub-point 1", "Important sub-point 2"],\n'
            '      "examples": ["Illustrative example or practical application"]\n'
            '    }\n'
            '  ],\n'
            '  "important_terms": [\n'
            '    {"term": "Term Name", "definition": "Clear concise academic definition"}\n'
            '  ],\n'
            '  "revision_points": ["Quick recall question or summary bullet 1", "..."]\n'
            "}"
        )

        user_prompt = f"Study Material Content:\n\n{truncated_text}"
        if title_hint:
            user_prompt = f"Topic/Title: {title_hint}\n\n" + user_prompt

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        raw_json = self._call_chat_completion(messages, temperature=0.3, response_format={"type": "json_object"})
        if raw_json:
            try:
                parsed = self._extract_json(raw_json)
                if isinstance(parsed, dict) and "title" in parsed:
                    return parsed
            except Exception as e:
                logger.warning("Failed to parse AI notes JSON: %s. Using fallback.", str(e))

        return self._generate_fallback_notes(text, title_hint)

    def generate_quiz(self, text: str, number_of_questions: int = 5) -> List[Dict[str, Any]]:
        """
        Generate multiple-choice questions (5, 10, or 15) strictly based on the text.
        Guarantees clean, human-readable plain text without any JSON or serialized structures.
        """
        number_of_questions = min(max(int(number_of_questions), 5), 15)
        clean_text = self._clean_text_for_quiz(text)
        truncated_text = clean_text[:18000]

        system_prompt = (
            f"You are an academic assessment specialist for Studiora. "
            f"Generate a challenging yet fair {number_of_questions}-question multiple-choice quiz based SOLELY on the provided text. "
            "Each question must have 4 distinct, plausible options (labeled A, B, C, D) with exactly ONE unambiguously correct answer. "
            "All questions and options must be natural, readable English sentences. DO NOT include raw code, JSON keys, or curly braces. "
            "Provide an educational explanation detailing why the correct answer is right according to the material. "
            "Output ONLY a valid JSON object matching this schema:\n"
            "{\n"
            '  "questions": [\n'
            "    {\n"
            '      "id": 1,\n'
            '      "question": "Clear question text?",\n'
            '      "options": [\n'
            '        {"id": "A", "text": "Option A text"},\n'
            '        {"id": "B", "text": "Option B text"},\n'
            '        {"id": "C", "text": "Option C text"},\n'
            '        {"id": "D", "text": "Option D text"}\n'
            "      ],\n"
            '      "correct_answer": "A",\n'
            '      "explanation": "Detailed explanation grounded in the text."\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        user_prompt = f"Generate {number_of_questions} multiple-choice questions based on this study content:\n\n{truncated_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        raw_json = self._call_chat_completion(messages, temperature=0.2, response_format={"type": "json_object"})
        if raw_json:
            try:
                parsed = self._extract_json(raw_json)
                normalized = self._normalize_quiz_questions(parsed, number_of_questions)
                if len(normalized) >= min(3, number_of_questions):
                    # Pad if slightly under
                    if len(normalized) < number_of_questions:
                        extra = self._generate_fallback_quiz(clean_text, number_of_questions - len(normalized))
                        for ex in extra:
                            ex["id"] = len(normalized) + 1
                            normalized.append(ex)
                    return normalized[:number_of_questions]
            except Exception as e:
                logger.warning("Failed to parse AI quiz JSON: %s. Using fallback quiz generator.", str(e))

        return self._generate_fallback_quiz(clean_text, number_of_questions)

    def generate_explanation(self, question: str, user_answer: str, correct_answer: str, context: str) -> str:
        """Generate pedagogical explanation for a missed question."""
        system_prompt = (
            "You are a supportive tutor for Studiora. Explain concisely why the user's answer was incorrect "
            "and why the correct answer is accurate according to the learning material."
        )
        prompt = (
            f"Question: {question}\n"
            f"User Answer: {user_answer}\n"
            f"Correct Answer: {correct_answer}\n"
            f"Context:\n{context[:2000]}"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        result = self._call_chat_completion(messages, temperature=0.3, max_tokens=250)
        if result and result.strip():
            return result.strip()

        return f"'{correct_answer}' is the correct answer according to the study material. It directly fulfills the core definition and context presented in the lesson."

    def transcribe_audio(self, audio_file_path: str) -> str:
        """Transcribe an audio file using Groq Whisper Speech-to-Text model with automatic model fallback."""
        if not os.path.exists(audio_file_path):
            raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

        if not self.client:
            raise ValueError("GROQ_API_KEY is required to transcribe audio using the Groq Whisper model.")

        last_error = None
        for model_name in list(self.candidate_stt_models):
            try:
                with open(audio_file_path, "rb") as file_handle:
                    transcription = self.client.audio.transcriptions.create(
                        file=(os.path.basename(audio_file_path), file_handle.read()),
                        model=model_name,
                        response_format="text"
                    )
                    text = transcription if isinstance(transcription, str) else getattr(transcription, "text", str(transcription))
                    if text and text.strip():
                        if self.candidate_stt_models[0] != model_name:
                            self.candidate_stt_models.remove(model_name)
                            self.candidate_stt_models.insert(0, model_name)
                        return text.strip()
            except Exception as e:
                logger.warning("Groq STT failed with model '%s': %s", model_name, str(e))
                last_error = e
                continue

        raise RuntimeError(f"Audio transcription failed with Groq STT models ({', '.join(self.candidate_stt_models)}): {str(last_error)}")

    def _generate_fallback_notes(self, text: str, title_hint: Optional[str] = None) -> Dict[str, Any]:
        """Intelligent structured note generator when running offline or during API fallback."""
        clean_text = self._clean_text_for_quiz(text)
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        title = title_hint or (lines[0] if lines else "Study Material Notes")
        if len(title) > 60:
            title = title[:57] + "..."

        sentences = [s.strip() for s in re.split(r'[\.\?\!]+', clean_text) if len(s.strip()) > 20]
        summary = " ".join(sentences[:3]) if sentences else "Comprehensive study notes extracted from the provided material."

        key_points = sentences[1:5] if len(sentences) >= 5 else [
            "Core conceptual definitions and principles introduced in the material.",
            "Important methodologies, processes, and structured workflows.",
            "Practical use cases and analytical review questions for mastery."
        ]

        sections = []
        chunk_size = max(1, len(sentences) // 3)
        for i in range(min(3, max(1, len(sentences)))):
            sec_sentences = sentences[i*chunk_size : (i+1)*chunk_size]
            if not sec_sentences:
                continue
            sec_title = f"Key Concept {i+1}: " + " ".join(sec_sentences[0].split()[:5])
            sections.append({
                "title": sec_title,
                "content": " ".join(sec_sentences[:3]),
                "bullet_points": [s for s in sec_sentences[1:4] if len(s) > 10],
                "examples": [f"Practical application illustrating {sec_title.lower()}."]
            })

        if not sections:
            sections = [{
                "title": "Foundational Overview",
                "content": summary,
                "bullet_points": key_points,
                "examples": ["Real-world application across practical domain problem-solving."]
            }]

        words = re.findall(r'\b[A-Z][a-zA-Z]{3,}\b', clean_text)
        unique_terms = list(dict.fromkeys(words))[:4]
        important_terms = []
        for t in unique_terms:
            important_terms.append({
                "term": t,
                "definition": f"Key educational concept highlighted in the text concerning {t.lower()} principles."
            })
        if not important_terms:
            important_terms = [
                {"term": "Core Concept", "definition": "Fundamental principle governing this subject area."},
                {"term": "Methodology", "definition": "Structured analytical workflow utilized for problem analysis."}
            ]

        revision_points = [
            f"Review the primary distinction between the core sections of {title}.",
            "Practice recalling the central definitions and vocabulary terms.",
            "Test comprehension by explaining the main concept to a peer without notes."
        ]

        return {
            "title": title,
            "summary": summary,
            "key_points": key_points,
            "sections": sections,
            "important_terms": important_terms,
            "revision_points": revision_points
        }

    def _generate_fallback_quiz(self, text: str, count: int) -> List[Dict[str, Any]]:
        """Intelligent fallback quiz generator that guarantees 100% clean, human-readable questions and options."""
        clean_text = self._clean_text_for_quiz(text)
        sanitized = re.sub(r'[\{\}\[\]"\'\:\;\\_]+', ' ', clean_text)
        raw_sentences = [s.strip() for s in re.split(r'[\n\.\?\!]+', sanitized) if len(s.strip().split()) >= 4]
        sentences = [s for s in raw_sentences if not any(c in s for c in ['{', '}', '[', ']', '<', '>'])]

        questions = []
        for i in range(count):
            if sentences:
                base_sentence = sentences[i % len(sentences)]
                words = base_sentence.split()
                topic_phrase = " ".join(words[:min(5, len(words))])
            else:
                base_sentence = "The fundamental principles and operational methods established in the study curriculum."
                topic_phrase = f"Study Topic {i+1}"

            q_text = f"According to the study material, which statement accurately reflects the concept of {topic_phrase}?"
            opt_a = base_sentence
            opt_b = f"It operates independently with no direct connection to {topic_phrase}."
            opt_c = f"It serves solely as an auxiliary variable rather than a core principle of {topic_phrase}."
            opt_d = f"It directly contradicts the verified findings documented in the material."

            questions.append({
                "id": i + 1,
                "question": q_text,
                "options": [
                    {"id": "A", "text": opt_a},
                    {"id": "B", "text": opt_b},
                    {"id": "C", "text": opt_c},
                    {"id": "D", "text": opt_d}
                ],
                "correct_answer": "A",
                "explanation": f"Based on the provided lesson text, '{opt_a}' is the verified correct definition and principle."
            })
        return questions

    def generate_test_paper(self, text: str, title_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a comprehensive 25-mark test paper (exactly 20 questions in 4 sections):
        - Section A: 5 MCQs (1 mark each = 5 marks)
        - Section B: 5 True/False (1 mark each = 5 marks)
        - Section C: 5 Fill in the blanks (1 mark each = 5 marks)
        - Section D: 5 Question Answers (2 marks each = 10 marks)
        Total = 20 questions, 25 marks.
        """
        clean_text = self._clean_text_for_quiz(text)
        truncated_text = clean_text[:18000]

        system_prompt = (
            "You are an expert academic curriculum assessment designer for Studiora. "
            "Generate a rigorous, high-quality 25-mark test paper strictly based on the provided study material. "
            "The test MUST contain exactly 20 questions across 4 distinct sections:\n\n"
            "SECTION A — MCQs: 5 multiple-choice questions (ids 1 to 5). Each has 4 plausible options (A, B, C, D), exactly one unambiguously correct answer, 1 mark, and clear explanation.\n"
            "SECTION B — TRUE / FALSE: 5 statements (ids 6 to 10). Each has correct_answer as either 'True' or 'False', 1 mark, and explanation.\n"
            "SECTION C — FILL IN THE BLANKS: 5 sentences with a blank indicated by '_______' (ids 11 to 15). Each has correct_answer (single word or concise phrase), accepted_answers (list of acceptable variants), 1 mark, and explanation.\n"
            "SECTION D — QUESTION ANSWERS: 5 conceptual questions (ids 16 to 20). Each has model_answer (complete 2-mark standard response), important_keywords (list of essential terms/concepts), marking_guidance (guidelines for awarding 2, 1, or 0 marks), and marks: 2.\n\n"
            "TOTAL: exactly 20 questions, exactly 25 marks.\n"
            "All questions must be human-readable, educational, and grounded ONLY in the source text.\n"
            "Respond ONLY with a valid JSON object matching this schema:\n"
            "{\n"
            '  "title": "Topic or Unit Name Test",\n'
            '  "total_questions": 20,\n'
            '  "total_marks": 25,\n'
            '  "duration_minutes": 30,\n'
            '  "section_a": [\n'
            '    {\n'
            '      "id": 1,\n'
            '      "question": "Question text?",\n'
            '      "options": [\n'
            '        {"id": "A", "text": "Option A"},\n'
            '        {"id": "B", "text": "Option B"},\n'
            '        {"id": "C", "text": "Option C"},\n'
            '        {"id": "D", "text": "Option D"}\n'
            '      ],\n'
            '      "correct_answer": "A",\n'
            '      "marks": 1,\n'
            '      "explanation": "Why A is correct according to the material."\n'
            '    }\n'
            '  ],\n'
            '  "section_b": [\n'
            '    {\n'
            '      "id": 6,\n'
            '      "question": "Statement to evaluate as True or False.",\n'
            '      "correct_answer": "True",\n'
            '      "marks": 1,\n'
            '      "explanation": "Explanation of why the statement is True/False."\n'
            '    }\n'
            '  ],\n'
            '  "section_c": [\n'
            '    {\n'
            '      "id": 11,\n'
            '      "question": "The primary substance produced during this reaction is _______.",\n'
            '      "correct_answer": "glucose",\n'
            '      "accepted_answers": ["glucose", "sugar"],\n'
            '      "marks": 1,\n'
            '      "explanation": "Explanation for the blank."\n'
            '    }\n'
            '  ],\n'
            '  "section_d": [\n'
            '    {\n'
            '      "id": 16,\n'
            '      "question": "Explain the role of chlorophyll in photosynthesis.",\n'
            '      "model_answer": "Chlorophyll is the green pigment in chloroplasts that absorbs sunlight energy required to convert carbon dioxide and water into glucose and oxygen.",\n'
            '      "important_keywords": ["chlorophyll", "sunlight", "chloroplasts", "glucose", "energy"],\n'
            '      "marking_guidance": "Award 2 marks for explaining pigment function and light absorption; 1 mark if partial; 0 marks if irrelevant.",\n'
            '      "marks": 2\n'
            '    }\n'
            '  ]\n'
            "}"
        )

        user_prompt = f"Study Material Content:\n\n{truncated_text}"
        if title_hint:
            user_prompt = f"Subject / Topic: {title_hint}\n\n" + user_prompt

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        raw_json = self._call_chat_completion(
            messages,
            temperature=0.25,
            response_format={"type": "json_object"},
            max_tokens=4000
        )

        if raw_json:
            try:
                parsed = self._extract_json(raw_json)
                if isinstance(parsed, dict):
                    normalized = self._normalize_test_paper(parsed, text, title_hint)
                    if normalized:
                        return normalized
            except Exception as e:
                logger.warning("Failed to parse test paper JSON: %s. Using intelligent generator.", str(e))

        return self._generate_fallback_test_paper(text, title_hint)

    def evaluate_question_answers(self, eval_requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Evaluate student responses for Section D (2-mark conceptual questions).
        Each item in eval_requests:
        {
            "question_id": 16,
            "question": "...",
            "student_answer": "...",
            "model_answer": "...",
            "important_keywords": ["..."],
            "marking_guidance": "..."
        }
        """
        if not eval_requests:
            return []

        evaluations = {}
        pending_requests = []
        for req in eval_requests:
            q_id = req["question_id"]
            stud_ans = (req.get("student_answer") or "").strip()
            if not stud_ans:
                evaluations[q_id] = {
                    "question_id": q_id,
                    "marks": 0,
                    "max_marks": 2,
                    "evaluation": "Not attempted",
                    "matched_keywords": [],
                    "missing_keywords": req.get("important_keywords", []),
                    "feedback": "Question was not attempted."
                }
            else:
                pending_requests.append(req)

        if not pending_requests:
            return list(evaluations.values())

        system_prompt = (
            "You are an academic examiner for Studiora evaluating student answers for 2-mark conceptual questions.\n"
            "Marking criteria:\n"
            "- 2 MARKS: Substantially correct, relevant, covers key concepts/keywords, suitable explanation.\n"
            "- 1 MARK: Partially correct, misses important keywords/explanation, or has minor conceptual errors.\n"
            "- 0 MARKS: Incorrect, irrelevant, or fails to answer the question.\n"
            "Evaluate semantic meaning fairly. Do NOT penalize for alternate phrasing or concise answers if concepts are correct.\n"
            "Respond ONLY with a JSON object containing an 'evaluations' array matching this schema:\n"
            "{\n"
            '  "evaluations": [\n'
            "    {\n"
            '      "question_id": 16,\n'
            '      "marks": 2,\n'
            '      "max_marks": 2,\n'
            '      "evaluation": "Correct and sufficiently explained",\n'
            '      "matched_keywords": ["..."],\n'
            '      "missing_keywords": ["..."],\n'
            '      "feedback": "Educational explanation of marks awarded..."\n'
            "    }\n"
            "  ]\n"
            "}"
        )

        user_content = json.dumps(pending_requests, indent=2)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please evaluate these student question answers:\n\n{user_content}"}
        ]

        raw_json = self._call_chat_completion(
            messages,
            temperature=0.2,
            response_format={"type": "json_object"},
            max_tokens=2000
        )

        if raw_json:
            try:
                parsed = self._extract_json(raw_json)
                eval_list = parsed.get("evaluations") if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else None)
                if isinstance(eval_list, list):
                    for item in eval_list:
                        q_id = item.get("question_id")
                        raw_marks = item.get("marks", 0)
                        try:
                            marks = int(raw_marks)
                        except (ValueError, TypeError):
                            marks = 0
                        marks = max(0, min(2, marks))
                        evaluations[q_id] = {
                            "question_id": q_id,
                            "marks": marks,
                            "max_marks": 2,
                            "evaluation": item.get("evaluation") or ("Correct and sufficiently explained" if marks == 2 else ("Partially correct" if marks == 1 else "Incorrect")),
                            "matched_keywords": item.get("matched_keywords") or [],
                            "missing_keywords": item.get("missing_keywords") or [],
                            "feedback": item.get("feedback") or ("Answer is well explained and covers key concepts." if marks == 2 else "Answer lacks sufficient conceptual detail.")
                        }
            except Exception as e:
                logger.warning("Failed to parse AI evaluation response: %s", str(e))

        # Heuristic fallback for any pending items not resolved by AI
        for req in pending_requests:
            q_id = req["question_id"]
            if q_id not in evaluations:
                evaluations[q_id] = self._fallback_evaluate_single_qa(req)

        return [evaluations[req["question_id"]] for req in eval_requests if req["question_id"] in evaluations]

    def _fallback_evaluate_single_qa(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Semantic fallback grading for Section D question if AI call is unavailable."""
        q_id = req["question_id"]
        stud_ans = (req.get("student_answer") or "").strip().lower()
        keywords = [k.lower() for k in req.get("important_keywords", []) if k]

        if not stud_ans or len(stud_ans) < 3:
            return {
                "question_id": q_id,
                "marks": 0,
                "max_marks": 2,
                "evaluation": "Not attempted",
                "matched_keywords": [],
                "missing_keywords": req.get("important_keywords", []),
                "feedback": "Answer was empty or not attempted."
            }

        matched = [k for k in keywords if k in stud_ans]
        missing = [k for k in keywords if k not in stud_ans]

        ratio = len(matched) / max(1, len(keywords)) if keywords else 0.5
        words_count = len(stud_ans.split())

        if (ratio >= 0.6 and words_count >= 8) or ratio >= 0.8:
            marks = 2
            evaluation = "Correct and sufficiently explained"
            feedback = f"Good answer covering essential concepts such as {', '.join(matched[:3])}."
        elif ratio >= 0.3 or words_count >= 5:
            marks = 1
            evaluation = "Partially correct"
            feedback = f"Answer touches upon the topic but misses important concepts: {', '.join(missing[:3]) if missing else 'more detailed explanation'}."
        else:
            marks = 0
            evaluation = "Incorrect"
            feedback = "Answer does not sufficiently explain the core concepts required."

        return {
            "question_id": q_id,
            "marks": marks,
            "max_marks": 2,
            "evaluation": evaluation,
            "matched_keywords": matched,
            "missing_keywords": missing,
            "feedback": feedback
        }

    def _normalize_test_paper(self, parsed: Dict[str, Any], text: str, title_hint: Optional[str] = None) -> Dict[str, Any]:
        """Validate and normalize all 4 sections of the test paper to ensure exact 20 questions and 25 marks."""
        fallback = self._generate_fallback_test_paper(text, title_hint)
        title = str(parsed.get("title") or title_hint or "25-Mark Comprehensive Test").strip()

        # 1. Section A: 5 MCQs (ids 1-5, 1 mark each)
        raw_a = parsed.get("section_a") or []
        clean_a = []
        if isinstance(raw_a, list):
            clean_a = self._normalize_quiz_questions(raw_a, target_count=5)
            # Re-index ids 1 to 5 and add marks = 1
            for idx, q in enumerate(clean_a):
                q["id"] = idx + 1
                q["marks"] = 1
        # Fill missing from fallback if needed
        while len(clean_a) < 5:
            idx = len(clean_a)
            fb_item = fallback["section_a"][idx]
            clean_a.append(fb_item)
        clean_a = clean_a[:5]

        # 2. Section B: 5 True/False (ids 6-10, 1 mark each)
        raw_b = parsed.get("section_b") or []
        clean_b = []
        if isinstance(raw_b, list):
            for item in raw_b:
                if not isinstance(item, dict):
                    continue
                q_text = str(item.get("question") or item.get("statement") or "").strip()
                raw_ans = str(item.get("correct_answer") or item.get("answer") or "").strip().lower()
                correct_ans = "True" if "true" in raw_ans or raw_ans == "t" else "False"
                expl = str(item.get("explanation") or f"This statement is {correct_ans} according to the text.").strip()
                if q_text and len(q_text) > 10:
                    clean_b.append({
                        "id": 6 + len(clean_b),
                        "question": q_text,
                        "correct_answer": correct_ans,
                        "marks": 1,
                        "explanation": expl
                    })
                if len(clean_b) >= 5:
                    break
        while len(clean_b) < 5:
            idx = len(clean_b)
            clean_b.append(fallback["section_b"][idx])
        clean_b = clean_b[:5]

        # 3. Section C: 5 Fill in the Blanks (ids 11-15, 1 mark each)
        raw_c = parsed.get("section_c") or []
        clean_c = []
        if isinstance(raw_c, list):
            for item in raw_c:
                if not isinstance(item, dict):
                    continue
                q_text = str(item.get("question") or item.get("sentence") or "").strip()
                raw_ans = str(item.get("correct_answer") or item.get("blank") or "").strip()
                raw_accepted = item.get("accepted_answers") or [raw_ans]
                accepted_answers = [str(a).strip().lower() for a in raw_accepted if str(a).strip()]
                if raw_ans.lower() not in accepted_answers:
                    accepted_answers.insert(0, raw_ans.lower())
                expl = str(item.get("explanation") or f"'{raw_ans}' is the correct answer according to the lesson.").strip()
                if q_text and len(q_text) > 10 and raw_ans:
                    if "_______" not in q_text and "_" not in q_text:
                        q_text += " _______."
                    clean_c.append({
                        "id": 11 + len(clean_c),
                        "question": q_text,
                        "correct_answer": raw_ans,
                        "accepted_answers": accepted_answers,
                        "marks": 1,
                        "explanation": expl
                    })
                if len(clean_c) >= 5:
                    break
        while len(clean_c) < 5:
            idx = len(clean_c)
            clean_c.append(fallback["section_c"][idx])
        clean_c = clean_c[:5]

        # 4. Section D: 5 Question Answers (ids 16-20, 2 marks each)
        raw_d = parsed.get("section_d") or []
        clean_d = []
        if isinstance(raw_d, list):
            for item in raw_d:
                if not isinstance(item, dict):
                    continue
                q_text = str(item.get("question") or "").strip()
                model_ans = str(item.get("model_answer") or item.get("answer") or "").strip()
                keywords = item.get("important_keywords") or item.get("keywords") or []
                if isinstance(keywords, str):
                    keywords = [k.strip() for k in keywords.split(",") if k.strip()]
                elif isinstance(keywords, list):
                    keywords = [str(k).strip() for k in keywords if str(k).strip()]
                marking_guide = str(item.get("marking_guidance") or "Award 2 marks for full explanation covering keywords; 1 mark for partial understanding.").strip()
                if q_text and len(q_text) > 10 and model_ans:
                    clean_d.append({
                        "id": 16 + len(clean_d),
                        "question": q_text,
                        "model_answer": model_ans,
                        "important_keywords": keywords,
                        "marking_guidance": marking_guide,
                        "marks": 2
                    })
                if len(clean_d) >= 5:
                    break
        while len(clean_d) < 5:
            idx = len(clean_d)
            clean_d.append(fallback["section_d"][idx])
        clean_d = clean_d[:5]

        return {
            "title": title,
            "total_questions": 20,
            "total_marks": 25,
            "duration_minutes": 30,
            "section_a": clean_a,
            "section_b": clean_b,
            "section_c": clean_c,
            "section_d": clean_d
        }

    def _generate_fallback_test_paper(self, text: str, title_hint: Optional[str] = None) -> Dict[str, Any]:
        """Robust fallback generator guaranteeing exact 20 questions and 25 marks across all 4 sections."""
        clean_text = self._clean_text_for_quiz(text)
        sanitized = re.sub(r'[\{\}\[\]"\'\:\;\\_]+', ' ', clean_text)
        raw_sentences = [s.strip() for s in re.split(r'[\n\.\?\!]+', sanitized) if len(s.strip().split()) >= 4]
        sentences = [s for s in raw_sentences if not any(c in s for c in ['{', '}', '[', ']', '<', '>'])]
        if not sentences:
            sentences = [
                "The core principles establish the fundamental foundation of this subject.",
                "Photosynthesis allows green plants to convert solar radiation into chemical energy.",
                "Cellular respiration breaks down nutrient molecules to produce adenosine triphosphate.",
                "Enzymes serve as biological catalysts that accelerate chemical reactions.",
                "Cell membranes regulate the movement of substances in and out of the cell.",
                "DNA stores genetic instructions used in the growth and development of organisms.",
                "Active transport requires cellular energy to move ions against concentration gradients.",
                "Homeostasis maintains steady internal conditions essential for organism survival."
            ]

        title = title_hint or "25-Mark Comprehensive Test"

        # Section A: 5 MCQs
        fb_mcqs = self._generate_fallback_quiz(text, count=5)
        for i, q in enumerate(fb_mcqs):
            q["id"] = i + 1
            q["marks"] = 1

        # Section B: 5 True/False
        section_b = []
        for i in range(5):
            s = sentences[i % len(sentences)]
            words = s.split()
            concept = " ".join(words[:min(4, len(words))])
            is_true = (i % 2 == 0)
            if is_true:
                statement = f"According to the study material, {s.lower()}"
                expl = f"True: The study material states that '{s}'."
            else:
                statement = f"The study material states that {concept} has no functional significance in the system."
                expl = f"False: The study material affirms the primary importance of {concept}."
            section_b.append({
                "id": 6 + i,
                "question": statement,
                "correct_answer": "True" if is_true else "False",
                "marks": 1,
                "explanation": expl
            })

        # Section C: 5 Fill in the Blanks
        section_c = []
        for i in range(5):
            s = sentences[(i + 2) % len(sentences)]
            words = [w for w in s.split() if len(w) > 4]
            target_word = words[0] if words else "energy"
            blank_q = s.replace(target_word, "_______", 1)
            if "_______" not in blank_q:
                blank_q = f"In this system, the primary factor is _______ ({s[:40]})."
            section_c.append({
                "id": 11 + i,
                "question": blank_q,
                "correct_answer": target_word,
                "accepted_answers": [target_word.lower(), target_word.lower().strip(".,;:")] ,
                "marks": 1,
                "explanation": f"'{target_word}' is the correct term based on the provided material."
            })

        # Section D: 5 Question Answers (2 marks each)
        section_d = []
        for i in range(5):
            s = sentences[(i + 4) % len(sentences)]
            words = [w for w in s.split() if len(w) > 3]
            topic = " ".join(words[:min(3, len(words))])
            keywords = words[:min(4, len(words))]
            section_d.append({
                "id": 16 + i,
                "question": f"Explain the principle and significance of {topic} as described in the study material.",
                "model_answer": f"{s}. It serves as an essential concept ensuring optimal functionality and proper understanding of the topic.",
                "important_keywords": keywords,
                "marking_guidance": "Award 2 marks for a complete explanation covering key terms; 1 mark for partial explanation; 0 marks if irrelevant.",
                "marks": 2
            })

        return {
            "title": title,
            "total_questions": 20,
            "total_marks": 25,
            "duration_minutes": 30,
            "section_a": fb_mcqs,
            "section_b": section_b,
            "section_c": section_c,
            "section_d": section_d
        }

# Singleton instance
groq_service = GroqService()
