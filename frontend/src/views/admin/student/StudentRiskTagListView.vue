<template>
  <ModulePageShell
    title="学生风险标签"
    :subtitle="'共 ' + pagination.total + ' 条标签 · 新增 / 跟进 / 作废全程留痕'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="学生风险标签"
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
        title="暂无风险标签"
        description="系统预警会自动生成标签，也可点击右上角「新增风险标签」人工建档"
      />
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
          <button
            class="mp-link"
            :class="{ 'is-disabled': !can('batchRemindRisk') }"
            :title="reason('batchRemindRisk')"
            @click="batchRemind"
          >
            批量提醒责任人
          </button>
        </template>
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-tag="{ row }">
          <div class="mp-cell-main">{{ row.title }}</div>
          <div class="mp-cell-sub">{{ row.tagTypeLabel }} · {{ row.sourceLabel }}</div>
        </template>
        <template #cell-level="{ row }">
          <RiskTag :level="row.level" />
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot />
        </template>
        <template #cell-follow="{ row }">
          <template v-if="row.followUps.length">
            <div class="mp-cell-sub rt-follow">{{ row.followUps[0].note }}</div>
            <div class="mp-cell-sub">{{ row.followUps[0].time }} · {{ row.followUps[0].who }}</div>
          </template>
          <span v-else class="mp-note">暂无跟进</span>
        </template>
        <template #cell-actions="{ row }">
          <button
            class="mp-link"
            :class="{ 'is-disabled': !can('followRiskTag') || isFinal(row) }"
            :title="isFinal(row) ? '已解除 / 已作废标签无需跟进' : reason('followRiskTag')"
            @click="openFollow(row)"
          >
            跟进
          </button>
          <button
            class="mp-link rt-gap"
            :class="{ 'is-disabled': !can('editRiskTag') || row.status === 'VOIDED' }"
            :title="row.status === 'VOIDED' ? '已作废标签不可编辑' : reason('editRiskTag')"
            @click="openEdit(row)"
          >
            编辑
          </button>
          <button
            v-if="ctx.permissionActions.voidRiskTag.visible"
            class="mp-link rt-gap"
            :class="{ 'is-disabled': !can('voidRiskTag') || row.status === 'VOIDED' }"
            :title="row.status === 'VOIDED' ? '该标签已作废' : reason('voidRiskTag')"
            @click="openVoid(row)"
          >
            作废
          </button>
        </template>
      </DataTable>

      <p class="mp-note">
        作废为逻辑删除且原因必填；风险等级变化会同步学生主档风险标识；导出名单默认脱敏并附水印。
      </p>
    </div>

    <!-- 新增 / 编辑标签 -->
    <AppDrawer :visible="editDrawer.visible" :title="editDrawer.isCreate ? '新增风险标签' : '编辑风险标签'" @update:visible="editDrawer.visible = $event">
      <div class="mp-stack">
        <label v-if="editDrawer.isCreate" class="rt-field">
          <span class="rt-field__label">学生 *</span>
          <select v-model="editDrawer.form.studentId" class="rt-field__control">
            <option value="">请选择学生</option>
            <option v-for="s in candidates" :key="s.studentId" :value="s.studentId">
              {{ s.name }} · {{ s.className }}
            </option>
          </select>
        </label>
        <label class="rt-field">
          <span class="rt-field__label">风险类型 *</span>
          <select v-model="editDrawer.form.tagType" class="rt-field__control" :disabled="!editDrawer.isCreate">
            <option value="">请选择类型</option>
            <option v-for="t in ctx.statusOptions.riskTagType" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </label>
        <div>
          <div class="rt-field__label rt-field__label--block">风险等级 *</div>
          <label
            v-for="l in ctx.statusOptions.riskLevel"
            :key="l.value"
            class="mp-radio"
            :class="{ 'is-active': editDrawer.form.level === l.value }"
          >
            <input v-model="editDrawer.form.level" type="radio" :value="l.value" />
            <span><span class="mp-radio__title">{{ l.label }}</span></span>
          </label>
        </div>
        <label class="rt-field">
          <span class="rt-field__label">标签标题 *（≥4 字）</span>
          <input v-model="editDrawer.form.title" class="rt-field__control" placeholder="如：连续缺勤待家访核实" />
        </label>
        <label class="rt-field">
          <span class="rt-field__label">说明</span>
          <textarea v-model="editDrawer.form.description" class="mp-textarea" placeholder="风险来源、影响与建议措施" />
        </label>
        <p v-if="editDrawer.error" class="mp-form-err">{{ editDrawer.error }}</p>
        <div class="rt-drawer-ops">
          <AppButton variant="ghost" @click="editDrawer.visible = false">取消</AppButton>
          <AppButton variant="primary" :disabled="editDrawer.submitting" @click="submitEdit">
            {{ editDrawer.isCreate ? '确认建档' : '保存变更' }}
          </AppButton>
        </div>
      </div>
    </AppDrawer>

    <!-- 跟进 -->
    <AppDrawer :visible="followDrawer.visible" title="风险跟进" @update:visible="followDrawer.visible = $event">
      <div v-if="followDrawer.target" class="mp-stack">
        <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ followDrawer.target.studentName }}（{{ followDrawer.target.className }}）</span></div>
        <div class="mp-kv"><span class="mp-kv__k">标签</span><span class="mp-kv__v">{{ followDrawer.target.title }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">责任人</span><span class="mp-kv__v">{{ followDrawer.target.owner }}</span></div>

        <label class="rt-field">
          <span class="rt-field__label">跟进记录 *（≥5 字）</span>
          <textarea v-model="followDrawer.note" class="mp-textarea" placeholder="如：已与家长电话沟通，约定下周三家访" />
        </label>
        <p v-if="followDrawer.error" class="mp-form-err">{{ followDrawer.error }}</p>
        <div class="rt-drawer-ops">
          <AppButton variant="ghost" @click="followDrawer.visible = false">取消</AppButton>
          <AppButton variant="primary" :disabled="followDrawer.submitting" @click="submitFollow">提交跟进</AppButton>
        </div>

        <template v-if="followDrawer.target.followUps.length">
          <div class="rt-field__label rt-field__label--block">历史跟进</div>
          <ul class="mp-timeline">
            <li v-for="f in followDrawer.target.followUps" :key="f.time" class="mp-timeline__item">
              <div class="mp-timeline__desc">{{ f.note }}</div>
              <div class="mp-timeline__time">{{ f.time }} · {{ f.who }}</div>
            </li>
          </ul>
        </template>
      </div>
    </AppDrawer>

    <!-- 作废确认 -->
    <AppConfirmDialog
      :visible="voidDialog.visible"
      type="danger"
      title="作废风险标签"
      :message="voidDialog.target ? '确认作废「' + voidDialog.target.title + '」？作废为逻辑删除，历史跟进记录保留可追溯。' : ''"
      confirm-text="确认作废"
      require-reason
      reason-label="作废原因"
      reason-placeholder="如：系统误报，经两次面谈确认无风险（不少于 5 个字）"
      :submitting="voidDialog.submitting"
      @update:visible="voidDialog.visible = $event"
      @confirm="submitVoid"
    />

    <!-- 导出风险名单 -->
    <AppConfirmDialog
      :visible="exportDialog.visible"
      type="warning"
      title="导出风险名单"
      :message="'将导出当前筛选范围内 ' + pagination.total + ' 条风险标签：学生敏感信息脱敏、文件附水印、写入审计日志。'"
      confirm-text="确认导出"
      require-reason
      reason-label="导出用途"
      reason-placeholder="如：学工例会风险通报（不少于 5 个字）"
      :submitting="exportDialog.submitting"
      @update:visible="exportDialog.visible = $event"
      @confirm="submitExport"
    />
  </ModulePageShell>
</template>

<script>
/** 学生风险标签（/admin/student/risk-tags）：新增 / 编辑 / 跟进 / 作废 / 批量提醒 / 导出。 */
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
import { AppConfirmDialog } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { studentApi } from '@/modules/student/api/student.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', tagType: '', level: '', status: '' })
const EMPTY_FORM = () => ({ studentId: '', tagType: '', level: 'LOW', title: '', description: '' })

