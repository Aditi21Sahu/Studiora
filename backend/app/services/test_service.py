import json
import logging
import datetime
import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.test_paper import TestPaper
from app.models.test_attempt import TestAttempt
from app.models.material import Material
from app.models.note import Note
from app.models.activity import Activity
from app.ai.groq_service import groq_service

logger = logging.getLogger(__name__)

class TestService:
    """Service handling 25-mark test paper generation, secure taking, and AI evaluation."""

    def generate_test_paper(
        self,
        db: Session,
        user_id: int,
        material_id: Optional[int] = None,
        note_id: Optional[int] = None,
        title: Optional[str] = None
    ) -> TestPaper:
        """Extract study content and generate a 20-question, 25-mark test paper."""
        text_content = ""
        title_hint = title

        if note_id:
            note = db.query(Note).filter(Note.id == note_id, Note.user_id == user_id).first()
            if not note:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study note not found.")
            title_hint = title_hint or f"{note.title} Test Paper"
            text_content = f"{note.title}\n{note.summary or ''}\n"
            if note.key_points:
                try:
                    pts = json.loads(note.key_points)
                    text_content += "\nKey Points:\n" + "\n".join(pts)
                except Exception:
                    pass
            if note.sections:
                try:
                    secs = json.loads(note.sections)
                    for s in secs:
                        text_content += f"\n\n{s.get('title', '')}\n{s.get('content', '')}"
                except Exception:
                    pass
        elif material_id:
            mat = db.query(Material).filter(Material.id == material_id, Material.user_id == user_id).first()
            if not mat:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Study material not found.")
            title_hint = title_hint or f"{mat.title} Test Paper"
            text_content = mat.text_content or ""
        else:
            # Fallback to user's most recent material or note
            recent_mat = db.query(Material).filter(Material.user_id == user_id).order_by(Material.created_at.desc()).first()
            if recent_mat and recent_mat.text_content:
                material_id = recent_mat.id
                title_hint = title_hint or f"{recent_mat.title} Test Paper"
                text_content = recent_mat.text_content
            else:
                recent_note = db.query(Note).filter(Note.user_id == user_id).order_by(Note.created_at.desc()).first()
                if recent_note:
                    note_id = recent_note.id
                    title_hint = title_hint or f"{recent_note.title} Test Paper"
                    text_content = recent_note.summary or recent_note.title

        if not text_content or len(text_content.strip()) < 20:
            text_content = "Core academic concepts, principles, operational processes, and verified study material findings."
            title_hint = title_hint or "Comprehensive Academic Test Paper"

        # Generate 25-mark test paper via Groq AI
        paper_data = groq_service.generate_test_paper(text_content, title_hint=title_hint)

        test_paper = TestPaper(
            user_id=user_id,
            material_id=material_id,
            note_id=note_id,
            title=paper_data.get("title") or title_hint or "25-Mark Test Paper",
            total_questions=20,
            total_marks=25,
            duration_minutes=30,
            sections_json=json.dumps(paper_data)
        )
        db.add(test_paper)
        db.commit()
        db.refresh(test_paper)

        # Log Activity
        act = Activity(
            user_id=user_id,
            activity_type="test_created",
            title="Generated 25-Mark AI Test",
            description=f"Generated timed 25-mark test paper: '{test_paper.title}' with 20 questions."
        )
        db.add(act)
        db.commit()

        return test_paper

    def get_user_test_papers(self, db: Session, user_id: int) -> List[Dict[str, Any]]:
        """Retrieve all test papers generated for the user with attempt summaries."""
        papers = (
            db.query(TestPaper)
            .filter(TestPaper.user_id == user_id)
            .order_by(TestPaper.created_at.desc())
            .all()
        )
        result = []
        for p in papers:
            completed_attempts = [a for a in p.attempts if a.status in ("completed", "auto_submitted")]
            best_score = max((a.percentage for a in completed_attempts), default=None)
            result.append({
                "id": p.id,
                "title": p.title,
                "total_questions": p.total_questions,
                "total_marks": p.total_marks,
                "duration_minutes": p.duration_minutes,
                "attempts_count": len(completed_attempts),
                "best_score": best_score,
                "created_at": p.created_at
            })
        return result

    def get_test_paper_student_view(self, db: Session, test_id: int, user_id: int) -> Dict[str, Any]:
        """
        Retrieve student-safe view of a test paper.
        Crucial: Strips out correct answers, model answers, keywords, marking guidance and explanations.
        """
        test_paper = db.query(TestPaper).filter(TestPaper.id == test_id, TestPaper.user_id == user_id).first()
        if not test_paper:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test paper not found.")

        raw_data = json.loads(test_paper.sections_json)

        # Build student-safe section A (MCQs)
        section_a = [
            {
                "id": q["id"],
                "question": q["question"],
                "options": q["options"],
                "marks": q.get("marks", 1)
            }
            for q in raw_data.get("section_a", [])
        ]

        # Build student-safe section B (True/False)
        section_b = [
            {
                "id": q["id"],
                "question": q["question"],
                "marks": q.get("marks", 1)
            }
            for q in raw_data.get("section_b", [])
        ]

        # Build student-safe section C (Fill in blanks)
        section_c = [
            {
                "id": q["id"],
                "question": q["question"],
                "marks": q.get("marks", 1)
            }
            for q in raw_data.get("section_c", [])
        ]

        # Build student-safe section D (Question Answers)
        section_d = [
            {
                "id": q["id"],
                "question": q["question"],
                "marks": q.get("marks", 2)
            }
            for q in raw_data.get("section_d", [])
        ]

        return {
            "id": test_paper.id,
            "title": test_paper.title,
            "total_questions": test_paper.total_questions,
            "total_marks": test_paper.total_marks,
            "duration_minutes": test_paper.duration_minutes,
            "sections": {
                "section_a": section_a,
                "section_b": section_b,
                "section_c": section_c,
                "section_d": section_d
            },
            "created_at": test_paper.created_at
        }

    def start_test_attempt(self, db: Session, test_id: int, user_id: int) -> Dict[str, Any]:
        """
        Start or resume a 30-minute timed test attempt.
        Stores persistent ends_at timestamp on server so page refresh cannot reset the timer.
        """
        test_paper = db.query(TestPaper).filter(TestPaper.id == test_id, TestPaper.user_id == user_id).first()
        if not test_paper:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test paper not found.")

        now = datetime.datetime.utcnow()

        # Check for an active in-progress attempt for this test
        existing_attempt = (
            db.query(TestAttempt)
            .filter(
                TestAttempt.test_paper_id == test_id,
                TestAttempt.user_id == user_id,
                TestAttempt.status == "in_progress"
            )
            .order_by(TestAttempt.started_at.desc())
            .first()
        )

        if existing_attempt:
            # Check if still within time window
            if now < existing_attempt.ends_at:
                remaining = max(0, int((existing_attempt.ends_at - now).total_seconds()))
                saved_answers = {}
                try:
                    saved_answers = json.loads(existing_attempt.answers_json or "{}")
                except Exception:
                    pass
                return {
                    "attempt_id": existing_attempt.id,
                    "test_paper_id": test_id,
                    "started_at": existing_attempt.started_at,
                    "ends_at": existing_attempt.ends_at,
                    "duration_seconds": 1800,
                    "remaining_seconds": remaining,
                    "status": "in_progress",
                    "saved_answers": saved_answers
                }
            else:
                # Time expired for previous attempt, automatically finalize it
                saved_answers = {}
                try:
                    saved_answers = json.loads(existing_attempt.answers_json or "{}")
                except Exception:
                    pass
                self.submit_test_attempt(
                    db=db,
                    attempt_id=existing_attempt.id,
                    user_id=user_id,
                    answers=saved_answers,
                    submission_type="automatic"
                )

        # Create fresh attempt with strict 30-minute server timer
        duration_minutes = test_paper.duration_minutes or 30
        ends_at = now + datetime.timedelta(minutes=duration_minutes)

        attempt = TestAttempt(
            user_id=user_id,
            test_paper_id=test_id,
            started_at=now,
            ends_at=ends_at,
            status="in_progress",
            answers_json="{}"
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        return {
            "attempt_id": attempt.id,
            "test_paper_id": test_id,
            "started_at": attempt.started_at,
            "ends_at": attempt.ends_at,
            "duration_seconds": duration_minutes * 60,
            "remaining_seconds": duration_minutes * 60,
            "status": "in_progress",
            "saved_answers": {}
        }

    def save_test_draft(self, db: Session, attempt_id: int, user_id: int, answers: Dict[str, str]) -> Dict[str, Any]:
        """Save draft answers during test so user progress is never lost on refresh."""
        attempt = db.query(TestAttempt).filter(TestAttempt.id == attempt_id, TestAttempt.user_id == user_id).first()
        if not attempt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test attempt not found.")
        if attempt.status != "in_progress":
            return {"status": "already_submitted"}

        attempt.answers_json = json.dumps(answers)
        db.commit()
        return {"status": "saved"}

    def submit_test_attempt(
        self,
        db: Session,
        attempt_id: int,
        user_id: int,
        answers: Dict[str, str],
        submission_type: str = "manual"
    ) -> Dict[str, Any]:
        """
        Evaluate and submit test attempt.
        Calculates marks across all 4 sections (Sections A-C graded locally, Section D graded via Groq AI).
        """
        attempt = db.query(TestAttempt).filter(TestAttempt.id == attempt_id, TestAttempt.user_id == user_id).first()
        if not attempt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test attempt not found.")

        # Idempotency guard: if already graded, return cached result
        if attempt.status in ("completed", "auto_submitted") and attempt.evaluation_json:
            return self.get_attempt_result(db, attempt_id, user_id)

        now = datetime.datetime.utcnow()
        # Verify if submission occurred past expiration buffer (15 seconds grace period)
        if now > (attempt.ends_at + datetime.timedelta(seconds=15)):
            submission_type = "automatic"

        test_paper = db.query(TestPaper).filter(TestPaper.id == attempt.test_paper_id).first()
        if not test_paper:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated test paper not found.")

        raw_data = json.loads(test_paper.sections_json)
        all_reviews = []
        mistakes_review = []

        # ==========================================
        # 1. Grade Section A (5 MCQs, 1 mark each)
        # ==========================================
        sec_a_score = 0.0
        for q in raw_data.get("section_a", []):
            qid = str(q["id"])
            student_ans = str(answers.get(qid) or "").strip().upper()
            correct_ans = str(q["correct_answer"]).strip().upper()
            is_correct = (student_ans == correct_ans)
            marks = 1.0 if is_correct else 0.0
            sec_a_score += marks

            # Find option text
            selected_text = next((o["text"] for o in q.get("options", []) if o["id"] == student_ans), "")
            correct_text = next((o["text"] for o in q.get("options", []) if o["id"] == correct_ans), "")
            stud_display = f"Option {student_ans} — {selected_text}" if student_ans else "Not attempted"
            corr_display = f"Option {correct_ans} — {correct_text}"

            rev = {
                "question_id": q["id"],
                "section": "Section A — MCQs",
                "question": q["question"],
                "student_answer": stud_display,
                "correct_answer": corr_display,
                "marks_obtained": marks,
                "max_marks": 1,
                "is_correct": is_correct,
                "feedback": q.get("explanation") or ("Correct answer!" if is_correct else f"Option {correct_ans} is the correct concept."),
                "missing_concepts": []
            }
            all_reviews.append(rev)
            if not is_correct:
                mistakes_review.append(rev)

        # ==========================================
        # 2. Grade Section B (5 True/False, 1 mark each)
        # ==========================================
        sec_b_score = 0.0
        for q in raw_data.get("section_b", []):
            qid = str(q["id"])
            raw_stud = str(answers.get(qid) or "").strip().lower()
            student_ans = "True" if "true" in raw_stud or raw_stud == "t" else ("False" if "false" in raw_stud or raw_stud == "f" else "")
            correct_ans = str(q["correct_answer"]).strip()
            is_correct = (student_ans.lower() == correct_ans.lower())
            marks = 1.0 if is_correct else 0.0
            sec_b_score += marks

            stud_display = student_ans if student_ans else "Not attempted"
            rev = {
                "question_id": q["id"],
                "section": "Section B — True / False",
                "question": q["question"],
                "student_answer": stud_display,
                "correct_answer": correct_ans,
                "marks_obtained": marks,
                "max_marks": 1,
                "is_correct": is_correct,
                "feedback": q.get("explanation") or ("Correct evaluation." if is_correct else f"The statement is verified to be {correct_ans}."),
                "missing_concepts": []
            }
            all_reviews.append(rev)
            if not is_correct:
                mistakes_review.append(rev)

        # ==========================================
        # 3. Grade Section C (5 Fill in Blanks, 1 mark each)
        # ==========================================
        sec_c_score = 0.0
        for q in raw_data.get("section_c", []):
            qid = str(q["id"])
            student_ans = str(answers.get(qid) or "").strip()
            correct_ans = str(q["correct_answer"]).strip()
            raw_accepted = q.get("accepted_answers", [correct_ans])

            # Normalize for flexible comparison (trim, lowercase, strip punctuation)
            norm_stud = re.sub(r'[\s\.\,\;\:\-\_]+', ' ', student_ans.lower()).strip()
            norm_corr = re.sub(r'[\s\.\,\;\:\-\_]+', ' ', correct_ans.lower()).strip()
            norm_accepted = [re.sub(r'[\s\.\,\;\:\-\_]+', ' ', str(a).lower()).strip() for a in raw_accepted]
            if norm_corr not in norm_accepted:
                norm_accepted.append(norm_corr)

            is_correct = bool(norm_stud and (norm_stud in norm_accepted or any(norm_stud == a for a in norm_accepted)))
            marks = 1.0 if is_correct else 0.0
            sec_c_score += marks

            stud_display = student_ans if student_ans else "Not attempted"
            rev = {
                "question_id": q["id"],
                "section": "Section C — Fill in the Blanks",
                "question": q["question"],
                "student_answer": stud_display,
                "correct_answer": correct_ans,
                "marks_obtained": marks,
                "max_marks": 1,
                "is_correct": is_correct,
                "feedback": q.get("explanation") or ("Correct concept term identified!" if is_correct else f"'{correct_ans}' is the expected keyword for this blank."),
                "missing_concepts": []
            }
            all_reviews.append(rev)
            if not is_correct:
                mistakes_review.append(rev)

        # ==========================================
        # 4. Grade Section D (5 Question Answers, 2 marks each)
        # ==========================================
        qa_eval_requests = []
        for q in raw_data.get("section_d", []):
            qid = str(q["id"])
            student_ans = str(answers.get(qid) or "").strip()
            qa_eval_requests.append({
                "question_id": q["id"],
                "question": q["question"],
                "student_answer": student_ans,
                "model_answer": q.get("model_answer", ""),
                "important_keywords": q.get("important_keywords", []),
                "marking_guidance": q.get("marking_guidance", "")
            })

        # Call Groq AI evaluation service
        ai_evaluations = groq_service.evaluate_question_answers(qa_eval_requests)
        eval_lookup = {item["question_id"]: item for item in ai_evaluations}

        sec_d_score = 0.0
        for q in raw_data.get("section_d", []):
            qid = q["id"]
            eval_result = eval_lookup.get(qid, {
                "marks": 0,
                "evaluation": "Not attempted",
                "feedback": "Question was not attempted.",
                "matched_keywords": [],
                "missing_keywords": q.get("important_keywords", [])
            })

            marks = float(eval_result.get("marks", 0))
            marks = max(0.0, min(2.0, marks))
            sec_d_score += marks
            is_correct = (marks == 2.0)

            student_ans = str(answers.get(str(qid)) or "").strip()
            stud_display = student_ans if student_ans else "Not attempted"

            eval_status = eval_result.get("evaluation")
            if not eval_status or eval_status in ["Evaluation complete.", ""]:
                eval_status = "Correct" if marks == 2 else ("Partially Correct" if marks == 1 else "Incorrect")
            if stud_display == "Not attempted":
                eval_status = "Incorrect (Not attempted)"

            rev = {
                "question_id": qid,
                "section": "Section D — Short Answers",
                "question": q["question"],
                "student_answer": stud_display,
                "correct_answer": q.get("model_answer", ""),
                "marks_obtained": marks,
                "max_marks": 2,
                "is_correct": is_correct,
                "feedback": eval_result.get("feedback") or "Evaluation complete.",
                "missing_concepts": eval_result.get("missing_keywords") or [],
                "ai_evaluation": eval_status,
                "important_keywords": q.get("important_keywords") or []
            }
            all_reviews.append(rev)
            if not is_correct:
                mistakes_review.append(rev)

        # ==========================================
        # Calculate Final Scores
        # ==========================================
        total_score = round(sec_a_score + sec_b_score + sec_c_score + sec_d_score, 1)
        percentage = round((total_score / 25.0) * 100, 1)
        time_taken_seconds = max(0, min(1800, int((now - attempt.started_at).total_seconds())))

        section_scores = {
            "section_a": sec_a_score,
            "section_b": sec_b_score,
            "section_c": sec_c_score,
            "section_d": sec_d_score,
            "total": total_score
        }

        eval_payload = {
            "submission_type": submission_type,
            "section_scores": section_scores,
            "mistakes_review": mistakes_review,
            "all_questions_review": all_reviews
        }

        attempt.status = "completed" if submission_type == "manual" else "auto_submitted"
        attempt.submission_type = submission_type
        attempt.submitted_at = now
        attempt.score = total_score
        attempt.max_marks = 25
        attempt.percentage = percentage
        attempt.time_taken_seconds = time_taken_seconds
        attempt.section_scores_json = json.dumps(section_scores)
        attempt.answers_json = json.dumps(answers)
        attempt.evaluation_json = json.dumps(eval_payload)
        db.commit()

        # Log Activity
        sub_label = "manually submitted" if submission_type == "manual" else "automatically submitted (time expired)"
        act = Activity(
            user_id=user_id,
            activity_type="test_completed",
            title=f"Completed 25-Mark Test: {total_score}/25 ({percentage}%)",
            description=f"Attempt on '{test_paper.title}' scored {total_score}/25 marks ({sub_label})."
        )
        db.add(act)
        db.commit()

        submission_message = (
            "Submitted by student." if submission_type == "manual"
            else "Automatically submitted when time expired."
        )

        return {
            "id": attempt.id,
            "test_paper_id": test_paper.id,
            "test_title": test_paper.title,
            "score": total_score,
            "max_marks": 25,
            "percentage": percentage,
            "time_taken_seconds": time_taken_seconds,
            "started_at": attempt.started_at,
            "submitted_at": attempt.submitted_at,
            "submission_type": submission_type,
            "submission_message": submission_message,
            "section_scores": section_scores,
            "mistakes_review": mistakes_review,
            "all_questions_review": all_reviews
        }

    def get_attempt_result(self, db: Session, attempt_id: int, user_id: int) -> Dict[str, Any]:
        """Retrieve full score breakdown and mistake analysis for a completed test attempt."""
        attempt = db.query(TestAttempt).filter(TestAttempt.id == attempt_id, TestAttempt.user_id == user_id).first()
        if not attempt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Test attempt not found.")

        test_paper = db.query(TestPaper).filter(TestPaper.id == attempt.test_paper_id).first()
        test_title = test_paper.title if test_paper else f"Test #{attempt.test_paper_id}"

        eval_data = {}
        if attempt.evaluation_json:
            try:
                eval_data = json.loads(attempt.evaluation_json)
            except Exception:
                pass

        section_scores = eval_data.get("section_scores") or {
            "section_a": 0.0,
            "section_b": 0.0,
            "section_c": 0.0,
            "section_d": 0.0,
            "total": attempt.score
        }

        submission_type = attempt.submission_type or eval_data.get("submission_type") or "manual"
        submission_message = (
            "Submitted by student." if submission_type == "manual"
            else "Automatically submitted when time expired."
        )

        return {
            "id": attempt.id,
            "test_paper_id": attempt.test_paper_id,
            "test_title": test_title,
            "score": attempt.score,
            "max_marks": attempt.max_marks or 25,
            "percentage": attempt.percentage,
            "time_taken_seconds": attempt.time_taken_seconds,
            "started_at": attempt.started_at,
            "submitted_at": attempt.submitted_at or attempt.started_at,
            "submission_type": submission_type,
            "submission_message": submission_message,
            "section_scores": section_scores,
            "mistakes_review": eval_data.get("mistakes_review", []),
            "all_questions_review": eval_data.get("all_questions_review", [])
        }

test_service = TestService()
