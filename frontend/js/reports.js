/**
 * STUDIORA — Reports & Analytics Controller
 * Displays learning growth charts, performance metrics, and attempt history breakdown.
 */

let reportData = null;

document.addEventListener('DOMContentLoaded', async () => {
  Layout.init('reports');

  await loadReports();
});

async function loadReports() {
  try {
    const [summary, growth] = await Promise.all([
      api.get('/reports/summary'),
      api.get('/reports/growth-chart')
    ]);

    reportData = summary;
    renderMetrics(summary);
    renderGrowthCanvas(growth);
    renderAttemptsTable(summary.recent_attempts || []);
  } catch (err) {
    console.error('Failed to load reports:', err);
    Layout.showToast('Failed to load performance analytics', 'error');
  }
}

function renderMetrics(summary) {
  const avgEl = document.getElementById('report-avg-score');
  const attemptsEl = document.getElementById('report-total-attempts');
  const highEl = document.getElementById('report-highest-score');
  const accEl = document.getElementById('report-accuracy-rate');

  const quizzesCount = summary.total_attempts !== undefined ? summary.total_attempts : (summary.quizzes_completed || 0);
  const highest = summary.highest_score !== undefined ? summary.highest_score : (summary.max_score || 0);
  const avg = summary.average_score !== undefined ? summary.average_score : 0;
  const acc = summary.accuracy_percentage !== undefined ? summary.accuracy_percentage : 0;

  if (avgEl) avgEl.textContent = `${Math.round(avg)}%`;
  if (attemptsEl) attemptsEl.textContent = quizzesCount;
  if (highEl) highEl.textContent = `${Math.round(highest)}%`;
  if (accEl) accEl.textContent = `${Math.round(acc)}%`;
}

function renderGrowthCanvas(data) {
  const canvas = document.getElementById('reports-growth-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const width = canvas.parentElement.clientWidth;
  const height = 240;
  canvas.width = width;
  canvas.height = height;

  ctx.clearRect(0, 0, width, height);

  if (!data || data.length === 0) {
    ctx.fillStyle = '#65706D';
    ctx.font = '14px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Complete quizzes to track your score progression over time.', width / 2, height / 2);
    return;
  }

  // Draw grid lines
  ctx.strokeStyle = '#DDD4C5';
  ctx.lineWidth = 1;
  const steps = 4;
  for (let i = 0; i <= steps; i++) {
    const y = 25 + (i * (height - 55)) / steps;
    ctx.beginPath();
    ctx.moveTo(40, y);
    ctx.lineTo(width - 20, y);
    ctx.stroke();

    ctx.fillStyle = '#9DA8A5';
    ctx.font = '11px Inter, sans-serif';
    ctx.textAlign = 'right';
    const labelVal = Math.round(100 - (i * 100) / steps);
    ctx.fillText(`${labelVal}%`, 35, y + 4);
  }

  // Points
  const points = data.map((d, index) => {
    const x = data.length === 1 
      ? width / 2 
      : 40 + (index / (data.length - 1)) * (width - 70);
    const y = height - 30 - ((d.score_percentage || d.score || 0) / 100) * (height - 55);
    return { x, y, score: d.score_percentage || d.score || 0, date: d.date || `Q${index + 1}` };
  });

  // Gradient fill
  const gradient = ctx.createLinearGradient(0, 25, 0, height - 30);
  gradient.addColorStop(0, 'rgba(198, 154, 82, 0.40)');
  gradient.addColorStop(1, 'rgba(247, 241, 230, 0.05)');

  ctx.beginPath();
  ctx.moveTo(points[0].x, height - 30);
  ctx.lineTo(points[0].x, points[0].y);

  for (let i = 0; i < points.length - 1; i++) {
    const xc = (points[i].x + points[i + 1].x) / 2;
    const yc = (points[i].y + points[i + 1].y) / 2;
    ctx.quadraticCurveTo(points[i].x, points[i].y, xc, yc);
  }
  if (points.length > 1) {
    ctx.lineTo(points[points.length - 1].x, points[points.length - 1].y);
  }
  ctx.lineTo(points[points.length - 1].x, height - 30);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  // Line
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 0; i < points.length - 1; i++) {
    const xc = (points[i].x + points[i + 1].x) / 2;
    const yc = (points[i].y + points[i + 1].y) / 2;
    ctx.quadraticCurveTo(points[i].x, points[i].y, xc, yc);
  }
  if (points.length > 1) {
    ctx.lineTo(points[points.length - 1].x, points[points.length - 1].y);
  }
  ctx.strokeStyle = '#123F3F';
  ctx.lineWidth = 2.5;
  ctx.stroke();

  // Dots
  points.forEach((p) => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = '#FFFFFF';
    ctx.fill();
    ctx.strokeStyle = '#C98462';
    ctx.lineWidth = 2;
    ctx.stroke();
  });
}