export default {
  name: 'StudentRiskTagListView',
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
      candidates: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'student', title: '学生' },
        { key: 'tag', title: '风险标签' },
        { key: 'level', title: '等级' },
        { key: 'status', title: '状态' },
        { key: 'owner', title: '责任人' },
        { key: 'follow', title: '最近跟进' },
        { key: 'createdAt', title: '创建时间', width: '150px' },
        { key: 'actions', title: '操作', width: '170px' }
      ],
      editDrawer: { visible: false, isCreate: true, targetId: '', form: EMPTY_FORM(), error: '', submitting: false },
      followDrawer: { visible: false, target: null, note: '', error: '', submitting: false },
      voidDialog: { visible: false, target: null, submitting: false },
      exportDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    filterFields() {
      const s = this.ctx.statusOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 标签标题' },
        { key: 'tagType', label: '风险类型', type: 'select', options: s.riskTagType },
        { key: 'level', label: '风险等级', type: 'select', options: s.riskLevel },
        { key: 'status', label: '标签状态', type: 'select', options: s.riskTagStatus }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'create', label: '＋ 新增风险标签', variant: 'primary', perm: 'createRiskTag' },
        { key: 'export', label: '导出风险名单', perm: 'exportRiskList' }
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
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    isFinal(row) {
      return row.status === 'RESOLVED' || row.status === 'VOIDED'
    },
    statusLabel(v) {
      const hit = this.ctx.statusOptions.riskTagStatus.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    statusTone(v) {
      return { ACTIVE: 'warning', FOLLOWING: 'processing', RESOLVED: 'success', VOIDED: 'default' }[v] || 'default'
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
      if (key === 'create') {
        this.editDrawer = { visible: true, isCreate: true, targetId: '', form: EMPTY_FORM(), error: '', submitting: false }
      }
      if (key === 'export') this.exportDialog = { visible: true, submitting: false }
    },
    openEdit(row) {
      if (!this.can('editRiskTag') || row.status === 'VOIDED') return
      this.editDrawer = {
        visible: true,
        isCreate: false,
        targetId: row.id,
        error: '',
        submitting: false,
        form: {
          studentId: row.studentId,
          tagType: row.tagType,
          level: row.level,
          title: row.title,
          description: row.description
        }
      }
    },
    async submitEdit() {
      const d = this.editDrawer
      d.error = ''
      d.submitting = true
      const res = d.isCreate
        ? await studentApi.createRiskTag(d.form)
        : await studentApi.updateRiskTag(d.targetId, {
            title: d.form.title,
            description: d.form.description,
            level: d.form.level
          })
      d.submitting = false
      if (res.code === 0) {
        d.visible = false
        toast.success(d.isCreate ? '风险标签已建档并通知责任人（已留痕）' : '风险标签已更新（已留痕）')
        this.load()
      } else {
        d.error = res.message
      }
    },
    openFollow(row) {
      if (!this.can('followRiskTag') || this.isFinal(row)) return
      this.followDrawer = { visible: true, target: row, note: '', error: '', submitting: false }
    },
    async submitFollow() {
      const d = this.followDrawer
      d.error = ''
      if (String(d.note).trim().length < 5) {
        d.error = '跟进记录必填且不少于 5 个字'
        return
      }
      d.submitting = true
      const res = await studentApi.addRiskFollowUp(d.target.id, { note: d.note })
      d.submitting = false
      if (res.code === 0) {
        d.visible = false
        toast.success('跟进记录已提交（已留痕）')
        this.load()
      } else {
        d.error = res.message
      }
    },
    openVoid(row) {
      if (!this.can('voidRiskTag') || row.status === 'VOIDED') return
      this.voidDialog = { visible: true, target: row, submitting: false }
    },
    async submitVoid({ reason }) {
      const d = this.voidDialog
      d.submitting = true
      const res = await studentApi.voidRiskTag(d.target.id, { reason })
      d.submitting = false
      if (res.code === 0) {
        d.visible = false
        toast.success('风险标签已作废（逻辑删除，已留痕）')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async batchRemind() {
      if (!this.can('batchRemindRisk') || !this.selected.length) return
      const res = await studentApi.batchRemindRisk(this.selected)
      if (res.code === 0) {
        toast.success('已向 ' + res.data.count + ' 条标签的责任人与学生发送提醒（已留痕）')
        this.selected = []
      } else {
        toast.error(res.message)
      }
    },
    async submitExport({ reason }) {
      this.exportDialog.submitting = true
      const res = await studentApi.createExport({
        scope: 'FILTERED',
        fieldKeys: ['name', 'studentNo', 'riskLevel'],
        purpose: 'WORK',
        remark: reason,
        rowCount: this.pagination.total
      })
      this.exportDialog.submitting = false
      if (res.code === 0) {
        this.exportDialog.visible = false
        toast.success('风险名单导出任务已创建：已脱敏、含水印，审计编号 ' + res.data.auditId)
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
      const res = await studentApi.getRiskTags({
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

.rt-gap {
  margin-left: var(--space-2);
}
.rt-follow {
  max-width: 240px;
  white-space: normal;
}
.rt-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.rt-field__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.rt-field__label--block {
  margin-bottom: var(--space-2);
}
.rt-field__control {
  height: 34px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
}
.rt-field__control:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.rt-field__control:disabled {
  background: var(--bg-section-blue);
  color: var(--text-tertiary);
}
.rt-drawer-ops {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding-top: var(--space-2);
}
</style>
