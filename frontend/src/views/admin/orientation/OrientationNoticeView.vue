<template>
  <ModulePageShell title="迎新通知" subtitle="向新生下发报到通知（站内已接入；短信/邮件/小程序显示未配置，接入后再启用）" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="迎新通知">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="[{ key: 'create', label: '新建通知' }]" :hint="`共 ${total} 条通知`" @action="onToolbar" />
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无通知" description="点击右上角「新建通知」创建" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-status="{ row }">
          <StatusTag :type="statusTagType[row.status] || 'default'" :label="row.statusLabel" dot />
          <span v-if="row.failReason" class="onv-fail">（{{ row.failReason }}）</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>
      <EditDrawer v-model:visible="editVisible" title="新建通知" :fields="editFields" :model="editingModel" :submitting="submitting" @submit="onEditSubmit" />
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { EditDrawer, TableActionColumn, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '' })

export default {
  name: 'OrientationNoticeView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState, EditDrawer, TableActionColumn, NoPermissionState },
  data() {
    return { ctx: null, loading: true, error: '', submitting: false, rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(), editVisible: false, editingModel: null, statusTagType: { PENDING: 'warning', SENT: 'success', FAILED: 'danger', DISABLED: 'default' } }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '' },
    dataScopeName() { return this.ctx?.dataScope?.name || '' },
    perms() { return this.ctx?.permissionActions || {} },
    noPermission() { const p = this.perms['orientation.student.view']; return p ? !p.allowed : false },
    filterFields() { return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '通知标题' }, { key: 'status', label: '状态', type: 'select', options: [{ value: 'PENDING', label: '待发送' }, { value: 'SENT', label: '已发送' }, { value: 'DISABLED', label: '渠道未配置' }] }] },
    tableColumns() { return [{ key: 'title', title: '标题' }, { key: 'channelLabel', title: '渠道' }, { key: 'targetScope', title: '目标范围' }, { key: 'status', title: '状态' }, { key: 'sentCount', title: '发送数' }, { key: 'actions', title: '操作' }] },
    editFields() { return [{ key: 'title', label: '通知标题', type: 'text', required: true }, { key: 'content', label: '通知内容', type: 'textarea' }, { key: 'channel', label: '发送渠道', type: 'select', options: [{ value: 'INAPP', label: '站内通知（已接入）' }, { value: 'SMS', label: '短信（未配置）' }, { value: 'EMAIL', label: '邮件（未配置）' }, { value: 'MINIAPP', label: '小程序（未配置）' }] }, { key: 'targetScope', label: '目标范围', type: 'text', placeholder: '如：全体新生 / 某学院' }] }
  },
  async created() { const c = await api.getOrientationContext(); if (c.code === 0) this.ctx = c.data; await this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      try { const res = await api.getNoticeTasks({ ...this.filters, page: this.page, pageSize: this.pageSize }); if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message } catch (e) { this.error = e.message || '加载失败' } finally { this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(k) { if (k === 'create') { this.editingModel = { channel: 'INAPP' }; this.editVisible = true } },
    rowActions(row) { const sent = row.status === 'SENT'; return [{ key: 'send', label: '发送', disabled: sent, disabledReason: sent ? '已发送' : '' }] },
    async onRowAction(k, row) {
      if (k !== 'send') return
      const res = await api.sendNoticeTask(row.id)
      if (res.code === 0) { res.data.status === 'SENT' ? toast.success('已发送站内通知') : toast.error(res.data.failReason || '渠道未配置'); this.load() } else toast.error(res.message || '发送失败')
    },
    async onEditSubmit(form) {
      this.submitting = true
      try { const res = await api.createNoticeTask(form); if (res.code === 0) { toast.success('已新建通知'); this.editVisible = false; await this.load() } else toast.error(res.message || '保存失败') } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
.onv-fail {
  font-size: 11px;
  color: var(--t3);
  margin-left: 4px;
}
</style>
