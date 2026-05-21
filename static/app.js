/** Document Analyzer - Web UI */
const API = '/api';
let currentTaskId = null;
let currentResults = [];
let currentFilter = 'all';
let sortColumn = 'original_name';
let sortAsc = true;
let availableModels = [];
let currentPipelineConfig = {};

// Initialize app
async function initializeApp() {
  await loadModels();
  await checkConnection();
}

// Show validation error in UI
function showValidationError(message) {
  const errorMsg = document.getElementById('validationError');
  if (errorMsg) {
    errorMsg.innerHTML = `
      <div class="alert alert-danger alert-dismissible fade show" role="alert">
        <strong>Ошибка:</strong> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
      </div>
    `;
    errorMsg.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// Clear validation error
function clearValidationError() {
  const errorMsg = document.getElementById('validationError');
  if (errorMsg) errorMsg.innerHTML = '';
}

// Load available models
async function loadModels() {
  console.log('loadModels: starting...');
  try {
    const res = await fetch(`${API}/models`);
    console.log('loadModels: response status', res.status);

    if (!res.ok) {
      throw new Error('Сервер вернул ошибку: ' + res.status);
    }

    const data = await res.json();
    console.log('loadModels: response data', data);

    availableModels = data.available_models || [];
    currentPipelineConfig = data.pipeline_config || {};
    console.log('loadModels: available models count', availableModels.length);

    // Populate model selectors
    const populateSelect = (selectId) => {
      const select = document.getElementById(selectId);
      if (!select) {
        console.error('loadModels: select not found', selectId);
        return;
      }

      if (availableModels.length === 0) {
        select.innerHTML = '<option value="" disabled selected>Нет доступных моделей</option>';
        return;
      }

      select.innerHTML = '<option value="" disabled selected>-- Выберите модель --</option>';
      availableModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        option.textContent = model;
        select.appendChild(option);
      });
      console.log('loadModels: populated', selectId);
    };

    populateSelect('translateModel');
    populateSelect('annotateModel');
    populateSelect('reviewModel');

    // Set pipeline config
    document.getElementById('enableTranslation').checked = currentPipelineConfig.enable_translation !== false;
    document.getElementById('enableReview').checked = currentPipelineConfig.enable_review !== false;

  } catch (err) {
    console.error('loadModels: error', err);
    showValidationError('Не удалось загрузить список моделей: ' + err.message);
    const setError = (id) => {
      const select = document.getElementById(id);
      if (select) {
        select.innerHTML = '<option value="" disabled selected>Ошибка загрузки</option>';
      }
    };
    setError('translateModel');
    setError('annotateModel');
    setError('reviewModel');
  }
}

// Check connection
async function checkConnection() {
  const statusDiv = document.getElementById('connectionStatus');
  // По умолчанию не показываем статус пока не проверили
  statusDiv.innerHTML = '<span class="badge bg-secondary"><i class="bi bi-hourglass-split me-1"></i>Проверка...</span>';
  
  try {
    const res = await fetch(`${API}/test-connection`);
    const data = await res.json();
    console.log('checkConnection: response', data);
    
    if (data.connected) {
      statusDiv.innerHTML = '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Подключено</span>';
    } else {
      // Скрываем статус если Ollama недоступна (не показываем красное)
      statusDiv.innerHTML = '';
    }
  } catch (err) {
    console.error('checkConnection: error', err);
    // Скрываем статус при ошибке (не показываем красное)
    statusDiv.innerHTML = '';
  }
}

// Refresh models
document.getElementById('refreshModels').onclick = async () => {
  const btn = document.getElementById('refreshModels');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Загрузка...';
  await loadModels();
  btn.disabled = false;
  btn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Обновить список моделей';
};

// Reset models to defaults
document.getElementById('resetModels').onclick = () => {
  document.getElementById('translateModel').selectedIndex = 0;
  document.getElementById('annotateModel').selectedIndex = 0;
  document.getElementById('reviewModel').selectedIndex = 0;
};

