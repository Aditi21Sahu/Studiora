/**
 * STUDIORA — Test Paper Controller
 * Manages 25-mark timed curriculum tests (MCQs, True/False, Blanks & Short Answers).
 */

let allTests = [];
let currentTest = null;
let currentAttempt = null;
let studentAnswers = {};
let timerInterval = null;
let remainingSeconds = 1800;
let saveDraftTimeout = null;
let isSubmitting = false;

document.addEventListener('DOMContentLoaded', async () => {
  Layout.init('test-papers');

  await loadTestPapers();
  await loadGenerationSources();

  // Check if there is an active test attempt in progress (e.g. user refreshed the page)
  await checkAndResumeActiveAttempt();

  // Check URL parameters for source pre-fill
  const params = new URLSearchParams(window.location.search);
  const matId = params.get('material_id');
  const noteId = params.get('note_id');
  if (matId || noteId) {
    openGenerateTestModal(matId ? `mat_${matId}` : `note_${noteId}`);
  }
});

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
}

async function loadTestPapers() {
  const grid = document.getElementById('tests-grid');
  const emptyState = document.getElementById('tests-empty-state');
  if (!grid) return;

  try {
    allTests = await api.get('/tests/');
    renderTestGrid(allTests);
  } catch (err) {
    console.error('Failed to load test papers:', err);
    Layout.showToast('Failed to load test papers', 'error');
  }
}

function renderTestGrid(tests) {
  const grid = document.getElementById('tests-grid');
  const emptyState = document.getElementById('tests-empty-state');
  if (!grid) return;

  if (!tests || tests.length === 0) {
    grid.innerHTML = '';
    if (emptyState) emptyState.style.display = 'block';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';

  grid.innerHTML = tests.map(t => {
    const bestScoreText = t.best_score !== null && t.best_score !== undefined
      ? `Best: ${t.best_score}%`
      : 'Not attempted yet';
    const bestBadgeClass = t.best_score !== null && t.best_score >= 80
      ? 'badge-completed'
      : (t.best_score !== null ? 'badge-processing' : 'badge-uploaded');

    return `
      <div class="card card-hover" style="display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
            <span class="badge ${bestBadgeClass}">25 MARKS</span>
            <span style="font-size: 0.78rem; font-weight: 600; color: var(--text-secondary);">
              30 Mins &bull; 20 Qs
            </span>
          </div>
          <h3 style="font-size: 1.15rem; font-weight: 700; color: var(--text-dark); line-height: 1.35; margin-bottom: 0.4rem;">
            ${escapeHtml(t.title)}
          </h3>
          <p style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 1.25rem;">
            ${t.attempts_count} attempt${t.attempts_count === 1 ? '' : 's'} &bull; ${bestScoreText}
          </p>
        </div>

        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 1rem; border-top: 1px solid var(--border);">
          <span style="font-size: 0.78rem; color: var(--text-secondary);">
            ${t.created_at ? new Date(t.created_at).toLocaleDateString() : 'Recent'}
          </span>
          <button class="btn btn-primary btn-sm" onclick="openTestStartScreen(${t.id})">
            Take Test &rarr;
          </button>
        </div>
      </div>
    `;
  }).join('');
}

let availableSources = [];

async function loadGenerationSources() {
  const select = document.getElementById('gen-source-select');
  if (!select) return;

  try {
    const [materials, notes] = await Promise.all([
      api.get('/materials/').catch(() => []),
      api.get('/notes/').catch(() => [])
    ]);

    const validMaterials = (materials || []).filter(m => m.status === 'completed' || m.text_content);
    const validNotes = notes || [];
    availableSources = [
      ...validMaterials.map(m => ({ type: 'mat', id: m.id, title: m.title })),
      ...validNotes.map(n => ({ type: 'note', id: n.id, title: n.title }))
    ];

    let optionsHtml = '<option value="">Choose material or note...</option>';

    if (validMaterials.length > 0) {
      optionsHtml += '<optgroup label="Study Materials (Uploaded / YouTube)">';
      validMaterials.forEach(m => {
        optionsHtml += `<option value="mat_${m.id}">[Material] ${escapeHtml(m.title)}</option>`;
      });
      optionsHtml += '</optgroup>';
    }

    if (validNotes.length > 0) {
      optionsHtml += '<optgroup label="Study Notes">';
      validNotes.forEach(n => {
        optionsHtml += `<option value="note_${n.id}">[Note] ${escapeHtml(n.title)}</option>`;
      });
      optionsHtml += '</optgroup>';
    }

    select.innerHTML = optionsHtml;
  } catch (err) {
    console.error('Failed to load sources for test generator:', err);
  }
}

async function handleGenerateButtonClick() {
  await loadGenerationSources();

  if (!availableSources || availableSources.length === 0) {
    Layout.showToast('Please upload study material or create notes before generating a test paper.', 'warning');
    return;
  }

  // Pre-select first available source if none selected
  const select = document.getElementById('gen-source-select');
  if (select && (!select.value || select.value === '')) {
    if (availableSources.length > 0) {
      const first = availableSources[0];
      select.value = `${first.type}_${first.id}`;
    }
  }

  openGenerateTestModal();
}

function openGenerateTestModal(preselectedVal = null) {
  const modal = document.getElementById('generate-test-modal');
  const select = document.getElementById('gen-source-select');
  if (preselectedVal && select) {
    select.value = preselectedVal;
  }
  if (modal) {
    modal.classList.add('open');
    modal.classList.add('active');
  }
}

function closeGenerateTestModal() {
  const modal = document.getElementById('generate-test-modal');
  if (modal) {
    modal.classList.remove('open');
    modal.classList.remove('active');
  }
}

async function handleGenerateTestSubmit(e) {
  e.preventDefault();
  const select = document.getElementById('gen-source-select');
  const titleInput = document.getElementById('gen-custom-title');
  const submitBtn = document.getElementById('gen-test-submit-btn');

  if (!select || !select.value) {
    Layout.showToast('Please select study material or note', 'error');
    return;
  }

  const val = select.value;
  const payload = {
    title: titleInput ? titleInput.value.trim() : null
  };

  if (val.startsWith('mat_')) {
    payload.material_id = parseInt(val.replace('mat_', ''), 10);
  } else if (val.startsWith('note_')) {
    payload.note_id = parseInt(val.replace('note_', ''), 10);
  }

  try {
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerText = 'Generating 25-Mark Test...';
    }

    const testPaper = await api.post('/tests/generate', payload);
    closeGenerateTestModal();
    Layout.showToast('25-Mark Test Generated Successfully!', 'success');

    // Refresh list and open confirmation/start screen
    await loadTestPapers();
    openTestStartScreen(testPaper.id);
  } catch (err) {
    console.error('Error generating test paper:', err);
    Layout.showToast(err.message || 'Failed to generate test paper', 'error');
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = 'Generate 25-Mark Test';
    }
  }
}

