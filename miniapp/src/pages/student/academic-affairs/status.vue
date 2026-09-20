<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="学籍与异动" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view v-if="applicationNotice" class="card"><text>{{ applicationNotice }}</text><button v-if="pendingApplication" class="btn" @click="load">核对本人记录</button></view>
        <view class="stx__cur" :class="data.enrolled ? 'is-ok' : 'is-warn'">
          <text class="stx__cur-t">当前学籍</text>
          <text class="stx__cur-v">{{ statusText(data.studentStatus) }}</text>
        </view>

        <view class="stx__sec-t">异动记录</view>
        <view class="stx__empty" v-if="!(data.changes || []).length"><text>暂无异动记录</text></view>
        <view v-for="c in data.changes" :key="c.changeId" class="stx__ch">
          <view class="stx__ch-head">
            <text class="stx__ch-t">{{ ctText(c.changeType) }}</text>
            <view class="stx__ch-state">
              <text class="stx__ch-s" :class="c.status === 'EFFECTIVE' ? 'is-ok' : ''">{{ statusLabel(c.status) }}</text>
              <text v-if="c.status === 'APPROVED_PENDING_EFFECTIVE' && c.effectiveDate" class="stx__ch-plan">计划 {{ dateTime(c.effectiveDate) }} 生效</text>
            </view>
          </view>
          <view v-if="c.status === 'RETURNED'" class="stx__resubmit">
            <text v-if="c.reviewNote" class="stx__review-note">退回意见：{{ c.reviewNote }}</text>
            <text class="stx__resubmit-hint">申请已被退回。修改事由后重交，系统会继续使用原申请编号，不会新建第二张异动单。</text>
            <textarea :disabled="submitting || !!pendingApplication"
              class="stx__reason stx__reason--resubmit"
              v-model="resubmitReasons[c.changeId]"
              placeholder="修改后的申请事由（不少于5字）"
              maxlength="200"
            />
            <button
              class="stx__btn stx__btn--resubmit"
              :disabled="submitting || !!pendingApplication || !canResubmit(c)"
              @click="resubmit(c)"
            >修改并重交原申请</button>
          </view>
        </view>

        <view v-if="data.total > 0 || page > 1" class="stx__pager">
          <button class="btn stx__pager-button" :disabled="page <= 1 || isPaging" @click="previousPage">上一页</button>
          <text>第 {{ page }} / {{ pageCount }} 页，共 {{ data.total }} 条</text>
          <button class="btn stx__pager-button" :disabled="!data.hasMore || isPaging" @click="nextPage">下一页</button>
        </view>
        <button class="stx__btn" @click="showForm = !showForm">{{ showForm ? '收起申请表' : '发起学籍异动' }}</button>
        <text class="stx__resubmit-hint">申请须经学校审批并到生效时间后，才会改变当前学籍。</text>
        <view v-if="showForm" class="stx__form">
          <view class="stx__chips">
            <view v-for="t in TYPES" :key="t.v" class="stx__chip" :class="{ 'is-on': form.changeType === t.v }"
              @click="onType(t.v)">{{ t.l }}</view>
          </view>
          <button v-if="optionsFailed" class="btn" @click="loadTransferOptions">目标专业或班级读取失败，点击重试</button>
          <text v-if="optionsLoading" class="stx__pick-l">正在读取本页可选目标…</text>

          <view v-if="form.changeType === 'TRANSFER_MAJOR'" class="stx__pick">
            <text class="stx__pick-l">目标专业（必选）</text>
            <view class="stx__option-query">
              <input v-model="majorKeyword" maxlength="60" confirm-type="search" placeholder="按学院或专业名称搜索" @confirm="searchMajorOptions" />
              <button class="btn stx__option-search" :disabled="optionsLoading" @click="searchMajorOptions">搜索</button>
            </view>
            <picker mode="selector" :range="majorLabels" :value="majorIndex" @change="onMajorPick">
              <view class="stx__pick-v">{{ selectedMajorText }}</view>
            </picker>
            <text v-if="!optionsLoading && !majors.length" class="stx__option-empty">本页没有可转入专业，可调整关键词后搜索。</text>
            <view v-if="majorPage.total > 0" class="stx__option-pager">
              <button class="btn" :disabled="majorPage.page <= 1 || optionsLoading" @click="previousMajorPage">上一页</button>
              <text>专业第 {{ majorPage.page }} / {{ majorPageCount }} 页，共 {{ majorPage.total }} 项</text>
              <button class="btn" :disabled="!majorPage.hasMore || optionsLoading" @click="nextMajorPage">下一页</button>
            </view>
            <text class="stx__pick-l">目标班级（可选）</text>
            <view v-if="form.toMajorId" class="stx__option-query">
              <input v-model="targetClassKeyword" maxlength="60" confirm-type="search" placeholder="按班级名称或年级搜索" @confirm="searchTargetClassOptions" />
              <button class="btn stx__option-search" :disabled="optionsLoading" @click="searchTargetClassOptions">搜索</button>
            </view>
            <picker mode="selector" :range="targetClassLabels" :value="targetClassIndex" @change="onTargetClassPick" :disabled="!form.toMajorId">
              <view class="stx__pick-v">{{ selectedTargetClassText }}</view>
            </picker>
            <text v-if="form.toMajorId && !optionsLoading && !targetClasses.length" class="stx__option-empty">本页没有可转入班级；不选时由教务老师后续编班。</text>
            <view v-if="form.toMajorId && targetClassPage.total > 0" class="stx__option-pager">
              <button class="btn" :disabled="targetClassPage.page <= 1 || optionsLoading" @click="previousTargetClassPage">上一页</button>
              <text>班级第 {{ targetClassPage.page }} / {{ targetClassPageCount }} 页，共 {{ targetClassPage.total }} 项</text>
              <button class="btn" :disabled="!targetClassPage.hasMore || optionsLoading" @click="nextTargetClassPage">下一页</button>
            </view>
          </view>

          <view v-if="form.changeType === 'TRANSFER_CLASS'" class="stx__pick">
            <text class="stx__pick-l">目标班级（必选，同专业）</text>
            <view class="stx__option-query">
              <input v-model="sameClassKeyword" maxlength="60" confirm-type="search" placeholder="按班级名称或年级搜索" @confirm="searchSameClassOptions" />
              <button class="btn stx__option-search" :disabled="optionsLoading" @click="searchSameClassOptions">搜索</button>
            </view>
            <picker mode="selector" :range="sameMajorClassLabels" :value="sameClassIndex" @change="onSameClassPick">
              <view class="stx__pick-v">{{ selectedSameClassText }}</view>
            </picker>
            <text v-if="!optionsLoading && !sameMajorClasses.length" class="stx__option-empty">本页没有可转入班级，可调整关键词后搜索。</text>
            <view v-if="sameClassPage.total > 0" class="stx__option-pager">
              <button class="btn" :disabled="sameClassPage.page <= 1 || optionsLoading" @click="previousSameClassPage">上一页</button>
              <text>班级第 {{ sameClassPage.page }} / {{ sameClassPageCount }} 页，共 {{ sameClassPage.total }} 项</text>
              <button class="btn" :disabled="!sameClassPage.hasMore || optionsLoading" @click="nextSameClassPage">下一页</button>
            </view>
          </view>

          <textarea :disabled="submitting || !!pendingApplication" class="stx__reason" v-model="form.reason" placeholder="申请原因（不少于5字）" maxlength="200" />
          <button class="stx__btn" :disabled="submitting || !!pendingApplication || !canSubmit" @click="submit">提交申请</button>
        </view>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { realRequest } from '@/services/request'
