<template>
  <view class="mobile-page mobile-student page-wrap student-home internship-flow">
    <MobileNavBar title="我的岗位实习" show-back fallback-url="/pages/login/index">
      <template #right><button class="mobile-control in__message" @click="go('/pages/student-internship/messages/index')">消息</button></template>
    </MobileNavBar>
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="needSelect" class="page-pad stack">
        <MobileInlineAlert type="warning" title="请选择要办理的实习批次"
          description="请选择本次要查看的实习记录。" />
        <view class="card in__selector">
          <text class="t-md t-bold">进行中的实习批次</text>
          <view v-for="candidate in candidates" :key="candidate.recordId" class="in__candidate"
            :class="{ 'is-on': String(candidate.batchId) === String(selectedBatchId) }"
            @click="selectCandidate(candidate)">
            <view class="flex-1">
              <text class="t-md t-bold">{{ candidate.batchName || `批次 ${candidate.batchId}` }}</text>
              <text class="in__candidate-sub">实习状态 {{ candidateStatusLabel(candidate.status) }} · 记录 {{ candidate.recordId }}</text>
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
        <view class="in__batch-switch">
          <text class="in__batch-switch-label">当前实习批次</text>
          <picker class="mobile-picker" v-if="candidates.length > 1" mode="selector" :range="candidateLabels" :value="candidateIndex" @change="onCandidatePicker">
            <view class="in__batch-switch-value">{{ currentCandidateLabel }} <text>▾</text></view>
          </picker>
          <text v-else class="in__batch-switch-value">{{ i.batch || currentCandidateLabel }}</text>
        </view>

        <MobileInlineAlert v-if="i.destinationType === 'EXEMPTED'" type="success" title="免实习已批准"
          description="学校已正式批准本次免实习申请。企业、岗位、协议、保险、打卡和周报等普通上岗事项不再要求办理。" />

        <view class="in__hero card">
          <view class="in__hero-head">
            <text class="in__destination">{{ destinationLabel }}</text>
            <MobileStatusTag :label="qualification.label" :type="qualification.status === 'QUALIFIED' ? 'success' : qualification.status === 'UNQUALIFIED' ? 'danger' : 'warning'" />
          </view>
          <text class="in__hero-company">{{ i.company || '企业待落实' }}</text>
          <text class="in__hero-post">{{ i.post || '岗位待落实' }}</text>
          <text v-if="i.schoolMentor" class="flow-mentor">指导教师：{{ i.schoolMentor }}</text>
          <text v-if="!detailsOpen && qualification.status !== 'QUALIFIED' && compliance.currentTask?.code !== 'eligibility'" class="in__qualification-reason">{{ qualification.reason || qualificationHint }}</text>
          <view class="in__hero-footer">
            <button class="mobile-control in__details-toggle" :aria-expanded="detailsOpen" @click="detailsOpen = !detailsOpen">{{ detailsOpen ? '收起详情' : '实习详情' }}</button>
            <button class="mobile-control in__refresh" @click="load">刷新</button>
          </view>
        </view>

        <view v-if="i.historyMode" class="flow-history">
          <view class="flow-result-head"><MobileTaskIcon name="check" /><view class="flex-1"><text class="flow-title">{{ i.statusText === 'ARCHIVED' ? '已归档 · 仅供查看' : '历史实习记录 · 仅供查看' }}</text><text class="flow-copy">本次实习已结束，历史办理记录继续保留。</text></view></view>
          <button class="mobile-control flow-history-row" @click="openSub('/pages/student-internship/plan/index')"><MobileTaskIcon name="clipboard-check" /><view class="flex-1"><text>实习计划</text><text class="flow-copy">查看本次实习安排</text></view><text class="flow-link">查看</text></button>
          <button class="mobile-control flow-history-row" @click="weekly"><MobileTaskIcon name="file-text" /><view class="flex-1"><text>周报与批阅记录</text><text class="flow-copy">保留每次提交与教师意见</text></view><text class="flow-link">查看</text></button>
          <button class="mobile-control flow-history-row" @click="openSub('/pages/student-internship/materials/index')"><MobileTaskIcon name="folder" /><view class="flex-1"><text>实习材料</text><text class="flow-copy">查看已提交的材料</text></view><text class="flow-link">查看</text></button>
          <button class="mobile-control flow-history-row" @click="openSub('/pages/student-internship/self-eval/index')"><MobileTaskIcon name="clipboard-check" /><view class="flex-1"><text>实习鉴定与成绩</text><text class="flow-copy">查看正式结果及各方意见</text></view><text class="flow-link">查看</text></button>
          <text class="flow-copy">就业登记及其他事项可从下方继续办理。</text>
        </view>
        <MobileInlineAlert v-if="noticeError" type="warning" title="通知读取未完成" :description="noticeError" />
        <button v-if="noticeError" class="mobile-control btn btn-ghost" :disabled="noticeLoading" @click="loadEmergencyNotices()">重新读取通知</button>
        <MobileInlineAlert v-if="complianceError" type="warning" title="合规状态暂不可用" :description="complianceError" />
        <MobileInlineAlert v-else-if="compliance.currentTask" :type="compliance.passed ? 'success' : 'warning'"
          :title="compliance.passed ? '上岗合规已通过' : `当前待办：${compliance.currentTask.label}`"
          :description="complianceReason(compliance.currentTask)" />
        <button v-if="compliance.nextAction && compliance.nextAction.route" class="mobile-control btn btn-primary" @click="openSub(compliance.nextAction.route)">
          {{ compliance.nextAction.label }}
        </button>

        <view v-if="detailsOpen" class="card in__details">
          <view class="in__detail-head"><text class="t-bold">学校资格认定</text><MobileStatusTag :label="qualification.label" :type="qualification.status === 'QUALIFIED' ? 'success' : qualification.status === 'UNQUALIFIED' ? 'danger' : 'warning'" /></view>
          <text v-if="qualification.reason && compliance.currentTask?.code !== 'eligibility'" class="in__qualification-reason">{{ qualification.reason }}</text>
          <text v-else-if="qualification.status !== 'QUALIFIED' && compliance.currentTask?.code !== 'eligibility'" class="in__qualification-reason">{{ qualificationHint }}</text>
          <text v-if="qualification.reviewedAt" class="in__qualification-time">认定时间 {{ formatDateTime(qualification.reviewedAt) }}</text>
          <view class="in__hero-mentors"><text class="in__mentor">校内导师 {{ i.schoolMentor }}</text><text class="in__mentor">企业导师 {{ i.companyMentor }}</text></view>
          <button v-if="i.basicInfo && !i.basicInfo.todoCount" id="student-basic-info-entry" class="mobile-control in__details-link" @click="openSub('/pages/student-internship/basic-info/index')">查看基础资料</button>
          <view class="in__detail-head in__detail-head--section"><text class="t-bold">上岗条件</text><text class="in__completeness">{{ completenessText }}</text></view>
          <view v-for="item in visibleComplianceItems" :key="item.code" class="in__compliance-row" :class="{ 'is-clickable': !!item.route }" @click="item.route && openSub(item.route)">
            <view class="flex-1"><text class="in__compliance-label">{{ item.label }}</text><text v-if="item.reason && item.code !== compliance.currentTask?.code && !(item.code === 'eligibility' && item.reason === qualification.reason)" class="in__compliance-reason">{{ complianceReason(item) }}</text></view>
            <MobileStatusTag :label="item.statusLabel" :type="complianceTone(item.status)" />
          </view>
          <template v-if="canShowDailyWork">
            <view class="in__detail-head in__detail-head--section"><text class="t-bold">实习状态</text></view>
            <view class="in__status-grid">
              <view class="in__status-item"><text class="in__status-k">协议</text><MobileStatusTag :status="i.status.agreement" /></view>
              <view class="in__status-item"><text class="in__status-k">保险</text><MobileStatusTag :status="i.status.insurance" /></view>
              <view class="in__status-item"><text class="in__status-k">到岗</text><MobileStatusTag :status="i.status.onboard" /></view>
              <view class="in__status-item"><text class="in__status-k">今日打卡</text><MobileStatusTag :status="i.status.todayCheckin" /></view>
              <view class="in__status-item"><text class="in__status-k">本周周报</text><MobileStatusTag :status="i.status.weekly" /></view>
              <view class="in__status-item"><text class="in__status-k">请假</text><MobileStatusTag :status="i.status.leave" /></view>
            </view>
          </template>
          <view class="in__detail-head in__detail-head--section"><text class="t-bold">实习流程</text></view>
          <MobileTimeline :nodes="compliance.timeline && compliance.timeline.length ? compliance.timeline : i.timeline" />
        </view>
        <view v-if="canShowDailyWork" class="in__today">
          <text class="in__section-title">今天要办</text>
          <view class="in__today-card">
            <MobileTaskIcon name="map-pin" />
            <view class="flex-1"><text class="in__today-title">今日打卡</text><text class="in__today-status" :class="{ 'is-warn': !i.checkin.done }">{{ i.checkin.done ? '已打卡' : '待完成' }}</text></view>
            <button class="mobile-control btn btn-primary" @click="openSub('/pages/student-internship/checkin/index')">{{ i.checkin.done ? '查看记录' : '去打卡' }}</button>
          </view>
          <view v-if="dailyRequired" class="in__today-card"><MobileTaskIcon name="file-text" /><view class="flex-1"><text class="in__today-title">我的日报</text><text class="in__today-status">按本批次要求填写</text></view><button class="mobile-control btn btn-ghost" @click="openSub('/pages/student-internship/process-report/index?type=daily')">填写／查看日报</button></view>
          <view class="in__today-card">
            <MobileTaskIcon name="file-text" />
            <view class="flex-1"><text class="in__today-title">我的周报</text><text class="in__today-status">{{ i.weekly.week }} · {{ i.weekly.approved ? '已批阅' : i.weekly.submitted ? '已提交' : '可填写' }}</text></view>
            <button class="mobile-control btn btn-ghost" @click="weekly">{{ i.weekly.submitted || i.weekly.approved ? '查看周报' : '写周报' }}</button>
          </view>
