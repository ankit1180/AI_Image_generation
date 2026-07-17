/* ── Config ─────────────────────────────────────────────────── */
const API = '/api/v1';
let activeFolderId = null;
let activeImageId  = null;
let pollTimer      = null;

/* ── Utility ────────────────────────────────────────────────── */
const $  = (id) => document.getElementById(id);
const qs = (sel) => document.querySelector(sel);

function toast(msg, type = 'info') {
  const el = $('toast');
  el.textContent = msg;
  el.className = `toast ${type}`;
  el.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add('hidden'), 3500);
}

async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  if (res.status === 204) return null;
  return res.json();
}

/* ── Health check ────────────────────────────────────────────── */
async function checkHealth() {
  try {
    const data = await apiFetch('/health/');
    const dot   = $('health-dot');
    const label = $('health-label');
    if (data.status === 'ok') {
      dot.className = 'health-dot ok';
      label.textContent = 'All systems go';
    } else {
      dot.className = 'health-dot error';
      label.textContent = 'Degraded';
    }
  } catch {
    $('health-dot').className = 'health-dot error';
    $('health-label').textContent = 'Offline';
  }
}

/* ── Folders ─────────────────────────────────────────────────── */
async function loadFolders() {
  try {
    const folders = await apiFetch('/folders/');
    renderFolders(folders);
  } catch (e) {
    toast('Could not load folders: ' + e.message, 'error');
    $('folder-list').innerHTML = '<p style="color:var(--danger);padding:8px;">Failed to load</p>';
  }
}

function renderFolders(folders) {
  const list = $('folder-list');
  if (!folders.length) {
    list.innerHTML = '<p style="color:var(--text-muted);padding:8px;font-size:12px;">No folders yet.</p>';
    return;
  }
  list.innerHTML = folders.map(f => `
    <div class="folder-item ${f.id === activeFolderId ? 'active' : ''}"
         id="fi-${f.id}"
         onclick="selectFolder('${f.id}','${escHtml(f.name)}','${f.image_count}')">
      <span class="folder-icon">📁</span>
      <div class="folder-info">
        <div class="folder-name">${escHtml(f.name)}</div>
        <div class="folder-count">${f.image_count} image${f.image_count !== 1 ? 's' : ''}</div>
      </div>
    </div>
  `).join('');
}

async function selectFolder(id, name, count) {
  activeFolderId = id;
  // Highlight active
  document.querySelectorAll('.folder-item').forEach(el => el.classList.remove('active'));
  const fi = $('fi-' + id);
  if (fi) fi.classList.add('active');

  // Show folder view
  $('empty-state').classList.add('hidden');
  $('folder-view').classList.remove('hidden');
  $('folder-title').textContent = name;
  $('folder-meta').textContent  = `${count} image${count !== 1 ? 's' : ''}`;

  // Reset upload panel
  hideUploadPanel();
  closeDrawer();

  await loadImages(id);
}

/* ── Create folder ───────────────────────────────────────────── */
function showCreateFolder() { $('create-folder-panel').classList.remove('hidden'); }
function hideCreateFolder() {
  $('create-folder-panel').classList.add('hidden');
  $('new-folder-name').value = '';
  $('new-folder-desc').value = '';
}

async function createFolder() {
  const name = $('new-folder-name').value.trim();
  if (!name) { toast('Folder name is required', 'error'); return; }
  try {
    const f = await apiFetch('/folders/', {
      method: 'POST',
      body: JSON.stringify({ name, description: $('new-folder-desc').value.trim() }),
    });
    toast(`Folder "${f.name}" created`, 'success');
    hideCreateFolder();
    await loadFolders();
    selectFolder(f.id, f.name, 0);
  } catch (e) {
    toast('Error: ' + e.message, 'error');
  }
}

/* ── Images ──────────────────────────────────────────────────── */
async function loadImages(folderId) {
  $('image-grid').innerHTML = '<div class="skeleton-row" style="height:160px;border-radius:10px;grid-column:1/-1"></div>';
  $('images-empty').classList.add('hidden');
  try {
    const images = await apiFetch(`/images/folder/${folderId}`);
    renderImages(images);
  } catch (e) {
    toast('Could not load images: ' + e.message, 'error');
    $('image-grid').innerHTML = '';
  }
}