import { academicApplicationPage } from './application-page'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { savePending } from './pending-ledger'

const ST = {
  REGISTERED: '在籍注册', NORMAL: '在籍', SUSPENDED: '休学中', PRESERVED: '保留学籍',
  RETAINED: '留级', WITHDRAWN: '已退学', GRADUATED: '已毕业', TRANSFERRED: '已转学'
}
const CT = {
  SUSPEND: '休学', PRESERVE: '保留学籍', RESUME: '复学', WITHDRAW: '退学',
  RETAIN: '留级', TRANSFER_MAJOR: '转专业', TRANSFER_CLASS: '转班'
}
const SL = {
  SUBMITTED: '已提交', IN_REVIEW: '审批中', APPROVED_PENDING_EFFECTIVE: '已通过·待生效',
  EFFECTIVE: '已生效', REJECTED: '已驳回', RETURNED: '已退回'
}
const isForbidden = error => Number(error?.httpStatus || error?.statusCode) === 403 || /^403/.test(String(error?.code || '')) || error?.code === 'NO_PERMISSION'
const STATUS_PAGE_SIZE = 20
const TRANSFER_OPTION_PAGE_SIZE = 20

const emptyTransferPage = (target) => ({ target, items: [], page: 1, pageSize: TRANSFER_OPTION_PAGE_SIZE, total: 0, hasMore: false })

