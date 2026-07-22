<template>
  <ModulePageShell
    title="工作量申报审核"
    subtitle="教师在移动端申报教学/监考/阅卷/出卷工作量，教务处在此审核；通过后计入教师工作量统计（仅供教务参考，非薪酬核算）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <span class="aa-filter__label">状态</span>
        <AppSelect v-model="status" :options="statusOptions" style="min-width:140px" @change="load" />
        <span class="aa-filter__label">学期</span>
        <AppTermCodePicker v-model="termCode" placeholder="全部学期" style="max-width:220px" />
        <AppButton variant="ghost" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <AppSectionCard title="工作量申报台账">
          <EmptyState v-if="!rows.length" title="暂无申报" description="教师在移动端提交工作量申报后，这里出现待审核记录" />
          <DataTable v-else :columns="columns" :rows="rows" row-key="declarationId">
            <template #cell-teacher="{ row }">{{ row.teacherName || row.teacherKey }}</template>
            <template #cell-termCode="{ row }">{{ row.termCode || '—' }}</template>
            <template #cell-description="{ row }"><span :title="row.description">{{ row.description || '—' }}</span></template>
            <template #cell-status="{ row }">
              <AppStatusTag :type="statusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
            </template>
            <template #cell-actions="{ row }">
              <template v-if="row.status === 'SUBMITTED'">
                <button class="mp-link" @click="approve(row)">通过</button>
                <button class="mp-link mp-link--danger" @click="openReject(row)">驳回</button>
              </template>
              <span v-else class="aa-note-sm">{{ row.reviewNote || '—' }}</span>
            </template>
          </DataTable>
        </AppSectionCard>

        <AppSectionCard v-if="rejecting" :title="`驳回：${rejecting.teacherName || rejecting.teacherKey} · ${rejecting.categoryLabel} ${rejecting.hours}课时`">
          <AppFormItem label="驳回原因" required>
            <AppTextarea v-model="rejectNote" :rows="2" placeholder="驳回原因（必填，≥5字）" />
          </AppFormItem>
          <div class="aa-actions">
            <AppButton variant="primary" :loading="submitting" @click="doReject">确认驳回</AppButton>
            <AppButton variant="ghost" @click="rejecting = null">取消</AppButton>
          </div>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 工作量申报审核（/admin/academic-affairs/workload-review）：GET /workload-declarations + review。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppFormItem, AppSelect, AppTextarea, AppTermCodePicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const STATUS = { SUBMITTED: '待审核', APPROVED: '已通过', REJECTED: '已驳回' }

export default {
  name: 'AaWorkloadReviewView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
      AppButton, AppSectionCard, AppStatusTag, AppFormItem, AppSelect, AppTextarea, AppTermCodePicker
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', status: '', termCode: '', rows: [], rejecting: null, rejectNote: '', submitting: false,
      statusOptions: [
        { label: '全部', value: '' }, { label: '待审核', value: 'SUBMITTED' },
        { label: '已通过', value: 'APPROVED' }, { label: '已驳回', value: 'REJECTED' }
      ],
      columns: [
        { key: 'teacher', title: '教师' }, { key: 'termCode', title: '学期', align: 'center' },
        { key: 'categoryLabel', title: '类别', align: 'center' }, { key: 'hours', title: '申报课时', align: 'center' },
        { key: 'description', title: '工作说明' }, { key: 'status', title: '状态', align: 'center' },
        { key: 'actions', title: '操作', align: 'center' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    statusLabel(s) { return STATUS[s] || s },
    statusColor(s) {
      if (s === 'APPROVED') return 'success'
      if (s === 'REJECTED') return 'danger'
      if (s === 'SUBMITTED') return 'primary'
      return 'default'
    },
    async load() {
      this.loading = true
      this.error = ''
      this.rejecting = null
      const res = await academicAffairsApi.getWorkloadDeclarations({ status: this.status || undefined, termCode: this.termCode || undefined, page: 1, pageSize: 100 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    async approve(r) {
      const res = await academicAffairsApi.reviewWorkloadDeclaration(r.declarationId, { action: 'APPROVE' })
      if (res.code === 0) { toast.success('已通过'); this.load() } else toast.error(res.message || '操作失败')
    },
    openReject(r) { this.rejecting = r; this.rejectNote = '' },
    async doReject() {
      if (this.submitting) return
      if (!this.rejectNote || this.rejectNote.trim().length < 5) { toast.error('驳回原因必填且不少于 5 字'); return }
      this.submitting = true
      const res = await academicAffairsApi.reviewWorkloadDeclaration(this.rejecting.declarationId, { action: 'REJECT', note: this.rejectNote.trim() })
      this.submitting = false
      if (res.code === 0) { toast.success('已驳回'); this.rejecting = null; this.load() } else toast.error(res.message || '操作失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.aa-filter__label { font-size: 13px; color: var(--text-700, #4e5969); }
.aa-note-sm { color: var(--text-500, #646a73); font-size: 12px; }
.mp-link--danger { color: var(--danger-600, #f53f3f); margin-left: 10px; }
.aa-actions { margin-top: 12px; display: flex; gap: 12px; }
</style>
