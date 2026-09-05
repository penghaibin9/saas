<template>
  <ModulePageShell
    title="过程指导"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="gp-layout">
      <aside class="gp-side" aria-label="毕设学生队列">
        <div class="gp-side__head">
          <div><span>学生队列</span><small>{{ studentOptions.length }} 人可见</small></div>
          <b v-if="current">{{ current.name }}</b>
        </div>
        <input
          v-model="studentKeyword"
          class="ie-in"
          type="search"
          aria-label="搜索毕设学生"
          :disabled="!batchStore.selectedBatchId"
          placeholder="搜索学生姓名/学号"
          @input="onKeywordInput"
        />
        <LoadingState v-if="sideLoading" text="加载学生…" />
        <ErrorState v-else-if="sideError" :description="sideError" @retry="searchStudents" />
        <EmptyState v-else-if="!studentOptions.length" title="未找到学生" :description="batchEmptyHint" />
        <ul v-else class="gp-stu-list">
          <li
            v-for="s in studentOptions"
            :key="s.id"
            class="gp-stu-item"
            :class="{ 'is-active': current && current.id === s.id }"
            tabindex="0"
            role="button"
            :aria-current="current && current.id === s.id ? 'true' : undefined"
            @click="selectStudent(s)"
            @keydown.enter.prevent="selectStudent(s)"
            @keydown.space.prevent="selectStudent(s)"
          >
            <div class="mp-cell-main">{{ s.name }}</div>
            <div class="mp-cell-sub">{{ s.studentNo }} · {{ s.advisorName || '未分配导师' }}</div>
            <div class="gp-stu-item__stage">{{ s.stageLabel || '过程指导' }}</div>
          </li>
        </ul>
      </aside>

      <main class="gp-main">
        <section v-if="current" class="gp-context" aria-label="当前处理学生">
          <div class="gp-context__avatar">{{ (current.name || '学').slice(0, 1) }}</div>
          <div class="gp-context__identity">
            <span class="gp-context__eyebrow">当前学生</span>
            <strong>{{ current.name }}</strong>
            <span>{{ current.studentNo || '未关联学号' }} · {{ current.advisorName || '未分配指导教师' }}</span>
          </div>
          <div class="gp-context__stage">{{ current.stageLabel || '过程指导' }}</div>
        </section>

        <section v-if="current" class="gp-context-board" aria-label="当前办理结论">
          <article>
            <span>当前办理</span>
            <strong>{{ workContextLabel }}</strong>
            <small>保存或取消后继续处理该生，不丢失当前页签</small>
          </article>
          <article>
            <span>最近记录</span>
            <strong>{{ recentFact }}</strong>
            <small>显示该生当前业务页签的最新记录</small>
          </article>
          <article :class="gateTone">
            <span>当前结论</span>
            <strong>{{ gateConclusion }}</strong>
            <small>{{ gateNextAction }}</small>
          </article>
        </section>

        <nav class="gp-tabs" aria-label="过程指导页签">
          <button
            v-for="item in tabOptions"
            :key="item.value"
            type="button"
            class="gp-tabs__item"
            :class="{ 'is-active': tab === item.value }"
            :aria-pressed="tab === item.value"
            @click="switchTab(item.value)"
          >{{ item.label }}</button>
        </nav>

        <EmptyState v-if="!current" title="请先从左侧选择一名毕设学生" description="选择后即可处理该生的任务书、指导记录、计划、评价和中期检查。" />

        <section v-if="current && tab === 'taskbook'" class="gp-panel" aria-label="任务书">
          <LoadingState v-if="tbLoading" />
          <ErrorState v-else-if="tbError" :description="tbError" @retry="loadTaskbook(true)" />
          <template v-else-if="taskbook && taskbook.exists">
            <div class="gp-panel__title"><div><span>当前任务书</span><strong>{{ taskbook.objective || '任务目标待补充' }}</strong></div><StatusTag :type="taskbook.statusTone" :label="taskbook.statusLabel" dot /></div>
            <div class="gp-kv"><span>版本</span><span>v{{ taskbook.taskbookVersion }}</span></div>
            <div class="gp-kv"><span>任务内容</span><span>{{ taskbook.content }}</span></div>
            <div class="gp-kv"><span>进度计划</span><span>{{ taskbook.progressPlan || '—' }}</span></div>
            <div class="gp-kv"><span>成果要求</span><span>{{ taskbook.outcomeRequirement || '—' }}</span></div>
            <div class="gp-kv"><span>下达时间</span><AppDateDisplay :value="taskbook.issuedAt || taskbook.createdAt" mode="datetime" /></div>
            <div class="gp-kv"><span>截止时间</span><AppDateDisplay :value="taskbook.deadline" mode="deadline" /></div>
            <div class="ie-actions">
              <AppPermissionButton
                :allowed="exportPdfPerm.allowed"
                :reason="exportPdfPerm.reason"
                variant="ghost"
                size="sm"
                :loading="pdfLoading"
                @click="downloadTaskbookPdf"
              >下载任务书 PDF</AppPermissionButton>
              <span v-if="taskbook.status !== 'CONFIRMED'" class="gp-waiting">等待学生在学生端确认任务书</span>
              <button v-if="taskbook.status === 'CONFIRMED' && writeEnabled" type="button" class="mp-btn" :disabled="Boolean(actionBusy)" @click="openChangeTaskbook">发起变更</button>
            </div>
            <details v-if="taskbook.history && taskbook.history.length" class="gp-history">
              <summary>历史版本 · {{ taskbook.history.length }} 个</summary>
              <div v-for="h in taskbook.history" :key="h.version" class="gp-history-item">v{{ h.version }}：{{ h.objective }}</div>
            </details>
          </template>
          <template v-else-if="!tbLoading && !tbError">
            <EmptyState title="尚未下达任务书" description="先下达任务书，学生确认后才能继续后续环节。" />
            <div v-if="writeEnabled" class="ie-actions"><button type="button" class="mp-btn mp-btn--primary" @click="openIssueTaskbook">下达任务书</button></div>
          </template>
        </section>

        <section v-if="current && tab === 'guidance'" class="gp-panel" aria-label="指导记录">
          <div class="gp-panel__toolbar"><div><strong>指导记录</strong><small>共 {{ guidanceList.length }} 条</small></div><button v-if="writeEnabled" type="button" class="mp-btn mp-btn--primary" @click="openGuidanceCreate">＋ 新增指导记录</button></div>
          <LoadingState v-if="guidanceLoading" />
          <ErrorState v-else-if="guidanceError" :description="guidanceError" @retry="loadGuidance(true)" />
          <EmptyState v-else-if="!guidanceList.length" title="暂无指导记录" description="完成一次指导后，在这里记录问题、意见和后续要求。" />
          <ul v-else class="gp-timeline">
            <li v-for="(g, index) in guidanceList" :key="g.id" class="gp-timeline-item" :class="{ 'is-latest': index === 0 }">
              <div class="gp-timeline-item__head"><span v-if="index === 0">最近一次</span><strong><AppDateDisplay :value="g.guidanceDate" mode="datetime" /> · {{ g.methodLabel }}</strong></div>
              <div class="mp-cell-sub">{{ g.content }}</div>
              <div v-if="g.issues" class="gp-issue">问题：{{ g.issues }}</div>
            </li>
          </ul>
        </section>

        <section v-if="current && tab === 'plan'" class="gp-panel" aria-label="指导计划">
          <div class="gp-panel__toolbar"><div><strong>指导计划</strong><small>共 {{ planList.length }} 条</small></div><button v-if="writeEnabled" type="button" class="mp-btn mp-btn--primary" @click="openPlanCreate">＋ 新增指导计划</button></div>
          <LoadingState v-if="planLoading" />
          <ErrorState v-else-if="planError" :description="planError" @retry="loadPlans(true)" />
          <EmptyState v-else-if="!planList.length" title="暂无指导计划" description="创建计划后，导师或学生可在执行时签到留痕。" />
          <ul v-else class="gp-timeline">
            <li v-for="p in planList" :key="p.id" class="gp-timeline-item">
              <div class="gp-timeline-item__head"><strong>{{ p.title }}</strong><StatusTag :type="p.status === 'CHECKED_IN' ? 'success' : (p.status === 'CANCELLED' ? 'danger' : 'warn')" :label="p.statusLabel" dot /></div>
              <div class="mp-cell-sub"><AppDateDisplay :value="p.planDate" mode="datetime" /> · {{ p.content || '—' }}</div>
              <div v-if="p.status === 'CHECKED_IN'" class="mp-cell-sub">签到：{{ p.checkedInBy }}（{{ p.checkinRole }}）· <AppDateDisplay :value="p.checkedInAt" mode="datetime" /></div>
              <div v-if="p.status === 'PLANNED' && writeEnabled" class="ie-actions ie-actions--left"><button type="button" class="mp-btn mp-btn--primary" :disabled="Boolean(actionBusy)" @click="doPlanCheckin(p)">导师签到</button></div>
            </li>
          </ul>
        </section>

        <section v-if="current && tab === 'eval'" class="gp-panel" aria-label="导师评价">
          <div class="gp-panel__toolbar"><div><strong>导师评价</strong><small>共 {{ evalList.length }} 条</small></div><button v-if="writeEnabled" type="button" class="mp-btn mp-btn--primary" @click="openEvalCreate">＋ 提交导师评价</button></div>
          <LoadingState v-if="evalLoading" />
          <ErrorState v-else-if="evalError" :description="evalError" @retry="loadEvals(true)" />
          <EmptyState v-else-if="!evalList.length" title="暂无导师评价" description="完成阶段指导后，可提交本阶段评价。" />
          <ul v-else class="gp-timeline">
            <li v-for="(e, index) in evalList" :key="e.id" class="gp-timeline-item" :class="{ 'is-latest': index === 0 }">
              <div class="gp-timeline-item__head"><span v-if="index === 0">最近评价</span><strong>{{ e.level }} · {{ e.score }} 分 {{ e.period ? '（' + e.period + '）' : '' }}</strong><StatusTag type="info" :label="e.statusLabel" dot /></div>
              <div class="mp-cell-sub">{{ e.content || '—' }}</div>
              <div class="mp-cell-sub">{{ e.submittedBy || '—' }} · <AppDateDisplay :value="e.submittedAt || e.createdAt" mode="datetime" /></div>
            </li>
          </ul>
        </section>

        <section v-if="current && tab === 'midterm'" class="gp-panel" aria-label="中期检查">
          <LoadingState v-if="mtLoading" />
          <ErrorState v-else-if="mtError" :description="mtError" @retry="loadMidterm(true)" />
          <template v-else-if="midterm">
            <div class="gp-panel__title"><div><span>中期检查结果</span><strong>{{ midterm.conclusionLabel || midterm.statusLabel || '待检查' }}</strong></div><StatusTag :type="midterm.statusTone" :label="midterm.statusLabel" dot /></div>
            <div v-if="midterm.checkComment" class="gp-kv"><span>检查意见</span><span>{{ midterm.checkComment }}</span></div>
            <div v-if="midterm.rectifyContent" class="gp-kv"><span>整改内容</span><span>{{ midterm.rectifyContent }}</span></div>
            <div class="gp-kv"><span>检查时间</span><AppDateDisplay :value="midterm.checkedAt || midterm.checkAt" mode="datetime" /></div>
            <div v-if="midterm.rectifyDeadline" class="gp-kv"><span>整改截止</span><AppDateDisplay :value="midterm.rectifyDeadline" mode="deadline" /></div>
            <div v-if="writeEnabled" class="ie-actions">
              <button v-if="['PENDING', 'RECTIFIED_PASS', 'CHECKED_FAIL'].includes(midterm.status)" type="button" class="mp-btn mp-btn--primary" :disabled="Boolean(actionBusy)" @click="openMidtermCheck">发起中期检查</button>
              <span v-if="midterm.status === 'RECTIFYING'" class="gp-waiting">等待学生提交整改说明</span>
              <button v-if="midterm.status === 'RECTIFY_SUBMITTED'" type="button" class="mp-btn mp-btn--primary" :disabled="Boolean(actionBusy)" @click="doReviewRectify('PASS')">整改复核通过</button>
              <button v-if="midterm.status === 'RECTIFY_SUBMITTED'" type="button" class="mp-btn mp-link--danger" :disabled="Boolean(actionBusy)" @click="doReviewRectify('FAIL')">复核不通过</button>
            </div>
          </template>
        </section>
      </main>
    </div>

    <AppPageGuide guide-key="graduation.gd-process" />
  </ModulePageShell>
