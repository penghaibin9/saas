import { phoneFlowNonce } from './phoneBindingFlow.mjs'

// Presentation of the existing reset protocol. Proofs remain memory-only; all
// subject, OTP, policy and password decisions belong to the original backend.
export const resetFlowState = (identity = {}) => ({ step: 1, error: '', note: '', loading: false, countdown: 0,
  form: { loginName: '', tenantCode: '', identifierType: 'ACCOUNT', ...identity, smsCode: '', newPassword: '', confirmPassword: '' },
  captcha: { id: '', code: '', image: '', loading: false } })

export function createResetFlow(state, { request, clientType, random = phoneFlowNonce }) {
  let generation = 0, alive = true, nonce = '', requestId = '', token = '', expiry = 0, retryAt = 0
  const clearProof = () => { nonce = ''; requestId = ''; token = ''; expiry = 0
    state.form.smsCode = ''; state.form.newPassword = ''; state.form.confirmPassword = ''
    Object.assign(state.captcha, { id: '', code: '', image: '', loading: false }) }
  const identity = () => ({ identifierType: state.form.identifierType, identifier: state.form.loginName.trim(),
    tenantCode: state.form.tenantCode.trim() || undefined })
  const call = (path, body) => request('/auth/' + path, { method: 'POST', auth: false, noAuthRetry: true, body })
  const run = async task => {
    if (!alive || state.loading) return
    const revision = generation
    const current = () => alive && revision === generation
    state.loading = true; state.error = ''
    try { await task(current) }
    catch (e) { if (current()) state.error = e?.message || '办理失败，请核对状态' }
    finally { if (current()) { state.loading = false; state.captcha.loading = false } }
  }
  const complete = data => {
    if (!data?.success || data.runtimeMaterialized !== true) throw Error('未取得生效回执，请查询原操作')
    state.step = 5; state.note = '密码已重置，旧会话已失效。请使用新密码重新登录。'; clearProof()
  }
  const valid = () => { if (expiry <= Date.now()) throw Error('本次验证已过期，请返回登录后重新办理') }
  const flow = {
    tick() { state.countdown = Math.max(0, Math.ceil((retryAt - Date.now()) / 1000)) },
    identityChanged() { generation++; clearProof(); state.step = 1; state.loading = false; state.error = ''; state.note = '' },
    dispose() { alive = false; generation++; clearProof(); state.form.loginName = ''; state.form.tenantCode = '' },
    loadCaptcha() {
      if (state.step !== 1) return
      return run(async current => {
        const target = identity()
        if (!target.identifier) throw Error('请先填写原账号或已验证手机号')
        state.captcha.loading = true; state.captcha.id = ''; state.captcha.code = ''; state.captcha.image = ''
        const nextNonce = await random()
        if (!current()) return
        nonce = nextNonce
        const data = await call('captcha', { ...target, scene: 'PASSWORD_RESET', clientNonce: nonce, clientType })
        if (current()) Object.assign(state.captcha, { id: data.captchaId, image: data.imageDataUrl, code: '' })
      })
    },
    requestCode() {
      if (state.step !== 1) return
      if (!state.captcha.id) return flow.loadCaptcha()
      return run(async current => {
        if (!/^[0-9]{6}$/.test(state.captcha.code)) throw Error('请输入图中 6 位验证码')
        const body = { ...identity(), captchaId: state.captcha.id, captchaCode: state.captcha.code, clientNonce: nonce, clientType }
        state.captcha.id = ''; state.captcha.code = ''
        const data = await call('password-reset/request', body)
        if (!current()) return
        requestId = data.requestId; expiry = Date.now() + Number(data.expiresIn || 300) * 1000
        retryAt = Date.now() + Number(data.retryAfter || 60) * 1000; flow.tick()
        state.step = 2; state.note = '请求已受理；仅符合条件的本人已验证号码会收到短信，不代表短信已经送达。'
      })
    },
    verifyCode() {
      if (state.step !== 2) return
      return run(async current => {
        valid()
        if (!/^[0-9]{6}$/.test(state.form.smsCode)) throw Error('请输入 6 位短信验证码')
        const code = state.form.smsCode; state.form.smsCode = ''
        const data = await call('password-reset/verify', { requestId, code, clientNonce: nonce, clientType })
        if (!current()) return
        if (!data.verified || !data.resetToken) throw Error('未取得有效重置证明')
        token = data.resetToken; expiry = Math.min(expiry, Date.now() + Number(data.expiresIn) * 1000); state.step = 3
      })
    },
    confirmReset() {
      if (state.step !== 3) return
      return run(async current => {
        valid()
        if (state.form.newPassword.length < 8) throw Error('新密码至少 8 位，实际要求以学校策略为准')
        if (state.form.newPassword !== state.form.confirmPassword) throw Error('两次输入的新密码不一致')
        const body = { resetToken: token, newPassword: state.form.newPassword, confirmPassword: state.form.confirmPassword }
        state.form.newPassword = ''; state.form.confirmPassword = ''; state.step = 4
        state.note = '结果待确认，请只查询原操作，不要重复重置密码。'
        const data = await call('password-reset/confirm', body)
        if (current()) complete(data)
      })
    },
    checkResult() {
      if (state.step !== 4) return
      return run(async current => {
        const data = await call('password-reset/operation-status', { resetToken: token, clientNonce: nonce })
        if (!current()) return
        if (data.runtimeMaterialized) complete(data)
        else state.note = '尚未查到已提交结果，请稍后再查询。不要重复提交。'
      })
    },
    restart() {
      if (state.loading || state.step !== 2 || state.countdown > 0) return
      flow.identityChanged(); return flow.loadCaptcha()
    }
  }
  return flow
}
