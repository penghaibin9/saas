<template>
  <ModulePageShell
    title="我的待办"
    :subtitle="'共 ' + pagination.total + ' 条在办任务 · 超时与临期任务自动置顶'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" hint="导出默认脱敏并加水印" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="没有符合条件的待办任务"
        description="可调整筛选条件，或等待新的审批申请进入队列"
      />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="taskId"
        selectable
        v-model:selected="selected"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #batch-actions>
          <button
            v-for="b in ctx.batchActions"
            :key="b.key"
            class="mp-link"
            :class="{ 'is-disabled': !can(b.key) }"
            :title="reason(b.key)"
            @click="onBatch(b.key)"
          >
            {{ b.label }}
          </button>
        </template>
        <template #cell-task="{ row }">
          <div class="mp-cell-main">{{ row.title }}</div>
          <div class="mp-cell-sub">{{ row.taskId }} · {{ row.bizTypeLabel }}</div>
        </template>
        <template #cell-applicant="{ row }">
          <div class="mp-cell-main">{{ row.applicant.name }}</div>
          <div class="mp-cell-sub">{{ maskNo(row.applicant.studentNo) }} · {{ row.applicant.className }}</div>
        </template>
        <template #cell-deadline="{ row }">
          <div class="mp-cell-main">{{ row.deadline }}</div>
          <StatusTag :type="urgencyTone(row.urgency)" :label="row.urgencyLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/approval/todos/' + row.taskId)">办理</button>
        </template>
      </DataTable>

      <section class="mp-card">
        <div class="mp-card__head">
          <span class="mp-card__title">最近审计留痕</span>
          <span class="mp-note">审批、退回、转交与导出动作全部留痕</span>
        </div>
        <div class="mp-card__body">
          <table class="mp-audit">
            <thead>
              <tr><th>操作人</th><th>时间</th><th>动作</th><th>对象</th><th>说明</th></tr>
            </thead>
            <tbody>
              <tr v-for="a in audits" :key="a.id">
                <td class="is-who">{{ a.who }} · {{ a.roleName }}</td>
                <td>{{ a.time }}</td>
                <td>{{ a.action }}</td>
                <td>{{ a.target }}</td>
                <td>{{ a.detail }}</td>
              </tr>
              <tr v-if="!audits.length">
                <td colspan="5" class="mp-note">暂无审计记录</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <AppConfirmDialog
      v-model:visible="approveDialog"
      title="批量通过确认"
      :message="'将对已选 ' + selected.length + ' 条待办执行通过操作，审批意见默认为空，逐条留痕并同步申请人。'"
      type="primary"
      confirm-text="确认通过"
      :submitting="submitting"
      @confirm="doBatchApprove"
    />
    <AppConfirmDialog
      v-model:visible="returnDialog"
      title="批量退回确认"
      :message="'将对已选 ' + selected.length + ' 条待办执行退回操作，退回原因将原样同步申请人。'"
      type="danger"
      confirm-text="确认退回"
      require-reason
      reason-label="退回原因"
      reason-placeholder="请写明统一退回原因（不少于 5 个字），将同步至每位申请人"
      :submitting="submitting"
      @confirm="doBatchReturn"
    />
    <AppConfirmDialog
      v-model:visible="exportDialog"
      title="导出待办清单"
      message="导出文件默认脱敏敏感字段并添加页面水印，导出动作将写入审计日志。"
      type="primary"
      confirm-text="确认导出"
      :submitting="submitting"
      @confirm="doExport"
    />

    <AppDrawer v-model:visible="transferDrawer" title="批量转交待办">
      <p class="mp-note" style="margin: 0 0 var(--space-3)">
        已选 {{ selected.length }} 条待办将转交给同一位办理人，任务状态不变、办理节点转移并留痕。
      </p>
      <div
        v-for="t in ctx.transferTargets"
        :key="t.userId"
        class="mp-radio"
        :class="{ 'is-active': transferForm.targetUserId === t.userId }"
        @click="transferForm.targetUserId = t.userId"
      >
        <input type="radio" :checked="transferForm.targetUserId === t.userId" style="margin-top: 3px" />
        <div>
          <div class="mp-radio__title">{{ t.userName }} · {{ t.roleName }}</div>
          <div class="mp-radio__desc">{{ t.orgName }} · 当前在办 {{ t.pendingCount }} 条</div>
        </div>
      </div>
      <label class="mp-note" style="display: block; margin: var(--space-3) 0 var(--space-1)">转交说明（选填）</label>
      <textarea
        v-model="transferForm.note"
        class="mp-textarea"
        placeholder="例如：本人外出监考，请代为办理，紧急件优先…"
      ></textarea>
      <p v-if="transferError" class="mp-form-err">{{ transferError }}</p>
      <template #footer>
        <AppButton variant="ghost" @click="transferDrawer = false">取消</AppButton>
        <AppButton variant="primary" :loading="submitting" @click="doBatchTransfer">确认转交</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 我的待办（/admin/approval/todos）：高级筛选 + 批量通过/退回/转交闭环 + 导出留痕。
 * 批量按钮受 permissionActions 控制（置灰 + reason）；支持 $route.query.bizType 初始筛选。
 */
