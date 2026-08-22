<template>
  <div class="w74-center">
    <section class="w74-summary" aria-label="评阅中心摘要">
      <button v-for="card in summaryCards" :key="card.key" type="button" class="w74-summary__card" @click="applySummaryCard(card)">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.hint }}</small>
      </button>
    </section>

    <section class="w74-toolbar" aria-label="评阅队列筛选">
      <div class="w74-filter-group">
        <span class="w74-filter-label">材料类型</span>
        <button
          v-for="item in caseOptions" :key="item.value" type="button"
          :class="['w74-chip', { 'is-active': filters.caseType === item.value }]"
          @click="setCaseType(item.value)"
        >{{ item.label }}</button>
      </div>
      <div class="w74-filter-group">
        <span class="w74-filter-label">队列状态</span>
        <button
          v-for="item in statusOptions" :key="item.value" type="button"
          :class="['w74-chip', { 'is-active': filters.statusGroup === item.value }]"
          @click="setStatusGroup(item.value)"
        >{{ item.label }}</button>
      </div>
      <div class="w74-toolbar__search">
        <input v-model.trim="filters.keyword" type="search" placeholder="学生 / 学号 / 班级 / 课题" @input="scheduleReload" />
        <label><input v-model="filters.reviewerOnly" type="checkbox" @change="reloadFromFirstPage" /> 只看分配给我的正式评阅</label>
        <button type="button" class="w74-refresh" :disabled="loading" @click="loadAll({ preserveSelection: true })">刷新</button>
      </div>
    </section>

    <div v-if="error" class="w74-state w74-state--error">
      <strong>评阅中心加载失败</strong><span>{{ error }}</span><button type="button" @click="loadAll()">重试</button>
    </div>
    <div v-else-if="loading && !queue.length" class="w74-state">正在加载评阅队列…</div>
    <div v-else-if="!queue.length" class="w74-state">
      <strong>当前筛选下没有评阅任务</strong><span>可以切换材料类型、队列状态或取消“只看我的”。</span>
    </div>

    <GraduationDocumentReviewWorkspace
      v-else
      queue-title="统一评阅队列"
      :queue="queue" :current-index="activeIndex" :current-record="currentRecord" :detail="detail"
      :files="previewFiles" :versions="previewFiles" :evidence-versions="previewFiles"
      :canonical-file-version-id="targetFileVersionId" :review-ready="taskReviewReady"
      :expected-version="expectedVersion" :comment="form.opinion" :submitting="submitting"
      :auto-next="autoNext" mode="final" :provider="previewProvider" :descriptor="previewDescriptor"
      :active-file-key="activeFileKey" :active-version-id="activeVersionId"
      :version-conflict="versionConflict" :allow-download="false"
      @select="selectTask" @previous="move(-1)" @next="move(1)"
      @select-file="selectPreview" @select-version="selectPreview"
      @update:auto-next="autoNext = $event" @reload="reloadCurrent({ preserveDraft: true })"
      @open-student-dossier="openStudentDossier"
    >
      <template #queue-footer>
        <div class="w74-pagination">
          <button type="button" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
          <span>{{ page }} / {{ pageCount }} · {{ total }} 条</span>
          <button type="button" :disabled="page >= pageCount" @click="changePage(page + 1)">下一页</button>
        </div>
      </template>

      <template #review>
        <div v-if="loadingDetail" class="w74-review-loading">正在读取当前任务的 canonical 写入上下文…</div>
        <template v-else-if="activeTask && detail">
          <div class="w74-case-head">
            <span class="w74-case-type">{{ caseLabel(activeTask.caseType) }}</span>
            <span :class="['w74-status', `is-${String(activeTask.statusGroup || '').toLowerCase()}`]">{{ activeTask.statusLabel || activeTask.status }}</span>
            <span v-if="activeTask.overdue" class="w74-overdue">已逾期</span>
          </div>

          <div v-if="activeTask.blockingReasons?.length" class="w74-blockers">
            <strong>当前阻断</strong>
            <ul><li v-for="item in activeTask.blockingReasons" :key="item.code">{{ item.message }}</li></ul>
          </div>
          <div v-if="activeVersionId && targetFileVersionId && String(activeVersionId) !== String(targetFileVersionId)" class="w74-history-lock">
            当前正在阅读历史 FileVersion {{ activeVersionId }}。历史版本只读；切回任务目标 FileVersion {{ targetFileVersionId }} 后才能提交。
          </div>
          <p v-if="formError" class="w74-form-error">{{ formError }}</p>

          <section class="w74-feedback">
            <div class="w74-section-title"><strong>历史反馈</strong><span>{{ feedbackHistory.length }} 条</span></div>
            <div v-if="!feedbackHistory.length" class="w74-muted">暂无历史批阅反馈</div>
            <div v-else class="w74-feedback-list">
              <article v-for="item in feedbackHistory" :key="item.id || `${item.stage}-${item.roundNo}`">
                <div><b>{{ item.result || item.stage }}</b><span>第 {{ item.roundNo || '—' }} 轮</span></div>
                <p>{{ item.summary || '未填写文字意见' }}</p>
                <small>FileVersion {{ item.fileVersionId || '—' }} · {{ item.createdAt || '' }}</small>
              </article>
            </div>
          </section>

          <section v-if="canShowWriteForm" class="w74-write-form">
            <div class="w74-section-title"><strong>结构化反馈</strong><span>草稿绑定当前任务 + FileVersion</span></div>
            <div class="w74-category-list">
              <button
                v-for="item in categoryOptions" :key="item" type="button"
                :class="['w74-category', { 'is-active': form.categories.includes(item) }]"
                @click="toggleCategory(item)"
              >{{ item }}</button>
            </div>
            <label class="w74-field">
              <span>问题清单 <small>每行一项</small></span>
              <textarea v-model="form.issuesText" rows="3" placeholder="例如：第 3 章论证与数据结论不一致" @input="saveDraft"></textarea>
            </label>
            <label v-if="activeTask.caseType === 'FORMAL_REVIEW'" class="w74-field">
              <span>评阅评分 <small>0–100</small></span>
              <input v-model="form.score" type="number" min="0" max="100" step="1" @input="saveDraft" />
            </label>
            <label class="w74-field">
              <span>{{ activeTask.caseType === 'FORMAL_REVIEW' ? '评阅意见' : '批阅意见' }}</span>
              <textarea v-model="form.opinion" rows="5" placeholder="写明结论、主要问题和修改建议…" @input="saveDraft"></textarea>
            </label>

            <div v-if="canSubmitFormal" class="w74-actions">
              <button type="button" class="w74-primary" :disabled="!canSubmitCurrent || submitting" @click="submitFormal">提交正式评阅</button>
            </div>
            <div v-else-if="canReviewBusiness" class="w74-actions w74-actions--two">
              <button type="button" class="w74-primary" :disabled="!canSubmitCurrent || submitting" @click="submitBusiness('APPROVE')">通过当前版本</button>
              <button type="button" class="w74-warning" :disabled="!canSubmitCurrent || submitting" @click="submitBusiness('REJECT')">退回修改</button>
            </div>
          </section>

          <section v-if="canReturnFormalAction" class="w74-return-form">
            <div class="w74-section-title"><strong>退回重评</strong><span>仅已完成正式评阅</span></div>
            <label class="w74-field"><span>退回原因</span><textarea v-model="form.returnReason" rows="3" placeholder="至少 5 个字" @input="saveDraft"></textarea></label>
            <button type="button" class="w74-warning" :disabled="!canReturnFormal || submitting" @click="returnFormal">退回重评</button>
          </section>
        </template>
      </template>
    </GraduationDocumentReviewWorkspace>

    <div v-if="dossierOpen" class="w74-modal" role="dialog" aria-modal="true" aria-label="学生完整档案" @click.self="closeDossier">
      <section class="w74-modal__panel">
        <header><div><small>学生完整档案</small><strong>{{ dossier?.name || dossier?.studentName || currentRecord?.studentName || '学生' }}</strong></div><button type="button" @click="closeDossier">×</button></header>
        <div v-if="dossierLoading" class="w74-state">正在读取学生档案…</div>
        <div v-else-if="dossierError" class="w74-state w74-state--error">{{ dossierError }}</div>
        <div v-else class="w74-dossier-grid">
          <div><span>学号</span><b>{{ dossier?.studentNo || currentRecord?.studentNo || '—' }}</b></div>
          <div><span>班级</span><b>{{ dossier?.className || currentRecord?.className || '—' }}</b></div>
          <div><span>课题</span><b>{{ dossier?.topicTitle || currentRecord?.topicTitle || '—' }}</b></div>
          <div><span>指导教师</span><b>{{ dossier?.advisorName || currentRecord?.advisorName || '—' }}</b></div>
          <div><span>当前阶段</span><b>{{ dossier?.stageLabel || dossier?.stage || '—' }}</b></div>
          <div><span>风险</span><b>{{ dossier?.riskLevel || '—' }}</b></div>
        </div>
        <footer><button type="button" class="w74-primary" @click="closeDossier">返回评阅中心</button></footer>
      </section>
    </div>
  </div>
