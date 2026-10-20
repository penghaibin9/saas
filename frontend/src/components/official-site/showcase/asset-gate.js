export const SHOWCASE_VERSION = '20260909-pc40-wechat20'
export const RELEASE_URL = '/official-site/showcase-20260909/release.json'

export function validRelease(value) {
  return value?.version === SHOWCASE_VERSION && value.assetCount === 143 && value.businessCount === 67 && value.expandedCount === 60
}

// A half-uploaded asset release must never replace the working public homepage.
export async function hasShowcaseAssets({ fetcher = globalThis.fetch, signal, timeoutMs = 2500 } = {}) {
  if (!fetcher || signal?.aborted) return false
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  const timer = setTimeout(abort, timeoutMs)
  try {
    const response = await fetcher(RELEASE_URL, { signal: controller.signal, headers: { Accept: 'application/json' }, cache: 'no-cache', credentials: 'omit' })
    if (!response.ok) return false
    return validRelease(await response.json())
  } catch { return false } finally { clearTimeout(timer); signal?.removeEventListener('abort', abort) }
}
