<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="g && !g.hasBatch">
        <MobileGlobalState state="empty" title="当前暂无毕业设计任务" description="进入毕业设计阶段后，这里会显示课题、任务书、开题、中期、答辩等节点。" />
      </view>
      <view class="page-pad stack" v-else-if="g">
        <!-- 课题卡 -->
        <view class="gd__hero card">
          <text class="gd__hero-batch">{{ g.batch }}</text>
          <text class="gd__hero-topic">{{ g.topic }}</text>
          <text class="gd__hero-mentor">指导教师 · {{ g.mentor }}</text>
        </view>

        <!-- 当前主任务 -->
        <MobileActionCard
          :title="g.primaryAction.title"
          :description="g.primaryAction.desc"
          icon="→"
          :action-text="g.primaryAction.actionText"
          @action="submitNode"
          @click="submitNode"
        />
        <MobileInlineAlert v-if="g.returnedNote" type="danger" title="材料被退回" :description="g.returnedNote" />

        <!-- 节点进度 -->
        <view class="section-head"><text class="section-head__title">毕设节点</text></view>
        <view class="card"><MobileTimeline :nodes="g.nodes" /></view>

        <!-- 选题管理：未选题→浏览题目库提交志愿；已选题→申请更换课题 -->
        <view v-if="activeRound" class="section-head">
          <text class="section-head__title">选题管理</text>
          <text class="section-head__more">{{ activeRound.roundName }} · 最多{{ activeRound.maxChoices }}志愿</text>
        </view>

        <view v-if="activeRound && myChoices.length" class="card stack-sm">
          <view v-for="c in myChoices" :key="c.id" class="gd__choice-row">
            <text class="gd__choice-title">{{ c.topicTitle }}</text>
            <MobileStatusTag :label="choiceLabel(c.status)" :type="choiceTag(c.status)" />
          </view>
          <button v-if="canWithdraw" class="btn btn-ghost" :disabled="withdrawing" @click="withdrawChoices">
            {{ withdrawing ? '退选中…' : '退选（撤回志愿后可重填）' }}
          </button>
        </view>

        <view v-if="activeRound && !g.hasTopic" class="card stack-sm">
          <text class="gd__hint">从题目库选择 1~{{ activeRound.maxChoices }} 个志愿，按点选顺序确定志愿序：</text>
          <view v-for="t in topics" :key="t.id" class="gd__topic-row" @click="toggleChoice(t.id)">
            <view class="gd__topic-main">
              <text class="gd__topic-title">{{ t.title }}</text>
              <text class="gd__topic-sub">{{ t.advisorName || '—' }} · 余量 {{ t.remaining }}/{{ t.capacity }}</text>
            </view>
            <text v-if="choiceRank(t.id)" class="gd__topic-badge">志愿{{ choiceRank(t.id) }}</text>
          </view>
          <button class="btn btn-primary" :disabled="!selectedChoices.length || choiceSubmitting"
                  @click="submitChoices">
            {{ choiceSubmitting ? '提交中…' : `提交志愿（已选${selectedChoices.length}）` }}
          </button>
        </view>

        <view v-if="activeRound && g.hasTopic" class="card stack-sm">
          <button class="btn btn-ghost" @click="showChangeForm = !showChangeForm">
            {{ showChangeForm ? '收起' : '申请更换课题' }}
          </button>
          <template v-if="showChangeForm">
            <text class="gd__hint">获批课题已锁定，更换须重新审核，请选择目标课题并说明理由：</text>
            <view v-for="t in topics" :key="t.id" class="gd__topic-row" @click="changeTargetTopicId = t.id">
              <view class="gd__topic-main">
                <text class="gd__topic-title">{{ t.title }}</text>
                <text class="gd__topic-sub">{{ t.advisorName || '—' }} · 余量 {{ t.remaining }}/{{ t.capacity }}</text>
              </view>
              <text v-if="changeTargetTopicId === t.id" class="gd__topic-badge">已选</text>
            </view>
            <textarea class="gd__reason" v-model="changeReason" :maxlength="200" placeholder="变更理由（至少5个字）" placeholder-class="wr__ph" />
            <button class="btn btn-primary" :disabled="!changeTargetTopicId || changeSubmitting" @click="submitChangeRequest">
              {{ changeSubmitting ? '提交中…' : '提交变更申请' }}
            </button>
          </template>
          <view v-if="changeRequests.length" class="stack-sm">
            <view v-for="r in changeRequests" :key="r.id" class="gd__choice-row">
              <text class="gd__choice-title">{{ r.oldTopicTitle }} → {{ r.newTopicTitle }}</text>
              <MobileStatusTag :label="r.statusLabel" :type="changeTag(r.status)" />
            </view>
          </view>
        </view>

        <!-- 开题报告 -->
        <view v-if="proposal && proposal.hasData" class="section-head"><text class="section-head__title">开题报告</text></view>
        <view v-if="proposal && proposal.hasData" class="card stack-sm">
          <view v-if="proposal.latest" class="gd__choice-row">
            <text class="gd__choice-title">{{ proposal.latest.version }} · {{ proposal.latest.statusLabel }}</text>
            <MobileStatusTag :label="proposal.latest.statusLabel"
                             :type="proposal.latest.status === 'APPROVED' ? 'success' : proposal.latest.status === 'REJECTED' ? 'danger' : 'warning'" />
          </view>
          <MobileInlineAlert v-if="proposal.latest && proposal.latest.status === 'REJECTED' && proposal.latest.reviewComment"
                             type="danger" title="开题被驳回" :description="proposal.latest.reviewComment" />
          <text v-if="!proposal.canSubmit && proposal.reason" class="gd__hint">{{ proposal.reason }}</text>
          <button v-if="proposal.canSubmit && !showProposalForm" class="btn btn-primary" @click="startProposal">
            {{ proposal.latest && proposal.latest.status === 'REJECTED' ? '修改后重交开题报告' : '提交开题报告' }}
          </button>
          <template v-if="proposal.canSubmit && showProposalForm">
            <textarea class="gd__reason" v-model="propForm.background" :maxlength="2000" placeholder="选题背景（必填）" placeholder-class="wr__ph" />
            <textarea class="gd__reason" v-model="propForm.plan" :maxlength="2000" placeholder="研究方案与进度（必填）" placeholder-class="wr__ph" />
            <textarea class="gd__reason" v-model="propForm.outcome" :maxlength="2000" placeholder="预期成果（选填）" placeholder-class="wr__ph" />
            <button class="btn btn-primary" :disabled="!propForm.background.trim() || !propForm.plan.trim() || proposalSubmitting" @click="submitProposal">
              {{ proposalSubmitting ? '提交中…' : '提交开题报告' }}
            </button>
          </template>
        </view>

        <!-- 任务书 -->
        <view v-if="taskbook && taskbook.exists" class="section-head"><text class="section-head__title">任务书</text></view>
        <view v-if="taskbook && taskbook.exists" class="card stack-sm">
          <view class="gd__choice-row"><text class="gd__choice-title">v{{ taskbook.taskbookVersion }} · {{ taskbook.objective }}</text><MobileStatusTag :label="taskbook.statusLabel" :type="taskbook.status === 'CONFIRMED' ? 'success' : 'warning'" /></view>
          <button v-if="taskbook.status !== 'CONFIRMED'" class="btn btn-primary" :disabled="taskbookSubmitting" @click="confirmTaskbook">
            {{ taskbookSubmitting ? '提交中…' : '确认任务书' }}
          </button>
        </view>

        <!-- 中期检查 -->
        <view v-if="midterm && midterm.hasData && midterm.status !== 'PENDING'" class="section-head"><text class="section-head__title">中期检查</text></view>
        <view v-if="midterm && midterm.hasData && midterm.status !== 'PENDING'" class="card stack-sm">
          <view class="gd__choice-row"><text class="gd__choice-title">{{ midterm.conclusionLabel || midterm.statusLabel }}</text><MobileStatusTag :label="midterm.statusLabel" :type="midterm.status === 'RECTIFYING' ? 'danger' : 'success'" /></view>
          <template v-if="midterm.status === 'RECTIFYING'">
            <textarea class="gd__reason" v-model="rectifyContent" :maxlength="500" placeholder="填写整改内容后提交" placeholder-class="wr__ph" />
            <button class="btn btn-primary" :disabled="!rectifyContent.trim() || rectifySubmitting" @click="submitRectify">
              {{ rectifySubmitting ? '提交中…' : '提交整改' }}
            </button>
          </template>
        </view>

        <!-- 成果提交（论文初稿/定稿） -->
        <view v-if="final && final.hasData" class="section-head"><text class="section-head__title">成果提交</text></view>
        <view v-if="final && final.hasData" class="card stack-sm">
          <view v-for="it in final.items" :key="it.id" class="gd__choice-row">
            <text class="gd__choice-title">{{ it.type }} {{ it.version }} · 查重 {{ it.plagiarismRate }}</text>
            <MobileStatusTag :label="it.statusLabel"
                             :type="it.status === 'APPROVED' ? 'success' : it.status === 'REJECTED' ? 'danger' : 'warning'" />
          </view>
          <MobileInlineAlert v-if="finalRejected" type="danger" title="成果被退回" :description="finalRejected" />
          <text class="gd__hint">{{ final.hint }}</text>
          <button v-if="final.canSubmitDraft" class="btn btn-primary" :disabled="finalSubmitting" @click="submitFinal('初稿')">
            {{ finalSubmitting ? '提交中…' : '提交论文初稿' }}
          </button>
          <button v-if="final.canSubmitFinal" class="btn btn-primary" :disabled="finalSubmitting" @click="submitFinal('定稿')">
            {{ finalSubmitting ? '提交中…' : '提交论文定稿' }}
          </button>
        </view>

        <!-- 答辩安排 -->
        <view v-if="defense && defense.assigned" class="section-head"><text class="section-head__title">答辩安排</text></view>
        <view v-if="defense && defense.assigned" class="card stack-sm">
          <view class="gd__choice-row">
            <text class="gd__choice-title">{{ defense.groupName }}</text>
            <MobileStatusTag :label="defense.published ? '已发布' : '编制中'" :type="defense.published ? 'success' : 'warning'" />
          </view>
          <template v-if="defense.published">
            <text class="gd__hint">时间：{{ defense.date }} · 地点：{{ defense.location }}</text>
            <text class="gd__hint">组长：{{ defense.chair }} · 秘书：{{ defense.secretary }}</text>
            <text class="gd__hint">评委：{{ (defense.members || []).join('、') || '待安排' }}</text>
          </template>
          <text v-else class="gd__hint">{{ defense.message }}</text>
        </view>

        <!-- 成绩 -->
        <view v-if="grade && grade.published" class="section-head"><text class="section-head__title">毕设成绩</text></view>
        <view v-if="grade && grade.published" class="card stack-sm">
          <view class="gd__choice-row"><text class="gd__choice-title">综合成绩 {{ grade.totalScore }} 分（{{ grade.gradeLevel }}）</text></view>
          <button v-if="!showAppeal" class="btn btn-ghost" @click="showAppeal = true">对成绩有异议？发起更正申诉</button>
          <template v-else>
            <textarea class="gd__reason" v-model="appealReason" :maxlength="500" placeholder="申诉理由（至少5字）" placeholder-class="wr__ph" />
            <button class="btn btn-primary" :disabled="appealReason.trim().length < 5 || appealSubmitting" @click="submitAppeal">
              {{ appealSubmitting ? '提交中…' : '提交申诉' }}
            </button>
          </template>
        </view>

        <!-- 指导记录 -->
        <view class="section-head"><text class="section-head__title">指导记录</text></view>
        <view class="card stack-sm">
          <view v-for="l in g.guideLogs" :key="l.id" class="gd__log">
            <view class="gd__log-head">
              <text class="gd__log-from">{{ l.from }}</text>
              <text class="gd__log-date">{{ l.date }}</text>
            </view>
            <text class="gd__log-text">{{ l.text }}</text>
          </view>
        </view>

        <!-- 功能入口 -->
        <view class="section-head"><text class="section-head__title">毕设功能</text></view>
        <view class="gd__entries card">
          <text v-for="e in g.entries" :key="e" class="gd__entry" @click="toast(e + '：入口即将开放')">{{ e }}</text>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const choiceLock = createSubmitLock(1500)
