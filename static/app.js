/** Document Analyzer - Web UI */
const API = '/api';

// ============ Глобальное состояние ============
let currentTaskId = null;
let currentResults = [];
let currentFilter = 'all';
let sortColumn = 'original_name';
let sortAsc = true;
let availableModels = [];
let currentPipelineConfig = {};
let browseTarget = null;
let browseModalInstance = null;
let defaultPrompts = {};  // Стандартные промты

// ============ Утилиты ============
function $(id) { return document.getElementById(id); }

function escapeHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function showValidationError(message) {
  const errorMsg = $('validationError');
  if (errorMsg) {
    errorMsg.innerHTML = `
      <div class="alert alert-danger alert-dismissible fade show" role="alert">
        <strong>Ошибка:</strong> ${escapeHtml(message)}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
      </div>
    `;
    errorMsg.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function clearValidationError() {
  const errorMsg = $('validationError');
  if (errorMsg) errorMsg.innerHTML = '';
}

function parseError(data) {
  if (!data || !data.detail) return 'Неизвестная ошибка';
  if (Array.isArray(data.detail)) {
    return data.detail.map(e => typeof e === 'string' ? e : (e.msg || JSON.stringify(e))).join('; ');
  }
  if (typeof data.detail === 'string') return data.detail;
  return JSON.stringify(data.detail);
}

// ============ Тема ============
function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'light';
  setTheme(savedTheme);
}

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
  const icon = $('themeIcon');
  if (icon) {
    icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme');
  setTheme(current === 'dark' ? 'light' : 'dark');
}

// ============ Загрузка моделей ============
async function loadModels() {
  console.log('[loadModels] starting...');
  
  // Показываем состояние "загрузка"
  ['translateModel', 'annotateModel', 'reviewModel'].forEach(id => {
    const sel = $(id);
    if (sel) sel.innerHTML = '<option value="" disabled selected>Загрузка...</option>';
  });

  try {
    const res = await fetch(`${API}/models`);
    console.log('[loadModels] status:', res.status);

    if (!res.ok) throw new Error('Сервер вернул ошибку: ' + res.status);

    const data = await res.json();
    console.log('[loadModels] моделей всего:', data.available_models?.length);
    console.log('[loadModels] активных моделей:', data.active_models?.length);

    availableModels = data.available_models || [];
    const activeModels = data.active_models || [];
    currentPipelineConfig = data.pipeline_config || {};

    const populateSelect = (selectId) => {
      const select = $(selectId);
      if (!select) return;
      
      if (availableModels.length === 0) {
        select.innerHTML = '<option value="" disabled selected>Нет доступных моделей</option>';
        return;
      }
      
      select.innerHTML = '<option value="" disabled selected>-- Выберите модель --</option>';
      availableModels.forEach(model => {
        const option = document.createElement('option');
        option.value = model;
        // Помечаем активные модели
        if (activeModels.includes(model)) {
          option.textContent = `✅ ${model}`;
          option.style.fontWeight = 'bold';
        } else {
          option.textContent = `⚪ ${model}`;
          option.style.color = '#999';
        }
        select.appendChild(option);
      });
      
      // Добавляем легенду
      const legend = select.parentElement.querySelector('.model-legend');
      if (!legend) {
        const legendDiv = document.createElement('div');
        legendDiv.className = 'model-legend mt-1 text-muted small';
        legendDiv.innerHTML = `<small>✅ Активна | ⚪ Не активна</small>`;
        select.parentElement.appendChild(legendDiv);
      }
    };

    populateSelect('translateModel');
    populateSelect('annotateModel');
    populateSelect('reviewModel');

    // Применяем конфигурацию pipeline
    const enableTrans = $('enableTranslation');
    if (enableTrans) enableTrans.checked = currentPipelineConfig.enable_translation !== false;
    const enableRev = $('enableReview');
    if (enableRev) enableRev.checked = currentPipelineConfig.enable_review !== false;

  } catch (err) {
    console.error('[loadModels] error:', err);
    showValidationError('Не удалось загрузить список моделей: ' + err.message);
    ['translateModel', 'annotateModel', 'reviewModel'].forEach(id => {
      const sel = $(id);
      if (sel) sel.innerHTML = '<option value="" disabled selected>Ошибка загрузки</option>';
    });
  }
}

// ============ Проверка подключения ============
async function checkConnection() {
  const statusDiv = $('connectionStatus');
  if (!statusDiv) return;
  
  statusDiv.innerHTML = '<span class="badge bg-secondary"><i class="bi bi-hourglass-split me-1"></i>Проверка...</span>';
  
  try {
    const res = await fetch(`${API}/test-connection`);
    const data = await res.json();
    if (data.connected) {
      statusDiv.innerHTML = '<span class="badge bg-success"><i class="bi bi-check-circle me-1"></i>Подключено</span>';
    } else {
      statusDiv.innerHTML = '';
    }
  } catch (err) {
    console.error('[checkConnection]:', err);
    statusDiv.innerHTML = '';
  }
}

// ============ Валидация моделей ============
function validateModels() {
  const translateModel = $('translateModel')?.value;
  const annotateModel = $('annotateModel')?.value;
  const reviewModel = $('reviewModel')?.value;

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

// ============ Обзор папок ============
function initBrowseModal() {
  if (!browseModalInstance) {
    const modalEl = $('browseModal');
    if (modalEl) browseModalInstance = new bootstrap.Modal(modalEl);
  }
  return browseModalInstance;
}

async function loadBrowse(path = '') {
  try {
    const res = await fetch(`${API}/browse?path=${encodeURIComponent(path)}`);
    const data = await res.json();
    $('browsePath').value = data.path;
    const list = $('browseList');
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
      a.innerHTML = `<i class="bi bi-${item.is_dir ? 'folder-fill text-warning' : 'file-earmark'} me-2"></i>${escapeHtml(item.name)}`;
      a.onclick = (e) => {
        e.preventDefault();
        if (item.is_dir) loadBrowse(item.path);
      };
      list.appendChild(a);
    });
  } catch (err) {
    console.error('[loadBrowse]:', err);
    showValidationError('Не удалось загрузить список папок');
  }
}

