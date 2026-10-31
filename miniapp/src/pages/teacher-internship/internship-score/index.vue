<template>
  <view class="internship-surface mobile-page mobile-teacher page-wrap">
    <MobileNavBar variant="teacher" title="实习成绩" show-back :fallback-url="'/pages/teacher-internship/index?batchId=' + batchId" />

    <view class="is__tabs">
      <view class="is__tab" :class="{ 'is-on': tab === 'list' }" @click="tab = 'list'">
        成绩列表<text v-if="list && list.length" class="is__tab-badge">{{ list.length }}</text>
        <text v-if="tab === 'list'" class="is__tab-u" />
      </view>
      <view v-if="canCompute" class="is__tab" :class="{ 'is-on': tab === 'compute' }" @click="onComputeTab">
        核算成绩<text v-if="tab === 'compute'" class="is__tab-u" />
      </view>
    </view>

    <view v-if="receipt" class="card is__receipt">
      <view class="row-between"><text class="t-bold">✓ {{ receipt.actionLabel }}</text><text>第{{ receipt.version }}版</text></view>
      <text>成绩 #{{ receipt.id }} · {{ receipt.statusLabel }}</text>
      <text>{{ receipt.nextStep }}</text>
    </view>

    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad is__page" v-if="tab === 'list'">
        <view class="card is__batch" v-if="batches.length">
          <view class="is__batch-copy">
            <text class="is__eyebrow">当前成绩批次</text>
            <text class="is__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          </view>
          <picker class="mobile-picker is__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="submitting" @change="onBatch">
            <view class="is__pick-val">切换批次 <text class="is__arrow">▾</text></view>
          </picker>
        </view>

        <button v-if="batches.length && list?.length" class="mobile-control btn btn-ghost" :aria-expanded="queueSummaryOpen" @click="queueSummaryOpen=!queueSummaryOpen">{{ queueSummaryOpen ? '收起成绩状态统计' : '查看成绩状态统计' }}</button>
        <view v-if="batches.length && list?.length && queueSummaryOpen" class="card is__summary">
          <view class="is__summary-main">
            <text class="is__summary-label">本批次已核算</text>
            <view class="is__summary-value"><text>{{ list.length }}</text><text>人</text></view>
            <text class="is__summary-note">{{ summaryConclusion }}</text>
          </view>
          <view class="is__summary-metrics">
            <view class="is__metric is-danger"><text>{{ incompleteCount }}</text><text>存在缺项</text></view>
            <view class="is__metric is-warning"><text>{{ pendingReviewCount }}</text><text>待学校复核</text></view>
            <view class="is__metric is-success"><text>{{ completedCount }}</text><text>已发布/归档</text></view>
          </view>
        </view>

        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可查看的实习批次。" />
        <MobileGlobalState v-else-if="!list || !list.length" state="empty" title="当前批次尚未核算成绩"
          description="进入“核算成绩”选择学生办理。" />

        <view class="stack" v-else>
          <view v-for="s in list" :key="s.id" class="card is">
            <view class="row-between is__head">
              <view class="flex-1 is__identity">
                <text class="t-md t-bold">{{ s.studentName || '—' }}</text>
                <text class="is__sub">{{ s.studentNo || '' }}</text>
              </view>
              <MobileStatusTag :label="s.statusLabel" :type="statusTone(s)" />
            </view>

            <view class="is__score-overview">
              <view class="is__total-block">
                <text class="is__total-value">{{ s.totalScore != null ? s.totalScore : '—' }}</text>
                <text class="is__total-label">加权总分</text>
              </view>
              <view class="is__score-grid">
                <view><text>打卡</text><text>{{ scoreText(s.checkinScore) }}</text></view>
                <view><text>周报</text><text>{{ scoreText(s.weeklyScore) }}</text></view>
                <view><text>月报总结</text><text>{{ scoreText(s.monthlyScore) }}</text></view>
                <view><text>企业评价</text><text>{{ s.enterpriseScore != null ? s.enterpriseScore : '待审核' }}</text></view>
                <view><text>学校评价</text><text>{{ scoreText(s.schoolScore) }}</text></view>
              </view>
            </view>

            <view v-if="s.incomplete" class="is__issue">
              <text class="is__issue-title">成绩存在缺项</text>
              <text class="is__issue-text">{{ s.incompleteReason || '请检查各评分来源' }}</text>
            </view>
            <view v-else-if="s.status === 'PENDING_REVIEW'" class="is__pending-box">
              <text class="is__pending-title">已提交学校复核</text>
              <text class="is__pending-text">教师端不能直接发布，请等待学校管理端完成复核。</text>
            </view>
            <view v-else-if="s.status === 'PENDING_PUBLISH'" class="is__pending-box">
              <text class="is__pending-title">复核通过，等待发布</text>
              <text class="is__pending-text">学校管理员发布后学生端才会看到正式成绩。</text>
            </view>

            <view class="is__sources">
              <text :class="{ ok: s.sourceReadiness?.enterpriseEvaluation }">企业评价 · {{ s.sourceReadiness?.enterpriseEvaluation ? '已齐备' : '待补齐' }}</text>
              <text :class="{ ok: s.sourceReadiness?.studentSelfEvaluation }">学生自评 · {{ s.sourceReadiness?.studentSelfEvaluation ? '已齐备' : '待补齐' }}</text>
              <text :class="{ ok: s.sourceReadiness?.advisorEvaluation }">导师评价 · {{ s.sourceReadiness?.advisorEvaluation ? '已齐备' : '待补齐' }}</text>
            </view>

            <view class="is__next" :class="{ 'is-danger': s.incomplete }">
              <text class="is__next-label">{{ ['PUBLISHED','ARCHIVED'].includes(s.status) ? '查看权限' : '下一步' }}</text>
              <text class="is__next-text">{{ nextStepText(s) }}</text>
            </view>
          </view>
        </view>
      </view>

      <view class="page-pad is__page" v-if="tab === 'compute' && canCompute">
        <view class="card is__batch" v-if="batches.length">
          <view class="is__batch-copy">
            <text class="is__eyebrow">当前核算批次</text>
            <text class="is__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          </view>
          <picker class="mobile-picker is__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="submitting" @change="onBatch">
            <view class="is__pick-val">切换批次 <text class="is__arrow">▾</text></view>
          </picker>
        </view>

        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可核算的实习批次。" />
        <MobileInlineAlert v-else-if="!canReadStudents" type="warning" description="当前身份没有学生名单查看权限，不能选择或核算学生成绩。" />
        <MobileInlineAlert v-else-if="studentError" type="warning" :description="studentError" />
        <text v-else-if="studentsLoading">正在读取学生名单…</text>
        <MobileGlobalState v-else-if="!students.length" state="empty" title="暂无可核算学生"
          description="当前批次仅可为本人指导的实习学生核算成绩。" />
        <button v-if="studentError && studentState !== 'forbidden' && canReadStudents" class="mobile-control btn btn-ghost" :disabled="studentsLoading" @click="loadStudents(studentAppendFailed)">重试读取学生名单</button>
        <button v-else-if="studentHasMore && canReadStudents" class="mobile-control btn btn-ghost" :disabled="studentsLoading || submitting" @click="loadMoreStudents">{{ studentsLoading ? '正在读取…' : '继续加载学生' }}</button>

        <template v-if="students.length && canReadStudents">
          <view class="card is__selected">
            <view class="is__selected-copy">
              <text class="is__selected-label">当前核算学生</text>
              <text class="is__selected-name">{{ selectedStudent?.name || '请选择学生' }}</text>
              <text class="is__selected-meta">{{ selectedStudent?.studentNo || '—' }} · {{ selectedStudent?.enterpriseName || '企业待落实' }}</text>
            </view>
            <MobileStatusTag v-if="selectedExisting" :label="selectedExisting.statusLabel || '状态待核对'" :type="statusTone(selectedExisting)" />
          </view>

          <view class="card is__form-section">
            <view class="is__section-head">
              <text class="is__step">1</text>
              <view><text class="is__section-title">选择学生</text><text class="is__section-hint">查看该学生的已有成绩。</text></view>
            </view>
            <view class="is__row">
              <text class="is__label">实习学生 <text class="is__required">*</text></text>
              <picker class="mobile-picker is__picker" mode="selector" :disabled="studentsLoading || submitting || !canReadStudents" :range="studentLabels" :value="studentIndex" @change="onStudent">
                <view class="is__field-value">{{ studentLabels[studentIndex] || '请选择' }}<text class="is__arrow">▾</text></view>
              </picker>
            </view>
            <text class="is__sub">已加载 {{ students.length }} 名可选学生</text>
          </view>

          <view class="card is__form-section">
            <view class="is__section-head">
              <text class="is__step">2</text>
              <view><text class="is__section-title">核对评分资料</text></view>
            </view>
            <view class="is__truth-list">
              <text>请核对打卡、报告和已审核的企业评价。</text>
              <text>学校评价还需学生自评、岗位反馈和导师意见齐全。</text>
            </view>
          </view>

          <view class="card is__source-note">
            <text class="is__source-title">学校复核后发布</text>
            <text class="is__source-text">成绩按过程记录核算。资料有变化时需重新核算；调分需在学校管理端提交依据并复核。</text>
          </view>
        </template>

        <MobileSafeAreaBar v-if="students.length && canCompute && canReadStudents">
          <button class="mobile-control btn btn-primary flex-1" :disabled="submitting || studentsLoading || studentState !== 'ready'" @click="submit">{{ submitting ? '核算中…' : (selectedExisting ? '按当前版本重新核算' : '提交核算') }}</button>
        </MobileSafeAreaBar>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { teacherInternshipMyStudents, teacherInternshipScores } from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

