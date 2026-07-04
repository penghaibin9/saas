<template>
  <ModulePageShell
    title="学生主档"
    :subtitle="'共 ' + pagination.total + ' 名学生 · 手机号 / 身份证默认脱敏展示'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="学生主档列表"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <AppGlobalState
      v-if="forbidden"
      state="forbidden"
      title="暂无学生主档访问权限"
      :description="ctx.permissionActions.viewList.reason || '请联系系统管理员开通'"
    />
    <div v-else class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset">
        <template #ops>
          <label class="sl-voided-toggle">
            <input v-model="filters.includeVoided" type="checkbox" @change="search" />
            显示已作废
          </label>
        </template>
      </AdvancedFilter>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length"
        title="没有符合条件的学生"
        description="可调整筛选条件，或确认当前数据范围是否覆盖目标班级"
      />
      <DataTable
        v-else
        :columns="visibleColumns"
        :rows="rows"
        row-key="studentId"
        selectable
        v-model:selected="selected"
        :pagination="pagination"
        row-clickable
        @row-click="goDetail"
        @page-change="onPageChange"
      >
        <template #batch-actions>
          <button
            class="mp-link"
            :class="{ 'is-disabled': !can('batchAssignClass') }"
            :title="reason('batchAssignClass')"
            @click="openBatch('assignClass')"
          >
            批量分班
          </button>
          <button
            class="mp-link"
            :class="{ 'is-disabled': !can('batchAssignCounselor') }"
            :title="reason('batchAssignCounselor')"
            @click="openBatch('assignCounselor')"
          >
            批量分配辅导员
          </button>
          <button
            class="mp-link"
            :class="{ 'is-disabled': !can('batchRemind') }"
            :title="reason('batchRemind')"
            @click="batchRemind"
          >
            批量提醒
          </button>
          <button
            class="mp-link"
            :class="{ 'is-disabled': !can('exportStudents') }"
            :title="reason('exportStudents')"
            @click="exportSelected"
          >
            导出所选
          </button>
        </template>
        <template #cell-student="{ row }">
          <div class="mp-cell-main">
            {{ row.name }}
            <AppStatusTag v-if="row.voided" type="default" label="已作废" />
          </div>
          <div class="mp-cell-sub">{{ row.studentNo }} · {{ row.gender }}</div>
        </template>
        <template #cell-orgPath="{ row }">
          <div class="mp-cell-main">{{ row.className }}</div>
          <div class="mp-cell-sub">{{ row.collegeName }} / {{ row.majorName }}</div>
        </template>
        <template #cell-phone="{ row }">{{ mask(row.phone, 'phone') }}</template>
        <template #cell-idCard="{ row }">{{ mask(row.idCard, 'idCard') }}</template>
        <template #cell-studentStatus="{ row }">
          <AppStatusTag :type="statusTone(row.studentStatus)" :label="statusLabel(row.studentStatus)" dot />
        </template>
        <template #cell-identityVerifyStatus="{ row }">
          <AppStatusTag :type="identityTone(row.identityVerifyStatus)" :label="identityLabel(row.identityVerifyStatus)" />
        </template>
        <template #cell-riskLevel="{ row }">
          <RiskTag v-if="row.riskLevel !== 'NONE'" :level="row.riskLevel" />
          <span v-else class="mp-note">无</span>
        </template>
        <template #cell-dataCompleteness="{ row }">{{ row.dataCompleteness }}%</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row)">学生360</button>
          <button
            class="mp-link sl-gap"
            :class="{ 'is-disabled': !can('editStudent') }"
            :title="reason('editStudent')"
            @click="openEdit(row)"
          >
            编辑
          </button>
          <button
            v-if="ctx.permissionActions.voidStudent.visible"
            class="mp-link sl-gap"
            :class="{ 'is-disabled': !can('voidStudent') || row.voided }"
            :title="row.voided ? '该主档已作废' : reason('voidStudent')"
            @click="openVoid(row)"
          >
            作废
          </button>
        </template>
      </DataTable>

      <p class="mp-note">
        管理动作全部写入审计留痕；作废为逻辑删除，可追溯不可物理清除；导出默认脱敏并附
        「{{ ctx.tenantBrandConfig.watermarkText }}」水印。
      </p>
    </div>

    <!-- 新增 / 编辑学生 -->
    <AppDrawer :visible="editDrawer.visible" :title="editDrawer.isCreate ? '新增学生主档' : '编辑学生信息'" @update:visible="editDrawer.visible = $event">
      <div class="mp-stack">
        <label class="sl-field">
          <span class="sl-field__label">姓名 *</span>
          <input v-model="editDrawer.form.name" class="sl-field__control" placeholder="与身份证一致" />
        </label>
        <label class="sl-field">
          <span class="sl-field__label">学号 *</span>
          <input
            v-model="editDrawer.form.studentNo"
            class="sl-field__control"
            :disabled="!editDrawer.isCreate"
            placeholder="全校唯一"
          />
        </label>
        <label class="sl-field">
          <span class="sl-field__label">性别</span>
          <select v-model="editDrawer.form.gender" class="sl-field__control">
            <option value="男">男</option>
            <option value="女">女</option>
          </select>
        </label>
        <label class="sl-field">
          <span class="sl-field__label">班级 *</span>
          <select v-model="editDrawer.form.classId" class="sl-field__control">
            <option value="">请选择班级</option>
            <option v-for="c in ctx.filterOptions.classes" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </label>
        <label class="sl-field">
          <span class="sl-field__label">手机号</span>
          <input v-model="editDrawer.form.phone" class="sl-field__control" placeholder="学生本人手机号" />
        </label>
        <label class="sl-field">
          <span class="sl-field__label">身份证号</span>
          <input v-model="editDrawer.form.idCard" class="sl-field__control" placeholder="用于实名核验" />
        </label>
        <p v-if="editDrawer.error" class="mp-form-err">{{ editDrawer.error }}</p>
        <div class="sl-drawer-ops">
          <AppButton variant="ghost" @click="editDrawer.visible = false">取消</AppButton>
          <AppButton variant="primary" :disabled="editDrawer.submitting" @click="submitEdit">
            {{ editDrawer.isCreate ? '确认建档' : '保存变更' }}
          </AppButton>
        </div>
        <p class="mp-note">提交后写入审计留痕；新增学生默认「已录取 / 待核验」，进入迎新与身份核验流程。</p>
      </div>
    </AppDrawer>

    <!-- 批量分班 / 分配辅导员 -->
    <AppDrawer :visible="batchDrawer.visible" :title="batchDrawer.mode === 'assignClass' ? '批量分班' : '批量分配辅导员'" @update:visible="batchDrawer.visible = $event">
      <div class="mp-stack">
        <p class="mp-note">已勾选 {{ selected.length }} 名学生，超出当前数据范围的记录将自动跳过。</p>
        <label v-if="batchDrawer.mode === 'assignClass'" class="sl-field">
          <span class="sl-field__label">目标班级 *</span>
          <select v-model="batchDrawer.value" class="sl-field__control">
            <option value="">请选择班级</option>
            <option v-for="c in ctx.filterOptions.classes" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </label>
        <label v-else class="sl-field">
          <span class="sl-field__label">目标辅导员 *</span>
          <select v-model="batchDrawer.value" class="sl-field__control">
            <option value="">请选择辅导员</option>
            <option v-for="c in ctx.filterOptions.counselors" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </label>
        <p v-if="batchDrawer.error" class="mp-form-err">{{ batchDrawer.error }}</p>
        <div class="sl-drawer-ops">
          <AppButton variant="ghost" @click="batchDrawer.visible = false">取消</AppButton>
          <AppButton variant="primary" :disabled="batchDrawer.submitting" @click="submitBatch">确认执行</AppButton>
        </div>
      </div>
    </AppDrawer>

    <!-- 列设置 -->
    <AppDrawer :visible="columnDrawer.visible" title="表格列设置" @update:visible="columnDrawer.visible = $event">
      <div class="mp-stack">
        <p class="mp-note">固定列不可取消；身份证号列建议仅在必要时开启（展示仍为脱敏值）。</p>
        <label v-for="c in columnDrawer.draft" :key="c.key" class="sl-col-item" :class="{ 'is-locked': c.locked }">
          <input type="checkbox" :checked="c.visible" :disabled="c.locked" @change="c.visible = $event.target.checked" />
          <span>{{ c.title }}</span>
          <span v-if="c.locked" class="mp-note">固定列</span>
        </label>
        <div class="sl-drawer-ops">
          <AppButton variant="ghost" @click="columnDrawer.visible = false">取消</AppButton>
          <AppButton variant="primary" @click="saveColumns">保存列设置</AppButton>
        </div>
      </div>
    </AppDrawer>

    <!-- 作废确认 -->
    <AppConfirmDialog
      :visible="voidDialog.visible"
      type="danger"
      title="作废学生主档"
      :message="voidDialog.target ? '确认作废 ' + voidDialog.target.name + '（' + voidDialog.target.studentNo + '）的主档？作废为逻辑删除，档案保留可追溯。' : ''"
      confirm-text="确认作废"
      require-reason
      reason-label="作废原因"
      reason-placeholder="不少于 5 个字，将写入审计留痕"
      :submitting="voidDialog.submitting"
      @update:visible="voidDialog.visible = $event"
      @confirm="submitVoid"
    />

    <!-- 导出所选确认 -->
    <AppConfirmDialog
      :visible="exportDialog.visible"
      type="warning"
      title="导出所选学生"
      :message="'将导出 ' + selected.length + ' 条学生记录：敏感字段自动脱敏，文件附水印，本次导出写入审计日志。'"
      confirm-text="确认导出"
      require-reason
      reason-label="导出用途"
      reason-placeholder="如：学院例会名单核对（不少于 5 个字）"
      :submitting="exportDialog.submitting"
      @update:visible="exportDialog.visible = $event"
      @confirm="submitExport"
    />
  </ModulePageShell>