// ============ Анализ папки ============
async function runFolderAnalysis() {
  const source = $('sourceFolder').value.trim().replace(/^["']|["']$/g, '');
  const output = $('outputFolder').value.trim().replace(/^["']|["']$/g, '');
  if (!source) return showValidationError('Укажите исходную папку');
  if (!output) return showValidationError('Укажите папку для сохранения');
  if (!validateModels()) return;

  const btn = $('runFolder');
  const stopBtn = $('stopFolder');
  btn.disabled = true;
  stopBtn.classList.remove('d-none');
  $('progressSection').classList.remove('d-none');
  $('logSection').classList.remove('d-none');
  $('logShow').classList.add('d-none');
  $('logPanel').innerHTML = '';
  $('progressBar').style.width = '0%';
  $('progressBar').classList.add('progress-bar-animated');

  try {
    const res = await fetch(`${API}/analyze-folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_folder: source,
        output_folder: output,
        translate_model: $('translateModel').value,
        annotate_model: $('annotateModel').value,
        review_model: $('reviewModel').value,
        enable_translation: $('enableTranslation').checked,
        enable_review: $('enableReview').checked,
        // Параметры из режима разработчика
        max_annotation_chars: parseInt($('maxAnnotationChars').value) || 800,
        max_review_iterations: parseInt($('maxReviewIterations').value) || 2
      })
    });
    const data = await res.json();
    
    if (!res.ok) {
      showValidationError(parseError(data));
      btn.disabled = false;
      stopBtn.classList.add('d-none');
      return;
    }
    
    currentTaskId = data.task_id;

    // WebSocket для логов
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${location.host}/ws/logs/${data.task_id}`);
    ws.onmessage = (ev) => {
      const div = $('logPanel');
      const line = document.createElement('div');
      line.className = 'log-line';
      line.textContent = ev.data;
      div.appendChild(line);
      div.scrollTop = div.scrollHeight;
    };

    // Опрос статуса
    const checkStatus = setInterval(async () => {
      try {
        const s = await fetch(`${API}/status/${currentTaskId}`);
        const st = await s.json();
        if (['completed', 'failed', 'cancelled'].includes(st.status)) {
          clearInterval(checkStatus);
          ws.close();
          btn.disabled = false;
          stopBtn.classList.add('d-none');
          $('progressBar').style.width = st.status === 'cancelled' ? '0%' : '100%';
          $('progressBar').classList.remove('progress-bar-animated');
          setTimeout(() => $('progressSection').classList.add('d-none'), 1000);
          
          if (st.status === 'completed') await loadResults(currentTaskId);
          if (st.status === 'cancelled') {
            currentTaskId = null;
            currentResults = [];
            renderTable([]);
          }
        }
      } catch (e) {
        console.error('[checkStatus]:', e);
      }
    }, 1000);
    
  } catch (err) {
    showValidationError(err.message);
    btn.disabled = false;
    stopBtn.classList.add('d-none');
  }
}

// ============ Остановка анализа ============
async function stopFolderAnalysis() {
  if (!currentTaskId) return;
  
  const taskIdToCancel = currentTaskId;
  
  // МГНОВЕННО сбрасываем UI — не ждём backend
  currentTaskId = null;
  $('runFolder').disabled = false;
  $('stopFolder').classList.add('d-none');
  $('stopFolder').disabled = false;
  $('stopFolder').innerHTML = '<i class="bi bi-stop-fill me-2"></i>Остановить';
  $('progressSection').classList.add('d-none');
  
  // Добавляем запись в лог
  const logPanel = $('logPanel');
  if (logPanel) {
    const line = document.createElement('div');
    line.className = 'log-line';
    line.textContent = '⏹ Остановлено пользователем';
    logPanel.appendChild(line);
    logPanel.scrollTop = logPanel.scrollHeight;
  }
  
  // Отправляем запрос отмены в фоне (не ждём ответа — fire and forget)
  fetch(`${API}/cancel-task`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskIdToCancel })
  }).catch(() => {});
}

// ============ Анализ одного файла ============
async function handleFile(file) {
  if (!validateModels()) return;
  
  const ext = (file.name || '').toLowerCase();
  if (!['.docx', '.doc', '.pdf'].some(e => ext.endsWith(e))) {
    return showValidationError('Поддерживаются только .docx, .doc, .pdf');
  }

  const fd = new FormData();
  fd.append('file', file);
  fd.append('translate_model', $('translateModel').value);
  fd.append('annotate_model', $('annotateModel').value);
  fd.append('review_model', $('reviewModel').value);
  // Передаём параметры из режима разработчика
  fd.append('max_annotation_chars', $('maxAnnotationChars').value || 800);
  fd.append('max_review_iterations', $('maxReviewIterations').value || 2);

  const resultDiv = $('singleFileResult');
  resultDiv.classList.remove('d-none', 'alert-success', 'alert-danger', 'alert-warning');
  resultDiv.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Анализ...';

  try {
    const res = await fetch(`${API}/analyze-file`, { method: 'POST', body: fd });
    const data = await res.json();
    
    if (!res.ok) {
      const errorMsg = parseError(data);
      showValidationError(errorMsg);
      resultDiv.innerHTML = 'Ошибка: ' + escapeHtml(errorMsg);
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
        resultDiv.innerHTML = `<strong>${escapeHtml(row.original_name)}</strong>: готово`;
        resultDiv.classList.add(row.status === 'success' ? 'alert-success' : 'alert-danger');
        return;
      }
      if (st.status === 'failed') {
        resultDiv.innerHTML = 'Ошибка анализа';
        resultDiv.classList.add('alert-danger');
        return;
      }
      attempts++;
      if (attempts < 600) setTimeout(poll, 500);
      else resultDiv.innerHTML = '⏱ Таймаут ожидания';
    };
    poll();
  } catch (err) {
    resultDiv.innerHTML = 'Ошибка: ' + escapeHtml(err.message);
    resultDiv.classList.add('alert-danger');
  }
}
  