const submitLock = createSubmitLock(1500)
export default {
  data() {
    return { requestedBatchId: '', queueSummaryOpen:false,
      tab: 'list', list: null, state: 'loading', error: '',
      students: [], studentIndex: 0,
      batches: [], batchId: '', batchIndex: 0,
      page: 1, hasMore: false, loadingMore: false,
      submitting: false, receipt: null,
      sequence: 0, hidden: false, generation: currentSessionGeneration(), studentPage: 0, studentHasMore: false, studentTotal: 0, studentsLoading: false, studentState: 'idle', studentError: '', studentSequence: 0, studentScope: '', studentAppendFailed: false
    }
  },
  onLoad(query={}) { this.requestedBatchId=String(query.batchId||'');this.load() },
  onShow() { if (this.hidden || this.generation !== currentSessionGeneration()) { this.hidden = false; this.load() } },
  onHide() { this.hidden = true; this.sequence++; this.studentSequence++; this.studentsLoading = false; this.loadingMore = false; this.submitting = false },
  onUnload() { this.hidden = true; this.sequence++; this.studentSequence++ },
  onReachBottom() { if (this.tab === 'list') this.loadMore() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    context() { return useInternshipContextStore() },
    canReadStudents() { return this.context.can('internship.student.view') },
    studentLabels() { return this.students.map((s) => `${s.name}（${s.studentNo}）· ${s.enterpriseName || '未落实企业'}`) },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.studentCount}人`) },
    canCompute() { return useInternshipContextStore().can('internship.score.manage') },
    incompleteCount() { return (this.list || []).filter((item) => item.incomplete).length },
    pendingReviewCount() { return (this.list || []).filter((item) => item.status === 'PENDING_REVIEW').length },
    completedCount() { return (this.list || []).filter((item) => ['PUBLISHED', 'ARCHIVED'].includes(item.status)).length },
    selectedStudent() { return this.students[this.studentIndex] || null },
    selectedExisting() { return this.findExisting(this.selectedStudent) },
    summaryConclusion() {
      if (!this.list?.length) return '当前批次尚未核算成绩。'
      if (this.incompleteCount) return `优先处理 ${this.incompleteCount} 名学生的成绩缺项。`
      if (this.pendingReviewCount) return `${this.pendingReviewCount} 份成绩等待学校复核。`
      return '当前已核算成绩没有明显缺项。'
    }
  },
  methods: {
    readCurrent(sequence, generation, batchId = '') { return !this.hidden && sequence === this.sequence && generation === currentSessionGeneration() && (!batchId || (String(batchId) === String(this.batchId) && String(batchId) === String(this.context.selectedBatchId || ''))) },
    resetStudents() { this.studentSequence++; this.students = []; this.studentIndex = 0; this.studentPage = 0; this.studentHasMore = false; this.studentTotal = 0; this.studentsLoading = false; this.studentState = 'idle'; this.studentError = ''; this.studentScope = '' },
    scoreText(value) { return value != null ? value : '—' },
    statusTone(s) { return ['PUBLISHED', 'ARCHIVED'].includes(s.status) ? 'success' : s.incomplete ? 'danger' : 'warning' },
    nextStepText(s) {
      if (s.incomplete) return this.canCompute ? '进入“核算成绩”，选择该学生补齐缺项后重新核算。' : '联系有核算权限的教师补齐缺项。'
      if (s.status === 'PENDING_REVIEW') return '等待学校管理端复核并发布成绩。'
      if (s.status === 'PENDING_PUBLISH') return '独立复核已完成，等待学校管理员发布。'
      if (['PUBLISHED', 'ARCHIVED'].includes(s.status)) return '仅供查阅。'
      return this.canCompute ? '如评分来源有更新，可按当前版本重新核算。' : '等待学校复核或后续状态更新。'
    },
    async load(done) {
      const sequence = ++this.sequence, generation = currentSessionGeneration()
      this.studentSequence++; this.studentsLoading = false
      if (this.generation !== generation) { this.list = []; this.resetStudents(); this.receipt = null; this.tab = 'list' }
      this.generation = generation; this.state = 'loading'; this.error = ''
      this.page = 1
      this.hasMore = false
      try {
        const context = useInternshipContextStore()
        context.restore()
        await context.load(true)
        if (!this.readCurrent(sequence, generation)) return
        if(this.requestedBatchId){if(!context.selectBatch(this.requestedBatchId))throw {httpStatus:403,message:'当前批次不在授权范围'};this.requestedBatchId=''}
        const nextBatch = String(context.selectedBatchId || '')
        if (this.batchId !== nextBatch) { this.resetStudents(); this.receipt = null }
        this.batches = context.batches || []
        this.batchId = nextBatch
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        await this.loadScores()
        if (!this.readCurrent(sequence, generation, nextBatch)) return
        this.state = 'ready'
        if (this.tab === 'compute' && this.canCompute) await this.loadStudents()
      } catch (e) {
        if (this.readCurrent(sequence, generation)) { const error = normalizeError(e); this.state = error.pageState || 'error'; this.error = error.text }
      } finally { if (done) done() }
    },
    async loadScores() {
      if (!this.batchId) { this.list = []; return }
      const sequence = this.sequence, generation = this.generation, batchId = this.batchId
      const data = await teacherInternshipScores(batchId, 1, 20)
      if (!this.readCurrent(sequence, generation, batchId)) return
      this.list = (data && (data.items || data.list)) || []
      this.hasMore = !!data?.hasMore
    },
    async loadMore() {
      if (!this.batchId || !this.hasMore || this.loadingMore || this.state !== 'ready') return
      const selectedBatch = this.batchId, sequence = this.sequence, generation = this.generation
      this.loadingMore = true
      try {
        const nextPage = this.page + 1
        const data = await teacherInternshipScores(selectedBatch, nextPage, 20)
        if (!this.readCurrent(sequence, generation, selectedBatch)) return
        this.list = [...(this.list || []), ...(data?.items || [])]
        this.page = nextPage
        this.hasMore = !!data?.hasMore
      } finally { if (sequence === this.sequence) this.loadingMore = false }
    },
    async onComputeTab() {
      if (!this.canCompute || this.hidden || this.submitting || this.generation !== currentSessionGeneration()) return
      this.tab = 'compute'
      if (this.studentState !== 'ready') await this.loadStudents()
    },
    async onBatch(e) {
      if (this.submitting) return
      const batch = this.batches[Number(e.detail.value)]
      if (!batch || !this.context.selectBatch(batch.id)) return
      return this.load()
    },
    onStudent(e) {
      if (!this.canCompute || !this.canReadStudents || this.studentsLoading || this.submitting) return
      this.studentIndex = Number(e.detail.value)
    },
    async loadStudents(append = false) {
      if (this.hidden || (append && (this.studentsLoading || !this.studentHasMore))) return
      if (!this.canCompute || !this.canReadStudents) { this.resetStudents(); this.studentState = 'forbidden'; this.studentError = '当前身份没有学生名单查看或成绩核算权限'; return }
      const batchId = String(this.batchId || ''), generation = currentSessionGeneration(), scope = `${generation}:${batchId}`
      if (!batchId || batchId !== String(this.context.selectedBatchId || '')) { this.resetStudents(); return }
      if (scope !== this.studentScope) { this.resetStudents(); this.studentScope = scope; append = false }
      const sequence = ++this.studentSequence, nextPage = append ? this.studentPage + 1 : 1, selectedId = this.students[this.studentIndex]?.id
      const current = () => !this.hidden && sequence === this.studentSequence && generation === currentSessionGeneration() && batchId === String(this.batchId) && batchId === String(this.context.selectedBatchId || '')
      this.studentsLoading = true; this.studentError = ''; this.studentState = 'loading'
      try {
        const data = await teacherInternshipMyStudents(batchId, { page: nextPage, pageSize: 20 })
        if (!current()) return
        if (!this.canCompute || !this.canReadStudents) { this.resetStudents(); this.studentState = 'forbidden'; this.studentError = '当前身份没有学生名单查看或成绩核算权限'; return }
        this.students = [...new Map([...(append ? this.students : []), ...(data?.items || data?.list || [])].map(x => [String(x.id), x])).values()]
        this.studentPage = nextPage; this.studentTotal = Number(data?.total ?? this.students.length)
        this.studentHasMore = data?.hasMore ?? nextPage * 20 < this.studentTotal
        this.studentIndex = selectedId == null ? 0 : this.students.findIndex(x => String(x.id) === String(selectedId))
        this.studentState = 'ready'; this.studentAppendFailed = false
      } catch (e) { if (current()) { const error = normalizeError(e); this.studentError = error.text; this.studentState = error.pageState || 'error'; this.studentAppendFailed = append; if (['forbidden','unauthorized','noLicense'].includes(this.studentState)) { this.students = []; this.studentIndex = 0; this.studentHasMore = false } } }
      finally { if (sequence === this.studentSequence) this.studentsLoading = false }
    },
    loadMoreStudents() { return this.loadStudents(true) },
    findExisting(stu) {
      if (!stu) return null
      return (this.list || []).find((x) => String(x.internshipId || x.internId) === String(stu.id)) || null
    },
    submit() {
      if (this.submitting || this.state !== 'ready' || this.tab !== 'compute' || !this.canCompute || !this.canReadStudents || this.studentsLoading || this.studentState !== 'ready' || this.hidden || this.generation !== currentSessionGeneration() || String(this.batchId) !== String(this.context.selectedBatchId || '')) return
      const stu = this.students[this.studentIndex]
      if (!stu) { toast('请选择实习学生'); return }
      const existing = this.findExisting(stu)
      if (existing && ['PUBLISHED', 'ARCHIVED'].includes(existing.status)) {
        toast('该生成绩已发布或归档，不能在教师端直接重算'); return
      }
      this.submitting = true
      const body = { internshipId: stu.id, batchId: this.batchId }
      if (existing) body.expectedVersion = existing.version
      const sequence = this.sequence, generation = this.generation, batchId = this.batchId
      submitLock.run(() => teacherApi.computeInternshipScore(body)).then((result) => {
        if (!this.readCurrent(sequence, generation, batchId)) return
        uni.showToast({ title: result && result.incomplete ? `已保存，缺：${result.incompleteReason}` : `核算完成，总分 ${result.total}`, icon: 'none' })
        this.receipt = { actionLabel: '核算完成', id: result.id, version: result.version,
          statusLabel: result.incomplete ? '缺项待补齐' : '待复核',
          nextStep: result.incomplete ? (result.incompleteReason || '补齐来源后重算') : '等待授权管理员独立复核' }
        this.submitting = false; this.tab = 'list'; this.load()
      }).catch((e) => {
        if (!this.readCurrent(sequence, generation, batchId)) return
        if (e && e.code === 'LOCKED') return
        if (e && e.biz) toast(normalizeError(e).text)
        else toast('网络异常，提交未成功，请稍后重试')
      }).finally(() => { if (sequence === this.sequence) this.submitting = false })
    }
  }
}
</script>

<style scoped>
.is__receipt{display:flex;flex-direction:column;gap:5px;margin:var(--space-3) var(--page-padding-mobile) 0;padding:var(--space-3);border-color:var(--success-300,#86efac);background:var(--success-50,#f0fdf4);font-size:var(--font-size-xs);color:var(--text-secondary)}
.is__sources{display:flex;gap:6px;flex-wrap:wrap}.is__sources text{padding:3px 7px;border-radius:999px;background:var(--danger-50,#fef2f2);color:var(--danger-600);font-size:10px}.is__sources text.ok{background:var(--success-50,#ecfdf5);color:var(--success-700,#047857)}
.is__truth-list{display:flex;flex-direction:column;gap:8px;padding-top:var(--space-3)}.is__truth-list text{padding:9px 10px;border-radius:var(--radius-md);background:var(--gray-50);font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}
.is__tabs{display:flex;gap:var(--space-6);padding:var(--space-3) var(--page-padding-mobile) 0;background:var(--bg-card)}.is__tab{position:relative;font-size:var(--font-size-base);color:var(--text-tertiary);font-weight:var(--font-weight-medium);padding-bottom:var(--space-3)}.is__tab.is-on{color:var(--text-primary);font-weight:var(--font-weight-semibold)}.is__tab-u{position:absolute;left:50%;bottom:0;transform:translateX(-50%);width:22px;height:3px;border-radius:2px;background:var(--teacher-600)}.is__tab-badge{margin-left:4px;font-size:10px;color:#fff;background:var(--danger-500);padding:1px 5px;border-radius:var(--radius-full)}.is__page{display:flex;flex-direction:column;gap:var(--space-3);padding-bottom:calc(var(--safe-bottom) + 88px)}.is__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.is__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.is__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.is__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.is__picker{flex-shrink:0}.is__pick-val{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.is__arrow{margin-left:4px;color:var(--text-tertiary)}.is__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.is__summary-main{flex:1;min-width:0}.is__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.is__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.is__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.is__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.is__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.is__summary-metrics{width:52%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.is__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 3px;border-left:1px solid var(--border-light);text-align:center}.is__metric:first-child{border-left:0}.is__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.is__metric.is-danger text:first-child{color:var(--danger-600)}.is__metric.is-warning text:first-child{color:var(--warning-700)}.is__metric.is-success text:first-child{color:var(--success-700)}.is__metric text:last-child{font-size:10px;line-height:1.25;color:var(--text-tertiary)}.is{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.is__head{align-items:flex-start}.is__identity{min-width:0}.is__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px}.is__score-overview{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-2);background:var(--gray-50);border-radius:var(--radius-md)}.is__total-block{width:82px;flex-shrink:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:8px;border-right:1px solid var(--border-light)}.is__total-value{font-size:30px;line-height:1;font-weight:700;color:var(--teacher-700)}.is__total-label{margin-top:5px;font-size:10px;color:var(--text-tertiary)}.is__score-grid{flex:1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px 12px}.is__score-grid>view{display:flex;justify-content:space-between;gap:8px;min-width:0}.is__score-grid text:first-child{font-size:10px;color:var(--text-tertiary)}.is__score-grid text:last-child{font-size:var(--font-size-xs);font-weight:600;color:var(--text-primary);word-break:break-word}.is__issue,.is__pending-box{padding:var(--space-2) var(--space-3);border-radius:var(--radius-md)}.is__issue{border:1px solid var(--danger-200,#fecaca);background:var(--danger-50)}.is__pending-box{border:1px solid var(--warning-200,#fed7aa);background:var(--warning-50,#fff7ed)}.is__issue-title,.is__pending-title{display:block;font-size:var(--font-size-sm);font-weight:600}.is__issue-title{color:var(--danger-700)}.is__pending-title{color:var(--warning-800,#9a3412)}.is__issue-text,.is__pending-text{display:block;margin-top:4px;font-size:var(--font-size-xs);line-height:1.5}.is__issue-text{color:var(--danger-600)}.is__pending-text{color:var(--warning-700)}.is__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.is__next.is-danger{background:var(--warning-50,#fff7ed)}.is__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.is__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.is__selected{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3);background:var(--teacher-50,#eff6ff);border-color:var(--teacher-200,#bfdbfe)}.is__selected-copy{min-width:0}.is__selected-label{display:block;font-size:10px;color:var(--text-tertiary)}.is__selected-name{display:block;margin-top:3px;font-size:var(--font-size-md);font-weight:600;color:var(--text-primary)}.is__selected-meta{display:block;margin-top:3px;font-size:var(--font-size-xs);color:var(--text-secondary);word-break:break-word}.is__form-section{display:flex;flex-direction:column;padding:var(--space-3)}.is__section-head{display:flex;align-items:center;gap:10px;padding-bottom:var(--space-2);border-bottom:1px solid var(--border-light)}.is__step{display:flex;align-items:center;justify-content:center;width:26px;height:26px;flex-shrink:0;border-radius:50%;background:var(--teacher-600);color:#fff;font-size:var(--font-size-sm);font-weight:700}.is__section-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.is__section-hint{display:block;margin-top:2px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.is__row{display:flex;align-items:center;min-height:52px;border-bottom:1px solid var(--border-light);gap:var(--space-3)}.is__label{width:100px;flex-shrink:0;font-size:var(--font-size-sm);color:var(--text-secondary)}.is__required{color:var(--danger-600)}.is__field-value{min-width:0;font-size:var(--font-size-sm);color:var(--text-primary);text-align:right;word-break:break-word}.is__score-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding-top:var(--space-3)}.is__score-field{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:11px 12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50)}.is__score-name{display:block;font-size:var(--font-size-sm);color:var(--text-secondary)}.is__score-help{display:block;margin-top:2px;font-size:10px;color:var(--text-tertiary)}.is__score-field input{width:74px;text-align:right;font-size:var(--font-size-lg);color:var(--text-primary)}.is__source-note{padding:var(--space-3);border-color:var(--success-200,#bbf7d0);background:var(--success-50)}.is__source-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--success-800,#166534)}.is__source-text{display:block;margin-top:4px;font-size:var(--font-size-xs);line-height:1.5;color:var(--success-700)}@media(max-width:360px){.is__summary{flex-direction:column}.is__summary-metrics{width:100%}.is__score-overview{align-items:flex-start}.is__score-grid,.is__score-form{grid-template-columns:1fr}.is__batch{align-items:flex-start}}
.is__row{flex-direction:column;align-items:stretch;gap:8px;padding:10px 0}.is__row>.is__label{width:auto}.is__row>.is__picker{width:100%;min-width:0}.is__field-value{text-align:left;white-space:normal;overflow-wrap:anywhere;line-height:1.6}
</style>
<style scoped>
.is__tab{min-height:44px;display:flex;align-items:center;font-size:15px}.is__eyebrow,.is__summary-note,.is__source-text,.is__section-hint,.is__selected-meta{font-size:14px;line-height:1.6}.is__pick-val{min-height:44px;display:flex;align-items:center;font-size:14px}.is__batch-name{white-space:normal;overflow-wrap:anywhere}.is__section-title,.is__source-title{font-size:16px}.is__truth-list{font-size:14px;line-height:1.6}.is__form-section :deep(.uni-picker-container){font-size:14px}
</style>
