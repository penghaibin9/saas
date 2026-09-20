<template>
  <view class="page-wrap">
    <MobileNavBar title="我的岗位实习" subtitle="查看安排、资格与当前事项" show-back fallback-url="/pages/student/me/index" />
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="needSelect" class="page-pad stack">
        <MobileInlineAlert type="warning" title="请选择要办理的实习批次"
          description="你有多条进行中的实习记录。系统不会替你猜测；选择后，首页、合规状态和安全教育都使用同一批次。" />
        <view class="card in__selector">
          <text class="t-md t-bold">进行中的实习批次</text>
          <view v-for="candidate in candidates" :key="candidate.recordId" class="in__candidate"
            :class="{ 'is-on': String(candidate.batchId) === String(selectedBatchId) }"
            @click="selectCandidate(candidate)">
            <view class="flex-1">
              <text class="t-md t-bold">{{ candidate.batchName || `批次 ${candidate.batchId}` }}</text>
              <text class="in__candidate-sub">实习状态 {{ candidateStatusLabel(candidate.status) }}</text>
            </view>
            <MobileStatusTag :label="String(candidate.batchId) === String(selectedBatchId) ? '已选择' : '选择'"
              :type="String(candidate.batchId) === String(selectedBatchId) ? 'success' : 'info'" />
          </view>
        </view>
      </view>

      <template v-else-if="i && !i.hasBatch">
        <view class="page-pad"><MobileGlobalState state="empty" title="当前暂无实习任务" :description="i.message || '进入实习阶段后，这里会显示岗位、协议、打卡与周报。'" /></view>
      </template>

      <view class="page-pad stack" v-else-if="i">
        <view v-if="candidates.length > 1" class="card in__batch-switch">
          <text class="in__batch-switch-label">当前实习批次</text>
          <picker mode="selector" :range="candidateLabels" :value="candidateIndex" @change="onCandidatePicker">
            <view class="in__batch-switch-value">{{ currentCandidateLabel }} <text>▾</text></view>
          </picker>
        </view>

        <view class="in__qualification card">
          <view class="in__qualification-head"><text class="in__qualification-label">学校资格认定</text><MobileStatusTag :label="qualification.label" :type="qualification.status === 'QUALIFIED' ? 'success' : qualification.status === 'UNQUALIFIED' ? 'danger' : 'warning'" /></view>
          <text class="in__qualification-title">{{ qualification.status === 'QUALIFIED' ? '实习资格已通过' : qualification.status === 'UNQUALIFIED' ? '请查看认定说明' : '关注本批次资格认定' }}</text>
          <text class="in__qualification-reason">{{ qualification.reason || qualificationHint }}</text>
          <text v-if="qualification.reviewedAt" class="in__qualification-time">更新于 {{ formatDateTime(qualification.reviewedAt) }}</text>
          <view class="in__qualification-footer"><text>指导教师 · {{ i.schoolMentor }}</text><button class="in__refresh" size="mini" @click="load">刷新结果</button></view>
        </view>
        <view class="in__hero card">
          <text class="in__hero-batch">{{ compliance.batchName || i.batch }}</text>
          <text class="in__hero-post">{{ i.post || '岗位待落实' }}</text>
          <text class="in__hero-company">{{ i.company || '企业待落实' }}</text>
          <view class="in__hero-mentors">
            <text class="in__mentor">校内导师 {{ i.schoolMentor }}</text>
            <text class="in__mentor">企业导师 {{ i.companyMentor }}</text>
          </view>
        </view>

        <MobileInlineAlert v-if="i.historyMode" type="info" title="历史实习记录"
          description="当前批次已结束，仅可查看历史状态，不可继续打卡、周报或发起业务申请。" />
        <MobileInlineAlert v-if="complianceError" type="warning" title="合规状态暂不可用" :description="complianceError" />
        <MobileInlineAlert v-else-if="compliance.currentTask" :type="compliance.passed ? 'success' : 'warning'"
          :title="compliance.passed ? '上岗合规已通过' : `当前待办：${compliance.currentTask.label}`"
          :description="compliance.currentTask.reason || '请按学校要求完成当前任务'" />
        <view v-if="canShowDailyWork" class="in__today">
          <view class="in__today-card" @click="openSub('/pages/student-internship/checkin/index')">
            <text class="in__today-icon">📍</text><text class="in__today-title">今日打卡</text>
            <text class="in__today-status" :class="{ 'is-warn': !i.checkin.done }">{{ i.checkin.done ? '已打卡' : '未打卡' }}</text>
            <text class="in__today-btn">{{ i.checkin.done ? '已完成' : '去打卡' }}</text>
          </view>
          <view class="in__today-card" @click="weekly">
            <text class="in__today-icon">✎</text><text class="in__today-title">{{ i.weekly.week }}周报</text>
            <text class="in__today-status" :class="{ 'is-warn': !i.weekly.submitted }">{{ i.weekly.submitted ? '已提交' : '未提交' }}</text>
            <text class="in__today-btn">写周报</text>
          </view>
        </view>
        <MobileInlineAlert v-if="canShowDailyWork" type="info" :description="i.checkin.note" />
        <MobileInlineAlert v-if="canShowDailyWork && i.weekly.lastFeedback" type="warning" title="导师上周反馈" :description="i.weekly.lastFeedback" />

        <template v-if="canShowDailyWork"><view class="section-head"><text class="section-head__title">实习状态</text></view>
        <view class="card"><view class="in__status-grid">
          <view class="in__status-item"><text class="in__status-k">协议</text><MobileStatusTag :status="i.status.agreement" /></view>
          <view class="in__status-item"><text class="in__status-k">保险</text><MobileStatusTag :status="i.status.insurance" /></view>
          <view class="in__status-item"><text class="in__status-k">到岗</text><MobileStatusTag :status="i.status.onboard" /></view>
          <view class="in__status-item"><text class="in__status-k">今日打卡</text><MobileStatusTag :status="i.status.todayCheckin" /></view>
          <view class="in__status-item"><text class="in__status-k">本周周报</text><MobileStatusTag :status="i.status.weekly" /></view>
          <view class="in__status-item"><text class="in__status-k">请假</text><MobileStatusTag :status="i.status.leave" /></view>
        </view></view></template>

        <view class="section-head"><text class="section-head__title">上岗合规</text><text class="section-head__more">{{ completenessText }}</text></view>
        <view class="card">
          <view v-for="item in visibleComplianceItems" :key="item.code" class="in__compliance-row" :class="{ 'is-clickable': !!item.route }" @click="item.route && openSub(item.route)">
            <view class="flex-1"><text class="in__compliance-label">{{ item.label }}</text><text v-if="item.reason" class="in__compliance-reason">{{ item.reason }}</text></view>
            <MobileStatusTag :label="item.statusLabel" :type="complianceTone(item.status)" />
          </view>
          <MobileInlineAlert v-if="blockingReason" type="warning" title="上岗阻断原因" :description="blockingReason" />
        </view>

        <template v-if="canShowDailyWork"><view class="section-head"><text class="section-head__title">实习流程</text></view>
        <view class="card"><MobileTimeline :nodes="compliance.timeline && compliance.timeline.length ? compliance.timeline : i.timeline" /></view></template>

        <view class="section-head"><text class="section-head__title">阶段服务</text><text class="section-head__more">按当前实习状态整理</text></view>
        <view class="in__service-groups">
          <view v-for="group in serviceGroups" :key="group.key" class="in__service-group">
            <view class="in__service-head">
              <view><text class="in__service-title">{{ group.label }}</text><text class="in__service-hint">{{ group.hint }}</text></view>
              <text class="in__service-count">{{ group.items.length }} 项</text>
            </view>
            <view class="in__nav card">
              <view v-for="n in group.items" :key="n.path" class="in__nav-item" @click="openSub(n.path)"><text class="in__nav-icon">{{ n.icon }}</text><text class="in__nav-label">{{ n.label }}</text></view>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="primaryAction">
      <button class="btn btn-primary flex-1" :disabled="primaryAction.done" @click="runPrimaryAction">{{ primaryAction.label }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { formatDateTime } from '@/utils/format'
import { studentApi } from '@/services/studentApi'
import { toast, go } from '@/utils/nav'

const STORAGE_KEY = 'gx_student_internship_batch_v1'
const INTERNSHIP_RECORD_STATUS_LABELS = {
  DRAFT: '待完善', APPLIED: '待审核', APPROVED: '待确认', ONBOARD: '实习中',
  ASSESSING: '考核中', ENDED: '已结束', ARCHIVED: '已归档', TERMINATED: '已终止'
}

export default {
  data() {
    return {
      i: null, state: 'loading', loadSequence: 0, selectedBatchId: '', candidates: [],
      compliance: { items: [], blockers: [], warnings: [], timeline: [] }, complianceError: '',
      navItems: [
        { label: '知情确认', path: '/pages/student-internship/consent/index', icon: '✅', stages: ['onboard'] },
        { label: '安全教育', path: '/pages/student-internship/safety/index', icon: '⛑️', stages: ['onboard'] },
        { label: '实习意向', path: '/pages/student-internship/intention/index', icon: '🎯', stages: ['selection'] },
        { label: '正式申请', path: '/pages/student-internship/application/index', icon: '📋', stages: ['selection'] },
        { label: '实习选岗', path: '/pages/student-internship/enterprises/index', icon: '🏢', stages: ['selection'] },
        { label: '三方协议', path: '/pages/student-internship/agreement/index', icon: '📄', stages: ['onboard'] },
        { label: '实习保险', path: '/pages/student-internship/insurance/index', icon: '🛡️', stages: ['onboard'] },
        { label: '实习计划', path: '/pages/student-internship/plan/index', icon: '🗂️', stages: ['onboard', 'process'] },
        { label: '实习请假', path: '/pages/student-internship/leave/index', icon: '🗓️', today: true },
        { label: '补卡申请', path: '/pages/student-internship/makeup/index', icon: '📍', today: true },
        { label: '日报', path: '/pages/student-internship/process-report/index?type=daily', icon: '📝', today: true },
        { label: '月报', path: '/pages/student-internship/process-report/index?type=monthly', icon: '📑', stages: ['process'] },
        { label: '实习总结', path: '/pages/student-internship/process-report/index?type=summary', icon: '📒', stages: ['result'] },
        { label: '调岗退岗', path: '/pages/student-internship/change/index', icon: '🔄', stages: ['process'] },
        { label: '实习求助', path: '/pages/student-internship/help/index', icon: '🆘', today: true },
        { label: '鉴定与成绩', path: '/pages/student-internship/self-eval/index', icon: '⭐', stages: ['result'] },
        { label: '就业衔接', path: '/pages/student/employment/index', icon: '🎯', stages: ['result'] }
      ]
    }
  },
  computed: {
    qualification() { return this.i?.eligibilityReview || { status: 'UNKNOWN', label: '暂未取得结果', reason: '' } },
    qualificationHint() { return ({ QUALIFIED: '学校已完成本批次实习资格认定。', PENDING: '学校正在核对实习资格。需要补充材料时，请联系校内指导教师。', UNQUALIFIED: '本次认定未通过。请联系指导教师了解原因及后续安排。' })[this.qualification.status] || '请刷新认定结果，或联系指导教师核对。' },
    canShowDailyWork() { return this.i?.hasBatch && !this.i.historyMode && this.i.statusText === 'ONBOARD' },
    primaryAction() {
      const next = this.compliance?.nextAction
      if (!this.i?.historyMode && next?.route) {
        return { label: next.label || '继续办理', route: next.route, kind: 'route', done: false }
      }
      if (!this.canShowDailyWork) return null
      if (!this.i?.checkin?.done) {
        return { label: '立即打卡', route: '/pages/student-internship/checkin/index', kind: 'route', done: false }
      }
      if (!this.i?.weekly?.submitted) {
        return { label: `填写${this.i?.weekly?.week || '本周'}周报`, kind: 'weekly', done: false }
      }
      return { label: '今天的实习任务已完成', kind: 'done', done: true }
    },
    needSelect() { return !!(this.i?.needSelect || this.compliance?.needSelect) && !this.selectedBatchId },
    candidateLabels() { return this.candidates.map((x) => `${x.batchName || `批次 ${x.batchId}`} · ${this.candidateStatusLabel(x.status)}`) },
    candidateIndex() { return Math.max(0, this.candidates.findIndex((x) => String(x.batchId) === String(this.selectedBatchId))) },
    currentCandidateLabel() { return this.candidateLabels[this.candidateIndex] || this.i?.batch || '请选择批次' },
    visibleComplianceItems() { return (this.compliance.items || []).filter((x) => x.required || x.status !== 'NOT_APPLICABLE') },
    blockingReason() { return (this.compliance.blockers || []).map((x) => `${x.label}：${x.reason || x.statusLabel}`).join('；') },
    completenessText() { const c = this.compliance.completeness; return c ? `${c.done}/${c.required}` : '' },
    currentStage() {
      if (this.i?.historyMode || ['ASSESSING', 'ARCHIVED', 'ENDED'].includes(this.i?.statusText)) return 'result'
      if (!this.i?.company || !this.i?.post) return 'selection'
      if (this.i?.statusText === 'ONBOARD') return 'process'
      return 'onboard'
    },
    serviceGroups() {
      const actionRoute = String(this.compliance?.nextAction?.route || '').split('?')[0]
      const required = actionRoute ? this.navItems.filter((item) => item.path.split('?')[0] === actionRoute) : []
      const requiredPaths = new Set(required.map((item) => item.path))
      const today = this.navItems.filter((item) => item.today && (this.canShowDailyWork || item.path.includes('/help/')) && !requiredPaths.has(item.path))
      const todayPaths = new Set(today.map((item) => item.path))
      const stage = this.navItems.filter((item) => (item.stages || []).includes(this.currentStage) && !requiredPaths.has(item.path) && !todayPaths.has(item.path))
      const stagePaths = new Set(stage.map((item) => item.path))
      const more = this.navItems.filter((item) => !requiredPaths.has(item.path) && !todayPaths.has(item.path) && !stagePaths.has(item.path))
      return [
        { key: 'required', label: '当前必须做', hint: '来自学校合规任务', items: required },
        { key: 'today', label: this.canShowDailyWork ? '今天' : '需要帮助', hint: this.canShowDailyWork ? '高频记录与即时求助' : '遇到问题及时联系学校', items: today },
        { key: 'stage', label: '当前阶段服务', hint: '与你现在的实习阶段相关', items: stage },
        { key: 'more', label: '更多服务', hint: '查看其他实习事项', items: more }
      ].filter((group) => group.items.length)
    }
  },
  onLoad(options = {}) {
    const requestedBatchId = String(options.batchId || '').trim()
    if (/^\d+$/.test(requestedBatchId)) {
      this.selectedBatchId = requestedBatchId
      this.persistBatch()
    } else {
      this.restoreBatch()
    }
    this.load()
  },
  onShow() { if (this.i) this.load() },
  onUnload() { this.loadSequence++ },
  methods: {
    formatDateTime,
    toast, go,
    candidateStatusLabel(status) { return INTERNSHIP_RECORD_STATUS_LABELS[String(status || '').toUpperCase()] || '状态待确认' },
    restoreBatch() { try { this.selectedBatchId = String(uni.getStorageSync(STORAGE_KEY) || '') } catch (e) {} },
    persistBatch() { try { if (this.selectedBatchId) uni.setStorageSync(STORAGE_KEY, this.selectedBatchId); else uni.removeStorageSync(STORAGE_KEY) } catch (e) {} },
    withBatch(path) { if (!this.selectedBatchId) return path; return `${path}${path.includes('?') ? '&' : '?'}batchId=${encodeURIComponent(this.selectedBatchId)}` },
    openSub(path) { go(this.withBatch(path)) },
    selectCandidate(candidate) { this.selectedBatchId = String(candidate?.batchId || ''); this.persistBatch(); this.load() },
    onCandidatePicker(e) { this.selectCandidate(this.candidates[Number(e.detail.value)]) },
    async load() {
      const seq = ++this.loadSequence
      const batchId = this.selectedBatchId
      this.state = 'loading'; this.complianceError = ''
      const [dashboard, compliance] = await Promise.allSettled([
        studentApi.getInternship(batchId), studentApi.getInternshipCompliance('ONBOARD', batchId)
      ])
      if (seq !== this.loadSequence) return
      if (dashboard.status !== 'fulfilled') { this.state = 'error'; return }
      this.i = dashboard.value
      this.compliance = compliance.status === 'fulfilled' ? compliance.value : { items: [], blockers: [], warnings: [], timeline: [] }
      this.complianceError = compliance.status === 'rejected' ? (compliance.reason?.message || '合规状态暂不可用，请稍后重试') : ''
      this.candidates = this.i?.candidates?.length ? this.i.candidates : (this.compliance?.candidates || [])
      // 首次进入没有本地选择时，以刚从服务端回读的实习记录批次为准。候选数组可同时
      // 包含已归档历史批次，不能因 picker 默认第 0 项而把“当前批次”显示成历史事实。
      const serverBatchId = String(this.i?.batchId || '')
      if (!this.selectedBatchId && serverBatchId && this.candidates.some((x) => String(x.batchId) === serverBatchId)) {
        this.selectedBatchId = serverBatchId
        this.persistBatch()
      }
      this.state = 'ready'
    },
    complianceTone(status) { if (['VALID', 'EXEMPTED', 'NOT_APPLICABLE'].includes(status)) return 'success'; if (['REJECTED', 'CONFIG_ERROR'].includes(status)) return 'danger'; return 'warning' },
    runPrimaryAction() {
      const action = this.primaryAction
      if (!action || action.done) return
      if (action.kind === 'weekly') return this.weekly()
      if (action.route) return this.openSub(action.route)
    },
    weekly() {
      if (this.i?.historyMode) return toast('历史实习记录仅可查看')
      if (this.i?.weekly?.submitted) return toast('本周周报已提交')
      const q = 'week=' + encodeURIComponent(this.i.weekly.week) + '&company=' + encodeURIComponent(this.i.company) + '&post=' + encodeURIComponent(this.i.post)
      go(this.withBatch('/pages/student/weekly-report/index?' + q))
    }
  }
}
</script>

<style scoped>
.in__selector { display: flex; flex-direction: column; gap: var(--space-3); }
.in__candidate { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md); }
.in__candidate.is-on { border-color: var(--brand-primary); background: var(--brand-50); }
.in__candidate-sub { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.in__batch-switch { display: flex; align-items: center; justify-content: space-between; }
.in__batch-switch-label { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.in__batch-switch-value { color: var(--brand-primary); font-weight: var(--font-weight-medium); }
.in__hero-batch { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.in__hero-post { display: block; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); color: var(--text-primary); margin-top: 4px; }
.in__hero-company { display: block; font-size: var(--font-size-base); color: var(--text-secondary); margin-top: 2px; }
.in__hero-mentors { display: flex; gap: var(--space-3); margin-top: var(--space-3); }
.in__mentor { font-size: var(--font-size-xs); color: var(--text-secondary); background: var(--gray-100); padding: 3px 8px; border-radius: var(--radius-full); }
.in__today { display: flex; gap: var(--card-gap-mobile); }
.in__today-card { flex: 1; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--card-padding-mobile); box-shadow: var(--shadow-card); display: flex; flex-direction: column; gap: 4px; }
.in__today-icon { font-size: 24px; }.in__today-title { font-size: var(--font-size-md); font-weight: var(--font-weight-medium); color: var(--text-primary); }.in__today-status { font-size: var(--font-size-sm); color: var(--success-600); }.in__today-status.is-warn { color: var(--warning-600); }.in__today-btn { margin-top: var(--space-2); font-size: var(--font-size-sm); color: var(--brand-primary); }
.in__status-grid { display: flex; flex-wrap: wrap; }.in__status-item { width: 33.33%; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: var(--space-2) 0; }.in__status-k { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.in__compliance-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--border-light); }.in__compliance-row:last-child { border-bottom: 0; }.in__compliance-row.is-clickable { cursor: pointer; }.in__compliance-label { display: block; color: var(--text-primary); font-size: var(--font-size-sm); }.in__compliance-reason { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.5; }
.in__service-groups { display: flex; flex-direction: column; gap: var(--space-3); }
.in__service-head { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-2); padding: 0 2px; }
.in__service-title { display: block; color: var(--text-primary); font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); }
.in__service-hint { display: block; margin-top: 2px; color: var(--text-tertiary); font-size: 10px; }
.in__service-count { flex-shrink: 0; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.in__service-group:first-child .in__nav { border-color: var(--warning-300, #fcd34d); background: var(--warning-50, #fffbeb); }
.in__nav { display: flex; flex-wrap: wrap; }.in__nav-item { width: 25%; min-height: var(--touch-target-min); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; padding: var(--space-3) 0; }.in__nav-icon { font-size: 26px; line-height: 1; }.in__nav-label { font-size: var(--font-size-xs); color: var(--text-secondary); }

.in__qualification{border-top:3px solid var(--brand-primary);padding:var(--card-padding-mobile)}
.in__qualification-head{display:flex;justify-content:space-between;align-items:center;gap:12px}.in__qualification-label{font-size:12px;color:var(--text-tertiary)}
.in__qualification-title{display:block;font-size:20px;font-weight:600;line-height:1.5;margin:18px 0 10px;color:var(--text-primary)}
.in__qualification-reason{display:block;font-size:14px;line-height:1.8;color:var(--text-secondary);white-space:pre-wrap;word-break:break-word}
.in__qualification-time{display:block;font-size:11px;color:var(--text-tertiary);margin-top:14px}.in__qualification-footer{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:20px;padding-top:14px;border-top:1px solid var(--border-light);font-size:12px;color:var(--text-secondary)}
.in__refresh{margin:0;background:transparent;color:var(--brand-primary);font-size:12px}.in__refresh::after{border:0}
</style>
