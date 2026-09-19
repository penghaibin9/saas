import { phoneFlowNonce } from './phoneBindingFlow.mjs'

// In-memory lifecycle only. The original captcha service signs and validates.
export function createIdentityCaptcha(box, { identity, issue, error, random = phoneFlowNonce }) {
  let revision = 0, alive = true
  const flow = {
    invalidate() { revision++; Object.assign(box, { id: '', code: '', image: '', nonce: '', loading: false }) },
    dispose() { alive = false; flow.invalidate() },
    async ensureNonce() {
      if (box.nonce) return box.nonce
      const current = revision, value = await random()
      if (!alive || current !== revision) throw Error('登录方式或学校已变化，请重新提交')
      box.nonce = value; return value
    },
    async load() {
      const current = ++revision, target = identity()
      Object.assign(box, { id: '', image: '', code: '', loading: true })
      try {
        const nonce = await flow.ensureNonce()
        if (!alive || current !== revision) return
        const data = await issue({ ...target, clientNonce: nonce })
        if (alive && current === revision) Object.assign(box, { id: data.captchaId, image: data.imageDataUrl, code: '' })
      } catch (e) { if (alive && current === revision) error(e?.message || '验证码加载失败，请稍后重试') }
      finally { if (alive && current === revision) box.loading = false }
    }
  }
  return flow
}