// Validate model selection
function validateModels() {
  const translateModel = document.getElementById('translateModel').value;
  const annotateModel = document.getElementById('annotateModel').value;
  const reviewModel = document.getElementById('reviewModel').value;

  const errors = [];
  if (!translateModel) errors.push('Модель перевода');
  if (!annotateModel) errors.push('Модель аннотирования');
  if (!reviewModel) errors.push('Модель проверки');

  if (errors.length > 0) {
    showValidationError('Выберите модели: ' + errors.join(', '));
    return false;
  }

  clearValidationError();
  return true;
}

// Toggle model settings icon
document.querySelector('[data-bs-toggle="collapse"][data-bs-target="#modelSettings"]').addEventListener('click', () => {
  const icon = document.getElementById('modelSettingsIcon');
  icon.classList.toggle('bi-chevron-down');
  icon.classList.toggle('bi-chevron-up');
});

// Mode switching
document.querySelectorAll('[data-mode]').forEach(btn => {
  btn.addEventListener('click', (e) => {
    e.preventDefault();
    document.querySelectorAll('.nav-pills .nav-link').forEach(l => l.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('folderSection').classList.remove('active');
    document.getElementById('fileSection').classList.remove('active');
    document.getElementById(btn.dataset.mode === 'folder' ? 'folderSection' : 'fileSection').classList.add('active');
  });
});

// Browse folder
let browseTarget = null;
const browseModal = new bootstrap.Modal(document.getElementById('browseModal'));

async function loadBrowse(path = '') {
  const res = await fetch(`${API}/browse?path=${encodeURIComponent(path)}`);
  const data = await res.json();
  document.getElementById('browsePath').value = data.path;
  const list = document.getElementById('browseList');
  list.innerHTML = '';
  if (path) {
    const parent = document.createElement('a');
    parent.href = '#';
    parent.className = 'list-group-item list-group-item-action';
    parent.textContent = '.. (на уровень выше)';
    parent.onclick = (e) => {
      e.preventDefault();
      const parts = data.path.replace(/\\/g, '/').split('/').filter(Boolean);
      if (parts.length > 1) parts.pop();
      else if (parts.length === 1 && parts[0].length > 2) parts.length = 0;
      const parentPath = parts.length ? parts.join('/').replace(/^\/([a-zA-Z])/, '$1:\\').replace(/\//g, '\\') : '';
      loadBrowse(parentPath || undefined);
    };
    list.appendChild(parent);
  }
  data.items.forEach(item => {
    const a = document.createElement('a');
    a.href = '#';
    a.className = 'list-group-item list-group-item-action d-flex align-items-center';
    a.innerHTML = `<i class="bi bi-${item.is_dir ? 'folder-fill text-warning' : 'file-earmark'} me-2"></i>${item.name}`;
    a.onclick = (e) => {
      e.preventDefault();
      if (item.is_dir) loadBrowse(item.path);
      else return;
    };
    list.appendChild(a);
  });
}

document.getElementById('browseSource').onclick = () => {
  browseTarget = 'source';
  document.getElementById('browsePath').value = document.getElementById('sourceFolder').value;
  loadBrowse(document.getElementById('sourceFolder').value || undefined);
  browseModal.show();
};

document.getElementById('browseOutput').onclick = () => {
  browseTarget = 'output';
  document.getElementById('browsePath').value = document.getElementById('outputFolder').value;
  loadBrowse(document.getElementById('outputFolder').value || undefined);
  browseModal.show();
};

document.getElementById('browsePath').addEventListener('change', () => {
  loadBrowse(document.getElementById('browsePath').value);
});

// Path is set only when user clicks "Выбрать эту папку"

document.getElementById('selectFolderBtn').onclick = () => {
  const path = document.getElementById('browsePath').value;
  if (path && browseTarget) {
    if (browseTarget === 'source') document.getElementById('sourceFolder').value = path;
    else document.getElementById('outputFolder').value = path;
    browseModal.hide();
  }
};

document.getElementById('browsePath').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    loadBrowse(document.getElementById('browsePath').value);
  }
});

