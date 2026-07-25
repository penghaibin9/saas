<template>
  <ModulePageShell
    title="学籍状态管理"
    :subtitle="'共 ' + pagination.total + ' 条变更记录 · 每次变更均需原因并留痕'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="学籍状态管理"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="暂无学籍变更记录"
        description="可调整筛选条件，或点击右上角「发起状态变更」"
      />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-change="{ row }">
          <AppStatusTag :type="tone(row.fromStatus)" :label="statusLabel(row.fromStatus)" />
          <span class="ss-arrow">→</span>
          <AppStatusTag :type="tone(row.toStatus)" :label="statusLabel(row.toStatus)" dot />
        </template>
        <template #cell-reason="{ row }">
          <div class="mp-cell-main ss-reason">{{ row.reason }}</div>
          <div v-if="row.attachment" class="mp-cell-sub">附件：{{ row.attachment }}</div>
        </template>
        <template #cell-operator="{ row }">
          <div class="mp-cell-main">{{ row.operator }}</div>
          <div class="mp-cell-sub">{{ row.roleName }}</div>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/student/' + row.studentId)">学生360</button>
        </template>
      </DataTable>

      <p class="mp-note">
        本页为学籍异动台账（只读）：学籍状态的唯一写入口是「学籍异动」多级审批，
        审批终审通过后状态才真正变更并在此显示。发起休学/复学/退学/保留学籍/留级/转班请前往
        <button class="mp-link" @click="goApply">教务中心 › 学籍异动 › 发起异动</button>。
      </p>
    </div>

    <!-- 发起 / 批量状态变更 -->
    <AppDrawer :visible="drawer.visible" :title="drawer.batch ? '批量变更学籍状态' : '发起学籍状态变更'" @update:visible="drawer.visible = $event">
      <div class="mp-stack">
        <template v-if="drawer.batch">
          <p class="mp-note">在当前数据范围内选择学生（已排除作废主档），本次将统一变更为同一目标状态。</p>
          <div class="ss-stu-list">
            <label v-for="s in candidates" :key="s.studentId" class="ss-stu-item">
              <input
                type="checkbox"
                :checked="drawer.studentIds.includes(s.studentId)"
                @change="toggleStudent(s.studentId, $event.target.checked)"
              />
              <span class="mp-cell-main">{{ s.name }}</span>
              <span class="mp-cell-sub">{{ s.className }} · {{ statusLabel(s.studentStatus) }}</span>
            </label>
          </div>
        </template>
        <template v-else>
          <label class="ss-field">
            <span class="ss-field__label">选择学生 *</span>
            <select v-model="drawer.studentId" class="ss-field__control">
              <option value="">请选择学生</option>
              <option v-for="s in candidates" :key="s.studentId" :value="s.studentId">
                {{ s.name }} · {{ s.className }} · 当前 {{ statusLabel(s.studentStatus) }}
              </option>
            </select>
          </label>
        </template>

        <div>
          <div class="ss-field__label ss-field__label--block">目标状态 *</div>
          <label
            v-for="o in ctx.statusOptions.studentStatusFlow"
            :key="o.value"
            class="mp-radio"
            :class="{ 'is-active': drawer.toStatus === o.value }"
          >
            <input v-model="drawer.toStatus" type="radio" :value="o.value" />
            <span>
              <span class="mp-radio__title">{{ o.label }}</span>
              <span class="mp-radio__desc">{{ statusDesc(o.value) }}</span>
            </span>
          </label>
        </div>

        <label class="ss-field">
          <span class="ss-field__label">变更原因 *（≥5 字，写入审计）</span>
          <textarea v-model="drawer.reason" class="mp-textarea" placeholder="如：因病申请休学一学年，附三甲医院诊断证明" />
        </label>
        <label class="ss-field">
          <span class="ss-field__label">依据附件（选填）</span>
          <input v-model="drawer.attachment" class="ss-field__control" placeholder="如：休学申请表.pdf" />
        </label>

        <p v-if="drawer.error" class="mp-form-err">{{ drawer.error }}</p>
        <div class="ss-drawer-ops">
          <AppButton variant="ghost" @click="drawer.visible = false">取消</AppButton>
          <AppButton variant="primary" :disabled="drawer.submitting" @click="submitChange">
            {{ drawer.batch ? '确认批量变更' : '确认变更' }}
          </AppButton>
        </div>
      </div>
    </AppDrawer>

    <!-- 学籍状态变更 · 高风险二次确认 -->
    <AppConfirmDialog
      :visible="confirmDialog.visible"
      type="danger"
      title="确认变更学籍状态"
      :message="'操作对象：' + confirmTargetText() + '。将申请变更为「' + statusLabel(drawer.toStatus) + '」，变更原因：' + drawer.reason + '。提交后进入学籍异动审批（辅导员→学院→教务处），终审通过才生效，请确认。'"
      confirm-text="确认变更"
      :submitting="confirmDialog.submitting"
      @update:visible="confirmDialog.visible = $event"
      @confirm="doSubmitChange"
    />

    <!-- 导出变更记录 -->
    <AppConfirmDialog
      :visible="exportDialog.visible"
      type="warning"
      title="导出学籍变更记录"
      :message="'将导出当前筛选范围内 ' + pagination.total + ' 条变更记录：敏感字段脱敏、文件附水印、写入审计日志。'"
      confirm-text="确认导出"
      require-reason
      reason-label="导出用途"
      reason-placeholder="如：学籍季度检查材料（不少于 5 个字）"
      :submitting="exportDialog.submitting"
      @update:visible="exportDialog.visible = $event"
      @confirm="submitExport"
    />
  </ModulePageShell>
