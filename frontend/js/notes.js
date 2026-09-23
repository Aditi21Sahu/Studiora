/**
 * STUDIORA — Notes Controller
 * Renders notes library, structured study guides, PDF/TXT downloads, and quiz triggers.
 */

let allNotes = [];
let activeNote = null;

document.addEventListener('DOMContentLoaded', async () => {
  Layout.init('notes');

  await loadNotes();

  // Check URL parameters for direct note view
  const urlParams = new URLSearchParams(window.location.search);
  const noteId = urlParams.get('id');
  if (noteId) {
    await openNoteViewer(noteId);
  }
});

async function loadNotes() {
  const container = document.getElementById('notes-grid');
  const emptyState = document.getElementById('notes-empty-state');
  if (!container) return;

  try {
    allNotes = await api.get('/notes/');
    renderNotes(allNotes);
  } catch (err) {
    console.error('Failed to fetch notes:', err);
    Layout.showToast('Failed to load notes', 'error');
  }
}

function renderNotes(notes) {
  const container = document.getElementById('notes-grid');
  const emptyState = document.getElementById('notes-empty-state');
  if (!container) return;

  if (!notes || notes.length === 0) {
    container.innerHTML = '';
    if (emptyState) emptyState.style.display = 'block';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';

  container.innerHTML = notes.map((n) => `
    <div class="card card-hover" style="display: flex; flex-direction: column; justify-content: space-between;">
      <div>
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">
          <span class="badge badge-uploaded">AI Study Guide</span>
          <span style="font-size: 0.72rem; color: var(--text-light); font-weight: 500;">
            ${n.created_at ? new Date(n.created_at).toLocaleDateString() : 'Recent'}
          </span>
        </div>
        <h3 style="font-size: 1.1rem; font-weight: 700; color: var(--text-main); line-height: 1.35; margin-bottom: 0.5rem; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">
          ${escapeHtml(n.title)}
        </h3>
        <p style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;">
          ${escapeHtml(n.summary || 'Comprehensive structured study notes.')}
        </p>
      </div>

      <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--border-light); display: flex; align-items: center; justify-content: space-between;">
        <button class="btn btn-primary btn-sm" onclick="openNoteViewer(${n.id})">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>
          Read Notes
        </button>
        <div style="display: flex; align-items: center; gap: 0.4rem;">
          <a href="/quizzes.html?note_id=${n.id}" class="btn btn-secondary btn-sm" title="Generate Quiz from this note">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
          </a>
          <button class="btn btn-danger btn-sm" onclick="handleDeleteNote(${n.id})" title="Delete note">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </div>
      </div>
    </div>
  `).join('');
}

async function openNoteViewer(id) {
  const modal = document.getElementById('note-viewer-modal');
  if (!modal) return;

  try {
    const note = await api.get(`/notes/${id}`);
    activeNote = note;

    document.getElementById('modal-note-title').textContent = note.title;
    document.getElementById('modal-note-summary').textContent = note.summary || '';

    // Key points
    const keyPointsEl = document.getElementById('modal-note-keypoints');
    if (keyPointsEl) {
      const pts = note.key_points || [];
      keyPointsEl.innerHTML = pts.map((pt) => `
        <li style="margin-bottom: 0.5rem; display: flex; align-items: flex-start; gap: 0.5rem;">
          <span style="color: var(--primary); font-size: 1.1rem; line-height: 1;">&bull;</span>
          <span style="font-size: 0.92rem; color: var(--text-main);">${escapeHtml(pt)}</span>
        </li>
      `).join('');
    }

    // Sections
    const sectionsEl = document.getElementById('modal-note-sections');
    if (sectionsEl) {
      const secs = note.sections || [];
      sectionsEl.innerHTML = secs.map((sec) => `
        <div style="margin-bottom: 1.75rem;">
          <h4 style="font-size: 1.05rem; font-weight: 700; color: var(--primary-dark); margin-bottom: 0.5rem;">
            ${escapeHtml(sec.heading || sec.title || 'Section')}
          </h4>
          <p style="font-size: 0.92rem; color: var(--text-main); line-height: 1.6; white-space: pre-line;">
            ${escapeHtml(sec.content || sec.text || '')}
          </p>
        </div>
      `).join('');
    }

    // Important Terms
    const termsEl = document.getElementById('modal-note-terms');
    if (termsEl) {
      const terms = note.important_terms || [];
      termsEl.innerHTML = terms.map((t) => {
        const term = typeof t === 'string' ? t : t.term;
        const def = typeof t === 'object' ? t.definition : '';
        return `
          <div style="background: var(--primary-subtle); border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 0.75rem 1rem;">
            <span style="font-weight: 700; color: var(--primary); font-size: 0.88rem;">${escapeHtml(term)}</span>
            ${def ? `<p style="font-size: 0.82rem; color: var(--text-muted); margin-top: 0.2rem;">${escapeHtml(def)}</p>` : ''}
          </div>
        `;
      }).join('');
    }

    // Revision Checklist
    const revisionEl = document.getElementById('modal-note-revision');
    if (revisionEl) {
      const revs = note.revision_points || [];
      revisionEl.innerHTML = revs.map((r, idx) => `
        <div style="display: flex; align-items: center; gap: 0.6rem; padding: 0.4rem 0;">
          <input type="checkbox" id="rev-${idx}" style="accent-color: var(--primary); width: 16px; height: 16px;" />
          <label for="rev-${idx}" style="font-size: 0.88rem; color: var(--text-main); cursor: pointer;">
            ${escapeHtml(r)}
          </label>
        </div>
      `).join('');
    }

    // Setup action buttons in modal
    const pdfBtn = document.getElementById('download-pdf-btn');
    const txtBtn = document.getElementById('download-txt-btn');
    const quizBtn = document.getElementById('quiz-from-note-btn');

    if (pdfBtn) {
      pdfBtn.onclick = () => downloadNote(note.id, 'pdf', note.title);
    }
    if (txtBtn) {
      txtBtn.onclick = () => downloadNote(note.id, 'txt', note.title);
    }
    if (quizBtn) {
      quizBtn.onclick = () => {
        window.location.href = `/quizzes.html?note_id=${note.id}`;
      };
    }

    modal.classList.add('open');
  } catch (err) {
    Layout.showToast('Failed to open note', 'error');
  }
}

function closeNoteViewer() {
  const modal = document.getElementById('note-viewer-modal');
  if (modal) modal.classList.remove('open');
}

async function downloadNote(noteId, format, title) {
  try {
    const token = api.getToken();
    const url = `/api/notes/${noteId}/download/${format}`;
    
    const response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) throw new Error('Download failed');

    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    const cleanTitle = (title || 'study_notes').replace(/[^a-zA-Z0-9_-]/g, '_');
    a.download = `${cleanTitle}.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(downloadUrl);
    Layout.showToast(`Downloaded ${format.toUpperCase()} successfully!`, 'success');
  } catch (err) {
    Layout.showToast(`Failed to download ${format.toUpperCase()}`, 'error');
  }
}

async function handleDeleteNote(id) {
  if (!confirm('Are you sure you want to delete this study guide?')) return;

  try {
    await api.delete(`/notes/${id}`);
    Layout.showToast('Note deleted successfully', 'info');
    await loadNotes();
  } catch (err) {
    Layout.showToast(err.message || 'Failed to delete note', 'error');
  }
}

function escapeHtml(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