import {
  ModulePageShell,
  ModuleToolbar,
  AdvancedFilter,
  DataTable,
  StatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { approvalApi } from '@/modules/approval/api/approval.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ bizType: '', urgency: '', keyword: '', submitDate: '' })

export default {
  name: 'ApprovalTodoListView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppConfirmDialog,
    AppButton,
    AppDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      audits: [],
      selected: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      approveDialog: false,
      returnDialog: false,
      exportDialog: false,
      transferDrawer: false,
      transferForm: { targetUserId: '', note: '' },
      transferError: '',
      submitting: false,
      columns: [
        { key: 'task', title: '审批任务' },
        { key: 'applicant', title: '申请人' },
        { key: 'submitTime', title: '提交时间' },
        { key: 'deadline', title: '办理期限' },
        { key: 'currentNode', title: '当前节点' },
        { key: 'actions', title: '操作', width: '90px' }
      ]
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.filterOptions
      return [
        { key: 'bizType', label: '业务类型', type: 'select', options: o.bizTypes },
        { key: 'urgency', label: '紧急度', type: 'select', options: o.urgencies },
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '标题 / 申请人 / 学号 / 单号' },
        { key: 'submitDate', label: '提交日期', type: 'date' }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportRecords', label: '导出待办清单' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  watch: {
    '$route.query.bizType'(value) {
      if (this.$route.path !== '/admin/approval/todos') return
      this.filters.bizType =
        value && this.ctx.filterOptions.bizTypes.some((b) => b.value === value) ? value : ''
      this.pagination.page = 1
      this.load()
    }
  },
  created() {
    const bizType = this.$route.query.bizType
    if (bizType && this.ctx.filterOptions.bizTypes.some((b) => b.value === bizType)) {
      this.filters.bizType = bizType
    }
    const urgency = this.$route.query.urgency
    if (urgency && this.ctx.filterOptions.urgencies.some((u) => u.value === urgency)) {
      this.filters.urgency = urgency
    }
    // UnifiedTodo 分类下钻：approval 列表无 todoType 字段时仍保留 urgency/bizType；
    // todoType 透传给 load 作为关键词兜底提示（业务页自带 status 筛选更准）。
    if (this.$route.query.todoType && !this.filters.keyword) {
      this.filters.keyword = String(this.$route.query.todoType)
    }
    this.load()
    this.loadAudits()
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
    urgencyTone(urgency) {
      if (urgency === 'OVERDUE') return 'danger'
      if (urgency === 'URGENT') return 'warning'
      return 'default'
    },
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
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
    onToolbar(key) {
      if (key === 'exportRecords') this.exportDialog = true
    },
    onBatch(key) {
      if (!this.can(key)) return
      if (key === 'batchApprove') this.approveDialog = true
      if (key === 'batchReturn') this.returnDialog = true
      if (key === 'batchTransfer') {
        this.transferForm = { targetUserId: '', note: '' }
        this.transferError = ''
        this.transferDrawer = true
      }
    },
    async doBatchApprove() {
      this.submitting = true
      const res = await approvalApi.batchApprove([...this.selected])
      this.submitting = false
      this.approveDialog = false
      if (res.code === 0) {
        toast.success(
          '批量通过完成：成功 ' + res.data.succeeded + ' 条' + (res.data.skipped ? '，跳过 ' + res.data.skipped + ' 条' : '') + '，已留痕并同步申请人'
        )
        this.afterMutate()
      } else {
        toast.error(res.message)
      }
    },
    async doBatchReturn({ reason }) {
      this.submitting = true
      const res = await approvalApi.batchReturn([...this.selected], { reason })
      this.submitting = false
      this.returnDialog = false
      if (res.code === 0) {
        toast.success('批量退回完成：成功 ' + res.data.succeeded + ' 条，退回原因已同步申请人并写入退回记录')
        this.afterMutate()
      } else {
        toast.error(res.message)
      }
    },
    async doBatchTransfer() {
      this.transferError = ''
      if (!this.transferForm.targetUserId) {
        this.transferError = '请选择转交对象'
        return
      }
      this.submitting = true
      const res = await approvalApi.batchTransfer([...this.selected], {
        targetUserId: this.transferForm.targetUserId,
        note: this.transferForm.note
      })
      this.submitting = false
      if (res.code === 0) {
        this.transferDrawer = false
        toast.success('批量转交完成：' + res.data.succeeded + ' 条已转交给 ' + res.data.transferredTo + '，任务状态不变并已留痕')
        this.afterMutate()
      } else {
        this.transferError = res.message
      }
    },
    async doExport() {
      this.submitting = true
      const res = await approvalApi.exportRecords({ scope: 'TODO', purpose: '待办清单核对' })
      this.submitting = false
      this.exportDialog = false
      if (res.code === 0) {
        toast.success('导出任务已创建（' + res.data.auditId + '）：字段已脱敏、文件含水印，本次导出已写入审计日志')
        this.loadAudits()
      } else {
        toast.error(res.message)
      }
    },
    afterMutate() {
      this.selected = []
      this.load()
      this.loadAudits()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await approvalApi.getTodos({
        ...this.filters,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    async loadAudits() {
      const res = await approvalApi.getAuditLogs()
      if (res.code === 0) this.audits = res.data.slice(0, 6)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
