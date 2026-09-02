<template>
  <ModulePageShell
    title="成果检查"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton
        v-if="exportPerm.visible"
        :export-fn="exportFinalsFn"
        :has-permission="exportPerm.allowed"
      >导出成果清单</AppExportButton>
    </template>

    <div class="mp-stack fr-workbench-stack">
      <div class="fr-command" aria-label="成果批阅工作结论">
        <div class="fr-command__copy">
          <span>当前工作队列</span>
          <strong>{{ queueConclusion }}</strong>
        </div>
        <div class="fr-command__counts">
          <span><b>{{ statusCount('PENDING_REVIEW') }}</b>待审阅</span>
          <span><b>{{ stats?.plagiarismOver ?? 0 }}</b>查重超标</span>
          <span><b>{{ total }}</b>当前队列</span>
        </div>
      </div>

      <div class="mp-tabs" aria-label="成果状态筛选">
        <button
          v-for="t in tabs"
          :key="t.value"
          class="mp-tab"
          :class="{ 'is-active': filters.status === t.value }"
          :disabled="submitting"
          @click="switchTab(t.value)"
        >
          {{ t.label }}<span v-if="tabCount(t.value) !== null" class="fr-tab-count">{{ tabCount(t.value) }}</span>
        </button>
      </div>

      <div v-if="hasBatch" class="fr-filter-row">
        <AppSearchBox
          v-model="filters.keyword"
          :disabled="submitting"
          placeholder="搜索学生 / 学号 / 课题"
          @search="onFilterSearch"
        />
        <span v-if="selectedRow" class="fr-selected-summary">
          当前：<b>{{ selectedRow.studentName }}</b> · {{ selectedRow.version || '版本待确认' }}
          <em v-if="submitting">提交中，已锁定对象与版本</em>
        </span>
      </div>

      <aside v-if="reviewReceipt" class="fr-receipt" role="status">
        <div><strong>{{ reviewReceipt.title }}</strong><span>{{ reviewReceipt.result }}</span><small>{{ reviewReceipt.next }}</small></div>
        <button type="button" @click="reviewReceipt = null">关闭</button>
      </aside>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDesc" />

      <GraduationDocumentReviewWorkspace
        v-else
        :queue="rows"
        :queue-title="queueTitle"
        :current-index="Math.max(selIndex, 0)"
        :current-record="selectedRow"
        :detail="finalDetail"
        :files="secureVersionFiles"
        :versions="activeVersionHistory"
        :evidence-versions="secureVersionFiles"
        :canonical-file-version-id="canonicalFileVersionId"
        :review-ready="Boolean(finalDetail?.reviewReady) && !versionConflict"
        :expected-version="finalDetail?.materialVersion"
        :comment="comment"
        :submitting="submitting"
        :auto-next="autoNext"
        mode="final"
        :provider="previewProvider"
        :descriptor="previewDescriptor"
        :active-file-key="activePreviewFileKey"
        :active-version-id="activePreviewVersionId"
        :version-conflict="versionConflict"
        :allow-download="Boolean(activePreviewFile?.canDownload)"
        :narrow="isNarrow"
        @select="select"
        @previous="step(-1)"
        @next="step(1)"
        @update:auto-next="autoNext = $event"
        @select-file="selectPreviewFile"
        @select-version="selectPreviewVersion"
        @download="downloadActivePreview"
        @reload="loadSelectedDetail"
        @open-student-dossier="openDossier"
      >
        <template #queue-footer>
          <div class="fr-list__foot">
            <AppPagination
              :total="total"
              :page="page"
              :page-size="pageSize"
              :show-size-changer="false"
              @update:page="turnPage"
            />
          </div>
        </template>

        <template #review>
          <LoadingState v-if="detailLoading" />
          <ErrorState v-else-if="detailError" :description="detailError" @retry="loadSelectedDetail" />
          <template v-else-if="selectedRow?.status === 'NOT_SUBMITTED'">
            <AppButton variant="primary" :loading="reminding" :disabled="submitting" @click="remind(selectedRow)">发送成果催交提醒</AppButton>
            <p class="mp-note">本操作会创建真实站内消息并写入催办留痕。</p>
          </template>
          <template v-else-if="selectedRow?.status === 'PENDING_REVIEW'">
            <div v-if="!canReview" class="fr-review-blocked">{{ reviewReason }}（以下操作已置灰）</div>
            <label class="mp-note">批阅意见（退回时必填，≥5 字）</label>
            <textarea
              v-model="comment"
              class="mp-textarea"
              rows="5"
              :disabled="submitting"
              placeholder="批阅意见将同步学生端…"
              @input="saveCommentDraft"
            ></textarea>
            <AppTemplateChips v-if="canReview && !submitting" size="compact" :options="REJECT_REASON_CHIPS" @pick="appendComment" />
            <p v-if="formError" class="mp-form-err">{{ formError }}</p>
            <div class="fr-review-actions">
              <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="primary" :loading="submitting" @click="submitReview('APPROVE')">✓ 通过当前版本</AppPermissionButton>
              <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="warning" :loading="submitting" @click="submitReview('REJECT')">↩ 退回当前版本</AppPermissionButton>
            </div>
            <p class="mp-note">正式命令始终绑定当前记录、业务版本和 canonical FileVersion；历史版本只读。</p>
            <details class="mp-note"><summary>命令校验证据</summary><code>expectedVersion + fileVersionId</code> 由服务端原子校验。</details>
          </template>
          <template v-else>
            <div class="mp-kv"><span class="mp-kv__k">批阅结果</span><span class="mp-kv__v">{{ selectedRow?.statusLabel || '—' }}</span></div>
            <p class="mp-note">已批阅版本继续保留追溯；学生重交后会形成新的材料版本。</p>
          </template>
        </template>
      </GraduationDocumentReviewWorkspace>

      <p class="mp-note">筛选、分页和当前对象均写入 URL；初稿 / 定稿顺序、查重阈值与文件安全状态仍由服务器校验。</p>
    </div>
    <AppPageGuide guide-key="graduation.gd-final-review" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppExportButton, AppSearchBox, AppPagination, AppPermissionButton, AppTemplateChips, AppPageGuide } from '@/components/common'
