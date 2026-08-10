const HELP_QUERY_STOP_WORDS = new Set([
  '为什么', '什么', '怎么', '怎样', '如何', '请问', '我', '我的', '我要', '我想',
  '了', '呢', '吗', '啊', '呀', '吧', '不', '不了', '不能', '无法', '是否', '能否'
])

export function normalizeHelpQuery(value) {
  const raw = String(value || '')
  try {
    return raw.normalize('NFKC').trim().toLowerCase()
  } catch {
    return raw.trim().toLowerCase()
  }
}

/**
 * 问题式搜索不能要求整句连续命中。
 * 优先使用 Intl.Segmenter 做中文/英文混合分词，过滤“为什么/怎么/不了”等问句噪声；
 * 这样“为什么成绩提交不了”会落到“成绩 + 提交”，“成绩 409”会落到“成绩 + 409”。
 */
export function tokenizeHelpQuery(query) {
  const normalized = normalizeHelpQuery(query)
  if (!normalized) return []

  let parts = []
  try {
    if (typeof Intl !== 'undefined' && typeof Intl.Segmenter === 'function') {
      const segmenter = new Intl.Segmenter('zh-CN', { granularity: 'word' })
      parts = [...segmenter.segment(normalized)]
        .filter((item) => item.isWordLike)
        .map((item) => item.segment)
    }
  } catch {
    parts = []
  }
  if (!parts.length) {
    parts = normalized
      .replace(/为什么|怎么办|怎么|怎样|如何|请问|不了|不能|无法|是否|能否/g, ' ')
      .split(/[^0-9a-z\u4e00-\u9fff_.:-]+/i)
  }

  return [...new Set(parts
    .map((part) => normalizeHelpQuery(part))
    .filter(Boolean)
    .filter((part) => !HELP_QUERY_STOP_WORDS.has(part)))]
}

export function matchesHelpSearchText(searchText, query) {
  const haystack = normalizeHelpQuery(searchText)
  const q = normalizeHelpQuery(query)
  if (!q) return true
  if (haystack.includes(q)) return true
  const tokens = tokenizeHelpQuery(q)
  if (!tokens.length) return false
  return tokens.every((token) => haystack.includes(token))
}
