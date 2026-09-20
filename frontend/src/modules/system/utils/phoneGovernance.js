import { createRequestFence, paged } from './workspaceContract.js'

export const phoneGovernanceState = () => ({ rows: [], total: 0, page: 1, pageSize: 20,
  busy: false, error: '', note: '', edit: null, uncertain: false, preview: null, batchReason: '', exportJob: null })

export function createPhoneGovernance(state, api, filters) {
  const fence = createRequestFence()
  let alive = true
  return {
    dispose() { alive = false; fence.invalidate(); state.rows = []; state.edit = null; state.preview = null; state.exportJob = null; state.batchReason = ''; state.busy = false },
    async load() {
      if (!alive || state.busy) return
      const current = fence.start('operation')
      state.busy = true; state.rows = []; state.error = ''
      try {
        const result = paged(await api.query({ ...filters(), page: state.page, pageSize: state.pageSize }), 'list')
        if (!alive || !current()) return
        Object.assign(state, result, { edit: null, preview: null, uncertain: false })
      } catch (error) { if (alive && current()) state.error = error.message || '号码状态读取失败' }
      finally { if (alive && current()) state.busy = false }
    },
    edit(row) {
      if (!alive || state.busy || state.uncertain || !row.allowedActions?.candidate) return
      state.edit = { userId: row.userId, name: row.name, phone: '', reason: '', expectedCandidateVersion: row.candidateVersion }
      state.note = ''; state.error = ''
    },
    editRevoke(row) {
      if (!alive || state.busy || state.uncertain || !row.allowedActions?.revoke) return
      const bytes = new Uint8Array(24); globalThis.crypto.getRandomValues(bytes)
      state.edit = { kind: 'revoke', userId: row.userId, name: row.name, phoneMasked: row.phoneMasked,
        currentPassword: '', reason: '', expectedBindingVersion: row.bindingVersion,
        operationKey: Array.from(bytes, n => n.toString(16).padStart(2, '0')).join('') }
      state.note = ''; state.error = ''
    },
    async preview(action) {
      if (!alive || state.busy || state.uncertain) return
      if (state.batchReason.trim().length < 5) { state.error = '请填写至少 5 个字的办理用途'; return }
      const current = fence.start('operation'); state.busy = true; state.error = ''; state.preview = null
      try {
        const result = await api.preview({ action, filters: { ...filters() }, reason: state.batchReason })
        if (alive && current()) {
          if (!result?.previewId || result.count < 1) throw Error('未取得有效预览，请重新查询')
          state.preview = result
        }
      } catch (error) { if (alive && current()) state.error = error.message || '预览失败' }
      finally { if (alive && current()) state.busy = false }
    },
    async confirm() {
      if (!alive || state.busy || state.uncertain || !state.preview) return
      const current = fence.start('operation'); state.busy = true; state.error = ''
      try {
        const result = await api.confirm({ previewId: state.preview.previewId })
        if (!alive || !current()) return
        if (!result?.accepted) throw Error('未取得办理回执，请核对结果')
        state.note = result.channel === 'IN_APP' ? `已为 ${result.count} 个账号登记站内提醒，未发送短信。` : `已生成 ${result.count} 个账号的脱敏台账，请下载核对。`
        state.exportJob = result.job || null; state.preview = null
      } catch (error) { if (alive && current()) { state.error = error.message || '结果待核对'; state.uncertain = true } }
      finally { if (alive && current()) state.busy = false }
    },
    async checkBatchResult() {
      // Explicit recovery only: same frozen preview, never a freshly recomputed
      // payload. The server's durable receipt prevents duplicate delivery/jobs.
      if (!alive || state.busy || !state.preview) return
      state.uncertain = false
      await this.confirm()
    },
    async save() {
      if (!alive || state.busy || !state.edit || state.uncertain) return
      if (state.edit.reason.trim().length < 5) { state.error = '请填写至少 5 个字的登记或清除原因'; return }
      const { userId, phone, reason, expectedCandidateVersion } = state.edit
      const revoke = state.edit.kind === 'revoke'
      if (revoke && !state.edit.currentPassword) { state.error = '请输入经办人当前密码'; return }
      const current = fence.start('operation'); state.busy = true; state.error = ''
      try {
        const result = revoke
          ? await api.revoke(userId, { reason, currentPassword: state.edit.currentPassword,
            expectedBindingVersion: state.edit.expectedBindingVersion, operationKey: state.edit.operationKey })
          : await api.candidate(userId, { phone, reason, expectedCandidateVersion })
        if (!alive || !current()) return
        if (!result?.accepted || (revoke ? result.state !== 'REVOKED' : result.credentialChanged !== false)) throw Error('未取得可信办理回执，请重新读取核对')
        state.edit = null; state.note = revoke ? '已撤销手机号凭据，该账号旧会话失效；原账号及密码仍可登录。' : phone ? '已登记为待本人验证，尚不能用于登录；原账号和密码保持不变。' : '待核验号码已清除，登录凭据未改变。'
      } catch (error) {
        if (alive && current()) { state.error = error.message || '结果未取得，请重新读取核对'; state.uncertain = true }
      } finally { if (alive && current()) { state.busy = false; if (revoke && state.edit) state.edit.currentPassword = '' } }
      if (alive && current() && !state.uncertain) await this.load()
    }
  }
}
