<template>
  <ModulePageShell
    title="成果检查"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton v-if="exportPerm.visible" :export-fn="exportFinalsFn" :has-permission="exportPerm.allowed">导出成果清单</AppExportButton>
    </template>

    <div class="mp-stack fr-workbench-stack">
      <div class="mp-tabs">
        <button v-for="t in tabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}<span v-if="tabCount(t.value) !== null" class="fr-tab-count">{{ tabCount(t.value) }}</span>
        </button>
      </div>

      <div v-if="hasBatch" class="fr-filter-row">
        <AppSearchBox v-model="filters.keyword" placeholder="搜索学生 / 学号 / 课题" @search="onFilterSearch" />
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDesc" />

      <GraduationDocumentReviewWorkspace
        v-else
        :queue="rows"
        :current-index="Math.max(selIndex, 0)"
        :current-record="selectedRow"
        :detail="finalDetail"
        :files="secureVersionFiles"
        :versions="secureVersionFiles"
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
          <div class="fr-list__foot"><AppPagination :total="total" :page="page" :page-size="pageSize" :show-size-changer="false" @update:page="turnPage" /></div>
        </template>

        <template #review>
          <LoadingState v-if="detailLoading" />
          <ErrorState v-else-if="detailError" :description="detailError" @retry="loadSelectedDetail" />
          <template v-else-if="selectedRow?.status === 'NOT_SUBMITTED'">
            <AppButton variant="primary" :loading="reminding" @click="remind(selectedRow)">发送成果催交提醒</AppButton>
            <p class="mp-note">本操作会创建真实站内消息并写入催办留痕。</p>
          </template>
          <template v-else-if="selectedRow?.status === 'PENDING_REVIEW'">
            <div v-if="!canReview" class="fr-review-blocked">{{ reviewReason }}（以下操作已置灰）</div>
            <label class="mp-note">批阅意见（退回时必填，≥5 字）</label>
            <textarea v-model="comment" class="mp-textarea" rows="5" placeholder="批阅意见将同步学生端…" @input="saveCommentDraft"></textarea>
            <AppTemplateChips v-if="canReview" size="compact" :options="REJECT_REASON_CHIPS" @pick="appendComment" />
            <p v-if="formError" class="mp-form-err">{{ formError }}</p>
            <div class="fr-review-actions">
              <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="primary" :loading="submitting" @click="submitReview('APPROVE')">✓ 通过当前版本</AppPermissionButton>
              <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="warning" :loading="submitting" @click="submitReview('REJECT')">↩ 退回当前版本</AppPermissionButton>
            </div>
            <p class="mp-note">提交 payload 始终锁定服务端 canonical <code>expectedVersion + fileVersionId</code>；Viewer 展示形式不会改变审核源版本。</p>
          </template>
          <template v-else>
            <div class="mp-kv"><span class="mp-kv__k">批阅结果</span><span class="mp-kv__v">{{ selectedRow?.statusLabel || '—' }}</span></div>
            <p class="mp-note">已批阅版本继续保留追溯；学生重交后会生成新的 FileVersion。</p>
          </template>
        </template>
      </GraduationDocumentReviewWorkspace>

      <p class="mp-note">初稿 / 定稿顺序、查重超标、文件安全门和 canonical FileVersion 均由后端真实状态校验；历史版本只读。</p>
    </div>
    <AppPageGuide guide-key="graduation.gd-final-review" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
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
    AppPageGuide, ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppButton,
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
      detailLoading: false,
      detailError: '',
      detailRequestKey: '',
      activePreviewFileKey: null,
      activePreviewVersionId: null,
      readerMode: 'embedded',
      previewDraftKey: '',
      versionConflict: null,
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
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const batch = this.batchStore.selectedBatchName ? `${this.batchStore.selectedBatchName} · ` : ''
      if (!this.stats) return `${batch}左队列 → 中文档 → 右审核 · canonical FileVersion 锁定`
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
      if (!this.secureVersionFiles.length) return null
      return this.secureVersionFiles.find((item) => String(this.fileKey(item)) === String(this.activePreviewFileKey))
        || this.secureVersionFiles.find((item) => String(this.versionKey(item)) === String(this.activePreviewVersionId))
        || this.secureVersionFiles[0]
    },
    previewDescriptor() { return this.activePreviewFile ? graduationMaterialCenterApi.previewDescriptor(this.activePreviewFile) : null },
    canReview() {
      const pa = this.ctx.permissionActions.reviewFinal
      return !!(
        pa && pa.visible && pa.allowed && this.ctx.writeEnabled !== false &&
        this.selectedRow?.status === 'PENDING_REVIEW' && !this.detailLoading &&
        this.finalDetail?.reviewReady && !this.versionConflict &&
        String(this.activePreviewVersionId ?? '') === String(this.canonicalFileVersionId ?? '')
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
      if (this.versionConflict) return '学生已提交新版本，请切换最新版本后重新核验'
      if (String(this.activePreviewVersionId ?? '') !== String(this.canonicalFileVersionId ?? '')) return '当前正在阅读历史版本，历史版本只读不可批阅'
      return ''
    },
    pageStartIndex() { return (this.page - 1) * this.pageSize },
    selectedRow() { return this.rows.find((row) => this.rowKey(row) === this.selKey) || null },
    selIndex() { return this.rows.findIndex((row) => this.rowKey(row) === this.selKey) },
    hasNext() { return this.selIndex < this.rows.length - 1 || this.page * this.pageSize < this.total }
  },
  created() {
    const qTab = (this.$route.query.tab || '').toString()
    if (this.tabs.some((item) => item.value === qTab)) this.filters.status = qTab
    this.selKey = (this.$route.query.sel || '').toString()
    this.loadStats()
    this.load()
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.saveCommentDraft()
      this.page = 1
      this.selKey = ''
      this.resetDetail()
      this.loadStats()
      this.load()
    }
  },
  mounted() {
    this._mq = window.matchMedia('(max-width: 1100px)')
    this.isNarrow = this._mq.matches
    this._onMq = (event) => { this.isNarrow = event.matches }
    this._mq.addEventListener ? this._mq.addEventListener('change', this._onMq) : this._mq.addListener(this._onMq)
    this._onKey = (event) => {
      if (this.isNarrow) return
      const tag = event.target?.tagName || ''
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return
      if (event.key === 'ArrowDown') { event.preventDefault(); this.step(1) }
      if (event.key === 'ArrowUp') { event.preventDefault(); this.step(-1) }
    }
    window.addEventListener('keydown', this._onKey)
  },
  beforeUnmount() {
    this.saveCommentDraft()
    if (this._mq) this._mq.removeEventListener ? this._mq.removeEventListener('change', this._onMq) : this._mq.removeListener(this._onMq)
    window.removeEventListener('keydown', this._onKey)
  },
  methods: {
    rowKey(row) { return row?.id != null ? String(row.id) : `ns-${row?.gdStudentId}` },
    versionKey(item) { return item?.fileVersionId ?? item?.versionId ?? item?.id ?? null },
    fileKey(item) { return item?.fileKey ?? item?.fileId ?? this.versionKey(item) },
    statusCount(status) { const stat = (this.stats?.byStatus || []).find((item) => item.status === status); return stat ? stat.count : 0 },
    tabCount(value) { if (!this.stats || value === '' || value === 'NOT_SUBMITTED') return null; return this.statusCount(value) },
    resetDetail() {
      this.finalDetail = null
      this.detailLoading = false
      this.detailError = ''
      this.detailRequestKey = ''
      this.activePreviewFileKey = null
      this.activePreviewVersionId = null
      this.previewDraftKey = ''
      this.versionConflict = null
    },
    draftKey(row = this.selectedRow, fileVersionId = this.canonicalFileVersionId) {
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
    restoreCommentDraft() {
      this.previewDraftKey = this.draftKey()
      if (!this.previewDraftKey) return
      try { this.comment = sessionStorage.getItem(this.previewDraftKey) || '' } catch { this.comment = '' }
    },
    clearCommentDraft() {
      const key = this.previewDraftKey || this.draftKey()
      if (key) { try { sessionStorage.removeItem(key) } catch { /* ignore */ } }
      this.previewDraftKey = ''
    },
    appendComment(text) { this.comment = this.comment ? `${this.comment}\n${text}` : text; this.saveCommentDraft() },
    async loadStats() {
      if (!this.batchStore.selectedBatchId) { this.stats = null; return }
      const res = await graduationMoreApi.getFinalStats({ batchId: this.batchStore.selectedBatchId })
      if (res.code === 0) this.stats = res.data
    },
    switchTab(value) {
      this.saveCommentDraft()
      this.filters.status = value
      this.page = 1
      this.selKey = ''
      this.comment = ''
      this.resetDetail()
      const query = { ...this.$route.query, tab: value || undefined }
      delete query.sel
      this.$router.replace({ query })
      this.load()
    },
    onFilterSearch() { this.page = 1; this.load() },
    turnPage(page) { this.saveCommentDraft(); this.page = page; this.selKey = ''; this.comment = ''; this.resetDetail(); this.load() },
    select(row) {
      if (!row) return
      this.saveCommentDraft()
      this.selKey = this.rowKey(row)
      this.comment = ''
      this.formError = ''
      this.resetDetail()
      this.$router.replace({ query: { ...this.$route.query, sel: this.selKey } })
      this.loadSelectedDetail()
    },
    async loadSelectedDetail() {
      const row = this.selectedRow
      if (!row || row.status === 'NOT_SUBMITTED' || !row.id) { this.resetDetail(); return }
      const oldCanonicalVersionId = this.canonicalFileVersionId
      const oldActiveVersionId = this.activePreviewVersionId
      const requestKey = `${row.id}:${this.batchStore.selectedBatchId}:${Date.now()}`
      this.detailRequestKey = requestKey
      this.detailLoading = true
      this.detailError = ''
      const res = await graduationApi.getFinalDetail(row.id, { batchId: this.batchStore.selectedBatchId })
      if (this.detailRequestKey !== requestKey) return
      this.detailLoading = false
      if (res.code !== 0) {
        this.finalDetail = null
        this.detailError = res.message || '成果安全版本详情加载失败'
        return
      }
      this.finalDetail = res.data
      const latest = this.canonicalFileVersionId
      if (oldCanonicalVersionId != null && latest != null && String(oldCanonicalVersionId) !== String(latest)) {
        this.versionConflict = { old: oldCanonicalVersionId, latest }
        this.activePreviewVersionId = oldActiveVersionId ?? oldCanonicalVersionId
      } else {
        this.versionConflict = null
        this.activePreviewVersionId = latest
      }
      const active = this.secureVersionFiles.find((item) => String(this.versionKey(item)) === String(this.activePreviewVersionId)) || this.secureVersionFiles[0] || null
      this.activePreviewFileKey = active ? this.fileKey(active) : null
      this.restoreCommentDraft()
    },
    selectPreviewFile(item) {
      if (!item) return
      this.activePreviewFileKey = this.fileKey(item)
      this.activePreviewVersionId = this.versionKey(item)
      if (this.versionConflict && String(this.activePreviewVersionId) === String(this.canonicalFileVersionId) && this.finalDetail?.reviewReady) this.versionConflict = null
    },
    selectPreviewVersion(item) { this.selectPreviewFile(item) },
    async downloadActivePreview() {
      if (!this.activePreviewFile?.canDownload) return
      try { await graduationMaterialCenterApi.downloadMaterial(this.activePreviewFile) } catch (error) { toast.error(error?.message || '下载失败') }
    },
    step(delta) {
      const target = this.selIndex + delta
      if (target >= 0 && target < this.rows.length) { this.select(this.rows[target]); return }
      if (delta > 0 && this.page * this.pageSize < this.total) { this._selectIndexAfterLoad = 0; this.turnPage(this.page + 1) }
      else if (delta < 0 && this.page > 1) { this._selectLastAfterLoad = true; this.turnPage(this.page - 1) }
    },
    ensureSelection() {
      if (this.selectedRow) { this.loadSelectedDetail(); return }
      if (!this.rows.length) { this.selKey = ''; this.resetDetail(); return }
      let target = null
      if (Number.isInteger(this._selectIndexAfterLoad)) target = this.rows[Math.min(this._selectIndexAfterLoad, this.rows.length - 1)]
      else if (this._selectLastAfterLoad) target = this.rows[this.rows.length - 1]
      else target = this.rows.find((row) => row.status === 'PENDING_REVIEW') || this.rows[0]
      this._selectIndexAfterLoad = null
      this._selectLastAfterLoad = false
      if (target && !this.isNarrow) this.select(target)
    },
    openDossier(row) { if (row?.projectId) this.$router.push(`/admin/graduation/students/${row.projectId}`) },
    exportFinalsFn() {
      const hint = exportFilenameHint(this.batchStore.selectedBatchName, '成果提交')
      const params = buildMaterialQuery(this.filters, { batchId: this.batchStore.selectedBatchId })
      return graduationApi.exportFinals(params).then((res) => { if (res.code === 0 && res.data) res.data = { ...res.data, filename: res.data.filename || `${hint}.xlsx` }; return res })
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
      if (!this.canReview || !this.selectedRow) return
      this.formError = ''
      if (action === 'REJECT' && (!this.comment || this.comment.trim().length < 5)) { this.formError = '退回原因必填且不少于 5 个字'; return }
      const reviewedIndex = Math.max(0, this.selIndex)
      const pendingQueue = this.filters.status === 'PENDING_REVIEW'
      const draft = this.comment
      this.submitting = true
      const res = await graduationApi.reviewFinal(this.selectedRow.id, {
        action,
        comment: draft,
        expectedVersion: this.finalDetail.materialVersion,
        fileVersionId: this.finalDetail.fileVersionId
      })
      this.submitting = false
      if (res.code === 0) {
        this.clearCommentDraft()
        this.comment = ''
        toast.success(`批阅完成：${res.data.statusLabel}，服务端已锁定 canonical FileVersion`)
        await this.loadStats()
        if (!this.autoNext || !pendingQueue) {
          if (this.selectedRow) { this.selectedRow.status = res.data.status; this.selectedRow.statusLabel = res.data.statusLabel }
          await this.loadSelectedDetail()
          return
        }
        this.selKey = ''
        this.resetDetail()
        this._selectIndexAfterLoad = reviewedIndex
        await this.load()
        if (!this.rows.length && this.page > 1) { this.page -= 1; this._selectIndexAfterLoad = this.pageSize - 1; await this.load() }
        if (!this.rows.length) toast.success('待审成果已全部处理完')
      } else if (isGraduationConflictResponse(res)) {
        await this.refreshSelectedConflictTruth(res, draft)
      } else {
        this.formError = graduationActionErrorMessage(res, '成果批阅未完成，请稍后重试')
        this.saveCommentDraft()
      }
    },
    async remind(row) {
      this.reminding = true
      const res = await graduationApi.remindFinal(row.projectId || row.gdStudentId)
      this.reminding = false
      if (res.code === 0) toast.success(`已向 ${row.studentName} 发送成果催交站内消息并记录催办留痕`)
      else toast.error(res.message || '催交失败')
    },
    async load() {
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = ''; this.rows = []; this.total = 0; this.selKey = ''; this.resetDetail(); return
      }
      this.loading = true
      this.error = ''
      const res = await graduationApi.getFinalSubmissions(buildMaterialQuery(this.filters, { page: this.page, pageSize: this.pageSize, batchId: this.batchStore.selectedBatchId }))
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total; this.ensureSelection() }
      else { this.error = res.message; this.resetDetail() }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.fr-workbench-stack{gap:var(--space-2)}.mp-tabs{display:flex;align-items:center;flex-wrap:wrap;gap:var(--space-1)}.mp-tab{padding:6px 10px}.fr-tab-count{margin-left:4px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.mp-tab.is-active .fr-tab-count{color:inherit}.fr-filter-row{display:flex;max-width:420px}.fr-list__foot{padding:8px;display:flex;justify-content:center}.fr-review-blocked{padding:8px;border-radius:8px;background:var(--warning-50,#fffbeb);color:var(--warning-700,#a16207);font-size:12px}.fr-review-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.fr-review-actions>*{width:100%}.mp-textarea{width:100%;resize:vertical;min-height:96px}.mp-note code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
</style>
