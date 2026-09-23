/**
 * STUDIORA — Study Material Controller
 * Handles document/video uploads, YouTube URL processing, previews, and note triggers.
 */

let allMaterials = [];

document.addEventListener('DOMContentLoaded', async () => {
  Layout.init('materials');

  initUploadHandlers();
  initUrlHandler();
  await loadMaterials();
});

async function loadMaterials() {
  const container = document.getElementById('materials-table-body');
  if (!container) return;

  try {
    allMaterials = await api.get('/materials/');
    renderMaterials(allMaterials);
  } catch (err) {
    console.error('Failed to load materials:', err);
    Layout.showToast('Failed to load study materials', 'error');
  }
}

function renderMaterials(materials) {
  const container = document.getElementById('materials-table-body');
  const emptyState = document.getElementById('materials-empty-state');
  if (!container) return;

  if (!materials || materials.length === 0) {
    container.innerHTML = '';
    if (emptyState) emptyState.style.display = 'block';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';

  container.innerHTML = materials.map((mat) => {
    const isYouTube = mat.source_type === 'youtube' || (mat.file_path && mat.file_path.includes('youtube'));
    let badgeClass = 'badge-txt';
    let typeLabel = mat.file_type.toUpperCase();

    if (isYouTube) {
      badgeClass = 'badge-youtube';
      typeLabel = 'YOUTUBE';
    } else if (mat.file_type === 'pdf') {
      badgeClass = 'badge-pdf';
    } else if (mat.file_type === 'docx') {
      badgeClass = 'badge-docx';
    } else if (mat.file_type === 'video') {
      badgeClass = 'badge-video';
    }

    const canGenerate = mat.status === 'completed';

    return `
      <tr style="border-bottom: 1px solid var(--border-light);">
        <td style="padding: 1.1rem 1rem;">
          <div style="display: flex; align-items: center; gap: 0.85rem;">
            <span class="badge ${badgeClass}">${typeLabel}</span>
            <div>
              <div style="font-weight: 600; font-size: 0.92rem; color: var(--text-main); line-height: 1.3;">
                ${escapeHtml(mat.title)}
              </div>
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.15rem;">
                ${mat.file_size || 'Ready'}
              </div>
            </div>
          </div>
        </td>
        <td style="padding: 1.1rem 1rem;">
          <span class="badge badge-${mat.status || 'completed'}">
            ${mat.status || 'completed'}
          </span>
        </td>
        <td style="padding: 1.1rem 1rem; font-size: 0.85rem; color: var(--text-muted);">
          ${mat.created_at ? new Date(mat.created_at).toLocaleDateString() : 'Recent'}
        </td>
        <td style="padding: 1.1rem 1rem; text-align: right;">
          <div style="display: flex; align-items: center; justify-content: flex-end; gap: 0.5rem;">
            ${canGenerate ? `
              <button class="btn btn-secondary btn-sm" onclick="handleGenerateNotes(${mat.id}, this)" title="Generate AI Study Notes">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                Generate Notes
              </button>
            ` : ''}
            <button class="btn btn-outline btn-sm" onclick="openPreviewModal(${mat.id})" title="Preview Content">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
            </button>
            <button class="btn btn-danger btn-sm" onclick="handleDeleteMaterial(${mat.id})" title="Delete">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

function initUploadHandlers() {
  const dropzone = document.getElementById('upload-dropzone');
  const fileInput = document.getElementById('file-input');

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('active');
    });
  });

  ['dragleave', 'drop'].forEach((eventName) => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('active');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      uploadFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files[0]) {
      uploadFile(fileInput.files[0]);
      fileInput.value = '';
    }
  });
}

async function uploadFile(file) {
  const customTitleInput = document.getElementById('upload-title-input');
  const customTitle = customTitleInput ? customTitleInput.value.trim() : '';

  const progressWrap = document.getElementById('upload-progress-wrap');
  const progressText = document.getElementById('upload-progress-text');
  if (progressWrap) progressWrap.style.display = 'block';
  if (progressText) progressText.textContent = `Uploading & parsing "${file.name}"...`;

  const formData = new FormData();
  formData.append('file', file);
  if (customTitle) {
    formData.append('custom_title', customTitle);
  }

  try {
    const res = await api.post('/materials/upload', formData, true);
    Layout.showToast(`Uploaded "${res.title}" successfully!`, 'success');
    if (customTitleInput) customTitleInput.value = '';
    await loadMaterials();
  } catch (err) {
    Layout.showToast(err.message || 'Failed to upload material', 'error');
  } finally {
    if (progressWrap) progressWrap.style.display = 'none';
  }
}

function initUrlHandler() {
  const form = document.getElementById('url-submit-form');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const urlInput = document.getElementById('youtube-url-input');
    const titleInput = document.getElementById('youtube-title-input');
    const submitBtn = document.getElementById('youtube-submit-btn');

    const url = urlInput ? urlInput.value.trim() : '';
    const title = titleInput ? titleInput.value.trim() : '';

    if (!url) return;

    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerText = 'Extracting content...';
    }

    try {
      const res = await api.post('/materials/url', { url, title: title || undefined });
      Layout.showToast(`Processed YouTube content: "${res.title}"!`, 'success');
      if (urlInput) urlInput.value = '';
      if (titleInput) titleInput.value = '';
      await loadMaterials();
    } catch (err) {
      Layout.showToast(err.message || 'Failed to process YouTube link', 'error');
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerText = 'Process Link';
      }
    }
  });
}

async function handleGenerateNotes(materialId, btn) {
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<span class="animate-pulse-glow">Generating...</span>';
  }

  try {
    const note = await api.post(`/notes/generate/${materialId}`);
    Layout.showToast('Study notes created successfully!', 'success');
    setTimeout(() => {
      window.location.href = `/notes.html?id=${note.id}`;
    }, 500);
  } catch (err) {
    Layout.showToast(err.message || 'Failed to generate study notes', 'error');
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = 'Generate Notes';
    }
  }
}

async function handleDeleteMaterial(id) {
  if (!confirm('Are you sure you want to delete this study material and all its generated notes?')) return;

  try {
    await api.delete(`/materials/${id}`);
    Layout.showToast('Study material deleted', 'info');
    await loadMaterials();
  } catch (err) {
    Layout.showToast(err.message || 'Failed to delete material', 'error');
  }
}

async function openPreviewModal(id) {
  const modal = document.getElementById('preview-modal');
  const titleEl = document.getElementById('preview-modal-title');
  const textEl = document.getElementById('preview-modal-text');

  if (!modal) return;

  try {
    const mat = await api.get(`/materials/${id}`);
    if (titleEl) titleEl.textContent = mat.title;
    if (textEl) {
      textEl.textContent = mat.text_content || 'No text extracted from this material.';
    }
    modal.classList.add('open');
  } catch (err) {
    Layout.showToast('Failed to load material details', 'error');
  }
}

function closePreviewModal() {
  const modal = document.getElementById('preview-modal');
  if (modal) modal.classList.remove('open');
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
