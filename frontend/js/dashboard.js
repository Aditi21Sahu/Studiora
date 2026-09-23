/**
 * STUDIORA — Dashboard Controller
 * Loads user statistics, renders HTML5 canvas progress chart, and displays recent activity.
 */

document.addEventListener('DOMContentLoaded', async () => {
  Layout.init('dashboard');

  await loadDashboard();
});

async function loadDashboard() {
  try {
    const [stats, growthData, activities, materials] = await Promise.all([
      api.get('/reports/dashboard-stats'),
      api.get('/reports/growth-chart'),
      api.get('/reports/recent-activity'),
      api.get('/materials/')
    ]);

    renderHeroGreeting();
    renderStats(stats);
    renderGrowthChart(growthData);
    renderRecentActivity(activities);
    renderRecentMaterials(materials);
  } catch (err) {
    console.error('Failed to load dashboard data:', err);
  }
}

function renderHeroGreeting() {
  const user = api.getUser();
  const firstName = user && user.full_name ? user.full_name.split(' ')[0] : 'Student';
  
  const hour = new Date().getHours();
  let greeting = 'Good evening';
  if (hour < 12) greeting = 'Good morning';
  else if (hour < 17) greeting = 'Good afternoon';

  const greetingEl = document.getElementById('hero-greeting-text');
  if (greetingEl) {
    greetingEl.textContent = `${greeting}, ${firstName}!`;
  }
}

function renderStats(stats) {
  const matEl = document.getElementById('stat-materials-count');
  const noteEl = document.getElementById('stat-notes-count');
  const quizEl = document.getElementById('stat-quizzes-count');
  const avgEl = document.getElementById('stat-average-score');

  const matBadge = document.getElementById('stat-materials-badge');
  const noteBadge = document.getElementById('stat-notes-badge');
  const quizBadge = document.getElementById('stat-quizzes-badge');
  const avgBadge = document.getElementById('stat-average-badge');

  const matVal = stats.study_materials_count ?? 0;
  const noteVal = stats.notes_count ?? 0;
  const quizVal = stats.quizzes_count ?? 0;
  const avgVal = `${Math.round(stats.average_score ?? 0)}%`;

  if (matEl) matEl.textContent = matVal;
  if (noteEl) noteEl.textContent = noteVal;
  if (quizEl) quizEl.textContent = quizVal;
  if (avgEl) avgEl.textContent = avgVal;

  if (matBadge) matBadge.textContent = matVal;
  if (noteBadge) noteBadge.textContent = noteVal;
  if (quizBadge) quizBadge.textContent = quizVal;
  if (avgBadge) avgBadge.textContent = avgVal;
}

function renderGrowthChart(data) {
  const canvas = document.getElementById('growth-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const width = canvas.parentElement.clientWidth;
  const height = 220;
  canvas.width = width;
  canvas.height = height;

  ctx.clearRect(0, 0, width, height);

  // If no attempts yet, display a subtle placeholder message
  if (!data || data.length === 0) {
    ctx.fillStyle = '#65706D';
    ctx.font = '14px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Take your first quiz to visualize your learning growth!', width / 2, height / 2);
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
    return { x, y, score: d.score_percentage || d.score || 0, date: d.date || `W${index + 1}` };
  });

  // Create warm gold/terracotta gradient fill
  const gradient = ctx.createLinearGradient(0, 25, 0, height - 30);
  gradient.addColorStop(0, 'rgba(198, 154, 82, 0.40)');
  gradient.addColorStop(1, 'rgba(247, 241, 230, 0.05)');

  // Draw area
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

  // Draw smooth line
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
  ctx.strokeStyle = '#C98462';
  ctx.lineWidth = 2.5;
  ctx.stroke();

  // Draw circular dots
  points.forEach((p) => {
    ctx.beginPath();
    ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2);
    ctx.fillStyle = '#FFFFFF';
    ctx.fill();
    ctx.strokeStyle = '#123F3F';
    ctx.lineWidth = 2;
    ctx.stroke();
  });
}

function renderRecentActivity(activities) {
  const container = document.getElementById('recent-activity-list');
  if (!container) return;

  if (!activities || activities.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 2rem; color: var(--text-secondary); font-size: 0.88rem;">
        No recent activity logged yet.
      </div>
    `;
    return;
  }

  container.innerHTML = activities.slice(0, 4).map((act) => `
    <div style="display: flex; align-items: center; gap: 0.85rem; padding: 0.75rem 0; border-bottom: 1px solid var(--border-light);">
      <div style="width: 34px; height: 34px; border-radius: var(--radius-full); background: var(--light-cream); border: 1px solid var(--border); color: var(--primary-dark-teal); display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
      </div>
      <div style="flex: 1; min-width: 0;">
        <div style="font-size: 0.88rem; font-weight: 600; color: var(--text-dark); line-height: 1.2;">
          ${act.title}
        </div>
        <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 0.15rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
          ${act.description || ''}
        </div>
      </div>
      <div style="font-size: 0.72rem; color: var(--text-secondary); white-space: nowrap;">
        ${act.created_at ? new Date(act.created_at).toLocaleDateString() : 'recently'}
      </div>
    </div>
  `).join('');
}

function renderRecentMaterials(materials) {
  const container = document.getElementById('recent-materials-list');
  if (!container) return;

  if (!materials || materials.length === 0) {
    container.innerHTML = `
      <div class="card" style="text-align: center; padding: 2.5rem 1.5rem; grid-column: 1 / -1;">
        <div style="width: 44px; height: 44px; border-radius: var(--radius-full); background: var(--light-teal); color: var(--primary-dark-teal); display: flex; align-items: center; justify-content: center; margin: 0 auto 0.85rem;">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        </div>
        <h4 style="font-size: 1rem; font-weight: 700; color: var(--text-dark);">No study materials added yet</h4>
        <p style="font-size: 0.85rem; color: var(--text-secondary); margin: 0.4rem 0 1.25rem;">
          Upload a PDF, DOCX, TXT or paste a YouTube link to generate your first study aid!
        </p>
        <a href="/study-material.html" class="btn btn-primary btn-sm">Add Your First Material</a>
      </div>
    `;
    return;
  }

  container.innerHTML = materials.slice(0, 3).map((mat) => {
    const badgeClass = mat.file_type === 'pdf' ? 'badge-pdf' : mat.file_type === 'docx' ? 'badge-docx' : mat.file_type === 'video' ? 'badge-video' : 'badge-txt';
    return `
      <div class="card card-hover" style="display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
            <span class="badge ${badgeClass}">${mat.file_type.toUpperCase()}</span>
            <span class="badge badge-${mat.status || 'completed'}">${mat.status || 'ready'}</span>
          </div>
          <h4 style="font-size: 0.95rem; font-weight: 700; color: var(--text-dark); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.35;">
            ${mat.title}
          </h4>
          <p style="font-size: 0.78rem; color: var(--text-secondary); margin-top: 0.35rem;">
            ${mat.file_size || 'Material'} &bull; ${new Date(mat.created_at).toLocaleDateString()}
          </p>
        </div>
        <div style="margin-top: 1.25rem; padding-top: 0.85rem; border-top: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between;">
          <a href="/study-material.html" style="font-size: 0.82rem; font-weight: 600; color: var(--primary-dark-teal);">Open Material &rarr;</a>
          <a href="/notes.html" style="font-size: 0.82rem; font-weight: 600; color: var(--text-secondary);">View Notes</a>
        </div>
      </div>
    `;
  }).join('');
}
