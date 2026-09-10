<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="专业分流志愿" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view v-if="notice" class="ms__notice" :class="'is-' + notice.tone"><text>{{ notice.title }}</text><text>{{ notice.description }}</text><button v-if="notice.tone === 'warning'" class="btn btn-ghost" :disabled="reading" @click="load(true)">核对已保存志愿</button></view>
        <template v-if="d.openBatches && d.openBatches.length">
          <view v-for="b in d.openBatches" :key="b.batchId" class="card stack-sm ms__batch">
            <text class="ms__title">{{ b.batchName }}</text>
            <text class="ms__hint">{{ b.grade ? b.grade + '级 · ' : '' }}至多填 {{ b.maxChoices }} 个志愿 · 按顺序点选专业(先点=第一志愿)</text>
            <button class="btn btn-ghost" :disabled="submitting" @click="activeBatchId = activeBatchId === String(b.batchId) ? '' : String(b.batchId)">{{ activeBatchId === String(b.batchId) ? '收起填报' : '查看与填写志愿' }}</button>
            <view v-if="activeBatchId === String(b.batchId)" class="ms__opts">
              <view v-for="o in b.options" :key="o.majorId"
                    :class="['ms__opt', { 'is-picked': pickRank(b, o.majorId) > 0 }]"
                    @click="toggle(b, o)">
                <text class="ms__opt-name">{{ o.majorName }}</text>
                <text class="ms__opt-cap">{{ o.remain != null ? '参考余量 ' + o.remain : '余量未公布' }}{{ o.capacity != null ? ' / 名额 ' + o.capacity : '' }} · 以学校结果为准</text>
                <text v-if="pickRank(b, o.majorId) > 0" class="ms__opt-rank">第{{ pickRank(b, o.majorId) }}志愿</text>
              </view>
            </view>
            <button v-if="activeBatchId === String(b.batchId) && !pending[b.batchId]" class="btn btn-primary" :disabled="!(picks[b.batchId] && picks[b.batchId].length) || submitting || reading" @click="submit(b)">
              {{ submitting ? '提交中…' : (myVolFor(b.batchId) ? '更新志愿' : '提交志愿') }}
            </button>
          </view>
        </template>
        <AcademicPageState v-else-if="!(d.myVolunteers && d.myVolunteers.length)" state="empty"
                           title="暂无开放中的分流批次" description="专业分流开放填报后在此选择志愿。" />

        <template v-if="d.myVolunteers && d.myVolunteers.length">
          <view class="section-head"><text class="section-head__title">我的志愿与结果</text></view>
          <view class="list-group">
            <view v-for="v in d.myVolunteers" :key="v.volunteerId" class="list-row ms__item">
              <view class="flex-1">
                <text class="t-md">志愿：{{ (v.choices || []).map(majorName).join(' / ') || '—' }}</text>
                <text v-if="v.resultMajorId" class="ms__result">录取：{{ majorName(v.resultMajorId) }}<text v-if="v.resultChoiceRank != null">（{{ v.resultChoiceRank === 0 ? '调剂' : '第' + v.resultChoiceRank + '志愿' }}）</text></text>
              </view>
              <MobileStatusTag :status="v.status" />
            </view>
          </view>
        </template>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { isUncertainWriteError, modalConfirm } from './write-state'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { canUpdatePendingCommand, createPendingCommand, readPending, savePending } from './pending-ledger'

const submitLock = createSubmitLock(1500)
const isForbidden = (error) => Number(error?.httpStatus) === 403 || /^403/.test(String(error?.code || ''))