<button v-if="dailyRuleError" class="mobile-control" @click="openSub('/pages/student-internship/process-report/index?type=daily')">日报要求暂未读取，进入核对</button><text class="in__privacy">{{ i.checkin.note }}</text>
        </view>
        <view v-for="item in returnedMaterials" :key="item.id" class="in__material-return">
          <MobileTaskIcon name="alert-circle" tone="amber" />
          <view class="flex-1"><text class="in__today-title">材料需补正</text><text class="in__return-title">{{ item.materialName }}</text><text class="in__return-note">{{ item.submission.reviewComment || '老师已退回，请按原单修改后重交。' }}</text></view>
          <button class="mobile-control" @click="openMaterial(item)">去补正</button>
        </view>
        <MobileInlineAlert v-if="materialError" type="warning" title="材料状态未能读取" :description="materialError" />
        <button v-if="materialError" class="mobile-control btn btn-ghost" @click="load">重新读取材料状态</button>

        <view class="in__quick">
          <text class="in__section-title">{{ i.historyMode ? '其他办理' : '常用办理' }}</text>
          <view class="in__quick-grid">
            <template v-if="!i.historyMode"><button class="mobile-control" v-for="n in quickItems" :key="n.path" @click="openSub(n.path)"><MobileTaskIcon :name="navIcon(n)" /><text>{{ n.label }}</text></button></template>
            <button class="mobile-control" :aria-expanded="moreExpanded" @click="moreExpanded = !moreExpanded"><MobileTaskIcon name="layout-grid" tone="gray" /><text>{{ moreExpanded ? '收起其他事项' : '更多事项' }}</text></button>
          </view>
        </view>
        <view v-if="moreExpanded" class="in__service-groups">
          <view v-for="group in moreServiceGroups" :key="group.key" class="in__service-group">
            <view class="in__service-head">
              <text class="in__service-title">{{ group.label }}</text>
            </view>
            <view class="in__nav card">
              <button v-for="n in group.items" :key="n.path" class="mobile-control in__nav-item" @click="openSub(n.path)"><MobileTaskIcon :name="navIcon(n)" plain /><text class="in__nav-label">{{ n.label }}</text></button>
            </view>
          </view>
        </view>
        <view v-if="i.basicInfo?.todoCount" class="in__basic-todo">
          <text>基础资料待完善：{{ i.basicInfo.missingFields.join('、') }}</text>
          <button id="student-basic-info-entry" class="mobile-control in__refresh" @click="openSub('/pages/student-internship/basic-info/index')">去完善</button>
        </view>
        <view v-if="canShowDailyWork && i.weekly.lastFeedback" class="in__feedback">
          <button class="mobile-control" :aria-expanded="feedbackOpen" @click="feedbackOpen = !feedbackOpen">{{ feedbackOpen ? '收起导师反馈' : '查看导师反馈' }}</button>
          <text v-if="feedbackOpen">{{ i.weekly.lastFeedback }}</text>
        </view>
      </view>
    </MobileGlobalState>

    <SchoolServiceInfo ref="schoolService" compact />

    <view v-if="activeEmergencyNotice" class="in__notice-mask">
      <view class="in__notice-dialog" role="dialog">
        <view class="in__notice-head">
          <text class="in__notice-kicker">紧急通知</text>
          <text class="in__notice-title">{{ activeEmergencyNotice.title }}</text>
          <text class="in__notice-meta">{{ activeEmergencyNotice.senderName || '学校' }} · {{ formatDateTime(activeEmergencyNotice.publishedAt) }}</text>
        </view>
        <scroll-view scroll-y class="in__notice-body">
          <text class="in__notice-content">{{ activeEmergencyNotice.content }}</text>
          <view class="in__notice-meta-box">
            <text>{{ noticeTypeLabel(activeEmergencyNotice.noticeType) }} · {{ noticeUrgencyLabel(activeEmergencyNotice.urgency) }}</text>
            <text v-if="activeEmergencyNotice.validFrom || activeEmergencyNotice.validUntil">有效期：{{ noticeDate(activeEmergencyNotice.validFrom) }} 至 {{ noticeDate(activeEmergencyNotice.validUntil) }}</text>
          </view>
          <view v-if="activeEmergencyNotice.attachments?.length" class="in__notice-files">
            <text class="in__notice-files-title">附件</text>
            <view v-for="file in activeEmergencyNotice.attachments" :key="file.fileId" class="in__notice-file" @click="openNoticeAttachment(file)">
              <text class="in__notice-file-name">{{ file.fileName || '通知附件' }}</text>
              <text class="in__notice-file-open">查看</text>
            </view>
          </view>
        </scroll-view>
        <MobileInlineAlert type="warning" description="该通知需要本人明确确认。关闭页面、网络中断或确认失败都不会自动记为已读，下次进入仍会继续提醒。" />
        <MobileInlineAlert v-if="noticeError" type="warning" title="通知操作未完成" :description="noticeError" />
        <button v-if="noticeError" class="mobile-control btn btn-ghost" :disabled="noticeLoading" @click="loadEmergencyNotices()">重新读取通知</button>
        <button class="mobile-control btn btn-primary in__notice-ack" :disabled="noticeAcking || noticeLoading" @click="acknowledgeEmergencyNotice">
          {{ noticeAcking ? '正在记录…' : '我已知悉' }}
        </button>
      </view>
    </view>
  </view>
