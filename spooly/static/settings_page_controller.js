(() => {
  const themeButtons = Array.from(document.querySelectorAll('[data-theme-preference]'));
  const refreshButton = document.getElementById('refresh-library');
  const clearCacheButton = document.getElementById('clear-cache');
  const resetButton = document.getElementById('reset-recommendations');
  const credentialMask = document.getElementById('credential-mask');
  function currentThemePreference() {
    const saved = localStorage.getItem('theme');
    return ['light', 'dark', 'system'].includes(saved) ? saved : 'system';
  }

  function syncThemeButtons(preference = currentThemePreference()) {
    themeButtons.forEach((button) => {
      const active = button.dataset.themePreference === preference;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  function setThemePreference(preference) {
    if (window.themeManager?.setPreference) {
      window.themeManager.setPreference(preference);
    } else {
      localStorage.setItem('theme', preference);
      const resolved = preference === 'system'
        ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
        : preference;
      document.body.setAttribute('data-theme', resolved);
    }
    syncThemeButtons(preference);
  }


  async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const payload = await response.json();
    if (!response.ok || payload.success === false) {
      const message = typeof payload.error === 'object' ? payload.error?.message : payload.error;
      throw new Error(message || 'Request failed');
    }
    return payload;
  }

  async function requestForm(url, formData) {
    const response = await fetch(url, { method: 'POST', body: formData });
    const payload = await response.json();
    if (!response.ok || payload.success === false) throw new Error(payload.error || 'Request failed');
    return payload;
  }

  function formatSyncTime(value) {
    if (!value) return 'No scan completed yet';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return 'A scan completed recently';
    return `Last scanned: ${date.toLocaleString('en')}`;
  }

  async function loadStats() {
    try {
      const payload = await requestJson('/api/library/stats');
      const videos = Number(payload.videos || 0);
      const images = Number(payload.images || 0);
      document.getElementById('media-total').textContent = Number(payload.indexed_total || videos + images);
      document.getElementById('videos-count').textContent = videos;
      document.getElementById('images-count').textContent = images;
      document.getElementById('cache-size').textContent = `${Number(payload.cache_mb || 0)} MB`;
      document.getElementById('index-sync-copy').textContent = formatSyncTime(payload.last_synced_at);
      document.getElementById('index-sync-state').classList.remove('is-error');
    } catch (error) {
      document.getElementById('index-sync-copy').textContent = 'Index status is unavailable';
      document.getElementById('index-sync-state').classList.add('is-error');
    }
  }

  async function confirmAction(title, copy, actionLabel, tone, onConfirm) {
    if (await SpoolyUI.confirm({ title, message: copy, confirmLabel: actionLabel, tone })) onConfirm();
  }

  async function runButton(button, busyLabel, task) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = busyLabel;
    try { await task(); } finally { button.disabled = false; button.textContent = original; }
  }

  function renderCredentials(files = []) {
    const list = document.getElementById('credential-list');
    document.getElementById('credential-summary').textContent = files.length ? `${files.length} credential files saved and matched to websites automatically.` : 'None added. Public content can still be downloaded.';
    if (!files.length) {
      list.innerHTML = '<div class="credential-empty">No credentials saved</div>';
    } else {
      list.innerHTML = files.map((name) => `
        <div class="credential-item"><span class="credential-mark"><i data-feather="key"></i></span><span class="credential-name"></span></div>`).join('');
      list.querySelectorAll('.credential-name').forEach((element, index) => { element.textContent = files[index]; });
    }
    feather.replace();
  }

  async function loadDownloadSettings() {
    try {
      const [probePayload, configPayload, cookiePayload] = await Promise.all([
        requestJson('/api/download/probe', { method: 'POST' }),
        requestJson('/api/download/config'),
        requestJson('/api/download/cookies'),
      ]);
      const probe = probePayload.data || {};
      const missing = [!probe.yt_dlp_available ? 'video' : '', !probe.gallery_dl_available ? 'image' : '', !probe.ffmpeg_available ? 'media merging' : ''].filter(Boolean);
      document.getElementById('download-dependency-copy').textContent = missing.length ? `${missing.join(', ')} components are not ready.` : 'Image and video downloads are ready.';
      const configured = Number(configPayload.data?.effective?.max_concurrent ?? 2);
      const shown = [1, 2, 4].includes(configured) ? configured : 2;
      document.querySelectorAll('[data-concurrency]').forEach((button) => button.classList.toggle('is-active', Number(button.dataset.concurrency) === shown));
      renderCredentials(cookiePayload.data?.files || []);
    } catch (_) {
      document.getElementById('download-dependency-copy').textContent = 'Download status is unavailable.';
      document.getElementById('credential-summary').textContent = 'Credentials are unavailable.';
    }
  }

  function openCredentials() {
    credentialMask.hidden = false;
    document.body.style.overflow = 'hidden';
    document.getElementById('close-credentials').focus();
  }

  function closeCredentials() {
    credentialMask.hidden = true;
    document.body.style.overflow = '';
    document.getElementById('manage-credentials').focus();
  }

  themeButtons.forEach((button) => button.addEventListener('click', () => setThemePreference(button.dataset.themePreference)));
  window.addEventListener('spooly:theme-changed', (event) => syncThemeButtons(event.detail?.preference));
  syncThemeButtons();

  refreshButton.addEventListener('click', () => {
    confirmAction('Rescan the media library?', 'The scan will reconcile files added, moved, or deleted while OwnFlick was running.', 'Start Scan', 'primary', () => {
      runButton(refreshButton, 'Scanning…', async () => {
        const payload = await requestJson('/api/library/sync', { method: 'POST' });
        await loadStats();
        SpoolyUI.toast(`Scan complete. Indexed ${Number(payload.data?.indexed || 0)} media items.`);
      }).catch(() => SpoolyUI.toast('Scan failed. Please try again later.', 'error'));
    });
  });

  clearCacheButton.addEventListener('click', () => {
    confirmAction('Clear the thumbnail cache?', 'Original media will be kept. Thumbnails regenerate as needed while browsing.', 'Clear Cache', 'warning', () => {
      runButton(clearCacheButton, 'Clearing…', async () => {
        const payload = await requestJson('/api/cache/clear', { method: 'POST' });
        await loadStats();
        SpoolyUI.toast(`Freed ${Number(payload.freed_mb || 0)} MB`);
      }).catch(() => SpoolyUI.toast('Cleanup failed. Please try again later.', 'error'));
    });
  });

  resetButton.addEventListener('click', () => {
    confirmAction('Reset recommendation history?', 'Views, skips, completions, and resume points will be cleared. Favorites and collections remain unchanged.', 'Reset History', 'danger', () => {
      runButton(resetButton, 'Resetting…', async () => {
        await requestJson('/api/activity', { method: 'DELETE' });
        SpoolyUI.toast('Recommendation history reset');
      }).catch(() => SpoolyUI.toast('Reset failed. Please try again later.', 'error'));
    });
  });

  document.getElementById('download-levels').addEventListener('click', async (event) => {
    const button = event.target.closest('[data-concurrency]');
    if (!button) return;
    const maxConcurrent = Number(button.dataset.concurrency);
    try {
      await requestJson('/api/download/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ max_concurrent: maxConcurrent }),
      });
      document.querySelectorAll('[data-concurrency]').forEach((item) => item.classList.toggle('is-active', item === button));
      SpoolyUI.toast(`Concurrent downloads set to ${maxConcurrent}`);
    } catch (_) { SpoolyUI.toast('Failed to save download settings', 'error'); }
  });

  document.getElementById('manage-credentials').addEventListener('click', openCredentials);
  document.getElementById('close-credentials').addEventListener('click', closeCredentials);
  credentialMask.addEventListener('click', (event) => { if (event.target === credentialMask) closeCredentials(); });
  credentialMask.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeCredentials(); });
  document.getElementById('upload-credential').addEventListener('click', (event) => {
    const input = document.getElementById('credential-file');
    const file = input.files?.[0];
    if (!file) { SpoolyUI.toast('Select a credential file first', 'error'); return; }
    runButton(event.currentTarget, 'Uploading…', async () => {
      const formData = new FormData();
      formData.append('file', file);
      await requestForm('/api/download/cookies/upload', formData);
      input.value = '';
      const payload = await requestJson('/api/download/cookies');
      renderCredentials(payload.data?.files || []);
      SpoolyUI.toast('Credentials updated');
    }).catch(() => SpoolyUI.toast('Failed to upload credentials', 'error'));
  });

  function formatBytes(bytes) {
    const mb = Number(bytes || 0) / 1048576;
    return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(1)} MB`;
  }

  function renderTrash(items, retentionDays) {
    const list = document.getElementById('trash-list');
    const total = items.reduce((sum, item) => sum + Number(item.size || 0), 0);
    document.getElementById('trash-summary').textContent = items.length
      ? `${items.length} ${items.length === 1 ? 'item' : 'items'} · ${formatBytes(total)}. Kept for ${retentionDays} days, then removed.`
      : `Deleted media stays here for ${retentionDays} days.`;
    document.getElementById('empty-trash').hidden = !items.length;
    list.querySelectorAll('.trash-item').forEach((row) => row.remove());
    items.forEach((item) => {
      const days = Math.max(0, retentionDays - Math.floor((Date.now() - new Date(item.deleted_at)) / 86400000));
      const row = document.createElement('div');
      row.className = 'settings-row trash-item';
      row.innerHTML = `<span class="setting-icon"><i data-feather="${/\.(jpe?g|png|gif|webp|bmp)$/i.test(item.name) ? 'image' : 'film'}"></i></span><div class="settings-row-main"><div class="settings-row-title trash-name"></div><div class="settings-row-copy"></div></div>`;
      row.querySelector('.trash-name').textContent = item.name;
      row.querySelector('.settings-row-copy').textContent = `${formatBytes(item.size)} · ${days} days left`;
      const restore = document.createElement('button');
      restore.className = 'settings-action';
      restore.type = 'button';
      restore.textContent = 'Restore';
      restore.addEventListener('click', () => {
        runButton(restore, 'Restoring…', async () => {
          const data = await requestJson(`/api/trash/${encodeURIComponent(item.id)}/restore`, { method: 'POST' });
          await Promise.all([loadTrash(), loadStats()]);
          SpoolyUI.toast(`Restored ${item.name}`, 'success', { label: 'Open', run: () => { location.href = data.url; } });
        }).catch((error) => SpoolyUI.toast(error.message || 'Restore failed. Please try again.', 'error'));
      });
      const purge = document.createElement('button');
      purge.className = 'settings-action is-danger';
      purge.type = 'button';
      purge.textContent = 'Delete';
      purge.addEventListener('click', () => {
        confirmAction(`Delete ${item.name} permanently?`, 'The file is removed from disk and cannot be restored.', 'Delete', 'danger', () => {
          runButton(purge, 'Deleting…', async () => {
            await requestJson(`/api/trash/${encodeURIComponent(item.id)}`, { method: 'DELETE' });
            await loadTrash();
          }).catch(() => SpoolyUI.toast('Delete failed. Please try again.', 'error'));
        });
      });
      row.querySelector('.settings-row-main').after(restore, purge);
      list.appendChild(row);
    });
    feather.replace();
  }

  async function loadTrash() {
    try {
      const data = await requestJson('/api/trash');
      renderTrash(data.items || [], data.retention_days || 30);
    } catch (_) {
      document.getElementById('trash-summary').textContent = 'Trash is unavailable.';
    }
  }

  document.getElementById('empty-trash').addEventListener('click', (event) => {
    const button = event.currentTarget;
    confirmAction('Empty the trash?', 'Every file in the trash is removed from disk and cannot be restored.', 'Empty Trash', 'danger', () => {
      runButton(button, 'Emptying…', async () => {
        const data = await requestJson('/api/trash', { method: 'DELETE' });
        await loadTrash();
        SpoolyUI.toast(`Deleted ${data.purged} items permanently`);
      }).catch(() => SpoolyUI.toast('Failed to empty the trash. Please try again.', 'error'));
    });
  });

  loadStats();
  loadTrash();
  loadDownloadSettings();
})();
