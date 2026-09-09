<template>
  <ModulePageShell
    title="材料与证据中心"
    subtitle="按学生核对实习材料，查看安全状态与归档清单。"
    :watermark="false"
  >
    <template #actions>
      <AppButton v-if="selectedId" variant="ghost" :disabled="syncing" @click="closeStudent">返回学生列表</AppButton>
      <AppButton variant="ghost" :disabled="syncing || loading || detailLoading" @click="refreshCurrent">刷新</AppButton>
      <AppButton v-if="selected && canSync" variant="secondary" :loading="syncing" :disabled="detailLoading" @click="syncCurrent">同步业务材料</AppButton>
    </template>

    <section v-if="!selectedId" class="filter-bar" aria-label="材料查询">
      <AppSearchBox v-model="keyword" placeholder="搜索学生姓名或学号" @search="reload" />
      <label for="material-safety">材料状态</label>
      <select id="material-safety" v-model="safetyStatus" @change="reload">
        <option value="">全部状态</option><option value="READY">全部安全可用</option>
        <option value="UNSAFE">存在待处理材料</option><option value="NOT_SYNCED">尚未登记材料</option>
      </select>
      <span v-if="!loading && !error" class="filter-hint">当前筛选 {{ total }} 人</span>
    </section>

    <div v-if="error && !selectedId" class="state error-state" role="alert">
      {{ error }}
      <button type="button" @click="load">重新加载</button>
    </div>

    <section v-else class="workspace">
      <div v-if="!selectedId" class="student-panel">
        <div v-if="loading" class="state">正在读取材料安全状态…</div>
        <div v-else-if="!rows.length" class="state">当前筛选条件下暂无学生</div>
        <button
          v-for="row in rows"
          v-else
          :key="row.internshipId"
          type="button"
          class="student-row"
          :class="{ active: selectedId === row.internshipId }"
          @click="openStudent(row)"
        >
          <div>
            <strong>{{ row.studentName || '未命名学生' }}</strong>
            <span>{{ row.studentNo || '-' }} · {{ row.enterpriseName || '未分配企业' }}</span>
          </div>
          <div class="row-status">
            <AppStatusTag :type="statusTone(row.safetyStatus)" size="sm">
              {{ statusText(row.safetyStatus) }}
            </AppStatusTag>
            <small>{{ row.materialCount ? `${row.readyCount}/${row.materialCount} 份安全可用` : '尚无登记材料' }}</small>
          </div>
        </button>
        <AppPagination v-if="!loading && total > pageSize" :total="total" :page="page" :page-size="pageSize" :show-size-changer="false" @change="changePage" />
      </div>

      <div v-else class="detail-panel">
        <div v-if="syncReceipt" class="sync-receipt" role="status">{{ syncReceipt }}</div>
        <div v-if="operationError" class="state error-state" role="alert">{{ operationError }}</div>
        <div v-if="detailLoading" class="state">正在加载文件版本…</div>
        <div v-else-if="detailError" class="state error-state" role="alert">{{ detailError }}<AppButton variant="ghost" @click="refreshDetail">重新加载</AppButton></div>
        <div v-else-if="!selected" class="state">正在读取学生材料…</div>
        <template v-else>
          <header class="detail-head">
            <div>
              <h2 id="material-student-title" tabindex="-1">{{ selected.studentName }}<small>{{ selected.studentNo }}</small></h2>
              <span>{{ selected.enterpriseName || '未分配企业' }} · 指导教师：{{ selected.advisorName || '-' }}</span>
            </div>
            <AppStatusTag :type="statusTone(selectedStatus)">{{ statusText(selectedStatus) }}</AppStatusTag>
          </header>

          <dl class="material-summary">
            <div><dt>已登记材料</dt><dd>{{ summary.total }}<small>份</small></dd></div>
            <div><dt>安全可用</dt><dd>{{ summary.ready }}<small>份</small></dd></div>
            <div><dt>待处理</dt><dd :class="{ danger: summary.unsafe > 0 }">{{ summary.unsafe }}<small>份</small></dd></div>
          </dl>
          <div class="material-note"><span>安全可用表示文件通过检查；是否满足实习归档要求仍需核验。</span><AppButton variant="ghost" size="sm" @click="goArchive">核对归档条件</AppButton></div>
          <section v-if="!previewRequested" class="file-workspace">
            <SecureFileList :items="selected.items" :loading="syncing" :empty-text="canSync ? '尚无登记材料，可同步现有业务记录中的附件。' : '尚无登记材料，请有权限的人员同步业务材料。'" @preview="previewFile" @download="downloadFile" @refresh="refreshDetail" />
          </section>
          <div v-else-if="!activePreviewFile" class="state error-state" role="alert">当前文件不属于该学生的可预览材料，或安全状态已变化。<AppButton variant="ghost" @click="closePreview">返回材料列表</AppButton></div>
          <section v-if="activePreviewFile" class="section-card reader-card">
            <div class="section-title">
              <div>
                <strong id="material-reader-title" tabindex="-1">{{ activePreviewFile.fileName }}</strong>
                <span>{{ activePreviewFile.categoryLabel || activePreviewFile.title }} · 当前安全版本</span>
              </div>
              <AppButton variant="ghost" size="sm" @click="closePreview">返回材料列表</AppButton>
            </div>
            <AppDocumentViewer
              :key="`${detailContext}:${activePreviewFile.fileId}:${activePreviewFile.versionId}`"
              :descriptor="previewDescriptor"
              :provider="previewProvider"
              :files="previewFiles"
              :versions="[activePreviewFile]"
              :active-file-key="activePreviewFile.fileId"
              :active-version-id="activePreviewFile.versionId"
              :canonical-version-id="activePreviewFile.versionId"
              :allow-download="Boolean(activePreviewFile.canDownload) && !downloadingId"
              :show-version-bar="false"
              :show-file-switcher="previewFiles.length > 1"
              @select-file="previewFile"
              @download="downloadPreview"
              @preview-error="previewError"
            />
          </section>

          <details class="technical-evidence">
            <summary>查看材料版本与归档清单</summary>
          <section class="section-card">
            <div class="section-title">
              <div><strong>材料版本清单</strong><span>核对每份材料的固定版本、文件检查与审核结果。</span></div>
            </div>
            <div class="table-scroll">
              <table>
                <thead><tr><th>材料</th><th>版本</th><th>版本编号</th><th>文件</th><th>扫描</th><th>审核</th><th>文件校验值</th></tr></thead>
                <tbody>
                  <tr v-for="item in selected.items" :key="item.versionId">
                    <td>{{ item.categoryLabel }}</td>
                    <td>v{{ item.versionNo }}</td>
                    <td class="mono">{{ item.versionId }}</td>
                    <td :title="item.fileName">{{ item.fileName }}</td>
                    <td><AppStatusTag :type="item.readyForBusiness ? 'success' : 'danger'" size="sm">{{ item.scanStatus }}</AppStatusTag></td>
                    <td>{{ item.reviewStatus || '-' }}</td>
                    <td class="mono hash" :title="item.sha256">{{ shortHash(item.sha256) }}</td>
                  </tr>
                  <tr v-if="!selected.items.length"><td colspan="7" class="empty-cell">暂无文件版本</td></tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="section-card manifest-card">
            <div class="section-title">
              <div><strong>归档清单</strong><span>归档时冻结文件名、大小、文件摘要、扫描结论和真实版本号</span></div>
              <AppStatusTag v-if="selected.manifest" :type="manifestTone(selected.manifest.status)">
                {{ manifestStatusLabel(selected.manifest.status) }}
              </AppStatusTag>
            </div>
            <div v-if="!selected.manifest" class="state compact">尚未生成归档版本清单</div>
            <template v-else>
              <dl class="manifest-meta">
                <div><dt>清单版本</dt><dd>第 {{ selected.manifest.revision }} 次修订</dd></div>
                <div><dt>清单编号</dt><dd class="mono">{{ selected.manifest.id }}</dd></div>
                <div><dt>文件版本数</dt><dd>{{ selected.manifest.items.length }}</dd></div>
                <div><dt>清单文件摘要（SHA-256）</dt><dd class="mono" :title="selected.manifest.manifestSha256">{{ selected.manifest.manifestSha256 }}</dd></div>
              </dl>
              <div class="manifest-list">
                <div v-for="item in selected.manifest.items" :key="`${item.versionId}-${item.materialCode}`">
                  <span>{{ item.fileName || item.materialCode }}</span>
                  <strong>版本编号 {{ item.versionId }}</strong>
                  <small>{{ scanResultLabel(item.scanResult) }} · 摘要 {{ shortHash(item.sha256) }}</small>
                </div>
              </div>
            </template>
          </section>
          </details>
        </template>
      </div>
    </section>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSearchBox, AppStatusTag, AppPagination } from '@/components/common'
