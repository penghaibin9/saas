<template>
  <ModulePageShell
    title="归档导出"
    :subtitle="isCollegeScope ? '学校封存材料和下载记录由校教务统筹；本院事项请查看实时预检' : '从正式封存批次申请导出；文件、用途和下载回执全程留痕'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <AppInlineAlert v-if="isCollegeScope" type="info" :description="scopeNote" />
    <AppButton v-if="isCollegeScope" variant="primary" @click="goCollegePrecheck">查看本院实时预检</AppButton>
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="listError" :description="listError" @retry="load" />
    <EmptyState v-else-if="!rows.length && !current && !detailError" title="暂无已归档批次" :description="isCollegeScope ? '学校正式封存由校教务统筹，本院可继续核对实时预检' : '批次确认归档后可在此下载物料'" />
    <template v-else>
      <div class="aaex-context">
        <label for="archive-export-batch">已封存批次</label>
        <AppSelect id="archive-export-batch" :model-value="selectedBatchId" :options="rows" label-key="batchName" value-key="batchId" :disabled="exporting || !!pendingExport" @change="select({ batchId: $event })" />
        <template v-if="current">
          <StatusTag type="success" label="已归档" dot />
          <span>封存时间：{{ fmt(current.archivedAt) || '时间待核' }}</span>
        </template>
        <AppButton v-if="rows.length < pagination.total" size="small" variant="ghost" :loading="loadingMore" @click="loadMore">加载更多已归档批次</AppButton>
      </div>
      <ErrorState v-if="detailError" :description="detailError" @retry="retryDetail" />
      <LoadingState v-else-if="!current" />
      <template v-else>
        <details class="aaex-responsibility">
          <summary>查看归档责任与后续办理</summary>
          <p>当前责任：{{ archiveOwner }}；下一责任岗位：{{ nextOwner }}</p>
        </details>
        <template v-if="!isCollegeScope">
          <div class="aaex-workspace">
            <section class="aaex-materials" aria-labelledby="archive-materials-title">
              <header><h2 id="archive-materials-title">归档材料</h2><span>{{ items.length }} 类资料 · {{ downloadableItems.length }} 类可导出</span></header>
              <EmptyState v-if="!downloadableItems.length" title="本批次暂无可导出资料" description="没有正式记录的资料不提供导出" />
              <DataTable v-else :columns="itemColumns" :rows="downloadableItems" row-key="domain">
                <template #cell-domain="{ row }">{{ row.domainLabel }}</template>
                <template #cell-action="{ row }">
                  <AppButton size="small" variant="ghost" :disabled="exporting || !!pendingExport" @click="openExport(row.domain)">单类导出</AppButton>
                </template>
              </DataTable>
              <p class="aaex-note">只列出有正式记录的资料，导出范围受当前账号权限限制。</p>
            </section>
            <section class="aaex-request-card" aria-labelledby="archive-request-title">
              <header><h2 id="archive-request-title">整批导出</h2></header>
              <div class="aaex-form">
                <AppFormItem label="导出范围"><AppTextInput model-value="当前批次全部可导出资料" disabled /></AppFormItem>
                <AppFormItem label="导出用途" required>
                  <AppTextarea v-model="exportPurpose" :rows="2" :maxlength="500" show-count placeholder="至少5个字，说明正式用途" :disabled="exporting || !!pendingExport" />
                </AppFormItem>
                <AppInlineAlert v-if="exportError && !exportVisible" type="danger" :description="exportError" />
                <AppButton variant="primary" :disabled="!!pendingExport || !downloadableItems.length" :loading="exporting && pendingCategory === null" @click="quickExport">生成整批文件</AppButton>
                <p class="aaex-note">文件带水印，生成及下载均留痕。</p>
                <AppInlineAlert v-if="exportNotice" :type="pendingExport ? 'warning' : 'success'" :description="exportNotice" />
              </div>
            </section>
          </div>
          <section class="aaex-log" aria-labelledby="archive-log-title">
            <header><h2 id="archive-log-title">下载记录</h2><AppButton size="small" variant="ghost" :loading="logLoading" @click="loadLog()">刷新记录</AppButton></header>
            <LoadingState v-if="logLoading" />
            <ErrorState v-else-if="logError" :description="logError" @retry="loadLog()" />
            <EmptyState v-else-if="!downloadLog.length" title="暂无下载记录" description="尚未有人下载过本批次物料" />
            <DataTable v-else :columns="logColumns" :rows="downloadLog" row-key="downloadAt">
              <template #cell-operator="{ row }">{{ logOperator(row) }}</template>
              <template #cell-action="{ row }">{{ logAction(row) }}</template>
              <template #cell-detail="{ row }">{{ logPurpose(row) }}</template>
              <template #cell-downloadAt="{ row }">{{ fmt(row.downloadAt) }}</template>
            </DataTable>
          </section>
        </template>
      </template>
    </template>

    <AppDrawer :visible="exportVisible" title="下载归档物料" mode="modal" size="small" @close="closeExport">
      <div class="aaex-form">
        <AppFormItem label="下载用途" required>
          <AppTextInput v-model="exportPurpose" placeholder="如 上级检查留档核对（≥5字，写审计）" :disabled="exporting" />
        </AppFormItem>
        <AppInlineAlert type="warning" description="导出文件含学生姓名/学号等敏感字段，首行水印 + 审计留痕，请勿随意外发。" />
        <AppInlineAlert v-if="exportError" type="danger" :description="exportError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="exporting" @click="closeExport">取消</AppButton>
        <AppButton variant="primary" :loading="exporting" @click="doExport">确认下载</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** AA-263 教务归档 · 归档导出（/admin/academic-affairs/archive/export）：
 * 已归档批次的水印 xlsx 单域下载 + zip 打包全量下载 + 下载记录查询。批次未 ARCHIVED 不出现在列表。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, StatusTag } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppTextarea, AppFormItem, AppInlineAlert, AppSelect } from '@/components/common'
import { academicAffairsArchiveApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { safeBusinessMessage } from '@/utils/presentationSafety'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import { academicFlowOwner, academicFlowNextOwner, academicFlowText } from '../config/academicFlowRegistry.js'

function _download(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export default {
  name: 'ArchiveExportView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, StatusTag, AppButton, AppDrawer, AppTextInput, AppTextarea, AppFormItem, AppInlineAlert, AppSelect },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      alive: true, scope: 0, listSeq: 0, detailSeq: 0, logSeq: 0,
      loading: true, listError: '', detailError: '', selectedBatchId: '', rows: [], current: null, items: [],
      pagination: { page: 1, pageSize: 20, total: 0 }, loadingMore: false,
      itemColumns: [{ key: 'domain', title: '资料名称' }, { key: 'recordCount', title: '正式记录数' }, { key: 'action', title: '操作' }],
      logLoading: false, logError: '', downloadLog: [],
      logColumns: [{ key: 'operator', title: '下载人' }, { key: 'action', title: '导出内容' }, { key: 'detail', title: '用途' }, { key: 'downloadAt', title: '下载时间' }],
      exportVisible: false, exportPurpose: '', exportError: '', exportNotice: '', exporting: false, pendingCategory: null, pendingExport: null
    }
  },
  computed: {
    identity() {
      const user = currentUserFromToken() || {}
      return JSON.stringify([user.tenantId, user.userId, user.activeContextId, user.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope])
    },
    isCollegeScope() { return this.current?.scopeType === 'COLLEGE' || (this.ctx.dataScope?.scopeType || this.ctx.dataScope?.scope) === 'COLLEGE' || this.rows.some(row => row.scopeType === 'COLLEGE') },
    scopeNote() { return academicFlowText(this.current?.scopeNote, '学校封存材料和下载记录由校教务统筹；请查看本院实时预检。') },
    archiveOwner() {
      if (!this.current?.responsibility) {
        if (this.current?.status === 'ARCHIVED') return '学校已完成封存'
        if (this.current?.status === 'CANCELLED') return '批次已取消'
      }
      return academicFlowOwner(this.current?.responsibility)
    },
    nextOwner() {
      if (!this.current?.nextStep) {
        if (this.current?.status === 'ARCHIVED') return '后续查阅或纠错由校教务统筹'
        if (this.current?.status === 'CANCELLED') return '无需继续办理此批次'
      }
      return academicFlowNextOwner(this.current?.nextStep)
    },
    downloadableItems() { return this.items.filter((item) => Number(item.recordCount) > 0) }
  },
  watch: { identity() { this.clearPrivate(); this.load() } },
  created() { this.load() },
  beforeUnmount() { this.alive = false; this.clearPrivate() },
  methods: {
    logOperator(row) {
      const name = row.operatorName || row.operator
      return name && !/^(?:db-\d+|\d+)$/.test(name) ? safeBusinessMessage(name, '操作人员信息待核实') : '操作人员信息待核实'
    },
    logAction(row) {
      return { ITEM_EXPORT_DOWNLOAD: '单类归档材料', BATCH_EXPORT_DOWNLOAD: '整批归档材料' }[row.action] || '归档材料下载'
    },
    logPurpose(row) {
      const detail = String(row.detail || '')
      const marker = detail.indexOf('用途=')
      return safeBusinessMessage(marker >= 0 ? detail.slice(marker + 3) : detail, '用途待核实')
    },
    capture(extra = '') { return { scope: this.scope, identity: this.identity, extra: String(extra || '') } },
    tokenValid(c) { return this.alive && c.scope === this.scope && c.identity === this.identity },
    denied(err) { return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code, err?.bizCode].join(' ')) },
    clearPrivate() {
      this.scope += 1; this.listSeq += 1; this.detailSeq += 1; this.logSeq += 1
      this.loading = false; this.loadingMore = false; this.listError = ''; this.detailError = ''; this.selectedBatchId = ''; this.rows = []; this.current = null; this.items = []
      this.pagination = { page: 1, pageSize: 20, total: 0 }; this.logLoading = false; this.logError = ''; this.downloadLog = []
      this.exportVisible = false; this.exportPurpose = ''; this.exportError = ''; this.exportNotice = ''; this.exporting = false; this.pendingCategory = null; this.pendingExport = null
    },
    fail(err, fallback) { if (this.denied(err)) this.clearPrivate(); return gradeError(err, fallback) },
    fmt(s) { return s ? s.replace('T', ' ').slice(0, 16) : '' },
    goCollegePrecheck() { return this.$router.push({ name: 'aa-archive-precheck', query: this.current?.termId ? { termId: String(this.current.termId) } : {} }) },
    async load(page = 1, append = false) {
      const c = this.capture(), seq = ++this.listSeq
      if (append) this.loadingMore = true; else this.loading = true
      this.listError = ''
      try {
        const res = await api.listBatches({ status: 'ARCHIVED', page, pageSize: this.pagination.pageSize })
        if (!this.tokenValid(c) || seq !== this.listSeq) return
        if (res.code !== 0) throw res
        if (!Array.isArray(res.data?.list) || res.data.list.some((row) => row.status !== 'ARCHIVED' || !String(row.batchId || ''))) throw { code: 503 }
        this.rows = append ? this.rows.concat(res.data.list.filter((row) => !this.rows.some((old) => String(old.batchId) === String(row.batchId)))) : res.data.list
        this.pagination.page = page
        this.pagination.total = Number.isFinite(res.data.total) ? res.data.total : this.rows.length
        if (!append && !this.current && this.rows.length) await this.select(this.rows[0])
      } catch (err) {
        if (this.tokenValid(c) && seq === this.listSeq) this.listError = this.fail(err, '已归档批次加载失败')
      } finally {
        if (this.tokenValid(c) && seq === this.listSeq) { this.loading = false; this.loadingMore = false }
      }
    },
    loadMore() { if (!this.loadingMore && this.rows.length < this.pagination.total) this.load(this.pagination.page + 1, true) },
    retryDetail() { if (this.selectedBatchId) return this.select({ batchId: this.selectedBatchId }) },
    async select(b) {
      if (this.exporting || this.pendingExport) return
      const batchId = String(b?.batchId || ''), c = this.capture(batchId), seq = ++this.detailSeq
      if (!batchId) return
      this.selectedBatchId = batchId
      this.exportError = ''; this.exportNotice = ''
      this.current = null; this.items = []; this.downloadLog = []; this.detailError = ''; this.logError = ''; this.logSeq++; this.logLoading = false
      try {
        const res = await api.getBatch(batchId)
        if (!this.tokenValid(c) || seq !== this.detailSeq) return
        if (res.code !== 0) throw res
        if (String(res.data?.batchId) !== batchId || res.data?.status !== 'ARCHIVED' || !Array.isArray(res.data?.items)) throw { code: 503 }
        this.current = res.data; this.items = res.data.items; this.downloadLog = []
        if (!this.isCollegeScope) await this.loadLog(batchId)
      } catch (err) {
        if (this.tokenValid(c) && seq === this.detailSeq) this.detailError = this.fail(err, '归档批次加载失败')
      }
    },
    async loadLog(requestedId = this.current?.batchId) {
      if (this.isCollegeScope) return false
      const batchId = String(requestedId || ''), c = this.capture(batchId), seq = ++this.logSeq
      if (!batchId || String(this.current?.batchId) !== batchId) return false
      this.logLoading = true
      this.logError = ''; this.downloadLog = []
      try {
        const res = await api.downloadLog(batchId)
        if (!this.tokenValid(c) || seq !== this.logSeq || String(this.current?.batchId) !== batchId) return false
        if (res.code !== 0 || !Array.isArray(res.data)) throw res
        this.downloadLog = res.data
        return true
      } catch (err) {
        if (this.tokenValid(c) && seq === this.logSeq) {
          this.logError = this.fail(err, '下载记录读取失败')
          if (this.denied(err)) this.listError = this.logError
        }
        return false
      } finally {
        if (this.tokenValid(c) && seq === this.logSeq) this.logLoading = false
      }
    },
    openExport(category) {
      if (this.isCollegeScope || !this.current || this.current.status !== 'ARCHIVED' || this.exporting || this.pendingExport) return
      this.pendingCategory = category
      this.exportError = ''; this.exportVisible = true
    },
    quickExport() {
      if (this.isCollegeScope || !this.current || this.exporting || this.pendingExport) return
      this.pendingCategory = null
      this.exportError = ''
      this.exportVisible = false
      return this.doExport()
    },
    closeExport() { if (!this.exporting) this.exportVisible = false },
    async doExport() {
      if (this.isCollegeScope) return
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) { this.exportError = '用途至少5字'; return }
      if (!this.current || this.current.status !== 'ARCHIVED' || this.exporting || this.pendingExport) return
      const frozen = { batchId: String(this.current.batchId), batchName: String(this.current.batchName || '归档批次'), category: this.pendingCategory ? String(this.pendingCategory) : '', purpose: this.exportPurpose.trim() }
      const c = this.capture(frozen.batchId)
      this.exporting = true; this.pendingExport = frozen; this.exportNotice = '下载结果待核实，请勿重复操作。'
      try {
        const before = await api.getBatch(frozen.batchId)
        if (!this.tokenValid(c)) return
        if (before?.code !== 0 || String(before.data?.batchId) !== frozen.batchId || before.data?.status !== 'ARCHIVED' || !Array.isArray(before.data?.items)) throw before
        if (before.data.scopeType === 'COLLEGE') { this.current = before.data; this.items = []; this.downloadLog = []; this.pendingExport = null; this.exportNotice = ''; this.exportVisible = false; return }
        if (frozen.category && !before.data.items.some((item) => item.domain === frozen.category && Number(item.recordCount) > 0)) throw { code: 409 }
        let res
        try { res = frozen.category ? await api.exportItem(frozen.batchId, frozen.category, frozen.purpose) : await api.exportAll(frozen.batchId, frozen.purpose) } catch (err) { res = err }
        if (!this.tokenValid(c)) return
        if (res?.code !== 0) {
          if (/403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code, res?.bizCode].join(' '))) { this.pendingExport = null; this.exportNotice = ''; throw res }
          this.exportError = '下载结果待核实，请勿重复下载。'; return
        }
        if (!(res.data instanceof Blob)) { this.exportError = '下载结果待核实，请勿重复下载。'; return }
        const action = frozen.category ? 'ITEM_EXPORT_DOWNLOAD' : 'BATCH_EXPORT_DOWNLOAD'
        const filename = frozen.category ? `${frozen.category}_${frozen.batchName}.xlsx` : `${frozen.batchName}_归档物料.zip`
        _download(res.data, filename)
        const logRead = await this.loadLog(frozen.batchId)
        if (!this.tokenValid(c)) return
        const verified = logRead && this.downloadLog.some((row) => row.action === action && String(row.detail || '').includes(frozen.purpose))
        if (verified) {
          this.pendingExport = null; this.exportNotice = '已生成下载文件，并核对正式下载记录。'; this.exportVisible = false; toast.success(this.exportNotice)
        } else this.exportError = '文件已生成，但正式下载记录待核实；请勿重复下载。'
      } catch (err) {
        if (this.tokenValid(c)) this.exportError = this.fail(err, '下载前核对未完成，请重试。')
      } finally {
        if (this.tokenValid(c)) this.exporting = false
      }
    }
  }
}
</script>

