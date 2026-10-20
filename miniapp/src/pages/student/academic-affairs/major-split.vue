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
            <button class="btn btn-ghost" :disabled="submitting || reading" @click="toggleBatch(b)">{{ activeBatchId === String(b.batchId) ? '收起填报' : '查看与填写志愿' }}</button>
            <view v-if="activeBatchId === String(b.batchId) && optionState(b).error" class="ms__option-state">
              <text>{{ optionState(b).error }}</text><button class="btn btn-ghost" :disabled="optionState(b).loading" @click="loadOptions(b, optionState(b).page || 1)">重新读取</button>
            </view>
            <view v-else-if="activeBatchId === String(b.batchId) && optionState(b).loading && !batchOptions(b).length" class="ms__option-state"><text>正在读取可选专业…</text></view>
            <view v-else-if="activeBatchId === String(b.batchId) && batchOptions(b).length" class="ms__opts">
              <view v-for="o in batchOptions(b)" :key="o.majorId"
                    :class="['ms__opt', { 'is-picked': pickRank(b, o.majorId) > 0 }]"
                    @click="toggle(b, o)">
                <text class="ms__opt-name">{{ o.majorName }}</text>
                <text class="ms__opt-cap">{{ o.remain != null ? '参考余量 ' + o.remain : '余量未公布' }}{{ o.capacity != null ? ' / 名额 ' + o.capacity : '' }} · 以学校结果为准</text>
                <text v-if="pickRank(b, o.majorId) > 0" class="ms__opt-rank">第{{ pickRank(b, o.majorId) }}志愿</text>
              </view>
              <view v-if="optionState(b).total > 0 || optionState(b).page > 1" class="ms__pager">
                <button class="btn ms__pager-button" :disabled="optionState(b).page <= 1 || optionState(b).loading" @click="loadOptions(b, optionState(b).page - 1)">上一页</button>
                <text>第 {{ optionState(b).page }} / {{ optionPageCount(b) }} 页，共 {{ optionState(b).total }} 个专业</text>
                <button class="btn ms__pager-button" :disabled="!optionState(b).hasMore || optionState(b).loading" @click="loadOptions(b, optionState(b).page + 1)">下一页</button>
              </view>
            </view>
            <view v-else-if="activeBatchId === String(b.batchId)" class="ms__option-state"><text>当前批次暂无可填报的专业，请联系教务老师核对。</text></view>
            <button v-if="activeBatchId === String(b.batchId) && !pending[b.batchId]" class="btn btn-primary" :disabled="!(picks[b.batchId] && picks[b.batchId].length) || submitting || reading || !optionState(b).loaded" @click="submit(b)">
              {{ submitting ? '提交中…' : (myVolFor(b.batchId) ? '更新志愿' : '提交志愿') }}
            </button>
          </view>
        </template>
        <view v-if="d.openPagination.total > 0 || openPage > 1" class="ms__pager">
          <button class="btn ms__pager-button" :disabled="openPage <= 1 || reading" @click="previousOpenPage">上一页</button>
          <text>第 {{ openPage }} / {{ openPageCount }} 页，共 {{ d.openPagination.total }} 个批次</text>
          <button class="btn ms__pager-button" :disabled="!d.openPagination.hasMore || reading" @click="nextOpenPage">下一页</button>
        </view>
        <AcademicPageState v-else-if="!(d.myVolunteers && d.myVolunteers.length)" state="empty"
                           title="暂无开放中的分流批次" description="专业分流开放填报后在此选择志愿。" />

        <template v-if="(d.myVolunteers && d.myVolunteers.length) || d.volunteerPagination.total > 0">
          <view class="section-head"><text class="section-head__title">我的志愿与结果</text></view>
          <view class="list-group">
            <view v-for="v in d.myVolunteers" :key="v.volunteerId" class="list-row ms__item">
              <view class="flex-1">
                <text class="t-md">{{ v.batchName || '分流批次名称待学校核对' }}</text>
                <text class="ms__choice">志愿：{{ choiceNames(v).join(' / ') || '—' }}</text>
                <text v-if="v.resultMajorId" class="ms__result">录取：{{ resultName(v) }}<text v-if="v.resultChoiceRank != null">（{{ v.resultChoiceRank === 0 ? '调剂' : '第' + v.resultChoiceRank + '志愿' }}）</text></text>
              </view>
              <MobileStatusTag :status="v.status" :label="splitStatusLabel(v.status, v)" />
            </view>
          </view>
          <view class="ms__pager">
            <button class="btn ms__pager-button" :disabled="volunteerPage <= 1 || reading" @click="previousVolunteerPage">上一页</button>
            <text>第 {{ volunteerPage }} / {{ volunteerPageCount }} 页，共 {{ d.volunteerPagination.total }} 条</text>
            <button class="btn ms__pager-button" :disabled="!d.volunteerPagination.hasMore || reading" @click="nextVolunteerPage">下一页</button>
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
const PAGE_SIZE = 20