// ============ Результаты и таблица ============
async function loadResults(taskId) {
  const res = await fetch(`${API}/results/${taskId}`);
  const data = await res.json();
  currentTaskId = taskId;
  currentResults = data.results || [];
  renderTable(currentResults);
}

function getReviewBadge(status) {
  if (status === 'passed') return '<span class="badge bg-success">✓ Проверена</span>';
  if (status === 'warnings') return '<span class="badge bg-warning text-dark">⚠ Замечания</span>';
  if (status === 'failed') return '<span class="badge bg-danger">✗ Проблемы</span>';
  return '<span class="badge bg-secondary">–</span>';
}

function renderTable(results) {
  const filter = currentFilter;
  const search = $('searchInput')?.value || '';
  
  let rows = [...results];
  if (filter === 'success') rows = rows.filter(r => r.status === 'success');
  if (filter === 'error') rows = rows.filter(r => r.status !== 'success');
  
  const q = search.toLowerCase();
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

  const tbody = $('resultsBody');
  if (rows.length === 0) {
    const msg = results.length === 0 ? 'Результаты появятся после анализа' : 'Нет данных';
    tbody.innerHTML = `<tr><td colspan="5" class="text-muted text-center py-5">${msg}</td></tr>`;
    return;
  }
  
  tbody.innerHTML = rows.map(r => {
    const reviewBadge = getReviewBadge(r.review_status);
    const fixButton = (r.review_status === 'warnings' || r.review_status === 'failed') && r.status === 'success'
      ? `<button type="button" class="btn btn-sm btn-outline-success ms-1 fix-review-btn" data-file-name="${escapeHtml(r.file_name || '')}" data-original-name="${escapeHtml(r.original_name || '')}" title="Устранить замечания"><i class="bi bi-check2-square"></i> Устранить</button>`
      : '';
    
    return `<tr data-file="${(r.file_name || r.original_name || '').replace(/"/g, '&quot;')}">
      <td><span class="status-${r.status === 'success' ? 'ok' : 'err'}">${r.status === 'success' ? 'Прочитан' : 'Не прочитан'}</span></td>
      <td>${escapeHtml(r.original_name || r.file_name || '')}</td>
      <td>
        <span class="editable-title" contenteditable="true" data-file-name="${escapeHtml(r.file_name || '')}" data-original-name="${escapeHtml(r.original_name || '')}">${escapeHtml(r.title || '')}</span>
        <button type="button" class="btn btn-sm btn-outline-primary ms-1 save-title-btn d-none" title="Сохранить"><i class="bi bi-check"></i></button>
      </td>
      <td>
        ${reviewBadge}
        <button type="button" class="btn btn-sm btn-outline-info ms-1 review-details-btn" data-review="${escapeHtml(r.review_report || '')}" title="Подробности"><i class="bi bi-info-circle"></i></button>
        ${fixButton}
      </td>
      <td><div class="actions-cell">
        ${(r.status === 'success' && (r.file_path || r.file_name)) ? `<a href="${API}/files/${currentTaskId}/${encodeURIComponent(r.file_name || r.original_name || '')}" target="_blank" class="btn btn-sm btn-outline-secondary" title="Открыть файл"><i class="bi bi-folder2-open"></i></a>` : ''}
        ${(r.file_path || r.file_name) ? `<button type="button" class="btn btn-sm btn-outline-secondary regenerate-btn" data-file-name="${escapeHtml(r.file_name || '')}" data-original-name="${escapeHtml(r.original_name || '')}" title="Перегенерировать"><i class="bi bi-arrow-clockwise"></i></button>` : ''}
        <button type="button" class="btn btn-sm btn-outline-secondary copy-title-btn" data-title="${escapeHtml(r.title || '')}" title="Скопировать"><i class="bi bi-clipboard"></i></button>
      </div></td>
    </tr>`;
  }).join('');

  attachRowHandlers(tbody);
}