// Run folder analysis
document.getElementById('runFolder').onclick = async () => {
  const source = document.getElementById('sourceFolder').value.trim().replace(/^["']|["']$/g, '');
  const output = document.getElementById('outputFolder').value.trim().replace(/^["']|["']$/g, '');
  if (!source) return showValidationError('Укажите исходную папку');
  if (!output) return showValidationError('Укажите папку для сохранения');
  if (!validateModels()) return;

  const btn = document.getElementById('runFolder');
  const stopBtn = document.getElementById('stopFolder');
  btn.disabled = true;
  stopBtn.classList.remove('d-none');
  document.getElementById('progressSection').classList.remove('d-none');
  document.getElementById('logSection').classList.remove('d-none');
  document.getElementById('logShow').classList.add('d-none');
  document.getElementById('logPanel').innerHTML = '';

  try {
    const res = await fetch(`${API}/analyze-folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_folder: source,
        output_folder: output,
        translate_model: document.getElementById('translateModel').value || null,
        annotate_model: document.getElementById('annotateModel').value || null,
        review_model: document.getElementById('reviewModel').value || null,
        enable_translation: document.getElementById('enableTranslation').checked,
        enable_review: document.getElementById('enableReview').checked
      })
    });
    const data = await res.json();
    if (!res.ok) {
      // Pydantic validation errors come as array of objects
      let errorMsg = 'Ошибка';
      if (data.detail) {
        if (Array.isArray(data.detail)) {
          errorMsg = data.detail.map(e => {
            if (typeof e === 'string') return e;
            if (e.msg) return e.msg;
            return JSON.stringify(e);
          }).join('; ');
        } else if (typeof data.detail === 'string') {
          errorMsg = data.detail;
        } else {
          errorMsg = JSON.stringify(data.detail);
        }
      }
      showValidationError(errorMsg);
      btn.disabled = false;
      stopBtn.classList.add('d-none');
      return;
    }
    currentTaskId = data.task_id;

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${location.host}/ws/logs/${data.task_id}`);
    ws.onmessage = (ev) => {
      const div = document.getElementById('logPanel');
      const line = document.createElement('div');
      line.className = 'log-line';
      line.textContent = ev.data;
      div.appendChild(line);
      div.scrollTop = div.scrollHeight;
    };

    const checkStatus = setInterval(async () => {
      const s = await fetch(`${API}/status/${currentTaskId}`);
      const st = await s.json();
      if (st.status === 'completed' || st.status === 'failed' || st.status === 'cancelled') {
        clearInterval(checkStatus);
        ws.close();
        btn.disabled = false;
        stopBtn.classList.add('d-none');
        document.getElementById('progressBar').style.width = st.status === 'cancelled' ? '0%' : '100%';
        document.getElementById('progressBar').classList.remove('progress-bar-animated');
        // Скрываем прогресс через 1 секунду после завершения
        setTimeout(() => {
          document.getElementById('progressSection').classList.add('d-none');
        }, 1000);
        if (st.status === 'completed') await loadResults(currentTaskId);
        if (st.status === 'cancelled') {
          currentTaskId = null;
          currentResults = [];
          renderTable([]);
          document.getElementById('progressSection').classList.add('d-none');
        }
      }
    }, 1000);
  } catch (err) {
    showValidationError(err.message);
    btn.disabled = false;
    document.getElementById('stopFolder').classList.add('d-none');
  }
};

// Stop folder analysis
document.getElementById('stopFolder').onclick = async () => {
  if (!currentTaskId) return;
  const stopBtn = document.getElementById('stopFolder');
  stopBtn.disabled = true;
  try {
    await fetch(`${API}/cancel-task`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: currentTaskId })
    });
    const poll = async () => {
      const s = await fetch(`${API}/status/${currentTaskId}`);
      const st = await s.json();
      if (st.status === 'cancelled') {
        currentTaskId = null;
        currentResults = [];
        renderTable([]);
        document.getElementById('runFolder').disabled = false;
        stopBtn.classList.add('d-none');
        stopBtn.disabled = false;
        document.getElementById('progressSection').classList.add('d-none');
      } else {
        setTimeout(poll, 500);
      }
    };
    poll();
  } catch (e) {
    stopBtn.disabled = false;
    showValidationError('Ошибка остановки');
  }
};

// Single file - drag & drop
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');

dropZone.onclick = () => fileInput.click();

['dragenter', 'dragover', 'dragleave', 'drop'].forEach(ev => {
  dropZone.addEventListener(ev, (e) => {
    e.preventDefault();
    e.stopPropagation();
  });
});

dropZone.addEventListener('dragenter', () => dropZone.classList.add('dragover'));
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'));
dropZone.addEventListener('drop', (e) => {
  dropZone.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f) handleFile(f);
});

