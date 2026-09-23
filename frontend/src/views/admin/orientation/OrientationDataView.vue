<template>
  <ModulePageShell title="新生查询" subtitle="查看当前批次新生，点击姓名继续办理；身份证与手机号默认脱敏" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="新生数据">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="canExport ? [{ key: 'export', label: '导出当前批次台账' }] : []" :hint="`共 ${total} 名新生 · 敏感字段脱敏`" @action="onToolbar" />
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无新生数据" description="当前数据范围内没有匹配的新生" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-name="{ row }"><button type="button" class="data-student-link" @click="openStudent(row)">{{ row.name }}</button></template>
        <template #cell-stage="{ row }">
          <StatusTag :type="row.stage === 'PRE_STUDENT_VERIFIED' ? 'success' : 'default'" :label="row.stageLabel" />
        </template>
      </DataTable>
      <ExportDialog v-model:visible="exportVisible" title="导出当前批次新生台账" :options="exportOpts" :data-scope-name="dataScopeName" :export-fn="exportFn" />
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { NoPermissionState, ExportDialog } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', stage: '' })

export default {
  name: 'OrientationDataView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState, NoPermissionState, ExportDialog },
  data() { return { ctx: null, loading: true, error: '', rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(), loadSerial: 0, exportVisible: false, exportOpts: {} } },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    canExport() { return !!this.perms['orientation.student.export']?.allowed },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    filterFields() { return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 录取编号' }, { key: 'stage', label: '阶段', type: 'select', options: [{ value: 'ADMITTED', label: '已录取' }, { value: 'PRE_STUDENT_VERIFIED', label: '预报到已核验' }, { value: 'ENROLLED', label: '已入学' }] }] },
    tableColumns() { return [{ key: 'name', title: '姓名' }, { key: 'admissionNo', title: '录取编号' }, { key: 'gender', title: '性别' }, { key: 'collegeName', title: '学院' }, { key: 'majorName', title: '专业' }, { key: 'className', title: '班级' }, { key: 'phone', title: '手机(脱敏)' }, { key: 'idCard', title: '身份证(脱敏)' }, { key: 'stage', title: '阶段' }] }
  },
  async created() {
    const [context, options] = await Promise.all([api.getOrientationContext(), api.getExportOptions('studentList')])
    if (context.code === 0) this.ctx = context.data
    if (options.code === 0) this.exportOpts = options.data
    await this.load()
  },
  beforeUnmount() { this.loadSerial++ },
  methods: {
    async load() {
      const serial = ++this.loadSerial
      this.loading = true; this.error = ''; this.rows = []; this.total = 0
      try {
        const res = await api.getOrientationStudents({ ...this.filters, batchId: this.$route.query.batchId || undefined, page: this.page, pageSize: this.pageSize })
        if (serial !== this.loadSerial) return
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
        else this.error = res.message || '新生读取失败，请重试'
      } catch (e) { if (serial === this.loadSerial) this.error = e.message || '加载失败' }
      finally { if (serial === this.loadSerial) this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(k) {
      if (k !== 'export' || !this.canExport) return
      if (!this.$route.query.batchId) { toast.error('请先从迎新批次进入，再导出该批次数据'); return }
      this.exportVisible = true
    },
    exportFn(payload) {
      if (!this.canExport) return { code: 403001, message: '当前身份没有迎新导出权限' }
      return api.createExport('studentList', { ...payload, batchId: this.$route.query.batchId })
    },
    openStudent(row) {
      this.$router.push({ path: `/admin/orientation/students/${row.id}`, query: { batchId: row.batchId || this.$route.query.batchId } })
    }
  }
}
</script>

<style scoped>
.data-student-link { padding: 0; border: 0; background: none; color: var(--primary-600); cursor: pointer; font: inherit; text-decoration: underline; }
</style>
