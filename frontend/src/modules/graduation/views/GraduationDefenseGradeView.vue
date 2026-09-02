<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <section class="dg-command" aria-label="答辩与成绩工作结论">
      <div>
        <span>{{ workModeLabel }}</span>
        <strong>{{ conclusion }}</strong>
        <small>{{ workContract }}</small>
      </div>
      <div class="dg-command__facts">
        <div><b>{{ mode === 'batch' ? batch.total : studentOptions.length }}</b><span>{{ mode === 'batch' ? '服务端台账' : '当前学生队列' }}</span></div>
        <div><b>{{ mode === 'batch' ? batch.rows.length : activeRecordCount }}</b><span>{{ mode === 'batch' ? '当前页' : '当前业务记录' }}</span></div>
        <div><b>{{ roleActionLabel }}</b><span>当前职责</span></div>
      </div>
    </section>

    <aside v-if="actionReceipt" class="dg-receipt" role="status">
      <div><strong>{{ actionReceipt.title }}</strong><span>{{ actionReceipt.result }}</span><small>{{ actionReceipt.next }}</small></div>
      <button type="button" :disabled="commandLocked" @click="actionReceipt = null">关闭</button>
    </aside>

    <EmptyState
      v-if="!hasBatch"
      title="请先选择或创建毕设批次"
      description="顶部批次条选择当前工作批次后，再处理查重、评阅、答辩评分和成绩台账。"
    />
    <template v-else>
      <div class="gp-mode" aria-label="成绩处理模式">
        <button class="gp-mode__btn" :class="{ 'is-active': mode === 'single' }" :disabled="commandLocked" @click="setMode('single')">按学生连续处理</button>
        <button v-if="canUseGradeBatch" class="gp-mode__btn" :class="{ 'is-active': mode === 'batch' }" :disabled="commandLocked" @click="setMode('batch')">成绩台账批量核对</button>
      </div>

      <div v-if="mode === 'batch' && canUseGradeBatch" class="mp-stack dg-batch" :class="{ 'is-command-locked': commandLocked }" :aria-busy="commandLocked">
        <div class="mp-tabs gp-queues" aria-label="成绩工作队列">
          <button v-for="q in batchQueues" :key="q.value" class="mp-tab" :class="{ 'is-active': batch.queue === q.value }" :disabled="commandLocked" @click="selectBatchQueue(q.value)">{{ q.label }}</button>
        </div>
        <AppSearchBox v-model="batch.keyword" placeholder="搜索学生 / 学号" :disabled="commandLocked" @search="searchGrades" />
        <ErrorState v-if="batch.error" :description="batch.error" @retry="loadGrades" />
        <LoadingState v-else-if="batch.loading" />
        <EmptyState v-else-if="!batch.rows.length" title="当前服务端队列暂无成绩记录" description="可调整队列或关键词；页面不会在当前页二次筛选冒充全量。" />
        <DataTable
          v-else
          :columns="batchColumns"
          :rows="batch.rows"
          row-key="id"
          :pagination="{ page: batch.page, pageSize: batch.pageSize, total: batch.total }"
          @page-change="changeGradePage"
        >
          <template #cell-student="{ row }"><div class="mp-cell-main">{{ row.studentName || '—' }}</div><div class="mp-cell-sub">{{ row.studentNo || '' }}</div></template>
          <template #cell-advisor="{ row }"><span :class="{ 'gp-miss': row.advisorScore == null }">{{ row.advisorScore ?? '缺' }}</span></template>
          <template #cell-reviewer="{ row }"><span :class="{ 'gp-miss': row.reviewerScore == null }">{{ row.reviewerScore ?? '缺' }}</span></template>
          <template #cell-defense="{ row }"><span :class="{ 'gp-miss': row.defenseScore == null }">{{ row.defenseScore ?? '缺' }}</span></template>
          <template #cell-total="{ row }"><b v-if="row.totalScore != null">{{ row.totalScore }}</b><span v-else class="gp-miss">未核算</span><span v-if="row.gradeLevel" class="mp-cell-sub"> {{ row.gradeLevel }}</span></template>
          <template #cell-status="{ row }"><StatusTag :type="row.statusTone" :label="row.statusLabel" dot /></template>
          <template #cell-actions="{ row }"><button class="mp-link" :disabled="commandLocked" @click="openFromBatch(row)">处理 →</button></template>
        </DataTable>
        <p class="mp-note">缺项队列、关键词、状态、总数和分页全部来自服务端；核算 → 复核 → 发布 → 撤回仍走原状态机并留痕。</p>
      </div>

      <div v-else class="gp-layout" :class="{ 'is-command-locked': commandLocked }" :aria-busy="commandLocked">
        <aside class="gp-side" aria-label="学生处理队列">
          <input v-model="studentKeyword" class="ie-in" placeholder="搜索学生姓名/学号" :disabled="commandLocked" @input="searchStudents" />
          <LoadingState v-if="sideLoading" />
          <ErrorState v-else-if="sideError" :description="sideError" @retry="searchStudents" />
          <EmptyState v-else-if="!studentOptions.length" title="未找到学生" description="当前批次与当前数据范围内没有匹配学生。" />
          <ul v-else class="gp-stu-list">
            <li
              v-for="s in studentOptions"
              :key="s.id"
              class="gp-stu-item"
              :class="{ 'is-active': current && String(current.id) === String(s.id) }"
              :tabindex="commandLocked ? -1 : 0"
              :aria-disabled="commandLocked"
              @click="selectStudent(s)"
              @keydown.enter.prevent="selectStudent(s)"
              @keydown.space.prevent="selectStudent(s)"
            >
              <div class="mp-cell-main">{{ s.name }}</div>
              <div class="mp-cell-sub">{{ s.studentNo }} · {{ s.advisorName || '未分配导师' }}</div>
            </li>
          </ul>
        </aside>

        <main class="gp-main">
          <EmptyState v-if="!current" title="请先从左侧选择一名毕设学生" description="学生、页签与批次共同组成当前工作上下文。" />
          <template v-else>
            <section class="gp-context" aria-label="当前处理学生">
              <div class="gp-context__avatar">{{ (current.name || '学').slice(0, 1) }}</div>
              <div class="gp-context__identity"><span>当前处理对象</span><strong>{{ current.name }}</strong><small>{{ current.studentNo || '未关联学号' }} · {{ current.advisorName || '未分配指导教师' }}</small></div>
              <div class="gp-context__hint">{{ currentContextHint }}</div>
            </section>

            <div class="gp-tabs" aria-label="学生业务页签">
              <button v-if="canPanel('plagiarism')" class="gp-tabs__item" :class="{ 'is-active': tab === 'plagiarism' }" :disabled="commandLocked" @click="switchTab('plagiarism')">查重记录</button>
              <button v-if="canPanel('review')" class="gp-tabs__item" :class="{ 'is-active': tab === 'review' }" :disabled="commandLocked" @click="switchTab('review')">教师评阅</button>
              <button v-if="canPanel('defense')" class="gp-tabs__item" :class="{ 'is-active': tab === 'defense' }" :disabled="commandLocked" @click="switchTab('defense')">答辩评分</button>
              <button v-if="canPanel('grade')" class="gp-tabs__item" :class="{ 'is-active': tab === 'grade' }" :disabled="commandLocked" @click="switchTab('grade')">成绩评定</button>
            </div>

            <ErrorState v-if="loadError" :description="loadError" @retry="loadActivePanel" />
            <LoadingState v-else-if="panelLoading" />

            <section v-else-if="tab === 'plagiarism' && canPanel('plagiarism')" class="gp-panel">
              <div class="gp-panel__head"><div><span>正式成果版本的查重事实</span><strong>查重记录</strong></div><button class="mp-btn mp-btn--primary" :disabled="commandLocked || !canAction('submitPlagiarism')" :title="actionReason('submitPlagiarism')" @click="doSubmitPlagiarism">发起查重</button></div>
              <ul v-if="plagiarismList.length" class="gp-timeline">
                <li v-for="p in plagiarismList" :key="p.id" class="gp-timeline-item">
                  <div class="mp-cell-main"><AppDateDisplay :value="p.submitAt" mode="datetime" /> · <StatusTag :type="p.overThreshold ? 'danger' : 'success'" :label="p.status === 'DONE' ? (p.rate || '—') : p.statusLabel" dot /></div>
                  <div v-if="p.status === 'CHECKING'" class="mp-cell-sub"><button class="mp-link" :disabled="commandLocked || !canAction('setPlagiarismResult')" :title="actionReason('setPlagiarismResult')" @click="fillResult(p)">回填结果</button></div>
                  <div v-if="p.overThreshold && !p.disputeStatus" class="mp-cell-sub"><button class="mp-link" :disabled="commandLocked" @click="doDispute(p)">申请复查</button></div>
                  <div v-if="p.disputeStatus === 'PENDING'" class="mp-cell-sub">复查申请：{{ p.disputeReason }} <button class="mp-link" :disabled="commandLocked || !canAction('reviewPlagiarismDispute')" :title="actionReason('reviewPlagiarismDispute')" @click="doDisputeReview(p, 'APPROVE')">通过</button> <button class="mp-link mp-link--danger" :disabled="commandLocked || !canAction('reviewPlagiarismDispute')" :title="actionReason('reviewPlagiarismDispute')" @click="doDisputeReview(p, 'REJECT')">驳回</button></div>
                </li>
              </ul>
              <EmptyState v-else title="暂无查重记录" description="查重结果绑定正式成果版本；超标、复查和后续准入只认服务端状态机。" />
            </section>

            <section v-else-if="tab === 'review' && canPanel('review')" class="gp-panel">
              <div class="gp-panel__head gp-panel__head--form">
                <div><span>独立评阅与回避关系</span><strong>教师评阅</strong></div>
                <div class="ie-actions"><AppGraduationMentorPicker v-model="reviewerMentorId" :query="{ qualificationStatus: 'QUALIFIED', valueMode: 'id', excludeMentorId: current?.mentorId || '', excludeTeacherName: current?.advisorName || '' }" placeholder="搜索评阅教师（自动回避该生导师）" style="width: 260px" /><button class="mp-btn mp-btn--primary" :disabled="commandLocked || !canAction('assignReview')" :title="actionReason('assignReview')" @click="doAssignReview">分配评阅</button></div>
              </div>
              <ul v-if="reviewList.length" class="gp-timeline">
                <li v-for="r in reviewList" :key="r.id" class="gp-timeline-item"><div class="mp-cell-main">{{ r.reviewerName }} · <StatusTag :type="r.statusTone" :label="r.statusLabel" dot /></div><div v-if="r.opinion" class="mp-cell-sub">评分 {{ r.score }} · {{ r.opinion }}</div><div class="ie-actions"><button v-if="['ASSIGNED', 'REVIEWING', 'RETURNED'].includes(r.status)" class="mp-link" :disabled="commandLocked || !canAction('submitReview')" :title="actionReason('submitReview')" @click="openReviewSubmit(r)">提交评阅</button><button v-if="r.status === 'COMPLETED'" class="mp-link" :disabled="commandLocked || !canAction('returnReview')" :title="actionReason('returnReview')" @click="openReviewReturn(r)">退回重评</button></div></li>
              </ul>
              <EmptyState v-else title="暂无评阅任务" />
            </section>

            <section v-else-if="tab === 'defense' && canPanel('defense')" class="gp-panel">
              <div class="gp-panel__head">
                <div><span>{{ defenseModeEyebrow }}</span><strong>{{ defenseModeTitle }}</strong></div>
                <button v-if="canEnterScore" class="mp-btn mp-btn--primary" :disabled="commandLocked" :title="enterScoreReason" @click="openScoreEntry">录入本人评分</button>
              </div>
              <ul v-if="scoreList.length" class="gp-timeline">
                <li v-for="d in scoreList" :key="d.id" class="gp-timeline-item"><div class="mp-cell-main">{{ d.judgeName }}（第{{ d.roundNo }}轮）· {{ d.absent ? '缺席' : d.score }} · <StatusTag :type="d.status === 'CONFIRMED' ? 'success' : 'warning'" :label="d.statusLabel" dot /></div><div v-if="d.absent && d.absentReason" class="mp-cell-sub">缺席说明：{{ d.absentReason }}</div></li>
              </ul>
              <EmptyState v-else title="暂无评分记录" description="本轮完整性由服务端判断；页面不根据当前列表推导确认条件。" />
              <div class="ie-actions ie-actions--footer">
                <button v-if="canConfirmScores" class="mp-btn" :disabled="commandLocked" :title="confirmScoresReason" @click="askConfirmScores">确认本轮成绩</button>
                <button v-if="canCreateSecondDefense" class="mp-btn" :disabled="commandLocked" :title="secondDefenseReason" @click="openSecondDefense">发起二次答辩</button>
              </div>
              <p class="mp-note">评委只能提交本人评分；秘书只能确认服务端判定为完整的评分轮次，不能代替评委补分。</p>
            </section>

            <section v-else-if="tab === 'grade' && canPanel('grade')" class="gp-panel">
              <div class="gp-panel__head"><div><span>核算 → 复核 → 发布 → 撤回</span><strong>成绩评定</strong></div><StatusTag v-if="grade" :type="grade.statusTone" :label="grade.statusLabel" dot /></div>
              <template v-if="grade">
                <div class="gp-grade-grid"><div><span>导师分</span><strong>{{ grade.advisorScore ?? '—' }}</strong></div><div><span>评阅分</span><strong>{{ grade.reviewerScore ?? '—' }}</strong></div><div><span>答辩分</span><strong>{{ grade.defenseScore ?? '—' }}</strong></div><div><span>综合分</span><strong>{{ grade.totalScore ?? '—' }}</strong><small>{{ grade.gradeLevel || '未定级' }}</small></div></div>
                <div class="gp-kv"><span>发布时间</span><AppDateDisplay :value="grade.publishedAt" mode="datetime" /></div>
                <div class="ie-actions ie-actions--footer">
                  <button v-if="['DRAFT', 'WITHDRAWN'].includes(grade.status)" class="mp-btn mp-btn--primary" :disabled="commandLocked || !canManageGrade" :title="manageGradeReason" @click="openCalculate">核算成绩</button>
                  <button v-if="grade.status === 'CALCULATED' && !grade.reviewedAt" class="mp-btn" :disabled="commandLocked || !canReviewGrade" :title="reviewGradeReason" @click="askGradeReview">复核通过</button>
                  <button v-if="grade.status === 'CALCULATED' && !grade.reviewedAt" class="mp-btn" :disabled="commandLocked || !canReviewGrade" :title="reviewGradeReason" @click="openReturnGrade">复核退回</button>
                  <button v-if="grade.status === 'REVIEWED'" class="mp-btn mp-btn--primary" :disabled="commandLocked || !canPublishGrade" :title="publishGradeReason" @click="askPublishGrade">发布成绩</button>
                  <button v-if="grade.status === 'PUBLISHED'" class="mp-btn mp-link--danger" :disabled="commandLocked || !canWithdrawGrade" :title="withdrawGradeReason" @click="openWithdraw">撤回</button>
                </div>
              </template>
              <EmptyState v-else title="暂无成绩记录" description="成绩生成、复核、发布和撤回顺序由服务端状态机控制。" />
            </section>
          </template>
        </main>
      </div>
    </template>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :submitting="submitting"
      @cancel="cancelConfirm"
      @confirm="executeConfirm"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSearchBox, AppGraduationMentorPicker } from '@/components/common'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppDateDisplay } from '@/components/common/date'
