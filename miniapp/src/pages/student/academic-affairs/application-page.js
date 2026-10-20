import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { academicReadPage } from './read-page'
import { modalConfirm, isUncertainWriteError } from './write-state'
import { canUpdatePendingCommand, createPendingCommand, readPending, redactPendingCommand, savePending } from './pending-ledger'

function matchesRecovery(row, pending, fallbackKey) {
  if (!pending.returnedId) return false
  const recordKey = pending.recordKey || fallbackKey
  const objectMatches = pending.objectId && String(row[recordKey] || '') === String(pending.objectId)
  const receiptMatches = String(row[pending.receiptKey || fallbackKey] || '') === String(pending.returnedId)
  const rule = pending.recovery
  if (!rule) return receiptMatches
  const value = row[rule.field]
  const valid = rule.equals !== undefined
    ? (typeof rule.equals === 'boolean' ? value === rule.equals : String(value) === String(rule.equals))
    : value != null && value !== '' && Array.isArray(rule.excludes) && !rule.excludes.includes(String(value))
  // An existing-object command must match both its original server receipt and frozen object.
  // A read-only current state, or a receipt attached to another object, never settles it.
  return valid && receiptMatches && (pending.objectId ? objectMatches : true)
}

export const academicApplicationPage = {
  mixins: [academicReadPage],
  data() { return { applicationScope: '', submitting: false, pendingApplication: null, applicationNotice: '', academicDraftRestored: false } },
  onHide() { this.saveAcademicDraft() },
  onUnload() { this.saveAcademicDraft() },
  methods: {
    saveAcademicDraft() {
      if (this.readIdentity !== currentSessionGeneration() || !this.academicDraftFields?.length) return
      if (this.prepareAcademicDraft) this.prepareAcademicDraft()
      const draft = {}
      for (const key of this.academicDraftFields) draft[key] = this[key]
      savePending('draft:' + this.applicationScope, draft)
    },
    retainPendingReference() {
      const reference = redactPendingCommand(this.applicationScope, this.pendingApplication)
      if (!reference) return false
      this.pendingApplication = reference
      return savePending(this.applicationScope, reference)
    },
    protectPendingReference() {
      const hadPending = !!this.pendingApplication
      if (hadPending && !this.retainPendingReference() && !this.pendingApplication?.recoveryOnly) this.pendingApplication = { recoveryOnly: true }
      return hadPending
    },
    restoreApplication() {
      if (!this.academicDraftRestored && this.academicDraftFields?.length) {
        const draft = readPending('draft:' + this.applicationScope)
        if (draft) for (const key of this.academicDraftFields) if (key in draft) this[key] = draft[key]
        if (draft && this.materials) this.materials = this.materials.map(file => ({ ...file, readyForBusiness: false }))
        this.academicDraftRestored = true
      }
      this.pendingApplication = readPending(this.applicationScope)
      if (this.pendingApplication) {
        this.applicationNotice = `结果待核实：${this.pendingApplication.title || '本次办理'}。请核对本人办理记录。`
        // A cold-start reference intentionally has no private request body and must never rebuild a form.
        if (!this.pendingApplication.recoveryOnly && this.restorePendingDraft) this.restorePendingDraft(this.pendingApplication)
      }
    },
    async sendApplication({ title, content = '请核对当前申请内容，提交后以学校受理记录为准。', body, send, rows, idKey, receiptKey = idKey, recordKey = idKey, recovery = null, kind = '', existingId = '' }) {
      if (this.submitting || this.pendingApplication || this.state !== 'ready') return
      const identity = currentSessionGeneration()
      const epoch = this.readEpoch
      const current = () => identity === currentSessionGeneration() && epoch === this.readEpoch && !this.readHidden
      const frozen = JSON.parse(JSON.stringify(body))
      this.submitting = true
      try {
        const answer = await modalConfirm({ title, content })
        if (!answer.confirm || !current()) return
        const pending = createPendingCommand(this.applicationScope, {
          action: this.applicationScope, title, body: frozen, kind, knownIds: rows.map(row => String(row[idKey])),
          returnedId: '', existingId: String(existingId), idKey, recordKey, receiptKey, recovery
        })
        if (!pending || !savePending(this.applicationScope, pending)) {
          this.applicationNotice = '本机无法安全保存本次办理的核对引用，未发送申请。请恢复存储后重试。'
          return
        }
        this.pendingApplication = pending
        this.applicationNotice = '结果待核实，请核对本人办理记录。'
        try {
          const result = await send(frozen)
          const receipt = result && result[receiptKey]
          if (receipt && canUpdatePendingCommand(this.applicationScope, pending)) {
            pending.returnedId = String(receipt)
            if (!savePending(this.applicationScope, pending)) {
              this.applicationNotice = '已收到学校回执，但本机无法安全保存回执编号；请保持页面并重新核对，切勿重复提交。'
              return
            }
            if (current()) this.pendingApplication = pending
          }
          if (!current()) return
        } catch (error) {
          if (!current()) return
          if (!isUncertainWriteError(error)) {
            if (canUpdatePendingCommand(this.applicationScope, pending) && savePending(this.applicationScope, null)) {
              this.pendingApplication = null
              this.applicationNotice = '本次申请未受理，请核对办理条件；已填写内容已保留。'
            } else {
              this.applicationNotice = '本次请求未获确认，且本机无法安全清除待核对引用；请稍后核对，切勿重复提交。'
            }
          }
        }
        if (current()) await this.load()
      } finally {
        if (identity === currentSessionGeneration()) this.submitting = false
      }
    },
    acceptApplication(rows, idKey, matches) {
      const pending = this.pendingApplication
      if (!pending || !canUpdatePendingCommand(this.applicationScope, pending)) return
      const record = rows.find(row => {
        if (pending.recoveryOnly) return matchesRecovery(row, pending, idKey)
        const id = String(row[idKey] || '')
        const recordId = String(row[pending.recordKey || idKey] || '')
        // A post that changes an existing object has to carry its original server receipt
        // before the matching object state may settle this command. New objects must likewise
        // be tied to the returned object ID; a changed list alone is never a confirmation.
        const originalObject = pending.existingId
          ? !!pending.returnedId && recordId === pending.existingId && String(row[pending.receiptKey || idKey] || '') === pending.returnedId
          : !!pending.returnedId && id === pending.returnedId
        return id && originalObject && matches(row, pending.body, pending.kind)
      })
      if (!record || !savePending(this.applicationScope, null)) {
        if (record) this.applicationNotice = '学校记录已读取，但本机无法安全清除待核对引用；请稍后再次核对。'
        return
      }
      this.pendingApplication = null
      this.applicationNotice = '已核对学校受理记录。请关注后续审核结果。'
      this.finishApplication(pending.kind)
      savePending('draft:' + this.applicationScope, null)
    },
    clearApplicationContext() { this.pendingApplication = null; this.applicationNotice = ''; this.submitting = false; this.academicDraftRestored = false }
  }
}