function normalizePagination(value, requestedPage, label) {
  const page = value?.page
  const pageSize = value?.pageSize
  const total = value?.total
  const hasMore = value?.hasMore
  if (!Number.isSafeInteger(page) || page !== requestedPage || page < 1
    || pageSize !== PAGE_SIZE || !Number.isSafeInteger(total) || total < 0
    || typeof hasMore !== 'boolean' || hasMore !== page * pageSize < total) {
    throw new Error(label + '分页信息无法核对')
  }
  return { page, pageSize, total, hasMore }
}

function normalizeMajorSplitPage(data, requestedOpenPage, requestedVolunteerPage) {
  if (!data || !Array.isArray(data.openBatches) || !Array.isArray(data.myVolunteers)
    || data.openBatches.length > PAGE_SIZE || data.myVolunteers.length > PAGE_SIZE) {
    throw new Error('专业分流记录无法核对')
  }
  const openPagination = normalizePagination(data.openPagination, requestedOpenPage, '分流批次')
  const volunteerPagination = normalizePagination(data.volunteerPagination, requestedVolunteerPage, '志愿记录')
  if ((data.openBatches.length > 0 && openPagination.total < (openPagination.page - 1) * PAGE_SIZE + data.openBatches.length)
    || (data.myVolunteers.length > 0 && volunteerPagination.total < (volunteerPagination.page - 1) * PAGE_SIZE + data.myVolunteers.length)) {
    throw new Error('专业分流分页记录不完整')
  }
  return { ...data, openPagination, volunteerPagination }
}

function normalizeOptionPage(data, requestedPage) {
  if (!data || !Array.isArray(data.items) || data.items.length > PAGE_SIZE) throw new Error('可选专业记录无法核对')
  const pagination = normalizePagination(data, requestedPage, '可选专业')
  if (data.items.length > 0 && pagination.total < (pagination.page - 1) * PAGE_SIZE + data.items.length) {
    throw new Error('可选专业分页记录不完整')
  }
  return { ...pagination, items: data.items }
}