import { graduationDefenseGradeApi } from '@/modules/graduation/api/graduation-defense-grade.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

const PANEL_ROUTES = { plagiarism: 'graduation-plagiarism-ledger', review: 'graduation-review-tasks', defense: 'graduation-defense-scoring', grade: 'graduation-grade-ledger' }
const PANEL_PERMISSIONS = {
  plagiarism: ['graduationDesign.plagiarism.view'],
  review: ['graduationDesign.review.view'],
  defense: ['graduationDesign.defense.score', 'graduationDesign.defense.scoreConfirm'],
  grade: ['graduationDesign.grade.view']
}
const BATCH_QUEUES = [
  { value: 'LEDGER', label: '全部台账' },
  { value: 'ANY', label: '全部缺项', missingType: 'ANY' },
  { value: 'ADVISOR', label: '导师分缺失', missingType: 'ADVISOR' },
  { value: 'REVIEWER', label: '评阅分缺失', missingType: 'REVIEWER' },
  { value: 'DEFENSE', label: '答辩分缺失', missingType: 'DEFENSE' },
  { value: 'TOTAL', label: '待核算', missingType: 'TOTAL' },
  { value: 'REVIEW', label: '待复核', status: 'CALCULATED' },
  { value: 'PUBLISH', label: '待发布', status: 'REVIEWED' }
]
const EMPTY_CONFIRM = () => ({ visible: false, title: '', message: '', type: 'warning', confirmText: '确认', action: '' })
const freezeSnapshot = (value) => Object.freeze({ ...value })