import GraduationDocumentReviewWorkspace from '@/modules/graduation/components/GraduationDocumentReviewWorkspace.vue'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { graduationMaterialCenterApi } from '@/modules/graduation/api/graduation-material-center.api'
import { graduationActionErrorMessage, graduationConflictMessage, isGraduationConflictResponse } from '@/modules/graduation/utils/form-state'
import { buildMaterialQuery, exportFilenameHint } from '@/modules/graduation/utils/queryParams'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'

const REJECT_REASON_CHIPS = ['材料不完整，请补充', '内容质量不达标，需修改', '格式不符合学校规范', '与选题方向不符']

export default {
  name: 'FinalSubmissionListView',
  components: {
    AppPageGuide, ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton,
    AppExportButton, AppSearchBox, AppPagination, AppPermissionButton, AppTemplateChips,
    GraduationDocumentReviewWorkspace
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      REJECT_REASON_CHIPS,
      batchStore: useGraduationBatchStore(),
      previewProvider: graduationMaterialCenterApi.createPreviewProvider(),
      loading: true,
      error: '',
      rows: [],
      total: 0,
      page: 1,
      pageSize: 20,
      filters: { status: 'PENDING_REVIEW', keyword: '', dateStart: '', dateEnd: '' },
      selKey: '',
      autoNext: true,
      comment: '',
      formError: '',
      submitting: false,
      reminding: false,
      stats: null,
      isNarrow: false,
      finalDetail: null,
      versionHistory: [],
      detailLoading: false,
      detailError: '',
      detailRequestKey: '',
      activePreviewFileKey: null,
      activePreviewVersionId: null,
      conflictPreviewFile: null,
      readerMode: 'embedded',
      previewDraftKey: '',
      draftFileVersionId: null,
      versionConflict: null,
      reviewReceipt: null,
      loadToken: 0,
      statsToken: 0,
      detailToken: 0,
      tabs: [
        { value: 'PENDING_REVIEW', label: '待审阅' },
        { value: 'APPROVED', label: '已通过' },
        { value: 'REJECTED', label: '已退回修改' },
        { value: 'NOT_SUBMITTED', label: '未提交' },
        { value: '', label: '全部' }
      ]
    }
  },
  computed: {
    hasBatch() { return !!this.batchStore.selectedBatchId },
    activeTab() { return this.tabs.find((item) => item.value === this.filters.status) || this.tabs[this.tabs.length - 1] },
    queueTitle() { return `${this.activeTab?.label || '全部'} · 第 ${this.page} 页` },
    queueConclusion() {
      if (this.submitting && this.selectedRow) return `正在提交 ${this.selectedRow.studentName} 的成果结论；对象与版本已锁定。`
      if (this.filters.status === 'PENDING_REVIEW' && this.statusCount('PENDING_REVIEW') > 0) return `待审阅 ${this.statusCount('PENDING_REVIEW')} 份；先核验安全版本，再提交正式结论。`
      if (!this.total) return `「${this.activeTab?.label || '全部'}」当前没有需要处理的成果。`
      return `当前查看「${this.activeTab?.label || '全部'}」${this.total} 条成果记录。`
    },
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const batch = this.batchStore.selectedBatchName ? `${this.batchStore.selectedBatchName} · ` : ''
      if (!this.stats) return `${batch}左队列 → 中文档 → 右审核 · 当前正式版本锁定`
      return `${batch}待审阅 ${this.statusCount('PENDING_REVIEW')} · 查重超标 ${this.stats.plagiarismOver ?? 0} · 安全版本审核`
    },
    emptyTitle() { return this.hasBatch ? '当前页签暂无成果提交' : '请先选择或创建毕设批次' },
    emptyDesc() { return this.hasBatch ? '可切换页签或调整搜索条件' : '顶部批次条选择当前工作批次后，再批阅成果材料。' },
    exportPerm() {
      const patterns = this.ctx.permissionPatterns
      return { visible: this.hasBatch, allowed: Array.isArray(patterns) && matchPermission(patterns, 'graduationDesign.final.export') }
    },
    secureVersionFiles() { return graduationMaterialCenterApi.normalizeVersions(this.finalDetail?.currentSafeVersions || []) },
    canonicalFileVersionId() { return this.finalDetail?.fileVersionId ?? null },
    activePreviewFile() {
      if (
        this.versionConflict && this.conflictPreviewFile &&
        String(this.versionKey(this.conflictPreviewFile)) === String(this.activePreviewVersionId)
      ) return this.conflictPreviewFile
      const current = this.secureVersionFiles.find((item) => String(this.fileKey(item)) === String(this.activePreviewFileKey))
        || this.secureVersionFiles.find((item) => String(this.versionKey(item)) === String(this.activePreviewVersionId))
      if (current) return current
      const historical = this.versionHistory.find((item) => String(this.versionKey(item)) === String(this.activePreviewVersionId))
      if (historical) return historical
      return this.versionConflict ? null : (this.secureVersionFiles[0] || null)
    },
    activeVersionHistory() {
      const assetId = this.activePreviewFile?.assetId
      if (assetId == null) return this.activePreviewFile ? [this.activePreviewFile] : []
      const rows = this.versionHistory.filter((item) => String(item.assetId ?? '') === String(assetId))
      return rows.length ? rows : [this.activePreviewFile]
    },
    previewDescriptor() { return this.activePreviewFile ? graduationMaterialCenterApi.previewDescriptor(this.activePreviewFile) : null },
    canReview() {
      const pa = this.ctx.permissionActions.reviewFinal
      return !!(
        pa && pa.visible && pa.allowed && this.ctx.writeEnabled !== false &&
        this.selectedRow?.status === 'PENDING_REVIEW' && !this.detailLoading &&
        this.finalDetail?.reviewReady && !this.versionConflict && this.activePreviewFile && this.activePreviewFile.isCurrent !== false
      )
    },
    reviewReason() {
      if (this.ctx.writeEnabled === false) return '写操作已禁用'
      const pa = this.ctx.permissionActions.reviewFinal
      if (pa && !pa.allowed) return pa.reason || '当前角色无成果批阅权限'
      if (this.detailLoading) return '正在核验当前文件版本'
      if (this.detailError) return '成果安全版本详情加载失败'
      if (this.finalDetail?.migrationRequired) return '历史材料尚未完成公共版本回填'
      if (!this.finalDetail?.reviewReady) return '当前材料版本未通过安全门禁'
      if (this.versionConflict) return '学生已提交新版本，请切换最新 canonical version 后重新核验'
      if (this.activePreviewFile?.isCurrent === false) return '当前正在阅读历史版本，历史版本只读不可批阅'
      return ''
    },
    pageStartIndex() { return (this.page - 1) * this.pageSize },
    selectedRow() { return this.rows.find((row) => this.rowKey(row) === this.selKey) || null },
    selIndex() { return this.rows.findIndex((row) => this.rowKey(row) === this.selKey) },
    hasNext() { return this.selIndex < this.rows.length - 1 || this.page * this.pageSize < this.total }
  },
  created() {
    this.applyInitialRouteState(this.$route.query)
    this.loadStats()
    this.load()
  },
  watch: {
    'batchStore.selectedBatchId'(batchId) {
      ++this.loadToken
      ++this.statsToken
      this.saveCommentDraft()
      this.submitting = false
      this.page = 1
      this.selKey = ''
      this.comment = ''
      this.resetDetail()
      this.replaceListQuery({ batchId: batchId ? String(batchId) : undefined, page: '1', sel: undefined })
      this.loadStats()
      this.load()
    },
    '$route.query': {
      deep: true,
      handler(query) { this.onRouteQueryChanged(query) }
    }
  },
  mounted() {
    this._mq = window.matchMedia('(max-width: 1100px)')
    this.isNarrow = this._mq.matches
    this._onMq = (event) => { this.isNarrow = event.matches }
    this._mq.addEventListener ? this._mq.addEventListener('change', this._onMq) : this._mq.addListener(this._onMq)
    this._onKey = (event) => {
      if (this.isNarrow || this.submitting) return
      const tag = event.target?.tagName || ''
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return
      if (event.key === 'ArrowDown') { event.preventDefault(); this.step(1) }
      if (event.key === 'ArrowUp') { event.preventDefault(); this.step(-1) }
    }
    window.addEventListener('keydown', this._onKey)
  },
  beforeUnmount() {
    ++this.loadToken
    ++this.statsToken
    ++this.detailToken
    this.saveCommentDraft()
    if (this._mq) this._mq.removeEventListener ? this._mq.removeEventListener('change', this._onMq) : this._mq.removeListener(this._onMq)
    window.removeEventListener('keydown', this._onKey)
  },
  methods: {
    routeText(value) { return Array.isArray(value) ? String(value[0] || '') : String(value || '') },
    normalizePage(value) {
      const page = Number.parseInt(this.routeText(value), 10)
      return Number.isFinite(page) && page > 0 ? page : 1
    },
    normalizeTab(value) {
      const tab = this.routeText(value)
      return this.tabs.some((item) => item.value === tab) ? tab : 'PENDING_REVIEW'
    },
    applyInitialRouteState(query) {
      this.filters.status = this.normalizeTab(query.tab)
      this.filters.keyword = this.routeText(query.keyword)
      this.page = this.normalizePage(query.page)
      this.selKey = this.routeText(query.sel)
    },
    onRouteQueryChanged(query) {
      const nextStatus = this.normalizeTab(query.tab)
      const nextKeyword = this.routeText(query.keyword)
      const nextPage = this.normalizePage(query.page)
      const nextSel = this.routeText(query.sel)
      const listChanged = nextStatus !== this.filters.status || nextKeyword !== this.filters.keyword || nextPage !== this.page
      const selectionChanged = nextSel !== this.selKey
      if (!listChanged && !selectionChanged) return
      if (this.submitting) return

      this.saveCommentDraft()
      this.filters.status = nextStatus
      this.filters.keyword = nextKeyword
      this.page = nextPage
      this.selKey = nextSel
      this.comment = ''
      this.resetDetail()
      if (listChanged) this.load()
      else if (this.selectedRow) this.loadSelectedDetail()
      else this.load()
    },
    buildListQuery(overrides = {}) {
      const keyword = String(this.filters.keyword || '').trim()
      const query = {
        ...this.$route.query,
        batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
        tab: this.filters.status || undefined,
        page: String(this.page),
        keyword: keyword || undefined,
        sel: this.selKey || undefined,
        ...overrides
      }
      Object.keys(query).forEach((key) => {
        if (query[key] == null || query[key] === '') delete query[key]
      })
      return query
    },
    replaceListQuery(overrides = {}) { return this.$router.replace({ query: this.buildListQuery(overrides) }) },
    rowKey(row) { return row?.id != null ? String(row.id) : `ns-${row?.gdStudentId}` },
    versionKey(item) { return item?.fileVersionId ?? item?.versionId ?? item?.id ?? null },
    fileKey(item) { return item?.fileKey ?? item?.fileId ?? this.versionKey(item) },
    statusCount(status) { const stat = (this.stats?.byStatus || []).find((item) => item.status === status); return stat ? stat.count : 0 },
    tabCount(value) { if (!this.stats || value === '' || value === 'NOT_SUBMITTED') return null; return this.statusCount(value) },
    resetDetail() {
      ++this.detailToken
      this.finalDetail = null
      this.versionHistory = []
      this.detailLoading = false
      this.detailError = ''
      this.detailRequestKey = ''
      this.activePreviewFileKey = null
      this.activePreviewVersionId = null
      this.conflictPreviewFile = null
      this.previewDraftKey = ''
      this.draftFileVersionId = null
      this.versionConflict = null
    },
    draftKey(row = this.selectedRow, fileVersionId = this.draftFileVersionId ?? this.canonicalFileVersionId) {
      if (!row?.id || fileVersionId == null) return ''
      return `gd-final-review-draft:${row.id}:${fileVersionId}`
    },
    saveCommentDraft() {
      const key = this.previewDraftKey || this.draftKey()
      if (!key) return
      try {
        if (this.comment) sessionStorage.setItem(key, this.comment)
        else sessionStorage.removeItem(key)
      } catch { /* sessionStorage unavailable */ }
    },
    restoreCommentDraft(fallback = '') {
      this.previewDraftKey = this.draftKey()
      if (!this.previewDraftKey) { this.comment = fallback; return }
      try { this.comment = sessionStorage.getItem(this.previewDraftKey) || fallback } catch { this.comment = fallback }
    },
    clearCommentDraft() {
      const key = this.previewDraftKey || this.draftKey()
      if (key) { try { sessionStorage.removeItem(key) } catch { /* ignore */ } }
      this.previewDraftKey = ''
    },
    appendComment(text) {
      if (this.submitting) return
      this.comment = this.comment ? `${this.comment}\n${text}` : text
      this.saveCommentDraft()
    },
    async loadStats() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.statsToken
      if (!batchId) { this.stats = null; return false }
      try {
        const res = await graduationMoreApi.getFinalStats({ batchId })
        if (token !== this.statsToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return false
        if (res.code === 0) this.stats = res.data
        return res.code === 0
      } catch {
        if (token === this.statsToken && String(batchId) === String(this.batchStore.selectedBatchId)) this.stats = null
        return false
      }
    },
    switchTab(value) {
      if (this.submitting) return
      this.saveCommentDraft()
      this.filters.status = value
      this.page = 1
      this.selKey = ''
      this.comment = ''
      this.resetDetail()
      this.replaceListQuery({ tab: value || undefined, page: '1', sel: undefined })
      this.load()
    },
    onFilterSearch() {
      if (this.submitting) return
      this.saveCommentDraft()
      this.page = 1
      this.selKey = ''
      this.comment = ''
      this.resetDetail()
      this.replaceListQuery({ page: '1', sel: undefined })
      this.load()
    },
    turnPage(page) {
      if (this.submitting) return
      this.saveCommentDraft()
      this.page = page
      this.selKey = ''
      this.comment = ''
      this.resetDetail()
      this.replaceListQuery({ page: String(page), sel: undefined })
      this.load()
    },
    select(row, { force = false } = {}) {
      if (!row || (this.submitting && !force)) return
      this.saveCommentDraft()
      this.selKey = this.rowKey(row)
      this.comment = ''
      this.formError = ''
      this.resetDetail()
      this.replaceListQuery({ sel: this.selKey })
      this.loadSelectedDetail()
    },
    async loadVersionHistory(recordId, requestKey) {
      try {
        const data = await graduationMaterialCenterApi.finalVersions(recordId)
        if (this.detailRequestKey !== requestKey) return false
        this.versionHistory = graduationMaterialCenterApi.normalizeVersions(data?.items || [])
      } catch {
        if (this.detailRequestKey !== requestKey) return false
        this.versionHistory = [...this.secureVersionFiles]
      }
      return true
    },
    async loadSelectedDetail() {
      const row = this.selectedRow
      if (!row || row.status === 'NOT_SUBMITTED' || !row.id) { this.resetDetail(); return false }
      const batchId = this.batchStore.selectedBatchId
      const oldCanonicalVersionId = this.canonicalFileVersionId
      const oldActiveVersionId = this.activePreviewVersionId
      const oldActiveFile = this.activePreviewFile ? { ...this.activePreviewFile } : null
      const oldDraft = this.comment
      this.saveCommentDraft()
      const requestKey = `${++this.detailToken}:${row.id}:${batchId}`
      this.detailRequestKey = requestKey
      this.detailLoading = true
      this.detailError = ''
      try {
        const res = await graduationApi.getFinalDetail(row.id, { batchId })
        if (this.detailRequestKey !== requestKey || this.rowKey(row) !== this.selKey) return false
        if (res.code !== 0) {
          this.finalDetail = null
          this.versionHistory = []
          this.detailError = res.message || '成果安全版本详情加载失败'
          return false
        }
        this.finalDetail = res.data
        const versionsReady = await this.loadVersionHistory(row.id, requestKey)
        if (!versionsReady || this.detailRequestKey !== requestKey || this.rowKey(row) !== this.selKey) return false
        const latest = this.canonicalFileVersionId
        if (oldCanonicalVersionId != null && latest != null && String(oldCanonicalVersionId) !== String(latest)) {
          this.versionConflict = { old: oldCanonicalVersionId, latest }
          this.draftFileVersionId = oldCanonicalVersionId
          this.activePreviewVersionId = oldActiveVersionId ?? oldCanonicalVersionId
          this.conflictPreviewFile = oldActiveFile
          this.activePreviewFileKey = oldActiveFile ? this.fileKey(oldActiveFile) : null
          this.restoreCommentDraft(oldDraft)
          return true
        }
        this.versionConflict = null
        this.conflictPreviewFile = null
        this.draftFileVersionId = latest
        this.activePreviewVersionId = latest
        const active = this.secureVersionFiles.find((item) => String(this.versionKey(item)) === String(this.activePreviewVersionId)) || this.secureVersionFiles[0] || null
        this.activePreviewFileKey = active ? this.fileKey(active) : null
        this.restoreCommentDraft(oldDraft)
        return true
      } catch (error) {
        if (this.detailRequestKey === requestKey && this.rowKey(row) === this.selKey) {
          this.finalDetail = null
          this.versionHistory = []
          this.detailError = error?.message || '成果安全版本详情加载失败，请稍后重试'
        }
        return false
      } finally {
        if (this.detailRequestKey === requestKey) this.detailLoading = false
      }
    },
    selectPreviewFile(item) {
      if (!item || this.submitting) return
      const carriedDraft = this.comment
      const previousDraftKey = this.draftKey()
      this.saveCommentDraft()
      this.activePreviewFileKey = this.fileKey(item)
      this.activePreviewVersionId = this.versionKey(item)
      this.conflictPreviewFile = null
      if (this.versionConflict && String(this.activePreviewVersionId) === String(this.canonicalFileVersionId) && this.finalDetail?.reviewReady) {
        this.versionConflict = null
        this.draftFileVersionId = this.canonicalFileVersionId
      }
      if (this.draftKey() !== previousDraftKey) {
        this.restoreCommentDraft(carriedDraft)
        this.saveCommentDraft()
      } else {
        this.comment = carriedDraft
      }
    },
    selectPreviewVersion(item) { this.selectPreviewFile(item) },
    async downloadActivePreview() {
      if (this.submitting || !this.activePreviewFile?.canDownload) return
      try { await graduationMaterialCenterApi.downloadMaterial(this.activePreviewFile) } catch (error) { toast.error(error?.message || '下载失败') }
    },
    step(delta) {
      if (this.submitting) return
      const target = this.selIndex + delta
      if (target >= 0 && target < this.rows.length) { this.select(this.rows[target]); return }
      if (delta > 0 && this.page * this.pageSize < this.total) { this._selectIndexAfterLoad = 0; this.turnPage(this.page + 1) }
      else if (delta < 0 && this.page > 1) { this._selectLastAfterLoad = true; this.turnPage(this.page - 1) }
    },
    ensureSelection() {
      if (this.selectedRow) { this.loadSelectedDetail(); return }
      if (!this.rows.length) {
        this.selKey = ''
        this.resetDetail()
        this.replaceListQuery({ sel: undefined })
        return
      }
      let target = null
      if (Number.isInteger(this._selectIndexAfterLoad)) target = this.rows[Math.min(this._selectIndexAfterLoad, this.rows.length - 1)]
      else if (this._selectLastAfterLoad) target = this.rows[this.rows.length - 1]
      else target = this.rows.find((row) => row.status === 'PENDING_REVIEW') || this.rows[0]
      this._selectIndexAfterLoad = null
      this._selectLastAfterLoad = false
      if (target && !this.isNarrow) this.select(target, { force: true })
    },
    openDossier(row) {
      if (this.submitting) return
      if (row?.projectId) this.$router.push(`/admin/graduation/students/${row.projectId}`)
    },
    exportFinalsFn() {
      const hint = exportFilenameHint(this.batchStore.selectedBatchName, '成果提交')
      const params = buildMaterialQuery(this.filters, { batchId: this.batchStore.selectedBatchId })
      return graduationApi.exportFinals(params).then((res) => {
        if (res.code === 0 && res.data) res.data = { ...res.data, filename: res.data.filename || `${hint}.xlsx` }
        return res
      })
    },
    async refreshSelectedConflictTruth(response, draft) {
      const selectedKey = this.selKey
      await this.loadStats()
      if (this.selKey !== selectedKey) return
      await this.loadSelectedDetail()
      if (this.selKey !== selectedKey) return
      this.comment = draft
      this.saveCommentDraft()
      const message = graduationConflictMessage(response)
      this.formError = message
      toast.error(message)
    },
    async submitReview(action) {
      if (this.submitting || !this.canReview || !this.selectedRow) return
      this.formError = ''
      if (action === 'REJECT' && (!this.comment || this.comment.trim().length < 5)) {
        this.formError = '退回原因必填且不少于 5 个字'
        return
      }
      const selectedKey = this.selKey
      const recordId = this.selectedRow.id
      const reviewedIndex = Math.max(0, this.selIndex)
      const pendingQueue = this.filters.status === 'PENDING_REVIEW'
      const draft = this.comment
      const targetName = this.selectedRow.studentName || '当前学生'
      const command = {
        action,
        comment: draft,
        expectedVersion: this.finalDetail.materialVersion,
        fileVersionId: this.finalDetail.fileVersionId
      }
      this.submitting = true
      try {
        const res = await graduationApi.reviewFinal(recordId, command)
        if (this.selKey !== selectedKey) return
        if (res.code === 0) {
          this.clearCommentDraft()
          this.comment = ''
          await this.loadStats()
          this.reviewReceipt = {
            title: `${targetName}的成果材料已处理`,
            result: `服务器最新结论：${res.data.statusLabel}；待审队列已回读`,
            next: action === 'APPROVE' ? '该版本可进入正式评阅、答辩或成绩环节。' : '下一步由学生按意见修改并提交新版本。'
          }
          toast.success('批阅完成，服务器最新结论与待审队列已回读')
          if (!this.autoNext || !pendingQueue) {
            if (this.selectedRow) { this.selectedRow.status = res.data.status; this.selectedRow.statusLabel = res.data.statusLabel }
            await this.loadSelectedDetail()
            return
          }
          this.selKey = ''
          this.resetDetail()
          this._selectIndexAfterLoad = reviewedIndex
          await this.load()
          if (!this.rows.length && this.page > 1) {
            this.page -= 1
            this._selectIndexAfterLoad = this.pageSize - 1
            await this.load()
          }
          if (!this.rows.length) toast.success('待审成果已全部处理完')
        } else if (isGraduationConflictResponse(res)) {
          await this.refreshSelectedConflictTruth(res, draft)
        } else {
          this.formError = graduationActionErrorMessage(res, '成果批阅未完成，请稍后重试')
          this.saveCommentDraft()
        }
      } catch (error) {
        if (this.selKey === selectedKey) {
          this.formError = error?.message || '成果批阅未完成，请稍后重试'
          this.saveCommentDraft()
        }
      } finally {
        this.submitting = false
      }
    },
    async remind(row) {
      if (this.reminding || this.submitting) return
      this.reminding = true
      try {
        const res = await graduationApi.remindFinal(row.projectId || row.gdStudentId)
        if (res.code === 0) toast.success(`已向 ${row.studentName} 发送成果催交站内消息并记录催办留痕`)
        else toast.error(res.message || '催交失败')
      } catch (error) {
        toast.error(error?.message || '催交失败')
      } finally {
        this.reminding = false
      }
    },
    async load() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.loadToken
      if (!batchId) {
        this.loading = false
        this.error = ''
        this.rows = []
        this.total = 0
        this.selKey = ''
        this.resetDetail()
        return false
      }
      this.loading = true
      this.error = ''
      try {
        const res = await graduationApi.getFinalSubmissions(buildMaterialQuery(this.filters, {
          page: this.page,
          pageSize: this.pageSize,
          batchId
        }))
        if (token !== this.loadToken || String(batchId) !== String(this.batchStore.selectedBatchId)) return false
        if (res.code === 0) {
          this.rows = Array.isArray(res.data?.list) ? res.data.list : []
          this.total = Number(res.data?.total) || 0
          this.ensureSelection()
        } else {
          this.error = res.message || '成果列表加载失败'
          this.resetDetail()
        }
        return res.code === 0
      } catch (error) {
        if (token === this.loadToken && String(batchId) === String(this.batchStore.selectedBatchId)) {
          this.error = error?.message || '成果列表加载失败，请稍后重试'
          this.resetDetail()
        }
        return false
      } finally {
        if (token === this.loadToken && String(batchId) === String(this.batchStore.selectedBatchId)) this.loading = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.fr-workbench-stack { gap: var(--space-2); }
.fr-command { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 10px 12px; border: 1px solid var(--primary-100, #dbeafe); border-radius: 10px; background: linear-gradient(110deg, var(--primary-50, #eff6ff), var(--card, #fff) 72%); }
.fr-command__copy { display: grid; min-width: 0; gap: 2px; }
.fr-command__copy span { color: var(--primary-600, #2563eb); font-size: 10px; font-weight: 700; letter-spacing: .08em; }
.fr-command__copy strong { overflow: hidden; color: var(--text-primary); font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
.fr-command__counts { display: flex; gap: 6px; }
.fr-command__counts span { display: inline-flex; align-items: baseline; gap: 4px; padding: 5px 8px; border: 1px solid var(--border-light); border-radius: var(--radius-full); background: rgba(255,255,255,.78); color: var(--text-tertiary); font-size: 10px; white-space: nowrap; }
.fr-command__counts b { color: var(--primary-700, #1d4ed8); font-size: 14px; }
.mp-tabs { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-1); }
.mp-tab { padding: 6px 10px; }
.mp-tab:disabled { cursor: not-allowed; opacity: .58; }
.fr-tab-count { margin-left: 4px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.mp-tab.is-active .fr-tab-count { color: inherit; }
.fr-filter-row { display: flex; align-items: center; gap: 10px; }
.fr-filter-row > :first-child { flex: 0 1 420px; }
.fr-selected-summary { min-width: 0; overflow: hidden; color: var(--text-secondary); font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.fr-selected-summary b { color: var(--text-primary); }
.fr-selected-summary em { margin-left: 8px; color: var(--warning-700, #a16207); font-style: normal; font-weight: 700; }
.fr-list__foot { display: flex; justify-content: center; padding: 8px; }
.fr-review-blocked { padding: 8px; border-radius: 8px; background: var(--warning-50, #fffbeb); color: var(--warning-700, #a16207); font-size: 12px; }
.fr-review-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.fr-review-actions > * { width: 100%; }
.mp-textarea { width: 100%; min-height: 96px; resize: vertical; }
.mp-textarea:disabled { cursor: not-allowed; opacity: .72; }
.fr-receipt { display: flex; align-items: center; gap: 14px; padding: 11px 12px; border: 1px solid #b7ebc6; border-radius: 9px; background: #f0fff4; }
.fr-receipt div { display: grid; flex: 1; gap: 3px; }
.fr-receipt strong { color: #137a43; }
.fr-receipt span { font-size: 13px; }
.fr-receipt small { color: var(--text-tertiary); }
.fr-receipt button { border: 0; background: transparent; color: var(--primary-600); cursor: pointer; }
@media (max-width: 1100px) {
  .fr-command { grid-template-columns: 1fr; }
  .fr-command__counts { overflow-x: auto; }
  .fr-filter-row { align-items: stretch; flex-direction: column; }
  .fr-filter-row > :first-child { flex-basis: auto; max-width: none; }
}
</style>