async function checkAndResumeActiveAttempt() {
  try {
    const active = await api.get('/tests/attempts/active');
    if (active && active.attempt_id) {
      currentAttempt = active;
      remainingSeconds = active.remaining_seconds;
      studentAnswers = active.saved_answers || {};

      currentTest = await api.get(`/tests/${active.test_paper_id}`);

      // Switch directly to active test runner
      document.getElementById('test-list-section').style.display = 'none';
      document.getElementById('test-start-section').style.display = 'none';
      document.getElementById('test-result-section').style.display = 'none';
      document.getElementById('test-runner-section').style.display = 'block';

      document.getElementById('runner-test-title').innerText = currentTest.title;
      renderTestQuestions();
      startCountdownTimer(remainingSeconds);

      Layout.showToast('Resumed active timed test paper', 'info');
    }
  } catch (err) {
    // No active attempt or error, proceed normally
  }
}

async function openTestStartScreen(testId) {
  try {
    currentTest = await api.get(`/tests/${testId}`);

    document.getElementById('test-list-section').style.display = 'none';
    document.getElementById('test-runner-section').style.display = 'none';
    document.getElementById('test-result-section').style.display = 'none';
    document.getElementById('test-start-section').style.display = 'block';

    document.getElementById('start-test-title').innerText = currentTest.title;
    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (err) {
    console.error('Failed to open test start screen:', err);
    Layout.showToast('Failed to load test details', 'error');
  }
}

function exitToTestList() {
  if (timerInterval) clearInterval(timerInterval);
  currentTest = null;
  currentAttempt = null;
  studentAnswers = {};

  document.getElementById('test-start-section').style.display = 'none';
  document.getElementById('test-runner-section').style.display = 'none';
  document.getElementById('test-result-section').style.display = 'none';
  document.getElementById('test-list-section').style.display = 'block';

  loadTestPapers();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

async function beginTestExecution() {
  if (!currentTest) return;

  const btn = document.getElementById('start-test-confirm-btn');
  try {
    if (btn) {
      btn.disabled = true;
      btn.innerText = 'Initializing Server Timer...';
    }

    currentAttempt = await api.post(`/tests/${currentTest.id}/start`, {});
    remainingSeconds = currentAttempt.remaining_seconds || 1800;
    studentAnswers = currentAttempt.saved_answers || {};

    document.getElementById('test-start-section').style.display = 'none';
    document.getElementById('test-runner-section').style.display = 'block';

    document.getElementById('runner-test-title').innerText = currentTest.title;
    renderTestQuestions();
    startCountdownTimer(remainingSeconds);

    window.scrollTo({ top: 0, behavior: 'smooth' });
  } catch (err) {
    console.error('Failed to start test attempt:', err);
    Layout.showToast('Failed to start test', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = 'Start Test \u2192';
    }
  }
}

function renderTestQuestions() {
  const container = document.getElementById('test-questions-container');
  if (!container || !currentTest || !currentTest.sections) return;

  const secs = currentTest.sections;
  let html = '';

  // ==========================================
  // Section A: MCQs (1-5)
  // ==========================================
  html += `
    <div id="section-a" class="card" style="padding: 2rem;">
      <div style="border-bottom: 2px solid var(--border); padding-bottom: 0.85rem; margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
        <div>
          <span class="badge badge-uploaded" style="margin-bottom: 0.25rem;">SECTION A</span>
          <h3 style="font-size: 1.25rem; font-weight: 800; color: var(--text-dark); margin: 0;">Multiple Choice Questions</h3>
          <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 0.15rem;">Select the single unambiguously correct option (1 Mark Each)</p>
        </div>
        <span class="badge badge-completed">5 Marks Total</span>
      </div>

      <div style="display: flex; flex-direction: column; gap: 1.75rem;">
  `;

  (secs.section_a || []).forEach(q => {
    const selected = studentAnswers[String(q.id)] || '';
    html += `
      <div class="test-question-item" data-qid="${q.id}" style="border-bottom: 1px solid var(--border); padding-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
          <h4 style="font-size: 1rem; font-weight: 700; color: var(--text-dark); line-height: 1.4;">
            Q${q.id}. ${escapeHtml(q.question)}
          </h4>
          <span class="badge badge-uploaded" style="font-size: 0.72rem;">1 Mark</span>
        </div>

        <div style="display: grid; grid-template-columns: 1fr; gap: 0.65rem;">
          ${(q.options || []).map(opt => {
            const isChecked = selected === opt.id;
            return `
              <label class="quiz-option-label ${isChecked ? 'selected' : ''}" style="cursor: pointer; display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 1rem; border: 1.5px solid ${isChecked ? 'var(--primary-dark-teal)' : 'var(--border)'}; border-radius: var(--radius-md); background: ${isChecked ? 'var(--light-cream)' : 'var(--bg-card)'};">
                <input type="radio" name="test_q_${q.id}" value="${opt.id}" ${isChecked ? 'checked' : ''} onchange="handleAnswerSelect(${q.id}, '${opt.id}')" style="accent-color: var(--primary-dark-teal);" />
                <span style="font-weight: 700; color: var(--primary-dark-teal); min-width: 20px;">${opt.id}.</span>
                <span style="font-size: 0.9rem; color: var(--text-dark); line-height: 1.35;">${escapeHtml(opt.text)}</span>
              </label>
            `;
          }).join('')}
        </div>
      </div>
    `;
  });

  html += '</div></div>';

  // ==========================================
  // Section B: True / False (6-10)
  // ==========================================
  html += `
    <div id="section-b" class="card" style="padding: 2rem;">
      <div style="border-bottom: 2px solid var(--border); padding-bottom: 0.85rem; margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
        <div>
          <span class="badge badge-uploaded" style="margin-bottom: 0.25rem;">SECTION B</span>
          <h3 style="font-size: 1.25rem; font-weight: 800; color: var(--text-dark); margin: 0;">True / False Statements</h3>
          <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 0.15rem;">Decide whether each statement is scientifically accurate (1 Mark Each)</p>
        </div>
        <span class="badge badge-completed">5 Marks Total</span>
      </div>

      <div style="display: flex; flex-direction: column; gap: 1.75rem;">
  `;

  (secs.section_b || []).forEach(q => {
    const selected = studentAnswers[String(q.id)] || '';
    html += `
      <div class="test-question-item" data-qid="${q.id}" style="border-bottom: 1px solid var(--border); padding-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
          <h4 style="font-size: 1rem; font-weight: 700; color: var(--text-dark); line-height: 1.4;">
            Q${q.id}. ${escapeHtml(q.question)}
          </h4>
          <span class="badge badge-uploaded" style="font-size: 0.72rem;">1 Mark</span>
        </div>

        <div style="display: flex; gap: 1rem;">
          <button type="button" class="btn ${selected === 'True' ? 'btn-primary' : 'btn-outline'} btn-sm tf-btn" data-qid="${q.id}" data-val="True" style="min-width: 110px;" onclick="handleAnswerSelect(${q.id}, 'True')">
            True
          </button>
          <button type="button" class="btn ${selected === 'False' ? 'btn-primary' : 'btn-outline'} btn-sm tf-btn" data-qid="${q.id}" data-val="False" style="min-width: 110px;" onclick="handleAnswerSelect(${q.id}, 'False')">
            False
          </button>
        </div>
      </div>
    `;
  });

  html += '</div></div>';

  // ==========================================
  // Section C: Fill in the Blanks (11-15)
  // ==========================================
  html += `
    <div id="section-c" class="card" style="padding: 2rem;">
      <div style="border-bottom: 2px solid var(--border); padding-bottom: 0.85rem; margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
        <div>
          <span class="badge badge-uploaded" style="margin-bottom: 0.25rem;">SECTION C</span>
          <h3 style="font-size: 1.25rem; font-weight: 800; color: var(--text-dark); margin: 0;">Fill in the Blanks</h3>
          <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 0.15rem;">Type the single appropriate term or key phrase for each blank (1 Mark Each)</p>
        </div>
        <span class="badge badge-completed">5 Marks Total</span>
      </div>

      <div style="display: flex; flex-direction: column; gap: 1.75rem;">
  `;

  (secs.section_c || []).forEach(q => {
    const val = studentAnswers[String(q.id)] || '';
    html += `
      <div class="test-question-item" data-qid="${q.id}" style="border-bottom: 1px solid var(--border); padding-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
          <h4 style="font-size: 1rem; font-weight: 700; color: var(--text-dark); line-height: 1.4;">
            Q${q.id}. ${escapeHtml(q.question)}
          </h4>
          <span class="badge badge-uploaded" style="font-size: 0.72rem;">1 Mark</span>
        </div>

        <div>
          <input type="text" class="form-control" placeholder="Type your answer here..." value="${escapeHtml(val)}" oninput="handleAnswerInput(${q.id}, this.value)" style="max-width: 420px;" />
        </div>
      </div>
    `;
  });

  html += '</div></div>';

  // ==========================================
  // Section D: Short Answer Questions (16-20)
  // ==========================================
  html += `
    <div id="section-d" class="card" style="padding: 2rem;">
      <div style="border-bottom: 2px solid var(--border); padding-bottom: 0.85rem; margin-bottom: 1.5rem; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem;">
        <div>
          <span class="badge badge-uploaded" style="margin-bottom: 0.25rem;">SECTION D</span>
          <h3 style="font-size: 1.25rem; font-weight: 800; color: var(--text-dark); margin: 0;">Short Answer Questions</h3>
          <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 0.15rem;">Provide clear, conceptual explanations. Evaluated semantically by AI (2 Marks Each)</p>
        </div>
        <span class="badge badge-completed" style="background: var(--gold); color: #fff;">10 Marks Total</span>
      </div>

      <div style="display: flex; flex-direction: column; gap: 2rem;">
  `;

  (secs.section_d || []).forEach(q => {
    const val = studentAnswers[String(q.id)] || '';
    html += `
      <div class="test-question-item" data-qid="${q.id}" style="border-bottom: 1px solid var(--border); padding-bottom: 1.5rem;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
          <h4 style="font-size: 1.05rem; font-weight: 700; color: var(--text-dark); line-height: 1.4;">
            Q${q.id}. ${escapeHtml(q.question)}
          </h4>
          <span class="badge badge-uploaded" style="font-size: 0.72rem; background: var(--light-cream); color: var(--gold); font-weight: 800;">2 Marks</span>
        </div>

        <div>
          <textarea class="form-control" rows="4" placeholder="Write your complete conceptual explanation here..." oninput="handleAnswerInput(${q.id}, this.value)" style="width: 100%; resize: vertical; line-height: 1.5;">${escapeHtml(val)}</textarea>
        </div>
      </div>
    `;
  });

  html += '</div></div>';

  container.innerHTML = html;
  updateAnsweredCounter();
}

function handleAnswerSelect(qid, value) {
  studentAnswers[String(qid)] = value;
  updateAnsweredCounter();

  // Update UI in-place to avoid re-rendering DOM and losing textarea focus
  const qItem = document.querySelector(`.test-question-item[data-qid="${qid}"]`);
  if (qItem) {
    // Section A options
    qItem.querySelectorAll('.quiz-option-label').forEach(lbl => {
      const radio = lbl.querySelector('input[type="radio"]');
      if (radio) {
        const isMatch = (radio.value === value);
        radio.checked = isMatch;
        lbl.classList.toggle('selected', isMatch);
        lbl.style.borderColor = isMatch ? 'var(--primary-dark-teal)' : 'var(--border)';
        lbl.style.background = isMatch ? 'var(--light-cream)' : 'var(--bg-card)';
      }
    });

    // Section B buttons
    qItem.querySelectorAll('.tf-btn').forEach(btn => {
      const isMatch = (btn.getAttribute('data-val') === value);
      btn.className = `btn ${isMatch ? 'btn-primary' : 'btn-outline'} btn-sm tf-btn`;
    });
  }

  triggerDebouncedDraftSave();
}

function handleAnswerInput(qid, value) {
  studentAnswers[String(qid)] = value;
  updateAnsweredCounter();
  triggerDebouncedDraftSave();
}

function updateAnsweredCounter() {
  const counterEl = document.getElementById('test-answered-counter');
  if (!counterEl) return;

  const count = Object.values(studentAnswers).filter(v => v !== null && v !== undefined && String(v).trim().length > 0).length;
  counterEl.innerText = `${count} of 20 Answered`;
}

function triggerDebouncedDraftSave() {
  if (saveDraftTimeout) clearTimeout(saveDraftTimeout);
  saveDraftTimeout = setTimeout(async () => {
    if (currentAttempt && currentAttempt.attempt_id) {
      try {
        await api.post(`/tests/attempts/${currentAttempt.attempt_id}/save-draft`, {
          answers: studentAnswers
        });
      } catch (e) {
        // Silently preserve locally
      }
    }
  }, 1000);
}

function scrollToSection(sectionId) {
  const el = document.getElementById(sectionId);
  if (el) {
    const yOffset = -90;
    const y = el.getBoundingClientRect().top + window.pageYOffset + yOffset;
    window.scrollTo({ top: y, behavior: 'smooth' });

    document.querySelectorAll('.section-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-section') === sectionId);
    });
  }
}

