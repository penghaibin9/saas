<template>
  <view class="internship-surface mobile-page mobile-student page-wrap pl">
    <MobileNavBar title="实习计划" show-back :fallback-url="'/pages/student-internship/index' + (context.batchId ? '?batchId=' + encodeURIComponent(context.batchId) : '')" />
    <MobilePrivacyGate />
    <MobileGlobalState :state="pageState" :title="pageState === 'empty' ? '暂无实习计划' : undefined" :description="error || (pageState === 'empty' ? '等待学校发布计划。' : undefined)" @retry="load" @back="returnHome">
      <view class="page-pad stack" v-if="plan">
        <view v-if="conflict" class="card stack">
          <MobileInlineAlert type="warning" title="计划已变化，全部任务草稿已保留" :description="conflict.error" />
          <button class="mobile-control btn btn-ghost" :disabled="conflictReading" @click="rereadConflict">读取最新计划和任务</button>
          <template v-if="conflict.latestPlan">
            <text>最新计划：{{ conflict.latestPlan.title }} · 第{{ conflict.latestPlan.version ?? conflict.latestPlan.planVersion }}版</text>
            <text>{{ conflict.latestPlan.content || '计划正文未填写' }}</text>
            <view v-for="task in conflict.taskData.tasks" :key="task.sortOrder">
              <text>{{ task.name || task.taskName }} · {{ task.progressStatusLabel || task.statusLabel || '状态待核对' }}</text>
              <text>{{ task.requirement }} {{ task.studentNote }}</text>
            </view>
            <button class="mobile-control btn btn-ghost" :disabled="conflictReading" @click="adoptLatestPlan">已核对最新计划和任务，保留草稿继续</button>
          </template>
        </view>
        <view v-if="plans.length > 1" class="card pl__switcher">
          <text class="pl__label">当前实习方案</text>
          <picker class="mobile-picker" mode="selector" :range="planLabels" :value="planIndex" :disabled="submitting !== false || uploading !== false" @change="onPlanChange">
            <view class="pl__picker">{{ planLabels[planIndex] || '选择实习方案' }} <text>▾</text></view>
          </picker>
        </view>
        <view class="card">
          <view class="row-between pl__heading"><text class="card-title">{{ plan.title }}</text><MobileStatusTag :status="plan.ackStatus" :label="plan.ackStatusLabel" /></view>
          <view v-if="summary.total" class="pl__prog">
            <text>任务完成 {{ summary.approved }}/{{ summary.total }}（{{ summary.rate }}%）</text>
            <view class="pl__bar"><view class="pl__bar-in" :style="{ width: summary.rate + '%' }" /></view>
          </view>
        </view>
        <view class="card">
          <button class="mobile-control pl__details-toggle" :aria-expanded="planDetailsExpanded" @click="expandedPlanScope = planDetailsExpanded ? '' : planDetailScope">{{ planDetailsExpanded ? '收起计划详情' : '计划详情' }} <text>{{ planDetailsExpanded ? '▴' : '▾' }}</text></button>
          <view v-if="planDetailsExpanded" class="pl__details">
          <text class="pl__label">计划基本信息</text>
          <view class="pl__facts">
            <view><text>计划编号</text><text class="pl__fact-value">{{ plan.planNo || '—' }}</text></view>
            <view><text>实习类别</text><text class="pl__fact-value">{{ plan.internshipTypeLabel || '—' }}</text></view>
            <view><text>适用专业</text><text class="pl__fact-value">{{ plan.majorName || '—' }}</text></view>
            <view><text>培养层次</text><text class="pl__fact-value">{{ plan.educationLevel || '—' }}</text></view>
            <view><text>指导老师</text><text class="pl__fact-value">{{ context.advisorName || '—' }}</text></view>
            <view><text>负责人</text><text class="pl__fact-value">{{ plan.responsibleName || '—' }}</text></view>
            <view><text>开始时间</text><text class="pl__fact-value">{{ plan.basicSnapshot?.startDate || '—' }}</text></view>
            <view><text>结束时间</text><text class="pl__fact-value">{{ plan.basicSnapshot?.endDate || '—' }}</text></view>
            <view class="pl__fact-wide"><text>补贴标准</text><text class="pl__fact-value">{{ plan.subsidyStandard || '—' }}</text></view>
            <view><text>应签到</text><text class="pl__fact-value">{{ plan.rulesSnapshot?.requiredCheckinDays ?? 0 }} 天</text></view>
            <view><text>应写日报</text><text class="pl__fact-value">{{ plan.rulesSnapshot?.dailyRequiredCount ?? 0 }} 篇</text></view>
            <view><text>应写周报</text><text class="pl__fact-value">{{ plan.rulesSnapshot?.weeklyRequiredCount ?? 0 }} 篇</text></view>
            <view><text>应写月报</text><text class="pl__fact-value">{{ plan.rulesSnapshot?.monthlyRequiredCount ?? 0 }} 篇</text></view>
            <view><text>应写总结</text><text class="pl__fact-value">{{ plan.rulesSnapshot?.summaryRequiredCount ?? 0 }} 篇</text></view>
          </view>
          <view class="pl__score" v-if="(plan.rulesSnapshot?.scoreComponents || []).length">
            <text>考核占比</text>
            <view class="pl__score-tags">
              <text v-for="(item, i) in plan.rulesSnapshot.scoreComponents" :key="i">{{ item.name || '考核项' }} {{ Math.round(Number(item.weight || 0) * 100) }}%</text>
            </view>
          </view>
          <text class="pl__label">实习目标</text>
          <text class="pl__text">{{ plan.objectives || '—' }}</text>
          <text class="pl__label">计划正文</text>
          <text class="pl__text">{{ plan.content || '—' }}</text>
          <text class="pl__label">实习要求与考核</text>
          <text class="pl__text">{{ plan.requirements || '未填写' }}</text>
          <text class="pl__text">{{ plan.assessmentContent || '未填写' }}</text>
          <button v-for="file in plan.attachments || []" :key="file.fileId" class="mobile-control btn btn-ghost" @click="openPlanFile(file)">查看{{ file.fileName || '计划附件' }}</button>
          </view>
        </view>
        <view v-if="tasks.length" class="card">
          <text class="pl__label">实习任务清单</text>
          <text v-if="tasks.some(task => canSubmit(task))" class="pl__task-req">按各项截止时间提交完成情况，交指导教师核对；教师确认后该项任务才算完成。</text>
          <view v-for="(t, i) in tasks" :key="t.progressId || t.sortOrder || i" class="pl__task">
            <view class="pl__task-head">
              <text class="pl__task-no">{{ t.sortOrder || i + 1 }}</text>
              <text class="pl__task-name">{{ t.name || t.taskName }}</text>
              <text class="pl__task-st">{{ t.progressStatusLabel || t.statusLabel || '未开始' }}</text>
            </view>
            <text v-if="t.requirement" class="pl__task-req">{{ t.requirement }}</text>
            <text v-if="t.deadline" class="pl__task-dl">截止：{{ formatDeadline(t.deadline) }}</text>
            <text v-if="t.reviewComment" :class="t.progressStatus === 'REJECTED' ? 'pl__task-reject' : 'pl__task-req'">教师意见：{{ t.reviewComment }}</text>
            <view v-if="t.evidenceFileId" class="pl__evidence">已上传任务凭证</view>
            <view v-if="canSubmit(t)" class="pl__task-act">
              <textarea v-model="t._note" class="mobile-textarea pl__input" maxlength="500" :placeholder="'填写完成说明（至少' + minimumWords + '字）'" />
              <view class="pl__file-row">
                <button class="mobile-control btn btn-secondary btn-sm" :disabled="submitting === t.sortOrder || uploading === t.sortOrder" @click="chooseEvidence(t)">
                  {{ uploading === t.sortOrder ? '上传中…' : (t._evidenceFileId ? '重新上传凭证' : '上传完成凭证') }}
                </button>
                <text class="pl__file-name" v-if="t._evidenceFileName">{{ t._evidenceFileName }}</text>
              </view>
              <button class="mobile-control btn btn-primary btn-sm pl__submit" :disabled="submitting === t.sortOrder || uploading === t.sortOrder" @click="submitTask(t)">
                {{ t.progressStatus === 'REJECTED' ? '修改后重新提交' : '提交完成情况' }}
              </button>
            </view>
            <view v-else-if="t._note || t._evidenceFileId" class="pl__task-act">
              <text>未提交内容已保留：{{ t._note }}</text><text>{{ t._evidenceFileName }}</text>
            </view>
            <text v-else-if="t.studentNote" class="pl__task-req">完成说明：{{ t.studentNote }}</text>
          </view>
        </view>
      </view>
      <view v-else class="page-pad"><MobileGlobalState state="empty" title="暂无实习计划" description="待学院发布当前批次实习计划书" /></view>
    </MobileGlobalState>
    <view v-if="pageState === 'error' && !context.internshipId" class="page-pad"><button class="mobile-control btn btn-ghost" @click="returnHome">返回实习首页</button></view>
    <MobileSafeAreaBar v-if="pageState === 'ready' && !context.historyMode && plan && plan.ackStatus === 'PENDING'">
      <button class="mobile-control btn btn-primary flex-1" :disabled="submitting !== false" @click="ack">确认已阅读当前版本计划</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import {
  studentInternshipPlans,
  studentInternshipPlan,
  studentInternshipPlanAcknowledge,
  studentInternshipPlanTasks,
  studentInternshipPlanTaskSubmit
} from '@/services/internshipApi'
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, uploadBusinessFile, openBusinessFile } from '@/services/fileApi'
import { go, toast } from '@/utils/nav'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