</template>

<script>
import SchoolServiceInfo from '@/components/SchoolServiceInfo.vue'
import { formatDateTime } from '@/utils/format'
import { studentApi } from '@/services/studentApi'
import { openBusinessFile } from '@/services/fileApi'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { toast, go } from '@/utils/nav'

const STORAGE_KEY = 'gx_student_internship_batch_v1'
const INTERNSHIP_RECORD_STATUS_LABELS = {
  DRAFT: '待完善', APPLIED: '待审核', APPROVED: '待确认', PREPARING: '实习准备', READY: '待上岗', ONBOARD: '实习中',
  ASSESSING: '考核中', ENDED: '已结束', ARCHIVED: '已归档', TERMINATED: '已终止'
}

export default {
  components: { SchoolServiceInfo },
  data() {
    return {
      i: null, state: 'loading', loadSequence: 0, selectedBatchId: '', candidates: [], detailsOpen: false,
      compliance: { items: [], blockers: [], warnings: [], timeline: [] }, complianceError: '',
      pendingEmergencyNotices: [], activeEmergencyNotice: null, noticeAcking: false,
      dailyRequired: false, dailyRuleError: false, returnedMaterials: [], materialError: '', moreExpanded: false, feedbackOpen: false,
      noticeError: '', noticeLoading: false, noticeSequence: 0, hidden: false, generation: currentSessionGeneration(),
      navItems: [
        { label: '知情确认', path: '/pages/student-internship/consent/index', icon: '✅', stages: ['onboard'] },
        { label: '安全教育', path: '/pages/student-internship/safety/index', icon: '⛑️', stages: ['onboard'] },
        { label: '实习意向', path: '/pages/student-internship/intention/index', icon: '🎯', stages: ['selection'] },
        { label: '正式申请', path: '/pages/student-internship/application/index', icon: '📋', stages: ['selection'] },
        { label: '实习选岗', path: '/pages/student-internship/enterprises/index', icon: '🏢', stages: ['selection'] },
        { label: '三方协议', path: '/pages/student-internship/agreement/index', icon: '📄', stages: ['onboard'] },
        { label: '实习保险', path: '/pages/student-internship/insurance/index', icon: '🛡️', stages: ['onboard'] },
        { label: '实习计划', path: '/pages/student-internship/plan/index', icon: '🗂️', stages: ['onboard', 'process'] },
        { label: '实习材料', path: '/pages/student-internship/materials/index', icon: '📎', stages: ['onboard', 'process', 'result'] },
        { label: '通知公告', path: '/pages/student-internship/notices/index', icon: '🔔', today: true },
        { label: '轮岗与工资', path: '/pages/student-internship/process-facts/index', icon: '💼', stages: ['process', 'result'] },
        { label: '就业上报', path: '/pages/student-internship/employment/index', icon: '🎓', stages: ['process', 'result'] },
        { label: '实习请假', path: '/pages/student-internship/leave/index', icon: '🗓️', today: true },
        { label: '补卡申请', path: '/pages/student-internship/makeup/index', icon: '📍', today: true },
        { label: '日报', path: '/pages/student-internship/process-report/index?type=daily', icon: '📝', today: true },
        { label: '月报', path: '/pages/student-internship/process-report/index?type=monthly', icon: '📑', stages: ['process'] },
        { label: '实习总结', path: '/pages/student-internship/process-report/index?type=summary', icon: '📒', stages: ['result'] },
        { label: '调岗退岗', path: '/pages/student-internship/change/index', icon: '🔄', stages: ['process'] },
        { label: '实习求助', path: '/pages/student-internship/help/index', icon: '🆘', today: true },
        { label: '免实习申请', path: '/pages/student-internship/exemption/index', icon: '🧾', stages: ['selection', 'onboard'] },
        { label: '意见反馈', path: '/pages/student-internship/feedback/index', icon: '💬', today: true },
        { label: '鉴定与成绩', path: '/pages/student-internship/self-eval/index', icon: '⭐', stages: ['result'] }
      ]
    }
  },
  computed: {
    quickItems() { return ['实习请假', '实习材料', '实习计划'].map(label => this.navItems.find(item => item.label === label)).filter(item => item && item.path !== this.compliance?.nextAction?.route) },
    moreServiceGroups() { const paths = new Set(this.quickItems.map(item => item.path)); return this.serviceGroups.map(group => ({ ...group, items: group.items.filter(item => !paths.has(item.path)) })).filter(group => group.items.length) },
    qualification() { return this.i?.eligibilityReview || { status: 'UNKNOWN', label: '暂未取得结果', reason: '' } },
    destinationLabel() { return ({ SELF_ARRANGED: '自主实习', ASSIGNED: '学校安排', EXEMPTED: '免实习' })[this.i?.destinationType] || '我的实习去向' },
    qualificationHint() { return ({ QUALIFIED: '学校已完成本批次实习资格认定。', PENDING: '学校正在核对实习资格。需要补充材料时，请联系校内指导教师。', UNQUALIFIED: '本次认定未通过。请联系指导教师了解原因及后续安排。' })[this.qualification.status] || '请刷新认定结果，或联系指导教师核对。' },
    canShowDailyWork() { return this.i?.hasBatch && !this.i.historyMode && this.i.statusText === 'ONBOARD' },
    needSelect() { return !!(this.i?.needSelect || this.compliance?.needSelect) && !this.selectedBatchId },
    candidateLabels() { return this.candidates.map((x) => `${x.batchName || `批次 ${x.batchId}`} · ${this.candidateStatusLabel(x.status)}`) },
    candidateIndex() { return Math.max(0, this.candidates.findIndex((x) => String(x.batchId) === String(this.selectedBatchId))) },
    currentCandidateLabel() { return this.candidateLabels[this.candidateIndex] || this.i?.batch || '请选择批次' },
    visibleComplianceItems() { return (this.compliance.items || []).filter((x) => x.required || x.status !== 'NOT_APPLICABLE') },
    completenessText() { const c = this.compliance.completeness; return c ? `${c.done}/${c.required}` : '' },
    currentStage() {
      if (this.i?.destinationType === 'EXEMPTED') return 'result'
      if (this.i?.historyMode || ['ASSESSING', 'ARCHIVED', 'ENDED'].includes(this.i?.statusText)) return 'result'
      if (!this.i?.company || !this.i?.post) return 'selection'
      if (this.i?.statusText === 'ONBOARD') return 'process'
      return 'onboard'
    },
    serviceGroups() {
      const actionRoute = String(this.compliance?.nextAction?.route || '')
      const required = actionRoute ? this.navItems.filter((item) => item.path === actionRoute) : []
      const requiredPaths = new Set(required.map((item) => item.path))
      const today = this.navItems.filter((item) => item.today && (this.canShowDailyWork || item.path.includes('/help/')) && !requiredPaths.has(item.path))
      const todayPaths = new Set(today.map((item) => item.path))
      const stage = this.navItems.filter((item) => (item.stages || []).includes(this.currentStage) && !requiredPaths.has(item.path) && !todayPaths.has(item.path))
      const stagePaths = new Set(stage.map((item) => item.path))
      const more = this.navItems.filter((item) => !requiredPaths.has(item.path) && !todayPaths.has(item.path) && !stagePaths.has(item.path))
      return [
        { key: 'today', label: this.canShowDailyWork ? '今天' : '需要帮助', items: today },
        { key: 'stage', label: ({ selection: '选岗申请', onboard: '上岗准备', process: '实习记录', result: '实习收尾' })[this.currentStage], items: stage },
        { key: 'more', label: '其他事项', items: more }
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
  onShow() {
    this.$nextTick(()=>this.$refs.schoolService?.load())
    const reload = this.hidden || !!this.i || this.generation !== currentSessionGeneration()
    this.hidden = false
    if (this.generation !== currentSessionGeneration()) this.clearAccountContext()
    if (reload) this.load()
  },
  onHide() { this.hidden = true; this.loadSequence++; this.noticeSequence++; this.noticeAcking = false; this.noticeLoading = false },
  onUnload() { this.hidden = true; this.loadSequence++; this.noticeSequence++ },
  methods: {
    complianceReason(item) {
      const reason = item?.reason || ''
      if (this.i?.destinationType !== 'SELF_ARRANGED' || item?.status !== 'MISSING') return reason
      if (item.code === 'enterprise' && String(this.i.company || '').trim() && reason === '尚未落实实习企业') return '企业已登记，待学校核实企业准入'
      if (item.code === 'position' && String(this.i.post || '').trim() && reason === '尚未落实实习岗位') return '岗位已登记，待学校核实岗位条件'
      return reason
    },
    formatDateTime,
    toast, go,
    candidateStatusLabel(status) { return INTERNSHIP_RECORD_STATUS_LABELS[String(status || '').toUpperCase()] || '状态待确认' },
    clearAccountContext() {
      this.detailsOpen = false
      this.returnedMaterials = []; this.materialError = ''; this.moreExpanded = false; this.feedbackOpen = false
      this.loadSequence++; this.noticeSequence++; this.i = null; this.candidates = []; this.selectedBatchId = ''
      this.compliance = { items: [], blockers: [], warnings: [], timeline: [] }; this.complianceError = ''
      this.pendingEmergencyNotices = []; this.activeEmergencyNotice = null; this.noticeError = ''
      this.noticeAcking = false; this.noticeLoading = false; this.generation = currentSessionGeneration()
      this.persistBatch()
    },
    readCurrent(seq, generation) { return !this.hidden && seq === this.loadSequence && generation === currentSessionGeneration() },
    noticeBatchId() { return String(this.selectedBatchId || this.i?.batchId || '') },
    restoreBatch() { try { this.selectedBatchId = String(uni.getStorageSync(STORAGE_KEY) || '') } catch (e) {} },
    persistBatch() { try { if (this.selectedBatchId) uni.setStorageSync(STORAGE_KEY, this.selectedBatchId); else uni.removeStorageSync(STORAGE_KEY) } catch (e) {} },
    withBatch(path) { if (!this.selectedBatchId) return path; return `${path}${path.includes('?') ? '&' : '?'}batchId=${encodeURIComponent(this.selectedBatchId)}` },
    openSub(path) { go(this.withBatch(path)) },
    selectCandidate(candidate) {
      this.detailsOpen = false
      this.returnedMaterials = []; this.materialError = ''; this.moreExpanded = false; this.feedbackOpen = false
      this.selectedBatchId = String(candidate?.batchId || '')
      this.pendingEmergencyNotices = []
      this.activeEmergencyNotice = null
      this.noticeAcking = false
      this.noticeError = ''; this.noticeLoading = false; this.noticeSequence++
      this.persistBatch()
      this.load()
    },
    onCandidatePicker(e) { this.selectCandidate(this.candidates[Number(e.detail.value)]) },
    async load() {
      if (this.generation !== currentSessionGeneration()) this.clearAccountContext()
      const seq = ++this.loadSequence
      const generation = currentSessionGeneration()
      const batchId = this.selectedBatchId
      this.dailyRequired=false;this.dailyRuleError=false;this.state = 'loading'; this.complianceError = ''; this.returnedMaterials = []; this.materialError = ''
      const [dashboard, compliance] = await Promise.allSettled([
        studentApi.getInternship(batchId), studentApi.getInternshipCompliance('ONBOARD', batchId)
      ])
      if (!this.readCurrent(seq, generation)) return
      if (dashboard.status !== 'fulfilled') { this.state = 'error'; return }
      this.i = dashboard.value
      if(this.i?.hasBatch && !this.i.historyMode && this.i.statusText === 'ONBOARD') {
        try { const reports=await studentApi.getInternshipProcessReports(this.i.batchId,this.i.recordId,1,1,'DAILY');if(!this.readCurrent(seq,generation))return;const count=reports?.rules?.dailyRequiredCount;if(!Number.isInteger(count)||count<0)throw new Error('日报要求尚未取得');this.dailyRequired=count>0 }
        catch { if(!this.readCurrent(seq,generation))return;this.dailyRuleError=true }
      }
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
      await Promise.all([this.loadEmergencyNotices(seq, generation), this.loadReturnedMaterials(seq, generation)])
    },
    async loadReturnedMaterials(seq, generation) {
      if (!this.i?.hasBatch || this.i.historyMode || !this.i.recordId || !this.readCurrent(seq, generation)) return
      const batchId = String(this.i.batchId || this.selectedBatchId || ''), recordId = String(this.i.recordId)
      try {
        const result = await studentApi.getInternshipMaterialRequirements(batchId, recordId)
        if (!this.readCurrent(seq, generation)) return
        this.returnedMaterials = (Array.isArray(result) ? result : result?.items || []).filter(item => item.submission?.status === 'RETURNED')
      } catch { if (this.readCurrent(seq, generation)) this.materialError = '请重新读取，或进入实习材料查看原任务。' }
    },
    openMaterial(item) { this.openSub('/pages/student-internship/materials/index?requirementId=' + encodeURIComponent(String(item.id))) },
    navIcon(item) {
      if (/请假/.test(item.label)) return 'calendar'
      if (/求助|反馈/.test(item.label)) return 'message-dots'
      if (/材料|档案/.test(item.label)) return 'folder'
      if (/岗位|打卡|补卡/.test(item.label)) return 'map-pin'
      if (/安全|保险/.test(item.label)) return 'shield-exclamation'
      return 'file-text'
    },
    async loadEmergencyNotices(seq = this.loadSequence, generation = currentSessionGeneration()) {
      if (this.needSelect || !this.i?.hasBatch || !this.readCurrent(seq, generation)) return
      const batchId = this.noticeBatchId()
      if (!batchId) return
      const noticeSequence = ++this.noticeSequence
      const current = () => this.readCurrent(seq, generation) && noticeSequence === this.noticeSequence && batchId === this.noticeBatchId()
      this.noticeLoading = true
      try {
        const rows = await studentApi.getPendingEmergencyNotices(batchId)
        if (!current()) return
        this.pendingEmergencyNotices = Array.isArray(rows) ? rows : []
        this.activeEmergencyNotice = this.pendingEmergencyNotices[0] || null
        this.noticeError = ''
      } catch (e) {
        if (current()) this.noticeError = '通知读取失败，尚不能确认是否有新的重要通知。请重新读取；已有通知会保留。'
      } finally { if (current()) this.noticeLoading = false }
    },
    noticeTypeLabel(value) {
      return ({ AGREEMENT: '实习协议', TRAINING: '岗前培训', SAFETY: '安全条例', NOTICE: '通知公告', OTHER: '其他' })[String(value || '').toUpperCase()] || '通知公告'
    },
    noticeUrgencyLabel(value) {
      return ({ NORMAL: '普通', IMPORTANT: '重要', URGENT: '紧急' })[String(value || '').toUpperCase()] || '普通'
    },
    noticeDate(value) { return value ? formatDateTime(value).slice(0, 10) : '不限' },
    async openNoticeAttachment(file) {
      try { await openBusinessFile(file.fileId, file.fileName || '通知附件') }
      catch (e) { toast(e?.message || '通知附件暂时无法打开') }
    },
    async acknowledgeEmergencyNotice() {
      const notice = this.activeEmergencyNotice
      if (!notice || this.noticeAcking || this.noticeLoading || this.hidden) return
      const batchId = this.noticeBatchId()
      if (!batchId) return toast('当前实习批次不可用，请刷新后重试')
      const seq = this.loadSequence, generation = currentSessionGeneration(), noticeSequence = this.noticeSequence
      const current = () => this.readCurrent(seq, generation) && noticeSequence === this.noticeSequence && batchId === this.noticeBatchId() && this.activeEmergencyNotice === notice
      this.noticeAcking = true
      try {
        await studentApi.acknowledgeEmergencyNotice(notice.id, batchId)
        if (!current()) return
        this.noticeError = ''
        this.noticeAcking = false
        this.pendingEmergencyNotices = this.pendingEmergencyNotices.filter((x) => String(x.id) !== String(notice.id))
        this.activeEmergencyNotice = this.pendingEmergencyNotices[0] || null
        if (!this.activeEmergencyNotice) toast('紧急通知已确认')
      } catch (e) {
        if (current()) { this.noticeError = e?.message || '知悉回执提交失败，通知仍会保留'; toast(this.noticeError) }
      } finally {
        if (current()) this.noticeAcking = false
      }
    },
    complianceTone(status) { if (['VALID', 'EXEMPTED', 'NOT_APPLICABLE'].includes(status)) return 'success'; if (['REJECTED', 'CONFIG_ERROR'].includes(status)) return 'danger'; return 'warning' },
    weekly() {
      go(this.withBatch('/pages/student/weekly-report/index'))
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
.in__message { margin: 0; padding: 0 6px; min-height: 44px; min-width: 44px; background: transparent; color: var(--brand-primary); font-size: var(--font-size-sm); }
.in__message::after { border: 0; }
.in__hero-head,.in__hero-footer,.in__detail-head,.in__basic-todo { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); }
.in__destination { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.in__hero-footer { margin-top: var(--space-3); padding-top: var(--space-2); border-top: 1px solid var(--border-light); }
.in__details-toggle,.in__details-link { display:flex;align-items:center;min-height:44px;min-width:44px;margin: 0; padding: 0; background: transparent; color: var(--brand-primary); font-size: var(--font-size-sm); text-align: left; }
.in__details-toggle::after,.in__details-link::after { border: 0; }
.in__details-link { margin-top: var(--space-3); }
.in__detail-head { font-size: var(--font-size-sm); }
.in__detail-head--section { margin-top: var(--space-5); }
.in__completeness { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.in__basic-todo { font-size: var(--font-size-sm); }
.in__basic-todo>text { min-width: 0; overflow-wrap: anywhere; }
.in__hero-post { display: block; font-size: var(--font-size-md); color: var(--text-secondary); margin-top: var(--space-2); }
.in__hero-company { display: block; font-size: var(--font-size-2xl); font-weight: var(--font-weight-semibold); color: var(--text-primary); margin-top: var(--space-2); overflow-wrap:anywhere; }
.in__hero-mentors { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-top: var(--space-3); }
.in__mentor { font-size: var(--font-size-xs); color: var(--text-secondary); background: var(--gray-100); padding: 3px 8px; border-radius: var(--radius-full); }
.in__today { display:flex;flex-direction:column;gap:var(--space-3); }
.in__today-card { background:var(--bg-card);border-radius:var(--radius-lg);padding:var(--space-4);box-shadow:var(--shadow-card);display:flex;align-items:center;gap:var(--space-3); }
.in__today-title{display:block;font-size:var(--font-size-lg);font-weight:var(--font-weight-semibold);color:var(--text-primary);line-height:1.5}
.in__today-status{display:block;margin-top:var(--space-1);font-size:var(--font-size-base);color:var(--text-secondary)}.in__today-status.is-warn{color:var(--warning-700)}
.in__today-card .btn{flex-shrink:0;min-width:84px;padding:0 var(--space-3);margin:0}
.student-home{padding-bottom:var(--space-6);font-size:var(--font-size-md)}
.student-home>.mnav{background:var(--bg-card)}
.student-home :deep(.page-pad){width:100%;max-width:760px;box-sizing:border-box;margin:0 auto;gap:var(--space-4)}
.in__batch-switch{gap:var(--space-3);font-size:var(--font-size-base);line-height:1.6}.in__batch-switch-label{flex-shrink:0}.in__batch-switch-value{overflow-wrap:anywhere}
.in__section-title{display:block;font-size:var(--font-size-xl);font-weight:var(--font-weight-semibold);line-height:1.5}
.in__privacy{display:block;font-size:var(--font-size-sm);line-height:1.6;color:var(--text-secondary)}
.in__quick{display:flex;flex-direction:column;gap:var(--space-3)}.in__quick-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--space-3)}
.in__quick-grid>button{display:flex;align-items:center;gap:var(--space-2);margin:0;padding:var(--space-3);min-height:76px;line-height:1.5;text-align:left;font-size:var(--font-size-md);border:0;border-radius:var(--radius-lg);background:var(--bg-card);color:var(--text-primary)}
.in__quick-grid>button::after,.in__material-return>button::after,.in__feedback>button::after{border:0}
.in__quick-grid>button>text{min-width:0;overflow-wrap:anywhere}
.in__material-return{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-4);border-radius:var(--radius-lg);background:var(--warning-50)}
.in__return-title,.in__return-note{display:block;font-size:var(--font-size-base);line-height:1.6;overflow-wrap:anywhere}.in__return-title{color:var(--warning-700)}.in__return-note{color:var(--text-secondary);margin-top:var(--space-1)}
.in__material-return>button{flex-shrink:0;margin:0;padding:0 var(--space-3);min-height:44px;line-height:44px;font-size:var(--font-size-md);border:0;border-radius:var(--radius-md);background:var(--warning-100);color:var(--warning-700)}
.in__basic-todo{padding:var(--space-3);background:var(--info-50);border-radius:var(--radius-md);line-height:1.6}
.in__feedback{padding:var(--space-3);border-radius:var(--radius-md);background:var(--bg-card)}.in__feedback>button{width:100%;min-height:44px;margin:0;padding:0;border:0;text-align:left;background:transparent;color:var(--brand-primary);font-size:var(--font-size-md)}.in__feedback>text{display:block;font-size:var(--font-size-base);line-height:1.7;color:var(--text-secondary);white-space:pre-wrap}
.in__nav-item{margin:0;border:0;background:var(--bg-card);font-size:var(--font-size-base);line-height:1.5;min-height:76px}.in__nav-item::after{border:0}
.in__status-grid { display: flex; flex-wrap: wrap; }.in__status-item { width: 33.33%; display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: var(--space-2) 0; }.in__status-k { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.in__compliance-row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--border-light); }.in__compliance-row:last-child { border-bottom: 0; }.in__compliance-row.is-clickable { cursor: pointer; }.in__compliance-label { display: block; color: var(--text-primary); font-size: var(--font-size-sm); }.in__compliance-reason { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.5; }
.in__service-groups { display: flex; flex-direction: column; gap: var(--space-3); }
.in__service-head { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-2); padding: 0 2px; }
.in__service-title { display: block; color: var(--text-primary); font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); }
.in__nav { display: flex; flex-wrap: wrap; }.in__nav-item { width: 25%; min-height: var(--touch-target-min); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 6px; padding: var(--space-3) 0; }.in__nav-icon { font-size: 26px; line-height: 1; }.in__nav-label { font-size: var(--font-size-xs); color: var(--text-secondary); }

.in__qualification-reason{display:block;margin-top:var(--space-2);font-size:var(--font-size-sm);line-height:1.6;color:var(--text-secondary);white-space:pre-wrap;word-break:break-word}
.in__qualification-time{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:var(--space-2)}
.in__refresh{display:flex;align-items:center;min-height:44px;min-width:44px;margin:0;background:transparent;color:var(--brand-primary);font-size:12px}.in__refresh::after{border:0}

.in__notice-mask{position:fixed;z-index:9999;inset:0;background:rgba(15,23,42,.68);display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box}
.in__notice-dialog{width:100%;max-width:560px;max-height:82vh;background:var(--bg-card);border-radius:var(--radius-lg);padding:20px;box-sizing:border-box;display:flex;flex-direction:column;gap:14px;box-shadow:0 24px 64px rgba(15,23,42,.28)}
.in__notice-head{display:flex;flex-direction:column;gap:6px}.in__notice-kicker{font-size:12px;font-weight:600;color:var(--danger-600,#dc2626)}
.in__notice-title{font-size:20px;font-weight:700;line-height:1.45;color:var(--text-primary)}.in__notice-meta{font-size:11px;color:var(--text-tertiary)}
.in__notice-body{max-height:38vh;padding:12px;background:var(--gray-50,#f8fafc);border:1px solid var(--border-light);border-radius:var(--radius-sm);box-sizing:border-box}
.in__notice-content{white-space:pre-wrap;word-break:break-word;font-size:14px;line-height:1.8;color:var(--text-secondary)}
.in__notice-meta-box{display:flex;flex-direction:column;gap:4px;margin-top:12px;padding-top:10px;border-top:1px solid var(--border-light);font-size:11px;color:var(--text-tertiary)}
.in__notice-files{display:flex;flex-direction:column;gap:7px;margin-top:12px}.in__notice-files-title{font-size:12px;font-weight:600;color:var(--text-secondary)}
.in__notice-file{display:flex;justify-content:space-between;gap:10px;padding:9px 10px;border-radius:8px;background:var(--bg-card);font-size:12px}.in__notice-file-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-primary)}.in__notice-file-open{flex:0 0 auto;color:var(--brand-primary)}
.in__notice-ack{width:100%;margin:0}
</style>
