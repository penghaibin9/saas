<template>
  <ModulePageShell
    title="成绩复查复审"
    subtitle="学生对已发布成绩发起复查，教务处复审：维持原成绩 / 调整成绩（回写成绩单并通知学生）/ 不予受理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <span class="aa-filter__label">状态</span>
        <AppSelect v-model="status" :options="statusOptions" style="min-width:150px" @change="load" />
        <AppButton variant="ghost" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <AppSectionCard title="复查申请台账">
          <EmptyState v-if="!rows.length" title="暂无复查申请" description="学生在小程序对已发布成绩发起复查后，这里出现待复审记录" />
          <DataTable v-else :columns="columns" :rows="rows" row-key="recheckId">
            <template #cell-newScore="{ row }">{{ row.newScore ?? '—' }}</template>
            <template #cell-reason="{ row }"><span :title="row.reason">{{ row.reason }}</span></template>
            <template #cell-status="{ row }">
              <AppStatusTag :type="statusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
            </template>
            <template #cell-actions="{ row }">
              <button v-if="row.status === 'SUBMITTED'" class="mp-link" @click="openReview(row)">复审</button>
              <span v-else class="aa-note-sm">{{ row.reviewNote || '—' }}</span>
            </template>
          </DataTable>
        </AppSectionCard>

        <AppSectionCard v-if="active" :title="`复审：${active.studentName} · ${active.courseName}（原 ${active.originalScore} 分）`">
          <AppFormItem label="复审结论">
            <AppSelect v-model="form.action" :options="actionOptions" style="min-width:150px" />
          </AppFormItem>
          <AppFormItem v-if="form.action === 'ADJUST'" label="调整后成绩" required>
            <AppTextInput v-model.number="form.newScore" type="number" size="compact" style="max-width:120px" />
          </AppFormItem>
          <AppFormItem :label="form.action === 'REJECT' ? '不予受理原因' : '复审意见'" :required="form.action === 'REJECT'">
            <AppTextarea v-model="form.note" :rows="2"
                         :placeholder="form.action === 'REJECT' ? '不予受理原因（必填，≥5字）' : '复审意见（选填）'" />
          </AppFormItem>
          <div class="aa-actions">
            <AppButton variant="primary" :loading="submitting" @click="doReview">提交复审结果</AppButton>
            <AppButton variant="ghost" @click="active = null">取消</AppButton>
          </div>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 成绩复查复审（/admin/academic-affairs/grade-recheck）：GET /grade-rechecks + POST /grade-rechecks/{id}/review。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppFormItem, AppSelect, AppTextInput, AppTextarea } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const STATUS = { SUBMITTED: '待复审', UPHELD: '已维持原成绩', ADJUSTED: '已调整成绩', REJECTED: '不予受理' }

export default {
  name: 'AaGradeRecheckView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
    AppButton, AppSectionCard, AppStatusTag, AppFormItem, AppSelect, AppTextInput, AppTextarea
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', status: '', rows: [], active: null, submitting: false,
      form: { action: 'UPHOLD', newScore: null, note: '' },
      statusOptions: [
        { label: '全部', value: '' }, { label: '待复审', value: 'SUBMITTED' },
        { label: '已维持', value: 'UPHELD' }, { label: '已调整', value: 'ADJUSTED' },
        { label: '不予受理', value: 'REJECTED' }
      ],
      actionOptions: [
        { label: '维持原成绩', value: 'UPHOLD' }, { label: '调整成绩', value: 'ADJUST' },
        { label: '不予受理', value: 'REJECT' }
      ],
      columns: [
        { key: 'studentName', title: '学生' }, { key: 'studentNo', title: '学号' },
        { key: 'courseName', title: '课程' }, { key: 'term', title: '学期' },
        { key: 'originalScore', title: '原成绩' }, { key: 'newScore', title: '调整后' },
        { key: 'reason', title: '理由' }, { key: 'status', title: '状态' },
        { key: 'actions', title: '操作' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    statusLabel(s) { return STATUS[s] || s },
    statusColor(s) {
      if (s === 'ADJUSTED') return 'success'
      if (s === 'REJECTED') return 'danger'
      if (s === 'SUBMITTED') return 'primary'
      return 'default'
    },
    async load() {
      this.loading = true
      this.error = ''
      this.active = null
      const res = await academicAffairsApi.getGradeRechecks({ status: this.status || undefined, page: 1, pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    openReview(r) {
      this.active = r
      this.form = { action: 'UPHOLD', newScore: r.originalScore, note: '' }
    },
    async doReview() {
      if (this.submitting) return
      if (this.form.action === 'ADJUST' && (this.form.newScore == null || this.form.newScore < 0 || this.form.newScore > 100)) {
        toast.error('调整后成绩须为 0-100')
        return
      }
      if (this.form.action === 'REJECT' && (!this.form.note || this.form.note.trim().length < 5)) {
        toast.error('不予受理原因必填且不少于 5 字')
        return
      }
      this.submitting = true
      const res = await academicAffairsApi.reviewGradeRecheck(this.active.recheckId, {
        action: this.form.action,
        note: this.form.note ? this.form.note.trim() : undefined,
        newScore: this.form.action === 'ADJUST' ? this.form.newScore : undefined
      })
      this.submitting = false
      if (res.code === 0) {
        toast.success('复审结果已提交')
        this.active = null
        this.load()
      } else toast.error(res.message || '提交失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.aa-filter__label { font-size: 13px; color: var(--text-700, #4e5969); }
.aa-note-sm { color: var(--text-500, #646a73); font-size: 12px; }
.aa-actions { margin-top: 12px; display: flex; gap: 12px; }
</style>