function startCountdownTimer(seconds) {
  if (timerInterval) clearInterval(timerInterval);
  remainingSeconds = Math.max(0, seconds);

  const timerText = document.getElementById('test-timer-text');
  const timerBadge = document.getElementById('test-timer-badge');

  function tick() {
    if (timerText) {
      timerText.innerText = `Time Remaining: ${formatTime(remainingSeconds)}`;
    }

    if (timerBadge) {
      if (remainingSeconds <= 60) {
        timerBadge.style.color = 'var(--danger)';
        timerBadge.style.borderColor = 'var(--danger)';
      } else if (remainingSeconds <= 300) {
        timerBadge.style.color = 'var(--gold)';
        timerBadge.style.borderColor = 'var(--gold)';
      } else {
        timerBadge.style.color = 'var(--text-dark)';
        timerBadge.style.borderColor = 'var(--border)';
      }
    }

    if (remainingSeconds <= 0) {
      clearInterval(timerInterval);
      handleTimeExpiredAutoSubmit();
    } else {
      remainingSeconds--;
    }
  }

  tick();
  timerInterval = setInterval(tick, 1000);
}

function handleTimeExpiredAutoSubmit() {
  Layout.showToast("Time is up. Your test has been submitted automatically.", 'warning');

  // Freeze all inputs to prevent edits
  document.querySelectorAll('#test-questions-container input, #test-questions-container textarea, #test-questions-container button').forEach(el => {
    el.disabled = true;
  });

  executeTestSubmission('automatic');
}

