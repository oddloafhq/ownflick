(() => {
  'use strict';
  const start = document.getElementById('media-index-start');
  const pause = document.getElementById('media-index-pause');
  const progress = document.getElementById('media-index-progress');
  if (!start) return;
  const active = ['running', 'pausing', 'grouping'];
  let reloadWhenFinished = false;

  async function post(url) {
    const response = await fetch(url, { method: 'POST' });
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.error || 'The request failed.');
    return result.data;
  }

  function show(job) {
    const running = active.includes(job.state);
    start.hidden = running;
    pause.hidden = !running;
    pause.disabled = job.state === 'pausing';
    if (job.state === 'running' || job.state === 'pausing') {
      progress.textContent = `${job.processed} of ${job.total} files · ${job.failed} failed${job.state === 'pausing' ? ' · Pausing…' : ''}`;
    } else if (job.state === 'grouping') {
      progress.textContent = 'Choosing related photo groups on this device…';
    } else if (job.state === 'failed') {
      progress.textContent = job.error || 'Preparation failed.';
    }
    if (running) {
      reloadWhenFinished = true;
      setTimeout(refresh, 2500);
    } else if (reloadWhenFinished) {
      window.location.reload();
    }
  }

  async function refresh() {
    try {
      const response = await fetch('/api/ai/embedding-index/job');
      const result = await response.json();
      if (!response.ok || !result.success) throw new Error(result.error || 'Could not read progress.');
      show(result.data);
    } catch (error) {
      progress.textContent = error.message;
      setTimeout(refresh, 5000);
    }
  }

  start.addEventListener('click', async () => {
    start.disabled = true;
    progress.textContent = 'Starting…';
    try {
      show(await post('/api/ai/embedding-index/run'));
    } catch (error) {
      progress.textContent = error.message;
      start.disabled = false;
    }
  });
  pause.addEventListener('click', async () => {
    pause.disabled = true;
    try {
      show(await post('/api/ai/embedding-index/pause'));
    } catch (error) {
      progress.textContent = error.message;
      pause.disabled = false;
    }
  });
  refresh();
})();