const changeLock = createSubmitLock(1500)

const CHOICE_LABEL = { PENDING: '待处理', MATCHED: '已匹配', UNMATCHED: '未录取', CONFIRMED: '已确认', REJECTED: '已驳回' }
const CHOICE_TAG = { PENDING: 'warning', MATCHED: 'success', UNMATCHED: 'default', CONFIRMED: 'success', REJECTED: 'danger' }
const CHANGE_TAG = { PENDING: 'warning', APPROVED: 'success', REJECTED: 'danger', CANCELLED: 'default' }

export default {
  data() {
    return {
      g: null, state: 'loading',
      topics: [], activeRound: null, changeRequests: [],
      selectedChoices: [], choiceSubmitting: false, withdrawing: false,
      showChangeForm: false, changeTargetTopicId: '', changeReason: '', changeSubmitting: false,
      proposal: null, showProposalForm: false, proposalSubmitting: false,
      propForm: { background: '', plan: '', outcome: '' },
      final: null, finalSubmitting: false,
      taskbook: null, taskbookSubmitting: false,
      midterm: null, rectifyContent: '', rectifySubmitting: false,
      defense: null, grade: null,
      showAppeal: false, appealReason: '', appealSubmitting: false
    }
  },
  computed: {
    myChoices() { return (this.activeRound && this.activeRound.myChoices) || [] },
    canWithdraw() {
      // 进行中轮次 + 存在待处理志愿（已确认/匹配的不可自助退选）
      return this.activeRound && this.myChoices.some((c) => c.status === 'PENDING') &&
        !this.myChoices.some((c) => c.status === 'CONFIRMED' || c.status === 'MATCHED')
    },
    finalRejected() {
      const items = (this.final && this.final.items) || []
      const r = items.find((i) => i.status === 'REJECTED')
      return r && r.reviewComment ? r.reviewComment : ''
    }
  },
  onLoad() { this.load() },
  methods: {
    toast,
    load() {
      this.state = 'loading'
      studentApi.getGraduation().then((d) => {
        this.g = d
        this.state = 'ready'
        if (d && d._real && d.hasBatch) {
          this.loadTopicSelection()
          this.loadProcess()
        }
      }).catch(() => { this.state = 'error' })
    },
    loadProcess() {
      studentApi.getGraduationProposal().then((d) => { this.proposal = d }).catch(() => {})
      studentApi.getGraduationFinal().then((d) => { this.final = d }).catch(() => {})
      studentApi.getGraduationTaskbook().then((d) => { this.taskbook = d }).catch(() => {})
      studentApi.getGraduationMidterm().then((d) => { this.midterm = d }).catch(() => {})
      studentApi.getGraduationDefense().then((d) => { this.defense = d }).catch(() => {})
      studentApi.getGraduationGrade().then((d) => { this.grade = d }).catch(() => {})
    },
    startProposal() {
      this.showProposalForm = true
      const l = this.proposal && this.proposal.latest
      // 重交时预填上一版内容，便于修改
      if (l) { this.propForm = { background: l.background || '', plan: l.plan || '', outcome: l.outcome || '' } }
    },
    submitProposal() {
      const f = this.propForm
      if (!f.background.trim() || !f.plan.trim() || this.proposalSubmitting) return
      this.proposalSubmitting = true
      studentApi.submitGraduationProposal({
        background: f.background.trim(), plan: f.plan.trim(), outcome: f.outcome.trim()
      }).then(() => {
        uni.showToast({ title: '开题报告已提交', icon: 'success' })
        this.showProposalForm = false
        this.propForm = { background: '', plan: '', outcome: '' }
        this.loadProcess()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.proposalSubmitting = false })
    },
    submitAppeal() {
      const reason = this.appealReason.trim()
      if (reason.length < 5 || this.appealSubmitting) return
      this.appealSubmitting = true
      studentApi.appealGraduationGrade(reason).then(() => {
        uni.showToast({ title: '申诉已提交', icon: 'success' })
        this.showAppeal = false
        this.appealReason = ''
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.appealSubmitting = false })
    },
    submitFinal(finalType) {
      if (this.finalSubmitting) return
      this.finalSubmitting = true
      studentApi.submitGraduationFinal({ finalType }).then(() => {
        uni.showToast({ title: finalType + '已提交', icon: 'success' })
        this.loadProcess()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.finalSubmitting = false })
    },
    confirmTaskbook() {
      if (this.taskbookSubmitting) return
      this.taskbookSubmitting = true
      studentApi.confirmGraduationTaskbook().then(() => {
        uni.showToast({ title: '已确认', icon: 'success' })
        this.loadProcess()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '确认失败，请稍后重试') })
        .finally(() => { this.taskbookSubmitting = false })
    },
    submitRectify() {
      const content = this.rectifyContent.trim()
      if (!content || this.rectifySubmitting) return
      this.rectifySubmitting = true
      studentApi.submitGraduationMidtermRectify(content).then(() => {
        uni.showToast({ title: '整改已提交', icon: 'success' })
        this.rectifyContent = ''
        this.loadProcess()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.rectifySubmitting = false })
    },
    loadTopicSelection() {
      studentApi.getGraduationActiveRound().then((r) => {
        this.activeRound = r || null
        if (r) return studentApi.getGraduationTopics()
        return null
      }).then((t) => { if (t) this.topics = t }).catch(() => { /* 选题为增量能力，静默降级不影响主页 */ })
      if (this.g && this.g.hasTopic) {
        studentApi.getMyGraduationChangeRequests().then((r) => { this.changeRequests = r || [] }).catch(() => {})
      }
    },
    choiceRank(topicId) {
      const i = this.selectedChoices.indexOf(topicId)
      return i >= 0 ? i + 1 : 0
    },
    toggleChoice(topicId) {
      const i = this.selectedChoices.indexOf(topicId)
      if (i >= 0) { this.selectedChoices.splice(i, 1); return }
      const max = (this.activeRound && this.activeRound.maxChoices) || 3
      if (this.selectedChoices.length >= max) { toast(`最多选择 ${max} 个志愿`); return }
      this.selectedChoices.push(topicId)
    },
    submitChoices() {
      if (!this.selectedChoices.length || this.choiceSubmitting) return
      const choices = this.selectedChoices.map((topicId, i) => ({ topicId, choiceOrder: i + 1 }))
      this.choiceSubmitting = true
      choiceLock.run(() => studentApi.submitGraduationChoices(this.activeRound.id, choices)).then(() => {
        uni.showToast({ title: '志愿已提交', icon: 'success' })
        this.selectedChoices = []
        this.loadTopicSelection()
      }).catch((e) => {
        if (e && e.code === 'LOCKED') return
        toast(e && e.biz ? normalizeError(e).text : '网络异常，提交未成功，请稍后重试')
      }).finally(() => { this.choiceSubmitting = false })
    },
    withdrawChoices() {
      if (this.withdrawing || !this.activeRound) return
      this.withdrawing = true
      studentApi.withdrawGraduationChoices(this.activeRound.id).then(() => {
        uni.showToast({ title: '已退选', icon: 'success' })
        this.loadTopicSelection()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '退选失败，请稍后重试') })
        .finally(() => { this.withdrawing = false })
    },
    submitChangeRequest() {
      if (!this.changeTargetTopicId || this.changeSubmitting) return
      const reason = this.changeReason.trim()
      if (reason.length < 5) { toast('变更理由至少 5 个字'); return }
      this.changeSubmitting = true
      changeLock.run(() => studentApi.requestGraduationTopicChange(this.changeTargetTopicId, reason)).then(() => {
        uni.showToast({ title: '变更申请已提交', icon: 'success' })
        this.showChangeForm = false
        this.changeTargetTopicId = ''
        this.changeReason = ''
        this.loadTopicSelection()
      }).catch((e) => {
        if (e && e.code === 'LOCKED') return
        toast(e && e.biz ? normalizeError(e).text : '网络异常，提交未成功，请稍后重试')
      }).finally(() => { this.changeSubmitting = false })
    },
    choiceLabel(status) { return CHOICE_LABEL[status] || status },
    choiceTag(status) { return CHOICE_TAG[status] || 'default' },
    changeTag(status) { return CHANGE_TAG[status] || 'default' },
    submitNode() { toast('「' + this.g.primaryAction.title + '」材料上传请在 PC 端毕设中心完成') }
  }
}
</script>

