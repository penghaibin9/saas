<template>
  <ModulePageShell title="实习归档" subtitle="检查实习材料是否齐全，完成学生归档并查看批次统计结果 · 材料完整性检查 · 缺失提醒 · 按学生/批次/企业归档"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="$router.push('/admin/internship/stats')">实习统计</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

    <div class="tabs">
      <button v-for="t in tabs" :key="t.key" class="tabs__btn" :class="{ 'is-active': tab === t.key }"
        @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <!-- 按学生 -->
    <template v-if="tab === 'student'">
      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <label class="chk"><input v-model="onlyIncomplete" type="checkbox" @change="reload" />仅看未完整</label>
        <span class="bar__hint">数据范围内可见</span>
      </div>
      <div v-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
      <DataTable v-else :columns="studentColumns" :rows="rows" row-key="id" :loading="loading"
        :pagination="pagination" @page-change="onPageChange">
        <template #cell-completeness="{ row }">
          <span class="pct"><span class="pct__bar"><span class="pct__fill" :class="{ 'is-full': row.completeness >= 100 }" :style="{ width: row.completeness + '%' }"></span></span>{{ row.completeness }}%</span>
        </template>
        <template #cell-missing="{ row }">
          <span class="miss">{{ row.missing.length ? row.missing.join('、') : '—' }}</span>
        </template>
        <template #cell-archived="{ row }">
          <AppStatusTag :type="row.archived ? 'success' : 'default'">{{ row.archived ? '已归档' : '未归档' }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <div class="ops">
            <AppButton variant="ghost" size="sm" @click="openDetail(row)">详情</AppButton>
            <AppPermissionButton v-if="!row.archived" code="internship.archive.handle" variant="secondary" size="sm" @click="doArchive(row)">归档</AppPermissionButton>
            <AppPermissionButton v-else code="internship.archive.handle" variant="ghost" size="sm" :danger="true" @click="doRevoke(row)">撤销归档</AppPermissionButton>
          </div>
        </template>
      </DataTable>
    </template>

    <!-- 按批次 / 按企业 -->
    <template v-else>
      <DataTable :columns="aggColumns" :rows="aggRows" row-key="group" :loading="loading">
        <template #cell-avgCompleteness="{ row }">{{ row.avgCompleteness }}%</template>
        <template #cell-archiveRate="{ row }">{{ row.archiveRate }}%</template>
      </DataTable>
    </template>

    <!-- 详情 -->
    <div v-if="detailDlg.visible" class="modal" @click.self="detailDlg.visible = false">
      <div class="modal__card">
        <div class="modal__head">归档材料清单</div>
        <div class="modal__body">
          <div v-if="detailDlg.loading" class="state">加载中…</div>
          <template v-else-if="detailDlg.data">
            <AppDescriptionList :items="detailItems" :columns="2" />
            <div class="mats">
              <div v-for="m in detailDlg.data.materialLabels" :key="m.key" class="mat" :class="{ 'is-miss': !m.present }">
                <span class="mat__dot">{{ m.present ? '✓' : '✗' }}</span>{{ m.label }}
              </div>
            </div>
            <div class="sec-t">归档留痕</div>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无归档记录" />
            <div v-if="detailDlg.data.archived" class="pkg-bar">
              <AppPermissionButton v-if="!detailDlg.data.packageReady" code="internship.archive.handle"
                variant="secondary" size="sm" :loading="pkgBusy" @click="buildPackage">生成归档包</AppPermissionButton>
              <AppButton v-else variant="secondary" size="sm" :loading="pkgBusy" @click="downloadPackage">下载归档包 (zip)</AppButton>
            </div>
            <p v-else class="hint">归档包需在「已归档」后生成；含 manifest + 材料清单 + 已有扫描件。</p>
          </template>
        </div>
        <div class="modal__foot"><AppButton variant="secondary" @click="detailDlg.visible = false">关闭</AppButton></div>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="原因" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton,
  AppDescriptionList, AppAuditTrail, AppSearchBox } from '@/components/common'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { archiveApi } from '@/modules/internship/api/archive.api'