function normalizeTransferPage(result, target, requestedPage) {
  const items = result?.items
  const page = result?.page
  const pageSize = result?.pageSize
  const total = result?.total
  const hasMore = result?.hasMore
  if (result?.target !== target || !Array.isArray(items) || !Number.isSafeInteger(page) || page !== requestedPage || page < 1
    || pageSize !== TRANSFER_OPTION_PAGE_SIZE || !Number.isSafeInteger(total) || total < 0
    || typeof hasMore !== 'boolean' || items.length > pageSize
    || (items.length > 0 && total < ((page - 1) * pageSize) + items.length)
    || hasMore !== page * pageSize < total) {
    throw new Error('可选目标分页信息无法核对')
  }
  return { ...result, items, page, pageSize, total, hasMore }
}

const majorText = (row) => `${row?.collegeName ? row.collegeName + ' · ' : ''}${row?.majorName || ''}`.trim()
const classText = (row) => `${row?.className || ''}${row?.grade ? ' · ' + row.grade : ''}`.trim()

function normalizeStatusPage(result, requestedPage) {
  const changes = result?.changes
  const page = result?.page
  const pageSize = result?.pageSize
  const total = result?.total
  const hasMore = result?.hasMore
  if (!Array.isArray(changes) || !Number.isSafeInteger(page) || page !== requestedPage || page < 1
    || pageSize !== STATUS_PAGE_SIZE || !Number.isSafeInteger(total) || total < 0
    || typeof hasMore !== 'boolean' || changes.length > pageSize
    || (changes.length > 0 && total < ((page - 1) * pageSize) + changes.length)
    || hasMore !== page * pageSize < total) {
    throw new Error('学籍异动分页信息无法核对')
  }
  return { ...result, changes, page, pageSize, total, hasMore }
}