</template>

<script>
/** 过程指导：按学生连续处理任务书、指导、计划、评价与中期检查；学生确认和整改由学生端完成。 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDateDisplay } from '@/components/common/date'
import { AppPageGuide, AppPermissionButton } from '@/components/common'
import { graduationTaskbookApi } from '@/modules/graduation/api/graduation-taskbook.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

const TAB_OPTIONS = [
  { value: 'taskbook', label: '任务书' },
  { value: 'guidance', label: '指导记录' },
  { value: 'plan', label: '指导计划' },
  { value: 'eval', label: '导师评价' },
  { value: 'midterm', label: '中期检查' }
]
const TAB_KEYS = TAB_OPTIONS.map((item) => item.value)
const PROCESS_CONTEXT_KEYS = ['batchId', 'studentId', 'panel', 'queue', 'source', 'returnTo']

function responseError(error, fallback) {
  return error?.message || fallback
}

export default {
  name: 'GraduationProcessView',
  components: { AppPageGuide, AppPermissionButton, ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppDateDisplay },
  props: { ctx: { type: Object, required: true } },
  setup() { return { batchStore: useGraduationBatchStore() } },
  data() {
    return {
      tabOptions: TAB_OPTIONS,
      studentKeyword: '', studentOptions: [], current: null, tab: 'taskbook',
      sideLoading: false, sideError: '', searchTimer: null, sideToken: 0, contextToken: 0,
      taskbook: null, tbLoading: false, tbError: '', tbLoadedFor: '',
      guidanceList: [], guidanceLoading: false, guidanceError: '', guidanceLoadedFor: '',
      planList: [], planLoading: false, planError: '', planLoadedFor: '',
      evalList: [], evalLoading: false, evalError: '', evalLoadedFor: '',
      midterm: null, mtLoading: false, mtError: '', mtLoadedFor: '',
      pdfLoading: false, actionBusy: ''
    }
  },
  computed: {
    writeEnabled() { return this.ctx.writeEnabled !== false && !!this.ctx.permissionReady },
    exportPdfPerm() {
      const pa = this.ctx.permissionActions?.exportTaskbookPdf || this.ctx.permissionActions?.exportStats || {}
      const allowed = !!(pa.visible && pa.allowed)
      return { allowed, reason: allowed ? '' : (pa.reason || '当前角色无任务书导出权限') }
    },
    pageSubtitle() {
      const batch = this.batchStore.selectedBatchName || '未选择批次'
      return `${batch} · 围绕同一学生连续处理任务书、指导记录、计划、评价与中期检查`
    },
    batchEmptyHint() {
      if (!this.batchStore.selectedBatchId) return '请先在顶部选择毕设批次'
      return '调整关键词重新搜索'
    },
    workContextLabel() {
      const hasQueue = Boolean(this.$route.query.queue || this.$route.query.source)
      return hasQueue ? '从原队列继续处理该生' : '当前批次 · 当前学生 · 当前页签'
    },
    recentFact() {
      if (this.tab === 'taskbook') {
        if (this.tbLoading) return '正在读取任务书…'
        if (!this.taskbook?.exists) return '尚未下达任务书'
        return `任务书 v${this.taskbook.taskbookVersion || '—'} · ${this.taskbook.statusLabel || '状态待确认'}`
      }
      if (this.tab === 'guidance') {
        if (this.guidanceLoading) return '正在读取最近指导…'
        const row = this.guidanceList[0]
        return row ? `${row.methodLabel || '指导'} · ${row.content || '已记录'}` : '尚无指导记录'
      }
      if (this.tab === 'plan') {
        if (this.planLoading) return '正在读取指导计划…'
        const row = this.planList.find((item) => item.status === 'PLANNED') || this.planList[0]
        return row ? `${row.title || '指导计划'} · ${row.statusLabel || row.status || '状态待确认'}` : '尚无指导计划'
      }
      if (this.tab === 'eval') {
        if (this.evalLoading) return '正在读取导师评价…'
        const row = this.evalList[0]
        return row ? `${row.level || '评价'} · ${row.score ?? '—'} 分` : '尚无导师评价'
      }
      if (this.tab === 'midterm') {
        if (this.mtLoading) return '正在读取中期检查…'
        return this.midterm ? `${this.midterm.statusLabel || '中期检查'} · ${this.midterm.conclusionLabel || '结论待确认'}` : '尚无中期检查'
      }
      return '请选择一个业务页签'
    },
    gateConclusion() {
      if (this.tab === 'taskbook') {
        if (!this.taskbook?.exists) return '尚未下达任务书'
        if (this.taskbook.status !== 'CONFIRMED') return '等待学生确认任务书'
        return '任务书已确认，可继续指导与中期检查'
      }
      if (this.tab === 'guidance') return this.guidanceList.length ? `已有 ${this.guidanceList.length} 条指导记录` : '尚未记录本阶段指导'
      if (this.tab === 'plan') return this.planList.some((item) => item.status === 'PLANNED') ? '存在待执行指导计划' : '当前没有待执行计划'
      if (this.tab === 'eval') return this.evalList.length ? '导师评价已提交' : '尚未提交导师评价'
      if (this.tab === 'midterm') {
        if (!this.midterm) return '中期检查尚未开始'
        if (this.midterm.status === 'RECTIFYING') return '等待学生提交整改说明'
        if (this.midterm.status === 'RECTIFY_SUBMITTED') return '学生已提交整改，等待复核'
        if (this.midterm.status === 'CHECKED_FAIL') return '中期检查未通过，需要安排整改'
        if (['CHECKED_PASS', 'RECTIFIED_PASS'].includes(this.midterm.status)) return '中期检查已通过'
        return '中期检查待处理'
      }
      return '请选择一个业务页签'
    },
    gateNextAction() {
      if (this.tab === 'taskbook') return this.taskbook?.exists ? '核对学生确认状态与截止时间' : '下一步：下达任务书'
      if (this.tab === 'guidance') return this.guidanceList.length ? '处理最近问题，必要时继续记录指导' : '下一步：新增指导记录'
      if (this.tab === 'plan') return '下一步：新建计划或完成导师签到'
      if (this.tab === 'eval') return '下一步：提交或复核导师评价'
      if (this.tab === 'midterm') return '下一步：检查、等待学生整改或完成复核'
      return ''
    },
    gateTone() {
      const text = this.gateConclusion
      if (/尚未|等待|未通过|没有|待处理/.test(text)) return 'is-warning'
      return 'is-ready'
    }
  },
  created() {
    const q = this.$route.query
    this.tab = TAB_KEYS.includes(q.panel) ? q.panel : 'taskbook'
    this.searchStudents().then(() => this.restoreRouteStudent())
  },
  beforeUnmount() {
    if (this.searchTimer) clearTimeout(this.searchTimer)
    ++this.sideToken
    ++this.contextToken
  },
  watch: {
    '$route.query': {
      deep: true,
      handler(query) {
        const panel = TAB_KEYS.includes(query.panel) ? query.panel : 'taskbook'
        if (panel !== this.tab) {
          this.tab = panel
          this.ensureTabData()
        }
        const sid = query.studentId
        if (sid && (!this.current || String(this.current.id) !== String(sid))) this.restoreRouteStudent()
      }
    },
    'batchStore.selectedBatchId'(batchId) {
      ++this.contextToken
      this.current = null
      this.clearTabCaches()
      const query = { ...this.$route.query, batchId: batchId ? String(batchId) : undefined, studentId: undefined }
      this.$router.replace({ query }).catch(() => {})
      this.searchStudents()
    }
  },
  methods: {
    onKeywordInput() {
      if (this.searchTimer) clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(() => this.searchStudents(), 300)
    },
    restoreRouteStudent() {
      const sid = this.$route.query.studentId
      if (!sid) return false
      const hit = this.studentOptions.find((student) => String(student.id) === String(sid))
      if (hit) { this.selectStudent(hit, false); return true }
      return false
    },
    async searchStudents() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.sideToken
      this.sideError = ''
      if (!batchId) {
        this.studentOptions = []
        this.sideLoading = false
        return false
      }
      this.sideLoading = true
      try {
        const res = await gdStudentApi.getStudents({ keyword: this.studentKeyword || undefined, batchId, pageSize: 50 })
        if (token !== this.sideToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return false
        if (res.code === 0) {
          this.studentOptions = Array.isArray(res.data?.list) ? res.data.list : []
          this.restoreRouteStudent()
          return true
        }
        this.studentOptions = []
        this.sideError = res.message || '学生列表加载失败'
        return false
      } catch (error) {
        if (token === this.sideToken) {
          this.studentOptions = []
          this.sideError = responseError(error, '学生列表加载失败')
        }
        return false
      } finally {
        if (token === this.sideToken) this.sideLoading = false
      }
    },
    clearTabCaches() {
      this.taskbook = null; this.tbError = ''; this.tbLoadedFor = ''
      this.guidanceList = []; this.guidanceError = ''; this.guidanceLoadedFor = ''
      this.planList = []; this.planError = ''; this.planLoadedFor = ''
      this.evalList = []; this.evalError = ''; this.evalLoadedFor = ''
      this.midterm = null; this.mtError = ''; this.mtLoadedFor = ''
    },
    selectStudent(student, syncUrl = true) {
      if (!student) return
      const changed = !this.current || String(this.current.id) !== String(student.id)
      if (changed) {
        ++this.contextToken
        this.clearTabCaches()
      }
      this.current = student
      if (syncUrl) {
        this.$router.replace({ query: { ...this.$route.query, panel: this.tab, studentId: String(student.id) } }).catch(() => {})
      }
      this.ensureTabData()
    },
    switchTab(tab) {
      if (!TAB_KEYS.includes(tab)) return
      this.tab = tab
      this.$router.replace({
        query: { ...this.$route.query, panel: tab, ...(this.current ? { studentId: String(this.current.id) } : {}) }
      }).catch(() => {})
      this.ensureTabData()
    },
    ensureTabData() {
      if (!this.current) return
      if (this.tab === 'taskbook') this.loadTaskbook()
      else if (this.tab === 'guidance') this.loadGuidance()
      else if (this.tab === 'plan') this.loadPlans()
      else if (this.tab === 'eval') this.loadEvals()
      else if (this.tab === 'midterm') this.loadMidterm()
    },
    requestContext() {
      return { studentId: this.current?.id, epoch: this.contextToken }
    },
    isCurrentRequest({ studentId, epoch }) {
      return epoch === this.contextToken && String(studentId || '') === String(this.current?.id || '')
    },
    async loadTaskbook(force = false) {
      if (!this.current) return false
      const request = this.requestContext()
      const key = String(request.studentId)
      if (!force && this.tbLoadedFor === key) return true
      this.tbLoading = true; this.tbError = ''
      try {
        const res = await graduationTaskbookApi.getTaskbook(request.studentId)
        if (!this.isCurrentRequest(request)) return false
        if (res.code === 0) { this.taskbook = res.data; this.tbLoadedFor = key; return true }
        this.taskbook = null; this.tbError = res.message || '任务书加载失败'; this.tbLoadedFor = ''
        return false
      } catch (error) {
        if (this.isCurrentRequest(request)) { this.taskbook = null; this.tbError = responseError(error, '任务书加载失败'); this.tbLoadedFor = '' }
        return false
      } finally { if (this.isCurrentRequest(request)) this.tbLoading = false }
    },
    async loadGuidance(force = false) {
      if (!this.current) return false
      const request = this.requestContext(); const key = String(request.studentId)
      if (!force && this.guidanceLoadedFor === key) return true
      this.guidanceLoading = true; this.guidanceError = ''
      try {
        const res = await graduationTaskbookApi.getGuidanceList({ gdStudentId: request.studentId, pageSize: 50 })
        if (!this.isCurrentRequest(request)) return false
        if (res.code === 0) { this.guidanceList = Array.isArray(res.data?.list) ? res.data.list : []; this.guidanceLoadedFor = key; return true }
        this.guidanceList = []; this.guidanceError = res.message || '指导记录加载失败'; this.guidanceLoadedFor = ''
        return false
      } catch (error) {
        if (this.isCurrentRequest(request)) { this.guidanceList = []; this.guidanceError = responseError(error, '指导记录加载失败'); this.guidanceLoadedFor = '' }
        return false
      } finally { if (this.isCurrentRequest(request)) this.guidanceLoading = false }
    },
    async loadPlans(force = false) {
      if (!this.current) return false
      const request = this.requestContext(); const key = String(request.studentId)
      if (!force && this.planLoadedFor === key) return true
      this.planLoading = true; this.planError = ''
      try {
        const res = await graduationTaskbookApi.getGuidancePlans({ gdStudentId: request.studentId, pageSize: 50 })
        if (!this.isCurrentRequest(request)) return false
        if (res.code === 0) { this.planList = Array.isArray(res.data?.list) ? res.data.list : []; this.planLoadedFor = key; return true }
        this.planList = []; this.planError = res.message || '指导计划加载失败'; this.planLoadedFor = ''
        return false
      } catch (error) {
        if (this.isCurrentRequest(request)) { this.planList = []; this.planError = responseError(error, '指导计划加载失败'); this.planLoadedFor = '' }
        return false
      } finally { if (this.isCurrentRequest(request)) this.planLoading = false }
    },
    async loadEvals(force = false) {
      if (!this.current) return false
      const request = this.requestContext(); const key = String(request.studentId)
      if (!force && this.evalLoadedFor === key) return true
      this.evalLoading = true; this.evalError = ''
      try {
        const res = await graduationTaskbookApi.getStudentEvals({ gdStudentId: request.studentId, pageSize: 50 })
        if (!this.isCurrentRequest(request)) return false
        if (res.code === 0) { this.evalList = Array.isArray(res.data?.list) ? res.data.list : []; this.evalLoadedFor = key; return true }
        this.evalList = []; this.evalError = res.message || '导师评价加载失败'; this.evalLoadedFor = ''
        return false
      } catch (error) {
        if (this.isCurrentRequest(request)) { this.evalList = []; this.evalError = responseError(error, '导师评价加载失败'); this.evalLoadedFor = '' }
        return false
      } finally { if (this.isCurrentRequest(request)) this.evalLoading = false }
    },
    async loadMidterm(force = false) {
      if (!this.current) return false
      const request = this.requestContext(); const key = String(request.studentId)
      if (!force && this.mtLoadedFor === key) return true
      this.mtLoading = true; this.mtError = ''
      try {
        const res = await graduationTaskbookApi.getMidterm(request.studentId)
        if (!this.isCurrentRequest(request)) return false
        if (res.code === 0) { this.midterm = res.data; this.mtLoadedFor = key; return true }
        this.midterm = null; this.mtError = res.message || '中期检查加载失败'; this.mtLoadedFor = ''
        return false
      } catch (error) {
        if (this.isCurrentRequest(request)) { this.midterm = null; this.mtError = responseError(error, '中期检查加载失败'); this.mtLoadedFor = '' }
        return false
      } finally { if (this.isCurrentRequest(request)) this.mtLoading = false }
    },
    processQuery(extra = {}) {
      const query = {}
      for (const key of PROCESS_CONTEXT_KEYS) {
        const value = this.$route.query[key]
        if (value != null && value !== '') query[key] = value
      }
      query.panel = this.tab
      if (this.batchStore.selectedBatchId) query.batchId = String(this.batchStore.selectedBatchId)
      if (this.current) query.studentId = String(this.current.id)
      return { ...query, ...extra }
    },
    openIssueTaskbook() { if (this.current) this.$router.push({ path: `/admin/graduation/process/${this.current.id}/taskbook`, query: this.processQuery() }) },
    openChangeTaskbook() { if (this.current) this.$router.push({ path: `/admin/graduation/process/${this.current.id}/taskbook`, query: this.processQuery({ mode: 'change' }) }) },
    openGuidanceCreate() { if (this.current) this.$router.push({ path: `/admin/graduation/process/${this.current.id}/guidance`, query: this.processQuery() }) },
    openPlanCreate() { if (this.current) this.$router.push({ path: `/admin/graduation/process/${this.current.id}/plan`, query: this.processQuery() }) },
    openEvalCreate() { if (this.current) this.$router.push({ path: `/admin/graduation/process/${this.current.id}/eval`, query: this.processQuery() }) },
    openMidtermCheck() { if (this.current) this.$router.push({ path: `/admin/graduation/process/${this.current.id}/midterm`, query: this.processQuery() }) },
    async downloadTaskbookPdf() {
      if (!this.current?.id || this.pdfLoading) return
      this.pdfLoading = true
      try {
        const res = await graduationTaskbookApi.downloadTaskbookPdf(this.current.id)
        if (res.code !== 0) toast.error(res.message || 'PDF 生成失败')
        else toast.success('任务书 PDF 已生成并记录下载日志')
      } catch (error) { toast.error(responseError(error, 'PDF 生成失败')) }
      finally { this.pdfLoading = false }
    },
    async doPlanCheckin(plan) {
      if (!plan?.id || this.actionBusy) return
      this.actionBusy = `plan-${plan.id}`
      try {
        const res = await graduationTaskbookApi.checkinGuidancePlan(plan.id, { method: 'MANUAL', note: '导师端签到' })
        if (res.code === 0) { toast.success('已签到'); await this.loadPlans(true) } else toast.error(res.message)
      } catch (error) { toast.error(responseError(error, '签到失败')) }
      finally { this.actionBusy = '' }
    },
    async doReviewRectify(action) {
      if (!this.current || this.actionBusy) return
      this.actionBusy = `rectify-${action}`
      try {
        const res = await graduationTaskbookApi.reviewRectification(this.current.id, { action })
        if (res.code === 0) { toast.success('已复核'); await this.loadMidterm(true) } else toast.error(res.message)
      } catch (error) { toast.error(responseError(error, '整改复核失败')) }
      finally { this.actionBusy = '' }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gp-layout{display:grid;grid-template-columns:286px minmax(0,1fr);gap:var(--space-3);align-items:start}.gp-side,.gp-main{border:1px solid var(--border-light,#e2e8f0);border-radius:12px;background:var(--card,#fff);box-shadow:0 12px 28px -28px rgba(15,23,42,.55)}.gp-side{position:sticky;top:12px;padding:12px;max-height:calc(100vh - 130px);overflow:hidden}.gp-side__head{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px}.gp-side__head>div{display:grid}.gp-side__head span{font-size:13px;font-weight:700;color:var(--text-primary)}.gp-side__head small{font-size:10px;color:var(--text-tertiary)}.gp-side__head b{max-width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:3px 7px;border-radius:999px;background:var(--primary-50,#eff6ff);color:var(--primary-700,#1d4ed8);font-size:10px}.gp-main{min-width:0;padding:14px}.gp-stu-list{list-style:none;margin:8px 0 0;padding:0;max-height:calc(100vh - 220px);overflow-y:auto}.gp-stu-item{position:relative;padding:9px 10px;border:1px solid transparent;border-radius:9px;cursor:pointer;transition:background .12s ease,border-color .12s ease}.gp-stu-item:hover{background:var(--gray-50,#f8fafc)}.gp-stu-item.is-active{background:var(--primary-50,#eff6ff);border-color:var(--primary-200,#bfdbfe);box-shadow:inset 3px 0 0 var(--primary-600,#2563eb)}.gp-stu-item:focus-visible,.gp-tabs__item:focus-visible{outline:2px solid var(--primary-400,#60a5fa);outline-offset:-2px}.gp-stu-item__stage{margin-top:3px;color:var(--primary-700,#1d4ed8);font-size:10px}.gp-context{display:flex;align-items:center;gap:10px;padding-bottom:10px;border-bottom:1px solid var(--border-light,#e2e8f0)}.gp-context__avatar{display:grid;place-items:center;width:38px;height:38px;flex:none;border-radius:50%;background:linear-gradient(145deg,var(--primary-100,#dbeafe),var(--primary-50,#eff6ff));color:var(--primary-700,#1d4ed8);font-size:17px;font-weight:700}.gp-context__identity{display:grid;min-width:0;gap:1px}.gp-context__eyebrow{color:var(--primary-600,#2563eb)!important;font-size:9px!important;font-weight:700;letter-spacing:.08em}.gp-context__identity strong{color:var(--text-primary);font-size:15px}.gp-context__identity span{overflow:hidden;color:var(--text-tertiary);font-size:11px;text-overflow:ellipsis;white-space:nowrap}.gp-context__stage{margin-left:auto;padding:4px 8px;border-radius:999px;color:var(--primary-700,#1d4ed8);background:var(--primary-50,#eff6ff);font-size:11px;white-space:nowrap}.gp-context-board{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:10px 0}.gp-context-board article{display:grid;gap:3px;min-width:0;padding:9px 10px;border:1px solid var(--border-light,#e2e8f0);border-radius:9px;background:var(--gray-50,#f8fafc)}.gp-context-board article.is-ready{border-color:var(--success-100,#d1fae5);background:var(--success-50,#ecfdf5)}.gp-context-board article.is-warning{border-color:var(--warning-100,#fef3c7);background:var(--warning-50,#fffbeb)}.gp-context-board span,.gp-context-board small{color:var(--text-tertiary);font-size:10px}.gp-context-board strong{overflow:hidden;color:var(--text-primary);font-size:12px;line-height:1.45;text-overflow:ellipsis;white-space:nowrap}.gp-tabs{display:flex;gap:2px;margin-bottom:10px;border-bottom:1px solid var(--border-light,#e2e8f0);overflow-x:auto}.gp-tabs__item{flex:none;padding:8px 11px;border:0;border-bottom:2px solid transparent;background:transparent;color:var(--text-secondary,#475569);font-size:12px;cursor:pointer}.gp-tabs__item.is-active{border-bottom-color:var(--primary-600,#2563eb);color:var(--primary-700,#1d4ed8);font-weight:700}.gp-panel{min-height:280px;font-size:13px}.gp-panel__title,.gp-panel__toolbar{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 11px;margin-bottom:8px;border:1px solid var(--primary-100,#dbeafe);border-radius:9px;background:linear-gradient(110deg,var(--primary-50,#eff6ff),#fff)}.gp-panel__title>div,.gp-panel__toolbar>div{display:grid;min-width:0}.gp-panel__title span,.gp-panel__toolbar small{color:var(--text-tertiary);font-size:10px}.gp-panel__title strong,.gp-panel__toolbar strong{overflow:hidden;color:var(--text-primary);font-size:13px;text-overflow:ellipsis;white-space:nowrap}.gp-kv{display:grid;grid-template-columns:96px minmax(0,1fr);gap:10px;padding:7px 2px;border-bottom:1px dashed var(--border-light,#eef1f6)}.gp-kv>span:first-child{color:var(--text-tertiary)}.gp-kv>span:last-child{min-width:0;white-space:pre-wrap}.gp-history{margin-top:10px;padding-top:8px;border-top:1px solid var(--border-light)}.gp-history summary{cursor:pointer;color:var(--text-secondary);font-size:12px}.gp-history-item{padding:4px 0;color:var(--text-tertiary)}.gp-timeline{list-style:none;margin:0;padding:0;display:grid;gap:7px}.gp-timeline-item{padding:10px 11px;border:1px solid var(--border-light,#e2e8f0);border-radius:9px;background:#fff}.gp-timeline-item.is-latest{border-color:var(--primary-200,#bfdbfe);background:var(--primary-50,#eff6ff)}.gp-timeline-item__head{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:5px}.gp-timeline-item__head>span{padding:2px 6px;border-radius:999px;background:var(--primary-600,#2563eb);color:#fff;font-size:9px}.gp-timeline-item__head strong{font-size:12px}.gp-issue{margin-top:5px;color:var(--danger-600,#dc2626);font-size:11px}.gp-waiting{display:inline-flex;align-items:center;min-height:30px;padding:5px 9px;border-radius:8px;background:var(--warning-50,#fffbeb);color:var(--warning-800,#92400e);font-size:11px}.ie-in{width:100%;box-sizing:border-box;padding:7px 9px;border:1px solid var(--border-base,#cbd5e1);border-radius:8px;font-size:12px}.ie-in:disabled{background:var(--gray-50);cursor:not-allowed}.ie-actions{display:flex;justify-content:flex-end;align-items:center;flex-wrap:wrap;gap:7px;margin-top:10px}.ie-actions--left{justify-content:flex-start;margin-top:7px}.mp-btn{padding:7px 13px;border:1px solid var(--border-base,#cbd5e1);border-radius:8px;background:#fff;color:var(--text-primary);font-size:12px;cursor:pointer}.mp-btn--primary{border-color:var(--primary-600,#2563eb);background:var(--primary-600,#2563eb);color:#fff}.mp-btn:disabled{cursor:not-allowed;opacity:.5}.mp-link--danger{border-color:var(--danger-500,#ef4444);color:var(--danger-600,#dc2626)}
@media(max-width:1180px){.gp-layout{grid-template-columns:240px minmax(0,1fr)}.gp-context-board{grid-template-columns:1fr}.gp-context-board strong{white-space:normal}}@media(max-width:820px){.gp-layout{grid-template-columns:1fr}.gp-side{position:static;max-height:none}.gp-stu-list{max-height:300px}}
</style>