function attachRowHandlers(tbody) {
  // Редактирование названия
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
  
  tbody.querySelectorAll('.review-details-btn').forEach(btn => {
    btn.onclick = () => showReviewReport(btn.dataset.review || '');
  });
  
  tbody.querySelectorAll('.fix-review-btn').forEach(btn => {
    btn.onclick = () => {
      const fileName = btn.dataset.fileName || btn.dataset.originalName;
      fixReviewIssues(fileName);
    };
  });
  
  tbody.querySelectorAll('.regenerate-btn').forEach(btn => {
    btn.onclick = () => doRegenerate(btn);
  });
}

// ============ Сохранение названия ============
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
  } catch (e) {
    showValidationError('Ошибка сохранения');
  }
}

// ============ Перегенерация ============
async function doRegenerate(btn) {
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
        translate_model: $('translateModel').value,
        annotate_model: $('annotateModel').value,
        review_model: $('reviewModel').value
      })
    });
    const data = await res.json();
    
    if (res.ok && data.title) {
      const r = currentResults.find(x => (x.file_name || x.original_name) === fileName);
      if (r) {
        r.title = data.title;
        r.review_status = data.review_status || 'passed';
        r.review_report = data.review_report || '';
      }
      renderTable(currentResults);
    } else {
      throw new Error(parseError(data));
    }
  } catch (e) {
    showValidationError(e.message);
    btn.disabled = false;
    btn.innerHTML = origHtml;
  }
}

