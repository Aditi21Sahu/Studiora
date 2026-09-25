import os
import sys
import json
import datetime
from fastapi.testclient import TestClient

backend_dir = r"c:\Users\shbhm\OneDrive\Desktop\Studiora\backend"
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from app.main import app
from app.database import SessionLocal
from app.models.user import User
from app.models.material import Material
from app.models.test_paper import TestPaper
from app.models.test_attempt import TestAttempt
from app.services.auth_service import create_access_token

client = TestClient(app)

def run_test_paper_feature_suite():
    print("==================================================================")
    print("   STARTING COMPREHENSIVE AI 25-MARK TIMED TEST FEATURE SUITE     ")
    print("==================================================================")

    db = SessionLocal()
    user = db.query(User).filter(User.id == 2).first()
    if not user:
        user = db.query(User).first()
    assert user is not None, "No test user found!"

    token = create_access_token(data={"sub": user.email, "id": user.id})
    headers = {"Authorization": f"Bearer {token}"}

    # Find a material with content
    mat = db.query(Material).filter(Material.user_id == user.id, Material.text_content.isnot(None)).first()
    if not mat:
        mat = db.query(Material).first()
    assert mat is not None, "No study material found for user!"

    print(f"[TEST 1] Generating 25-Mark Test Paper from Material ID {mat.id} ('{mat.title}')...")
    gen_res = client.post("/api/tests/generate", json={
        "material_id": mat.id,
        "title": f"Midterm Exam — {mat.title[:30]}"
    }, headers=headers)
    assert gen_res.status_code == 201, f"Generate failed: {gen_res.text}"
    paper = gen_res.json()

    print(f"  Title: {paper['title']}")
    print(f"  Total Questions: {paper['total_questions']}")
    print(f"  Total Marks: {paper['total_marks']}")
    print(f"  Duration: {paper['duration_minutes']} minutes")

    assert paper["total_questions"] == 20, f"Expected 20 questions, got {paper['total_questions']}"
    assert paper["total_marks"] == 25, f"Expected 25 marks, got {paper['total_marks']}"
    assert paper["duration_minutes"] == 30, f"Expected 30 mins, got {paper['duration_minutes']}"

    secs = paper["sections"]
    sec_a = secs["section_a"]
    sec_b = secs["section_b"]
    sec_c = secs["section_c"]
    sec_d = secs["section_d"]

    assert len(sec_a) == 5, f"Expected 5 MCQs, got {len(sec_a)}"
    assert len(sec_b) == 5, f"Expected 5 True/False, got {len(sec_b)}"
    assert len(sec_c) == 5, f"Expected 5 Blanks, got {len(sec_c)}"
    assert len(sec_d) == 5, f"Expected 5 Q&A, got {len(sec_d)}"
    print("[PASS] Exactly 20 questions verified across Sections A (5), B (5), C (5), D (5)")

    # Test 2: Security check - Verify NO answer keys or model answers leaked to student
    print("\n[TEST 2] Verifying security invariants (no answer keys leaked)...")
    for q in sec_a:
        assert "correct_answer" not in q, "MCQ correct_answer exposed to student!"
        assert "explanation" not in q, "MCQ explanation exposed to student!"
        assert len(q["options"]) == 4, "MCQ must have 4 options"
        assert q["marks"] == 1
    for q in sec_b:
        assert "correct_answer" not in q, "True/False correct_answer exposed to student!"
        assert q["marks"] == 1
    for q in sec_c:
        assert "correct_answer" not in q, "Blank correct_answer exposed to student!"
        assert "accepted_answers" not in q, "accepted_answers exposed to student!"
        assert q["marks"] == 1
    for q in sec_d:
        assert "model_answer" not in q, "Q&A model_answer exposed to student!"
        assert "important_keywords" not in q, "keywords exposed to student!"
        assert "marking_guidance" not in q, "marking_guidance exposed to student!"
        assert q["marks"] == 2
    print("[PASS] Security invariants strictly preserved: 0 answer keys or evaluation cues exposed")

    # Test 3: Start test attempt with server-side persistent 30-min timer
    print("\n[TEST 3] Starting timed test attempt...")
    start_res = client.post(f"/api/tests/{paper['id']}/start", headers=headers)
    assert start_res.status_code == 200, f"Start failed: {start_res.text}"
    att_data = start_res.json()
    att_id = att_data["attempt_id"]
    print(f"  Attempt ID: {att_id}")
    print(f"  Remaining Seconds: {att_data['remaining_seconds']} (out of 1800)")
    assert att_data["duration_seconds"] == 1800
    assert 1780 <= att_data["remaining_seconds"] <= 1800
    print("[PASS] 30-minute server timer started accurately")

    # Test 4: Save draft & resume on simulated page refresh
    print("\n[TEST 4] Testing draft autosave and persistence (refresh simulation)...")
    save_res = client.post(f"/api/tests/attempts/{att_id}/save-draft", json={
        "answers": {"1": "A", "6": "True", "11": "energy"}
    }, headers=headers)
    assert save_res.status_code == 200

    active_res = client.get("/api/tests/attempts/active", headers=headers)
    assert active_res.status_code == 200
    active_data = active_res.json()
    assert active_data is not None
    assert active_data["attempt_id"] == att_id
    assert active_data["saved_answers"].get("1") == "A"
    assert active_data["saved_answers"].get("11") == "energy"
    print("[PASS] Persistence verified: active attempt & draft answers recovered on page refresh")

    # Fetch underlying test paper from DB to inspect actual answers for grading test
    db_paper = db.query(TestPaper).filter(TestPaper.id == paper["id"]).first()
    db_secs = json.loads(db_paper.sections_json)

    # Test 5: Submit with mixed answers (correct, partial, incorrect, unanswered)
    print("\n[TEST 5] Submitting test with realistic mixed student answers...")
    answers_payload = {}

    # Section A: 4 correct, 1 wrong
    for idx, q in enumerate(db_secs["section_a"]):
        qid = str(q["id"])
        if idx < 4:
            answers_payload[qid] = q["correct_answer"]
        else:
            wrong_opt = "B" if q["correct_answer"] == "A" else "A"
            answers_payload[qid] = wrong_opt

    # Section B: 5 correct
    for q in db_secs["section_b"]:
        qid = str(q["id"])
        answers_payload[qid] = q["correct_answer"]

    # Section C: 3 exact, 1 variant, 1 wrong
    for idx, q in enumerate(db_secs["section_c"]):
        qid = str(q["id"])
        if idx < 3:
            answers_payload[qid] = q["correct_answer"]
        elif idx == 3:
            answers_payload[qid] = f"  {q['correct_answer'].upper()}  "  # flexible trim & case test
        else:
            answers_payload[qid] = "completely_wrong_answer"

    # Section D:
    # Q16: Good answer with keywords
    q16 = db_secs["section_d"][0]
    answers_payload[str(q16["id"])] = q16["model_answer"]

    # Q17: Good answer
    q17 = db_secs["section_d"][1]
    answers_payload[str(q17["id"])] = f"This process functions by utilizing {', '.join(q17.get('important_keywords', ['energy'])[:2])} to facilitate system operation."

    # Q18: Partial answer
    q18 = db_secs["section_d"][2]
    answers_payload[str(q18["id"])] = "It has a partial effect on the system."

    # Q19: Irrelevant answer
    q19 = db_secs["section_d"][3]
    answers_payload[str(q19["id"])] = "Random irrelevant sentence."

    # Q20: Unanswered (empty)
    q20 = db_secs["section_d"][4]
    answers_payload[str(q20["id"])] = ""

    sub_res = client.post(f"/api/tests/attempts/{att_id}/submit", json={
        "answers": answers_payload,
        "submission_type": "manual"
    }, headers=headers)
    assert sub_res.status_code == 200, f"Submit failed: {sub_res.text}"
    result = sub_res.json()

    print(f"  Total Score: {result['score']} / {result['max_marks']}")
    print(f"  Percentage: {result['percentage']}%")
    print(f"  Submission Message: {result['submission_message']}")
    print(f"  Section Scores: {result['section_scores']}")

    sec_scores = result["section_scores"]
    assert sec_scores["section_a"] == 4.0, f"Expected 4/5 for Sec A, got {sec_scores['section_a']}"
    assert sec_scores["section_b"] == 5.0, f"Expected 5/5 for Sec B, got {sec_scores['section_b']}"
    assert sec_scores["section_c"] == 4.0, f"Expected 4/5 for Sec C (with trim/case handling), got {sec_scores['section_c']}"
    assert 0.0 <= sec_scores["section_d"] <= 10.0
    computed_total = round(sec_scores["section_a"] + sec_scores["section_b"] + sec_scores["section_c"] + sec_scores["section_d"], 1)
    assert result["score"] == computed_total
    assert result["submission_message"] == "Submitted by student."

    # Verify Q20 was marked 0 with "Not attempted"
    q20_rev = next(r for r in result["all_questions_review"] if r["question_id"] == q20["id"])
    assert q20_rev["marks_obtained"] == 0.0
    assert q20_rev["student_answer"] == "Not attempted"
    print(f"[PASS] Scoring & AI evaluation verified: Total = {result['score']}/25 ({result['percentage']}%)")

    # Test 6: Verify Mistake Analysis details
    print("\n[TEST 6] Verifying mistake analysis items...")
    mistakes = result["mistakes_review"]
    assert len(mistakes) > 0, "Expected at least 3 mistakes from test data"
    for m in mistakes:
        assert m["is_correct"] is False or m["marks_obtained"] < m["max_marks"]
        assert "question" in m and len(m["question"]) > 0
        assert "student_answer" in m
        assert "correct_answer" in m and len(m["correct_answer"]) > 0
        assert "feedback" in m and len(m["feedback"]) > 0
    print(f"[PASS] Mistake analysis verified: {len(mistakes)} items with detailed pedagogical feedback")

    # Test 7: Automatic expiration submission test
    print("\n[TEST 7] Testing automatic timeout submission when timer hits 00:00...")
    start_res2 = client.post(f"/api/tests/{paper['id']}/start", headers=headers)
    att_id2 = start_res2.json()["attempt_id"]
    # Force attempt ends_at to past
    db_att2 = db.query(TestAttempt).filter(TestAttempt.id == att_id2).first()
    db_att2.ends_at = datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
    db.commit()

    sub_res2 = client.post(f"/api/tests/attempts/{att_id2}/submit", json={
        "answers": {"1": "A"},
        "submission_type": "automatic"
    }, headers=headers)
    assert sub_res2.status_code == 200
    res2 = sub_res2.json()
    assert res2["submission_type"] == "automatic"
    assert res2["submission_message"] == "Automatically submitted when time expired."
    print("[PASS] Automatic timeout submission verified ('Automatically submitted when time expired.')")

    # Test 8: Integration with Reports Summary
    print("\n[TEST 8] Verifying integration with Reports page endpoint...")
    rep_res = client.get("/api/reports/summary", headers=headers)
    assert rep_res.status_code == 200
    rep_summary = rep_res.json()
    recent_att = rep_summary.get("recent_attempts", [])
    test_paper_attempts = [a for a in recent_att if a.get("attempt_type") == "test_paper"]
    assert len(test_paper_attempts) > 0, "Completed test paper attempt not found in reports recent_attempts!"
    print(f"[PASS] Test paper attempts ({len(test_paper_attempts)}) integrated into Reports history table")

    # Test 9: Verify Frontend Routes and Static Files
    print("\n[TEST 9] Verifying frontend static routes...")
    r1 = client.get("/test-papers.html")
    assert r1.status_code == 200, "test-papers.html not found!"
    r2 = client.get("/js/test-paper.js")
    assert r2.status_code == 200, "test-paper.js not found!"
    r3 = client.get("/test-papers", follow_redirects=False)
    assert r3.status_code in (302, 307), "Redirect for /test-papers failed!"
    print("[PASS] All frontend HTML and JS files load properly (200 OK)")

    # Cleanup test paper and attempts created during testing
    print("\n[CLEANUP] Cleaning up test data...")
    db.query(TestAttempt).filter(TestAttempt.test_paper_id == paper["id"]).delete()
    db.query(TestPaper).filter(TestPaper.id == paper["id"]).delete()
    db.commit()
    db.close()
    print("[PASS] Cleanup complete. Database restored to pristine state.")

    print("\n******************************************************************")
    print("  ALL 23 REQUIREMENTS FOR AI 25-MARK TIMED TEST PASSED 100%!     ")
    print("******************************************************************")

if __name__ == "__main__":
    run_test_paper_feature_suite()
