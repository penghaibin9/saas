/** Public headline cards: textContent only; published API, never untrusted HTML. */
export function mountNewsPreview(root, { fetcher = globalThis.fetch } = {}) {
  const target = root.querySelector('#news-preview')
  if (!target || !fetcher) return () => {}
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 5000)
  let active = true
  fetcher('/api/v1/website-news/latest', { signal: controller.signal, credentials: 'omit' })
    .then(r => { if(!r.ok) throw new Error('News unavailable'); return r.json() })
    .then(payload => {
      if(!active || payload.code !== 0 || !Array.isArray(payload.data?.items)) return
      const items = payload.data.items.slice(0,3)
      if(!items.length) return
      const doc=root.ownerDocument, fragment=doc.createDocumentFragment()
      for(const item of items) {
        if(typeof item.url !== 'string' || !/^\/news\/news-[a-f0-9]{32}$/.test(item.url)) continue
        const card=doc.createElement('article'), label=doc.createElement('small'), heading=doc.createElement('h3'), link=doc.createElement('a'), summary=doc.createElement('p')
        card.className='news-card';label.textContent=item.categoryName || '教育动态';link.href=item.url;link.textContent=item.title;summary.textContent=item.summary
        heading.append(link);card.append(label,heading,summary);fragment.append(card)
      }
      if(fragment.childNodes.length) target.replaceChildren(fragment)
    }).catch(() => { /* Keep real newsroom link; no fake news or empty success state. */ })
    .finally(() => clearTimeout(timer))
  return () => { active=false;controller.abort();clearTimeout(timer) }
}