import AppDocumentViewer from '@/components/file/viewer/AppDocumentViewer.vue'
import SecureFileList from '@/components/file/SecureFileList.vue'
import { internshipMaterialCenterApi } from '@/modules/internship/api/material-center.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/internship/composables/permission'

export default {
  name: 'InternshipMaterialCenterView',
  components: { ModulePageShell, AppButton, AppSearchBox, AppStatusTag, AppDocumentViewer, SecureFileList, AppPagination },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20,
      keyword: '', safetyStatus: '', loading: false, detailLoading: false,
      syncing: false, error: '', selectedId: '', selected: null,
      activePreviewFileId: '', detailError: '', operationError: '', syncReceipt: '', downloadingId: '',
      listSeq: 0, detailSeq: 0, epoch: 0, requestKey: '', removeRouteGuard: null,
      previewProvider: internshipMaterialCenterApi.createPreviewProvider()
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    canView() { return canCode(this.ctx, 'internship.archive.view') },
    canSync() { return canCode(this.ctx, 'internship.archive.manage') },
    scopeKey() { return JSON.stringify([this.epoch, String(this.batchStore.selectedBatchId || '')]) },
    listContext() { return JSON.stringify([this.scopeKey, this.keyword, this.safetyStatus, this.page]) },
    detailContext() { return `${this.scopeKey}:${this.selectedId}` },
    previewRequested() { return typeof this.$route.query.file === 'string' && !!this.$route.query.file },
    selectedStatus() { return !this.summary.total ? 'NOT_SYNCED' : this.summary.unsafe ? 'UNSAFE' : 'READY' },
    summary() {
      return this.selected?.summary || { total: 0, ready: 0, unsafe: 0 }
    },
    previewFiles() {
      return (this.selected?.items || []).filter((item) => item.canPreview && item.readyForBusiness)
    },
    activePreviewFile() {
      return this.previewFiles.find((item) => String(item.fileId) === String(this.activePreviewFileId)) || null
    },
    previewDescriptor() {
      return this.activePreviewFile ? internshipMaterialCenterApi.previewDescriptor(this.activePreviewFile) : null
    }
  },
  watch: {
    '$route.query'() { this.restoreQuery(); if (this.requestKey !== this.listContext) this.load(); this.syncRouteDetail() },
    'batchStore.selectedBatchId'(next, previous) {
      this.epoch++; this.clearDetail(); this.selectedId = ''; this.page = 1
      if (previous && String(next) !== String(previous)) {
        this.keyword = ''; this.safetyStatus = ''
        this.navigate({ id: undefined, file: undefined, page: '1', keyword: undefined, safetyStatus: undefined }, true)
        this.load()
      } else { this.restoreQuery(); this.load(); this.syncRouteDetail() }
    },
    ctx: { deep: true, handler() { this.epoch++; this.clearDetail(); this.selectedId = ''; this.load(); this.syncRouteDetail() } }
  },
  created() { this.restoreQuery(); this.load(); this.syncRouteDetail() },
  mounted() { this.removeRouteGuard = this.$router.beforeEach((to, from) => to.fullPath === from.fullPath || !this.syncing) },
  beforeUnmount() { this.epoch++; this.listSeq++; this.clearDetail(); this.removeRouteGuard?.() },
  methods: {
    navigate(extra, replace = false) {
      if (this.syncing) return
      return this.$router[replace ? 'replace' : 'push']({ path: '/admin/internship/material-center', query: this.batchStore.withBatchQuery({ ...this.$route.query, ...extra }) })
    },
    restoreQuery() {
      const q = this.$route.query
      this.keyword = typeof q.keyword === 'string' ? q.keyword : ''
      this.safetyStatus = ['READY', 'UNSAFE', 'NOT_SYNCED'].includes(q.safetyStatus) ? q.safetyStatus : ''
      this.page = /^[1-9]\d*$/.test(String(q.page || '')) ? Math.min(Number(q.page), 1000000) : 1
    },
    syncRouteDetail() {
      const id = typeof this.$route.query.id === 'string' ? this.$route.query.id : ''
      if (id !== this.selectedId) { this.clearDetail(); this.selectedId = id; if (id) this.refreshDetail() }
      else this.restorePreview()
    },
    clearDetail() { this.detailSeq++; this.selected = null; this.activePreviewFileId = ''; this.detailError = ''; this.operationError = ''; this.syncReceipt = ''; this.detailLoading = false; this.syncing = false; this.downloadingId = '' },
    async load() {
      const seq = ++this.listSeq, key = this.listContext
      this.requestKey = key; this.rows = []; this.total = 0; this.error = ''; this.loading = false
      if (!this.batchStore.selectedBatchId) { this.error = '请先选择实习批次'; return }
      if (!this.canView) { this.error = '无材料查看权限'; return }
      this.loading = true
      try {
        const data = await internshipMaterialCenterApi.list({ page: this.page, pageSize: this.pageSize, batchId: this.batchStore.selectedBatchId, keyword: this.keyword || undefined, safetyStatus: this.safetyStatus || undefined })
        if (seq !== this.listSeq || key !== this.listContext) return
        this.rows = data?.items || []; this.total = data?.total ?? 0
      } catch (error) { if (seq === this.listSeq && key === this.listContext) this.error = error?.message || '材料列表加载失败' }
      finally { if (seq === this.listSeq && key === this.listContext) this.loading = false }
    },
    reload() { this.navigate({ keyword: this.keyword, safetyStatus: this.safetyStatus, page: '1', id: undefined, file: undefined }); this.page = 1; this.load() },
    changePage(page) { this.navigate({ page: String(page) }) },
    openStudent(row) { this.navigate({ id: String(row.internshipId), file: undefined }) },
    closeStudent() { this.navigate({ id: undefined, file: undefined }) },
    refreshCurrent() { return this.selectedId ? this.refreshDetail() : this.load() },
    async refreshDetail(afterSync = false) {
      if (!this.selectedId || (this.syncing && !afterSync)) return false
      const seq = ++this.detailSeq, key = this.detailContext
      this.detailLoading = false; this.selected = null; this.activePreviewFileId = ''; this.detailError = ''
      if (!this.batchStore.selectedBatchId || !this.canView) { this.detailError = '请先选择有权查看的实习批次'; return false }
      this.detailLoading = true
      try {
        const data = await internshipMaterialCenterApi.detail(this.selectedId)
        if (seq !== this.detailSeq || key !== this.detailContext) return false
        if (String(data.internshipId) !== this.selectedId || String(data.batchId) !== String(this.batchStore.selectedBatchId)) { this.detailError = '该材料对象不属于当前批次，请返回学生列表重新定位'; return false }
        this.selected = data; this.restorePreview(); this.focusDetail(); return true
      } catch (error) { if (seq === this.detailSeq && key === this.detailContext) this.detailError = error?.message || '学生材料详情加载失败'; return false }
      finally { if (seq === this.detailSeq && key === this.detailContext) this.detailLoading = false }
    },
    focusDetail() { this.$nextTick?.(() => { const heading = this.$el?.querySelector(this.activePreviewFile ? '#material-reader-title' : '#material-student-title'); heading?.focus({ preventScroll: true }); heading?.scrollIntoView({ block: this.activePreviewFile ? 'start' : 'nearest' }) }) },
    async syncCurrent() {
      if (!this.selected || this.detailLoading || this.syncing || !this.canSync) return
      const id = this.selectedId, key = this.detailContext
      this.syncing = true; this.operationError = ''; this.syncReceipt = ''
      try {
        const result = await internshipMaterialCenterApi.sync(id)
        if (key !== this.detailContext) return
        const count = result?.items?.length || 0, unsafe = result?.unsafe?.length || 0
        this.syncReceipt = count ? `已同步 ${count} 份材料${unsafe ? `，其中 ${unsafe} 份仍待安全处理` : '，请以重新读取的材料状态为准'}。` : '同步已完成，现有业务记录中暂无可登记材料。'
        await Promise.all([this.load(), this.refreshDetail(true)])
      } catch (error) { if (key === this.detailContext) this.operationError = error?.message || '材料同步未确认，请刷新核对当前状态' }
      finally { if (key === this.detailContext) this.syncing = false }
    },
    restorePreview() {
      const item = this.previewFiles.find(file => String(file.fileId) === this.$route.query.file)
      this.activePreviewFileId = item ? String(item.fileId) : ''
      this.operationError = ''
      if (this.selected) this.focusDetail()
    },
    previewFile(candidate) {
      const item = this.previewFiles.find(file => String(file.fileId) === String(candidate?.fileId))
      if (!item || this.syncing || !this.canView) { toast.warning('当前材料尚未通过安全门禁，不能预览'); return }
      this.activePreviewFileId = String(item.fileId)
      this.navigate({ file: this.activePreviewFileId })
    },
    closePreview() { this.navigate({ file: undefined }) },
    downloadPreview(descriptor) {
      const item = this.selected?.items?.find(file => String(file.fileId) === String(descriptor?.fileId))
      if (item) return this.downloadFile(item)
    },
    async downloadFile(candidate) {
      const item = this.selected?.items?.find(file => String(file.fileId) === String(candidate?.fileId))
      if (!item?.canDownload || !item.readyForBusiness || this.downloadingId || this.syncing || !this.canView) return
      const key = this.detailContext; this.downloadingId = String(item.fileId); this.operationError = ''
      try { await internshipMaterialCenterApi.downloadMaterial(item) }
      catch (error) { if (key === this.detailContext) this.operationError = error?.message || '文件下载失败' }
      finally { if (key === this.detailContext) this.downloadingId = '' }
    },
    previewError(error) { this.operationError = error?.message || '站内预览失败，请刷新材料状态后重试' },
    goArchive() { if (!this.syncing && this.selected) this.$router.push({ path: '/admin/internship/archive', query: this.batchStore.withBatchQuery({ id: this.selectedId }) }) },
    shortHash(value) {
      const text = String(value || '')
      return text ? `${text.slice(0, 10)}…${text.slice(-8)}` : '-'
    },
    statusText(value) {
      return { READY: '安全可用', UNSAFE: '存在待处理', NOT_SYNCED: '尚未登记材料' }[value] || (value ? '待确认' : '未知')
    },
    statusTone(value) {
      return { READY: 'success', UNSAFE: 'danger', NOT_SYNCED: 'default' }[value] || 'default'
    },
    manifestTone(value) {
      return ['FROZEN', 'PACKAGED'].includes(value) ? 'success' : (value === 'REVOKED' ? 'danger' : 'warning')
    },
    manifestStatusLabel(value) { return ({ DRAFT: '草稿', FROZEN: '已冻结', PACKAGED: '已打包', REVOKED: '已撤销', PENDING: '生成中' })[value] || (value ? '状态待确认' : '—') },
    scanResultLabel(value) { return ({ CLEAN: '已通过', NOT_REQUIRED: '无需扫描', PENDING: '待扫描', INFECTED: '未通过', FAILED: '扫描失败' })[value] || (value ? '扫描结果待确认' : '—') }
  }
}
</script>

