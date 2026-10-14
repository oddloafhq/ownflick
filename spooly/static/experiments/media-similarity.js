document.addEventListener('DOMContentLoaded', async () => {
  const section = document.getElementById('similar-media-section');
  if (!section) return;
  try {
    const response = await fetch(`/api/recommend/similar?uri=${encodeURIComponent(section.dataset.uri)}&limit=${section.dataset.limit}`);
    const result = await response.json();
    if (!response.ok || !result.success || !result.data?.indexed) return;
    const grid = document.getElementById('similar-media-grid');
    for (const item of result.data.items || []) {
      const link = document.createElement('a');
      link.href = item.detail_url;
      link.className = 'flex flex-col overflow-hidden rounded-lg';
      link.title = item.title;
      const preview = document.createElement('figure');
      preview.className = section.dataset.mediaType === 'video' ? 'aspect-video' : 'aspect-square';
      const image = document.createElement('img');
      image.src = item.thumb_url;
      image.alt = item.title;
      image.loading = 'lazy';
      image.className = 'h-full w-full object-cover';
      preview.appendChild(image);
      link.appendChild(preview);
      if (section.dataset.mediaType === 'video') {
        const title = document.createElement('span');
        title.className = 'truncate py-2 text-sm';
        title.textContent = item.title;
        link.appendChild(title);
      }
      grid.appendChild(link);
    }
    section.hidden = grid.childElementCount === 0;
  } catch (error) {
    section.hidden = true;
  }
});