</template>

<script>
/** 学籍状态管理（/admin/student/status）：变更记录 + 发起变更 + 批量变更 + 导出留痕。 */
import {
  ModulePageShell,
  ModuleToolbar,
  AdvancedFilter,
  DataTable,
  StatusTag as AppStatusTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { studentApi } from '@/modules/student/api/student.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', toStatus: '', dateFrom: '' })

const STATUS_DESC = {
  ADMITTED: '新生已录取，待完成迎新报到',
  ACTIVE: '正常在读，参与全部教学与实习安排',
  SUSPENDED: '保留学籍暂停学业，需附医院或相关证明',
  GRADUATED: '完成培养方案审核，准予毕业',
  DROPPED: '终止学业，需本人申请与监护人确认'
}

export default {
  name: 'StudentStatusView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    AppStatusTag,
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
      candidates: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'student', title: '学生' },
        { key: 'change', title: '状态变更' },
        { key: 'reason', title: '原因与依据' },
        { key: 'operator', title: '操作人' },
        { key: 'operatedAt', title: '时间', width: '150px' },
        { key: 'actions', title: '操作', width: '90px' }
      ],
      drawer: {
        visible: false,
        batch: false,
        studentId: '',
        studentIds: [],
        toStatus: '',
        reason: '',
        attachment: '',
        error: '',
        submitting: false
      },
      exportDialog: { visible: false, submitting: false },
      /* 高风险二次确认（2026-07-10 第二批交互纠偏） */
      confirmDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '学生姓名', type: 'text', placeholder: '按姓名搜索' },
        { key: 'toStatus', label: '目标状态', type: 'select', options: this.ctx.statusOptions.studentStatusFlow },
        { key: 'dateFrom', label: '起始日期', type: 'date' }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'change', label: '发起状态变更', variant: 'primary', perm: 'changeStatus' },
        { key: 'batch', label: '批量变更', perm: 'batchChangeStatus' },
        { key: 'export', label: '导出变更记录', perm: 'exportStatusRecords' }
      ]
        .filter((a) => pa[a.perm] && pa[a.perm].visible)
        .map((a) => ({ ...a, disabled: !pa[a.perm].allowed, disabledReason: pa[a.perm].reason }))
    }
  },
  created() {
    this.load()
    this.loadCandidates()
  },
  methods: {
    statusLabel(v) {
      const hit = this.ctx.statusOptions.studentStatus.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    statusDesc(v) {
      return STATUS_DESC[v] || ''
    },
    tone(v) {
      return { ADMITTED: 'processing', ACTIVE: 'success', SUSPENDED: 'warning', GRADUATED: 'info', DROPPED: 'default' }[v] || 'default'
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
      if (key === 'change') this.openDrawer(false)
      if (key === 'batch') this.openDrawer(true)
      if (key === 'export') this.exportDialog = { visible: true, submitting: false }
    },
    openDrawer(batch) {
      this.drawer = {
        visible: true,
        batch,
        studentId: '',
        studentIds: [],
        toStatus: '',
        reason: '',
        attachment: '',
        error: '',
        submitting: false
      }
    },
    toggleStudent(id, checked) {
      const list = this.drawer.studentIds
      this.drawer.studentIds = checked ? [...list, id] : list.filter((x) => x !== id)
    },
    /* 2026-07-10 第二批交互纠偏：学籍状态变更属高风险正式状态，提交前必须二次确认
       （明确操作对象、变更影响、原因回显、不可自动撤销提示），确认后才调用接口 */
    submitChange() {
      const d = this.drawer
      d.error = ''
      if (!d.toStatus) {
        d.error = '请选择目标状态'
        return
      }
      if (String(d.reason).trim().length < 5) {
        d.error = '变更原因必填且不少于 5 个字'
        return
      }
      if (d.batch && !d.studentIds.length) {
        d.error = '请至少勾选一名学生'
        return
      }
      if (!d.batch && !d.studentId) {
        d.error = '请选择学生'
        return
      }
      this.confirmDialog = { visible: true, submitting: false }
    },
    confirmTargetText() {
      const d = this.drawer
      if (d.batch) return `已勾选的 ${d.studentIds.length} 名学生`
      const stu = this.candidates.find((c) => c.studentId === d.studentId)
      return stu ? `${stu.name}（${stu.className}，当前 ${this.statusLabel(stu.studentStatus)}）` : '所选学生'
    },
    goApply() {
      this.$router.push('/admin/academic-affairs/status-changes/new')
    },
    async doSubmitChange() {
      const d = this.drawer
      this.confirmDialog.submitting = true
      d.submitting = true
      let res
      if (d.batch) {
        res = await studentApi.batchChangeStatus(d.studentIds, { toStatus: d.toStatus, reason: d.reason })
      } else {
        res = await studentApi.changeStatus(d.studentId, {
          toStatus: d.toStatus,
          reason: d.reason,
          attachment: d.attachment
        })
      }
      d.submitting = false
      this.confirmDialog.submitting = false
      this.confirmDialog.visible = false
      if (res.code === 0) {
        d.visible = false
        toast.success(
          d.batch
            ? '批量提交完成：成功 ' + res.data.success + ' 条，跳过 ' + res.data.skipped + ' 条（已留痕）'
            : '学籍状态变更已登记并留痕'
        )
        this.load()
        this.loadCandidates()
      } else {
        d.error = res.message
      }
    },
    async submitExport({ reason }) {
      this.exportDialog.submitting = true
      const res = await studentApi.createExport({
        scope: 'FILTERED',
        fieldKeys: ['name', 'studentNo', 'studentStatus'],
        purpose: 'AUDIT',
        remark: reason,
        rowCount: this.pagination.total
      })
      this.exportDialog.submitting = false
      if (res.code === 0) {
        this.exportDialog.visible = false
        toast.success('变更记录导出任务已创建：已脱敏、含水印，审计编号 ' + res.data.auditId)
      } else {
        toast.error(res.message)
      }
    },
    async loadCandidates() {
      const res = await studentApi.getStudents({ page: 1, pageSize: 100 })
      if (res.code === 0) this.candidates = res.data.list.filter((s) => !s.voided)
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await studentApi.getStatusRecords({
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
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

/* 状态流转箭头 */
.ss-arrow {
  margin: 0 var(--space-1);
  color: var(--text-tertiary);
}
.ss-reason {
  max-width: 360px;
  white-space: normal;
}
.ss-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.ss-field__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.ss-field__label--block {
  margin-bottom: var(--space-2);
}
.ss-field__control {
  height: 34px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
}
.ss-field__control:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.ss-stu-list {
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  padding: var(--space-2);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.ss-stu-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-base);
  cursor: pointer;
}
.ss-stu-item:hover {
  background: var(--bg-hover);
}
.ss-drawer-ops {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding-top: var(--space-2);
}
</style>
