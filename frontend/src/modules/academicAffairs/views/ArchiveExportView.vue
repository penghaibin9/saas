<template>
  <ModulePageShell
    title="归档导出"
    subtitle="从正式封存批次申请导出；文件、用途和下载回执全程留痕"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ol class="aaex-stage-rail" aria-label="归档导出所处阶段">
      <li class="is-done"><b>✓</b><span><strong>建立批次</strong><small>归档对象已建立</small></span></li>
      <li class="is-done"><b>✓</b><span><strong>十三域预检</strong><small>正式检查已完成</small></span></li>
      <li class="is-done"><b>✓</b><span><strong>补齐缺失</strong><small>阻断已处理</small></span></li>
      <li class="is-current"><b>4</b><span><strong>正式封存</strong><small>从封存事实申请导出</small></span></li>
      <li><b>5</b><span><strong>双人纠错</strong><small>不通过导出改写事实</small></span></li>
    </ol>

    <section v-if="current" class="aaex-object-card">
      <div>
        <small>当前业务对象 · 学期归档批次 #{{ current.batchId }}</small>
        <h2>{{ current.batchName }}</h2>
        <p>来源：已封存学期归档事实 · 为什么轮到我：当前岗位拥有归档导出权限</p>
      </div>
      <dl>
        <div><dt>当前状态</dt><dd><StatusTag type="success" label="已归档" dot /></dd></div>
        <div><dt>当前责任</dt><dd>归档管理岗</dd></div>
        <div><dt>当前阻断</dt><dd>无；下载用途必须留痕</dd></div>
        <div><dt>下一责任岗位</dt><dd>授权查阅人</dd></div>
      </dl>
    </section>

    <section v-if="current" class="aaex-request-grid">
      <div class="aaex-request-card">
        <header><div><h3>导出范围与用途</h3><p>范围由当前归档批次和服务端授权共同确定</p></div></header>
        <div class="aaex-request-fields">
          <AppFormItem label="学期归档批次"><AppTextInput :model-value="`${current.batchName}（#${current.batchId}）`" disabled /></AppFormItem>
          <AppFormItem label="数据范围"><AppTextInput model-value="当前批次全部十三域（按正式记录数导出）" disabled /></AppFormItem>
          <AppFormItem label="导出用途" required>
            <AppTextarea v-model="exportPurpose" :rows="4" :maxlength="500" show-count placeholder="至少5个字，说明正式用途" :disabled="exporting" />
          </AppFormItem>
          <AppInlineAlert v-if="exportError" type="danger" :description="exportError" />
        </div>
        <footer><span>完整导出由服务端生成水印文件并写下载审计。</span><AppButton variant="primary" :disabled="!!pendingExport" :loading="exporting && pendingCategory === null" @click="quickExport">申请归档导出</AppButton></footer>
      </div>
      <aside class="aaex-scope-card">
        <h3>三种范围不要混淆</h3>
        <ul>
          <li><b>本页记录</b><span>当前表格可见的数据域</span></li>
          <li><b>已选记录</b><span>使用单域“下载”动作</span></li>
          <li><b>当前筛选全部</b><span>由服务端按当前批次与权限完成</span></li>
        </ul>
      </aside>
    </section>

    <div class="aaex-layout">
      <div class="aaex-list">
        <div class="aaex-list-title">已归档批次</div>
        <LoadingState v-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无已归档批次" description="批次确认归档后可在此下载物料" />
        <ul v-else class="aaex-items">
          <li v-for="b in rows" :key="b.batchId" :class="['aaex-item', { 'is-active': current && current.batchId === b.batchId }]" @click="select(b)">
            <span>{{ b.batchName }}</span>
            <span class="aaex-item-date">{{ fmt(b.archivedAt) }}</span>
          </li>
        </ul>
        <AppButton v-if="rows.length < pagination.total" size="small" variant="ghost" :loading="loadingMore" @click="loadMore">加载更多已归档批次</AppButton>
      </div>

      <div class="aaex-detail">
        <EmptyState v-if="!current" title="选择批次" description="从左侧选择已归档批次查看可下载物料" />
        <template v-else>
          <div class="aaex-head">
            <div class="aaex-title">{{ current.batchName }}</div>
            <span class="aaex-server-note">正式记录 {{ items.reduce((sum, item) => sum + Number(item.recordCount || 0), 0) }} 条 · 封存于 {{ fmt(current.archivedAt) || '时间待核' }}</span>
          </div>

          <div class="aaex-section-title">物料清单（{{ items.length }} 域，仅列出有数据域）</div>
          <DataTable :columns="itemColumns" :rows="downloadableItems" row-key="domain">
            <template #cell-domain="{ row }">{{ row.domainLabel }}</template>
            <template #cell-action="{ row }">
              <AppButton size="small" variant="ghost" :disabled="!!pendingExport" @click="openExport(row.domain)">下载</AppButton>
            </template>
          </DataTable>

          <div class="aaex-section-title">下载记录</div>
          <LoadingState v-if="logLoading" />
          <EmptyState v-else-if="!downloadLog.length" title="暂无下载记录" description="尚未有人下载过本批次物料" />
          <DataTable v-else :columns="logColumns" :rows="downloadLog" row-key="downloadAt">
            <template #cell-downloadAt="{ row }">{{ fmt(row.downloadAt) }}</template>
          </DataTable>
        </template>
      </div>
    </div>

    <AppInlineAlert v-if="exportNotice" :type="pendingExport ? 'warning' : 'success'" :description="exportNotice" />

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
import { ModulePageShell, DataTable, LoadingState, EmptyState, StatusTag } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppTextarea, AppFormItem, AppInlineAlert } from '@/components/common'
import { academicAffairsArchiveApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'

function _download(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

export default {
  name: 'ArchiveExportView',
  components: { ModulePageShell, DataTable, LoadingState, EmptyState, StatusTag, AppButton, AppDrawer, AppTextInput, AppTextarea, AppFormItem, AppInlineAlert },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      alive: true, scope: 0, listSeq: 0, detailSeq: 0, logSeq: 0,
      loading: true, rows: [], current: null, items: [],
      pagination: { page: 1, pageSize: 20, total: 0 }, loadingMore: false,
      itemColumns: [{ key: 'domain', title: '数据域' }, { key: 'domainLabel', title: '名称' }, { key: 'recordCount', title: '记录数' }, { key: 'action', title: '操作' }],
      logLoading: false, downloadLog: [],
      logColumns: [{ key: 'operator', title: '下载人' }, { key: 'action', title: '类型' }, { key: 'detail', title: '说明' }, { key: 'downloadAt', title: '时间' }],
      exportVisible: false, exportPurpose: '', exportError: '', exportNotice: '', exporting: false, pendingCategory: null, pendingExport: null
    }
  },
  computed: {
    identity() {
      const user = currentUserFromToken() || {}
      return JSON.stringify([user.tenantId, user.userId, user.activeContextId, user.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope])
    },
    downloadableItems() { return this.items.filter((item) => Number(item.recordCount) > 0) }
  },
  watch: { identity() { this.clearPrivate(); this.load() } },
  created() { this.load() },
  beforeUnmount() { this.alive = false; this.clearPrivate() },
  methods: {
    capture(extra = '') { return { scope: this.scope, identity: this.identity, extra: String(extra || '') } },
    tokenValid(c) { return this.alive && c.scope === this.scope && c.identity === this.identity },
    denied(err) { return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code, err?.bizCode].join(' ')) },
    clearPrivate() {
      this.scope += 1; this.listSeq += 1; this.detailSeq += 1; this.logSeq += 1
      this.loading = false; this.loadingMore = false; this.rows = []; this.current = null; this.items = []
      this.pagination = { page: 1, pageSize: 20, total: 0 }; this.logLoading = false; this.downloadLog = []
      this.exportVisible = false; this.exportPurpose = ''; this.exportError = ''; this.exportNotice = ''; this.exporting = false; this.pendingCategory = null; this.pendingExport = null
    },
    fail(err, fallback) { if (this.denied(err)) this.clearPrivate(); return gradeError(err, fallback) },
    fmt(s) { return s ? s.replace('T', ' ').slice(0, 16) : '' },
    async load(page = 1, append = false) {
      const c = this.capture(), seq = ++this.listSeq
      if (append) this.loadingMore = true; else this.loading = true
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
        if (this.tokenValid(c) && seq === this.listSeq) toast.error(this.fail(err, '已归档批次加载失败'))
      } finally {
        if (this.tokenValid(c) && seq === this.listSeq) { this.loading = false; this.loadingMore = false }
      }
    },
    loadMore() { if (!this.loadingMore && this.rows.length < this.pagination.total) this.load(this.pagination.page + 1, true) },
    async select(b) {
      if (this.exporting || this.pendingExport) return
      const batchId = String(b?.batchId || ''), c = this.capture(batchId), seq = ++this.detailSeq
      if (!batchId) return
      try {
        const res = await api.getBatch(batchId)
        if (!this.tokenValid(c) || seq !== this.detailSeq) return
        if (res.code !== 0) throw res
        if (String(res.data?.batchId) !== batchId || res.data?.status !== 'ARCHIVED' || !Array.isArray(res.data?.items)) throw { code: 503 }
        this.current = res.data; this.items = res.data.items; this.downloadLog = []
        await this.loadLog(batchId)
      } catch (err) {
        if (this.tokenValid(c) && seq === this.detailSeq) toast.error(this.fail(err, '归档批次加载失败'))
      }
    },
    async loadLog(requestedId = this.current?.batchId) {
      const batchId = String(requestedId || ''), c = this.capture(batchId), seq = ++this.logSeq
      if (!batchId || String(this.current?.batchId) !== batchId) return false
      this.logLoading = true
      try {
        const res = await api.downloadLog(batchId)
        if (!this.tokenValid(c) || seq !== this.logSeq || String(this.current?.batchId) !== batchId) return false
        if (res.code !== 0 || !Array.isArray(res.data)) throw res
        this.downloadLog = res.data
        return true
      } catch (err) {
        if (this.tokenValid(c) && seq === this.logSeq) toast.error(this.fail(err, '下载记录读取失败'))
        return false
      } finally {
        if (this.tokenValid(c) && seq === this.logSeq) this.logLoading = false
      }
    },
    openExport(category) {
      if (!this.current || this.current.status !== 'ARCHIVED' || this.exporting || this.pendingExport) return
      this.pendingCategory = category
      this.exportPurpose = ''; this.exportError = ''; this.exportVisible = true
    },
    quickExport() {
      if (!this.current || this.exporting || this.pendingExport) return
      this.pendingCategory = null
      this.exportError = ''
      this.exportVisible = false
      return this.doExport()
    },
    closeExport() { if (!this.exporting) this.exportVisible = false },
    async doExport() {
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) { this.exportError = '用途至少5字'; return }
      if (!this.current || this.current.status !== 'ARCHIVED' || this.exporting || this.pendingExport) return
      const frozen = { batchId: String(this.current.batchId), batchName: String(this.current.batchName || '归档批次'), category: this.pendingCategory ? String(this.pendingCategory) : '', purpose: this.exportPurpose.trim() }
      const c = this.capture(frozen.batchId)
      this.exporting = true; this.pendingExport = frozen; this.exportNotice = '下载结果待核实，请勿重复操作。'
      try {
        const before = await api.getBatch(frozen.batchId)
        if (!this.tokenValid(c)) return
        if (before?.code !== 0 || String(before.data?.batchId) !== frozen.batchId || before.data?.status !== 'ARCHIVED' || !Array.isArray(before.data?.items)) throw before
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
.aaex-stage-rail { display:grid;grid-template-columns:repeat(5,minmax(0,1fr));list-style:none;margin:0 0 16px;padding:14px 16px;border:1px solid var(--border-color,#dbe3ee);border-radius:10px;background:var(--bg-card,#fff); }
.aaex-stage-rail li { display:flex;gap:9px;align-items:flex-start;position:relative;color:var(--text-tertiary,#94a3b8); }
.aaex-stage-rail li:not(:last-child)::after { content:'';position:absolute;left:31px;right:8px;top:12px;height:1px;background:var(--border-color,#dbe3ee); }
.aaex-stage-rail b { position:relative;z-index:1;display:grid;place-items:center;width:24px;height:24px;border:1px solid var(--border-color,#dbe3ee);border-radius:50%;background:var(--bg-card,#fff);font-size:12px; }
.aaex-stage-rail span { display:grid;gap:2px;min-width:0; }
.aaex-stage-rail strong { color:var(--text-primary,#183153);font-size:13px; }
.aaex-stage-rail small { font-size:11px;line-height:1.35; }
.aaex-stage-rail .is-done b { color:#26875f;border-color:#b9e4d1;background:#effaf5; }
.aaex-stage-rail .is-current b { color:#fff;border-color:var(--primary-color,#2563eb);background:var(--primary-color,#2563eb); }
.aaex-object-card { display:grid;grid-template-columns:minmax(0,1fr) auto;gap:24px;margin-bottom:16px;padding:16px;border:1px solid var(--border-color,#dbe3ee);border-left:3px solid var(--primary-color,#2563eb);border-radius:10px;background:var(--bg-card,#fff); }
.aaex-object-card small,.aaex-object-card p,.aaex-request-card p,.aaex-server-note { color:var(--text-secondary,#64748b);font-size:12px; }
.aaex-object-card h2 { margin:5px 0;font-size:18px; }
.aaex-object-card p { margin:0; }
.aaex-object-card dl { display:grid;grid-template-columns:repeat(2,minmax(130px,1fr));gap:10px 18px;margin:0; }
.aaex-object-card dl div { display:grid;gap:3px; }
.aaex-object-card dt { color:var(--text-tertiary,#94a3b8);font-size:11px; }
.aaex-object-card dd { margin:0;font-size:13px; }
.aaex-request-grid { display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:16px;margin-bottom:16px; }
.aaex-request-card,.aaex-scope-card { border:1px solid var(--border-color,#dbe3ee);border-radius:10px;background:var(--bg-card,#fff); }
.aaex-request-card header,.aaex-request-card footer,.aaex-scope-card h3 { padding:14px 16px;border-bottom:1px solid var(--border-color,#dbe3ee); }
.aaex-request-card h3,.aaex-request-card p,.aaex-scope-card h3 { margin:0; }
.aaex-request-card footer { display:flex;align-items:center;justify-content:space-between;gap:16px;border-top:1px solid var(--border-color,#dbe3ee);border-bottom:0;background:var(--primary-bg,#eff6ff); }
.aaex-request-card footer span { color:var(--text-secondary,#64748b);font-size:12px; }
.aaex-request-fields { display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:16px; }
.aaex-request-fields > :nth-child(3),.aaex-request-fields > :nth-child(4) { grid-column:1 / -1; }
.aaex-scope-card h3 { font-size:15px; }
.aaex-scope-card ul { list-style:none;margin:0;padding:4px 16px 12px; }
.aaex-scope-card li { display:grid;gap:3px;padding:12px 0;border-bottom:1px solid var(--border-color,#eef2f7); }
.aaex-scope-card li:last-child { border-bottom:0; }
.aaex-scope-card b { font-size:13px; }
.aaex-scope-card span { color:var(--text-secondary,#64748b);font-size:12px;line-height:1.5; }
.aaex-layout { display: grid; grid-template-columns: 280px 1fr; gap: 16px; }
.aaex-list-title { font-weight: 500; margin-bottom: 8px; }
.aaex-items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaex-item { display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aaex-item.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aaex-item-date { font-size: 12px; color: var(--text-tertiary, #94a3b8); }
.aaex-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.aaex-title { font-size: 16px; font-weight: 600; }
.aaex-server-note { text-align:right; }
.aaex-section-title { font-weight: 500; margin: 16px 0 8px; }
.aaex-form { display: flex; flex-direction: column; gap: 12px; }
@media (max-width: 1050px) { .aaex-stage-rail { grid-template-columns:1fr;gap:10px; }.aaex-stage-rail li::after { display:none; }.aaex-object-card,.aaex-request-grid,.aaex-layout { grid-template-columns:1fr; }.aaex-request-fields { grid-template-columns:1fr; }.aaex-request-fields > * { grid-column:auto !important; } }
</style>