export default {
  data() {
    return {
      pageState: 'loading', plan: null, plans: [], selectedPlanId: '', planIndex: 0, tasks: [],
      context: {}, loadSeq: 0, expandedPlanScope: '',
      requestedBatchId: '', requestedRecordId: '', error: '', drafts: {}, minimumWords: 10,
      conflict: null, conflictReading: false, conflictReadSeq: 0,
      generation: currentSessionGeneration(), hidden: false, writeSeq: 0,
      summary: { total: 0, approved: 0, rate: 0 },
      submitting: false, uploading: false
    }
  },
  computed: {
    planDetailScope() { return [this.generation,this.context.batchId,this.context.internshipId,this.plan?.id || this.plan?.planId,this.plan?.version ?? this.plan?.planVersion].join(':') },
    planDetailsExpanded() { return this.expandedPlanScope === this.planDetailScope },
    planLabels() {
      return this.plans.map((item) => `${item.isPrimary ? '主方案 · ' : ''}${item.planTitle || '未命名方案'} · ${item.batchName || ''}`)
    }
  },
  onLoad(options = {}) { this.requestedBatchId = String(options.batchId || ''); this.requestedRecordId = String(options.internshipId || ''); this.load() },
  onHide() { this.hidden = true; this.loadSeq++; this.conflictReadSeq++; this.writeSeq++; this.conflictReading = false; this.submitting = false },
  onUnload() { this.hidden = true; this.loadSeq++; this.conflictReadSeq++ },
  onShow() { this.hidden = false; if (this.generation !== currentSessionGeneration()) {
    this.generation = currentSessionGeneration(); this.conflict = null; this.plan = null; this.tasks = []; this.context = {}; this.drafts = {}; this.plans = []; this.selectedPlanId = ''; this.uploading = false; this.submitting = false; this.load()
  } else if (this.pageState === 'loading') this.load() },
  methods: {
    async openPlanFile(file) {
      const scope = this.planDetailScope, generation = currentSessionGeneration()
      const isCurrent = () => !this.hidden && scope === this.planDetailScope && generation === currentSessionGeneration()
      if (!file?.fileId || !isCurrent()) return
      try { await openBusinessFile(String(file.fileId), file.fileName, { isCurrent }) }
      catch (e) { if (isCurrent()) toast(e?.message || '计划附件暂时无法打开，请重试') }
    },
    returnHome() { go('/pages/student-internship/index' + (this.requestedBatchId ? '?batchId=' + encodeURIComponent(this.requestedBatchId) : '')) },
    draftKey(planId, context = this.context) { return [this.generation, context.batchId, context.internshipId, planId].join(':') },
    hasTaskDraft(task) { return !task._accepted && ((task._note || '') !== (task.progressStatus === 'REJECTED' ? task.studentNote || '' : '') || (task._evidenceFileId || '') !== (task.evidenceFileId || '')) },
    rememberDrafts() {
      if (!this.plan) return
      const key = this.draftKey(this.plan.id || this.plan.planId)
      if (this.tasks.some(this.hasTaskDraft)) this.drafts[key] = { plan: this.plan, tasks: this.tasks.map(task => ({ ...task })) }
      else delete this.drafts[key]
    },
    matchesContext(data, context) { return String(data?.context?.batchId || '') === context.batchId && String(data?.context?.internshipId || '') === context.internshipId },
    async load(preferredPlanId = '') {
      if (this.conflict) return this.rereadConflict()
      this.rememberDrafts()
      const seq = ++this.loadSeq, generation = currentSessionGeneration(), batchId = this.requestedBatchId
      const current = () => !this.hidden && seq === this.loadSeq && generation === currentSessionGeneration() && batchId === this.requestedBatchId
      this.pageState = 'loading'
      this.error = ''
      try {
        const dashboard = await studentApi.getInternship(batchId)
        if (!current()) return
        if (!dashboard || typeof dashboard.hasBatch !== 'boolean') throw new Error('invalid dashboard')
        if (!dashboard.hasBatch || !dashboard.batchId || !dashboard.recordId) {
          this.plan = null; this.tasks = []; this.plans = []; this.context = {}
          this.pageState = dashboard.hasBatch ? 'error' : 'empty'
          this.error = dashboard.hasBatch ? '实习记录信息不完整，请返回首页重新选择。' : (dashboard.message || '请返回实习首页查看当前安排并选择批次。')
          return
        }
        const context = { batchId: String(dashboard.batchId), internshipId: String(dashboard.recordId), advisorName: dashboard.schoolMentor || '', historyMode: !!dashboard.historyMode }
        if ((batchId && batchId !== context.batchId) || (this.requestedRecordId && this.requestedRecordId !== context.internshipId)) throw new Error('context changed')
        const planListData = await studentInternshipPlans(context.batchId, context.internshipId)
        if (!current()) return
        if (!Array.isArray(planListData?.items) || !this.matchesContext(planListData, context)) throw new Error('invalid assigned plans')
        this.context = context
        this.plans = planListData.items
        const candidate = String(preferredPlanId || this.selectedPlanId || '')
        const selected = this.plans.find((item) => String(item.planId) === candidate)
          || this.plans.find((item) => item.isPrimary)
          || this.plans[0]
        this.selectedPlanId = selected ? String(selected.planId) : ''
        this.planIndex = Math.max(0, this.plans.findIndex((item) => String(item.planId) === this.selectedPlanId))
        if (!this.selectedPlanId) {
          this.plan = null
          this.tasks = []
          this.pageState = 'empty'
          return
        }
        const [plan, taskData] = await Promise.all([
          studentInternshipPlan(this.selectedPlanId, context.batchId, context.internshipId),
          studentInternshipPlanTasks(this.selectedPlanId, context.batchId, context.internshipId)
        ])
        if (!current()) return
        if (!this.matchesContext(plan, context) || !this.matchesContext(taskData, context) || !Array.isArray(taskData?.tasks) ||
          String(plan?.id || plan?.planId) !== this.selectedPlanId || String(taskData?.planId) !== this.selectedPlanId ||
          (plan.version ?? plan.planVersion) !== taskData.planVersion || plan.ackVersion !== taskData.ackVersion || plan.ackStatus !== taskData.ackStatus) throw new Error('plan changed during read')
        const sourceTasks = taskData.tasks
        const saved = this.drafts[this.draftKey(this.selectedPlanId, context)]
        const old = new Map((saved?.tasks || []).filter(this.hasTaskDraft).map(task => [String(task.sortOrder), task]))
        if (saved && ((saved.plan.version ?? saved.plan.planVersion) !== (plan.version ?? plan.planVersion) || [...old.values()].some(task => {
          const fresh = sourceTasks.find(row => String(row.sortOrder) === String(task.sortOrder))
          return !fresh || String(fresh.progressId) !== String(task.progressId) || fresh.progressVersion !== task.progressVersion || fresh.progressStatus !== task.progressStatus
        }))) {
          this.plan = saved.plan; this.tasks = saved.tasks; this.pageState = 'ready'; this.beginConflict(); return
        }
        this.plan = plan
        this.tasks = sourceTasks.map((t) => ({
          ...t,
          _note: old.get(String(t.sortOrder))?._note ?? (t.progressStatus === 'REJECTED' ? (t.studentNote || '') : ''),
          _evidenceFileId: old.get(String(t.sortOrder))?._evidenceFileId ?? t.evidenceFileId ?? '',
          _evidenceFileName: old.get(String(t.sortOrder))?._evidenceFileName ?? (t.evidenceFileId ? '已上传凭证' : '')
        }))
        this.summary = (taskData && taskData.summary) || (plan && plan.taskSummary) || { total: 0, approved: 0, rate: 0 }
        this.minimumWords = Math.max(1, Number(taskData?.minimumWords || 10))
        this.pageState = plan ? 'ready' : 'empty'
      } catch (e) {
        if (current()) { const error = normalizeError(e); this.pageState = error.pageState || 'error'; this.error = error.text }
      }
    },
    onPlanChange(e) {
      if (this.conflict || this.submitting !== false || this.uploading !== false) return
      const index = Number(e?.detail?.value || 0)
      const selected = this.plans[index]
      if (!selected || String(selected.planId) === this.selectedPlanId) return
      this.planIndex = index
      this.selectedPlanId = String(selected.planId)
      this.load(this.selectedPlanId)
    },
    canSubmit(t) {
      if (this.pageState !== 'ready' || this.hidden || this.context.historyMode || this.generation !== currentSessionGeneration()) return false
      if (!this.plan || this.plan.ackStatus !== 'ACKNOWLEDGED') return false
      return ['NOT_STARTED', 'REJECTED'].includes(t.progressStatus || t.status)
    },
    async ack() {
      if (this.pageState !== 'ready' || this.hidden || this.context.historyMode || this.generation !== currentSessionGeneration() || this.submitting !== false || !this.plan || this.conflict) return
      const plan = this.plan, context = this.context, generation = currentSessionGeneration(), operation = ++this.writeSeq
      const current = () => !this.hidden && operation === this.writeSeq && generation === currentSessionGeneration() && plan === this.plan && context === this.context
      this.submitting = 'ack'
      try {
        await studentInternshipPlanAcknowledge({
          ...this.context,
          planId: this.plan.id || this.plan.planId,
          expectedVersion: this.plan.ackVersion || 0,
          planVersion: this.plan.version || this.plan.planVersion
        })
        if (!current()) return
        toast('已确认当前版本实习计划')
        await this.load(this.selectedPlanId)
      } catch (e) {
        if (!current()) return
        toast((e && e.message) || '计划确认失败，请刷新后重试')
        if (normalizeError(e).kind === 'conflict') this.beginConflict()
      } finally { if (!this.hidden && operation === this.writeSeq && generation === currentSessionGeneration()) this.submitting = false }
    },
    async chooseEvidence(t) {
      if (this.uploading || !this.canSubmit(t) || this.conflict) return
      const context = this.context, plan = this.plan, generation = currentSessionGeneration()
      const current = () => generation === currentSessionGeneration() && context === this.context && plan === this.plan && this.tasks.includes(t)
      this.uploading = t.sortOrder
      try {
        const file = await chooseSingleFile()
        if (!file || !current()) return
        if (Number(file.size || 0) > 20 * 1024 * 1024) return toast('单个凭证文件不能超过20MB')
        const uploaded = await uploadBusinessFile(file, {
          bizType: 'INTERNSHIP_PLAN_TASK', bizId: t.progressId || ''
        })
        if (!current()) return
        t._evidenceFileId = uploaded.fileId
        t._evidenceFileName = uploaded.fileName || file.name || '任务凭证'
        toast('凭证上传成功')
      } catch (e) {
        if (current()) toast((e && e.message) || '凭证上传失败')
      } finally { if (current()) this.uploading = false }
    },
    async submitTask(t) {
      if (this.submitting !== false || this.uploading || this.conflict || !this.canSubmit(t)) return
      const plan = this.plan, context = this.context, generation = currentSessionGeneration(), operation = ++this.writeSeq
      const current = () => !this.hidden && operation === this.writeSeq && generation === currentSessionGeneration() && plan === this.plan && context === this.context
      const note = (t._note || '').trim()
      if (note.length < this.minimumWords) return toast('完成说明至少' + this.minimumWords + '字')
      this.submitting = t.sortOrder
      try {
        await studentInternshipPlanTaskSubmit(t.sortOrder, {
          ...this.context,
          planId: this.plan.id || this.plan.planId,
          studentNote: note,
          evidenceFileId: t._evidenceFileId || '',
          expectedVersion: t.progressVersion ?? t.version ?? 0
        })
        if (!current()) return
        t._accepted = true
        toast('已提交，等待教师确认')
        await this.load(this.selectedPlanId)
      } catch (e) {
        if (!current()) return
        toast((e && e.message) || '提交失败，请刷新后重试')
        if (normalizeError(e).kind === 'conflict') this.beginConflict()
      } finally { if (!this.hidden && operation === this.writeSeq && generation === currentSessionGeneration()) this.submitting = false }
    },
    beginConflict() {
      this.conflict = { planId: String(this.plan.id || this.plan.planId), batchId: String(this.context.batchId),
        internshipId: String(this.context.internshipId), generation: currentSessionGeneration(), latestPlan: null, taskData: null,
        error: '原计划版本、全部完成说明和凭证已保留，请读取并核对最新计划及任务后继续。' }
    },
    async rereadConflict() {
      const c = this.conflict
      if (!c || this.conflictReading) return
      const sequence = ++this.conflictReadSeq
      const current = () => !this.hidden && c === this.conflict && sequence === this.conflictReadSeq && c.generation === currentSessionGeneration() &&
        c.batchId === String(this.context.batchId) && c.internshipId === String(this.context.internshipId)
      if (!current()) return
      this.conflictReading = true; c.latestPlan = null; c.taskData = null
      try {
        const [plan, tasks, dashboard] = await Promise.all([
          studentInternshipPlan(c.planId, c.batchId, c.internshipId), studentInternshipPlanTasks(c.planId, c.batchId, c.internshipId), studentApi.getInternship(c.batchId)
        ])
        if (!current()) return
        if (dashboard?.historyMode) throw new Error('当前实习记录已转为历史只读，任务草稿保留，不能继续写入')
        if (String(plan?.id || plan?.planId) !== c.planId || String(tasks?.planId) !== c.planId ||
          (plan.version ?? plan.planVersion) !== tasks.planVersion || String(dashboard?.batchId) !== c.batchId ||
          String(plan.ackId || '') !== String(tasks.ackId || '') || plan.ackVersion !== tasks.ackVersion || plan.ackStatus !== tasks.ackStatus ||
          String(dashboard?.recordId || dashboard?.internshipId) !== c.internshipId) throw new Error('计划或本人实习记录不一致，读取期间可能又有变化，请重新读取')
        c.latestPlan = plan; c.taskData = tasks; c.error = '请核对最新计划正文和全部任务；明确采用后保留原草稿，不会自动提交。'
      } catch (e) { if (current()) c.error = e?.message || '读取失败，全部草稿已保留' }
      finally { if (sequence === this.conflictReadSeq) this.conflictReading = false }
    },
    adoptLatestPlan() {
      const c = this.conflict
      if (!c?.latestPlan || !c.taskData || this.hidden || this.conflictReading || this.submitting !== false || this.uploading !== false || c.generation !== currentSessionGeneration()) return
      if (c.batchId !== String(this.context.batchId) || c.internshipId !== String(this.context.internshipId)) return
      const fresh = c.taskData.tasks || [], old = new Map(this.tasks.map(task => [String(task.sortOrder), task]))
      if (this.tasks.some(task => !fresh.some(row => String(row.sortOrder) === String(task.sortOrder))) || fresh.some(task =>
        old.get(String(task.sortOrder))?.progressId && String(old.get(String(task.sortOrder)).progressId) !== String(task.progressId))) {
        c.error = '任务对象已调整，原完成说明和凭证保留，请核对调整情况后办理'; return
      }
      this.tasks = fresh.map(task => { const draft = old.get(String(task.sortOrder)); return { ...task,
        _note: draft?._note ?? (task.progressStatus === 'REJECTED' ? task.studentNote || '' : ''),
        _evidenceFileId: draft?._evidenceFileId ?? task.evidenceFileId ?? '',
        _evidenceFileName: draft?._evidenceFileName ?? (task.evidenceFileId ? '已上传凭证' : '') } })
      this.plan = c.latestPlan
      this.summary = c.taskData.summary || this.summary; this.minimumWords = Math.max(1, Number(c.taskData.minimumWords || 10))
      this.conflict = null
    },
    formatDeadline(v) {
      if (!v) return '—'
      const s = String(v).replace('T', ' ').slice(0, 16)
      return s.endsWith('23:59') ? s.slice(0, 10) + ' 23:59' : s
    }
  }
}
</script>

