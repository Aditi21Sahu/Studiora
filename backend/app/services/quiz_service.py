import json
import logging
import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.material import Material
from app.models.note import Note
from app.models.quiz import Quiz
from app.models.attempt import QuizAttempt
from app.models.activity import Activity
from app.ai.groq_service import groq_service

logger = logging.getLogger(__name__)

def _extract_clean_text_from_note(note: Note) -> str:
    """Extract clean, formatted human-readable text from a Note object without raw JSON strings."""
    parts = []
    if note.title:
        parts.append(f"# {note.title}")
    if note.summary:
        parts.append(f"Summary: {note.summary}")

    if note.key_points:
        try:
            kp = json.loads(note.key_points) if isinstance(note.key_points, str) else note.key_points
            if isinstance(kp, list):
                kp_lines = [f"- {p}" for p in kp if isinstance(p, str) and p.strip()]
                if kp_lines:
                    parts.append("Key Points:\n" + "\n".join(kp_lines))
            elif isinstance(kp, str) and kp.strip():
                parts.append(f"Key Points:\n{kp}")
        except Exception:
            pass

    if note.sections:
        try:
            secs = json.loads(note.sections) if isinstance(note.sections, str) else note.sections
            if isinstance(secs, list):
                sec_blocks = []
                for s in secs:
                    if isinstance(s, dict):
                        title = s.get("title", "")
                        content = s.get("content", "")
                        bullets = s.get("bullet_points", [])
                        examples = s.get("examples", [])
                        block = f"## {title}\n{content}"
                        if bullets and isinstance(bullets, list):
                            block += "\n" + "\n".join(f"- {b}" for b in bullets if b)
                        if examples and isinstance(examples, list):
                            block += "\n" + "\n".join(f"Example: {e}" for e in examples if e)
                        sec_blocks.append(block)
                    elif isinstance(s, str) and s.strip():
                        sec_blocks.append(s)
                if sec_blocks:
                    parts.append("\n\n".join(sec_blocks))
            elif isinstance(secs, str) and secs.strip():
                parts.append(secs)
        except Exception:
            pass

    if note.important_terms:
        try:
            terms = json.loads(note.important_terms) if isinstance(note.important_terms, str) else note.important_terms
            if isinstance(terms, list):
                term_lines = []
                for t in terms:
                    if isinstance(t, dict):
                        term_lines.append(f"- {t.get('term', '')}: {t.get('definition', '')}")
                    elif isinstance(t, str):
                        term_lines.append(f"- {t}")
                if term_lines:
                    parts.append("Important Terms:\n" + "\n".join(term_lines))
        except Exception:
            pass

    return "\n\n".join(parts)

def _clean_options_list(raw_options: Any) -> List[Dict[str, str]]:
    cleaned = []
    if isinstance(raw_options, list):
        for idx, opt in enumerate(raw_options[:4]):
            letter = ["A", "B", "C", "D"][idx]
            if isinstance(opt, dict):
                opt_id = str(opt.get("id") or letter).strip().upper()
                opt_text = opt.get("text") or opt.get("value") or opt.get("content") or ""
                if isinstance(opt_text, (dict, list)):
                    opt_text = str(opt_text)
                opt_text = str(opt_text).strip()
                if (opt_text.startswith("{") and opt_text.endswith("}")) or (opt_text.startswith("[") and opt_text.endswith("]")):
                    try:
                        parsed = json.loads(opt_text)
                        if isinstance(parsed, dict):
                            opt_text = " ".join(str(v) for v in parsed.values())
                        elif isinstance(parsed, list):
                            opt_text = " ".join(str(v) for v in parsed)
                    except Exception:
                        import re
                        opt_text = re.sub(r'["{}\[\]]', '', opt_text)
                cleaned.append({"id": opt_id if opt_id in ["A", "B", "C", "D"] else letter, "text": opt_text})
            else:
                cleaned.append({"id": letter, "text": str(opt)})
    return cleaned