// ============ Устранение замечаний ============
async function fixReviewIssues(fileName) {
  if (!currentTaskId || !fileName) return;
  if (!validateModels()) return;
  
  const row = document.querySelector(`tr[data-file="${fileName.replace(/"/g, '&quot;')}"]`);
  const fixBtn = row?.querySelector('.fix-review-btn');
  if (!fixBtn) return;
  
  const origHtml = fixBtn.innerHTML;
  fixBtn.disabled = true;
  fixBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Устранение...';
  
  try {
    const res = await fetch(`${API}/fix-review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        task_id: currentTaskId,
        file_name: fileName,
        translate_model: $('translateModel').value,
        annotate_model: $('annotateModel').value,
        review_model: $('reviewModel').value
      })
    });
    const data = await res.json();
    
    if (res.ok && data.title) {
      const r = currentResults.find(x => (x.file_name || x.original_name) === fileName);
      if (r) {
        r.title = data.title;
        r.review_status = data.review_status || 'passed';
        r.review_report = data.review_report || '';
      }
      renderTable(currentResults);
    } else {
      throw new Error(parseError(data));
    }
  } catch (e) {
    showValidationError(e.message);
    fixBtn.disabled = false;
    fixBtn.innerHTML = origHtml;
  }
}

// ============ Модалка отчёта проверки ============
function showReviewReport(report) {
  const existing = $('reviewReportModal');
  if (existing) existing.remove();
  
  const modalHtml = `
    <div class="modal fade" id="reviewReportModal" tabindex="-1">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">Результат проверки</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <pre style="white-space: pre-wrap; word-break: break-word;">${escapeHtml(report)}</pre>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>
          </div>
        </div>
      </div>
    </div>
  `;
  
  document.body.insertAdjacentHTML('beforeend', modalHtml);
  const modal = new bootstrap.Modal($('reviewReportModal'));
  modal.show();
  
  $('reviewReportModal').addEventListener('hidden.bs.modal', () => {
    $('reviewReportModal').remove();
  });
}

// ============ Экспорт ============
function exportUrl(format) {
  if (!currentTaskId) {
    showValidationError('Сначала выполните анализ');
    return null;
  }
  return `${API}/export/${currentTaskId}?format=${format}`;
}

// ============ Привязка обработчиков ============
function bindEventHandlers() {
  // Тема
  const themeBtn = $('themeToggle');
  if (themeBtn) themeBtn.onclick = toggleTheme;

  // Обновить модели
  const refreshBtn = $('refreshModels');
  if (refreshBtn) {
    refreshBtn.onclick = async () => {
      refreshBtn.disabled = true;
      refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Загрузка...';
      await loadModels();
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-1"></i>Обновить список моделей';
    };
  }

  // Сбросить модели
  const resetBtn = $('resetModels');
  if (resetBtn) {
    resetBtn.onclick = () => {
      ['translateModel', 'annotateModel', 'reviewModel'].forEach(id => {
        const sel = $(id);
        if (sel) sel.selectedIndex = 0;
      });
    };
  }

  // Иконка свертывания настроек
  const modelToggle = document.querySelector('[data-bs-toggle="collapse"][data-bs-target="#modelSettings"]');
  if (modelToggle) {
    modelToggle.addEventListener('click', () => {
      const icon = $('modelSettingsIcon');
      if (icon) {
        icon.classList.toggle('bi-chevron-down');
        icon.classList.toggle('bi-chevron-up');
      }
    });
  }

  // Переключение режима (папка/файл)
  document.querySelectorAll('[data-mode]').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      document.querySelectorAll('.nav-pills .nav-link').forEach(l => l.classList.remove('active'));
      btn.classList.add('active');
      $('folderSection').classList.remove('active');
      $('fileSection').classList.remove('active');
      $(btn.dataset.mode === 'folder' ? 'folderSection' : 'fileSection').classList.add('active');
    });
  });

  // Обзор папок
  const browseSourceBtn = $('browseSource');
  if (browseSourceBtn) {
    browseSourceBtn.onclick = () => {
      browseTarget = 'source';
      const currentPath = $('sourceFolder').value;
      $('browsePath').value = currentPath;
      loadBrowse(currentPath || undefined);
      const modal = initBrowseModal();
      if (modal) modal.show();
    };
  }

  const browseOutputBtn = $('browseOutput');
  if (browseOutputBtn) {
    browseOutputBtn.onclick = () => {
      browseTarget = 'output';
      const currentPath = $('outputFolder').value;
      $('browsePath').value = currentPath;
      loadBrowse(currentPath || undefined);
      const modal = initBrowseModal();
      if (modal) modal.show();
    };
  }

  const browsePathInput = $('browsePath');
  if (browsePathInput) {
    browsePathInput.addEventListener('change', () => loadBrowse(browsePathInput.value));
    browsePathInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        loadBrowse(browsePathInput.value);
      }
    });
  }

  // Выбор папки в модалке
  const selectFolderBtn = $('selectFolderBtn');
  if (selectFolderBtn) {
    selectFolderBtn.onclick = () => {
      const path = $('browsePath').value;
      if (path && browseTarget) {
        if (browseTarget === 'source') $('sourceFolder').value = path;
        else $('outputFolder').value = path;
        const modal = initBrowseModal();
        if (modal) modal.hide();
      }
    };
  }

  // Запуск анализа папки
  const runBtn = $('runFolder');
  if (runBtn) runBtn.onclick = runFolderAnalysis;

  // Остановка
  const stopBtn = $('stopFolder');
  if (stopBtn) stopBtn.onclick = stopFolderAnalysis;

  // Drag & drop для файла
  const dropZone = $('dropZone');
  const fileInput = $('fileInput');
  
  if (dropZone && fileInput) {
    dropZone.onclick = () => fileInput.click();
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(ev => {
      dropZone.addEventListener(ev, (e) => {
        e.preventDefault();
        e.stopPropagation();
      });
    });
    
    dropZone.addEventListener('dragenter', () => dropZone.classList.add('dragover'));
    dropZone.addEventListener('dragover', () => dropZone.classList.add('dragover'));
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
      dropZone.classList.remove('dragover');
      const f = e.dataTransfer.files[0];
      if (f) handleFile(f);
    });
    
    fileInput.onchange = () => {
      const f = fileInput.files[0];
      if (f) handleFile(f);
    };
  }

  // Лог-панель
  const logReset = $('logReset');
  if (logReset) logReset.onclick = () => { $('logPanel').innerHTML = ''; };
  
  const logHide = $('logHide');
  if (logHide) {
    logHide.onclick = () => {
      $('logSection').classList.add('d-none');
      $('logShow').classList.remove('d-none');
    };
  }
  
  const logShow = $('logShow');
  if (logShow) {
    logShow.onclick = () => {
      $('logSection').classList.remove('d-none');
      $('logShow').classList.add('d-none');
    };
  }

  // Экспорт
  const exportCsv = $('exportCsv');
  if (exportCsv) {
    exportCsv.onclick = () => {
      const url = exportUrl('csv');
      if (url) window.open(url, '_blank');
    };
  }
  
  const exportExcel = $('exportExcel');
  if (exportExcel) {
    exportExcel.onclick = () => {
      const url = exportUrl('excel');
      if (url) window.open(url, '_blank');
    };
  }

  // Сброс результатов
  const resetResults = $('resetResults');
  if (resetResults) {
    resetResults.onclick = () => {
      currentTaskId = null;
      currentResults = [];
      document.querySelectorAll('[data-filter]').forEach(b => {
        b.classList.remove('active');
        if (b.dataset.filter === 'all') b.classList.add('active');
      });
      currentFilter = 'all';
      const searchInput = $('searchInput');
      if (searchInput) searchInput.value = '';
      renderTable([]);
    };
  }

  // Фильтры
  document.querySelectorAll('[data-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-filter]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      renderTable(currentResults);
    });
  });

  // Поиск
  const searchInput = $('searchInput');
  if (searchInput) {
    searchInput.addEventListener('input', () => renderTable(currentResults));
  }

  // Сортировка
  document.querySelectorAll('#resultsTable th[data-sort]').forEach(th => {
    th.addEventListener('click', () => {
      if (sortColumn === th.dataset.sort) sortAsc = !sortAsc;
      else { sortColumn = th.dataset.sort; sortAsc = true; }
      renderTable(currentResults);
    });
  });

  // Режим разработчика - иконка свертывания
  const devToggle = document.querySelector('[data-bs-toggle="collapse"][data-bs-target="#devSettings"]');
  if (devToggle) {
    devToggle.addEventListener('click', () => {
      const icon = $('devSettingsIcon');
      if (icon) {
        icon.classList.toggle('bi-chevron-down');
        icon.classList.toggle('bi-chevron-up');
      }
    });
  }

  // Сохранение промтов
  const savePromptsBtn = $('savePrompts');
  if (savePromptsBtn) {
    savePromptsBtn.onclick = savePromptsToServer;
  }

  // Сброс промтов
  const resetPromptsBtn = $('resetPrompts');
  if (resetPromptsBtn) {
    resetPromptsBtn.onclick = resetPromptsToDefault;
  }
  
  // Загружаем промты при инициализации
  loadPromptsFromServer();
}

// ============ Режим разработчика: Промты ============
async function loadPromptsFromServer() {
  try {
    const res = await fetch(`${API}/prompts`);
    if (!res.ok) {
      console.warn('[loadPrompts] Не удалось загрузить:', res.status);
      return;
    }
    
    const data = await res.json();
    defaultPrompts = data.default_prompts || {};
    const current = data.current_prompts || {};
    
    // Заполняем поля текущими значениями
    $('promptTranslate').value = current.translate || defaultPrompts.translate || '';
    $('promptAnnotate').value = current.annotate || defaultPrompts.annotate || '';
    $('promptReview').value = current.review || defaultPrompts.review || '';
    $('promptFix').value = current.fix || defaultPrompts.fix || '';
    
    // Заполняем поля настроек
    if (data.config) {
      $('maxAnnotationChars').value = data.config.max_annotation_chars || 800;
      $('maxReviewIterations').value = data.config.max_review_iterations || 2;
    }
    
    console.log('[loadPrompts] Промты загружены');
  } catch (err) {
    console.error('[loadPrompts] Ошибка:', err);
  }
}

function resetPromptsToDefault() {
  if (Object.keys(defaultPrompts).length === 0) {
    showValidationError('Стандартные промты ещё не загружены');
    return;
  }
  
  $('promptTranslate').value = defaultPrompts.translate || '';
  $('promptAnnotate').value = defaultPrompts.annotate || '';
  $('promptReview').value = defaultPrompts.review || '';
  $('promptFix').value = defaultPrompts.fix || '';
  
  // Сбрасываем настройки к стандартным
  $('maxAnnotationChars').value = 800;
  $('maxReviewIterations').value = 2;
}

async function savePromptsToServer() {
  const btn = $('savePrompts');
  if (!btn) return;
  
  const origHtml = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Сохранение...';
  
  try {
    const res = await fetch(`${API}/prompts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompts: {
          translate: $('promptTranslate').value,
          annotate: $('promptAnnotate').value,
          review: $('promptReview').value,
          fix: $('promptFix').value
        },
        config: {
          max_annotation_chars: parseInt($('maxAnnotationChars').value) || 800,
          max_review_iterations: parseInt($('maxReviewIterations').value) || 2
        }
      })
    });
    
    if (!res.ok) throw new Error('Ошибка сохранения: ' + res.status);
    
    btn.innerHTML = '<i class="bi bi-check me-1"></i>Сохранено';
    setTimeout(() => {
      btn.disabled = false;
      btn.innerHTML = '<i class="bi bi-save me-1"></i>Сохранить в файлы';
    }, 1500);
    
  } catch (err) {
    showValidationError('Ошибка сохранения: ' + err.message);
    btn.disabled = false;
    btn.innerHTML = origHtml;
  }
}

// ============ Инициализация ============
async function initializeApp() {
  console.log('[init] starting...');
  initTheme();
  bindEventHandlers();
  console.log('[init] handlers bound');
  
  // Запускаем загрузку моделей и проверку параллельно
  loadModels();
  checkConnection();
}

// Запуск после загрузки DOM
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeApp);
} else {
  initializeApp();
}