<style scoped>
.pl__switcher{display:grid;gap:8px}.pl__picker{padding:10px 12px;border:1px solid var(--border-light);border-radius:8px;background:var(--bg-card);font-size:var(--font-size-base);color:var(--text-primary)}.pl__switch-note{font-size:var(--font-size-base);color:var(--text-tertiary)}.pl__status { display:block;margin-top:6px;font-size:var(--font-size-base);color:var(--warning-600); }
.pl__facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:8px}.pl__facts>view{display:grid;gap:3px;padding:8px;border-radius:8px;background:var(--bg-subtle,#f8fafc)}.pl__facts text{font-size:var(--font-size-base);color:var(--text-tertiary)}.pl__facts .pl__fact-value{font-size:var(--font-size-base);color:var(--text-primary);font-weight:600;overflow-wrap:anywhere}.pl__fact-wide{grid-column:1/-1}.pl__score{margin-top:10px;font-size:var(--font-size-base);color:var(--text-secondary)}.pl__score-tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}.pl__score-tags text{padding:4px 7px;border-radius:999px;background:var(--primary-50,#eff6ff);color:var(--primary-700,#1d4ed8)}
.pl__prog { margin-top:10px;font-size:var(--font-size-base);color:var(--text-secondary); }
.pl__bar { height:6px;background:#e2e8f0;border-radius:3px;margin-top:6px;overflow:hidden; }
.pl__bar-in { height:100%;background:var(--primary-500,#2563eb);border-radius:3px; }
.pl__label { display:block;font-size:var(--font-size-base);font-weight:var(--font-weight-medium);margin:10px 0 4px; }
.pl__text { display:block;font-size:var(--font-size-base);color:var(--text-secondary);line-height:1.6;white-space:pre-wrap; }
.pl__task { margin-top:10px;padding:10px;background:var(--bg-subtle,#f8fafc);border-radius:8px; }
.pl__task-head { display:flex;align-items:center;gap:8px;flex-wrap:wrap; }
.pl__task-no { width:22px;height:22px;line-height:22px;text-align:center;border-radius:50%;background:var(--primary-100,#dbeafe);color:var(--primary-700,#1d4ed8);font-size:var(--font-size-base);font-weight:600; }
.pl__task-name { flex:1;font-size:var(--font-size-base);font-weight:var(--font-weight-medium); }
.pl__task-st { font-size:var(--font-size-base);color:var(--warning-700,#b45309); }
.pl__task-req,.pl__task-dl,.pl__task-reject { display:block;margin-top:6px;font-size:var(--font-size-base);line-height:1.5; }
.pl__task-req { color:var(--text-secondary); }
.pl__task-dl { color:var(--warning-700,#b45309); }
.pl__task-reject { color:var(--danger-600,#dc2626); }
.pl__evidence { margin-top:6px;font-size:var(--font-size-base);color:var(--success-600); }
.pl__task-act { margin-top:8px; }
.pl__input { width:100%;min-height:72px;padding:8px;border:1px solid #e2e8f0;border-radius:6px;font-size:var(--font-size-base);margin-bottom:8px;box-sizing:border-box; }
.pl__file-row { display:flex;align-items:center;gap:8px;margin-bottom:8px; }
.pl__file-name { flex:1;font-size:var(--font-size-base);color:var(--text-tertiary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
.pl__submit { width:100%; }
.pl__heading{gap:12px;align-items:flex-start}.pl__heading .card-title{flex:1;min-width:0;word-break:break-word}.pl__details-toggle{display:flex;align-items:center;justify-content:space-between;width:100%;min-height:44px;margin:0;padding:0;border:0;background:transparent;color:var(--text-link);font-size:var(--font-size-base)}.pl__details-toggle::after{border:0}.pl__details{padding-top:8px}.pl__picker{min-height:44px;box-sizing:border-box}.pl__facts>view{background:transparent;padding:8px 0;border-bottom:1px solid var(--border-light);border-radius:0}</style>