class QuizService:
    """Service handling quiz generation, question validation, and interactive scoring."""

    @staticmethod
    def generate_quiz(db: Session, user_id: int, material_id: Optional[int], note_id: Optional[int], question_count: int = 5) -> Quiz:
        source_text = ""
        source_title = "Study Topic"

        if note_id:
            note = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
            if not note:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
            source_title = note.title
            source_text = _extract_clean_text_from_note(note)
            material_id = note.material_id
            # Fallback to underlying material text if note text is empty
            if not source_text.strip() and note.material_id:
                mat = db.query(Material).filter(Material.id == note.material_id, Material.user_id == user_id).first()
                if mat and mat.text_content:
                    source_text = mat.text_content
        elif material_id:
            material = db.query(Material).filter(Material.id == material_id, Material.user_id == user_id).first()
            if not material:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study material not found")
            if material.status == "failed":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=material.text_content or "Study material processing failed")
            source_title = material.title
            source_text = material.text_content or ""
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Either material_id or note_id must be provided")

        if not source_text.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source material does not have sufficient text to generate a quiz")

        count = 5
        if question_count in [5, 10, 15]:
            count = question_count

        try:
            questions = groq_service.generate_quiz(source_text, number_of_questions=count)
            quiz = Quiz(
                user_id=user_id,
                material_id=material_id,
                note_id=note_id,
                title=f"{source_title} Quiz",
                question_count=len(questions),
                questions_json=json.dumps(questions)
            )
            db.add(quiz)
            
            # Record activity
            activity = Activity(
                user_id=user_id,
                activity_type="quiz_generated",
                title="Quiz created",
                description=f"Generated {len(questions)}-question quiz for '{source_title}'"
            )
            db.add(activity)

            db.commit()
            db.refresh(quiz)
            return quiz
        except Exception as e:
            logger.error("Failed to generate quiz: %s", str(e))
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate quiz: {str(e)}")

    @staticmethod
    def get_user_quizzes(db: Session, user_id: int) -> List[Dict[str, Any]]:
        quizzes = db.query(Quiz).filter(Quiz.user_id == user_id).order_by(Quiz.created_at.desc()).all()
        results = []
        for q in quizzes:
            attempts = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == q.id).all()
            best_score = max([a.percentage for a in attempts], default=None)
            total_attempts = len(attempts)
            
            # Parse questions to public form
            try:
                raw_q = json.loads(q.questions_json)
                public_q = [
                    {
                        "id": item.get("id", idx + 1),
                        "question": str(item.get("question", "")),
                        "options": _clean_options_list(item.get("options", []))
                    }
                    for idx, item in enumerate(raw_q)
                ]
            except Exception:
                public_q = []

            results.append({
                "id": q.id,
                "user_id": q.user_id,
                "material_id": q.material_id,
                "note_id": q.note_id,
                "title": q.title,
                "question_count": q.question_count,
                "questions": public_q,
                "created_at": q.created_at,
                "best_score": best_score,
                "total_attempts": total_attempts
            })
        return results

    @staticmethod
    def get_quiz_by_id(db: Session, quiz_id: int, user_id: int, reveal_answers: bool = False) -> Dict[str, Any]:
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.user_id == user_id).first()
        if not quiz:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

        raw_questions = json.loads(quiz.questions_json)
        questions = []
        for idx, item in enumerate(raw_questions):
            opts = _clean_options_list(item.get("options", []))
            q_obj = {
                "id": item.get("id", idx + 1),
                "question": str(item.get("question", "")),
                "options": opts
            }
            if reveal_answers:
                q_obj["correct_answer"] = item.get("correct_answer", "A")
                q_obj["explanation"] = item.get("explanation", "")
            questions.append(q_obj)

        attempts = db.query(QuizAttempt).filter(QuizAttempt.quiz_id == quiz.id).all()
        best_score = max([a.percentage for a in attempts], default=None)

        return {
            "id": quiz.id,
            "user_id": quiz.user_id,
            "material_id": quiz.material_id,
            "note_id": quiz.note_id,
            "title": quiz.title,
            "question_count": quiz.question_count,
            "questions": questions,
            "created_at": quiz.created_at,
            "best_score": best_score,
            "total_attempts": len(attempts)
        }

    @staticmethod
    def check_single_answer(db: Session, quiz_id: int, question_id: int, selected_option: str, user_id: int) -> Dict[str, Any]:
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.user_id == user_id).first()
        if not quiz:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

        questions = json.loads(quiz.questions_json)
        target_q = next((q for q in questions if q["id"] == question_id), None)
        if not target_q:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found in quiz")

        options = _clean_options_list(target_q.get("options", []))
        correct_opt = str(target_q.get("correct_answer", "A")).strip().upper()
        user_opt = selected_option.strip().upper()
        is_correct = (user_opt == correct_opt)

        # Retrieve text representation
        user_text = next((opt["text"] for opt in options if opt["id"].upper() == user_opt), user_opt)
        correct_text = next((opt["text"] for opt in options if opt["id"].upper() == correct_opt), correct_opt)

        return {
            "question_id": question_id,
            "is_correct": is_correct,
            "correct_option": correct_opt,
            "correct_text": correct_text,
            "correct_answer": f"{correct_opt}. {correct_text}",
            "selected_option": user_opt,
            "selected_text": user_text,
            "user_answer": f"{user_opt}. {user_text}",
            "explanation": target_q.get("explanation", "The answer is based directly on the provided study material.")
        }

    @staticmethod
    def submit_attempt(db: Session, quiz_id: int, user_id: int, time_taken_seconds: int, answers: List[Any]) -> QuizAttempt:
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.user_id == user_id).first()
        if not quiz:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")

        # Duplicate submission check (within last 4 seconds for the same user and quiz)
        recent_cutoff = datetime.datetime.utcnow() - datetime.timedelta(seconds=4)
        recent_attempt = (
            db.query(QuizAttempt)
            .filter(
                QuizAttempt.quiz_id == quiz_id,
                QuizAttempt.user_id == user_id,
                QuizAttempt.created_at >= recent_cutoff
            )
            .order_by(QuizAttempt.created_at.desc())
            .first()
        )
        if recent_attempt:
            logger.info("Duplicate quiz submit request detected within 4s window. Returning existing attempt %d.", recent_attempt.id)
            return recent_attempt

        questions = json.loads(quiz.questions_json)
        answers_map = {a.question_id: a.selected_option.strip().upper() for a in answers}

        correct_count = 0
        questions_to_review = []
        attempt_details = []

        for q in questions:
            qid = q["id"]
            options = _clean_options_list(q.get("options", []))
            correct_opt = str(q.get("correct_answer", "A")).strip().upper()
            user_opt = answers_map.get(qid, "")
            is_correct = (user_opt == correct_opt)

            user_text = next((opt["text"] for opt in options if opt["id"].upper() == user_opt), user_opt)
            correct_text = next((opt["text"] for opt in options if opt["id"].upper() == correct_opt), correct_opt)

            detail = {
                "question_id": qid,
                "question": q["question"],
                "question_text": q["question"],
                "options": options,
                "selected_option": user_opt,
                "selected_text": user_text,
                "user_answer": f"{user_opt}. {user_text}" if user_opt else "Unanswered",
                "correct_option": correct_opt,
                "correct_text": correct_text,
                "correct_answer": f"{correct_opt}. {correct_text}",
                "is_correct": is_correct,
                "explanation": q.get("explanation", "")
            }
            attempt_details.append(detail)

            if is_correct:
                correct_count += 1
            else:
                questions_to_review.append(detail)

        total_q = len(questions)
        percentage = round((correct_count / total_q) * 100, 1) if total_q > 0 else 0.0

        attempt = QuizAttempt(
            user_id=user_id,
            quiz_id=quiz.id,
            score=correct_count,
            total_questions=total_q,
            percentage=percentage,
            time_taken_seconds=time_taken_seconds,
            answers_json=json.dumps(attempt_details)
        )
        db.add(attempt)

        # Record activity
        activity = Activity(
            user_id=user_id,
            activity_type="quiz_completed",
            title="Quiz completed",
            description=f"Scored {correct_count}/{total_q} ({percentage}%) on '{quiz.title}'"
        )
        db.add(activity)

        db.commit()
        db.refresh(attempt)
        return attempt

    @staticmethod
    def get_attempt_by_id(db: Session, attempt_id: int, user_id: int) -> Dict[str, Any]:
        attempt = db.query(QuizAttempt).filter(QuizAttempt.id == attempt_id, QuizAttempt.user_id == user_id).first()
        if not attempt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz attempt not found")

        quiz = db.query(Quiz).filter(Quiz.id == attempt.quiz_id).first()
        details = json.loads(attempt.answers_json)
        questions_to_review = [d for d in details if not d.get("is_correct", False)]

        return {
            "id": attempt.id,
            "quiz_id": attempt.quiz_id,
            "quiz_title": quiz.title if quiz else "Quiz",
            "score": attempt.score,
            "total_questions": attempt.total_questions,
            "percentage": attempt.percentage,
            "time_taken_seconds": attempt.time_taken_seconds,
            "questions_to_review": questions_to_review,
            "answers": details,
            "all_answers": details,
            "created_at": attempt.created_at
        }

quiz_service = QuizService()
