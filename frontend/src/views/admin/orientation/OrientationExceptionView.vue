<template>
  <ModulePageShell title="迎新异常学生" subtitle="报到卡点 / 未到校 / 缴费与宿舍异常闭环处理" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="迎新异常处理">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 条异常 · 处理动作全程留痕`" @action="onToolbar">
        <template #right>
          <ColumnSettings v-model:selected-keys="visibleColumnKeys" :columns="allColumns" />
        </template>
      </ModuleToolbar>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" title="暂无迎新异常" description="当前数据范围内所有新生报到正常" />
      <DataTable
        v-else
        :columns="tableColumns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #batch-actions>
          <BatchActionBar :actions="batchBarActions" @action="onBatch" />
        </template>
        <template #cell-exceptionType="{ row }">
          <StatusTag type="danger" :label="labelOf('exceptionType', row.exceptionType)" dot />
        </template>
        <template #cell-riskLevel="{ row }">
          <RiskTag :level="row.riskLevel" />
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="exceptionTagType[row.status] || 'default'" :label="labelOf('exceptionStatus', row.status)" />
        </template>
        <template #cell-lastFollowTime="{ row }">
          <span :class="{ 'ori-overdue': !row.lastFollowTime }">{{ row.lastFollowTime || '从未跟进' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 异常详情 -->
      <AppDrawer v-model:visible="detailVisible" :title="detailData ? `异常详情 · ${detailData.exception.name}` : '异常详情'">
        <template v-if="detailData">
          <div class="ori-kv">
            <div class="ori-kv__item">
              <span class="ori-kv__label">异常类型</span>
              <StatusTag type="danger" :label="labelOf('exceptionType', detailData.exception.exceptionType)" />
            </div>
            <div class="ori-kv__item">
              <span class="ori-kv__label">处理状态</span>
              <StatusTag :type="exceptionTagType[detailData.exception.status] || 'default'" :label="labelOf('exceptionStatus', detailData.exception.status)" />
            </div>
            <div class="ori-kv__item"><span class="ori-kv__label">负责人</span><span class="ori-kv__value">{{ detailData.exception.handler }}</span></div>
            <div class="ori-kv__item"><span class="ori-kv__label">班级</span><span class="ori-kv__value">{{ detailData.exception.className }}</span></div>
          </div>
          <p class="ori-exc-desc">{{ detailData.exception.description }}</p>

          <h4 class="ori-drawer-sub">跟进记录（{{ detailData.exception.followUps.length }}）</h4>
          <div v-for="f in detailData.exception.followUps" :key="f.id" class="ori-follow">
            <div class="ori-follow__head">
              <span>{{ f.followTime }} · {{ labelOf('followUpWay', f.way) }} · {{ f.operator }}</span>
              <button type="button" class="ori-section__more" @click="startEditFollow(f)">编辑</button>
            </div>
            <div class="ori-follow__content">{{ f.content }}</div>
          </div>
          <EmptyState v-if="!detailData.exception.followUps.length" title="暂无跟进记录" />

          <h4 class="ori-drawer-sub">处理留痕</h4>
          <AuditTrailPanel :logs="detailData.auditLogs" />
        </template>
        <template #footer>
          <div class="ori-issue-footer">
            <AppButton variant="secondary" :disabled="!perm('orientation.followup.create').allowed" :title="perm('orientation.followup.create').reason" @click="startAddFollow">
              新增跟进
            </AppButton>
            <AppButton variant="warning" :disabled="!canEscalate" :title="!canEscalate ? escalateTip : ''" @click="escalateVisible = true">升级风险</AppButton>
            <AppButton variant="primary" :disabled="!canResolve" :title="!canResolve ? resolveTip : ''" @click="resolveVisible = true">标记已处理</AppButton>
          </div>
        </template>
      </AppDrawer>

      <!-- 新增/编辑跟进 -->
      <EditDrawer
        v-model:visible="followVisible"
        :title="editingFollow ? '编辑跟进记录' : '新增跟进记录'"
        :fields="followFields"
        :model="editingFollow"
        :submitting="submitting"
        submit-text="保存跟进"
        @submit="onFollowSubmit"
      />

      <AppConfirmDialog
        v-model:visible="resolveVisible"
        title="标记异常已处理"
        :message="detailData ? `确认「${detailData.exception.name}」的异常已处理完成？` : ''"
        type="primary"
        confirm-text="确认已处理"
        :submitting="submitting"
        @confirm="onResolve"
      />
      <AppConfirmDialog
        v-model:visible="escalateVisible"
        title="升级异常风险"
        :message="detailData ? `将「${detailData.exception.name}」的异常升级为高风险，并通知学院管理员。` : ''"
        type="danger"
        confirm-text="确认升级"
        require-reason
        reason-label="升级说明"
        reason-placeholder="请说明升级原因与需要协调的资源（不少于 5 个字）"
        :submitting="submitting"
        @confirm="onEscalate"
      />

      <ExportDialog
        v-model:visible="exportVisible"
        title="导出异常名单"
        :options="exportOpts"
        :selected-count="selected.length"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <AppDrawer v-model:visible="auditVisible" title="操作留痕 · 迎新异常">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 8：/admin/orientation/exceptions 迎新异常学生列表（详情 / 跟进 / 已处理 / 升级 / 批量提醒 / 导出 / 留痕）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppDrawer, AppButton } from '@/components/ui'
import { TableActionColumn, BatchActionBar, EditDrawer, ExportDialog, AuditTrailPanel, ColumnSettings, NoPermissionState } from '@/modules/orientation/components'
import * as api from '@/modules/orientation/api/orientation.api'
import { EXCEPTION_TAG_TYPE, toLabelMap } from '@/modules/orientation/constants/orientation.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', exceptionType: '', status: '', riskLevel: '' })

export default {
  name: 'OrientationExceptionView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    RiskTag,
    EmptyState,
    LoadingState,
    ErrorState,
    AppConfirmDialog,
    AppDrawer,
    AppButton,
    TableActionColumn,
    BatchActionBar,
    EditDrawer,
    ExportDialog,
    AuditTrailPanel,
    ColumnSettings,
    NoPermissionState
  },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      submitting: false,
      rows: [],
      total: 0,
      page: 1,
      pageSize: 10,
      selected: [],
      filters: EMPTY_FILTERS(),
      statusOptions: {},
      allColumns: [],
      visibleColumnKeys: [],
      batchDefs: [],
      exportOpts: {},
      detailVisible: false,
      detailData: null,
      followVisible: false,
      editingFollow: null,
      resolveVisible: false,
      escalateVisible: false,
      exportVisible: false,
      auditVisible: false,
      auditLogs: [],
      exceptionTagType: EXCEPTION_TAG_TYPE
    }
  },
  computed: {
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    perms() {
      return this.ctx?.permissionActions || {}
    },
    noPermission() {
      const p = this.perms['orientation.student.view']
      return p ? !p.allowed : false
    },
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 异常描述' },
        { key: 'exceptionType', label: '异常类型', type: 'select', options: this.statusOptions.exceptionType || [] },
        { key: 'status', label: '处理状态', type: 'select', options: this.statusOptions.exceptionStatus || [] },
        { key: 'riskLevel', label: '风险等级', type: 'select', options: this.statusOptions.riskLevel || [] }
      ]
    },
    tableColumns() {
      return this.allColumns.filter((c) => this.visibleColumnKeys.includes(c.key)).map((c) => ({ key: c.key, title: c.title }))
    },
    toolbarActions() {
      const exp = this.perms['orientation.exception.export']
      return [
        exp && !exp.visible ? null : { key: 'export', label: '导出异常名单', disabled: exp ? !exp.allowed : false, disabledReason: exp?.reason },
        { key: 'audit', label: '操作留痕' }
      ].filter(Boolean)
    },
    batchBarActions() {
      return this.batchDefs
        .map((b) => {
          const p = this.perms[b.permission]
          if (p && !p.visible) return null
          return { ...b, disabled: p ? !p.allowed : false, disabledReason: p?.reason }
        })
        .filter(Boolean)
    },
    followFields() {
      return [
        { key: 'way', label: '跟进方式', type: 'select', options: this.statusOptions.followUpWay || [], required: true },
        { key: 'content', label: '跟进内容', type: 'textarea', required: true, placeholder: '本次联系 / 处理的具体情况' }
      ]
    },
    canResolve() {
      const p = this.perms['orientation.exception.handle']
      const open = ['OPEN', 'PROCESSING', 'ESCALATED'].includes(this.detailData?.exception?.status)
      return open && (p ? p.allowed : true)
    },
    resolveTip() {
      if (!['OPEN', 'PROCESSING', 'ESCALATED'].includes(this.detailData?.exception?.status)) return '该异常已处理完成'
      return this.perms['orientation.exception.handle']?.reason || ''
    },
    canEscalate() {
      const p = this.perms['orientation.exception.escalate']
      const open = ['OPEN', 'PROCESSING'].includes(this.detailData?.exception?.status)
      return open && (p ? p.allowed : true)
    },
    escalateTip() {
      if (!['OPEN', 'PROCESSING'].includes(this.detailData?.exception?.status)) return '该异常当前状态不可升级'
      return this.perms['orientation.exception.escalate']?.reason || ''
    }
  },
  async created() {
    await this.init()
  },
  methods: {
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || value || '—'
    },
    perm(key) {
      return this.perms[key] || { allowed: true, visible: true, reason: '' }
    },
    async init() {
      const [ctx, status, cols, batch, exp] = await Promise.all([
        api.getOrientationContext(),
        api.getStatusOptions(),
        api.getFieldColumns('exceptionList'),
        api.getBatchActions('exceptionList'),
        api.getExportOptions('exceptionList')
      ])
      if (ctx.code === 0) this.ctx = ctx.data
      if (status.code === 0) this.statusOptions = status.data
      if (cols.code === 0) {
        this.allColumns = cols.data
        this.visibleColumnKeys = cols.data.filter((c) => c.default || c.locked).map((c) => c.key)
      }
      if (batch.code === 0) this.batchDefs = batch.data
      if (exp.code === 0) this.exportOpts = exp.data
      await this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      this.selected = []
      try {
        const res = await api.getExceptionStudents({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (res.code === 0) {
          this.rows = res.data.list
          this.total = res.data.total
        } else this.error = res.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    search() {
      this.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.page = 1
      this.load()
    },
    turnPage(p) {
      this.page = p
      this.load()
    },
    rowActions(row) {
      const handleP = this.perms['orientation.exception.handle']
      return [
        { key: 'detail', label: '异常详情' },
        { key: 'follow', label: '新增跟进', disabled: !this.perm('orientation.followup.create').allowed, disabledReason: this.perm('orientation.followup.create').reason },
        {
          key: 'resolve',
          label: '标记已处理',
          disabled: (handleP ? !handleP.allowed : false) || row.status === 'RESOLVED',
          disabledReason: row.status === 'RESOLVED' ? '该异常已处理' : handleP?.reason
        },
        { key: 'student', label: '学生详情' }
      ]
    },
    async openDetail(row) {
      const res = await api.getExceptionDetail(row.id)
      if (res.code === 0) {
        this.detailData = res.data
        this.detailVisible = true
      } else toast.error(res.message)
    },
    onRowAction(key, row) {
      if (key === 'detail') this.openDetail(row)
      if (key === 'student') this.$router.push(`/admin/orientation/students/${row.studentId}`)
      if (key === 'follow') {
        this.detailData = { exception: row, student: null, auditLogs: [] }
        this.startAddFollow()
      }
      if (key === 'resolve') {
        this.detailData = { exception: row, student: null, auditLogs: [] }
        this.resolveVisible = true
      }
    },
    startAddFollow() {
      this.editingFollow = null
      this.followVisible = true
    },
    startEditFollow(f) {
      this.editingFollow = f
      this.followVisible = true
    },
    onToolbar(key) {
      if (key === 'export') this.exportVisible = true
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({ bizType: 'EXCEPTION' })
      if (res.code === 0) this.auditLogs = res.data.list
      this.auditVisible = true
    },
    onBatch(key) {
      if (!this.selected.length) return
      if (key === 'batchRemind') this.doBatchRemind()
    },
    async doBatchRemind() {
      const ids = this.rows.filter((r) => this.selected.includes(r.id)).map((r) => r.studentId)
      const res = await api.batchRemindStudents(ids, '迎新异常处理提醒')
      if (res.code === 0) toast.success(`已向 ${res.data.count} 名学生/家长发送提醒，操作已留痕`)
    },
    async onFollowSubmit(form) {
      if (!this.detailData) return
      this.submitting = true
      try {
        const exceptionId = this.detailData.exception.id
        const res = this.editingFollow
          ? await api.updateExceptionFollowUp(exceptionId, this.editingFollow.id, form)
          : await api.addExceptionFollowUp(exceptionId, form)
        if (res.code === 0) {
          toast.success(this.editingFollow ? '跟进记录已更新并留痕' : '跟进记录已保存并留痕')
          this.followVisible = false
          const refreshed = await api.getExceptionDetail(exceptionId)
          if (refreshed.code === 0) this.detailData = refreshed.data
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onResolve() {
      if (!this.detailData) return
      this.submitting = true
      try {
        const res = await api.resolveException(this.detailData.exception.id, {})
        if (res.code === 0) {
          toast.success('异常已标记为已处理，操作已留痕')
          this.resolveVisible = false
          this.detailVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onEscalate({ reason }) {
      if (!this.detailData) return
      this.submitting = true
      try {
        const res = await api.escalateException(this.detailData.exception.id, { reason })
        if (res.code === 0) {
          toast.success('异常已升级为高风险，说明已留痕')
          this.escalateVisible = false
          this.detailVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    exportFn(payload) {
      return api.createExport('exceptionList', payload)
    }
  }
}
</script>

<style scoped>
@import './orientation-page.css';

.ori-overdue {
  color: var(--danger-600);
}
.ori-exc-desc {
  margin: var(--space-3) 0 0;
  padding: var(--space-3);
  background: var(--danger-50);
  border: 1px solid var(--danger-100);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--danger-600);
}
.ori-drawer-sub {
  margin: var(--space-4) 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.ori-follow {
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--border-light);
}
.ori-follow__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.ori-follow__content {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
}
.ori-issue-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