<style scoped>
.aaex-context { display:flex;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:10px; }
.aaex-context .app-select { width:390px;max-width:100%; }
.aaex-context > span,.aaex-note,.aaex-responsibility { color:var(--text-secondary,#64748b);font-size:13px;line-height:1.6; }
.aaex-responsibility { margin-bottom:16px; }
.aaex-responsibility summary { cursor:pointer; }
.aaex-responsibility p { margin:8px 0; }
.aaex-workspace { display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:20px;align-items:start; }
.aaex-materials,.aaex-request-card,.aaex-log { min-width:0;background:var(--bg-card,#fff);border:1px solid var(--border-color,#dbe3ee);border-radius:8px;padding:16px; }
.aaex-workspace header,.aaex-log header { display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:14px; }
.aaex-workspace header span { color:var(--text-secondary,#64748b);font-size:13px; }
.aaex-workspace h2,.aaex-log h2 { margin:0;font-size:17px; }
.aaex-form { display:flex;flex-direction:column;gap:14px; }
.aaex-note { margin:10px 0 0; }
.aaex-log { margin-top:20px; }
.aaex-materials :deep(.dt__scroll) { max-height:370px;overflow:auto; }
.aaex-materials :deep(.dt__th) { position:sticky;top:0;z-index:1;background:var(--fill-light,#f4f7fc); }
.aaex-log :deep(.dt__td) { overflow-wrap:anywhere; }
@media(max-width:1100px) { .aaex-workspace { grid-template-columns:minmax(0,1fr); }.aaex-materials :deep(.dt__scroll) { max-height:none; } }
@media(max-width:600px) { .aaex-context { align-items:flex-start;flex-direction:column; }.aaex-context .app-select { width:100%; }.aaex-materials,.aaex-request-card,.aaex-log { padding:12px; }.aaex-materials :deep(table),.aaex-log :deep(table) { min-width:500px; } }
</style>