</template>

<script>
import GraduationDocumentReviewWorkspace from '@/modules/graduation/components/GraduationDocumentReviewWorkspace.vue'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMaterialCenterApi } from '@/modules/graduation/api/graduation-material-center.api'
import { graduationReviewCenterApi } from '@/modules/graduation/api/graduation-review-center.api'
import { toast } from '@/utils/toast'

const CASE_OPTIONS = [
  { value: '', label: '全部' }, { value: 'PROPOSAL', label: '开题' },
  { value: 'FINAL_DRAFT', label: '初稿' }, { value: 'FINAL', label: '定稿' },
  { value: 'FORMAL_REVIEW', label: '正式评阅' }
]
const STATUS_OPTIONS = [
  { value: '', label: '全部' }, { value: 'RETURNED', label: '退回优先' },
  { value: 'WAITING', label: '待处理' }, { value: 'IN_REVIEW', label: '处理中' },
  { value: 'BLOCKED', label: '有阻断' }, { value: 'DONE', label: '已完成' }
]
const CATEGORY_OPTIONS = ['内容质量', '结构逻辑', '格式规范', '引用规范', '创新与工作量']

function errorMessage(error, fallback = '操作失败，请稍后重试') {
  return error?.message || error?.details?.message || fallback
}

export default {
  name: 'GraduationReviewCenterView',
  components: { GraduationDocumentReviewWorkspace },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      caseOptions: CASE_OPTIONS, statusOptions: STATUS_OPTIONS, categoryOptions: CATEGORY_OPTIONS,
      loading: false, loadingDetail: false, error: '', formError: '',
      summary: {}, queue: [], total: 0, page: 1, pageSize: 50,
      filters: { caseType: '', statusGroup: '', keyword: '', reviewerOnly: false },
      activeIndex: 0, activeTask: null, detail: null, writeContext: null,
      activeFileKey: null, activeVersionId: null,
      previewProvider: graduationMaterialCenterApi.createPreviewProvider(),
      autoNext: true, submitting: false, selectionToken: 0, searchTimer: null,
      form: { score: '', opinion: '', categories: [], issuesText: '', returnReason: '' },
      dossierOpen: false, dossierLoading: false, dossierError: '', dossier: null
    }
  },
  computed: {
    summaryCards() {
      return [
        { key: 'pending', label: '待处理', value: this.summary.pending ?? '—', hint: '含阻断项', status: 'WAITING' },
        { key: 'inReview', label: '处理中', value: this.summary.inReview ?? '—', hint: '正式评阅进行中', status: 'IN_REVIEW' },
        { key: 'returned', label: '已退回', value: this.summary.returned ?? '—', hint: '最高业务优先级', status: 'RETURNED' },
        { key: 'doneToday', label: '今日完成', value: this.summary.doneToday ?? '—', hint: '今日已处理', status: 'DONE' },
        { key: 'overdue', label: '逾期', value: this.summary.overdue ?? '—', hint: '按批次阶段期限', status: '' },
        { key: 'avgHours', label: '平均用时', value: this.summary.avgHours == null ? '—' : `${this.summary.avgHours}h`, hint: '已完成任务' }
      ]
    },
    pageCount() { return Math.max(1, Math.ceil(Number(this.total || 0) / this.pageSize)) },
    currentRecord() {
      if (!this.activeTask) return null
      return { ...this.activeTask, plagiarismRate: this.detail?.plagiarism?.rate ?? null }
    },
    feedbackHistory() { return Array.isArray(this.detail?.feedbackHistory) ? this.detail.feedbackHistory : [] },
    targetFile() {
      if (!this.detail) return null
      return this.activeTask?.caseType === 'FORMAL_REVIEW'
        ? (this.detail.frozenFile || this.detail.canonicalFile)
        : this.detail.canonicalFile
    },
    targetFileVersionId() { return this.targetFile?.fileVersionId ?? this.activeTask?.fileVersionId ?? null },
    previewFiles() {
      const raw = Array.isArray(this.detail?.versionHistory) ? [...this.detail.versionHistory] : []
      if (this.targetFile?.fileVersionId != null && !raw.some((item) => String(item.fileVersionId) === String(this.targetFile.fileVersionId))) raw.push(this.targetFile)
      return graduationMaterialCenterApi.normalizeVersions(raw)
    },
    activePreviewFile() {
      return this.previewFiles.find((item) => String(this.versionKey(item)) === String(this.activeVersionId))
        || this.previewFiles.find((item) => String(this.fileKey(item)) === String(this.activeFileKey))
        || this.previewFiles[0] || null
    },
    previewDescriptor() { return this.activePreviewFile ? graduationMaterialCenterApi.previewDescriptor(this.activePreviewFile) : null },
    expectedVersion() {
      if (!this.writeContext) return null
      return this.activeTask?.caseType === 'FORMAL_REVIEW' ? this.writeContext.version : this.writeContext.materialVersion
    },
    versionConflict() {
      const blockers = this.activeTask?.blockingReasons || []
      const conflict = Boolean(this.activeTask?.versionConflict || blockers.some((item) => item.code === 'CANONICAL_VERSION_CHANGED' || item.code === 'SOURCE_SHA_CONFLICT'))
      return conflict ? { task: this.targetFileVersionId, canonical: this.detail?.canonicalFile?.fileVersionId ?? null } : null
    },
    targetVersionSelected() {
      return this.activeVersionId != null && this.targetFileVersionId != null && String(this.activeVersionId) === String(this.targetFileVersionId)
    },
    taskReviewReady() { return Boolean(this.activeTask?.reviewReady && !this.versionConflict && this.targetVersionSelected) },
    allowedActions() { return Array.isArray(this.activeTask?.allowedActions) ? this.activeTask.allowedActions : [] },
    canReviewBusiness() {
      const type = String(this.activeTask?.caseType || '')
      return ['PROPOSAL', 'FINAL', 'FINAL_DRAFT'].includes(type) && this.allowedActions.includes('REVIEW')
    },
    canSubmitFormal() {
      return this.activeTask?.caseType === 'FORMAL_REVIEW' && this.allowedActions.includes('SUBMIT')
    },
    canReturnFormalAction() {
      return this.activeTask?.caseType === 'FORMAL_REVIEW' && this.allowedActions.includes('RETURN')
    },
    canShowWriteForm() { return this.canReviewBusiness || this.canSubmitFormal },
    canSubmitCurrent() {
      return Boolean(this.taskReviewReady && this.writeContext && this.canShowWriteForm)
    },
    canReturnFormal() {
      return Boolean(this.canReturnFormalAction && String(this.form.returnReason || '').trim().length >= 5)
    }
  },
  watch: {
    '$route.query.batchId'(next, prev) {
      if (prev != null && String(next || '') !== String(prev || '')) this.loadAll()
    }
  },
  created() { this.loadAll() },
  beforeUnmount() {
    this.saveDraft()
    if (this.searchTimer) clearTimeout(this.searchTimer)
    this.previewProvider?.dispose?.()
  },
  methods: {
    caseLabel(type) { return CASE_OPTIONS.find((item) => item.value === type)?.label || type || '任务' },
    versionKey(item) { return item?.fileVersionId ?? item?.versionId ?? item?.id ?? null },
    fileKey(item) { return item?.fileKey ?? item?.fileId ?? this.versionKey(item) },
    draftKey() {
      return this.activeTask?.caseKey && this.targetFileVersionId != null
        ? `gd-review-center-draft:v1:${this.activeTask.caseKey}:${this.targetFileVersionId}` : ''
    },
    saveDraft() {
      const key = this.draftKey()
      if (!key) return
      const payload = { ...this.form, at: Date.now() }
      try { sessionStorage.setItem(key, JSON.stringify(payload)) } catch { /* browser storage unavailable */ }
    },
    restoreDraft() {
      this.form = { score: '', opinion: '', categories: [], issuesText: '', returnReason: '' }
      const key = this.draftKey()
      if (!key) return
      try {
        const payload = JSON.parse(sessionStorage.getItem(key) || 'null')
        if (payload) this.form = { ...this.form, ...payload, categories: Array.isArray(payload.categories) ? payload.categories : [] }
      } catch { /* ignore malformed draft */ }
    },
    clearDraft() {
      const key = this.draftKey()
      if (key) { try { sessionStorage.removeItem(key) } catch { /* ignore */ } }
    },
    issueRows() {
      return String(this.form.issuesText || '').split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
    },
    structuredComment() {
      const chunks = []
      if (this.form.categories.length) chunks.push(`关注项：${this.form.categories.join('、')}`)
      const issues = this.issueRows()
      if (issues.length) chunks.push(`问题清单：\n${issues.map((item) => `- ${item}`).join('\n')}`)
      const opinion = String(this.form.opinion || '').trim()
      if (opinion) chunks.push(`批阅意见：\n${opinion}`)
      return chunks.join('\n\n')
    },
    toggleCategory(item) {
      const hit = this.form.categories.indexOf(item)
      if (hit >= 0) this.form.categories.splice(hit, 1)
      else this.form.categories.push(item)
      this.saveDraft()
    },
    setCaseType(value) { this.filters.caseType = value; this.reloadFromFirstPage() },
    setStatusGroup(value) { this.filters.statusGroup = value; this.reloadFromFirstPage() },
    applySummaryCard(card) {
      if (card.status) this.filters.statusGroup = card.status
      this.reloadFromFirstPage()
    },
    scheduleReload() {
      if (this.searchTimer) clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(() => this.reloadFromFirstPage(), 300)
    },
    reloadFromFirstPage() { this.page = 1; this.loadAll() },
    async loadSummary() {
      this.summary = await graduationReviewCenterApi.summary()
    },
    async loadQueue({ select = true, preserveSelection = false } = {}) {
      const oldKey = preserveSelection ? this.activeTask?.caseKey : null
      const data = await graduationReviewCenterApi.tasks({
        page: this.page, pageSize: this.pageSize, caseType: this.filters.caseType || undefined,
        statusGroup: this.filters.statusGroup || undefined, keyword: this.filters.keyword || undefined,
        reviewerOnly: this.filters.reviewerOnly, sort: 'PRIORITY'
      })
      this.queue = Array.isArray(data?.items) ? data.items : []
      this.total = Number(data?.total || 0)
      if (!select) return
      if (!this.queue.length) { this.resetSelection(); return }
      const target = oldKey ? this.queue.find((item) => item.caseKey === oldKey) : null
      await this.selectTask(target || this.queue[0])
    },
    async loadAll({ preserveSelection = false } = {}) {
      this.loading = true; this.error = ''
      try {
        await Promise.all([this.loadSummary(), this.loadQueue({ preserveSelection })])
      } catch (error) {
        this.error = errorMessage(error, '评阅中心数据加载失败')
      } finally { this.loading = false }
    },
    resetSelection() {
      this.saveDraft()
      this.activeTask = null; this.detail = null; this.writeContext = null
      this.activeIndex = 0; this.activeFileKey = null; this.activeVersionId = null
      this.formError = ''
    },
    async selectTask(task) {
      if (!task) return
      this.saveDraft()
      const token = ++this.selectionToken
      this.activeTask = task
      this.activeIndex = Math.max(0, this.queue.findIndex((item) => item.caseKey === task.caseKey))
      this.loadingDetail = true; this.formError = ''; this.detail = null; this.writeContext = null
      try {
        const [detail, writeContext] = await Promise.all([
          graduationReviewCenterApi.detail(task.caseType, task.recordId),
          graduationReviewCenterApi.writeContext(task)
        ])
        if (token !== this.selectionToken) return
        this.detail = detail
        this.activeTask = detail?.case ? { ...task, ...detail.case } : task
        this.writeContext = writeContext
        this.activeVersionId = this.targetFileVersionId
        const active = this.previewFiles.find((item) => String(this.versionKey(item)) === String(this.activeVersionId)) || this.previewFiles[0] || null
        this.activeFileKey = active ? this.fileKey(active) : null
        this.restoreDraft()
      } catch (error) {
        if (token === this.selectionToken) this.formError = errorMessage(error, '当前评阅任务读取失败')
      } finally {
        if (token === this.selectionToken) this.loadingDetail = false
      }
    },
    async reloadCurrent({ preserveDraft = false } = {}) {
      if (!this.activeTask) return
      if (preserveDraft) this.saveDraft()
      const task = this.activeTask
      await this.selectTask(task)
    },
    move(step) {
      const index = this.activeIndex + step
      if (index >= 0 && index < this.queue.length) this.selectTask(this.queue[index])
    },
    selectPreview(item) {
      if (!item) return
      this.saveDraft()
      this.activeVersionId = this.versionKey(item)
      this.activeFileKey = this.fileKey(item)
      this.restoreDraft()
    },
    async changePage(next) {
      if (next < 1 || next > this.pageCount || next === this.page) return
      this.page = next
      await this.loadAll()
    },
    async submitBusiness(action) {
      if (!this.canReviewBusiness || !this.canSubmitCurrent || this.submitting) return
      if (!['APPROVE', 'REJECT'].includes(action)) { this.formError = '不支持的批阅动作'; return }
      const type = String(this.activeTask?.caseType || '')
      if (!['PROPOSAL', 'FINAL', 'FINAL_DRAFT'].includes(type)) return
      const comment = this.structuredComment()
      if (action === 'REJECT' && comment.trim().length < 5) { this.formError = '退回修改必须填写不少于 5 个字的批阅意见'; return }
      this.submitting = true; this.formError = ''
      try {
        const payload = {
          action, comment, expectedVersion: this.expectedVersion,
          fileVersionId: Number(this.targetFileVersionId)
        }
        if (type === 'PROPOSAL') await graduationReviewCenterApi.reviewProposal(this.activeTask.recordId, payload)
        else await graduationReviewCenterApi.reviewFinal(this.activeTask.recordId, payload)
        await this.afterMutation(action === 'APPROVE' ? '当前版本已通过，证据已绑定' : '已退回学生修改')
      } catch (error) { await this.handleMutationError(error) }
      finally { this.submitting = false }
    },
    async submitFormal() {
      if (!this.canSubmitFormal || !this.canSubmitCurrent || this.submitting) return
      const score = Number(this.form.score)
      const opinion = String(this.form.opinion || '').trim()
      if (!Number.isFinite(score) || score < 0 || score > 100) { this.formError = '正式评阅评分必须为 0–100'; return }
      if (opinion.length < 2) { this.formError = '正式评阅意见至少填写 2 个字'; return }
      this.submitting = true; this.formError = ''
      try {
        await graduationReviewCenterApi.submitFormal(this.activeTask.recordId, {
          score, opinion, expectedVersion: Number(this.expectedVersion), fileVersionId: Number(this.targetFileVersionId),
          categories: [...this.form.categories], issues: this.issueRows().map((text) => ({ text }))
        })
        await this.afterMutation('正式评阅已提交并绑定冻结 FileVersion')
      } catch (error) { await this.handleMutationError(error) }
      finally { this.submitting = false }
    },
    async returnFormal() {
      if (!this.canReturnFormal || this.submitting) return
      this.submitting = true; this.formError = ''
      try {
        await graduationReviewCenterApi.returnFormal(this.activeTask.recordId, String(this.form.returnReason).trim())
        await this.afterMutation('已退回重评')
      } catch (error) { await this.handleMutationError(error) }
      finally { this.submitting = false }
    },
    async handleMutationError(error) {
      this.saveDraft()
      const code = String(error?.code || error?.data?.code || '')
      const conflict = code.includes('VERSION') || code.includes('CONFLICT') || code.includes('REVIEW_TARGET')
      if (conflict) {
        await this.reloadCurrent({ preserveDraft: true })
        this.formError = '任务或 FileVersion 已变化，系统已刷新 canonical 事实；草稿仍保留，请重新核验后提交。'
      } else this.formError = errorMessage(error)
    },
    async afterMutation(message) {
      const oldKey = this.activeTask?.caseKey
      const oldIndex = this.activeIndex
      this.clearDraft()
      toast.success(message)
      await this.loadSummary()
      await this.loadQueue({ select: false })
      if (!this.queue.length) { this.resetSelection(); return }
      const sameIndex = this.queue.findIndex((item) => item.caseKey === oldKey)
      let target
      if (this.autoNext) {
        if (sameIndex >= 0) target = this.queue[sameIndex + 1] || (sameIndex > 0 ? this.queue[sameIndex - 1] : this.queue[sameIndex])
        else target = this.queue[Math.min(oldIndex, this.queue.length - 1)]
      } else target = sameIndex >= 0 ? this.queue[sameIndex] : this.queue[Math.min(oldIndex, this.queue.length - 1)]
      await this.selectTask(target)
    },
    async openStudentDossier(record) {
      const studentId = record?.gdStudentId || this.activeTask?.gdStudentId
      if (!studentId) return
      this.dossierOpen = true; this.dossierLoading = true; this.dossierError = ''; this.dossier = null
      const res = await graduationApi.getStudentDetail(studentId)
      if (res.code === 0) this.dossier = res.data
      else this.dossierError = res.message || '学生档案读取失败'
      this.dossierLoading = false
    },
    closeDossier() { this.dossierOpen = false; this.dossier = null; this.dossierError = '' }
  }
}
</script>

