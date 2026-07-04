<template>
  <ModulePageShell
    title="身份核验记录"
    :subtitle="'共 ' + pagination.total + ' 条核验记录 · 复核 / 退回 / 标记异常全程留痕'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="身份核验管理"
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
        title="暂无符合条件的核验记录"
        description="可调整筛选条件后重新查询"
      />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-result="{ row }">
          <AppStatusTag :type="resultTone(row.result)" :label="resultLabel(row.result)" />
          <span v-if="row.similarity" class="mp-cell-sub si-sim">相似度 {{ row.similarity }}</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot />
        </template>
        <template #cell-review="{ row }">
          <template v-if="row.reviewer">
            <div class="mp-cell-main">{{ row.reviewer }}</div>
            <div class="mp-cell-sub si-comment">{{ row.reviewComment || '—' }}</div>
          </template>
          <span v-else class="mp-note">{{ row.reviewComment || '待人工处理' }}</span>
        </template>
        <template #cell-actions="{ row }">
          <button
            v-if="row.status === 'PENDING_REVIEW'"
            class="mp-link"
            :class="{ 'is-disabled': !can('reviewIdentity') }"
            :title="reason('reviewIdentity')"
            @click="openReview(row)"
          >
            人工复核
          </button>
          <button
            v-if="row.status !== 'ABNORMAL'"
            class="mp-link si-gap"
            :class="{ 'is-disabled': !can('markIdentityAbnormal') }"
            :title="reason('markIdentityAbnormal')"
            @click="openAbnormal(row)"
          >
            标记异常
          </button>
          <button class="mp-link si-gap" @click="$router.push('/admin/student/' + row.studentId)">学生360</button>
        </template>
      </DataTable>

      <p class="mp-note">核验结论直接回写学生主档身份状态；异常记录将同步生成「身份异常」风险标签建议。</p>
    </div>

    <!-- 人工复核 -->
    <AppDrawer :visible="reviewDrawer.visible" title="人工复核" @update:visible="reviewDrawer.visible = $event">
      <div v-if="reviewDrawer.target" class="mp-stack">
        <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ reviewDrawer.target.studentName }}（{{ reviewDrawer.target.className }}）</span></div>
        <div class="mp-kv"><span class="mp-kv__k">核验方式</span><span class="mp-kv__v">{{ reviewDrawer.target.method }}</span></div>
        <div class="mp-kv"><span class="mp-kv__k">机器结论</span><span class="mp-kv__v">{{ resultLabel(reviewDrawer.target.result) }}<template v-if="reviewDrawer.target.similarity">（{{ reviewDrawer.target.similarity }}）</template></span></div>
        <div class="mp-kv"><span class="mp-kv__k">核验时间</span><span class="mp-kv__v">{{ reviewDrawer.target.checkedAt }}</span></div>

        <label class="mp-radio" :class="{ 'is-active': reviewDrawer.action === 'CONFIRM' }">
          <input v-model="reviewDrawer.action" type="radio" value="CONFIRM" />
          <span>
            <span class="mp-radio__title">复核通过</span>
            <span class="mp-radio__desc">确认身份真实有效，主档核验状态更新为「已核验」</span>
          </span>
        </label>
        <label class="mp-radio" :class="{ 'is-active': reviewDrawer.action === 'RETURN' }">
          <input v-model="reviewDrawer.action" type="radio" value="RETURN" />
          <span>
            <span class="mp-radio__title">退回重验</span>
            <span class="mp-radio__desc">材料不足或比对存疑，退回学生端重新提交（原因必填）</span>
          </span>
        </label>

        <label class="si-field">
          <span class="si-field__label">{{ reviewDrawer.action === 'RETURN' ? '退回原因 *（≥5 字）' : '复核意见（选填）' }}</span>
          <textarea v-model="reviewDrawer.comment" class="mp-textarea" placeholder="将写入核验记录与审计留痕" />
        </label>

        <p v-if="reviewDrawer.error" class="mp-form-err">{{ reviewDrawer.error }}</p>
        <div class="si-drawer-ops">
          <AppButton variant="ghost" @click="reviewDrawer.visible = false">取消</AppButton>
          <AppButton variant="primary" :disabled="reviewDrawer.submitting" @click="submitReview">
            {{ reviewDrawer.action === 'RETURN' ? '确认退回' : '确认通过' }}
          </AppButton>
        </div>
      </div>
    </AppDrawer>

    <!-- 标记异常 -->
    <AppConfirmDialog
      :visible="abnormalDialog.visible"
      type="danger"
      title="标记核验异常"
      :message="abnormalDialog.target ? '确认将 ' + abnormalDialog.target.studentName + ' 的本条核验记录标记为异常？主档身份状态将同步为「核验异常」。' : ''"
      confirm-text="确认标记异常"
      require-reason
      reason-label="异常说明"
      reason-placeholder="如：证件照片存在明显 PS 痕迹（不少于 5 个字）"
      :submitting="abnormalDialog.submitting"
      @update:visible="abnormalDialog.visible = $event"
      @confirm="submitAbnormal"
    />

    <!-- 导出核验记录 -->
    <AppConfirmDialog
      :visible="exportDialog.visible"
      type="warning"
      title="导出核验记录"
      :message="'将导出当前筛选范围内 ' + pagination.total + ' 条核验记录：证件号自动脱敏、文件附水印、写入审计日志。'"
      confirm-text="确认导出"
      require-reason
      reason-label="导出用途"
      reason-placeholder="如：实名核验专项检查（不少于 5 个字）"
      :submitting="exportDialog.submitting"
      @update:visible="exportDialog.visible = $event"
      @confirm="submitExport"
    />
  </ModulePageShell>