function renderImages(images) {
  const grid = $('image-grid');
  if (!images.length) {
    grid.innerHTML = '';
    $('images-empty').classList.remove('hidden');
    return;
  }
  $('images-empty').classList.add('hidden');
  grid.innerHTML = images.map(img => `
    <div class="image-card" onclick="openDrawer('${img.id}')">
      ${img.cloudinary_url
        ? `<img class="card-thumb" src="${img.cloudinary_url}" alt="${escHtml(img.filename)}" loading="lazy" />`
        : `<div class="card-thumb-placeholder">🖼️</div>`}
      <div class="card-body">
        <div class="card-name">${escHtml(img.filename)}</div>
        <div class="card-status ${img.status}">${img.status}</div>
      </div>
    </div>
  `).join('');
}

/* ── Upload ───────────────────────────────────────────────────── */
function showUploadPanel() { $('upload-panel').classList.remove('hidden'); }
function hideUploadPanel() {
  $('upload-panel').classList.add('hidden');
  $('upload-status').classList.add('hidden');
  $('upload-file').value = '';
  $('upload-filename').value = '';
  $('upload-prompt').value = '';
  $('upload-meta').value = '';
}

async function uploadImage() {
  if (!activeFolderId) return;

  const file     = $('upload-file').files[0];
  const filename = $('upload-filename').value.trim() || file?.name || '';
  const prompt   = $('upload-prompt').value.trim();
  const meta     = $('upload-meta').value.trim() || '{}';

  if (!file)     { toast('Select a file', 'error'); return; }
  if (!filename) { toast('Enter a filename', 'error'); return; }
  if (!prompt)   { toast('Prompt is required', 'error'); return; }

  const fd = new FormData();
  fd.append('folder_id', activeFolderId);
  fd.append('filename', filename);
  fd.append('prompt', prompt);
  fd.append('metadata', meta);
  fd.append('file', file);

  const statusEl = $('upload-status');
  statusEl.className = 'upload-status';
  statusEl.textContent = '⏳ Uploading…';
  statusEl.classList.remove('hidden');

  try {
    const res = await fetch(API + '/images/upload/file', { method: 'POST', body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Upload failed');
    }
    const task = await res.json();
    statusEl.textContent = `✅ Queued! Task: ${task.task_id}`;
    toast('Upload queued! Processing…', 'success');

    // Poll until done
    pollTask(task.task_id, task.image_id, statusEl);
  } catch (e) {
    statusEl.className = 'upload-status error';
    statusEl.textContent = '❌ ' + e.message;
    toast('Upload failed: ' + e.message, 'error');
  }
}

function pollTask(taskId, imageId, statusEl) {
  clearTimeout(pollTimer);
  let attempts = 0;
  const max = 30;

  async function tick() {
    if (attempts++ > max) {
      statusEl.textContent = '⏱ Timed out waiting for task';
      return;
    }
    try {
      const t = await apiFetch(`/tasks/${taskId}`);
      if (t.status === 'SUCCESS') {
        statusEl.textContent = `✅ Done! Image live.`;
        toast('Image uploaded successfully!', 'success');
        await loadImages(activeFolderId);
        await loadFolders();
        hideUploadPanel();
      } else if (t.status === 'FAILURE') {
        statusEl.className = 'upload-status error';
        statusEl.textContent = '❌ Task failed: ' + (t.error || 'unknown');
      } else {
        statusEl.textContent = `⏳ Status: ${t.status}… (${attempts}/${max})`;
        pollTimer = setTimeout(tick, 2000);
      }
    } catch {
      pollTimer = setTimeout(tick, 3000);
    }
  }
  pollTimer = setTimeout(tick, 1500);
}

/* ── Drawer ──────────────────────────────────────────────────── */
async function openDrawer(imageId) {
  activeImageId = imageId;

  // Reset prompt area
  $('prompt-box').classList.add('hidden');
  $('prompt-box').textContent = '';
  $('prompt-error').classList.add('hidden');
  $('prompt-secret-row').classList.add('hidden');
  $('prompt-btn').textContent = 'Reveal Prompt';
  $('prompt-secret-input').value = '';

  $('drawer-overlay').classList.remove('hidden');
  $('drawer').classList.remove('hidden');

  try {
    const img = await apiFetch(`/images/${imageId}`);
    renderDrawer(img);
  } catch (e) {
    toast('Could not load image detail: ' + e.message, 'error');
  }
}

function renderDrawer(img) {
  if (img.cloudinary_url) {
    const el = $('drawer-img');
    el.src = img.cloudinary_url;
    el.style.display = 'block';
  } else {
    $('drawer-img').style.display = 'none';
  }

  $('drawer-filename').textContent = img.filename;

  const statusBadge = $('drawer-status');
  statusBadge.textContent = img.status;
  statusBadge.className = `badge ${img.status}`;

  $('drawer-format').textContent = img.metadata?.format || '';

  // Meta table
  const metaRows = [
    ['ID',       img.id],
    ['Folder',   img.folder_id],
    ['Status',   img.status],
    ['Created',  fmtDate(img.created_at)],
    ['Updated',  fmtDate(img.updated_at)],
    ...(img.metadata?.width  ? [['Dimensions', `${img.metadata.width}×${img.metadata.height}`]] : []),
    ...(img.metadata?.bytes  ? [['Size', fmtBytes(img.metadata.bytes)]] : []),
    ...(img.public_id        ? [['Public ID', img.public_id]] : []),
  ];

  $('drawer-meta').innerHTML = metaRows
    .filter(([,v]) => v)
    .map(([k, v]) => `
      <div class="meta-row">
        <span class="meta-key">${k}</span>
        <span class="meta-val">${escHtml(String(v))}</span>
      </div>`)
    .join('');
}

function closeDrawer() {
  $('drawer-overlay').classList.add('hidden');
  $('drawer').classList.add('hidden');
  activeImageId = null;
}

/* ── Prompt reveal ───────────────────────────────────────────── */
function fetchPrompt() {
  const secretRow = $('prompt-secret-row');
  if (secretRow.classList.contains('hidden')) {
    secretRow.classList.remove('hidden');
    $('prompt-secret-input').focus();
  } else {
    secretRow.classList.add('hidden');
  }
}

async function submitSecret() {
  if (!activeImageId) return;
  const secret = $('prompt-secret-input').value.trim();
  if (!secret) { toast('Enter the secret key', 'error'); return; }

  const errEl = $('prompt-error');
  const box   = $('prompt-box');
  errEl.classList.add('hidden');
  box.classList.add('hidden');

  try {
    const data = await apiFetch(`/images/${activeImageId}/prompt`, {
      headers: { 'X-Prompt-Secret': secret },
    });
    box.textContent = data.prompt || '(no prompt set)';
    box.classList.remove('hidden');
    $('prompt-secret-row').classList.add('hidden');
    $('prompt-btn').textContent = 'Hide Prompt';
    $('prompt-btn').onclick = () => {
      box.classList.add('hidden');
      $('prompt-btn').textContent = 'Reveal Prompt';
      $('prompt-btn').onclick = fetchPrompt;
    };
  } catch (e) {
    errEl.textContent = '❌ ' + (e.message.includes('401') ? 'Invalid secret key' : e.message);
    errEl.classList.remove('hidden');
  }
}

/* ── Delete image ─────────────────────────────────────────────── */
async function deleteImage() {
  if (!activeImageId) return;
  if (!confirm('Delete this image? This cannot be undone.')) return;
  try {
    await apiFetch(`/images/${activeImageId}`, { method: 'DELETE' });
    toast('Image deleted', 'success');
    closeDrawer();
    await loadImages(activeFolderId);
    await loadFolders();
  } catch (e) {
    toast('Delete failed: ' + e.message, 'error');
  }
}

/* ── Helpers ─────────────────────────────────────────────────── */
function escHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

function fmtDate(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function fmtBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
  return (b/1048576).toFixed(2) + ' MB';
}

/* ── Init ───────────────────────────────────────────────────── */
(async () => {
  await checkHealth();
  await loadFolders();
  setInterval(checkHealth, 30000);
})();