fileInput.onchange = () => {
  const f = fileInput.files[0];
  if (f) handleFile(f);
};

async function handleFile(file) {
  if (!validateModels()) return;
  
  const ext = (file.name || '').toLowerCase().slice(-5);
  if (!['.docx', '.doc', '.pdf'].some(e => ext.endsWith(e))) {
    return showValidationError('Поддерживаются только .docx, .doc, .pdf');
  }

  const fd = new FormData();
  fd.append('file', file);
  fd.append('translate_model', document.getElementById('translateModel').value || '');
  fd.append('annotate_model', document.getElementById('annotateModel').value || '');
  fd.append('review_model', document.getElementById('reviewModel').value || '');

  const resultDiv = document.getElementById('singleFileResult');
  resultDiv.classList.remove('d-none');
  resultDiv.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Анализ...';

  try {
    const res = await fetch(`${API}/analyze-file`, { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) {
      let errorMsg = 'Ошибка';
      if (data.detail) {
        if (Array.isArray(data.detail)) {
          errorMsg = data.detail.map(e => {
            if (typeof e === 'string') return e;
            if (e.msg) return e.msg;
            return JSON.stringify(e);
          }).join('; ');
        } else if (typeof data.detail === 'string') {
          errorMsg = data.detail;
        } else {
          errorMsg = JSON.stringify(data.detail);
        }
      }
      showValidationError(errorMsg);
      resultDiv.innerHTML = 'Ошибка: ' + errorMsg;
      resultDiv.classList.add('alert-danger');
      return;
    }

    let attempts = 0;
    const poll = async () => {
      const s = await fetch(`${API}/status/${data.task_id}`);
      const st = await s.json();
      if (st.status === 'completed') {
        const r = await fetch(`${API}/results/${data.task_id}`);
        const rj = await r.json();
        const row = rj.results[0];
        currentTaskId = data.task_id;
        currentResults = rj.results;
        renderTable(currentResults);
        resultDiv.innerHTML = `<strong>${row.original_name}</strong>: ${row.title}`;
        resultDiv.classList.remove('alert-warning');
        resultDiv.classList.add(row.status === 'success' ? 'alert-success' : 'alert-danger');
        return;
      }
      if (st.status === 'failed') {
        resultDiv.innerHTML = 'Ошибка анализа';
        resultDiv.classList.add('alert-danger');
        return;
      }
      attempts++;
      if (attempts < 120) setTimeout(poll, 500);
      else resultDiv.innerHTML = '⏱ Таймаут ожидания';
    };
    poll();
  } catch (err) {
    resultDiv.innerHTML = 'Ошибка: ' + err.message;
    resultDiv.classList.add('alert-danger');
  }
}

// Load results
async function loadResults(taskId) {
  const res = await fetch(`${API}/results/${taskId}`);
  const data = await res.json();
  currentTaskId = taskId;
  currentResults = data.results || [];
  renderTable(currentResults);
}

// Render table
function renderTable(results, filter = currentFilter, search = document.getElementById('searchInput').value) {
  let rows = [...results];
  if (filter === 'success') rows = rows.filter(r => r.status === 'success');
  if (filter === 'error') rows = rows.filter(r => r.status !== 'success');
  const q = (search || '').toLowerCase();
  if (q) rows = rows.filter(r =>
    (r.original_name || '').toLowerCase().includes(q) ||
    (r.title || '').toLowerCase().includes(q)
  );
  rows.sort((a, b) => {
    let va = a[sortColumn] || '';
    let vb = b[sortColumn] || '';
    if (sortColumn === 'status') { va = va === 'success' ? 1 : 0; vb = vb === 'success' ? 1 : 0; }
    const c = String(va).localeCompare(String(vb), 'ru');
    return sortAsc ? c : -c;
  });

  const tbody = document.getElementById('resultsBody');
  if (rows.length === 0) {
    const msg = results.length === 0 ? 'Результаты появятся после анализа' : 'Нет данных';
    tbody.innerHTML = `<tr><td colspan="4" class="text-muted text-center py-5">${msg}</td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr data-file="${(r.file_name || r.original_name || '').replace(/"/g, '&quot;')}">
      <td><span class="status-${r.status === 'success' ? 'ok' : 'err'}">${r.status === 'success' ? 'Прочитан' : 'Не прочитан'}</span></td>
      <td>${escapeHtml(r.original_name || r.file_name || '')}</td>
      <td><span class="editable-title" contenteditable="true" data-file-name="${escapeHtml(r.file_name || '')}" data-original-name="${escapeHtml(r.original_name || '')}">${escapeHtml(r.title || '')}</span>
          <button type="button" class="btn btn-sm btn-outline-primary ms-1 save-title-btn d-none" title="Сохранить"><i class="bi bi-check"></i></button></td>
      <td><div class="actions-cell">
        ${(r.status === 'success' && (r.file_path || r.file_name)) ? `<a href="${API}/files/${currentTaskId}/${encodeURIComponent(r.file_name || r.original_name || '')}" target="_blank" class="btn btn-sm btn-outline-secondary" title="Открыть файл"><i class="bi bi-folder2-open"></i></a>` : ''}
        ${(r.status === 'success' && (r.file_path || r.file_name)) ? `<button type="button" class="btn btn-sm btn-outline-secondary regenerate-btn" data-file-name="${escapeHtml(r.file_name || '')}" data-original-name="${escapeHtml(r.original_name || '')}" title="Перегенерировать"><i class="bi bi-arrow-clockwise"></i></button>` : ''}
        <button type="button" class="btn btn-sm btn-outline-secondary copy-title-btn" data-title="${escapeHtml(r.title || '')}" title="Скопировать"><i class="bi bi-clipboard"></i></button>
      </div></td>
    </tr>
  `).join('');

  // Edit + save
  tbody.querySelectorAll('.editable-title').forEach(el => {
    el.addEventListener('input', () => {
      el.nextElementSibling?.classList.remove('d-none');
    });
    el.addEventListener('blur', () => {
      const btn = el.nextElementSibling;
      if (btn && !btn.classList.contains('d-none')) {
        saveTitle(el.dataset.fileName || el.dataset.originalName, el.textContent.trim());
        btn.classList.add('d-none');
      }
    });
  });
  tbody.querySelectorAll('.save-title-btn').forEach(btn => {
    btn.onclick = () => {
      const span = btn.previousElementSibling;
      saveTitle(span.dataset.fileName || span.dataset.originalName, span.textContent.trim());
      btn.classList.add('d-none');
    };
  });
  tbody.querySelectorAll('.copy-title-btn').forEach(btn => {
    btn.onclick = () => {
      const title = btn.closest('tr')?.querySelector('.editable-title')?.textContent?.trim() || btn.dataset.title || '';
      navigator.clipboard.writeText(title);
      btn.innerHTML = '<i class="bi bi-check text-success"></i>';
      setTimeout(() => { btn.innerHTML = '<i class="bi bi-clipboard"></i>'; }, 800);
    };
  });
  const doRegenerate = async (btn) => {
    if (!validateModels()) return;
    const fileName = btn.dataset.fileName || btn.dataset.originalName;
    if (!currentTaskId || !fileName) return;
    const origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    try {
      const res = await fetch(`${API}/regenerate-title`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task_id: currentTaskId,
          file_name: fileName,
          translate_model: document.getElementById('translateModel').value,
          annotate_model: document.getElementById('annotateModel').value,
          review_model: document.getElementById('reviewModel').value
        })
      });
      const data = await res.json();
      if (res.ok && data.title) {
        const r = currentResults.find(x => (x.file_name || x.original_name) === fileName);
        if (r) r.title = data.title;
        const span = btn.closest('tr')?.querySelector('.editable-title');
        if (span) span.textContent = data.title;
        const copyBtn = btn.closest('tr')?.querySelector('.copy-title-btn');
        if (copyBtn) copyBtn.dataset.title = data.title;
      } else throw new Error(data.detail || 'Ошибка');
    } catch (e) {
      showValidationError(e.message);
    }
    btn.disabled = false;
    btn.innerHTML = origHtml;
  };
  tbody.querySelectorAll('.regenerate-btn').forEach(btn => {
    btn.onclick = () => doRegenerate(btn);
  });
}