export default {
  components: { AcademicPageNav, AcademicPageState },
  data() {
    return { d: null, state: 'loading', submitting: false, picks: {}, majorNames: {}, notice: null, requestEpoch: 0, writeToken: 0, hidden: false, identity: currentSessionGeneration(), activeBatchId: '', dirty: {}, pending: {}, reading: false }
  },
  onLoad() { const draft = readPending('draft:major-split'); if (draft) { this.picks = draft.picks || {}; this.dirty = draft.dirty || {}; this.activeBatchId = draft.activeBatchId || '' }; this.load() },
  onShow() {
    const changed = this.identity !== currentSessionGeneration()
    if (changed) {
      this.identity = currentSessionGeneration(); this.requestEpoch += 1; this.writeToken += 1
      this.d = null; this.picks = {}; this.majorNames = {}; this.dirty = {}; this.pending = {}; this.notice = null; this.activeBatchId = ''; this.submitting = false
    }
    if (this.hidden || changed) { this.hidden = false; this.load(true) }
  },
  onHide() { this.saveDraft(); this.hidden = true; this.requestEpoch += 1; this.writeToken += 1; this.submitting = false },
  onUnload() { this.saveDraft(); this.hidden = true; this.requestEpoch += 1; this.writeToken += 1 },
  methods: {
    pendingEntry(entry, batchId) {
      const choices = Array.isArray(entry) ? entry : entry?.choices
      return {
        choices: Array.isArray(choices) ? choices.map(String) : [],
        volunteerId: entry && !Array.isArray(entry) && entry.volunteerId ? String(entry.volunteerId) : '',
        batchId: entry && !Array.isArray(entry) && entry.batchId != null ? String(entry.batchId) : String(batchId),
        commandId: entry && !Array.isArray(entry) && entry.commandId ? String(entry.commandId) : '',
        _pendingOwner: entry && !Array.isArray(entry) ? entry._pendingOwner || '' : '',
        recoveryOnly: !!(entry && !Array.isArray(entry) && entry.recoveryOnly)
      }
    },
    choicesMatch(left, right) { return JSON.stringify((left || []).map(String)) === JSON.stringify((right || []).map(String)) },
    clearForbiddenMajorSplit() {
      this.d = null
      this.picks = {}
      this.majorNames = {}
      this.dirty = {}
      this.activeBatchId = ''
      savePending('draft:major-split', null)
      this.state = 'forbidden'
      this.notice = Object.keys(this.pending).length
        ? { tone: 'warning', title: '结果待核实', description: '暂时无法读取志愿记录；已保留待核实的本次操作，不会自动重复提交。' }
        : null
    },
    saveDraft() { if (this.identity === currentSessionGeneration()) savePending('draft:major-split', { picks: this.picks, dirty: this.dirty, activeBatchId: this.activeBatchId }) },
    load(preserve = false) {
      const savedPending = readPending('major-split')
      const pending = savedPending && typeof savedPending === 'object' && !Array.isArray(savedPending) ? savedPending : this.pending
      const normalizedPending = {}
      for (const [batchId, entry] of Object.entries(pending || {})) {
        const normalized = this.pendingEntry(entry, batchId)
        if (normalized.choices.length) normalizedPending[batchId] = normalized
      }
      this.pending = normalizedPending
      for (const [batchId, entry] of Object.entries(normalizedPending)) { this.picks[batchId] = [...entry.choices]; this.dirty[batchId] = true }
      const epoch = ++this.requestEpoch
      const identity = this.identity
      this.reading = true
      if (!preserve || !this.d) this.state = 'loading'
      return studentApi.getMyMajorSplit().then((d) => {
        if (epoch !== this.requestEpoch || this.hidden || identity !== currentSessionGeneration()) return null
        if (!d || !Array.isArray(d.myVolunteers) || !Array.isArray(d.openBatches)) throw new Error('Incomplete read')
        this.d = d
        if (this.notice?.title === '暂时无法更新') this.notice = null
        // 建 majorId→名 映射（含开放批次可选专业）
        const nm = {}
        ;(d.openBatches || []).forEach((b) => (b.options || []).forEach((o) => { nm[String(o.majorId)] = o.majorName }))
        this.majorNames = nm
        // 预填已提交志愿
        const picks = { ...this.picks }
        ;(d.openBatches || []).forEach((b) => {
          const mine = (d.myVolunteers || []).find((v) => v.batchId ? String(v.batchId) === String(b.batchId) : false)
          if (!this.dirty[b.batchId]) picks[b.batchId] = mine && mine.choices ? mine.choices.map(String) : []
        })
        this.picks = picks
        const originalPending = this.pending
        const pending = { ...this.pending }
        let confirmed = false
        for (const [batchId, entry] of Object.entries(pending)) {
          const mine = d.myVolunteers.find((item) => String(item.batchId) === batchId)
          if (entry.volunteerId && mine && String(mine.volunteerId) === entry.volunteerId && String(mine.batchId) === entry.batchId && this.choicesMatch(mine.choices, entry.choices)) {
            delete pending[batchId]; this.dirty = { ...this.dirty, [batchId]: false }
            confirmed = true
            this.notice = { tone: 'success', title: '志愿记录已确认', description: '已核对服务器保存的本人志愿与本次提交顺序一致。' }
          }
        }
        this.pending = pending
        if (!savePending('major-split', pending)) {
          this.pending = originalPending
          if (confirmed) this.notice = { tone: 'warning', title: '结果待核实', description: '学校记录已读取，但本机无法安全清除待核对引用；请稍后再次核对。' }
        }
        this.state = 'ready'
        return d
      }).catch((error) => {
        if (epoch !== this.requestEpoch || this.hidden || identity !== currentSessionGeneration()) return null
        if (isForbidden(error)) {
          this.clearForbiddenMajorSplit()
          return null
        }
        if (!this.d) this.state = 'error'
        this.notice = { tone: 'warning', title: Object.keys(this.pending).length ? '结果待核实' : '暂时无法更新', description: '尚未取得最新记录，已保留本批次填写内容。' }
        return null
      }).finally(() => { if (epoch === this.requestEpoch && identity === currentSessionGeneration()) this.reading = false })
    },
    majorName(id) { return this.majorNames[String(id)] || '专业名称待学校补充' },
    myVolFor(batchId) { return (this.d?.myVolunteers || []).find((v) => String(v.batchId) === String(batchId)) },
    pickRank(b, majorId) {
      const arr = this.picks[b.batchId] || []
      return arr.indexOf(String(majorId)) + 1
    },
    toggle(b, o) {
      if (this.submitting || this.pending[b.batchId]) return
      const key = b.batchId
      const arr = (this.picks[key] || []).slice()
      const mid = String(o.majorId)
      const i = arr.indexOf(mid)
      if (i >= 0) { arr.splice(i, 1) }
      else {
        if (arr.length >= b.maxChoices) { toast(`最多填 ${b.maxChoices} 个志愿`); return }
        arr.push(mid)
      }
      this.picks = { ...this.picks, [key]: arr }
      this.dirty = { ...this.dirty, [key]: true }
    },
    async submit(b) {
      const choices = [...(this.picks[b.batchId] || [])]
      if (!choices.length || this.submitting || this.reading || this.pending[b.batchId]) return
      const token = ++this.writeToken
      const identity = this.identity
      const epoch = this.requestEpoch
      this.submitting = true
      const names = choices.map(this.majorName).join('、')
      const answer = await modalConfirm({ title: this.myVolFor(b.batchId) ? '确认更新志愿' : '确认提交志愿', content: `志愿顺序：${names}\n实时余量仅供参考，最终结果以学校分流结果为准。`, confirmText: '确认提交' })
      const current = () => token === this.writeToken && !this.hidden && identity === currentSessionGeneration()
      if (!current()) return
      if (!answer.confirm || epoch !== this.requestEpoch || JSON.stringify(choices) !== JSON.stringify(this.picks[b.batchId])) { this.submitting = false; return }
      const entry = createPendingCommand('major-split', { action: 'MAJOR_SPLIT_SUBMIT', choices, volunteerId: '', batchId: String(b.batchId) })
      const pending = entry ? { ...this.pending, [b.batchId]: entry } : null
      if (!pending || !savePending('major-split', pending)) {
        this.submitting = false
        this.notice = { tone: 'warning', title: '未发送志愿', description: '本机无法安全保存本次志愿的核对引用，请恢复存储后重试。' }
        return
      }
      this.pending = pending
      this.notice = { tone: 'warning', title: '结果待核实', description: '正在提交并核对正式志愿顺序，请勿重复操作。' }
      return Promise.resolve().then(() => studentApi.submitMajorSplit(b.batchId, choices))
        .then((result) => {
          if (!current()) return null
          const original = this.pending[b.batchId]
          const volunteerId = result?.volunteerId ? String(result.volunteerId) : ''
          if (!volunteerId || String(result?.batchId) !== String(b.batchId)) {
            this.notice = { tone: 'warning', title: '结果待核实', description: '未收到本次提交的确认回执，请先核对已保存志愿，不要重复提交。' }
            return this.load(true)
          }
          if (!original || !canUpdatePendingCommand('major-split', original)) return null
          const acknowledged = { ...original, choices, volunteerId, batchId: String(b.batchId) }
          const next = { ...this.pending, [b.batchId]: acknowledged }
          if (!savePending('major-split', next)) {
            this.notice = { tone: 'warning', title: '结果待核实', description: '已收到学校回执，但本机无法安全保存回执编号；请保持页面并重新核对，切勿重复提交。' }
            return null
          }
          this.pending = next
          return this.load(true)
        })
        .catch((e) => {
          if (!current()) return
          if (isUncertainWriteError(e)) {
            this.notice = { tone: 'warning', title: '结果待核实', description: '网络返回不完整，请先核对已保存志愿，不要重复提交。' }
            return this.load(true)
          }
          const pending = { ...this.pending }; delete pending[b.batchId]
          if (!savePending('major-split', pending)) {
            this.notice = { tone: 'warning', title: '结果待核实', description: '本机无法安全清除待核对引用；请恢复存储后核对，切勿重复提交。' }
            return
          }
          this.pending = pending
          this.notice = null
          toast(e && e.biz ? normalizeError(e).text : '志愿未提交')
          return this.load(true)
        })
        .finally(() => { if (current()) this.submitting = false })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.ms__batch { border: 1px solid var(--border-base); }
.ms__title { font-size: var(--font-size-base); font-weight: 600; color: var(--text-primary); }
.ms__hint { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin: 2px 0 var(--space-2); }
.ms__opts { display: flex; flex-direction: column; gap: var(--space-2); }
.ms__opt { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-md); }
.ms__opt.is-picked { border-color: var(--brand-600, #2563eb); background: var(--brand-50, #eff6ff); }
.ms__opt-name { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); }
.ms__opt-cap { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ms__opt-rank { font-size: var(--font-size-xs); color: var(--brand-600, #2563eb); font-weight: 600; }
.ms__item { align-items: flex-start; }
.ms__result { display: block; font-size: var(--font-size-xs); color: var(--success-600); margin-top: 4px; }
.ms__notice { display: flex; flex-direction: column; gap: 3px; padding: 10px 12px; border-radius: var(--radius-md); background: var(--success-50); color: var(--success-700); font-size: 12px; }
.ms__notice.is-warning { background: var(--warning-50); color: var(--warning-700); }
.ms__notice text:first-child { font-weight: 700; font-size: 14px; }
</style>