export default {
  name: 'GraduationDefenseGradeView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDateDisplay, AppGraduationMentorPicker, AppSearchBox, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      studentKeyword: '',
      studentOptions: [],
      current: null,
      tab: 'plagiarism',
      mode: 'single',
      routeReady: false,
      sideLoading: false,
      sideError: '',
      loadError: '',
      panelLoading: false,
      plagiarismList: [],
      reviewList: [],
      scoreList: [],
      grade: null,
      reviewerMentorId: '',
      submitting: false,
      commandSnapshot: null,
      actionReceipt: null,
      confirm: EMPTY_CONFIRM(),
      studentLoadToken: 0,
      restoreToken: 0,
      plagiarismToken: 0,
      reviewToken: 0,
      scoreToken: 0,
      gradeToken: 0,
      batchLoadToken: 0,
      batch: { loading: false, error: '', rows: [], total: 0, page: 1, pageSize: 20, keyword: '', queue: 'LEDGER', loaded: false },
      batchQueues: BATCH_QUEUES,
      batchColumns: [
        { key: 'student', title: '学生' },
        { key: 'advisor', title: '导师分' },
        { key: 'reviewer', title: '评阅分' },
        { key: 'defense', title: '答辩分' },
        { key: 'total', title: '综合分' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '90px' }
      ]
    }
  },
  computed: {
    permissionPatterns() { return Array.isArray(this.ctx?.permissionPatterns) ? this.ctx.permissionPatterns : [] },
    hasBatch() { return Boolean(this.batchStore.selectedBatchId) },
    commandLocked() { return Boolean(this.submitting || (this.confirm.visible && this.commandSnapshot)) },
    pageTitle() { return this.$route.meta?.title || '答辩与成绩' },
    pageSubtitle() {
      if (!this.hasBatch) return '请先选择毕业设计批次'
      const batch = this.batchStore.selectedBatchName ? `${this.batchStore.selectedBatchName} · ` : ''
      return `${batch}${this.workContract}`
    },
    workModeLabel() { return this.mode === 'batch' ? '服务端成绩台账' : `按学生连续处理 · ${this.tabLabel}` },
    tabLabel() { return { plagiarism: '查重记录', review: '教师评阅', defense: '答辩评分', grade: '成绩评定' }[this.tab] || '当前业务' },
    workContract() {
      if (this.mode === 'batch') return '服务端分页与缺项队列；不在当前页二次筛选。'
      if (this.tab === 'defense') return '评委只提交本人评分；秘书只确认完整轮次，二者权限严格分离。'
      if (this.tab === 'plagiarism') return '查重绑定正式成果版本，后续准入只认服务端状态机。'
      if (this.tab === 'review') return '评阅分配、提交与退回继续调用原 canonical API。'
      return '核算 → 复核 → 发布 → 撤回顺序冻结。'
    },
    conclusion() {
      if (!this.hasBatch) return '先选择批次，再进入当前职责工作区。'
      if (this.mode === 'batch') {
        if (this.batch.loading) return '正在读取服务端成绩台账。'
        if (this.batch.error) return '成绩台账暂不可用，请按错误信息重试。'
        return `${this.activeBatchQueue().label}共 ${this.batch.total} 条；当前页 ${this.batch.rows.length} 条。`
      }
      if (!this.current) return `当前队列有 ${this.studentOptions.length} 名学生；先选择处理对象。`
      if (this.panelLoading) return `正在读取 ${this.current.name} 的${this.tabLabel}。`
      return `${this.current.name} · ${this.tabLabel} · ${this.activeRecordCount} 条当前事实。`
    },
    activeRecordCount() {
      if (this.tab === 'plagiarism') return this.plagiarismList.length
      if (this.tab === 'review') return this.reviewList.length
      if (this.tab === 'defense') return this.scoreList.length
      return this.grade ? 1 : 0
    },
    roleActionLabel() {
      if (this.$route.name === 'graduation-defense-confirmation') return '秘书确认'
      if (this.$route.name === 'graduation-defense-scoring') return '本人评分'
      if (this.$route.name === 'graduation-grade-ledger') return '成绩台账'
      if (this.$route.name === 'graduation-plagiarism-ledger') return '查重处理'
      return this.tabLabel
    },
    currentContextHint() {
      if (this.tab === 'defense') return this.$route.name === 'graduation-defense-confirmation' ? '当前仅执行完整评分轮次确认，不代替评委补分。' : '当前仅提交本人评分；可见评分不等于具有确认权限。'
      return `当前批次与学生已锁定；切换页签只加载${this.tabLabel}。`
    },
    defenseModeEyebrow() { return this.$route.name === 'graduation-defense-confirmation' ? '答辩秘书职责' : '评委本人职责' },
    defenseModeTitle() { return this.$route.name === 'graduation-defense-confirmation' ? '完整评分轮次确认' : '本人答辩评分' },
    canUseGradeBatch() { return this.canPanel('grade') },
    canEnterScore() { const pa = this.ctx.permissionActions.enterDefenseScore; return Boolean(pa?.allowed) && !this.commandLocked },
    enterScoreReason() { const pa = this.ctx.permissionActions.enterDefenseScore; return pa && !pa.allowed ? (pa.reason || '无答辩评分权限') : '' },
    canConfirmScores() { const pa = this.ctx.permissionActions.confirmDefenseScores; return Boolean(pa?.allowed) },
    confirmScoresReason() { const pa = this.ctx.permissionActions.confirmDefenseScores; return pa && !pa.allowed ? (pa.reason || '仅答辩秘书/管理员可确认成绩') : '' },
    canCreateSecondDefense() { const pa = this.ctx.permissionActions.createSecondDefense; return Boolean(pa?.allowed) },
    secondDefenseReason() { const pa = this.ctx.permissionActions.createSecondDefense; return pa && !pa.allowed ? (pa.reason || '仅答辩秘书/管理员可发起二次答辩') : '' },
    canManageGrade() { const pa = this.ctx.permissionActions.manageGrade; return Boolean(pa?.allowed) },
    manageGradeReason() { const pa = this.ctx.permissionActions.manageGrade; return pa && !pa.allowed ? (pa.reason || '无成绩管理权限') : '' },
    canReviewGrade() { const pa = this.ctx.permissionActions.reviewGrade; return Boolean(pa?.allowed) },
    reviewGradeReason() { const pa = this.ctx.permissionActions.reviewGrade; return pa && !pa.allowed ? (pa.reason || '无成绩复核权限') : '' },
    canWithdrawGrade() { const pa = this.ctx.permissionActions.withdrawGrade; return Boolean(pa?.allowed) },
    withdrawGradeReason() { const pa = this.ctx.permissionActions.withdrawGrade; return pa && !pa.allowed ? (pa.reason || '无成绩撤回权限') : '' },
    canPublishGrade() { const pa = this.ctx.permissionActions.publishGrade; return Boolean(pa?.allowed) },
    publishGradeReason() { const pa = this.ctx.permissionActions.publishGrade; return pa && !pa.allowed ? (pa.reason || '无成绩发布权限') : '' }
  },
  async created() {
    this.applyRouteState(this.$route.query)
    this.routeReady = true
    this.syncRoute()
    if (this.mode === 'batch' && this.canUseGradeBatch) await this.loadGrades()
    else await this.restoreStudentFromRoute()
    this.searchStudents()
  },
  beforeUnmount() { this.invalidateReads() },
  beforeRouteLeave(to, from, next) {
    if (this.commandLocked) {
      toast.info('当前答辩或成绩命令正在等待服务器回执，请完成后再离开')
      next(false)
      return
    }
    next()
  },
  watch: {
    '$route.query': {
      deep: true,
      async handler(query) {
        if (!this.routeReady) return
        if (this.commandLocked) {
          this.restoreCommandRoute()
          return
        }
        const previous = `${this.mode}|${this.tab}|${this.current?.id || ''}|${this.batch.queue}|${this.batch.keyword}|${this.batch.page}`
        this.applyRouteState(query)
        const current = `${this.mode}|${this.tab}|${this.current?.id || ''}|${this.batch.queue}|${this.batch.keyword}|${this.batch.page}`
        if (previous !== current) {
          if (this.mode === 'batch' && this.canUseGradeBatch) await this.loadGrades()
          else await this.restoreStudentFromRoute()
        }
      }
    },
    'batchStore.selectedBatchId'(batchId) {
      const snapshot = this.commandSnapshot
      if (snapshot) {
        if (String(batchId || '') !== String(snapshot.batchId || '')) this.batchStore.selectBatch(snapshot.batchId)
        this.restoreCommandRoute()
        return
      }
      this.invalidateReads()
      this.current = null
      this.studentOptions = []
      this.batch.loaded = false
      this.batch.page = 1
      this.actionReceipt = null
      void this.syncRoute({ batchId: batchId ? String(batchId) : undefined, studentId: undefined, page: undefined })
      this.searchStudents()
      if (this.mode === 'batch' && this.canUseGradeBatch) this.loadGrades()
    }
  },
  methods: {
    routeText(value) { return Array.isArray(value) ? String(value[0] || '') : String(value || '') },
    routePage(value) {
      const page = Number.parseInt(this.routeText(value), 10)
      return Number.isFinite(page) && page > 0 ? page : 1
    },
    invalidateReads() {
      ++this.studentLoadToken
      ++this.restoreToken
      ++this.plagiarismToken
      ++this.reviewToken
      ++this.scoreToken
      ++this.gradeToken
      ++this.batchLoadToken
    },
    hasPermission(permissionKey) { return matchPermission(this.permissionPatterns, permissionKey) },
    canPanel(panel) { return (PANEL_PERMISSIONS[panel] || []).some((permissionKey) => this.hasPermission(permissionKey)) },
    firstAllowedPanel() { return ['plagiarism', 'review', 'defense', 'grade'].find((panel) => this.canPanel(panel)) || '' },
    panelRoute(panel) {
      if (panel !== 'defense') return PANEL_ROUTES[panel]
      if (this.$route.name === 'graduation-defense-confirmation' && this.hasPermission('graduationDesign.defense.scoreConfirm')) return 'graduation-defense-confirmation'
      if (this.hasPermission('graduationDesign.defense.score')) return 'graduation-defense-scoring'
      if (this.hasPermission('graduationDesign.defense.scoreConfirm')) return 'graduation-defense-confirmation'
      return null
    },
    canAction(key) { const pa = this.ctx.permissionActions[key]; return Boolean(pa?.allowed) },
    actionReason(key) { const pa = this.ctx.permissionActions[key]; return pa && !pa.allowed ? (pa.reason || '无此操作权限') : '' },
    activeBatchQueue() { return this.batchQueues.find((item) => item.value === this.batch.queue) || this.batchQueues[0] },
    routeQueueToBatchQueue(query = {}) {
      const queue = this.routeText(query.queue).toUpperCase()
      if (BATCH_QUEUES.some((item) => item.value === queue)) return queue
      const missing = this.routeText(query.missingType).toUpperCase()
      const status = this.routeText(query.status).toUpperCase()
      if (['ANY', 'ADVISOR', 'REVIEWER', 'DEFENSE', 'TOTAL'].includes(missing)) return missing
      if (status === 'CALCULATED') return 'REVIEW'
      if (status === 'REVIEWED') return 'PUBLISH'
      if (this.routeText(query.queue) === 'grade-missing') return 'ANY'
      return 'LEDGER'
    },
    applyRouteState(query = {}) {
      const requested = this.$route.meta?.defaultPanel || this.routeText(query.panel)
      this.tab = this.canPanel(requested) ? requested : (this.firstAllowedPanel() || 'plagiarism')
      const requestedMode = this.routeText(query.mode) || (this.routeText(query.view) === 'batch' ? 'batch' : '')
      this.mode = requestedMode === 'batch' && this.canUseGradeBatch ? 'batch' : 'single'
      this.batch.queue = this.routeQueueToBatchQueue(query)
      this.batch.keyword = this.routeText(query.keyword)
      this.batch.page = this.routePage(query.page)
      const sid = this.routeText(query.studentId)
      if (!sid) this.current = null
    },
    buildRouteQuery(overrides = {}) {
      const queue = this.activeBatchQueue()
      const query = {
        ...this.$route.query,
        batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
        panel: this.tab,
        mode: this.mode,
        view: undefined,
        studentId: this.mode === 'single' ? (this.current?.id || this.routeText(this.$route.query.studentId) || undefined) : undefined,
        queue: this.mode === 'batch' ? this.batch.queue : (this.routeText(this.$route.query.queue) || 'ledger'),
        keyword: this.mode === 'batch' ? (String(this.batch.keyword || '').trim() || undefined) : undefined,
        page: this.mode === 'batch' && this.batch.page > 1 ? String(this.batch.page) : undefined,
        missingType: this.mode === 'batch' ? (queue.missingType || undefined) : this.$route.query.missingType,
        status: this.mode === 'batch' ? (queue.status || undefined) : this.$route.query.status,
        ...overrides
      }
      Object.keys(query).forEach((key) => {
        if (query[key] == null || query[key] === '') delete query[key]
      })
      return query
    },
    syncRoute(overrides = {}, routeName = this.$route.name) {
      return this.$router.replace({ name: routeName, query: this.buildRouteQuery(overrides) }).catch(() => {})
    },
    currentRouteSnapshot() { return { name: this.$route.name, query: this.buildRouteQuery() } },
    restoreCommandRoute() {
      if (!this.commandSnapshot?.route) return
      this.$router.replace(this.commandSnapshot.route).catch(() => {})
    },
    setMode(mode) {
      if (this.commandLocked || (mode === 'batch' && !this.canUseGradeBatch) || mode === this.mode) return
      this.mode = mode
      if (mode === 'batch') {
        this.batch.page = 1
        void this.syncRoute({ mode: 'batch', studentId: undefined, page: undefined }, 'graduation-grade-ledger')
        this.loadGrades()
      } else {
        void this.syncRoute({ mode: 'single', page: undefined, keyword: undefined })
        if (this.current) this.loadActivePanel()
      }
    },
    selectBatchQueue(value) {
      if (this.commandLocked || !this.canUseGradeBatch || !BATCH_QUEUES.some((item) => item.value === value)) return
      this.batch.queue = value
      this.batch.page = 1
      void this.syncRoute({ queue: value, page: undefined })
      this.loadGrades()
    },
    searchGrades() {
      if (this.commandLocked) return
      this.batch.page = 1
      void this.syncRoute({ keyword: String(this.batch.keyword || '').trim() || undefined, page: undefined })
      this.loadGrades()
    },
    changeGradePage(page) {
      if (this.commandLocked) return
      this.batch.page = page
      void this.syncRoute({ page: page > 1 ? String(page) : undefined })
      this.loadGrades()
    },
    async loadGrades() {
      const batchId = String(this.batchStore.selectedBatchId || '')
      const token = ++this.batchLoadToken
      const snapshot = { batchId, page: this.batch.page, keyword: this.batch.keyword, queue: this.batch.queue }
      const state = this.batch
      if (!this.canUseGradeBatch || !batchId) {
        state.rows = []
        state.total = 0
        state.loading = false
        return false
      }
      state.loading = true
      state.error = ''
      const queue = this.activeBatchQueue()
      try {
        const res = await graduationDefenseGradeApi.getGrades({ keyword: snapshot.keyword, status: queue.status || undefined, missingType: queue.missingType || undefined, batchId: snapshot.batchId, page: snapshot.page, pageSize: state.pageSize })
        if (
          token !== this.batchLoadToken
          || snapshot.batchId !== String(this.batchStore.selectedBatchId || '')
          || snapshot.page !== this.batch.page
          || snapshot.keyword !== this.batch.keyword
          || snapshot.queue !== this.batch.queue
        ) return false
        if (res.code === 0) {
          state.rows = Array.isArray(res.data?.list) ? res.data.list : []
          state.total = Number(res.data?.total) || 0
          state.loaded = true
          return true
        }
        state.rows = []
        state.total = 0
        state.error = res.message || '成绩台账加载失败'
      } catch (error) {
        if (token === this.batchLoadToken) {
          state.rows = []
          state.total = 0
          state.error = error?.message || '成绩台账加载失败'
        }
      } finally {
        if (token === this.batchLoadToken) state.loading = false
      }
      return false
    },
    openFromBatch(row) {
      if (this.commandLocked || !this.canUseGradeBatch || !row?.gdStudentId) return
      this.mode = 'single'
      this.tab = 'grade'
      this.current = { id: String(row.gdStudentId), name: row.studentName, studentNo: row.studentNo, advisorName: row.advisorName }
      void this.syncRoute({ mode: 'single', studentId: String(row.gdStudentId), panel: 'grade' }, 'graduation-grade-ledger')
      this.loadActivePanel()
    },
    switchTab(tab) {
      if (this.commandLocked || !this.canPanel(tab)) return
      const routeName = this.panelRoute(tab)
      if (!routeName) return
      this.tab = tab
      void this.syncRoute({ panel: tab, mode: 'single' }, routeName)
      this.loadActivePanel()
    },
    async searchStudents() {
      const batchId = String(this.batchStore.selectedBatchId || '')
      const keyword = this.studentKeyword
      const token = ++this.studentLoadToken
      this.sideError = ''
      if (!batchId) {
        this.studentOptions = []
        this.sideLoading = false
        return false
      }
      this.sideLoading = true
      try {
        const res = await gdStudentApi.getStudents({ keyword, batchId, pageSize: 20 })
        if (token !== this.studentLoadToken || batchId !== String(this.batchStore.selectedBatchId || '') || keyword !== this.studentKeyword) return false
        if (res.code === 0) {
          this.studentOptions = Array.isArray(res.data?.list) ? res.data.list : []
          return true
        }
        this.studentOptions = []
        this.sideError = res.message || '学生列表加载失败'
      } catch (error) {
        if (token === this.studentLoadToken) {
          this.studentOptions = []
          this.sideError = error?.message || '学生列表加载失败'
        }
      } finally {
        if (token === this.studentLoadToken) this.sideLoading = false
      }
      return false
    },
    async restoreStudentFromRoute() {
      const sid = this.routeText(this.$route.query.studentId)
      const batchId = String(this.batchStore.selectedBatchId || '')
      const token = ++this.restoreToken
      if (!sid || !batchId) {
        this.current = null
        return false
      }
      try {
        const res = await gdStudentApi.getStudentDetail(sid)
        if (token !== this.restoreToken || batchId !== String(this.batchStore.selectedBatchId || '') || sid !== this.routeText(this.$route.query.studentId)) return false
        if (res.code !== 0) {
          this.current = null
          this.sideError = res.message || '学生上下文加载失败'
          return false
        }
        const student = res.data?.student || res.data || {}
        const studentBatchId = String(student.batchId || '')
        if (batchId && studentBatchId && batchId !== studentBatchId) {
          this.current = null
          this.sideError = '当前批次与学生上下文不一致，请返回后重新选择学生'
          return false
        }
        this.current = { id: sid, name: student.name || '', studentNo: student.studentNo || '', advisorName: student.advisorName || '', mentorId: student.mentorId || null }
        await this.loadActivePanel()
        return true
      } catch (error) {
        if (token === this.restoreToken) {
          this.current = null
          this.sideError = error?.message || '学生上下文加载失败'
        }
        return false
      }
    },
    selectStudent(student) {
      if (this.commandLocked || !student) return
      this.current = { ...student }
      void this.syncRoute({ studentId: String(student.id), mode: 'single' })
      this.loadActivePanel()
    },
    async loadActivePanel() {
      this.loadError = ''
      if (!this.current || !this.canPanel(this.tab)) return false
      if (this.tab === 'plagiarism') return this.loadPlagiarism()
      if (this.tab === 'review') return this.loadReview()
      if (this.tab === 'defense') return this.loadScores()
      if (this.tab === 'grade') return this.loadGrade()
      return false
    },
    async loadPlagiarism() {
      const snapshot = { batchId: String(this.batchStore.selectedBatchId), studentId: String(this.current.id), tab: this.tab }
      const token = ++this.plagiarismToken
      this.panelLoading = true
      try {
        const res = await graduationDefenseGradeApi.getPlagiarismList({ gdStudentId: snapshot.studentId, batchId: snapshot.batchId, pageSize: 50 })
        if (token !== this.plagiarismToken || !this.isCurrentSnapshot(snapshot)) return false
        if (res.code === 0) this.plagiarismList = Array.isArray(res.data?.list) ? res.data.list : []
        else { this.plagiarismList = []; this.loadError = res.message || '查重记录加载失败' }
        return res.code === 0
      } finally { if (token === this.plagiarismToken) this.panelLoading = false }
    },
    async loadReview() {
      const snapshot = { batchId: String(this.batchStore.selectedBatchId), studentId: String(this.current.id), tab: this.tab }
      const token = ++this.reviewToken
      this.panelLoading = true
      try {
        const res = await graduationDefenseGradeApi.getReviewList({ gdStudentId: snapshot.studentId, batchId: snapshot.batchId, pageSize: 50 })
        if (token !== this.reviewToken || !this.isCurrentSnapshot(snapshot)) return false
        if (res.code === 0) this.reviewList = Array.isArray(res.data?.list) ? res.data.list : []
        else { this.reviewList = []; this.loadError = res.message || '评阅记录加载失败' }
        return res.code === 0
      } finally { if (token === this.reviewToken) this.panelLoading = false }
    },
    async loadScores() {
      const snapshot = { batchId: String(this.batchStore.selectedBatchId), studentId: String(this.current.id), tab: this.tab }
      const token = ++this.scoreToken
      this.panelLoading = true
      try {
        const res = await graduationDefenseGradeApi.getScoreList({ gdStudentId: snapshot.studentId, batchId: snapshot.batchId, pageSize: 50 })
        if (token !== this.scoreToken || !this.isCurrentSnapshot(snapshot)) return false
        if (res.code === 0) this.scoreList = Array.isArray(res.data?.list) ? res.data.list : []
        else { this.scoreList = []; this.loadError = res.message || '评分记录加载失败' }
        return res.code === 0
      } finally { if (token === this.scoreToken) this.panelLoading = false }
    },
    async loadGrade() {
      const snapshot = { batchId: String(this.batchStore.selectedBatchId), studentId: String(this.current.id), tab: this.tab }
      const token = ++this.gradeToken
      this.panelLoading = true
      try {
        const res = await graduationDefenseGradeApi.getGrade(snapshot.studentId)
        if (token !== this.gradeToken || !this.isCurrentSnapshot(snapshot)) return false
        if (res.code === 0) this.grade = res.data || null
        else { this.grade = null; this.loadError = res.message || '成绩加载失败' }
        return res.code === 0
      } finally { if (token === this.gradeToken) this.panelLoading = false }
    },
    isCurrentSnapshot(snapshot) {
      return snapshot.batchId === String(this.batchStore.selectedBatchId || '') && snapshot.studentId === String(this.current?.id || '') && snapshot.tab === this.tab
    },
    createCommandSnapshot(action, extra = {}) {
      return freezeSnapshot({
        action,
        batchId: String(this.batchStore.selectedBatchId || ''),
        studentId: String(this.current?.id || ''),
        panel: this.tab,
        route: this.currentRouteSnapshot(),
        ...extra
      })
    },
    async runCommand(snapshot, task, success) {
      if (this.commandLocked || !snapshot?.batchId || !snapshot?.studentId) return false
      this.commandSnapshot = snapshot
      this.submitting = true
      try {
        const res = await task(snapshot)
        if (res.code === 0) {
          await this.loadActivePanel()
          this.actionReceipt = success(res, snapshot)
          toast.success(this.actionReceipt.title)
          return true
        }
        toast.error(res.message || '操作失败')
      } catch (error) {
        toast.error(error?.message || '操作失败，请按服务器最新状态核对')
      } finally {
        this.submitting = false
        this.commandSnapshot = null
      }
      return false
    },
    doSubmitPlagiarism() {
      if (!this.canAction('submitPlagiarism')) return
      const snapshot = this.createCommandSnapshot('SUBMIT_PLAGIARISM')
      return this.runCommand(snapshot,
        (ctx) => graduationDefenseGradeApi.submitPlagiarism(ctx.studentId),
        (_res, ctx) => ({ title: '查重已提交', result: `服务器已接收学生 ${ctx.studentId} 的查重任务。`, next: '后续状态以查重台账回读为准。' }))
    },
    openForm(formKey, recordId = '') {
      if (!this.current || this.commandLocked) return
      this.$router.push({
        name: 'graduation-defense-grade-student-form',
        params: { studentId: String(this.current.id) },
        query: {
          formKey,
          recordId: recordId || undefined,
          panel: this.tab,
          batchId: this.batchStore.selectedBatchId,
          studentId: String(this.current.id),
          mode: this.mode,
          view: this.mode === 'batch' ? 'batch' : undefined,
          queue: this.mode === 'batch' ? this.batch.queue : (this.$route.query.queue || 'ledger'),
          keyword: this.mode === 'batch' ? (this.batch.keyword || undefined) : undefined,
          page: this.mode === 'batch' && this.batch.page > 1 ? String(this.batch.page) : undefined,
          missingType: this.$route.query.missingType,
          status: this.$route.query.status,
          source: this.$route.query.source,
          returnTo: this.$route.query.returnTo,
          returnRoute: this.$route.name
        }
      })
    },
    fillResult(row) { this.openForm('plagiarismResult', row.id) },
    doDispute(row) { this.openForm('dispute', row.id) },
    doDisputeReview(row, action) {
      if (!this.canAction('reviewPlagiarismDispute')) return
      const snapshot = this.createCommandSnapshot('REVIEW_PLAGIARISM_DISPUTE', { recordId: row.id, reviewAction: action })
      return this.runCommand(snapshot,
        (ctx) => graduationDefenseGradeApi.reviewDispute(ctx.recordId, ctx.reviewAction, ctx.reviewAction === 'REJECT' ? '维持原查重结果' : '核实无误'),
        (_res, ctx) => ({ title: '查重复查已审核', result: `服务器已记录 ${ctx.reviewAction === 'APPROVE' ? '通过' : '驳回'} 结论。`, next: '后续准入继续由服务端状态机判断。' }))
    },
    doAssignReview() {
      if (!this.canAction('assignReview')) return
      if (!this.reviewerMentorId) {
        toast.error('请选择评阅教师')
        return
      }
      const snapshot = this.createCommandSnapshot('ASSIGN_REVIEW', { reviewerMentorId: this.reviewerMentorId })
      return this.runCommand(snapshot,
        (ctx) => graduationDefenseGradeApi.assignReview(ctx.studentId, null, ctx.reviewerMentorId),
        (_res, ctx) => {
          this.reviewerMentorId = ''
          return { title: '评阅任务已分配', result: `服务器已为学生 ${ctx.studentId} 建立正式评阅任务。`, next: '下一步由被分配教师提交评阅。' }
        })
    },
    openReviewSubmit(row) { this.openForm('reviewSubmit', row.id) },
    openReviewReturn(row) { this.openForm('reviewReturn', row.id) },
    openScoreEntry() { if (this.canEnterScore) this.openForm('scoreEntry') },
    askConfirmScores() {
      if (!this.canConfirmScores || this.commandLocked || !this.current) return
      this.commandSnapshot = this.createCommandSnapshot('CONFIRM_SCORES')
      this.confirm = { visible: true, title: '确认本轮答辩成绩', message: `确认「${this.current.name}」当前评分轮次？完整性、缺席说明和轮次条件由服务端最终校验；秘书不能代替评委补分。`, type: 'warning', confirmText: '确认本轮', action: 'CONFIRM_SCORES' }
    },
    openSecondDefense() { if (this.canCreateSecondDefense) this.openForm('secondDefense') },
    openCalculate() { if (this.canManageGrade) this.openForm('calculate') },
    askGradeReview() {
      if (!this.canReviewGrade || this.commandLocked || !this.current) return
      this.commandSnapshot = this.createCommandSnapshot('REVIEW_GRADE')
      this.confirm = { visible: true, title: '成绩复核通过', message: `确认「${this.current.name}」当前成绩复核通过？服务端会再次校验状态顺序。`, type: 'warning', confirmText: '复核通过', action: 'REVIEW_GRADE' }
    },
    openReturnGrade() { if (this.canReviewGrade) this.openForm('returnGrade') },
    askPublishGrade() {
      if (!this.canPublishGrade || this.commandLocked || !this.current) return
      this.commandSnapshot = this.createCommandSnapshot('PUBLISH_GRADE')
      this.confirm = { visible: true, title: '发布成绩', message: `确认发布「${this.current.name}」的毕业设计成绩？发布后学生可见，正式状态只认服务端回执。`, type: 'warning', confirmText: '确认发布', action: 'PUBLISH_GRADE' }
    },
    openWithdraw() { if (this.canWithdrawGrade) this.openForm('withdraw') },
    cancelConfirm() {
      if (!this.submitting) this.commandSnapshot = null
      this.confirm = EMPTY_CONFIRM()
    },
    async executeConfirm() {
      const snapshot = this.commandSnapshot
      if (!snapshot || this.submitting) return
      this.confirm = EMPTY_CONFIRM()
      if (snapshot.action === 'CONFIRM_SCORES') {
        await this.runCommand(snapshot,
          (ctx) => graduationDefenseGradeApi.confirmScores(ctx.studentId),
          (_res, ctx) => ({ title: '本轮成绩已确认', result: `服务器已确认学生 ${ctx.studentId} 的完整评分轮次。`, next: '下一步进入成绩核算；页面未替代评委补分。' }))
      } else if (snapshot.action === 'REVIEW_GRADE') {
        await this.runCommand(snapshot,
          (ctx) => graduationDefenseGradeApi.reviewGrade(ctx.studentId, { action: 'APPROVE' }),
          (_res) => ({ title: '成绩复核已通过', result: '服务器已回读 REVIEWED 状态。', next: '下一步由授权角色发布成绩。' }))
      } else if (snapshot.action === 'PUBLISH_GRADE') {
        await this.runCommand(snapshot,
          (ctx) => graduationDefenseGradeApi.publishGrade(ctx.studentId),
          (_res) => ({ title: '成绩已发布', result: '服务器已回读 PUBLISHED 状态。', next: '如需撤回，必须填写原因并走原状态机。' }))
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dg-command { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-4); align-items: center; margin-bottom: var(--space-3); padding: 12px 14px; border: 1px solid var(--primary-100, #dbeafe); border-radius: var(--radius-lg, 12px); background: linear-gradient(120deg, var(--primary-50, #eff6ff), var(--bg-card, #fff) 76%); }
.dg-command > div:first-child { display: grid; min-width: 0; gap: 2px; }
.dg-command > div:first-child > span { color: var(--primary-600, #2563eb); font-size: 10px; font-weight: 700; letter-spacing: .08em; }
.dg-command strong { color: var(--text-primary, #0f172a); font-size: 14px; }
.dg-command small { color: var(--text-tertiary, #64748b); font-size: 10px; line-height: 1.5; }
.dg-command__facts { display: flex; align-items: stretch; }
.dg-command__facts div { display: grid; min-width: 90px; gap: 1px; padding: 2px 12px; border-left: 1px solid var(--primary-100, #dbeafe); }
.dg-command__facts b { overflow: hidden; color: var(--text-primary, #0f172a); font-size: 16px; text-overflow: ellipsis; white-space: nowrap; }
.dg-command__facts span { color: var(--text-tertiary, #64748b); font-size: 9px; }
.dg-receipt { display: flex; align-items: center; gap: 14px; margin-bottom: var(--space-3); padding: 11px 12px; border: 1px solid var(--success-200, #bbf7d0); border-radius: 9px; background: var(--success-50, #f0fdf4); }
.dg-receipt div { display: grid; flex: 1; gap: 2px; }
.dg-receipt strong { color: var(--success-700, #15803d); }
.dg-receipt span, .dg-receipt small { color: var(--text-secondary, #475569); font-size: 10px; }
.dg-receipt button { border: 0; background: transparent; color: var(--primary-600, #2563eb); cursor: pointer; }
.gp-mode { display: inline-flex; margin-bottom: var(--space-3); overflow: hidden; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); box-shadow: 0 1px 2px rgba(15, 23, 42, .04); }
.gp-mode__btn { padding: 8px 16px; border: 0; background: var(--bg-card, #fff); color: var(--text-secondary, #475569); cursor: pointer; font-size: 12px; }
.gp-mode__btn:hover:not(:disabled):not(.is-active) { background: var(--bg-subtle, #f8fafc); }
.gp-mode__btn.is-active { background: var(--primary-600, #2563eb); color: #fff; font-weight: 600; }
.gp-mode__btn:disabled { cursor: not-allowed; opacity: .55; }
.gp-layout { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: var(--space-3); align-items: start; }
.gp-side, .gp-main { min-width: 0; padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-lg, 10px); background: var(--bg-card, #fff); }
.ie-in { width: 100%; box-sizing: border-box; padding: 8px 10px; border: 1px solid var(--border-light, #d9dee8); border-radius: 8px; background: var(--bg-card, #fff); color: var(--text-primary, #0f172a); font-size: 12px; }
.gp-stu-list { display: grid; gap: 4px; max-height: 630px; margin: 9px 0 0; padding: 0; overflow-y: auto; list-style: none; }
.gp-stu-item { padding: 8px 9px; border: 1px solid transparent; border-radius: 7px; cursor: pointer; }
.gp-stu-item:hover { background: var(--bg-subtle, #f8fafc); }
.gp-stu-item.is-active { border-color: var(--primary-200, #bfdbfe); background: var(--primary-50, #eff6ff); box-shadow: inset 3px 0 0 var(--primary-600, #2563eb); }
.gp-stu-item:focus-visible, .gp-tabs__item:focus-visible, .gp-mode__btn:focus-visible { outline: 2px solid var(--primary-400, #60a5fa); outline-offset: 2px; }
.gp-context { display: grid; grid-template-columns: 38px minmax(0, 1fr) minmax(220px, .55fr); gap: 10px; align-items: center; margin-bottom: 9px; padding: 9px 11px; border: 1px solid var(--primary-100, #dbeafe); border-radius: 9px; background: var(--primary-50, #eff6ff); }
.gp-context__avatar { display: grid; width: 34px; height: 34px; place-items: center; border-radius: 10px; background: var(--primary-600, #2563eb); color: #fff; font-weight: 700; }
.gp-context__identity { display: grid; min-width: 0; gap: 1px; }
.gp-context__identity > span { color: var(--primary-600, #2563eb); font-size: 9px; font-weight: 700; letter-spacing: .06em; }
.gp-context__identity strong, .gp-context__identity small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.gp-context__identity strong { color: var(--text-primary, #0f172a); font-size: 13px; }
.gp-context__identity small, .gp-context__hint { color: var(--text-secondary, #475569); font-size: 10px; }
.gp-context__hint { line-height: 1.5; }
.gp-tabs { display: flex; gap: var(--space-1); margin-bottom: var(--space-3); border-bottom: 1px solid var(--border-light, #e2e8f0); }
.gp-tabs__item { padding: 8px 14px; border: 0; border-bottom: 2px solid transparent; background: transparent; color: var(--text-secondary, #475569); cursor: pointer; font-size: 12px; }
.gp-tabs__item.is-active { border-bottom-color: var(--primary-600, #2563eb); color: var(--primary-600, #2563eb); font-weight: 700; }
.gp-tabs__item:disabled { cursor: not-allowed; opacity: .5; }
.gp-panel { min-height: 280px; }
.gp-panel__head { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 9px; padding-bottom: 8px; border-bottom: 1px solid var(--border-light, #e2e8f0); }
.gp-panel__head > div:first-child { display: grid; gap: 1px; }
.gp-panel__head span { color: var(--primary-600, #2563eb); font-size: 9px; font-weight: 700; }
.gp-panel__head strong { color: var(--text-primary, #0f172a); font-size: 13px; }
.gp-panel__head--form { align-items: flex-end; }
.gp-timeline { display: grid; gap: 7px; margin: 0; padding: 0; list-style: none; }
.gp-timeline-item { padding: 9px 10px; border: 1px solid var(--border-light, #e2e8f0); border-radius: 8px; background: var(--bg-subtle, #f8fafc); }
.mp-cell-main { color: var(--text-primary, #0f172a); font-size: 12px; font-weight: 600; }
.mp-cell-sub { margin-top: 2px; color: var(--text-tertiary, #64748b); font-size: 10px; }
.ie-actions { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-2); }
.ie-actions--footer { margin-top: var(--space-3); }
.gp-grade-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 7px; margin-bottom: 9px; }
.gp-grade-grid > div { display: grid; gap: 2px; padding: 10px; border: 1px solid var(--border-light, #e2e8f0); border-radius: 8px; background: var(--bg-subtle, #f8fafc); }
.gp-grade-grid span, .gp-grade-grid small { color: var(--text-tertiary, #64748b); font-size: 9px; }
.gp-grade-grid strong { color: var(--text-primary, #0f172a); font-size: 18px; }
.gp-kv { display: flex; justify-content: space-between; gap: 10px; padding: 7px 0; border-bottom: 1px solid var(--border-light, #e2e8f0); font-size: 11px; }
.gp-miss { color: var(--danger-600, #dc2626); font-weight: 700; }
.mp-link { padding: 0; border: 0; background: transparent; color: var(--primary-600, #2563eb); cursor: pointer; font-size: 11px; }
.mp-link:disabled { cursor: not-allowed; opacity: .5; }
.mp-link--danger { color: var(--danger-600, #dc2626); }
.mp-btn { padding: 7px 14px; border: 1px solid var(--border-light, #d9dee8); border-radius: 8px; background: var(--bg-card, #fff); color: var(--text-primary, #0f172a); cursor: pointer; font-size: 11px; }
.mp-btn--primary { border-color: var(--primary-600, #2563eb); background: var(--primary-600, #2563eb); color: #fff; }
.mp-btn:disabled { cursor: not-allowed; opacity: .5; }
.is-command-locked { pointer-events: none; opacity: .74; }
@media (max-width: 1000px) { .gp-layout { grid-template-columns: 1fr; } .gp-side { max-height: 300px; } .gp-stu-list { max-height: 210px; } .gp-context { grid-template-columns: 38px minmax(0, 1fr); } .gp-context__hint { grid-column: 1 / -1; } }
@media (max-width: 760px) { .dg-command { grid-template-columns: 1fr; } .dg-command__facts { overflow-x: auto; } .dg-command__facts div:first-child { border-left: 0; padding-left: 0; } .gp-grade-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .gp-panel__head, .gp-panel__head--form { align-items: stretch; flex-direction: column; } }
</style>