import { downloadAttachment } from '@/modules/internship/api/guidance-visit.api'
import { toast } from '@/utils/toast'

const STUDENT_COLUMNS = [
  { key: 'studentNo', title: '学号', width: '110px' }, { key: 'studentName', title: '姓名' },
  { key: 'advisorName', title: '指导教师' }, { key: 'enterpriseName', title: '企业' },
  { key: 'completeness', title: '完整度', width: '150px' }, { key: 'missing', title: '缺失材料' },
  { key: 'archived', title: '归档' }, { key: 'actions', title: '操作', width: '200px' }
]

export default {
  name: 'ArchiveView',
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppConfirmDialog,
    AppExportButton, AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox, ModuleSummaryStrip },
  data() {
    return {
      tab: 'student',
      tabs: [{ key: 'student', label: '按学生' }, { key: 'batch', label: '按批次' }, { key: 'enterprise', label: '按企业' }],
      studentColumns: STUDENT_COLUMNS,
      rows: [], total: 0, page: 1, pageSize: 20, aggRows: [], loading: false, error: '',
      archiveStudentTotal: null,
      keyword: '', onlyIncomplete: false,
      detailDlg: { visible: false, loading: false, data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      pkgBusy: false,
      pkgFile: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    aggColumns() {
      return [
        { key: 'group', title: this.tab === 'batch' ? '批次' : '企业' },
        { key: 'total', title: '实习人数' }, { key: 'complete', title: '材料完整' },
        { key: 'avgCompleteness', title: '平均完整度' }, { key: 'archived', title: '已归档' },
        { key: 'archiveRate', title: '归档率' }
      ]
    },
    detailItems() {
      const d = this.detailDlg.data || {}
      return [
        { label: '学生', value: `${d.studentName || '-'}（${d.studentNo || '-'}）` },
        { label: '完整度', value: `${d.completeness ?? 0}%` }
      ]
    },
    auditRecords() {
      return (this.detailDlg.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator,
        reason: t.detail && (t.detail.reason || t.detail.note || ''), at: t.occurredAt
      }))
    },
    summaryMetrics() {
      // 仅用「按学生」Tab 未筛选时的服务端 total；接口未返回缺失/已归档聚合数，不伪造
      if (this.loading || this.error) return []
      if (this.archiveStudentTotal == null) return []
      return [{ label: '应归档学生', value: this.archiveStudentTotal }]
    }
  },
  created() { this.load() },
  methods: {
    exportFn() { return archiveApi.exportArchives({ keyword: this.keyword }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    switchTab(k) { this.tab = k; this.page = 1; this.load() },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true; this.error = ''
      if (this.tab === 'student') {
        const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
        if (this.onlyIncomplete) params.onlyIncomplete = true
        const res = await archiveApi.getByStudent(params)
        this.loading = false
        if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
        this.rows = res.data.list; this.total = res.data.total
        // 无筛选时缓存服务端全量应归档人数，避免把筛选后小计当全量
        if (!this.keyword && !this.onlyIncomplete) this.archiveStudentTotal = res.data.total
      } else {
        const res = this.tab === 'batch' ? await archiveApi.byBatch() : await archiveApi.byEnterprise()
        this.loading = false
        if (res.code !== 0) { this.error = res.message || '加载失败'; this.aggRows = []; return }
        this.aggRows = res.data || []
      }
    },
    async openDetail(r) {
      this.detailDlg = { visible: true, loading: true, data: null }
      const res = await archiveApi.getDetail(r.id)
      this.detailDlg.loading = false
      if (res.code !== 0) { toast.error(res.message); this.detailDlg.visible = false; return }
      this.detailDlg.data = res.data
    },
    doArchive(r) {
      this.pending = { id: r.id, kind: 'archive', complete: r.completeness >= 100 }
      this.cd = { visible: true, title: '归档学生',
        content: r.completeness >= 100
          ? `「${r.studentName}」材料完整，确认归档？`
          : `「${r.studentName}」材料不完整（缺：${r.missing.join('、')}），确认带缺失强制归档？`,
        danger: r.completeness < 100, confirmText: '归档', requireReason: false, submitting: false }
    },
    doRevoke(r) {
      this.pending = { id: r.id, kind: 'revoke' }
      this.cd = { visible: true, title: '撤销归档', content: `撤销「${r.studentName}」的归档，原因将写审计。`,
        danger: true, confirmText: '撤销归档', requireReason: true, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      this.cd.submitting = true
      const res = p.kind === 'archive'
        ? await archiveApi.archive(p.id, { force: !p.complete })
        : await archiveApi.revoke(p.id, { reason })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('操作成功，已写审计'); this.load()
    },
    async buildPackage() {
      const id = this.detailDlg.data?.id
      if (!id) return
      this.pkgBusy = true
      const res = await archiveApi.buildPackage(id)
      this.pkgBusy = false
      if (res.code !== 0) return toast.error(res.message || '生成失败')
      this.pkgFile = res.data
      this.detailDlg.data = { ...this.detailDlg.data, packageReady: true }
      toast.success('归档包已生成，可下载')
    },
    async downloadPackage() {
      const id = this.detailDlg.data?.id
      if (!id) return
      if (!this.detailDlg.data?.packageReady && !this.pkgFile) {
        return this.buildPackage()
      }
      this.pkgBusy = true
      let fileId = this.pkgFile?.fileId
      let fileName = this.pkgFile?.fileName || '实习归档.zip'
      if (!fileId) {
        const res = await archiveApi.buildPackage(id)
        if (res.code !== 0) { this.pkgBusy = false; return toast.error(res.message) }
        fileId = res.data.fileId; fileName = res.data.fileName
      }
      try {
        await downloadAttachment(fileId, fileName)
      } catch (e) {
        toast.error(e?.message || '下载失败')
      }
      this.pkgBusy = false
    }
  }
}
</script>

<style scoped>
.tabs { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); border-bottom: 1px solid var(--border-light); }
.tabs__btn { border: none; background: none; padding: var(--space-2) var(--space-3); cursor: pointer; color: var(--text-secondary); font-size: var(--font-size-sm); border-bottom: 2px solid transparent; }
.tabs__btn.is-active { color: var(--primary-700); border-bottom-color: var(--primary-600); font-weight: var(--font-weight-medium); }
.bar { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.bar__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: auto; }
.chk { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); color: var(--text-secondary); }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.miss { color: var(--danger-600); font-size: var(--font-size-xs); }
.pct { display: flex; align-items: center; gap: var(--space-1); }
.pct__bar { width: 60px; height: 8px; background: var(--bg-subtle); border-radius: var(--radius-sm); overflow: hidden; }
.pct__fill { display: block; height: 100%; background: var(--warning-500, #f59e0b); }
.pct__fill.is-full { background: var(--success-500, #22c55e); }
.ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.modal { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: var(--z-modal, 1000); padding: var(--space-4); }
.modal__card { background: var(--bg-card); border-radius: var(--radius-lg); width: min(560px, 100%); max-height: 88vh; display: flex; flex-direction: column; box-shadow: var(--shadow-lg); }
.modal__head { padding: var(--space-4); font-weight: var(--font-weight-semibold); border-bottom: 1px solid var(--border-light); }
.modal__body { padding: var(--space-4); overflow-y: auto; }
.modal__foot { padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); display: flex; justify-content: flex-end; gap: var(--space-2); }
.mats { display: flex; flex-wrap: wrap; gap: var(--space-2); margin: var(--space-3) 0; }
.mat { display: flex; align-items: center; gap: 4px; font-size: var(--font-size-sm); padding: 2px var(--space-2); border-radius: var(--radius-sm); background: var(--success-50, #f0fdf4); color: var(--success-700); }
.mat.is-miss { background: var(--danger-50, #fef2f2); color: var(--danger-600); }
.mat__dot { font-weight: bold; }
.hint { margin-top: var(--space-2); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.pkg-bar { margin-top: var(--space-3); }
</style>