<style scoped>
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
.summary-grid article { display: grid; gap: 7px; padding: 16px; border: 1px solid #e2e8f2; border-radius: 14px; background: #fff; }
.summary-grid span { color: #758197; font-size: 13px; }
.summary-grid strong { color: #1e2b45; font-size: 25px; }
.summary-grid .danger { color: #c73333; }
.filter-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.filter-bar select { min-height: 38px; padding: 0 12px; border: 1px solid #d8e1ed; border-radius: 9px; background: #fff; color: #34425a; }
.filter-hint { margin-left: auto; color: #758197; font-size: 13px; }
.workspace { display: grid; grid-template-columns: minmax(270px, 0.34fr) minmax(0, 1fr); gap: 16px; align-items: start; }
.student-panel, .detail-panel { min-height: 360px; border: 1px solid #dfe7f1; border-radius: 14px; background: #fff; overflow: hidden; }
.student-row { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 15px 16px; border: 0; border-bottom: 1px solid #edf1f6; background: #fff; text-align: left; cursor: pointer; }
.student-row:hover, .student-row.active { background: #f3f8ff; }
.student-row > div:first-child { min-width: 0; display: grid; gap: 5px; }
.student-row strong { color: #25324a; }
.student-row span, .student-row small { overflow: hidden; color: #758197; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.row-status { display: grid; justify-items: end; gap: 5px; flex: none; }
.pager { display: flex; justify-content: center; align-items: center; gap: 12px; padding: 12px; }
.pager button, .state button { border: 0; background: transparent; color: #1769e0; cursor: pointer; }
.pager button:disabled { color: #aab4c3; cursor: not-allowed; }
.detail-panel { padding: 16px; background: #f8fafc; }
.detail-head { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin-bottom: 14px; padding: 16px; border: 1px solid #dfe7f1; border-radius: 12px; background: #fff; }
.detail-head > div { display: grid; gap: 6px; }
.detail-head span { color: #758197; font-size: 13px; }
.section-card { margin-top: 14px; padding: 15px; border: 1px solid #dfe7f1; border-radius: 12px; background: #fff; }
.reader-card { padding: 12px; }
.reader-card :deep(.dv-fullscreen:not(.is-fullscreen) .document-viewer) { height: min(74vh, 800px); min-height: 400px; }
.reader-card :deep(.document-viewer__body), .reader-card :deep(.pdf-viewer) { min-height: 0; }
.reader-card :deep(.dv-toolbar), .reader-card :deep(.dv-toolbar__group) { flex-wrap: wrap; }
.reader-card :deep(.pdf-page) { scroll-margin-top: 16px; }
.section-title { display: flex; justify-content: space-between; align-items: center; gap: 14px; margin-bottom: 12px; }
.section-title > div { display: grid; gap: 4px; }
.section-title span { color: #758197; font-size: 12px; }
.table-scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 760px; }
th, td { padding: 11px 10px; border-bottom: 1px solid #edf1f6; text-align: left; font-size: 13px; }
th { color: #637086; background: #f8fafc; }
td { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #34425a; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
.hash { max-width: 150px; }
.manifest-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 0; }
.manifest-meta div { min-width: 0; padding: 10px; border-radius: 9px; background: #f7f9fc; }
.manifest-meta dt { color: #758197; font-size: 12px; }
.manifest-meta dd { margin: 5px 0 0; overflow-wrap: anywhere; color: #27354d; }
.manifest-list { display: grid; gap: 7px; margin-top: 12px; }
.manifest-list div { display: grid; grid-template-columns: minmax(0, 1fr) 90px 190px; gap: 12px; padding: 9px 10px; border: 1px solid #e7edf5; border-radius: 8px; }
.manifest-list small { color: #758197; }
.technical-evidence { margin-top: 14px; padding: 12px 14px; border: 1px dashed #cbd6e5; border-radius: 12px; background: #fff; color: #637086; }
.technical-evidence > summary { cursor: pointer; font-weight: 700; }
.technical-evidence > .section-card { margin-top: 12px; }
.state { padding: 40px 20px; text-align: center; color: #758197; }
.state.compact { padding: 22px; }
.error-state { border: 1px solid #f1c7c7; border-radius: 12px; background: #fff7f7; color: #b42b2b; }
.empty-cell { padding: 25px; text-align: center; color: #8490a2; }
@media (max-width: 1100px) { .summary-grid { grid-template-columns: repeat(2, 1fr); } .workspace { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .summary-grid { grid-template-columns: 1fr; } .filter-bar { align-items: stretch; flex-direction: column; } .filter-hint { margin-left: 0; } .manifest-meta { grid-template-columns: 1fr; } }
.workspace { grid-template-columns: minmax(0, 1fr); }
.filter-bar { flex-wrap: wrap; padding: 14px 16px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.filter-bar label { font-size: 13px; color: var(--text-secondary); }
.detail-panel { min-height: 0; padding: 18px; background: var(--bg-card); }
.detail-head { padding: 0 0 20px; border: 0; border-bottom: 1px solid var(--border-base); border-radius: 0; flex-wrap: wrap; }
h2 { margin: 0; font-size: 19px; color: var(--text-primary); }
h2 small { margin-left: 12px; font-size: 13px; font-weight: 400; color: var(--text-secondary); }
#material-student-title, #material-reader-title { scroll-margin-top: 16px; }
#material-student-title:focus, #material-reader-title:focus { outline: none; }
.material-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0; padding: 16px 0; border-bottom: 1px solid var(--border-base); }
.material-summary > div { padding: 0 16px; border-right: 1px solid var(--border-base); }
.material-summary > div:first-child { padding-left: 0; }
.material-summary > div:last-child { border: 0; }
.material-summary dt { color: var(--text-secondary); font-size: 12px; }
.material-summary dd { margin: 8px 0 0; font-size: 25px; font-weight: 600; }
.material-summary small { margin-left: 7px; font-size: 12px; font-weight: 400; color: var(--text-secondary); }
.danger { color: var(--danger-600, #b42318); }
.material-note { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; justify-content: space-between; font-size: 12px; color: var(--text-secondary); padding: 12px 0; }
.sync-receipt { padding: 12px 16px; margin-bottom: 12px; border: 1px solid var(--primary-200, #bfdbfe); border-radius: 8px; background: var(--primary-50, #eff6ff); font-size: 13px; }
.error-state { display: flex; align-items: center; justify-content: center; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.section-title { flex-wrap: wrap; }
.section-title strong { overflow-wrap: anywhere; }
.manifest-list div { grid-template-columns: minmax(0, 1fr); gap: 6px; overflow-wrap: anywhere; }
@media (max-width: 680px) { .detail-panel { padding: 14px; } .student-row { flex-wrap: wrap; } .student-row span { white-space: normal; line-height: 1.6; } .row-status { justify-items: start; } .material-summary > div { padding: 0 10px; } .reader-card { padding: 8px; } }
</style>
