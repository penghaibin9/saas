<template>
  <ModulePageShell
    title="服务工单"
    :subtitle="'共 ' + pagination.total + ' 条 · 待处理 ' + pendingTotal + ' 条 · SLA 超时自动标记逾期'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading && !rows.length" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的服务工单" description="学生可通过小程序服务大厅发起咨询/报修/证明等申请" />
      <SplitWorkspace v-else :has-selection="!!selectedId">
        <template #left>
          <div class="wov-queue">
            <div class="wov-queue__bar">
              <span>第 {{ positionText }} 条</span>
              <span class="wov-queue__ops">
                <button class="mp-link" :class="{ 'is-disabled': !can('campus.workorder.assign') || !checked.length }" :title="reason('campus.workorder.assign')" @click="openAssign">批量分派{{ checked.length ? '（' + checked.length + '）' : '' }}</button>
                <button class="mp-link" :class="{ 'is-disabled': !can('campus.workorder.export') }" :title="reason('campus.workorder.export')" @click="openExport">导出</button>
              </span>
            </div>
            <div class="wov-queue__list" ref="list">
              <div
                v-for="row in rows"
                :key="row.id"
                class="wov-item"
                :class="{ 'is-active': row.id === selectedId }"
                :data-row-id="row.id"
                @click="select(row.id)"
              >
                <input class="wov-item__check" type="checkbox" :value="row.id" v-model="checked" @click.stop />
                <div class="wov-item__main">
                  <div class="wov-item__line1">
                    <span class="wov-item__name">{{ row.title }}</span>
                    <StatusTag :status="row.status" :label="statusLabel(row.status)" dot />
                  </div>
                  <div class="wov-item__line2">
                    {{ row.name }}（{{ row.className }}）· {{ typeLabel(row.type) }}
                    <StatusTag :type="row.priority === 'HIGH' ? 'danger' : row.priority === 'MEDIUM' ? 'warning' : 'default'" :label="priorityLabel(row.priority)" />
                  </div>
                  <div class="wov-item__line3">
                    {{ row.code }} · {{ row.handler || '未分派' }}
                    <StatusTag v-if="row.overdue" type="danger" :label="row.slaHint" />
                  </div>
                </div>
              </div>
            </div>
            <div class="wov-queue__pager">
              <button class="mp-link" :class="{ 'is-disabled': pagination.page <= 1 }" @click="gotoPage(pagination.page - 1)">上一页</button>
              <span class="mp-note">第 {{ pagination.page }} / {{ maxPage }} 页 · 共 {{ pagination.total }} 条</span>
              <button class="mp-link" :class="{ 'is-disabled': pagination.page >= maxPage }" @click="gotoPage(pagination.page + 1)">下一页</button>
            </div>
          </div>
        </template>

        <template #detail="{ narrow }">
          <div v-if="!detail" class="mp-card wov-placeholder">
            <div class="mp-card__body"><p class="mp-note">从左侧选择一条工单开始处理</p></div>
          </div>
          <div v-else>
            <div class="wov-detail__head">
              <button v-if="narrow" class="mp-link" @click="backToList">← 返回列表</button>
              <div class="wov-detail__title">
                {{ detail.order.code }}
                <StatusTag :status="detail.order.status" :label="statusLabel(detail.order.status)" dot />
              </div>
              <div class="wov-detail__nav">
                <span class="mp-note">第 {{ positionText }} 条</span>
                <AppButton variant="ghost" :disabled="!hasPrev" @click="step(-1)">上一条</AppButton>
                <AppButton variant="ghost" :disabled="!hasNext" @click="step(1)">下一条</AppButton>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">工单信息</div></div>
              <div class="mp-card__body">
                <div class="mp-kv"><span class="mp-kv__k">标题</span><span class="mp-kv__v">{{ detail.order.title }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ detail.order.name }}（{{ detail.order.className }}）</span></div>
                <div class="mp-kv"><span class="mp-kv__k">类型 / 优先级</span><span class="mp-kv__v">{{ typeLabel(detail.order.type) }} · {{ priorityLabel(detail.order.priority) }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">处理人</span><span class="mp-kv__v">{{ detail.order.handler || '未分派' }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">SLA</span><span class="mp-kv__v">{{ detail.order.slaHint }}</span></div>
                <div class="mp-kv"><span class="mp-kv__k">申请内容</span><span class="mp-kv__v">{{ detail.order.detail }}</span></div>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">流程记录</div></div>
              <div class="mp-card__body">
                <ul class="mp-timeline">
                  <li v-for="(t, i) in detail.trail" :key="i" class="mp-timeline__item" :class="'is-' + (t.tone === 'success' ? 'success' : t.tone === 'warning' ? 'warning' : 'default')">
                    <div class="mp-timeline__title">{{ t.title }}</div>
                    <div v-if="t.desc" class="mp-timeline__desc">{{ t.desc }}</div>
                    <div class="mp-timeline__time">{{ t.time }}</div>
                  </li>
                </ul>
              </div>
            </div>

            <div class="mp-card">
              <div class="mp-card__head"><div class="mp-card__title">操作审计</div></div>
              <div class="mp-card__body">
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
            </div>

            <div v-if="!['COMPLETED', 'CLOSED'].includes(detail.order.status)" class="wov-actzone">
              <AppButton variant="secondary" :disabled="!can('campus.workorder.assign')" :title="reason('campus.workorder.assign')" @click="openAssignSingle(detail.order)">转交 / 分派</AppButton>
              <AppButton variant="danger" :disabled="!can('campus.workorder.close')" :title="reason('campus.workorder.close')" @click="openClose(detail.order)">关闭</AppButton>
              <span class="wov-actzone__sp" />
              <AppButton variant="primary" :disabled="!can('campus.workorder.handle')" :title="reason('campus.workorder.handle')" @click="openHandle(detail.order)">处理 / 办结</AppButton>
            </div>
            <p v-else class="mp-note">该工单已办结/关闭；可用「上一条 / 下一条」继续处理队列中的其他工单。</p>
          </div>
        </template>
      </SplitWorkspace>

      <p class="mp-note">
        关怀类工单内容涉密，仅心理老师可见完整描述。新增/分派/处理/办结/关闭均写入审计日志并同步学生端进度；导出台账含水印并留痕。
      </p>
    </div>

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
      :title="assignForm.single ? '转交 / 分派工单' : '批量分派（已选 ' + checked.length + ' 条）'"
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

    <ExportDrawer v-model:visible="exportVisible" :options="exportOpts" :selected-count="checked.length" :data-scope-name="ctx.dataScope.name" :export-fn="exportFn" />
  </ModulePageShell>
</template>

<script>
/**
 * 服务工单（/admin/campus-service/work-orders）— 列表＋详情双栏连续处理工作区（2026-07-10 第二批交互改造）。
 * 原工单详情抽屉改为右栏（工单信息/流程记录/操作审计/操作区），支持上一条/下一条、处理后自动定位；
 * 新建/分派仍为轻量表单抽屉（字段≤5），处理/关闭仍为确认弹窗（说明必填）。
 * 筛选、页码、选中项同步路由 query；窄屏降级全屏详情；接口与权限零改动。
 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppButton } from '@/components/ui'
import { ExportDrawer, FormDrawer, SplitWorkspace, readListState, writeListState } from '@/modules/campusService/components'
import {
  getServiceWorkOrders, getWorkOrderDetail, createWorkOrder, assignWorkOrders, handleWorkOrder, closeWorkOrder,
  getExportOptions, createExport, getServiceStudents
} from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

const FILTER_KEYS = ['keyword', 'type', 'status', 'priority']
const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '', priority: '' })

export default {
  name: 'WorkOrderView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, StatusTag, LoadingState, ErrorState, EmptyState,
    AppConfirmDialog, AppButton, ExportDrawer, FormDrawer, SplitWorkspace
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      checked: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      pendingTotal: 0,
      selectedId: '',
      detail: null,
      studentsOptions: [],
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
    },
    maxPage() {
      return Math.max(1, Math.ceil(this.pagination.total / this.pagination.pageSize))
    },
    selectedIndex() {
      return this.rows.findIndex((r) => r.id === this.selectedId)
    },
    positionText() {
      const idx = this.selectedIndex
      const abs = idx >= 0 ? (this.pagination.page - 1) * this.pagination.pageSize + idx + 1 : 0
      return `${abs || '—'} / ${this.pagination.total}`
    },
    hasPrev() {
      return this.selectedIndex > 0 || this.pagination.page > 1
    },
    hasNext() {
      return (this.selectedIndex >= 0 && this.selectedIndex < this.rows.length - 1) || this.pagination.page < this.maxPage
    }
  },
  async created() {
    const st = readListState(this.$route, FILTER_KEYS)
    this.filters = { ...EMPTY_FILTERS(), ...st.filters }
    this.pagination.page = st.page
    this.selectedId = st.selectedId
    await this.load()
    this.loadPendingTotal()
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
    syncQuery() {
      writeListState(this.$router, this.$route, {
        page: this.pagination.page, filters: this.filters, selectedId: this.selectedId, filterKeys: FILTER_KEYS
      })
    },
    async loadPendingTotal() {
      const res = await getServiceWorkOrders({ status: 'PENDING', page: 1, pageSize: 1 })
      if (res.code === 0) this.pendingTotal = res.data.total
    },
    async load({ select = 'keep' } = {}) {
      this.loading = true
      this.error = ''
      const res = await getServiceWorkOrders({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
        this.checked = this.checked.filter((id) => this.rows.some((r) => r.id === id))
        await this.ensureSelection(select)
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async ensureSelection(mode) {
      if (!this.rows.length) {
        this.selectedId = ''
        this.detail = null
        this.syncQuery()
        return
      }
      let target = this.rows.find((r) => r.id === this.selectedId)
      if (!target || mode === 'first') target = mode === 'last' ? this.rows[this.rows.length - 1] : this.rows[0]
      await this.select(target.id)
    },
    async select(id) {
      this.selectedId = id
      this.syncQuery()
      const res = await getWorkOrderDetail(id)
      if (res.code === 0) {
        this.detail = res.data
        this.$nextTick(() => {
          const el = this.$refs.list && this.$refs.list.querySelector(`[data-row-id="${id}"]`)
          if (el && el.scrollIntoView) el.scrollIntoView({ block: 'nearest' })
        })
      } else {
        this.detail = null
        toast.error(res.message)
      }
    },
    backToList() {
      this.selectedId = ''
      this.detail = null
      this.syncQuery()
    },
    async gotoPage(page) {
      if (page < 1 || page > this.maxPage) return
      this.pagination.page = page
      await this.load({ select: 'first' })
    },
    async step(delta) {
      const idx = this.selectedIndex
      const next = idx + delta
      if (next >= 0 && next < this.rows.length) {
        await this.select(this.rows[next].id)
      } else if (delta > 0 && this.pagination.page < this.maxPage) {
        this.pagination.page += 1
        await this.load({ select: 'first' })
      } else if (delta < 0 && this.pagination.page > 1) {
        this.pagination.page -= 1
        await this.load({ select: 'last' })
      }
    },
    search() {
      this.pagination.page = 1
      this.selectedId = ''
      this.load({ select: 'first' })
      this.loadPendingTotal()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.selectedId = ''
      this.load({ select: 'first' })
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
        this.loadPendingTotal()
      } else {
        toast.error(res.message)
      }
    },
    openAssign() {
      if (!this.can('campus.workorder.assign') || !this.checked.length) return
      this.assignForm = { visible: true, submitting: false, single: null, model: {} }
    },
    openAssignSingle(order) {
      if (!this.can('campus.workorder.assign')) return
      this.assignForm = { visible: true, submitting: false, single: order, model: {} }
    },
    async submitAssign() {
      this.assignForm.submitting = true
      const ids = this.assignForm.single ? [this.assignForm.single.id] : this.checked
      const res = await assignWorkOrders(ids, { handlerId: this.assignForm.model.handlerId })
      this.assignForm.submitting = false
      if (res.code === 0) {
        toast.success(`已分派 ${res.data.count} 条工单（已留痕并通知处理人）`)
        this.assignForm.visible = false
        if (!this.assignForm.single) this.checked = []
        await this.load()
        if (this.selectedId) this.select(this.selectedId)
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
      const prevIndex = this.selectedIndex
      const res = await handleWorkOrder(this.handleDialog.row.id, { note: reason, close: notify })
      this.handleDialog.submitting = false
      if (res.code === 0) {
        toast.success(notify ? '工单已办结，处理说明已留痕并同步学生端' : '处理进展已记录并同步学生端')
        this.handleDialog.visible = false
        await this.afterHandled(prevIndex, notify)
        this.loadPendingTotal()
      } else {
        toast.error(res.message)
        this.handleDialog.visible = false
        await this.load()
      }
    },
    openClose(row) {
      if (!this.can('campus.workorder.close')) return
      this.closeDialog = { visible: true, submitting: false, row }
    },
    async submitClose({ reason }) {
      this.closeDialog.submitting = true
      const prevIndex = this.selectedIndex
      const res = await closeWorkOrder(this.closeDialog.row.id, { reason })
      this.closeDialog.submitting = false
      if (res.code === 0) {
        toast.success('工单已关闭，关闭说明已同步学生端并留痕')
        this.closeDialog.visible = false
        await this.afterHandled(prevIndex, true)
        this.loadPendingTotal()
      } else {
        toast.error(res.message)
        this.closeDialog.visible = false
        await this.load()
      }
    },
    /* 办结/关闭后：刷新队列；goNext=true 时自动定位下一条待处理 */
    async afterHandled(prevIndex, goNext) {
      const handledId = this.selectedId
      const res = await getServiceWorkOrders({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code !== 0) {
        this.error = res.message
        return
      }
      this.rows = res.data.list
      this.pagination.total = res.data.total
      this.checked = this.checked.filter((id) => this.rows.some((r) => r.id === id))
      if (!this.rows.length) {
        if (this.pagination.page > 1) {
          this.pagination.page -= 1
          return this.load({ select: 'first' })
        }
        return this.ensureSelection('keep')
      }
      if (!goNext) {
        const still = this.rows.find((r) => r.id === handledId)
        return this.select(still ? handledId : this.rows[Math.min(prevIndex, this.rows.length - 1)].id)
      }
      const stillIdx = this.rows.findIndex((r) => r.id === handledId)
      let nextIdx = stillIdx >= 0 ? stillIdx + 1 : Math.min(Math.max(prevIndex, 0), this.rows.length - 1)
      if (nextIdx >= this.rows.length) {
        if (this.pagination.page < this.maxPage) {
          this.pagination.page += 1
          return this.load({ select: 'first' })
        }
        nextIdx = this.rows.length - 1
      }
      return this.select(this.rows[nextIdx].id)
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
.wov-queue {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
}
.wov-queue__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  font-size: var(--font-size-sm);
}
.wov-queue__ops .mp-link + .mp-link {
  margin-left: var(--space-2);
}
.wov-queue__list {
  max-height: 560px;
  overflow: auto;
}
.wov-item {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
}
.wov-item:hover {
  background: var(--bg-section-blue, var(--primary-50));
}
.wov-item.is-active {
  background: var(--primary-50);
  box-shadow: inset 2px 0 0 var(--primary-500);
}
.wov-item__check {
  margin-top: 4px;
  flex-shrink: 0;
}
.wov-item__main {
  min-width: 0;
}
.wov-item__line1 {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.wov-item__name {
  font-weight: var(--font-weight-semibold);
}
.wov-item__line2 {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.wov-item__line3 {
  font-size: var(--font-size-xs, 12px);
  color: var(--text-tertiary, var(--text-secondary));
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.wov-queue__pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) var(--space-3);
}
.wov-detail__head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  flex-wrap: wrap;
}
.wov-detail__title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.wov-detail__nav {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.mp-stack .mp-card + .mp-card {
  margin-top: var(--space-3);
}
.wov-actzone {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
}
.wov-actzone__sp {
  flex: 1;
}
.wov-placeholder {
  text-align: center;
}
.mp-link.is-disabled {
  pointer-events: none;
  opacity: 0.5;
}
</style>
