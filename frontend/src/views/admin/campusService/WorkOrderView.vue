<template>
  <ModulePageShell
    title="服务工单"
    :subtitle="'共 ' + pagination.total + ' 条 · SLA 超时自动标记逾期'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的服务工单" description="学生可通过小程序服务大厅发起咨询/报修/证明等申请" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #batch-actions>
          <button class="mp-link" :class="{ 'is-disabled': !can('campus.workorder.assign') }" :title="reason('campus.workorder.assign')" @click="openAssign">批量分派</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('campus.workorder.export') }" :title="reason('campus.workorder.export')" @click="openExport">导出选中</button>
        </template>
        <template #cell-code="{ row }">
          <div class="mp-cell-main">{{ row.code }}</div>
          <div class="mp-cell-sub">{{ row.createTime }}</div>
        </template>
        <template #cell-title="{ row }">
          <div class="mp-cell-main">{{ row.title }}</div>
        </template>
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-type="{ row }">{{ typeLabel(row.type) }}</template>
        <template #cell-priority="{ row }">
          <StatusTag :type="row.priority === 'HIGH' ? 'danger' : row.priority === 'MEDIUM' ? 'warning' : 'default'" :label="priorityLabel(row.priority)" />
        </template>
        <template #cell-handler="{ row }">
          <span :class="{ 'mp-note': !row.handler }">{{ row.handler || '未分派' }}</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status" :label="statusLabel(row.status)" dot />
        </template>
        <template #cell-overdue="{ row }">
          <StatusTag v-if="row.overdue" type="danger" :label="row.slaHint" />
          <span v-else class="mp-note">{{ row.slaHint }}</span>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">查看</button>
          <button
            v-if="!['COMPLETED', 'CLOSED'].includes(row.status)"
            class="mp-link"
            :class="{ 'is-disabled': !can('campus.workorder.handle') }"
            :title="reason('campus.workorder.handle')"
            @click="openHandle(row)"
          >
            处理
          </button>
          <button
            v-if="!['COMPLETED', 'CLOSED'].includes(row.status)"
            class="mp-link wov-danger"
            :class="{ 'is-disabled': !can('campus.workorder.close') }"
            :title="reason('campus.workorder.close')"
            @click="openClose(row)"
          >
            关闭
          </button>
        </template>
      </DataTable>

      <p class="mp-note">
        关怀类工单内容涉密，仅心理老师可见完整描述。新增/分派/处理/办结/关闭均写入审计日志并同步学生端进度；导出台账含水印并留痕。
      </p>
    </div>

    <AppDrawer v-model:visible="detailVisible" :title="detail ? '工单详情 · ' + detail.order.code : '工单详情'">
      <template v-if="detail">
        <div class="wov-sec">
          <div class="mp-kv"><span class="mp-kv__k">标题</span><span class="mp-kv__v">{{ detail.order.title }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ detail.order.name }}（{{ detail.order.className }}）</span></div>
          <div class="mp-kv"><span class="mp-kv__k">类型 / 优先级</span><span class="mp-kv__v">{{ typeLabel(detail.order.type) }} · {{ priorityLabel(detail.order.priority) }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">处理人</span><span class="mp-kv__v">{{ detail.order.handler || '未分派' }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">状态 / SLA</span><span class="mp-kv__v"><StatusTag :status="detail.order.status" :label="statusLabel(detail.order.status)" dot /> {{ detail.order.slaHint }}</span></div>
          <div class="mp-kv"><span class="mp-kv__k">申请内容</span><span class="mp-kv__v">{{ detail.order.detail }}</span></div>
        </div>
        <div class="wov-sec">
          <div class="wov-sec__title">流程记录</div>
          <ul class="mp-timeline">
            <li v-for="(t, i) in detail.trail" :key="i" class="mp-timeline__item" :class="'is-' + (t.tone === 'success' ? 'success' : t.tone === 'warning' ? 'warning' : 'default')">
              <div class="mp-timeline__title">{{ t.title }}</div>
              <div v-if="t.desc" class="mp-timeline__desc">{{ t.desc }}</div>
              <div class="mp-timeline__time">{{ t.time }}</div>
            </li>
          </ul>
        </div>
        <div class="wov-sec">
          <div class="wov-sec__title">操作审计</div>
          <table class="mp-audit">
            <thead><tr><th>时间</th><th>操作人</th><th>动作</th></tr></thead>
            <tbody>
              <tr v-for="a in detail.auditLogs" :key="a.id">
                <td>{{ a.time }}</td>
                <td class="is-who">{{ a.operator }}</td>
                <td>{{ a.detail }}</td>
              </tr>
              <tr v-if="!detail.auditLogs.length"><td colspan="3" class="mp-note">暂无审计记录</td></tr>
            </tbody>
          </table>
        </div>
      </template>
      <template #footer>
        <template v-if="detail && !['COMPLETED', 'CLOSED'].includes(detail.order.status)">
          <AppButton variant="secondary" :disabled="!can('campus.workorder.assign')" :title="reason('campus.workorder.assign')" @click="openAssignSingle(detail.order)">转交 / 分派</AppButton>
          <AppButton variant="primary" :disabled="!can('campus.workorder.handle')" :title="reason('campus.workorder.handle')" @click="openHandle(detail.order)">处理 / 办结</AppButton>
        </template>
        <AppButton v-else variant="ghost" @click="detailVisible = false">关闭</AppButton>
      </template>
    </AppDrawer>

    <FormDrawer
      v-model:visible="createForm.visible"
      v-model="createForm.model"
      title="新建服务工单（代学生登记）"
      :fields="createFields"
      :submitting="createForm.submitting"
      note="用于电话/现场接待时代学生登记；学生端小程序同步可见办理进度。"
      @submit="submitCreate"
    />

    <FormDrawer
      v-model:visible="assignForm.visible"
      v-model="assignForm.model"
      :title="assignForm.single ? '转交 / 分派工单' : '批量分派（已选 ' + selected.length + ' 条）'"
      :fields="assignFields"
      :submitting="assignForm.submitting"
      submit-text="确认分派"
      @submit="submitAssign"
    />

    <AppConfirmDialog
      v-model:visible="handleDialog.visible"
      type="primary"
      title="处理工单"
      :message="(handleDialog.row ? handleDialog.row.code + ' · ' + handleDialog.row.title : '') + '：填写处理说明后可选择继续处理或直接办结，进度同步学生端。'"
      confirm-text="提交处理"
      require-reason
      reason-label="处理说明"
      reason-placeholder="请填写处理过程与结果（不少于 5 个字）"
      show-notify
      notify-label="办结（勾选后状态置为已办结）"
      :submitting="handleDialog.submitting"
      @confirm="submitHandle"
    />

    <AppConfirmDialog
      v-model:visible="closeDialog.visible"
      type="danger"
      title="关闭工单"
      :message="'确认关闭「' + (closeDialog.row ? closeDialog.row.code : '') + '」？关闭用于重复/无效工单，关闭说明将同步学生端。'"
      confirm-text="确认关闭"
      require-reason
      reason-label="关闭说明"
      reason-placeholder="请说明关闭原因（如重复提交、已线下解决），不少于 5 个字"
      :submitting="closeDialog.submitting"
      @confirm="submitClose"
    />

    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="selected.length" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
  </ModulePageShell>
</template>

<script>
/**
 * 服务工单 / 咨询处理（/admin/campus-service/work-orders）。
 * 闭环：工单池 → 详情（流程记录+审计）→ 分派 / 处理（说明必填）→ 办结 / 关闭（原因必填）→ 导出（审计）。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppButton } from '@/components/ui'
import { ExportDrawer, FormDrawer } from '@/modules/campusService/components'
import {
  getServiceWorkOrders, getWorkOrderDetail, createWorkOrder, assignWorkOrders, handleWorkOrder, closeWorkOrder,
  getFieldColumns, getExportOptions, createExport, getServiceStudents
} from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '', priority: '' })

export default {
  name: 'WorkOrderView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, AppDrawer, AppButton, ExportDrawer, FormDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      selected: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [],
      studentsOptions: [],
      detailVisible: false,
      detail: null,
      createForm: { visible: false, submitting: false, model: {} },
      assignForm: { visible: false, submitting: false, single: null, model: {} },
      handleDialog: { visible: false, submitting: false, row: null },
      closeDialog: { visible: false, submitting: false, row: null },
      exportVisible: false,
      exportOpts: null
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.statusOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '标题 / 学生 / 编号' },
        { key: 'type', label: '工单类型', type: 'select', options: o.workOrderType },
        { key: 'status', label: '状态', type: 'select', options: o.workOrderStatus },
        { key: 'priority', label: '优先级', type: 'select', options: o.priority }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'create', permission: 'campus.workorder.create', label: '＋ 新建工单', variant: 'primary' },
        { key: 'export', permission: 'campus.workorder.export', label: '导出工单台账' }
      ]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({ ...a, disabled: !pa[a.permission].allowed, disabledReason: pa[a.permission].reason }))
    },
    createFields() {
      const o = this.ctx.statusOptions
      return [
        { key: 'studentId', label: '学生', type: 'select', required: true, options: this.studentsOptions },
        { key: 'title', label: '工单标题', type: 'text', required: true },
        { key: 'type', label: '类型', type: 'select', required: true, options: o.workOrderType },
        { key: 'priority', label: '优先级', type: 'select', required: true, options: o.priority },
        { key: 'detail', label: '内容描述', type: 'textarea', placeholder: '记录学生诉求与背景信息' }
      ]
    },
    assignFields() {
      return [{ key: 'handlerId', label: '处理人', type: 'select', required: true, options: this.ctx.filterOptions.handlers }]
    }
  },
  async created() {
    const cols = await getFieldColumns('workOrderList')
    if (cols.code === 0) this.columns = cols.data.filter((c) => c.locked || c.default).map((c) => ({ key: c.key, title: c.title }))
    await this.load()
    const createQ = this.$route.query.create
    if (createQ) this.openCreate(createQ === '1' ? '' : String(createQ))
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    lbl(group, v) {
      return ((this.ctx.statusOptions[group] || []).find((o) => o.value === v) || {}).label || v
    },
    typeLabel(v) {
      return this.lbl('workOrderType', v)
    },
    statusLabel(v) {
      return this.lbl('workOrderStatus', v)
    },
    priorityLabel(v) {
      return this.lbl('priority', v)
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await getServiceWorkOrders({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async onToolbar(key) {
      if (key === 'create') this.openCreate()
      else if (key === 'export') this.openExport()
    },
    async openCreate(studentId = '') {
      if (!this.can('campus.workorder.create')) return
      if (!this.studentsOptions.length) {
        const res = await getServiceStudents({ pageSize: 100 })
        if (res.code === 0) this.studentsOptions = res.data.list.map((s) => ({ value: s.id, label: `${s.name}（${s.className}）` }))
      }
      this.createForm = { visible: true, submitting: false, model: { studentId, priority: 'MEDIUM' } }
    },
    async submitCreate() {
      this.createForm.submitting = true
      const res = await createWorkOrder(this.createForm.model)
      this.createForm.submitting = false
      if (res.code === 0) {
        toast.success('工单已创建并写入审计日志，学生端可见办理进度')
        this.createForm.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openDetail(row) {
      const res = await getWorkOrderDetail(row.id)
      if (res.code === 0) {
        this.detail = res.data
        this.detailVisible = true
      } else {
        toast.error(res.message)
      }
    },
    openAssign() {
      if (!this.can('campus.workorder.assign')) return
      this.assignForm = { visible: true, submitting: false, single: null, model: {} }
    },
    openAssignSingle(order) {
      if (!this.can('campus.workorder.assign')) return
      this.assignForm = { visible: true, submitting: false, single: order, model: { handlerId: order.handlerId || '' } }
    },
    async submitAssign() {
      this.assignForm.submitting = true
      const ids = this.assignForm.single ? [this.assignForm.single.id] : this.selected
      const res = await assignWorkOrders(ids, { handlerId: this.assignForm.model.handlerId })
      this.assignForm.submitting = false
      if (res.code === 0) {
        toast.success(`已分派 ${res.data.count} 个工单，已留痕并通知处理人`)
        this.assignForm.visible = false
        this.detailVisible = false
        this.selected = []
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openHandle(row) {
      if (!this.can('campus.workorder.handle')) return
      this.handleDialog = { visible: true, submitting: false, row }
    },
    async submitHandle({ reason, notify }) {
      this.handleDialog.submitting = true
      const res = await handleWorkOrder(this.handleDialog.row.id, { note: reason, close: notify })
      this.handleDialog.submitting = false
      if (res.code === 0) {
        toast.success(notify ? '工单已办结，处理说明已同步学生端并留痕' : '处理进展已记录并同步学生端')
        this.handleDialog.visible = false
        this.detailVisible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    openClose(row) {
      if (!this.can('campus.workorder.close')) return
      this.closeDialog = { visible: true, submitting: false, row }
    },
    async submitClose({ reason }) {
      this.closeDialog.submitting = true
      const res = await closeWorkOrder(this.closeDialog.row.id, { reason })
      this.closeDialog.submitting = false
      if (res.code === 0) {
        toast.success('工单已关闭，说明已同步学生端并留痕')
        this.closeDialog.visible = false
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async openExport() {
      if (!this.can('campus.workorder.export')) return
      if (!this.exportOpts) {
        const res = await getExportOptions('workOrderList')
        if (res.code === 0) this.exportOpts = res.data
      }
      this.exportVisible = true
    },
    exportFn(payload) {
      return createExport('workOrderList', payload)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.wov-danger {
  color: var(--danger-600);
}
.mp-link + .mp-link {
  margin-left: var(--space-2);
}
.wov-sec {
  margin-bottom: var(--space-4);
}
.wov-sec__title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-2);
}
</style>