function promptSubmitTest() {
  const answeredCount = Object.values(studentAnswers).filter(v => v !== null && v !== undefined && String(v).trim().length > 0).length;
  const unansweredCount = 20 - answeredCount;

  const msgEl = document.getElementById('submit-confirm-message');
  const warnEl = document.getElementById('submit-unanswered-warning');

  if (unansweredCount > 0) {
    if (msgEl) msgEl.innerText = `You have completed ${answeredCount} of 20 questions. ${unansweredCount} question(s) remain unanswered.`;
    if (warnEl) warnEl.style.display = 'block';
  } else {
    if (msgEl) msgEl.innerText = `Great job! You have answered all 20 questions. Are you ready to submit your test?`;
    if (warnEl) warnEl.style.display = 'none';
  }

  const modal = document.getElementById('submit-confirm-modal');
  if (modal) {
    modal.classList.add('open');
    modal.classList.add('active');
  }
}

function closeSubmitConfirmModal() {
  const modal = document.getElementById('submit-confirm-modal');
  if (modal) {
    modal.classList.remove('open');
    modal.classList.remove('active');
  }
}

async function executeTestSubmission(submissionType = 'manual') {
  closeSubmitConfirmModal();
  if (!currentAttempt || isSubmitting) return;

  isSubmitting = true;
  if (timerInterval) clearInterval(timerInterval);

  Layout.showToast('Evaluating test paper...', 'info');

  try {
    const result = await api.post(`/tests/attempts/${currentAttempt.attempt_id}/submit`, {
      answers: studentAnswers,
      submission_type: submissionType
    });

    renderTestResult(result);
  } catch (err) {
    console.error('Submission failed:', err);
    Layout.showToast(err.message || 'Failed to submit test', 'error');
  } finally {
    isSubmitting = false;
  }
}

