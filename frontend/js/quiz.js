/**
 * STUDIORA — Quiz Controller
 * Handles quiz generation, interactive question runner, instant grading & reviews.
 */

let allQuizzes = [];
let currentQuiz = null;
let currentQuestionIndex = 0;
let userAnswers = {};
let quizTimer = null;
let timeTakenSeconds = 0;

document.addEventListener('DOMContentLoaded', async () => {
  Layout.init('quizzes');

  await loadQuizzes();
  await loadGenerationOptions();

  // Check if note_id or material_id is present in query string to prefill generation modal
  const urlParams = new URLSearchParams(window.location.search);
  const noteId = urlParams.get('note_id');
  if (noteId) {
    openGenerateModal(noteId);
  }
});

function extractCleanText(val) {
  if (val === null || val === undefined) return '';
  if (typeof val === 'object') {
    if (val.text) return extractCleanText(val.text);
    if (val.value) return extractCleanText(val.value);
    if (val.content) return extractCleanText(val.content);
    if (val.title) return extractCleanText(val.title);
    if (Array.isArray(val)) {
      return val.map(extractCleanText).filter(Boolean).join(' ');
    }
    return Object.values(val).map(extractCleanText).filter(Boolean).join(' ');
  }
  let s = String(val).trim();
  if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
    try {
      const parsed = JSON.parse(s);
      return extractCleanText(parsed);
    } catch (e) {
      return s.replace(/["{}\[\]]/g, '').trim();
    }
  }
  return s;
}

async function loadQuizzes() {
  const container = document.getElementById('quizzes-grid');
  const emptyState = document.getElementById('quizzes-empty-state');
  if (!container) return;

  try {
    allQuizzes = await api.get('/quizzes/');
    renderQuizzes(allQuizzes);
  } catch (err) {
    console.error('Failed to load quizzes:', err);
    Layout.showToast('Failed to load quizzes', 'error');
  }
}

function renderQuizzes(quizzes) {
  const container = document.getElementById('quizzes-grid');
  const emptyState = document.getElementById('quizzes-empty-state');
  if (!container) return;

  if (!quizzes || quizzes.length === 0) {
    container.innerHTML = '';
    if (emptyState) emptyState.style.display = 'block';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';

  container.innerHTML = quizzes.map((q) => {
    const questionsCount = q.questions ? q.questions.length : (q.question_count || 5);
    const difficulty = q.difficulty || 'Medium';
    let diffBadge = 'badge-completed';
    if (difficulty === 'Hard') diffBadge = 'badge-failed';
    else if (difficulty === 'Medium') diffBadge = 'badge-processing';

    return `
      <div class="card card-hover" style="display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
            <span class="badge ${diffBadge}">${difficulty}</span>
            <span style="font-size: 0.78rem; font-weight: 600; color: var(--text-secondary);">
              ${questionsCount} Questions
            </span>
          </div>
          <h3 style="font-size: 1.1rem; font-weight: 700; color: var(--text-dark); line-height: 1.35; margin-bottom: 0.4rem;">
            ${escapeHtml(extractCleanText(q.title))}
          </h3>
          <p style="font-size: 0.82rem; color: var(--text-secondary);">
            Created ${q.created_at ? new Date(q.created_at).toLocaleDateString() : 'recently'}
          </p>
        </div>

        <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between;">
          <button class="btn btn-primary btn-sm" onclick="startQuiz(${q.id})">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            Start Quiz
          </button>
          <button class="btn btn-danger btn-sm" onclick="handleDeleteQuiz(${q.id})" title="Delete quiz">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </div>
      </div>
    `;
  }).join('');
}

async function loadGenerationOptions() {
  const noteSelect = document.getElementById('gen-note-select');
  if (!noteSelect) return;

  try {
    const notes = await api.get('/notes/');
    noteSelect.innerHTML = notes.map((n) => `
      <option value="${n.id}">${escapeHtml(extractCleanText(n.title))}</option>
    `).join('');
  } catch (err) {
    console.error('Failed to load notes for selection:', err);
  }
}

function openGenerateModal(preselectedNoteId = null) {
  const modal = document.getElementById('generate-quiz-modal');
  if (!modal) return;

  if (preselectedNoteId) {
    const select = document.getElementById('gen-note-select');
    if (select) select.value = preselectedNoteId;
  }

  modal.classList.add('open');
}

function closeGenerateModal() {
  const modal = document.getElementById('generate-quiz-modal');
  if (modal) modal.classList.remove('open');
}

async function handleGenerateQuizSubmit(e) {
  e.preventDefault();
  const noteSelect = document.getElementById('gen-note-select');
  const countSelect = document.getElementById('gen-count-select');
  const diffSelect = document.getElementById('gen-difficulty-select');
  const submitBtn = document.getElementById('gen-submit-btn');

  const noteId = noteSelect ? noteSelect.value : null;
  const questionCount = countSelect ? parseInt(countSelect.value, 10) : 5;
  const difficulty = diffSelect ? diffSelect.value : 'Medium';

  if (!noteId) {
    Layout.showToast('Please select a study note first', 'error');
    return;
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerText = 'Generating Quiz...';
  }

  try {
    const quiz = await api.post('/quizzes/generate', {
      note_id: parseInt(noteId, 10),
      question_count: questionCount,
      difficulty
    });
    Layout.showToast('Quiz created successfully!', 'success');
    closeGenerateModal();
    await loadQuizzes();
    startQuiz(quiz.id);
  } catch (err) {
    Layout.showToast(err.message || 'Failed to generate quiz', 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = 'Generate Quiz';
    }
  }
}

async function startQuiz(quizId) {
  try {
    currentQuiz = await api.get(`/quizzes/${quizId}`);
    currentQuestionIndex = 0;
    userAnswers = {};
    timeTakenSeconds = 0;

    if (quizTimer) clearInterval(quizTimer);
    quizTimer = setInterval(() => {
      timeTakenSeconds++;
      const timerEl = document.getElementById('quiz-timer');
      if (timerEl) {
        const mins = Math.floor(timeTakenSeconds / 60).toString().padStart(2, '0');
        const secs = (timeTakenSeconds % 60).toString().padStart(2, '0');
        timerEl.textContent = `${mins}:${secs}`;
      }
    }, 1000);

    const listSection = document.getElementById('quiz-list-section');
    const runnerSection = document.getElementById('quiz-runner-section');
    const resultSection = document.getElementById('quiz-result-section');

    if (listSection) listSection.style.display = 'none';
    if (resultSection) resultSection.style.display = 'none';
    if (runnerSection) runnerSection.style.display = 'block';

    renderCurrentQuestion();
  } catch (err) {
    Layout.showToast('Failed to start quiz', 'error');
  }
}

function renderCurrentQuestion() {
  if (!currentQuiz || !currentQuiz.questions || !currentQuiz.questions[currentQuestionIndex]) return;

  const q = currentQuiz.questions[currentQuestionIndex];
  const total = currentQuiz.questions.length;
  const progressPercent = Math.round(((currentQuestionIndex + 1) / total) * 100);

  const progressText = document.getElementById('quiz-progress-text');
  if (progressText) progressText.textContent = `Question ${currentQuestionIndex + 1} of ${total}`;
  
  const progressBarFill = document.getElementById('quiz-progress-bar-fill');
  if (progressBarFill) {
    progressBarFill.style.width = `${progressPercent}%`;
  }
  const progressPctEl = document.getElementById('quiz-progress-percent-label');
  if (progressPctEl) progressPctEl.textContent = `${progressPercent}%`;

  const questionTitleEl = document.getElementById('quiz-question-text');
  if (questionTitleEl) {
    questionTitleEl.textContent = extractCleanText(q.question_text || q.question);
  }

  const optionsContainer = document.getElementById('quiz-options-container');
  const explanationBox = document.getElementById('quiz-explanation-box');
  const nextBtn = document.getElementById('quiz-next-btn');
  const prevBtn = document.getElementById('quiz-prev-btn');

  if (prevBtn) {
    prevBtn.disabled = currentQuestionIndex === 0;
  }

  if (explanationBox) explanationBox.style.display = 'none';
  if (nextBtn) {
    nextBtn.textContent = currentQuestionIndex === total - 1 ? 'Finish & Submit' : 'Continue >';
    nextBtn.disabled = !userAnswers[q.id];
  }

  const rawOptions = q.options || {};
  let entries = [];
  if (Array.isArray(rawOptions)) {
    entries = rawOptions.map((opt, idx) => {
      const optId = (opt && typeof opt === 'object' && opt.id) ? opt.id : String.fromCharCode(65 + idx);
      return [optId, extractCleanText(opt)];
    });
  } else {
    entries = Object.entries(rawOptions).map(([k, v]) => [k, extractCleanText(v)]);
  }

  optionsContainer.innerHTML = entries.map(([key, text]) => {
    const isSelected = userAnswers[q.id]?.selectedOption === key;
    let cardClass = 'quiz-option-card';
    if (userAnswers[q.id]) {
      if (key === userAnswers[q.id].correctOption) cardClass += ' correct';
      else if (isSelected) cardClass += ' incorrect';
    }

    return `
      <div class="${cardClass}" onclick="selectQuizOption('${key}')">
        <span class="option-badge">${key}</span>
        <span style="font-size: 0.95rem; font-weight: 500; color: var(--text-dark); flex: 1;">
          ${escapeHtml(text)}
        </span>
      </div>
    `;
  }).join('');

  // If already answered, show explanation
  if (userAnswers[q.id] && explanationBox) {
    const ans = userAnswers[q.id];
    const isCorrect = ans.isCorrect;

    explanationBox.innerHTML = `
      <div class="needs-review-card">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
          <span class="badge ${isCorrect ? 'badge-completed' : 'badge-failed'}">
            ${isCorrect ? '✓ Correct Answer!' : '✗ Needs Review'}
          </span>
        </div>
        <div style="font-size: 0.88rem; margin-bottom: 0.35rem;">
          <span style="color: var(--text-secondary);">Your Answer: </span>
          <strong style="color: ${isCorrect ? 'var(--success)' : 'var(--error)'};">
            Option ${ans.selectedOption} — ${escapeHtml(extractCleanText(ans.selectedText))}
          </strong>
        </div>
        ${!isCorrect ? `
          <div style="font-size: 0.88rem; margin-bottom: 0.35rem;">
            <span style="color: var(--text-secondary);">Correct Answer: </span>
            <strong style="color: var(--success);">
              Option ${ans.correctOption} — ${escapeHtml(extractCleanText(ans.correctText))}
            </strong>
          </div>
        ` : ''}
        <div class="why-explanation-box">
          <div style="font-weight: 700; color: var(--primary-dark-teal); margin-bottom: 0.25rem;">Why?</div>
          <div>${escapeHtml(extractCleanText(ans.explanation))}</div>
        </div>
      </div>
    `;
    explanationBox.style.display = 'block';
  }
}

async function selectQuizOption(selectedKey) {
  const q = currentQuiz.questions[currentQuestionIndex];
  if (userAnswers[q.id]) return; // already answered

  // Build option mapping
  let selectedText = '';
  let correctText = '';
  const rawOptions = q.options || {};
  let optMap = {};
  if (Array.isArray(rawOptions)) {
    rawOptions.forEach((opt, idx) => {
      const optId = (opt && typeof opt === 'object' && opt.id) ? opt.id : String.fromCharCode(65 + idx);
      optMap[optId] = extractCleanText(opt);
    });
  } else {
    Object.entries(rawOptions).forEach(([k, v]) => {
      optMap[k] = extractCleanText(v);
    });
  }
  selectedText = optMap[selectedKey] || selectedKey;

  try {
    const res = await api.post('/quizzes/check-answer', {
      quiz_id: currentQuiz.id,
      question_id: q.id,
      selected_option: selectedKey
    });

    // Extract correct option letter and text safely
    const correctOpt = (res.correct_option || (res.correct_answer ? res.correct_answer.charAt(0) : '') || 'A').trim().toUpperCase();
    correctText = res.correct_text || optMap[correctOpt] || (res.correct_answer ? res.correct_answer.replace(/^[A-D]\.\s*/, '') : '') || correctOpt;

    userAnswers[q.id] = {
      selectedOption: selectedKey,
      selectedText: selectedText,
      isCorrect: Boolean(res.is_correct),
      correctOption: correctOpt,
      correctText: correctText,
      explanation: res.explanation || 'The answer is based directly on the provided study material.'
    };

    renderCurrentQuestion();
  } catch (err) {
    Layout.showToast('Failed to verify answer', 'error');
  }
}

function prevQuestion() {
  if (currentQuestionIndex > 0) {
    currentQuestionIndex--;
    renderCurrentQuestion();
  }
}

async function nextQuestion() {
  const total = currentQuiz.questions.length;
  if (currentQuestionIndex < total - 1) {
    currentQuestionIndex++;
    renderCurrentQuestion();
  } else {
    await submitQuizAttempt();
  }
}

let isSubmittingQuiz = false;

async function submitQuizAttempt() {
  if (isSubmittingQuiz) return;
  isSubmittingQuiz = true;

  const nextBtn = document.getElementById('quiz-next-btn');
  if (nextBtn) {
    nextBtn.disabled = true;
    nextBtn.textContent = 'Submitting...';
  }

  if (quizTimer) clearInterval(quizTimer);

  const payloadAnswers = Object.entries(userAnswers).map(([qid, ans]) => ({
    question_id: parseInt(qid, 10),
    selected_option: ans.selectedOption
  }));

  try {
    const attempt = await api.post(`/quizzes/${currentQuiz.id}/submit`, {
      time_taken_seconds: timeTakenSeconds,
      answers: payloadAnswers
    });

    renderQuizResult(attempt);
  } catch (err) {
    Layout.showToast('Failed to record quiz results', 'error');
  } finally {
    isSubmittingQuiz = false;
  }
}

function renderQuizResult(attempt) {
  const runnerSection = document.getElementById('quiz-runner-section');
  const resultSection = document.getElementById('quiz-result-section');

  if (runnerSection) runnerSection.style.display = 'none';
  if (resultSection) resultSection.style.display = 'block';

  const scorePct = Math.round(attempt.percentage || 0);
  const gaugeEl = document.getElementById('result-score-gauge');
  if (gaugeEl) gaugeEl.textContent = `${scorePct}%`;

  const fractionEl = document.getElementById('result-score-fraction');
  if (fractionEl) fractionEl.textContent = `${attempt.score} / ${attempt.total_questions}`;

  const timeEl = document.getElementById('result-time-taken');
  if (timeEl) {
    const mins = Math.floor((attempt.time_taken_seconds || 0) / 60);
    const secs = (attempt.time_taken_seconds || 0) % 60;
    timeEl.textContent = `${mins}m ${secs}s`;
  }

  // Mistakes breakdown list
  const mistakesList = document.getElementById('result-mistakes-list');
  const reviewItems = attempt.questions_to_review || (attempt.answers ? attempt.answers.filter(a => !a.is_correct) : []);
  if (mistakesList) {
    if (reviewItems.length === 0) {
      mistakesList.innerHTML = `
        <div style="padding: 1rem; background: var(--success-bg); color: var(--success); border-radius: var(--radius-md); font-weight: 600; text-align: center;">
          ✓ Perfect score! You got every question right.
        </div>
      `;
    } else {
      mistakesList.innerHTML = reviewItems.map((m, idx) => {
        const qText = m.question_text || m.question || '';
        const userAns = m.user_answer || `Option ${m.selected_option || ''}`;
        const correctAns = m.correct_answer || `Option ${m.correct_option || ''}`;
        const expl = m.explanation || '';
        return `
        <div style="padding: 0.85rem; border: 1px solid var(--border); border-radius: var(--radius-md); margin-bottom: 0.75rem; background: var(--card-white);">
          <div style="font-weight: 600; font-size: 0.9rem; color: var(--text-dark); margin-bottom: 0.35rem;">
            ${idx + 1}. ${escapeHtml(extractCleanText(qText))}
          </div>
          <div style="font-size: 0.82rem; color: var(--error); margin-bottom: 0.2rem;">
            Your answer: ${escapeHtml(extractCleanText(userAns))}
          </div>
          <div style="font-size: 0.82rem; color: var(--success); margin-bottom: 0.35rem;">
            Correct answer: ${escapeHtml(extractCleanText(correctAns))}
          </div>
          <div style="font-size: 0.8rem; color: var(--text-secondary); background: var(--light-cream); padding: 0.5rem 0.75rem; border-radius: var(--radius-sm);">
            ${escapeHtml(extractCleanText(expl))}
          </div>
        </div>
      `;
      }).join('');
    }
  }
}

function exitQuizRunner() {
  if (quizTimer) clearInterval(quizTimer);
  const runnerSection = document.getElementById('quiz-runner-section');
  const resultSection = document.getElementById('quiz-result-section');
  const listSection = document.getElementById('quiz-list-section');

  if (runnerSection) runnerSection.style.display = 'none';
  if (resultSection) resultSection.style.display = 'none';
  if (listSection) listSection.style.display = 'block';
  loadQuizzes();
}

async function handleDeleteQuiz(id) {
  if (!confirm('Are you sure you want to delete this quiz?')) return;

  try {
    await api.delete(`/quizzes/${id}`);
    Layout.showToast('Quiz deleted', 'info');
    await loadQuizzes();
  } catch (err) {
    Layout.showToast(err.message || 'Failed to delete quiz', 'error');
  }
}

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
