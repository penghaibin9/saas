<template>
  <view class="mobile-page mobile-teacher page-wrap teacher-applications">
    <MobileNavBar variant="teacher" title="实习申请审核" show-back />

    <view class="page-pad ap__context">
      <view class="ap__batch" v-if="batches.length">
        <view class="ap__batch-copy">
          <text class="ap__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
        </view>
        <picker v-if="batches.length > 1" class="mobile-picker ap__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="!!actingId" @change="onBatch">
          <view class="ap__pick-val">切换批次 <text class="ap__arrow">▾</text></view>
        </picker>
      </view>
      <button v-if="canViewVolunteers" class="mobile-control ap__volunteers" @click="openVolunteers">招聘季志愿</button>

      <button v-if="batches.length && summary" class="mobile-control btn btn-ghost" :aria-expanded="summaryOpen" @click="summaryOpen=!summaryOpen">{{ summaryOpen ? '收起申请与志愿填报统计' : '填报统计' }}</button>
      <view v-if="batches.length && summary && summaryOpen" class="card ap__summary">
        <view class="ap__summary-main">
          <text class="ap__summary-label">普通申请与志愿填报覆盖</text>
          <text class="ap__summary-note">仅统计普通申请和招聘季志愿，不等于去向落实或实际上岗；学校安排请查看学生档案。</text>
          <view class="ap__summary-value"><text>{{ summary.filledStudents }}</text><text>/ {{ summary.totalStudents }} 人</text></view>
          <text class="ap__summary-note">{{ summaryConclusion }}</text>
          <view class="ap__coverage-bar" aria-label="普通申请与志愿填报比例">
            <view class="ap__coverage-fill" :style="{ width: filledRate + '%' }" />
          </view>
          <text class="ap__coverage-rate">已填报 {{ filledRate }}%</text>
        </view>
        <view class="ap__summary-metrics">
          <button class="mobile-control ap__metric" @click="toggleStudentState('FILLED')"><text>{{ summary.filledStudents }}</text><text>已填报</text></button>
          <button class="mobile-control ap__metric is-danger" @click="toggleStudentState('UNFILLED')"><text>{{ summary.unfilledStudents }}</text><text>未填报</text></button>
          <view class="ap__metric"><text>{{ summary.pendingReviewApplications }}</text><text>普通申请待审</text></view>
          <view class="ap__metric"><text>{{ summary.reviewedApplications }}</text><text>普通申请已审</text></view>
        </view>
        <button class="mobile-control" v-for="campaign in summary.recruitmentCampaigns || []" :key="campaign.campaignId" @click="openVolunteers(campaign)">{{ campaign.name }} · 已填 {{ campaign.filledGroups }} 人 · 待办理 {{ campaign.pendingGroups }} 组</button>
        <view v-if="studentState" class="ap__drill">
          <view class="row-between">
            <text class="ap__drill-title">{{ studentStateLabel }}（{{ studentTotal }}人）</text>
            <button class="mobile-control ap__drill-close" @click="closeStudentState">收起</button>
          </view>
          <text v-if="studentLoading && !studentRows.length" class="ap__drill-empty">正在读取完整名单…</text>
          <view v-else-if="studentError"><text class="ap__drill-empty">{{ studentError }}</text><button class="mobile-control" @click="loadStudentState(false)">重新读取名单</button></view>
          <text v-else-if="!studentRows.length" class="ap__drill-empty">当前范围没有{{ studentStateLabel }}学生。</text>
          <view v-else class="ap__student-list">
            <view v-for="student in studentRows" :key="student.recordId" class="ap__student">
              <view>
                <text class="ap__student-name">{{ student.studentName }}</text>
                <text class="ap__student-no">{{ student.studentNo }}<template v-if="student.advisorName"> · {{ student.advisorName }}</template></text>
              </view>
              <text class="ap__student-dest">{{ student.companyName || (studentState === 'UNFILLED' ? '未填普通申请或志愿' : '已填报') }}</text>
              <button class="mobile-control" v-if="canViewStudent" @click="openStudent(student)">学生档案</button>
            </view>
            <button v-if="studentHasMore" class="mobile-control ap__more" :disabled="studentLoading" @click="loadMoreStudents">
              {{ studentLoading ? '读取中…' : '继续加载名单' }}
            </button>
          </view>
        </view>
      </view>

      <view v-if="batches.length" class="ap__tabs">
        <button class="mobile-control" v-for="tab in reviewTabs" :key="tab.value" :class="{ 'is-active': reviewStatus === tab.value }" @click="setReviewStatus(tab.value)">
          <text>{{ tab.label }}</text><text v-if="summary">{{ reviewCount(tab.value) }}</text>
        </button>
      </view>
      <text v-if="batches.length" class="ap__summary-note">普通申请</text>

      <MobileInlineAlert v-if="canReview && list?.some(a => a.status === 'PENDING_REVIEW')" type="warning" description="通过后将落实实习去向，请先核对申请和证明材料。" />
      <MobileInlineAlert v-if="reviewDraft" type="warning" :description="'已保留' + reviewDraft.studentName + '的审核意见：' + reviewDraft.comment" />
      <view v-if="lastReceipt" class="card ap__note"><text class="ap__section-label">{{ lastReceipt.studentName }} · {{ lastReceipt.statusLabel }}</text><text class="ap__note-text">{{ lastReceipt.nextStep }}</text></view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad ap__list" v-if="list">
        <view v-if="focusId" class="card"><text>正在查看待办对应的原申请。</text><button class="mobile-control btn btn-ghost" @click="clearFocus">查看本批次全部申请</button></view>
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可审核的岗位实习批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" :title="emptyTitle"
          description="可切换分类查看其他申请。" />
        <view class="stack" v-else>
          <view v-for="a in list" :key="a.id" class="card ap">
            <view class="row-between ap__head">
              <view class="flex-1 ap__identity">
                <text class="t-md t-bold">{{ a.studentName || '—' }}</text>
                <text class="ap__sub">{{ a.studentNo || '' }} · {{ a.applicationTypeLabel }}</text>
              </view>
              <MobileStatusTag :label="a.statusLabel" :type="statusType(a.status)" />
            </view>

            <view class="ap__business">
              <view class="ap__row"><text class="ap__row-k">企业</text><text class="ap__row-v">{{ a.companyName || '—' }}</text></view>
              <view class="ap__row"><text class="ap__row-k">岗位</text><text class="ap__row-v">{{ a.positionName || '—' }}</text></view>
              <view class="ap__row" v-if="a.workAddress"><text class="ap__row-k">地点</text><text class="ap__row-v">{{ a.workAddress }}</text></view>
              <view class="ap__row" v-if="a.contactName"><text class="ap__row-k">联系人</text><text class="ap__row-v">{{ a.contactName }} {{ a.contactPhone || '' }}</text></view>
            </view>

            <button v-if="applicationIsFinal(a) && (a.applicationNote || a.reviewComment)" class="mobile-control btn btn-ghost" :aria-expanded="!!applicationDetailsOpen[a.id]" @click="applicationDetailsOpen[a.id]=!applicationDetailsOpen[a.id]">{{ applicationDetailsOpen[a.id] ? '收起申请说明与意见' : '查看申请说明与意见' }}</button>
            <view v-if="a.applicationNote && (!applicationIsFinal(a) || applicationDetailsOpen[a.id])" class="ap__note">
              <text class="ap__section-label">申请说明</text>
              <text class="ap__note-text">{{ a.applicationNote }}</text>
            </view>
            <view v-if="a.reviewComment && (!applicationIsFinal(a) || applicationDetailsOpen[a.id])" class="ap__note"><text class="ap__section-label">审核意见</text><text class="ap__note-text">{{ a.reviewComment }}</text></view>
            <button class="mobile-control" v-if="canViewStudent" @click="openStudent(a)">查看学生档案</button>

            <button v-if="a.evidenceFileId" class="mobile-control ap__evidence" :disabled="previewingId === a.id" @click="previewEvidence(a)">
              <view class="ap__evidence-copy">
                <text class="ap__evidence-title">申请证明材料</text>
                <text class="ap__evidence-hint">{{ applicationIsFinal(a) ? '查看本次申请的证明材料' : '核对材料后再审核' }}</text>
              </view>
              <text class="ap__evidence-action">{{ previewingId === a.id ? '打开中…' : '查看 ›' }}</text>
            </button>
            <view v-else-if="a.applicationType === 'SELF_ARRANGED'" class="ap__danger">
              <text class="ap__danger-title">缺少自主实习证明材料</text>
              <text class="ap__danger-text">{{ applicationIsFinal(a) ? '该申请未留存证明材料，请核对历史记录。' : '请退回学生补充材料。' }}</text>
            </view>

            <view class="ap__versions" :class="{ 'has-error': a.recordVersion == null || a.version == null }">
              <text v-if="a.recordVersion == null || a.version == null">资料待刷新，暂不能审核。</text>
              <view v-if="a.version != null"><text>申请版本</text><text>第 {{ a.version }} 版</text></view>
              <view><text>提交时间</text><text>{{ fmt(a.submittedAt) }}</text></view>
            </view>

            <view class="ap__next" :class="{ 'is-danger': !canApprove(a) }">
              <text class="ap__next-label">下一步</text>
              <text class="ap__next-text">{{ nextStepText(a) }}</text>
            </view>

            <view class="ap__actions" v-if="a.status === 'PENDING_REVIEW' && canReview">
              <button class="mobile-control ap__reject flex-1" :disabled="actingId === a.id" @click="review(a, 'REJECT')">驳回修改</button>
              <button class="mobile-control ap__approve flex-1" :disabled="actingId === a.id || !canApprove(a)" @click="review(a, 'APPROVE')">{{ approveLabel(a) }}</button>
            </view>
            <MobileInlineAlert v-else-if="a.status === 'PENDING_REVIEW'" type="warning" description="当前身份仅可查看，无正式实习申请审核权限。" />
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import {
  teacherInternshipApplications,
  teacherInternshipApplicationSummary,
  teacherInternshipApplicationStudents,
  teacherInternshipApplicationReview
} from '@/services/internshipApi'
import { openBusinessFile } from '@/services/fileApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      applicationDetailsOpen:{}, summaryOpen:false, list: null, summary: null, state: 'loading', actingId: '', previewingId: '', batches: [],
      batchId: '', batchIndex: 0, page: 1, hasMore: false, loadingMore: false,
      reviewStatus: 'PENDING_REVIEW',
      studentState: '', studentRows: [], studentPage: 1, studentTotal: 0,
      studentHasMore: false, studentLoading: false, studentError: '', reviewDraft: null, lastReceipt: null,
      requestSeq: 0, studentSeq: 0, reviewSeq: 0, generation: currentSessionGeneration(), hidden: false,
      requestedBatchId: '', focusId: ''
    }
  },
  computed: {
    canViewVolunteers() { return useInternshipContextStore().can('internship.application.view') },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.studentCount}人`) },
    canViewStudent() { return useInternshipContextStore().can('internship.student.view') },
    canReview() { return useInternshipContextStore().can('internship.application.review') },
    reviewTabs() {
      return [
        { value: 'PENDING_REVIEW', label: '未审核' },
        { value: 'REVIEWED', label: '已审核' },
        { value: 'REJECTED', label: '已驳回' },
        { value: 'ALL', label: '全部' }
      ]
    },
    filledRate() { return Number(this.summary?.filledRate || 0) },
    studentStateLabel() { return this.studentState === 'FILLED' ? '已填报名单' : '未填报名单' },
    emptyTitle() {
      const found = this.reviewTabs.find((item) => item.value === this.reviewStatus)
      return `当前批次没有${found?.label || ''}申请`
    },
    summaryConclusion() {
      if (!this.summary?.totalStudents) return '当前数据范围暂无应填报学生。'
      if (this.summary.unfilledStudents) return `${this.summary.unfilledStudents} 名学生尚未填普通申请或志愿；学校安排去向另行核对。`
      const pending = this.summary.pendingReviewApplications || 0, groups = this.summary.pendingRecruitmentGroups || 0
      if (pending || groups) return `全部学生已填报，仍有 ${pending} 条普通申请、${groups} 组招聘季志愿待办理。`
      return '暂无待审申请；草稿和待补正仍需学生继续办理。'
    }
  },
  onLoad(options = {}) { this.requestedBatchId = String(options.batchId || ''); this.focusId = String(options.applicationId || ''); if (this.focusId) this.reviewStatus = 'ALL'; return this.load() },
  onShow() { const refresh = this.hidden || this.generation !== currentSessionGeneration(); this.hidden = false; if (refresh) return this.load() },
  onHide() { this.hidden = true; this.requestSeq++; this.reviewSeq++; this.actingId = ''; this.closeStudentState() },
  onUnload() { this.hidden = true; this.requestSeq++; this.reviewSeq++; this.actingId = ''; this.closeStudentState() },
  onReachBottom() { this.loadMore() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    applicationIsFinal(item) { return ['APPROVED','CANCELLED','WITHDRAWN','CLOSED'].includes(item.status) },
    clearFocus() { this.focusId = ''; this.reviewStatus = 'PENDING_REVIEW'; return this.load() },
    current(seq, generation, batchId = this.batchId, status = this.reviewStatus) { return !this.hidden && seq === this.requestSeq && generation === currentSessionGeneration() && String(batchId) === String(this.batchId) && status === this.reviewStatus },
    openStudent(item) { if (this.canViewStudent && item.recordId) uni.navigateTo({ url: '/pages/teacher-internship/internship-students/detail?id=' + encodeURIComponent(item.recordId) + '&batchId=' + encodeURIComponent(this.batchId) }) },
    openVolunteers(campaign) { uni.navigateTo({ url: '/pages/teacher-internship/internship-volunteers/index' + (this.batchId ? '?batchId=' + encodeURIComponent(this.batchId) : '') + (campaign?.campaignId ? '&campaignId=' + encodeURIComponent(campaign.campaignId) : '') }) },
    statusType(status) {
      if (status === 'APPROVED') return 'success'
      if (status === 'REJECTED') return 'danger'
      if (status === 'PENDING_REVIEW') return 'warning'
      return 'default'
    },
    reviewCount(status) {
      if (!this.summary) return ''
      if (status === 'PENDING_REVIEW') return this.summary.pendingReviewApplications
      if (status === 'REVIEWED') return this.summary.reviewedApplications
      if (status === 'REJECTED') return this.summary.rejectedApplications
      return this.summary.pendingReviewApplications + this.summary.reviewedApplications + this.summary.draftApplications + this.summary.withdrawnApplications + this.summary.cancelledApplications
    },
    async setReviewStatus(status) {
      if (this.actingId || this.reviewStatus === status) return
      this.reviewStatus = status
      this.list = null
      this.page = 1
      await this.load()
    },
    async toggleStudentState(state) {
      if (this.studentState === state) { this.closeStudentState(); return }
      this.closeStudentState()
      this.studentState = state
      this.studentRows = []
      this.studentPage = 1
      this.studentTotal = 0
      this.studentHasMore = false
      await this.loadStudentState(false)
    },
    closeStudentState() {
      this.studentSeq++
      this.studentState = ''
      this.studentRows = []
      this.studentPage = 1
      this.studentTotal = 0
      this.studentHasMore = false
      this.studentLoading = false
      this.studentError = ''
    },
    async loadStudentState(append = false) {
      if (!this.batchId || !this.studentState || this.studentLoading) return
      const batchId = this.batchId
      const state = this.studentState
      const seq = ++this.studentSeq, view = this.requestSeq, generation = currentSessionGeneration()
      const current = () => this.current(view, generation, batchId) && seq === this.studentSeq && state === this.studentState
      this.studentLoading = true
      this.studentError = ''
      try {
        const page = append ? this.studentPage + 1 : 1
        const data = await teacherInternshipApplicationStudents(batchId, state, page, 20)
        if (!current()) return
        const rows = (data && (data.items || data.list)) || []
        this.studentRows = append ? [...this.studentRows, ...rows] : rows
        this.studentPage = page
        this.studentTotal = Number(data?.total ?? rows.length)
        this.studentHasMore = !!data?.hasMore
      } catch (e) {
        if (current()) this.studentError = '学生填报名单读取失败，已有名单保留，请重新读取。'
      } finally { if (current()) this.studentLoading = false }
    },
    async loadMoreStudents() { await this.loadStudentState(true) },
    fmt(value) { return value ? String(value).slice(0, 16).replace('T', ' ') : '—' },
    approveLabel(a) { return a.applicationType === 'EXEMPTION' ? '通过免实习申请' : a.applicationType === 'SELF_ARRANGED' ? '通过并确认自主实习' : '通过并落实岗位' },
    canApprove(a) {
      const evidenceOk = a.applicationType === 'POSITION' || !!a.evidenceFileId
      return evidenceOk && a.recordVersion != null && a.version != null
    },
    nextStepText(a) {
      if (a.applicationType === 'SELF_ARRANGED' && !a.evidenceFileId) return '驳回学生补充自主实习证明材料。'
      if (a.recordVersion == null || a.version == null) return '刷新页面获取最新申请与学生记录版本。'
      if (a.applicationType === 'EXEMPTION') return '核对免实习原因、去向及证明材料后审核。'
      return a.applicationType === 'SELF_ARRANGED' ? '查看证明材料，核实企业信息后确认自主实习。' : '核对企业与岗位信息后，通过并落实岗位。'
    },
    async load(done) {
      this.applicationDetailsOpen={}
      if (this.generation !== currentSessionGeneration()) { this.reviewDraft = null; this.lastReceipt = null; this.reviewSeq++; this.actingId = ''; this.batches = []; this.batchId = ''; this.batchIndex = 0 }
      const seq = ++this.requestSeq, generation = this.generation = currentSessionGeneration()
      this.state = 'loading'
      this.list = null; this.summary = null; this.loadingMore = false; this.closeStudentState()
      this.page = 1
      this.hasMore = false
      try {
        const context = useInternshipContextStore()
        context.restore()
        await context.load(true)
        if (this.hidden || seq !== this.requestSeq || generation !== currentSessionGeneration()) return
        if ((this.focusId && (!/^[1-9]\d*$/.test(this.focusId) || !this.requestedBatchId)) || (this.requestedBatchId && !/^[1-9]\d*$/.test(this.requestedBatchId))) throw new Error('待办定位信息不完整，请返回待办重新进入')
        if (this.requestedBatchId && !context.selectBatch(this.requestedBatchId)) throw new Error('当前身份无权处理该待办所属批次，请返回待办刷新核对')
        this.batches = context.batches || []
        if (String(this.batchId) !== String(context.selectedBatchId || '')) { this.reviewDraft = null; this.lastReceipt = null }
        this.batchId = context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        if (!this.batchId) {
          this.list = []
          this.summary = null
          this.closeStudentState()
          this.state = 'ready'
          return
        }
        const batchId = this.batchId, status = this.reviewStatus
        const [data, summary] = await Promise.all([
          teacherInternshipApplications(batchId, 1, 20, status, this.focusId),
          teacherInternshipApplicationSummary(batchId)
        ])
        if (!this.current(seq, generation, batchId, status)) return
        this.list = (data && (data.items || data.list)) || []
        this.summary = summary || null
        this.hasMore = !!data?.hasMore
        if (this.studentState) await this.loadStudentState(false)
        this.state = 'ready'
      } catch (e) {
        if (!this.current(seq, generation)) return
        this.list = []
        this.summary = null
        this.state = 'error'
        toast((e && e.message) || '实习申请加载失败')
      } finally { if (typeof done === 'function') done() }
    },
    async onBatch(e) {
      if (this.actingId) return
      this.focusId = ''; this.requestedBatchId = ''
      this.batchIndex = Number(e.detail.value)
      const batch = this.batches[this.batchIndex]
      const context = useInternshipContextStore()
      context.selectBatch(batch && batch.id)
      this.batchId = context.selectedBatchId
      this.reviewDraft = null
      this.lastReceipt = null
      this.list = []
      this.closeStudentState()
      await this.load()
    },
    async loadMore() {
      if (!this.batchId || !this.hasMore || this.loadingMore || this.state !== 'ready') return
      const selectedBatch = this.batchId
      const seq = this.requestSeq, generation = currentSessionGeneration(), status = this.reviewStatus
      this.loadingMore = true
      try {
        const nextPage = this.page + 1
        const data = await teacherInternshipApplications(selectedBatch, nextPage, 20, status, this.focusId)
        if (!this.current(seq, generation, selectedBatch, status)) return
        this.list = [...(this.list || []), ...(data?.items || [])]
        this.page = nextPage
        this.hasMore = !!data?.hasMore
      } catch (e) { if (this.current(seq, generation, selectedBatch, status)) toast('后续申请读取失败，已加载申请保留') }
      finally { if (this.current(seq, generation, selectedBatch, status)) this.loadingMore = false }
    },
    async previewEvidence(item) {
      if (!item.evidenceFileId || this.previewingId) return
      this.previewingId = item.id
      try { await openBusinessFile(item.evidenceFileId) }
      catch (e) { toast((e && e.message) || '证明材料打开失败') }
      finally { this.previewingId = '' }
    },
    review(a, action) {
      if (!this.canReview || this.actingId || this.state !== 'ready') return
      if (action === 'APPROVE' && !this.canApprove(a)) {
        toast(a.applicationType === 'SELF_ARRANGED' && !a.evidenceFileId
          ? '自主实习证明材料缺失，不能通过'
          : '申请或学生记录版本缺失，请刷新后再试')
        return
      }
      const reject = action === 'REJECT'
      const seq = this.requestSeq, generation = currentSessionGeneration(), batchId = this.batchId, status = this.reviewStatus
      const snapshot = { ...a }
      const operation = ++this.reviewSeq
      const release = () => { if (operation === this.reviewSeq) this.actingId = '' }
      this.actingId = a.id
      uni.showModal({
        title: reject ? '驳回申请' : this.approveLabel(a),
        editable: true,
        placeholderText: reject ? '请填写具体驳回原因（至少5字）' : '可填写审核意见',
        content: this.reviewDraft?.id === a.id && this.reviewDraft.batchId === batchId && this.reviewDraft.action === action ? this.reviewDraft.comment : '',
        success: async (r) => {
          if (!r.confirm) { release(); return }
          const comment = (r.content || '').trim()
          if (operation !== this.reviewSeq || !this.current(seq, generation, batchId, status)) { release(); return }
          this.reviewDraft = { id: a.id, batchId, action, studentName: a.studentName || '当前学生', comment }
          if (reject && comment.length < 5) { release(); toast('驳回原因至少5个字，意见已保留'); return }
          try {
            const receipt = await teacherInternshipApplicationReview(snapshot.id, batchId, {
              action,
              comment,
              expectedVersion: snapshot.version,
              recordExpectedVersion: snapshot.recordVersion,
              batchId
            })
            if (!this.current(seq, generation, batchId, status)) return
            this.reviewDraft = null
            this.lastReceipt = { studentName: snapshot.studentName || '当前学生', statusLabel: receipt.statusLabel || '状态待回读', nextStep: reject ? '由学生按意见修改原申请并重新提交。' : snapshot.applicationType === 'EXEMPTION' ? '学生可查看免实习审核结果。' : '学生可继续办理知情确认、协议与上岗前置。' }
            toast(receipt.statusLabel || '审核结果已返回，请核对回执')
            await this.load()
          } catch (e) {
            if (!this.current(seq, generation, batchId, status)) return
            if (['DATA_CONFLICT', 'APPROVAL_VERSION_CONFLICT', '409001'].includes(String(e && (e.bizCode || e.code)))) {
              toast((e && e.message) || '申请或学生记录已变化，正在刷新')
              await this.load()
            } else toast((e && e.message) || '申请审核失败，请重试')
          } finally { release() }
        },
        fail: release
      })
    }
  }
}
</script>

<style scoped>
.ap__context{display:flex;flex-direction:column;gap:var(--space-3)}.ap__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.ap__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.ap__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.ap__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ap__picker{flex-shrink:0}.ap__pick-val{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.ap__arrow{margin-left:4px;color:var(--text-tertiary)}.ap__summary{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.ap__summary-main{min-width:0}.ap__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ap__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.ap__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.ap__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.ap__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ap__coverage-bar{height:8px;margin-top:10px;overflow:hidden;border-radius:999px;background:var(--gray-100)}.ap__coverage-fill{height:100%;min-width:0;border-radius:999px;background:var(--teacher-600)}.ap__coverage-rate{display:block;margin-top:5px;font-size:10px;color:var(--text-tertiary)}.ap__summary-metrics{width:100%;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.ap__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 4px;border:0;border-left:1px solid var(--border-light);border-radius:0;background:transparent;text-align:center;line-height:1.2}.ap__metric::after{border:none}.ap__metric:first-child{border-left:0}.ap__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.ap__metric.is-danger text:first-child{color:var(--danger-600)}.ap__metric text:last-child{font-size:10px;line-height:1.3;color:var(--text-tertiary)}.ap__tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.ap__tabs button{display:flex;align-items:center;justify-content:center;gap:4px;min-height:38px;padding:0 4px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--bg-card);font-size:var(--font-size-xs);color:var(--text-secondary)}.ap__tabs button::after{border:none}.ap__tabs button.is-active{border-color:var(--teacher-500);background:var(--teacher-50);color:var(--teacher-700);font-weight:600}.ap__drill{padding:var(--space-2);border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--bg-card)}.ap__drill-title{font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.ap__drill-close{margin:0;padding:4px 8px;border:0;background:transparent;font-size:var(--font-size-xs);color:var(--teacher-700)}.ap__drill-close::after{border:none}.ap__drill-empty{display:block;padding:12px 0;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ap__student-list{display:flex;flex-direction:column;margin-top:8px}.ap__student{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 0;border-top:1px solid var(--border-light)}.ap__student-name{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.ap__student-no{display:block;margin-top:2px;font-size:10px;color:var(--text-tertiary)}.ap__student-dest{max-width:45%;font-size:var(--font-size-xs);color:var(--text-secondary);text-align:right;word-break:break-word}.ap__more{width:100%;min-height:38px;margin-top:8px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--bg-card);font-size:var(--font-size-sm);color:var(--teacher-700)}.ap__more::after{border:none}.ap__list{padding-top:0}.ap{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.ap__head{align-items:flex-start}.ap__identity{min-width:0}.ap__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px;word-break:break-word}.ap__business{display:flex;flex-direction:column;gap:8px;padding:var(--space-2) var(--space-3);background:var(--gray-50);border-radius:var(--radius-md)}.ap__row{display:flex;gap:var(--space-3);min-width:0}.ap__row-k{font-size:var(--font-size-xs);color:var(--text-tertiary);width:42px;flex-shrink:0}.ap__row-v{min-width:0;flex:1;font-size:var(--font-size-sm);line-height:1.5;color:var(--text-primary);word-break:break-word}.ap__note{padding:var(--space-2) var(--space-3);border:1px solid var(--border-light);border-radius:var(--radius-md)}.ap__section-label{display:block;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ap__note-text{display:block;margin-top:5px;font-size:var(--font-size-sm);line-height:1.6;color:var(--text-primary);white-space:pre-wrap;word-break:break-word}.ap__evidence{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);min-height:58px;padding:10px var(--space-3);border:1px solid var(--success-300,#86efac);border-radius:var(--radius-md);background:var(--success-50);text-align:left}.ap__evidence::after{border:none}.ap__evidence-copy{min-width:0}.ap__evidence-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--success-800,#166534)}.ap__evidence-hint{display:block;margin-top:3px;font-size:var(--font-size-xs);color:var(--success-700)}.ap__evidence-action{flex-shrink:0;font-size:var(--font-size-sm);color:var(--success-700)}.ap__danger{padding:var(--space-2) var(--space-3);border:1px solid var(--danger-200,#fecaca);border-radius:var(--radius-md);background:var(--danger-50)}.ap__danger-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--danger-700)}.ap__danger-text{display:block;margin-top:3px;font-size:var(--font-size-xs);line-height:1.5;color:var(--danger-600)}.ap__versions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:var(--space-2);border-radius:var(--radius-md);background:var(--gray-50)}.ap__versions.has-error{background:var(--warning-50,#fff7ed)}.ap__versions>view{min-width:0;display:flex;flex-direction:column;gap:3px}.ap__versions>view text:first-child{font-size:10px;color:var(--text-tertiary)}.ap__versions>view text:last-child{font-size:var(--font-size-xs);font-weight:600;color:var(--text-primary);word-break:break-word}.ap__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.ap__next.is-danger{background:var(--warning-50,#fff7ed)}.ap__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ap__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.ap__actions{display:flex;gap:var(--space-2)}.ap__reject,.ap__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.ap__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.ap__approve{border:none;background:var(--teacher-600);color:#fff}.ap__approve[disabled],.ap__reject[disabled],.ap__evidence[disabled]{opacity:.45}.ap__reject::after,.ap__approve::after{border:none}@media(max-width:360px){.ap__summary{flex-direction:column}.ap__summary-metrics{width:100%}.ap__versions{grid-template-columns:1fr}.ap__batch{align-items:flex-start}}
.teacher-applications .ap__context,.teacher-applications .ap__list{width:100%;max-width:760px;margin:0 auto;box-sizing:border-box}.teacher-applications .card{border-radius:8px;box-shadow:none}.teacher-applications button{min-height:44px;font-size:14px}.ap__batch{padding:4px 0 12px;border-bottom:1px solid var(--border-light);border-radius:0;background:transparent}.ap__batch-name{font-size:15px;line-height:22px;margin-top:0}.ap__pick-val{display:flex;align-items:center;min-height:44px;font-size:14px;white-space:nowrap}.ap__volunteers{margin:0;width:100%;border:1px solid var(--border-base);border-radius:8px;background:var(--bg-card);color:var(--brand-primary);text-align:left;padding:8px 12px}.ap__volunteers::after{border:0}.ap__summary-label,.ap__summary-note,.ap__coverage-rate,.ap__sub,.ap__row-k,.ap__row-v,.ap__section-label,.ap__note-text,.ap__evidence-hint,.ap__danger-text,.ap__next-label,.ap__next-text,.ap__student-no,.ap__student-dest,.ap__drill-empty{font-size:14px;line-height:22px}.ap__summary-value{font-size:28px}.ap__metric>text:last-child{font-size:14px;line-height:20px}.ap__tabs button{font-size:14px;min-height:44px;padding:8px}.ap__evidence-title,.ap__evidence-action,.ap__danger-title,.ap__student-name,.ap__drill-title{font-size:15px;line-height:22px}.ap__versions>view text{font-size:14px;line-height:22px}.ap__actions button{font-size:15px}.ap__summary{gap:12px}.ap__identity,.ap__batch-copy{min-width:0}.ap__sub,.ap__batch-name{overflow-wrap:anywhere}
</style>