<style scoped>
.w74-center{display:grid;gap:12px;min-width:0}.w74-summary{display:grid;grid-template-columns:repeat(6,minmax(120px,1fr));gap:8px}.w74-summary__card{display:grid;gap:2px;text-align:left;padding:11px 12px;border:1px solid var(--border-light,#e2e8f0);border-radius:10px;background:#fff;cursor:pointer}.w74-summary__card span,.w74-summary__card small{font-size:11px;color:var(--text-tertiary,#64748b)}.w74-summary__card strong{font-size:22px;color:var(--text-primary,#0f172a)}.w74-toolbar{display:grid;gap:9px;padding:10px 12px;border:1px solid var(--border-light,#e2e8f0);border-radius:10px;background:#fff}.w74-filter-group{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.w74-filter-label{width:64px;font-size:12px;color:var(--text-tertiary,#64748b)}.w74-chip,.w74-category{border:1px solid var(--border-light,#e2e8f0);border-radius:999px;background:#fff;padding:5px 9px;font-size:12px;color:var(--text-secondary,#475569);cursor:pointer}.w74-chip.is-active,.w74-category.is-active{border-color:var(--brand-primary,#2563eb);background:var(--primary-50,#eff6ff);color:var(--brand-primary,#2563eb)}.w74-toolbar__search{display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding-top:8px;border-top:1px solid var(--border-light,#e2e8f0)}.w74-toolbar__search input[type=search]{flex:1 1 300px;min-width:220px;border:1px solid var(--border-base,#cbd5e1);border-radius:8px;padding:7px 9px}.w74-toolbar__search label{font-size:12px;color:var(--text-secondary,#475569)}.w74-refresh,.w74-pagination button{border:1px solid var(--border-light,#e2e8f0);border-radius:7px;background:#fff;padding:6px 9px;cursor:pointer}.w74-state{min-height:120px;display:grid;place-content:center;justify-items:center;gap:5px;border:1px dashed var(--border-light,#e2e8f0);border-radius:10px;color:var(--text-secondary,#475569);background:#fff}.w74-state--error{color:#b91c1c}.w74-state button{margin-top:5px}.w74-pagination{display:flex;align-items:center;justify-content:space-between;gap:6px;padding:8px;font-size:11px;color:var(--text-tertiary,#64748b)}.w74-case-head{display:flex;align-items:center;gap:6px;flex-wrap:wrap}.w74-case-type,.w74-status,.w74-overdue{font-size:11px;border-radius:999px;padding:3px 7px;background:#f1f5f9;color:#475569}.w74-overdue{background:#fff1f2;color:#be123c}.w74-status.is-returned{background:#fff7ed;color:#c2410c}.w74-status.is-done{background:#ecfdf5;color:#047857}.w74-blockers,.w74-history-lock,.w74-form-error{padding:8px 9px;border-radius:8px;font-size:12px}.w74-blockers{background:#fff7ed;color:#9a3412}.w74-blockers ul{margin:5px 0 0;padding-left:18px}.w74-history-lock{background:#eff6ff;color:#1d4ed8;line-height:1.5}.w74-form-error{margin:0;background:#fef2f2;color:#b91c1c}.w74-feedback,.w74-write-form,.w74-return-form{display:grid;gap:8px;padding-top:8px;border-top:1px solid var(--border-light,#e2e8f0)}.w74-section-title{display:flex;justify-content:space-between;gap:8px;align-items:center}.w74-section-title span,.w74-muted{font-size:11px;color:var(--text-tertiary,#64748b)}.w74-feedback-list{display:grid;gap:6px;max-height:180px;overflow:auto}.w74-feedback-list article{display:grid;gap:3px;padding:7px;border-radius:7px;background:#f8fafc}.w74-feedback-list article>div{display:flex;justify-content:space-between;gap:6px;font-size:11px}.w74-feedback-list p{margin:0;white-space:pre-wrap;font-size:12px;line-height:1.5}.w74-feedback-list small{color:var(--text-tertiary,#64748b)}.w74-category-list{display:flex;gap:5px;flex-wrap:wrap}.w74-field{display:grid;gap:4px}.w74-field>span{font-size:12px;font-weight:600;color:var(--text-primary,#0f172a)}.w74-field small{font-weight:400;color:var(--text-tertiary,#64748b)}.w74-field textarea,.w74-field input{width:100%;box-sizing:border-box;border:1px solid var(--border-base,#cbd5e1);border-radius:8px;padding:7px 8px;font:inherit;resize:vertical}.w74-actions{display:grid;gap:7px}.w74-actions--two{grid-template-columns:1fr 1fr}.w74-primary,.w74-warning{border-radius:8px;padding:7px 10px;cursor:pointer}.w74-primary{border:1px solid var(--brand-primary,#2563eb);background:var(--brand-primary,#2563eb);color:#fff}.w74-warning{border:1px solid #f59e0b;background:#fffbeb;color:#a16207}.w74-primary:disabled,.w74-warning:disabled,.w74-refresh:disabled,.w74-pagination button:disabled{opacity:.5;cursor:not-allowed}.w74-review-loading{padding:18px 8px;text-align:center;color:var(--text-tertiary,#64748b);font-size:12px}.w74-modal{position:fixed;inset:0;z-index:1500;display:grid;place-items:center;padding:24px;background:rgba(15,23,42,.45)}.w74-modal__panel{width:min(680px,100%);max-height:80vh;overflow:auto;border-radius:14px;background:#fff;box-shadow:0 24px 60px rgba(15,23,42,.24)}.w74-modal__panel header,.w74-modal__panel footer{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 16px;border-bottom:1px solid var(--border-light,#e2e8f0)}.w74-modal__panel footer{justify-content:flex-end;border-top:1px solid var(--border-light,#e2e8f0);border-bottom:0}.w74-modal__panel header div{display:grid}.w74-modal__panel header small{color:var(--text-tertiary,#64748b)}.w74-modal__panel header button{border:0;background:transparent;font-size:24px;cursor:pointer}.w74-dossier-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px}.w74-dossier-grid div{display:grid;gap:3px}.w74-dossier-grid span{font-size:11px;color:var(--text-tertiary,#64748b)}.w74-dossier-grid b{font-size:13px;color:var(--text-primary,#0f172a)}
@media(max-width:1400px){.w74-summary{grid-template-columns:repeat(3,1fr)}}@media(max-width:900px){.w74-summary{grid-template-columns:repeat(2,1fr)}.w74-dossier-grid{grid-template-columns:1fr}}
</style>