function renderAttemptsTable(attempts) {
  const container = document.getElementById('attempts-table-body');
  const emptyState = document.getElementById('attempts-empty-state');
  if (!container) return;

  if (!attempts || attempts.length === 0) {
    container.innerHTML = '';
    if (emptyState) emptyState.style.display = 'block';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';

  container.innerHTML = attempts.map((att) => {
    const isTest = att.attempt_type === 'test_paper';
    const typeLabel = isTest ? 'Test Paper' : 'Quiz';
    const typeBadgeClass = isTest ? 'badge-completed' : 'badge-uploaded';

    const pct = Math.round(att.percentage || 0);
    let pctBadge = 'badge-completed';
    if (pct < 50) pctBadge = 'badge-failed';
    else if (pct < 75) pctBadge = 'badge-processing';

    const mins = Math.floor((att.time_taken_seconds || 0) / 60);
    const secs = (att.time_taken_seconds || 0) % 60;
    const timeStr = mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;

    const rawDate = att.created_at ? new Date(att.created_at) : new Date();
    const day = String(rawDate.getDate()).padStart(2, '0');
    const month = String(rawDate.getMonth() + 1).padStart(2, '0');
    const year = rawDate.getFullYear();
    const dateFormatted = `${day}/${month}/${year}`;

    return `
      <tr style="border-bottom: 1px solid var(--border-light);">
        <td style="padding: 1.1rem 1rem;">
          <div style="font-weight: 600; font-size: 0.92rem; color: var(--text-dark);">
            ${escapeHtml(att.quiz_title || (isTest ? 'Test Paper' : 'Quiz Assessment'))}
          </div>
        </td>
        <td style="padding: 1.1rem 1rem;">
          <span class="badge ${typeBadgeClass}">${typeLabel}</span>
        </td>
        <td style="padding: 1.1rem 1rem; font-size: 0.85rem; color: var(--text-secondary);">
          ${dateFormatted}
        </td>
        <td style="padding: 1.1rem 1rem; font-weight: 600; font-size: 0.92rem;">
          ${att.score} / ${att.total_questions}
        </td>
        <td style="padding: 1.1rem 1rem;">
          <span class="badge ${pctBadge}">${pct}%</span>
        </td>
        <td style="padding: 1.1rem 1rem; font-size: 0.85rem; color: var(--text-secondary);">
          ${timeStr}
        </td>
        <td style="padding: 1.1rem 1rem; text-align: right;">
          <button class="btn btn-outline btn-sm" onclick="openAttemptModal(${att.id}, '${att.attempt_type || 'quiz'}')">
            Review Answers
          </button>
        </td>
      </tr>
    `;
  }).join('');
}

async function openAttemptModal(attemptId, attemptType = 'quiz') {
  const modal = document.getElementById('attempt-detail-modal');
  if (!modal) return;

  try {
    if (attemptType === 'test_paper') {
      const attempt = await api.get(`/tests/attempts/${attemptId}/result`);
      document.getElementById('attempt-modal-title').textContent = attempt.test_title || '25-Mark Test Review';
      document.getElementById('attempt-modal-score').textContent = `${attempt.score} / ${attempt.max_marks} (${Math.round(attempt.percentage)}%) • ${attempt.submission_message}`;

      const breakdownContainer = document.getElementById('attempt-breakdown-container');
      const questions = attempt.all_questions_review || [];

      breakdownContainer.innerHTML = questions.map((q, idx) => {
        const isCorrect = Boolean(q.is_correct);
        const isPartial = q.marks_obtained > 0 && q.marks_obtained < q.max_marks;
        const isSectionD = q.section && q.section.includes('Section D');
        const evalStatus = q.ai_evaluation || (isCorrect ? 'Correct' : (isPartial ? 'Partially Correct' : 'Incorrect'));

        return `
          <div style="border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 1.25rem; margin-bottom: 1rem; background: var(--card-white);">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
              <span style="font-size: 0.82rem; font-weight: 700; color: var(--primary-dark-teal);">${escapeHtml(q.section || `Question ${idx + 1}`)}</span>
              <span class="badge ${isCorrect ? 'badge-completed' : (isPartial ? 'badge-processing' : 'badge-failed')}">
                ${isCorrect ? '✓ Correct' : (isPartial ? 'Partial' : 'Needs Review')} &bull; ${q.marks_obtained}/${q.max_marks} Marks
              </span>
            </div>
            <p style="font-size: 0.95rem; font-weight: 600; color: var(--text-dark); margin-bottom: 0.75rem;">
              Q${q.question_id}. ${escapeHtml(extractCleanText(q.question))}
            </p>
            <div style="font-size: 0.85rem; margin-bottom: 0.35rem;">
              <span style="color: var(--text-secondary);">Your Answer: </span>
              <strong style="color: ${isCorrect ? 'var(--success)' : (isPartial ? 'var(--gold)' : 'var(--danger)')};">
                ${escapeHtml(extractCleanText(q.student_answer))}
              </strong>
            </div>
            ${!isCorrect ? `
              <div style="font-size: 0.85rem; margin-bottom: 0.35rem;">
                <span style="color: var(--text-secondary);">Correct / Model Answer: </span>
                <strong style="color: var(--success);">${escapeHtml(extractCleanText(q.correct_answer))}</strong>
              </div>
            ` : ''}
            <div style="font-size: 0.85rem; margin-bottom: 0.35rem;">
              <span style="color: var(--text-secondary);">Marks: </span>
              <strong>${q.marks_obtained} / ${q.max_marks}</strong>
            </div>
            ${isSectionD ? `
              <div style="font-size: 0.85rem; margin-bottom: 0.35rem;">
                <span style="color: var(--text-secondary);">AI Evaluation: </span>
                <span class="badge ${isCorrect ? 'badge-completed' : (isPartial ? 'badge-processing' : 'badge-failed')}">${escapeHtml(evalStatus)}</span>
              </div>
              ${q.important_keywords && q.important_keywords.length > 0 ? `
                <div style="font-size: 0.82rem; margin-bottom: 0.35rem; color: var(--text-secondary);">
                  <span>Important keywords: </span>
                  ${q.important_keywords.map(kw => `<span class="badge badge-uploaded" style="margin-right: 0.25rem;">${escapeHtml(kw)}</span>`).join('')}
                </div>
              ` : ''}
              <div style="font-size: 0.82rem; color: var(--text-dark); background: var(--light-cream); border: 1px solid var(--border); padding: 0.65rem 0.85rem; border-radius: var(--radius-md); margin-top: 0.5rem;">
                <strong>Why you received ${q.marks_obtained}/${q.max_marks} marks: </strong>${escapeHtml(extractCleanText(q.feedback))}
              </div>
            ` : `
              <div style="font-size: 0.82rem; color: var(--text-dark); background: var(--light-cream); border: 1px solid var(--border); padding: 0.65rem 0.85rem; border-radius: var(--radius-md); margin-top: 0.5rem;">
                <strong>Explanation: </strong>${escapeHtml(extractCleanText(q.feedback))}
              </div>
            `}
          </div>
        `;
      }).join('');

      modal.classList.add('open');
      return;
    }

    const attempt = await api.get(`/quizzes/attempts/${attemptId}`);
    
    document.getElementById('attempt-modal-title').textContent = attempt.quiz_title || 'Quiz Review';
    document.getElementById('attempt-modal-score').textContent = `${attempt.score} / ${attempt.total_questions} (${Math.round(attempt.percentage)}%)`;

    const breakdownContainer = document.getElementById('attempt-breakdown-container');
    const answers = attempt.answers || attempt.all_answers || attempt.questions_to_review || [];

    breakdownContainer.innerHTML = answers.map((ans, idx) => {
      const isCorrect = Boolean(ans.is_correct);
      const qText = ans.question_text || ans.question || '';
      const userAns = ans.user_answer ? ans.user_answer : `Option ${ans.selected_option || ''}`;
      const correctAns = ans.correct_answer ? ans.correct_answer : `Option ${ans.correct_option || ''}`;
      const expl = ans.explanation || '';
      return `
        <div style="border: 1px solid var(--border); border-radius: var(--radius-lg); padding: 1.25rem; margin-bottom: 1rem; background: var(--card-white);">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
            <span style="font-size: 0.82rem; font-weight: 700; color: var(--primary-dark-teal);">Question ${idx + 1}</span>
            <span class="badge ${isCorrect ? 'badge-completed' : 'badge-failed'}">
              ${isCorrect ? '✓ Correct' : '✗ Needs Review'}
            </span>
          </div>
          <p style="font-size: 0.95rem; font-weight: 600; color: var(--text-dark); margin-bottom: 0.75rem;">
            ${escapeHtml(extractCleanText(qText))}
          </p>
          <div style="font-size: 0.85rem; margin-bottom: 0.35rem;">
            <span style="color: var(--text-secondary);">Your Answer: </span>
            <strong style="color: ${isCorrect ? 'var(--success)' : 'var(--error)'};">
              ${escapeHtml(extractCleanText(userAns))}
            </strong>
          </div>
          ${!isCorrect ? `
            <div style="font-size: 0.85rem; margin-bottom: 0.35rem;">
              <span style="color: var(--text-secondary);">Correct Answer: </span>
              <strong style="color: var(--success);">${escapeHtml(extractCleanText(correctAns))}</strong>
            </div>
          ` : ''}
          <div style="font-size: 0.82rem; color: var(--text-dark); background: var(--light-cream); border: 1px solid var(--border); padding: 0.65rem 0.85rem; border-radius: var(--radius-md); margin-top: 0.5rem;">
            <strong>Why? </strong>${escapeHtml(extractCleanText(expl))}
          </div>
        </div>
      `;
    }).join('');

    modal.classList.add('open');
  } catch (err) {
    Layout.showToast('Failed to load attempt details', 'error');
  }
}

function closeAttemptModal() {
  const modal = document.getElementById('attempt-detail-modal');
  if (modal) modal.classList.remove('open');
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