<style scoped>
.gd__hero-batch { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.gd__hero-topic { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); margin: 6px 0; line-height: 1.4; }
.gd__hero-mentor { font-size: var(--font-size-sm); color: var(--text-secondary); }
.gd__log { border-left: 3px solid var(--primary-100); padding-left: var(--space-3); }
.gd__log-head { display: flex; align-items: center; justify-content: space-between; }
.gd__log-from { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--brand-primary); }
.gd__log-date { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.gd__log-text { display: block; font-size: var(--font-size-base); color: var(--text-secondary); margin-top: 4px; line-height: 1.5; }
.gd__entries { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.gd__entry { font-size: var(--font-size-sm); color: var(--text-secondary); background: var(--gray-50); border: 1px solid var(--border-base); padding: 7px 12px; border-radius: var(--radius-md); }
.gd__hint { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: var(--space-2); }
.gd__choice-row { display: flex; align-items: center; justify-content: space-between; }
.gd__choice-title { font-size: var(--font-size-base); color: var(--text-primary); }
.gd__topic-row { display: flex; align-items: center; justify-content: space-between; padding: var(--space-3) 0; border-bottom: 1px solid var(--border-light); }
.gd__topic-row:last-of-type { border-bottom: none; }
.gd__topic-main { display: flex; flex-direction: column; gap: 2px; }
.gd__topic-title { font-size: var(--font-size-base); color: var(--text-primary); font-weight: var(--font-weight-medium); }
.gd__topic-sub { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.gd__topic-badge { flex-shrink: 0; font-size: var(--font-size-xs); color: #fff; background: var(--brand-primary); padding: 3px 10px; border-radius: var(--radius-full); }
.gd__reason { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; margin: var(--space-2) 0; }
</style>