function renderTestResult(res) {
  document.getElementById('test-runner-section').style.display = 'none';
  document.getElementById('test-result-section').style.display = 'block';

  document.getElementById('result-test-title').innerText = res.test_title || '25-Mark Examination';
  document.getElementById('result-submission-badge').innerText = res.submission_message || 'Submitted by student.';
  if (res.submission_type === 'automatic') {
    document.getElementById('result-submission-badge').className = 'badge badge-failed';
  } else {
    document.getElementById('result-submission-badge').className = 'badge badge-completed';
  }

  // Score
  const gauge = document.getElementById('result-score-gauge');
  if (gauge) {
    gauge.innerText = `${Math.round(res.percentage)}%`;
    gauge.style.borderColor = res.percentage >= 80 ? 'var(--success)' : (res.percentage >= 50 ? 'var(--gold)' : 'var(--danger)');
  }

  document.getElementById('result-score-text').innerText = `${res.score} / 25`;
  const m = Math.floor(res.time_taken_seconds / 60);
  const s = res.time_taken_seconds % 60;
  document.getElementById('result-time-taken').innerText = m > 0 ? `${m}m ${s}s` : `${s}s`;
  document.getElementById('result-date').innerText = new Date(res.submitted_at || Date.now()).toLocaleDateString();

  // Section Breakdown
  const sec = res.section_scores || {};
  document.getElementById('result-sec-a').innerText = `${sec.section_a || 0} / 5`;
  document.getElementById('result-sec-b').innerText = `${sec.section_b || 0} / 5`;
  document.getElementById('result-sec-c').innerText = `${sec.section_c || 0} / 5`;
  document.getElementById('result-sec-d').innerText = `${sec.section_d || 0} / 10`;

  // Question Reviews & Mistake Analysis
  const reviewsList = document.getElementById('result-reviews-list');
  const allQuestions = res.all_questions_review || [];

  if (reviewsList) {
    reviewsList.innerHTML = allQuestions.map(q => {
      const isCorrect = q.is_correct;
      const isPartial = q.marks_obtained > 0 && q.marks_obtained < q.max_marks;
      const isSectionD = q.section && q.section.includes('Section D');
      const isUnanswered = q.student_answer === 'Not attempted' || !q.student_answer;
      const evalStatus = q.ai_evaluation || (isCorrect ? 'Correct' : (isPartial ? 'Partially Correct' : 'Incorrect'));

      if (isCorrect) {
        return `
          <div style="background: #F4FAF7; border: 1.5px solid #C8E8D9; border-radius: var(--radius-md); padding: 1.25rem;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.4rem;">
              <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-dark);">
                Q${q.question_id}. ${escapeHtml(q.question)}
              </div>
              <span class="badge badge-completed" style="font-weight: 800;">&check; Correct &bull; ${q.marks_obtained}/${q.max_marks} Marks</span>
            </div>
            <div style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 0.35rem;">
              Your Answer: <strong style="color: var(--success);">${escapeHtml(q.student_answer)}</strong>
            </div>
            <div style="font-size: 0.82rem; color: var(--text-dark); background: rgba(0,0,0,0.02); border-left: 3px solid var(--success); padding: 0.5rem 0.75rem; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; margin-top: 0.5rem;">
              <strong>Explanation:</strong> ${escapeHtml(q.feedback)}
            </div>
          </div>
        `;
      }

      // Wrong or Partially Correct
      const badgeClass = isPartial ? 'badge-processing' : 'badge-failed';
      const borderCol = isPartial ? '#F5E4B8' : '#F7D6DB';
      const bgCol = isPartial ? '#FFFDF8' : '#FFF9FA';

      return `
        <div style="background: ${bgCol}; border: 1.5px solid ${borderCol}; border-radius: var(--radius-md); padding: 1.25rem;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.6rem;">
            <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-dark);">
              Q${q.question_id}. ${escapeHtml(q.question)}
            </div>
            <span class="badge ${badgeClass}" style="font-weight: 800;">
              ${isPartial ? 'Partially Correct' : 'Incorrect'} &bull; ${q.marks_obtained}/${q.max_marks} Marks
            </span>
          </div>

          <div style="display: flex; flex-direction: column; gap: 0.4rem; font-size: 0.85rem; margin-bottom: 0.75rem;">
            <div>
              <span style="color: var(--text-secondary);">Your Answer:</span>
              <span style="color: ${isUnanswered ? 'var(--text-secondary)' : 'var(--danger)'}; font-weight: 600; margin-left: 0.3rem;">
                ${escapeHtml(q.student_answer)}
              </span>
            </div>
            <div>
              <span style="color: var(--text-secondary);">Correct / Model Answer:</span>
              <span style="color: var(--success); font-weight: 600; margin-left: 0.3rem;">
                ${escapeHtml(q.correct_answer)}
              </span>
            </div>
            <div>
              <span style="color: var(--text-secondary);">Marks:</span>
              <strong style="margin-left: 0.3rem;">${q.marks_obtained} / ${q.max_marks}</strong>
            </div>
          </div>

          ${isSectionD ? `
            <div style="font-size: 0.85rem; margin-bottom: 0.4rem;">
              <span style="color: var(--text-secondary);">AI Evaluation:</span>
              <span class="badge ${isPartial ? 'badge-processing' : 'badge-failed'}" style="margin-left: 0.3rem;">${escapeHtml(evalStatus)}</span>
            </div>
            ${q.important_keywords && q.important_keywords.length > 0 ? `
              <div style="font-size: 0.82rem; margin-bottom: 0.5rem; color: var(--text-secondary);">
                <span>Important keywords:</span>
                ${q.important_keywords.map(c => `<span class="badge badge-uploaded" style="margin-left: 0.25rem;">${escapeHtml(c)}</span>`).join('')}
              </div>
            ` : ''}
            <div style="background: rgba(0,0,0,0.03); border-left: 3px solid ${isPartial ? 'var(--gold)' : 'var(--danger)'}; padding: 0.65rem 0.85rem; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; font-size: 0.82rem; color: var(--text-dark); line-height: 1.45;">
              <strong>Why you received ${q.marks_obtained}/${q.max_marks} marks:</strong> ${escapeHtml(q.feedback)}
            </div>
          ` : `
            <div style="background: rgba(0,0,0,0.03); border-left: 3px solid var(--danger); padding: 0.65rem 0.85rem; border-radius: 0 var(--radius-sm) var(--radius-sm) 0; font-size: 0.82rem; color: var(--text-dark); line-height: 1.45;">
              <strong>Explanation:</strong> ${escapeHtml(q.feedback)}
            </div>
          `}
        </div>
      `;
    }).join('');
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
}
