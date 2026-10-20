/** Shared SELF protocol only: no role grants, token issuance, SMS or identity writer.
 * Each surface injects its original authenticated transport and session generation.
 * Password/OTP/grants live only in this mounted flow, never storage or URLs.
 */
export const phoneBindingState = () => ({ binding: null, busy: false, step: 'LOADING',
  error: '', note: '', phone: '', currentPassword: '', code: '', reason: '', purpose: '', expiresAt: 0, result: null })

export async function phoneFlowNonce() {
  let bytes
  if (globalThis.crypto?.getRandomValues) {
    bytes = globalThis.crypto.getRandomValues(new Uint8Array(24))
  } else if (typeof wx !== 'undefined' && wx.getRandomValues) {
    // Existing installed WeChat API typings: length + success.randomValues (ArrayBuffer).
    const buffer = await new Promise((resolve, reject) => wx.getRandomValues({ length: 24,
      success: value => resolve(value.randomValues), fail: reject }))
    bytes = new Uint8Array(buffer)
  } else throw Error('当前环境缺少安全随机数支持，请使用受支持浏览器或更新微信')
  if (bytes.length !== 24) throw Error('安全随机数不可用，请重新打开页面')
  return Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('')
}

export function createPhoneBindingFlow(state, { request, sessionKey, random = phoneFlowNonce }) {
  const generation = sessionKey()
  let alive = true, proof = null
  const clearInputs = () => { state.phone = ''; state.currentPassword = ''; state.code = ''; state.reason = '' }
  const current = () => {
    if (!alive) return false
    if (sessionKey() !== generation) {
      alive = false; proof = null; clearInputs(); state.binding = null; state.busy = false
      state.step = 'SESSION_CHANGED'; state.error = '学校或登录身份已变化，请重新进入账号安全'
      return false
    }
    return true
  }
  const call = (path = '', body, extra = {}) => request('/auth/phone-binding' + path,
    { method: body ? 'POST' : 'GET', body, noAuthRetry: true, ...extra })
  const validProof = () => {
    if (!proof || !Number.isFinite(state.expiresAt) || state.expiresAt * 1000 <= Date.now()) {
      state.error = '验证流程已过期，请重新读取并办理'; return false
    }
    return true
  }
  const committed = result => {
    if (result?.runtimeMaterialized !== true || !['VERIFIED', 'REVOKED'].includes(result.state)) throw Error('未取得可信办理结果，请查询原操作')
    state.result = result; state.step = 'COMMITTED'; state.note = '号码变更已生效，原账号仍可使用。请重新登录。'
    proof = null; clearInputs()
  }
  const run = async task => {
    if (!current() || state.busy) return
    state.busy = true; state.error = ''
    try { await task() }
    catch (error) { if (current()) state.error = error?.message || '办理失败，请核对状态后重试' }
    finally { if (current()) { state.busy = false; state.currentPassword = ''; state.code = '' } }
  }
  return {
    checkSession: current,
    dispose() { alive = false; proof = null; clearInputs(); state.binding = null; state.result = null; state.busy = false },
    load() {
      if (state.step === 'UNCERTAIN') { state.error = '请先查询原操作结果，不能另起一次办理'; return }
      return run(async () => {
        proof = null; clearInputs(); state.purpose = ''; state.step = 'LOADING'
        const binding = await call()
        if (!current()) return
        if (!['UNBOUND', 'VERIFIED', 'REVOKED'].includes(binding?.state) || !Number.isSafeInteger(binding.bindingVersion)) throw Error('号码状态不可用，请稍后重试')
        state.binding = binding; state.step = 'READY'; state.expiresAt = 0
      })
    },
    registerCandidate() {
      if (state.step !== 'READY' || !state.binding?.allowedActions?.registerCandidate) return
      return run(async () => {
        if (!state.currentPassword || !state.phone) throw Error('请输入本人手机号和当前密码')
        state.step = 'READ_REQUIRED'
        state.note = '登记结果需要从服务端重新读取；未取得结果前请勿重复提交。'
        const result = await call('/candidate', { phone: state.phone, currentPassword: state.currentPassword,
          expectedCandidateVersion: state.binding.candidateVersion }, { method: 'PUT' })
        if (!current()) return
        if (!result?.accepted) throw Error('未取得登记回执，请重新读取核对')
        state.note = '已登记为待本人验证，尚不能使用手机号登录。'
        state.phone = ''
        const latest = await call()
        if (current()) { state.binding = latest; state.step = 'READY' }
      })
    },
    begin(purpose) {
      if (!current() || state.step !== 'READY') return
      const action = { BIND_PHONE: 'verify', CHANGE_PHONE: 'change', REVOKE_PHONE: 'revoke' }[purpose]
      if (!action || !state.binding?.allowedActions?.[action]) { state.error = state.binding?.verificationBlocked || '当前状态不能办理该操作'; return }
      return run(async () => {
        if (!state.currentPassword || (purpose !== 'REVOKE_PHONE' && !state.phone)) throw Error('请输入当前密码及本次本人手机号')
        const body = { purpose, currentPassword: state.currentPassword, expectedBindingVersion: state.binding.bindingVersion }
        if (purpose !== 'REVOKE_PHONE') body.newPhone = state.phone
        const nonce = await random()
        if (!current()) return
        const result = await call('/reauthenticate', { ...body, clientNonce: nonce })
        if (!current()) return
        if (!result?.operationId || !result.reauthTicket || !result.receiptToken) throw Error('未取得有效验证流程，请重新办理')
        proof = { ...result, nonce, purpose, version: body.expectedBindingVersion, key: nonce }
        state.purpose = purpose
        if (purpose === 'REVOKE_PHONE') state.phone = ''
        state.expiresAt = Number(result.expiresAt); state.step = purpose === 'REVOKE_PHONE' ? 'VERIFIED' : 'REAUTHENTICATED'
        state.note = purpose === 'REVOKE_PHONE' ? '请确认解绑影响并填写原因。' : '当前密码已验证，请提交验证码发送请求。'
      })
    },
    send() {
      if (state.step !== 'REAUTHENTICATED' || !validProof()) return
      return run(async () => {
        const result = await call('/challenges', { operationId: proof.operationId, reauthTicket: proof.reauthTicket, clientNonce: proof.nonce })
        if (!current()) return
        if (!result?.accepted || !result.challengeId) throw Error('短信请求未受理')
        proof.challengeId = result.challengeId; state.expiresAt = Number(result.expiresAt); state.step = 'CODE_SENT'
        state.note = '短信请求已受理，不代表已送达。请核对本次手机号并输入收到的验证码。'
      })
    },
    verify() {
      if (state.step !== 'CODE_SENT' || !validProof()) return
      return run(async () => {
        if (!/^[0-9]{6}$/.test(state.code)) throw Error('请输入 6 位短信验证码')
        const result = await call('/challenges/' + encodeURIComponent(proof.challengeId) + '/verify',
          { operationId: proof.operationId, clientNonce: proof.nonce, code: state.code })
        if (!current()) return
        if (!result?.verificationGrant) throw Error('未取得有效号码证明，请重新办理')
        proof.grant = result.verificationGrant; state.expiresAt = Number(result.expiresAt); state.step = 'VERIFIED'
        state.note = '新号码证明已取得，尚未更改登录凭据。请确认下方影响。'
      })
    },
    confirm() {
      if (state.step !== 'VERIFIED' || !validProof()) return
      return run(async () => {
        const revoke = proof.purpose === 'REVOKE_PHONE'
        if (revoke && state.reason.trim().length < 2) throw Error('请填写解绑原因')
        const body = { operationId: proof.operationId, clientNonce: proof.nonce, expectedBindingVersion: proof.version }
        if (revoke) Object.assign(body, { reauthTicket: proof.reauthTicket, reason: state.reason })
        else body.verificationGrant = proof.grant
        state.step = 'SUBMITTING'
        try {
          const result = await call(revoke ? '/revoke' : '/confirm', body, { headers: { 'Idempotency-Key': proof.key } })
          if (current()) committed(result)
        } catch (error) {
          if (current()) { state.step = 'UNCERTAIN'; state.note = '结果待确认，请查询原操作；不要重复绑定或换号。' }
          throw error
        }
      })
    },
    checkResult() {
      if (state.step !== 'UNCERTAIN' || !proof) return
      return run(async () => {
        const result = await call('/operation-status', { receiptToken: proof.receiptToken, clientNonce: proof.nonce }, { auth: false })
        if (!current()) return
        if (result?.runtimeMaterialized === true) committed(result)
        else state.note = '尚未查到已提交结果，请稍后再查询；不要重新提交。'
      })
    }
  }
}