</template>

<script>
/** 身份核验记录（/admin/student/identity）：人工复核 / 退回重验 / 标记异常 / 导出留痕。 */
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

const EMPTY_FILTERS = () => ({ keyword: '', status: '', result: '' })

export default {
  name: 'StudentIdentityView',
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
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'student', title: '学生' },
        { key: 'method', title: '核验方式' },
        { key: 'result', title: '机器结论' },
        { key: 'checkedAt', title: '核验时间', width: '150px' },
        { key: 'status', title: '处理状态' },
        { key: 'review', title: '复核人 / 意见' },
        { key: 'actions', title: '操作', width: '210px' }
      ],
      reviewDrawer: { visible: false, target: null, action: 'CONFIRM', comment: '', error: '', submitting: false },
      abnormalDialog: { visible: false, target: null, submitting: false },
      exportDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    filterFields() {
      const s = this.ctx.statusOptions
      return [
        { key: 'keyword', label: '学生姓名', type: 'text', placeholder: '按姓名搜索' },
        { key: 'status', label: '处理状态', type: 'select', options: s.identityRecordStatus },
        { key: 'result', label: '机器结论', type: 'select', options: s.identityResult }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'export', label: '导出核验记录', perm: 'exportIdentityRecords' }]
        .filter((a) => pa[a.perm] && pa[a.perm].visible)
        .map((a) => ({ ...a, disabled: !pa[a.perm].allowed, disabledReason: pa[a.perm].reason }))
    }
  },
  created() {
    this.load()
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
    resultLabel(v) {
      const hit = this.ctx.statusOptions.identityResult.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    resultTone(v) {
      return { PASS: 'success', FAIL: 'danger', PENDING: 'warning' }[v] || 'default'
    },
    statusLabel(v) {
      const hit = this.ctx.statusOptions.identityRecordStatus.find((o) => o.value === v)
      return hit ? hit.label : v
    },
    statusTone(v) {
      return { PENDING_REVIEW: 'warning', CONFIRMED: 'success', ABNORMAL: 'danger' }[v] || 'default'
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
      if (key === 'export') this.exportDialog = { visible: true, submitting: false }
    },
    openReview(row) {
      if (!this.can('reviewIdentity')) return
      this.reviewDrawer = { visible: true, target: row, action: 'CONFIRM', comment: '', error: '', submitting: false }
    },
    async submitReview() {
      const d = this.reviewDrawer
      d.error = ''
      if (d.action === 'RETURN' && String(d.comment).trim().length < 5) {
        d.error = '退回原因必填且不少于 5 个字'
        return
      }
      d.submitting = true
      const res = await studentApi.reviewIdentityRecord(d.target.id, { action: d.action, comment: d.comment })
      d.submitting = false
      if (res.code === 0) {
        d.visible = false
        toast.success(d.action === 'CONFIRM' ? '复核通过，主档身份状态已更新（已留痕）' : '已退回重验并通知学生（已留痕）')
        this.load()
      } else {
        d.error = res.message
      }
    },
    openAbnormal(row) {
      if (!this.can('markIdentityAbnormal')) return
      this.abnormalDialog = { visible: true, target: row, submitting: false }
    },
    async submitAbnormal({ reason }) {
      const d = this.abnormalDialog
      d.submitting = true
      const res = await studentApi.markIdentityAbnormal(d.target.id, { reason })
      d.submitting = false
      if (res.code === 0) {
        d.visible = false
        toast.success('已标记异常并同步主档（已留痕）')
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async submitExport({ reason }) {
      this.exportDialog.submitting = true
      const res = await studentApi.createExport({
        scope: 'FILTERED',
        fieldKeys: ['name', 'studentNo', 'identityVerifyStatus'],
        purpose: 'AUDIT',
        remark: reason,
        rowCount: this.pagination.total
      })
      this.exportDialog.submitting = false
      if (res.code === 0) {
        this.exportDialog.visible = false
        toast.success('核验记录导出任务已创建：已脱敏、含水印，审计编号 ' + res.data.auditId)
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await studentApi.getIdentityRecords({
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
.si-gap {
  margin-left: var(--space-2);
}
.si-sim {
  display: block;
  margin-top: 2px;
}
.si-comment {
  max-width: 260px;
  white-space: normal;
}
.si-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.si-field__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.si-drawer-ops {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding-top: var(--space-2);
}
</style>