export default {
  components: { AcademicPageNav, AcademicPageState },
  data() {
    return { d: null, state: 'loading', submitting: false, picks: {}, majorNames: {}, notice: null, requestEpoch: 0, writeToken: 0, hidden: false, identity: currentSessionGeneration(), activeBatchId: '', dirty: {}, pending: {}, reading: false, openPage: 1, volunteerPage: 1, optionStates: {}, optionRequestSerial: 0, optionRequestTokens: {} }
  },
  computed: {
    openPageCount() { return this.d?.openPagination?.total ? Math.ceil(this.d.openPagination.total / PAGE_SIZE) : 1 },
    volunteerPageCount() { return this.d?.volunteerPagination?.total ? Math.ceil(this.d.volunteerPagination.total / PAGE_SIZE) : 1 }
  },
  onLoad() { const draft = readPending('draft:major-split'); if (draft) { this.picks = draft.picks || {}; this.dirty = draft.dirty || {}; this.activeBatchId = draft.activeBatchId || '' }; this.load() },
  onShow() {
    const changed = this.identity !== currentSessionGeneration()
    if (changed) {
      this.identity = currentSessionGeneration(); this.requestEpoch += 1; this.writeToken += 1
      this.d = null; this.picks = {}; this.majorNames = {}; this.dirty = {}; this.pending = {}; this.notice = null; this.activeBatchId = ''; this.submitting = false; this.openPage = 1; this.volunteerPage = 1; this.optionStates = {}; this.optionRequestTokens = {}
    }
    if (this.hidden || changed) { this.hidden = false; this.load(true) }
  },
  onHide() { this.saveDraft(); this.hidden = true; this.requestEpoch += 1; this.writeToken += 1; this.submitting = false; this.invalidateOptionReads() },
  onUnload() { this.saveDraft(); this.hidden = true; this.requestEpoch += 1; this.writeToken += 1; this.invalidateOptionReads() },
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
      this.optionStates = {}
      this.optionRequestTokens = {}
      this.openPage = 1
      this.volunteerPage = 1
      savePending('draft:major-split', null)
      this.state = 'forbidden'
      this.notice = Object.keys(this.pending).length
        ? { tone: 'warning', title: '结果待核实', description: '暂时无法读取志愿记录；已保留待核实的本次操作，不会自动重复提交。' }
        : null
    },
    saveDraft() { if (this.identity === currentSessionGeneration()) savePending('draft:major-split', { picks: this.picks, dirty: this.dirty, activeBatchId: this.activeBatchId }) },
    invalidateOptionReads() {
      this.optionRequestTokens = {}
      const next = {}
      for (const [batchId, state] of Object.entries(this.optionStates || {})) {
        next[batchId] = state?.loading ? { ...state, loading: false } : state
      }
      this.optionStates = next
    },
    previousOpenPage() { return this.openPage > 1 ? this.load(true, this.openPage - 1, this.volunteerPage) : Promise.resolve(null) },
    nextOpenPage() { return this.d?.openPagination?.hasMore ? this.load(true, this.openPage + 1, this.volunteerPage) : Promise.resolve(null) },
    previousVolunteerPage() { return this.volunteerPage > 1 ? this.load(true, this.openPage, this.volunteerPage - 1) : Promise.resolve(null) },
    nextVolunteerPage() { return this.d?.volunteerPagination?.hasMore ? this.load(true, this.openPage, this.volunteerPage + 1) : Promise.resolve(null) },
    load(preserve = false, requestedOpenPage = this.openPage, requestedVolunteerPage = this.volunteerPage) {
      const identityChanged = this.identity !== currentSessionGeneration()
      const openPage = identityChanged ? 1 : Number(requestedOpenPage)
      const volunteerPage = identityChanged ? 1 : Number(requestedVolunteerPage)
      if (!Number.isSafeInteger(openPage) || !Number.isSafeInteger(volunteerPage) || openPage < 1 || volunteerPage < 1) return Promise.resolve(null)
      const savedPending = readPending('major-split')
      const pending = savedPending && typeof savedPending === 'object' && !Array.isArray(savedPending) ? savedPending : this.pending
      const normalizedPending = {}
      for (const [batchId, entry] of Object.entries(pending || {})) {
        const normalized = this.pendingEntry(entry, batchId)
        if (normalized.choices.length) normalizedPending[batchId] = normalized
      }
      this.pending = normalizedPending
      for (const [batchId, entry] of Object.entries(normalizedPending)) { this.picks[batchId] = [...entry.choices]; this.dirty[batchId] = true }
      this.invalidateOptionReads()
      const epoch = ++this.requestEpoch
      const identity = this.identity
      this.reading = true
      if (!preserve || !this.d) this.state = 'loading'
      return studentApi.getMyMajorSplit({
        openPage, openPageSize: PAGE_SIZE,
        volunteerPage, volunteerPageSize: PAGE_SIZE
      }).then((d) => {
        if (epoch !== this.requestEpoch || this.hidden || identity !== currentSessionGeneration()) return null
        const data = normalizeMajorSplitPage(d, openPage, volunteerPage)
        this.d = data
        this.openPage = data.openPagination.page
        this.volunteerPage = data.volunteerPagination.page
        if (!data.openBatches.some(batch => String(batch.batchId) === this.activeBatchId)) this.activeBatchId = ''
        if (this.notice?.title === '暂时无法更新') this.notice = null
        // 建 majorId→中文名映射：历史志愿名由服务端批量补齐，不依赖当前开放批次。
        const nm = {}
        ;(data.openBatches || []).forEach((b) => (b.options || []).forEach((o) => { nm[String(o.majorId)] = o.majorName }))
        ;Object.values(this.optionStates).forEach((optionState) => (optionState.items || []).forEach((option) => {
          if (option?.majorId && option.majorName) nm[String(option.majorId)] = option.majorName
        }))
        ;(data.myVolunteers || []).forEach((volunteer) => {
          ;(volunteer.choices || []).forEach((majorId, index) => {
            const name = volunteer.choiceNames?.[index]
            if (name) nm[String(majorId)] = name
          })
          if (volunteer.resultMajorId && volunteer.resultMajorName) nm[String(volunteer.resultMajorId)] = volunteer.resultMajorName
        })
        this.majorNames = nm
        // 预填已提交志愿
        const picks = { ...this.picks }
        ;(data.openBatches || []).forEach((b) => {
          const mine = b.myVolunteer || (data.myVolunteers || []).find((v) => v.batchId ? String(v.batchId) === String(b.batchId) : false)
          if (!this.dirty[b.batchId]) picks[b.batchId] = mine && mine.choices ? mine.choices.map(String) : []
        })
        this.picks = picks
        const originalPending = this.pending
        const pending = { ...this.pending }
        let confirmed = false
        for (const [batchId, entry] of Object.entries(pending)) {
          const mine = data.myVolunteers.find((item) => String(item.batchId) === batchId)
            || data.openBatches.find((item) => String(item.batchId) === batchId)?.myVolunteer
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
        return data
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
    optionState(batch) {
      const key = String(batch?.batchId || '')
      const saved = this.optionStates[key]
      if (saved) return saved
      if (Array.isArray(batch?.options)) return { items: batch.options, page: 1, pageSize: PAGE_SIZE, total: batch.options.length, hasMore: false, loading: false, error: '', loaded: true }
      return { items: [], page: 1, pageSize: PAGE_SIZE, total: 0, hasMore: false, loading: false, error: '', loaded: false }
    },
    batchOptions(batch) { return this.optionState(batch).items || [] },
    optionPageCount(batch) { const state = this.optionState(batch); return state.total ? Math.ceil(state.total / PAGE_SIZE) : 1 },
    toggleBatch(batch) {
      const batchId = String(batch.batchId)
      if (this.submitting || this.reading) return
      if (this.activeBatchId === batchId) { this.activeBatchId = ''; return }
      this.activeBatchId = batchId
      if (!this.optionState(batch).loaded) return this.loadOptions(batch, 1)
    },
    loadOptions(batch, requestedPage = 1) {
      const batchId = String(batch?.batchId || '')
      const page = Number(requestedPage)
      if (!batchId || !Number.isSafeInteger(page) || page < 1 || this.optionState(batch).loading) return Promise.resolve(null)
      if (typeof studentApi.getMajorSplitOptions !== 'function') {
        this.optionStates = { ...this.optionStates, [batchId]: { ...this.optionState(batch), error: '可选专业读取能力暂不可用，请联系学校更新后重试。' } }
        return Promise.resolve(null)
      }
      const epoch = this.requestEpoch
      const identity = this.identity
      const requestToken = ++this.optionRequestSerial
      this.optionRequestTokens = { ...this.optionRequestTokens, [batchId]: requestToken }
      this.optionStates = { ...this.optionStates, [batchId]: { ...this.optionState(batch), loading: true, error: '' } }
      return studentApi.getMajorSplitOptions(batchId, { page, pageSize: PAGE_SIZE }).then((result) => {
        if (this.optionRequestTokens[batchId] !== requestToken || epoch !== this.requestEpoch || this.hidden || identity !== currentSessionGeneration()) return null
        const data = normalizeOptionPage(result, page)
        const next = { ...data, loading: false, error: '', loaded: true }
        this.optionStates = { ...this.optionStates, [batchId]: next }
        const names = { ...this.majorNames }
        data.items.forEach(item => { if (item?.majorId && item.majorName) names[String(item.majorId)] = item.majorName })
        this.majorNames = names
        return data
      }).catch((error) => {
        if (this.optionRequestTokens[batchId] !== requestToken || epoch !== this.requestEpoch || this.hidden || identity !== currentSessionGeneration()) return null
        if (isForbidden(error)) { this.clearForbiddenMajorSplit(); return null }
        const previous = this.optionState(batch)
        this.optionStates = { ...this.optionStates, [batchId]: { ...previous, loading: false, error: Number(error?.httpStatus || error?.statusCode) === 409 ? '该批次已截止，请刷新后核对结果。' : '可选专业读取失败，请重新核对后重试。' } }
        return null
      }).finally(() => {
        if (this.optionRequestTokens[batchId] !== requestToken) return
        const { [batchId]: _completed, ...remainingTokens } = this.optionRequestTokens
        this.optionRequestTokens = remainingTokens
        const current = this.optionStates[batchId]
        if (current?.loading) {
          this.optionStates = { ...this.optionStates, [batchId]: { ...current, loading: false } }
        }
      })
    },
    majorName(id) { return this.majorNames[String(id)] || '专业名称待学校核对' },
    choiceNames(volunteer) {
      if (Array.isArray(volunteer?.choiceNames) && volunteer.choiceNames.length === (volunteer.choices || []).length) return volunteer.choiceNames
      return (volunteer?.choices || []).map(this.majorName)
    },
    resultName(volunteer) { return volunteer?.resultMajorName || this.majorName(volunteer?.resultMajorId) },
    splitStatusLabel(status, row = null) { return row?.statusLabel || { PENDING: '已提交，待分配', ALLOCATED: '已录取', UNALLOCATED: '待调剂', CONFIRMED: '已确认' }[String(status || '').toUpperCase()] || '' },
    myVolFor(batchId) {
      const batch = (this.d?.openBatches || []).find(item => String(item.batchId) === String(batchId))
      return batch?.myVolunteer || (this.d?.myVolunteers || []).find((v) => String(v.batchId) === String(batchId))
    },
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
.ms__choice { display:block; font-size:var(--font-size-xs); color:var(--text-secondary); margin-top:2px; }
.ms__result { display: block; font-size: var(--font-size-xs); color: var(--success-600); margin-top: 4px; }
.ms__option-state { display:flex; align-items:center; justify-content:space-between; gap:var(--space-2); padding:10px 12px; color:var(--text-secondary); background:var(--fill-50); border-radius:var(--radius-md); font-size:var(--font-size-sm); }
.ms__pager { display:flex; align-items:center; justify-content:space-between; gap:var(--space-2); margin:var(--space-3) 0; color:var(--text-secondary); font-size:var(--font-size-sm); }
.ms__pager-button { flex:1; margin:0; }
.ms__notice { display: flex; flex-direction: column; gap: 3px; padding: 10px 12px; border-radius: var(--radius-md); background: var(--success-50); color: var(--success-700); font-size: 12px; }
.ms__notice.is-warning { background: var(--warning-50); color: var(--warning-700); }
.ms__notice text:first-child { font-weight: 700; font-size: 14px; }
</style>
