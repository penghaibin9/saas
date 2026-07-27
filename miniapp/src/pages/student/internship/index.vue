<template>
  <view class="page-wrap">
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
              <text class="in__candidate-sub">实习状态 {{ candidate.status }} · 记录 {{ candidate.recordId }}</text>
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
        <button v-if="compliance.nextAction && compliance.nextAction.route" class="btn btn-primary" @click="openSub(compliance.nextAction.route)">
          {{ compliance.nextAction.label }}
        </button>

        <view class="in__today">
          <view class="in__today-card" @click="openSub('/pages/student/internship/checkin/index')">
            <text class="in__today-icon">📍</text>
            <text class="in__today-title">今日打卡</text>
            <text class="in__today-status" :class="{ 'is-warn': !i.checkin.done }">{{ i.checkin.done ? '已打卡' : '未打卡' }}</text>
            <text class="in__today-btn">{{ i.checkin.done ? '已完成' : '去打卡' }}</text>
          </view>
          <view class="in__today-card" @click="weekly">
            <text class="in__today-icon">✎</text>
            <text class="in__today-title">{{ i.weekly.week }}周报</text>
            <text class="in__today-status" :class="{ 'is-warn': !i.weekly.submitted }">{{ i.weekly.submitted ? '已提交' : '未提交' }}</text>
            <text class="in__today-btn">写周报</text>
          </view>
        </view>
        <MobileInlineAlert type="info" :description="i.checkin.note" />
        <MobileInlineAlert v-if="i.weekly.lastFeedback" type="warning" title="导师上周反馈" :description="i.weekly.lastFeedback" />

        <view class="section-head"><text class="section-head__title">实习状态</text></view>
        <view class="card">
          <view class="in__status-grid">
            <view class="in__status-item"><text class="in__status-k">协议</text><MobileStatusTag :status="i.status.agreement" /></view>
            <view class="in__status-item"><text class="in__status-k">保险</text><MobileStatusTag :status="i.status.insurance" /></view>
            <view class="in__status-item"><text class="in__status-k">到岗</text><MobileStatusTag :status="i.status.onboard" /></view>
            <view class="in__status-item"><text class="in__status-k">今日打卡</text><MobileStatusTag :status="i.status.todayCheckin" /></view>
            <view class="in__status-item"><text class="in__status-k">本周周报</text><MobileStatusTag :status="i.status.weekly" /></view>
            <view class="in__status-item"><text class="in__status-k">请假</text><MobileStatusTag :status="i.status.leave" /></view>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">上岗合规</text><text class="section-head__more">{{ completenessText }}</text></view>
        <view class="card">
          <view v-for="item in visibleComplianceItems" :key="item.code" class="in__compliance-row"
            :class="{ 'is-clickable': !!item.route }" @click="item.route && openSub(item.route)">
            <view class="flex-1">
              <text class="in__compliance-label">{{ item.label }}</text>
              <text v-if="item.reason" class="in__compliance-reason">{{ item.reason }}</text>
            </view>
            <MobileStatusTag :label="item.statusLabel" :type="complianceTone(item.status)" />
          </view>
          <MobileInlineAlert v-if="blockingReason" type="warning" title="上岗阻断原因" :description="blockingReason" />
        </view>

        <view class="section-head"><text class="section-head__title">实习流程</text></view>
        <view class="card"><MobileTimeline :nodes="compliance.timeline && compliance.timeline.length ? compliance.timeline : i.timeline" /></view>

        <view class="section-head"><text class="section-head__title">自助服务</text></view>
        <view class="in__nav card">
          <view v-for="n in navItems" :key="n.path" class="in__nav-item" @click="openSub(n.path)">
            <text class="in__nav-icon">{{ n.icon }}</text>
            <text class="in__nav-label">{{ n.label }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="i && i.hasBatch && !i.historyMode">
      <button class="btn btn-ghost flex-1" @click="weekly">写周报</button>
      <button class="btn btn-primary flex-1" :disabled="i.checkin.done" @click="openSub('/pages/student/internship/checkin/index')">{{ i.checkin.done ? '已打卡' : '去打卡' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast, go } from '@/utils/nav'

const STORAGE_KEY = 'gx_student_internship_batch_v1'

export default {
  data() {
    return {
      i: null, state: 'loading', selectedBatchId: '', candidates: [],
      compliance: { items: [], blockers: [], warnings: [], timeline: [] }, complianceError: '',
      navItems: [
        { label: '知情确认', path: '/pages/student/internship/consent/index', icon: '✅' },
        { label: '安全教育', path: '/pages/student/internship/safety/index', icon: '⛑️' },
        { label: '实习意向', path: '/pages/student/internship/intention/index', icon: '🎯' },
        { label: '正式申请', path: '/pages/student/internship/application/index', icon: '📋' },
        { label: '企业岗位库', path: '/pages/student/internship/enterprises/index', icon: '🏢' },
        { label: '三方协议', path: '/pages/student/internship/agreement/index', icon: '📄' },
        { label: '实习保险', path: '/pages/student/internship/insurance/index', icon: '🛡️' },
        { label: '实习计划', path: '/pages/student/internship/plan/index', icon: '🗂️' },
        { label: '实习请假', path: '/pages/student/internship/leave/index', icon: '🗓️' },
        { label: '补卡申请', path: '/pages/student/internship/makeup/index', icon: '📍' },
        { label: '日报', path: '/pages/student/internship/process-report/index?type=daily', icon: '📝' },
        { label: '月报', path: '/pages/student/internship/process-report/index?type=monthly', icon: '📑' },
        { label: '实习总结', path: '/pages/student/internship/process-report/index?type=summary', icon: '📒' },
        { label: '调岗退岗', path: '/pages/student/internship/change/index', icon: '🔄' },
        { label: '实习求助', path: '/pages/student/internship/help/index', icon: '🆘' },
        { label: '实习自评', path: '/pages/student/internship/self-eval/index', icon: '⭐' }
      ]
    }
  },
  computed: {
    needSelect() { return !!(this.i?.needSelect || this.compliance?.needSelect) && !this.selectedBatchId },
    candidateLabels() { return this.candidates.map((x) => `${x.batchName || `批次 ${x.batchId}`} · ${x.status}`) },
    candidateIndex() { return Math.max(0, this.candidates.findIndex((x) => String(x.batchId) === String(this.selectedBatchId))) },
    currentCandidateLabel() { return this.candidateLabels[this.candidateIndex] || this.i?.batch || '请选择批次' },
    visibleComplianceItems() { return (this.compliance.items || []).filter((x) => x.required || x.status !== 'NOT_APPLICABLE') },
    blockingReason() { return (this.compliance.blockers || []).map((x) => `${x.label}：${x.reason || x.statusLabel}`).join('；') },
    completenessText() { const c = this.compliance.completeness; return c ? `${c.done}/${c.required}` : '' }
  },
  onLoad() { this.restoreBatch(); this.load() },
  onShow() { if (this.i) this.load() },
  methods: {
    toast, go,
    restoreBatch() {
      try { this.selectedBatchId = String(uni.getStorageSync(STORAGE_KEY) || '') } catch (e) {}
    },
    persistBatch() {
      try {
        if (this.selectedBatchId) uni.setStorageSync(STORAGE_KEY, this.selectedBatchId)
        else uni.removeStorageSync(STORAGE_KEY)
      } catch (e) {}
    },
    withBatch(path) {
      if (!this.selectedBatchId) return path
      return `${path}${path.includes('?') ? '&' : '?'}batchId=${encodeURIComponent(this.selectedBatchId)}`
    },
    openSub(path) { go(this.withBatch(path)) },
    selectCandidate(candidate) {
      this.selectedBatchId = String(candidate?.batchId || '')
      this.persistBatch()
      this.load()
    },
    onCandidatePicker(e) { this.selectCandidate(this.candidates[Number(e.detail.value)]) },
    async load() {
      this.state = 'loading'
      this.complianceError = ''
      try {
        const [dashboard, compliance] = await Promise.all([
          studentApi.getInternship(this.selectedBatchId),
          studentApi.getInternshipCompliance('ONBOARD', this.selectedBatchId)
        ])
        const candidates = dashboard?.candidates?.length ? dashboard.candidates : (compliance?.candidates || [])
        this.candidates = candidates
        if (this.selectedBatchId && candidates.length && !candidates.some((x) => String(x.batchId) === String(this.selectedBatchId))) {
          this.selectedBatchId = ''
          this.persistBatch()
          this.i = dashboard
          this.compliance = compliance
          this.state = 'ready'
          return
        }
        this.i = dashboard
        this.compliance = compliance || { items: [], blockers: [], warnings: [], timeline: [] }
        this.state = 'ready'
      } catch (e) {
        try {
          this.i = await studentApi.getInternship(this.selectedBatchId)
          this.candidates = this.i?.candidates || []
          this.compliance = { items: [], blockers: [], warnings: [], timeline: [] }
          this.complianceError = (e && e.message) || '无法取得学校权威合规状态，请稍后重试；系统不会把未知状态显示为已通过。'
          this.state = 'ready'
        } catch (second) { this.state = 'error' }
      }
    },
    complianceTone(status) {
      if (['VALID', 'EXEMPTED', 'NOT_APPLICABLE'].includes(status)) return 'success'
      if (['REJECTED', 'CONFIG_ERROR'].includes(status)) return 'danger'
      return 'warning'
    },
    weekly() {
      if (this.i?.historyMode) return toast('历史实习记录仅可查看')
      if (this.i?.weekly?.submitted) return toast('本周周报已提交')
      const q = 'week=' + encodeURIComponent(this.i.weekly.week) +
        '&company=' + encodeURIComponent(this.i.company) +
        '&post=' + encodeURIComponent(this.i.post)
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
.in__today-icon { font-size: 24px; }
.in__today-title { font-size: var(--font-size-md); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.in__today-status { font-size: var(--font-size-sm); color: var(--success-600); }
.in__today-status.is-warn { color: var(--warning-600); }
.in__today-btn { margin-top: var(--space-2); font-size: var(--font-size-sm); color: var(--brand-primary); }
.in__status-grid { display: flex; flex-wrap: wrap; }
.in__status-item { width: 33.33%; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: var(--space-2) 0; }
.in__status-k { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.in__compliance-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--border-light); }
.in__compliance-row:last-child { border-bottom: 0; }
.in__compliance-row.is-clickable { cursor: pointer; }
.in__compliance-label { display: block; color: var(--text-primary); font-size: var(--font-size-sm); }
.in__compliance-reason { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.5; }
.in__nav { display: flex; flex-wrap: wrap; }
.in__nav-item { width: 25%; display: flex; flex-direction: column; align-items: center; gap: 6px; padding: var(--space-3) 0; }
.in__nav-icon { font-size: 26px; line-height: 1; }
.in__nav-label { font-size: var(--font-size-xs); color: var(--text-secondary); }
</style>
