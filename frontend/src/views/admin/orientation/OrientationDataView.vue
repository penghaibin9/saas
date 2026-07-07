<template>
  <ModulePageShell title="新生数据" subtitle="录取新生原始数据总览（身份证/手机号默认脱敏，导出带水印与审计）" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="新生数据">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[{ key: 'export', label: '导出新生数据' }]" :hint="`共 ${total} 名新生 · 敏感字段脱敏`" @action="onToolbar" />
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无新生数据" description="当前数据范围内没有匹配的新生" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-stage="{ row }">
          <StatusTag :type="row.stage === 'PRE_STUDENT_VERIFIED' ? 'success' : 'default'" :label="row.stageLabel" />
        </template>
      </DataTable>
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', stage: '' })

export default {
  name: 'OrientationDataView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState, NoPermissionState },
  data() { return { ctx: null, loading: true, error: '', rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS() } },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    filterFields() { return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 录取编号' }, { key: 'stage', label: '阶段', type: 'select', options: [{ value: 'ADMITTED', label: '已录取' }, { value: 'PRE_STUDENT_VERIFIED', label: '预报到已核验' }, { value: 'ENROLLED', label: '已入学' }] }] },
    tableColumns() { return [{ key: 'name', title: '姓名' }, { key: 'admissionNo', title: '录取编号' }, { key: 'gender', title: '性别' }, { key: 'collegeName', title: '学院' }, { key: 'majorName', title: '专业' }, { key: 'className', title: '班级' }, { key: 'phone', title: '手机(脱敏)' }, { key: 'idCard', title: '身份证(脱敏)' }, { key: 'stage', title: '阶段' }] }
  },
  async created() { const c = await api.getOrientationContext(); if (c.code === 0) this.ctx = c.data; await this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try { const res = await api.getOrientationStudents({ ...this.filters, page: this.page, pageSize: this.pageSize }); if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    async onToolbar(k) {
      if (k !== 'export') return
      const res = await api.createExport('orientationStudents', { scope: 'FILTERED', mask: true, auditConfirmed: true })
      if (res.code === 0) toast.success(`已生成导出：${res.data.fileName}`)
      else toast.error(res.message || '导出失败')
    }
  }
}
</script>