</template>

<script>
/** 学生主档列表（/admin/student/list）：增删查改 + 批量 + 导入导出入口 + 列设置 + 权限按钮 + 脱敏。 */
import {
  ModulePageShell,
  ModuleToolbar,
  AdvancedFilter,
  DataTable,
  StatusTag as AppStatusTag,
  RiskTag,
  LoadingState,
  ErrorState,
  EmptyState
} from '@/components/business'
import { AppGlobalState, AppConfirmDialog } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { studentApi } from '@/modules/student/api/student.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({
  keyword: '',
  collegeId: '',
  majorId: '',
  classId: '',
  grade: '',
  studentStatus: '',
  identityVerifyStatus: '',
  riskLevel: '',
  includeVoided: false
})

const EMPTY_FORM = () => ({ name: '', studentNo: '', gender: '男', classId: '', phone: '', idCard: '' })

export default {
  name: 'StudentListView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    AppStatusTag,
    RiskTag,
    LoadingState,
    ErrorState,
    EmptyState,
    AppGlobalState,
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
      selected: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [],
      editDrawer: { visible: false, isCreate: true, form: EMPTY_FORM(), targetId: '', error: '', submitting: false },
      batchDrawer: { visible: false, mode: 'assignClass', value: '', error: '', submitting: false },
      columnDrawer: { visible: false, draft: [] },
      voidDialog: { visible: false, target: null, submitting: false },
      exportDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    forbidden() {
      const pa = this.ctx.permissionActions.viewList
      return !pa || !pa.visible || !pa.allowed
    },
    filterFields() {
      const o = this.ctx.filterOptions
      const s = this.ctx.statusOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 学号 / 手机号' },
        { key: 'collegeId', label: '学院', type: 'select', options: o.colleges },
        { key: 'classId', label: '班级', type: 'select', options: o.classes },
        { key: 'grade', label: '年级', type: 'select', options: o.grades },
        { key: 'studentStatus', label: '学籍状态', type: 'select', options: s.studentStatus },
        { key: 'identityVerifyStatus', label: '身份核验', type: 'select', options: s.identityVerifyStatus },
        { key: 'riskLevel', label: '风险等级', type: 'select', options: s.riskLevel }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'create', label: '＋ 新增学生', variant: 'primary', perm: 'createStudent' },
        { key: 'import', label: '批量导入', perm: 'importStudents' },
        { key: 'export', label: '批量导出', perm: 'exportStudents' },
        { key: 'columns', label: '列设置', perm: 'columnSettings' }
      ]
        .filter((a) => pa[a.perm] && pa[a.perm].visible)
        .map((a) => ({ ...a, disabled: !pa[a.perm].allowed, disabledReason: pa[a.perm].reason }))
    },
    visibleColumns() {
      return this.columns
        .filter((c) => c.visible)
        .map((c) => ({ key: c.key, title: c.title, width: c.key === 'actions' ? '170px' : undefined }))
    }
  },
  async created() {
    const colRes = await studentApi.getFieldColumns('studentList')
    if (colRes.code === 0) this.columns = colRes.data
    if (!this.forbidden) await this.load()
    else this.loading = false
    if (this.$route.query.action === 'create' && this.can('createStudent')) this.openCreate()
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
    mask(v, type) {
      if (!v) return '未登记'
      if (this.can('viewSensitive')) return v
      if (type === 'phone') return v.slice(0, 3) + '****' + v.slice(-4)
      return v.slice(0, 6) + '********' + v.slice(-4)
    },
    statusLabel(v) {
      const hit = this.ctx.statusOptions.studentStatus.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    statusTone(v) {
      return { ADMITTED: 'processing', ACTIVE: 'success', SUSPENDED: 'warning', GRADUATED: 'info', DROPPED: 'default', VOIDED: 'default' }[v] || 'default'
    },
    identityLabel(v) {
      const hit = this.ctx.statusOptions.identityVerifyStatus.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    identityTone(v) {
      return { VERIFIED: 'success', PENDING: 'warning', REJECTED: 'danger', ABNORMAL: 'danger' }[v] || 'default'
    },
    goDetail(row) {
      this.$router.push('/admin/student/' + row.studentId)
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
      if (key === 'create') this.openCreate()
      if (key === 'import') this.$router.push('/admin/student/import-export')
      if (key === 'export') this.$router.push('/admin/student/import-export?tab=export')
      if (key === 'columns') this.openColumns()
    },
    /* ---- 新增 / 编辑 ---- */
    openCreate() {
      this.editDrawer = { visible: true, isCreate: true, form: EMPTY_FORM(), targetId: '', error: '', submitting: false }
    },
    openEdit(row) {
      if (!this.can('editStudent')) return
      this.editDrawer = {
        visible: true,
        isCreate: false,
        targetId: row.studentId,
        error: '',
        submitting: false,
        form: {
          name: row.name,
          studentNo: row.studentNo,
          gender: row.gender,
          classId: row.classId,
          phone: row.phone,
          idCard: row.idCard
        }
      }
    },
    async submitEdit() {
      const d = this.editDrawer
      d.submitting = true
      d.error = ''
      const res = d.isCreate
        ? await studentApi.createStudent(d.form)
        : await studentApi.updateStudent(d.targetId, d.form)
      d.submitting = false
      if (res.code === 0) {
        d.visible = false
        toast.success(d.isCreate ? '建档成功，已进入待核验队列（已留痕）' : '学生信息已更新（已留痕）')
        this.load()
      } else {
        d.error = res.message
      }
    },
    /* ---- 作废 ---- */
    openVoid(row) {
      if (!this.can('voidStudent') || row.voided) return
      this.voidDialog = { visible: true, target: row, submitting: false }
    },
    async submitVoid({ reason }) {
      const d = this.voidDialog
      d.submitting = true
      const res = await studentApi.voidStudent(d.target.studentId, { reason })
      d.submitting = false
      if (res.code === 0) {
        d.visible = false
        toast.success('主档已作废（逻辑删除，已留痕）')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    /* ---- 批量 ---- */
    openBatch(mode) {
      const perm = mode === 'assignClass' ? 'batchAssignClass' : 'batchAssignCounselor'
      if (!this.can(perm)) return
      this.batchDrawer = { visible: true, mode, value: '', error: '', submitting: false }
    },
    async submitBatch() {
      const d = this.batchDrawer
      if (!d.value) {
        d.error = d.mode === 'assignClass' ? '请选择目标班级' : '请选择目标辅导员'
        return
      }
      d.submitting = true
      const res =
        d.mode === 'assignClass'
          ? await studentApi.batchAssignClass(this.selected, d.value)
          : await studentApi.batchAssignCounselor(this.selected, d.value)
      d.submitting = false
      if (res.code === 0) {
        d.visible = false
        toast.success(
          d.mode === 'assignClass'
            ? '已将 ' + res.data.count + ' 名学生调整至 ' + res.data.className + '（已留痕）'
            : '已为 ' + res.data.count + ' 名学生分配辅导员 ' + res.data.counselorName + '（已留痕）'
        )
        this.selected = []
        this.load()
      } else {
        d.error = res.message
      }
    },
    async batchRemind() {
      if (!this.can('batchRemind')) return
      const res = await studentApi.batchRemind(this.selected)
      if (res.code === 0) {
        toast.success('已向 ' + res.data.count + ' 名学生发送提醒（站内信 + 小程序，已留痕）')
        this.selected = []
      } else {
        toast.error(res.message)
      }
    },
    /* ---- 导出所选 ---- */
    exportSelected() {
      if (!this.can('exportStudents') || !this.selected.length) return
      this.exportDialog = { visible: true, submitting: false }
    },
    async submitExport({ reason }) {
      this.exportDialog.submitting = true
      const res = await studentApi.createExport({
        scope: 'SELECTED',
        fieldKeys: ['name', 'studentNo', 'orgPath', 'studentStatus'],
        purpose: 'WORK',
        remark: reason,
        rowCount: this.selected.length
      })
      this.exportDialog.submitting = false
      if (res.code === 0) {
        this.exportDialog.visible = false
        toast.success('导出任务已创建：已脱敏、含水印，审计编号 ' + res.data.auditId)
        this.selected = []
      } else {
        toast.error(res.message)
      }
    },
    /* ---- 列设置 ---- */
    openColumns() {
      if (!this.can('columnSettings')) return
      this.columnDrawer = { visible: true, draft: JSON.parse(JSON.stringify(this.columns)) }
    },
    async saveColumns() {
      const res = await studentApi.saveFieldColumns('studentList', this.columnDrawer.draft)
      if (res.code === 0) {
        this.columns = res.data
        this.columnDrawer.visible = false
        toast.success('列设置已保存（已留痕）')
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await studentApi.getStudents({
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

/* 操作列按钮间距 */
.sl-gap {
  margin-left: var(--space-2);
}
.sl-voided-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
  cursor: pointer;
}
.sl-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.sl-field__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.sl-field__control {
  height: 34px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
}
.sl-field__control:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.sl-field__control:disabled {
  background: var(--bg-section-blue);
  color: var(--text-tertiary);
}
.sl-drawer-ops {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding-top: var(--space-2);
}
.sl-col-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.sl-col-item.is-locked {
  background: var(--bg-section-blue);
  cursor: not-allowed;
}
</style>
