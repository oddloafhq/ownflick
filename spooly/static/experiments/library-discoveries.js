(() => {
  const section = document.getElementById('library-discoveries');
  const grid = document.getElementById('library-discoveries-grid');
  if (window.location.hash === '#semantic-search-panel') {
    document.getElementById('semantic-search-panel').open = true;
  }
  if (!section || !grid) return;

  fetch('/api/library/similar-groups?limit=4&min_group_size=3')
    .then(response => response.ok ? response.json() : null)
    .then(payload => {
      if (!payload?.success) return;
      for (const group of payload.data.items || []) {
        const items = (group.items || []).slice(0, 4);
        if (items.length < 3) continue;
        const card = document.createElement('div');
        card.className = 'grid aspect-square grid-cols-2 grid-rows-2 gap-0.5 overflow-hidden rounded-lg';
        for (const [index, item] of items.entries()) {
          const link = document.createElement('a');
          link.href = item.detail_url;
          link.className = `block min-w-0 overflow-hidden${items.length === 3 && index === 0 ? ' row-span-2' : ''}`;
          link.title = item.name;
          const image = document.createElement('img');
          image.src = item.thumb_url;
          image.alt = item.name;
          image.loading = 'lazy';
          image.className = 'h-full w-full object-cover';
          link.appendChild(image);
          card.appendChild(link);
        }
        grid.appendChild(card);
      }
      section.hidden = !grid.childElementCount || section.dataset.searching === 'true' ||
        !!new URLSearchParams(window.location.search).get('q');
    })
    .catch(() => {});
})();
