/** 学工 API 契约测试用 mock http client（由 registerHooks 劫持 @/services/http/client） */
const calls = globalThis.__SA_API_CONTRACT_CALLS__ || (globalThis.__SA_API_CONTRACT_CALLS__ = [])

export async function request(path, { method = 'GET', body, params } = {}) {
  const throwSpec = globalThis.__SA_API_CONTRACT_THROW__
  if (throwSpec) {
    const err = new Error(throwSpec.message || 'biz error')
    err.biz = !!throwSpec.biz
    err.code = throwSpec.code
    err.bizCode = throwSpec.bizCode
    throw err
  }
  calls.push({
    path,
    method: String(method || 'GET').toUpperCase(),
    body: body == null ? undefined : { ...body },
    params: params == null ? undefined : { ...params }
  })
  return { ok: true, items: [], total: 0 }
}

export async function requestBlob() {
  throw new Error('requestBlob not mocked for contract test')
}

export async function requestUpload() {
  throw new Error('requestUpload not mocked for contract test')
}