// Log panel controls
document.getElementById('logReset').onclick = () => {
  document.getElementById('logPanel').innerHTML = '';
};
document.getElementById('logHide').onclick = () => {
  document.getElementById('logSection').classList.add('d-none');
  document.getElementById('logShow').classList.remove('d-none');
};
document.getElementById('logShow').onclick = () => {
  document.getElementById('logSection').classList.remove('d-none');
  document.getElementById('logShow').classList.add('d-none');
};

function escapeHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function saveTitle(fileName, newTitle) {
  if (!currentTaskId || !newTitle) return;
  try {
    await fetch(`${API}/update-title`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: currentTaskId, file_name: fileName, new_title: newTitle })
    });
    const r = currentResults.find(x => (x.file_name || x.original_name || '') === fileName);
    if (r) r.title = newTitle;
    const btn = [...document.querySelectorAll('.copy-title-btn')].find(b => b.closest('tr')?.querySelector(`[data-file="${fileName.replace(/"/g, '')}"]`));
    if (btn) btn.dataset.title = newTitle;
  } catch (e) { showValidationError('Ошибка сохранения'); }
}

// Filters
document.querySelectorAll('[data-filter]').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('[data-filter]').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentFilter = btn.dataset.filter;
    renderTable(currentResults);
  });
});