export default {
  components: { AcademicPageNav, AcademicPageState },
mixins: [academicApplicationPage],
  created() { this.applicationScope = 'status' },
  data() {
    return {
      data: null, state: 'loading', submitting: false, showForm: false, academicDraftFields: ['form', 'resubmitReasons', 'showForm'],
      form: { changeType: '', reason: '', toMajorId: '', toClassId: '' },
      resubmitReasons: {}, optionsLoaded: false,
      optionLoadingSlots: { major: false, targetClass: false, sameClass: false },
      optionFailureSlots: { major: false, targetClass: false, sameClass: false },
      transferRequestEpoch: 0,
      majorPage: emptyTransferPage('major'), targetClassPage: emptyTransferPage('class'), sameClassPage: emptyTransferPage('class'),
      majorKeyword: '', targetClassKeyword: '', sameClassKeyword: '',
      selectedMajorLabel: '', selectedTargetClassLabel: '', selectedSameClassLabel: '',
      majorIndex: 0, targetClassIndex: 0, sameClassIndex: 0, page: 1,
      TYPES: [
        { v: 'SUSPEND', l: '休学' }, { v: 'PRESERVE', l: '保留学籍' }, { v: 'RESUME', l: '复学' },
        { v: 'TRANSFER_MAJOR', l: '转专业' }, { v: 'TRANSFER_CLASS', l: '转班' },
        { v: 'RETAIN', l: '留级' }, { v: 'WITHDRAW', l: '退学' }
      ]
    }
  },
  computed: {
    majors() { return this.majorPage.items || [] },
    majorLabels() { return this.majors.map(majorText) },
    targetClasses() { return this.targetClassPage.items || [] },
    targetClassLabels() {
      return ['暂不指定班级'].concat(this.targetClasses.map(classText))
    },
    sameMajorClasses() { return this.sameClassPage.items || [] },
    sameMajorClassLabels() {
      return this.sameMajorClasses.map(classText)
    },
    optionsLoading() { return Object.values(this.optionLoadingSlots).some(Boolean) },
    optionsFailed() { return Object.values(this.optionFailureSlots).some(Boolean) },
    selectedMajorText() {
      if (!this.form.toMajorId) return '请选择目标专业'
      return this.selectedMajorLabel || '已选择目标专业（可搜索核对）'
    },
    selectedTargetClassText() {
      if (!this.form.toMajorId) return '请先选择目标专业'
      if (!this.form.toClassId) return '暂不指定，由教务编班'
      return this.selectedTargetClassLabel || '已选择目标班级（可搜索核对）'
    },
    selectedSameClassText() {
      if (!this.form.toClassId) return '请选择目标班级'
      return this.selectedSameClassLabel || '已选择目标班级（可搜索核对）'
    },
    majorPageCount() { return this.majorPage.total ? Math.ceil(this.majorPage.total / this.majorPage.pageSize) : 1 },
    targetClassPageCount() { return this.targetClassPage.total ? Math.ceil(this.targetClassPage.total / this.targetClassPage.pageSize) : 1 },
    sameClassPageCount() { return this.sameClassPage.total ? Math.ceil(this.sameClassPage.total / this.sameClassPage.pageSize) : 1 },
    canSubmit() {
      if (!this.form.changeType || (this.form.reason || '').trim().length < 5) return false
      if (this.form.changeType === 'TRANSFER_MAJOR' && !this.form.toMajorId) return false
      if (this.form.changeType === 'TRANSFER_CLASS' && !this.form.toClassId) return false
      return true
    },
    pageCount() { return this.data?.total ? Math.ceil(this.data.total / this.data.pageSize) : 1 },
    isPaging() { return this.state === 'loading' }
  },
  onLoad() { this.load() },
  methods: {
    restorePendingDraft(pending) { if (pending.kind === 'resubmit') this.resubmitReasons[pending.existingId] = pending.body.reason; else { this.form = { ...this.form, ...pending.body }; this.showForm = true } },
    resetTransferOptions() {
      this.optionsLoaded = false
      this.optionLoadingSlots = { major: false, targetClass: false, sameClass: false }
      this.optionFailureSlots = { major: false, targetClass: false, sameClass: false }
      this.majorPage = emptyTransferPage('major')
      this.targetClassPage = emptyTransferPage('class')
      this.sameClassPage = emptyTransferPage('class')
      this.majorKeyword = ''; this.targetClassKeyword = ''; this.sameClassKeyword = ''
      this.selectedMajorLabel = ''; this.selectedTargetClassLabel = ''; this.selectedSameClassLabel = ''
      this.majorIndex = 0; this.targetClassIndex = 0; this.sameClassIndex = 0
      this._transferRequestIds = {}
    },
    clearForbiddenStatus() {
      const hadPending = this.protectPendingReference()
      this.data = null; this.showForm = false; this.resubmitReasons = {}; this.resetTransferOptions()
      this.form = { changeType: '', reason: '', toMajorId: '', toClassId: '' }
      this.page = 1; this.submitting = false
      this.applicationNotice = hadPending ? '当前无权核对学籍异动记录；本次办理仍待核实。' : ''
      savePending('draft:' + this.applicationScope, null)
    },
    statusText(s) { return ST[s] || '待学校核对' },
    ctText(c) { return CT[c] || '学籍异动' },
    statusLabel(s) { return SL[s] || '请查看办理进度' },
    dateTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '—' },
    canResubmit(c) {
      return c && c.status === 'RETURNED' && String(this.resubmitReasons[c.changeId] || '').trim().length >= 5
    },
    onType(v) {
      if (this.submitting || this.pendingApplication) return
      this.form.changeType = v
      this.form.toMajorId = ''
      this.form.toClassId = ''
      this.resetTransferOptions()
      if (['TRANSFER_MAJOR', 'TRANSFER_CLASS'].includes(v)) return this.loadTransferOptions()
      return null
    },
    onMajorPick(e) {
      this.majorIndex = Number(e.detail.value)
      const m = this.majors[this.majorIndex]
      this.form.toMajorId = m ? m.majorId : ''
      this.form.toClassId = ''
      this.targetClassIndex = 0
      this.selectedMajorLabel = m ? majorText(m) : ''
      this.selectedTargetClassLabel = ''
      this.targetClassKeyword = ''
      this.targetClassPage = emptyTransferPage('class')
      return m ? this.loadTargetClassOptions(1) : Promise.resolve(null)
    },
    onTargetClassPick(e) {
      this.targetClassIndex = Number(e.detail.value)
      if (this.targetClassIndex <= 0) { this.form.toClassId = ''; this.selectedTargetClassLabel = ''; return }
      const c = this.targetClasses[this.targetClassIndex - 1]
      this.form.toClassId = c ? c.classId : ''
      this.selectedTargetClassLabel = c ? classText(c) : ''
    },
    onSameClassPick(e) {
      this.sameClassIndex = Number(e.detail.value)
      const c = this.sameMajorClasses[this.sameClassIndex]
      this.form.toClassId = c ? c.classId : ''
      this.selectedSameClassLabel = c ? classText(c) : ''
    },
    previousPage() { return this.page > 1 ? this.load(this.page - 1) : Promise.resolve(null) },
    nextPage() { return this.data?.hasMore ? this.load(this.page + 1) : Promise.resolve(null) },
    load(requested = this.pendingApplication?.kind === 'new' ? 1 : this.page) {
      const requestedPage = this.readIdentity !== currentSessionGeneration() ? 1 : Number(requested)
      if (!Number.isSafeInteger(requestedPage) || requestedPage < 1) return Promise.resolve(null)
      return this.readAcademic(async () => {
        const identity = currentSessionGeneration(); const epoch = this.readEpoch
        try { return await studentApi.getMyAcadStatus({ page: requestedPage, pageSize: STATUS_PAGE_SIZE }) }
        catch (error) { if (isForbidden(error) && epoch === this.readEpoch && identity === currentSessionGeneration() && !this.readHidden) this.clearForbiddenStatus(); throw error }
      }, (d) => {
        const data = normalizeStatusPage(d, requestedPage)
        this.data = data
        this.page = data.page
        if (['TRANSFER_MAJOR', 'TRANSFER_CLASS'].includes(this.form.changeType) && !this.optionsLoaded) this.loadTransferOptions()
        for (const c of data.changes) {
          if (c.status === 'RETURNED' && this.resubmitReasons[c.changeId] === undefined) {
            this.resubmitReasons[c.changeId] = c.reason || ''
          }
        }
        this.acceptApplication(data.changes, 'changeId', (row, body, kind) => kind === 'resubmit'
          ? row.status !== 'RETURNED' && row.reason === body.reason && Number(row.version) > Number(body.expectedVersion)
          : row.changeType === body.changeType && row.reason === body.reason)
      })
    },
    resetAcademicContext() {
      this.clearApplicationContext(); this.resubmitReasons = {}; this.finishApplication('new')
      this.resetTransferOptions(); this.page = 1
    },
    finishApplication(kind) {
      if (kind === 'resubmit') return
      this.form = { changeType: '', reason: '', toMajorId: '', toClassId: '' }; this.showForm = false
    },
    async loadOptionPage(slot, target, requestedPage, params, accepts) {
      const page = Number(requestedPage)
      if (!Number.isSafeInteger(page) || page < 1) return null
      const identity = currentSessionGeneration(); const epoch = this.readEpoch
      const current = () => identity === currentSessionGeneration() && epoch === this.readEpoch && !this.readHidden
      const requestId = ++this.transferRequestEpoch
      this._transferRequestIds = this._transferRequestIds || {}
      this._transferRequestIds[slot] = requestId
      this.optionLoadingSlots = { ...this.optionLoadingSlots, [slot]: true }
      this.optionFailureSlots = { ...this.optionFailureSlots, [slot]: false }
      try {
        const result = normalizeTransferPage(await studentApi.getTransferOptions({ ...params, target, page, pageSize: TRANSFER_OPTION_PAGE_SIZE }), target, page)
        if (!current() || this._transferRequestIds[slot] !== requestId) return null
        if (accepts && !accepts(result)) throw new Error('返回的目标范围与当前选择不一致')
        if (slot === 'major') this.majorPage = result
        if (slot === 'targetClass') this.targetClassPage = result
        if (slot === 'sameClass') this.sameClassPage = result
        this.optionsLoaded = true
        return result
      } catch (_) {
        if (current() && this._transferRequestIds[slot] === requestId) {
          this.optionFailureSlots = { ...this.optionFailureSlots, [slot]: true }
        }
        return null
      } finally {
        if (this._transferRequestIds?.[slot] === requestId) {
          this.optionLoadingSlots = { ...this.optionLoadingSlots, [slot]: false }
        }
      }
    },
    async loadMajorOptions(page = 1) {
      const result = await this.loadOptionPage('major', 'major', page, { keyword: this.majorKeyword.trim() })
      if (result && this.form.toMajorId) {
        const selected = this.majors.find(row => String(row.majorId) === String(this.form.toMajorId))
        if (selected) { this.majorIndex = this.majors.indexOf(selected); this.selectedMajorLabel = majorText(selected) }
      }
      return result
    },
    async loadTargetClassOptions(page = 1) {
      const selectedMajorId = this.form.toMajorId
      if (!selectedMajorId) return null
      const result = await this.loadOptionPage('targetClass', 'class', page, {
        majorId: selectedMajorId, keyword: this.targetClassKeyword.trim()
      }, value => String(value.majorId) === String(selectedMajorId))
      if (result && this.form.toClassId) {
        const selected = this.targetClasses.find(row => String(row.classId) === String(this.form.toClassId))
        if (selected) { this.targetClassIndex = this.targetClasses.indexOf(selected) + 1; this.selectedTargetClassLabel = classText(selected) }
      }
      return result
    },
    async loadSameClassOptions(page = 1) {
      const result = await this.loadOptionPage('sameClass', 'class', page, { keyword: this.sameClassKeyword.trim() })
      if (result && this.form.toClassId) {
        const selected = this.sameMajorClasses.find(row => String(row.classId) === String(this.form.toClassId))
        if (selected) { this.sameClassIndex = this.sameMajorClasses.indexOf(selected); this.selectedSameClassLabel = classText(selected) }
      }
      return result
    },
    async loadTransferOptions() {
      if (this.form.changeType === 'TRANSFER_MAJOR') {
        const result = await this.loadMajorOptions(1)
        if (result && this.form.toMajorId) return this.loadTargetClassOptions(1)
        return result
      }
      if (this.form.changeType === 'TRANSFER_CLASS') return this.loadSameClassOptions(1)
      return null
    },
    searchMajorOptions() { return this.loadMajorOptions(1) },
    searchTargetClassOptions() { return this.loadTargetClassOptions(1) },
    searchSameClassOptions() { return this.loadSameClassOptions(1) },
    previousMajorPage() { return this.majorPage.page > 1 ? this.loadMajorOptions(this.majorPage.page - 1) : Promise.resolve(null) },
    nextMajorPage() { return this.majorPage.hasMore ? this.loadMajorOptions(this.majorPage.page + 1) : Promise.resolve(null) },
    previousTargetClassPage() { return this.targetClassPage.page > 1 ? this.loadTargetClassOptions(this.targetClassPage.page - 1) : Promise.resolve(null) },
    nextTargetClassPage() { return this.targetClassPage.hasMore ? this.loadTargetClassOptions(this.targetClassPage.page + 1) : Promise.resolve(null) },
    previousSameClassPage() { return this.sameClassPage.page > 1 ? this.loadSameClassOptions(this.sameClassPage.page - 1) : Promise.resolve(null) },
    nextSameClassPage() { return this.sameClassPage.hasMore ? this.loadSameClassOptions(this.sameClassPage.page + 1) : Promise.resolve(null) },
    resubmit(c) {
      if (!this.canResubmit(c) || this.submitting || this.pendingApplication) return
      const body = { reason: String(this.resubmitReasons[c.changeId] || '').trim(), expectedVersion: c.version }
      return this.sendApplication({ title: '修改并重交原申请', kind: 'resubmit', existingId: c.changeId, body,
        recovery: { field: 'status', excludes: ['RETURNED', 'REJECTED', 'CANCELLED'] }, send: frozen => realRequest(`/mobile/academic/status-changes/${encodeURIComponent(c.changeId)}/resubmit`, { method: 'POST', data: frozen }), rows: this.data.changes, idKey: 'changeId' })
    },
    submit() {
      if (!this.canSubmit || this.submitting || this.pendingApplication) return
      const body = { changeType: this.form.changeType, reason: this.form.reason.trim(),
        toMajorId: this.form.changeType === 'TRANSFER_MAJOR' ? (this.form.toMajorId || undefined) : undefined,
        toClassId: ['TRANSFER_MAJOR', 'TRANSFER_CLASS'].includes(this.form.changeType) ? (this.form.toClassId || undefined) : undefined }
      return this.sendApplication({ title: '提交学籍异动申请', kind: 'new', body, send: frozen => studentApi.submitStatusChange(frozen), rows: this.data.changes, idKey: 'changeId' })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.stx__cur { border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4); color: #fff; }
.stx__cur.is-ok { background: var(--brand-primary); }
.stx__cur.is-warn { background: #d97706; }
.stx__cur-t { display: block; font-size: var(--font-size-sm); opacity: 0.85; }
.stx__cur-v { display: block; font-size: 20px; font-weight: 700; margin-top: 4px; }
.stx__sec-t { font-weight: 700; margin: var(--space-4) 0 var(--space-2); }
.stx__empty { color: var(--text-tertiary); font-size: var(--font-size-sm); padding: var(--space-2) 0; }
.stx__ch { display: flex; flex-direction: column; gap: 10px; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-2); box-shadow: var(--shadow-card); }
.stx__ch-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.stx__ch-state { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; }
.stx__ch-s.is-ok { color: #16a34a; }
.stx__ch-plan { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.stx__resubmit { border-top: 1px solid var(--border-base); padding-top: 10px; }
.stx__review-note { display: block; margin-bottom: 8px; padding: 8px 10px; border-radius: var(--radius-md); background: #fff7ed; color: #9a3412; font-size: var(--font-size-sm); line-height: 1.6; }
.stx__resubmit-hint { display: block; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; margin-bottom: 8px; }
.stx__reason--resubmit { min-height: 72px; }
.stx__btn--resubmit { margin-top: 8px; }
.stx__form { background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); }
.stx__chips { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-3); }
.stx__chip { padding: 8px 16px; border-radius: var(--radius-full); background: var(--bg-page); border: 1px solid var(--border-base); font-size: var(--font-size-sm); }
.stx__chip.is-on { background: var(--brand-primary); color: #fff; border-color: var(--brand-primary); }
.stx__pick { margin-bottom: var(--space-3); }
.stx__pick-l { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin: 8px 0 4px; }
.stx__pick-v { background: var(--bg-page); border-radius: var(--radius-md); padding: 10px 12px; font-size: var(--font-size-base); }
.stx__option-query { display: flex; gap: 8px; margin: 6px 0; }
.stx__option-query input { flex: 1; min-width: 0; box-sizing: border-box; background: var(--bg-page); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 8px 10px; font-size: var(--font-size-sm); }
.stx__option-search { flex: 0 0 auto; margin: 0; padding: 8px 14px; font-size: var(--font-size-sm); }
.stx__option-empty { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.5; margin-top: 6px; }
.stx__option-pager { display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-top: 8px; color: var(--text-secondary); font-size: var(--font-size-xs); }
.stx__option-pager button { flex: 0 0 auto; margin: 0; padding: 6px 8px; font-size: var(--font-size-xs); }
.stx__option-pager text { flex: 1; min-width: 0; text-align: center; }
.stx__reason { width: 100%; min-height: 80px; background: var(--bg-page); border-radius: var(--radius-md); padding: var(--space-3); font-size: var(--font-size-base); box-sizing: border-box; }
.stx__btn { margin-top: var(--space-3); background: var(--brand-primary); color: #fff; border-radius: var(--radius-full); padding: 12px; }
.stx__btn[disabled] { opacity: 0.5; }
.stx__pager { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); margin: var(--space-4) 0; color: var(--text-secondary); font-size: var(--font-size-sm); }
.stx__pager-button { flex: 1; margin: 0; }
</style>
