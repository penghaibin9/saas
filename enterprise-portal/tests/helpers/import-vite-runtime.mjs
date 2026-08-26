import { readFile } from 'node:fs/promises'

function dataModule(source, tag) {
  return `data:text/javascript;base64,${Buffer.from(source).toString('base64')}#${tag}`
}

function importClause(specifier) {
  return 'fr' + 'om ' + JSON.stringify(specifier)
}

export async function importEnterpriseRuntime() {
  const nonce = `${Date.now()}-${Math.random()}`
  const requestFile = new URL('../../src/services/request.js', import.meta.url)
  const contractFile = new URL('../../src/services/enterpriseContract.js', import.meta.url)
  const apiFile = new URL('../../src/services/enterpriseInternshipApi.js', import.meta.url)

  const [requestSourceRaw, contractSource, apiSourceRaw] = await Promise.all([
    readFile(requestFile, 'utf8'),
    readFile(contractFile, 'utf8'),
    readFile(apiFile, 'utf8'),
  ])

  const requestSource = requestSourceRaw.replaceAll(
    'import.meta.env',
    "({ VITE_API_BASE_URL: '', DEV: false })",
  )
  const requestUrl = dataModule(requestSource, `request-${nonce}`)
  const contractUrl = dataModule(contractSource, `contract-${nonce}`)
  const apiSource = apiSourceRaw
    .replace(importClause('./request.js'), importClause(requestUrl))
    .replace(importClause('./enterpriseContract.js'), importClause(contractUrl))
  const apiUrl = dataModule(apiSource, `api-${nonce}`)

  const [requestModule, apiModule] = await Promise.all([
    import(requestUrl),
    import(apiUrl),
  ])

  return { requestModule, apiModule }
}