document.getElementById('searchInput').addEventListener('input', () => renderTable(currentResults));

// Sort
document.querySelectorAll('#resultsTable th[data-sort]').forEach(th => {
  th.addEventListener('click', () => {
    if (sortColumn === th.dataset.sort) sortAsc = !sortAsc;
    else { sortColumn = th.dataset.sort; sortAsc = true; }
    renderTable(currentResults);
  });
});

// Export
function exportUrl(format) {
  if (!currentTaskId) {
    showValidationError('Сначала выполните анализ');
    return null;
  }
  return `${API}/export/${currentTaskId}?format=${format}`;
}

document.getElementById('exportCsv').onclick = () => {
  const url = exportUrl('csv');
  if (url) window.open(url, '_blank');
};
document.getElementById('exportExcel').onclick = () => {
  const url = exportUrl('excel');
  if (url) window.open(url, '_blank');
};

// Reset results
document.getElementById('resetResults').onclick = () => {
  currentTaskId = null;
  currentResults = [];
  document.querySelectorAll('[data-filter]').forEach(b => { b.classList.remove('active'); if (b.dataset.filter === 'all') b.classList.add('active'); });
  currentFilter = 'all';
  document.getElementById('searchInput').value = '';
  renderTable([]);
};

// Initialize app on load
document.addEventListener('DOMContentLoaded', initializeApp);