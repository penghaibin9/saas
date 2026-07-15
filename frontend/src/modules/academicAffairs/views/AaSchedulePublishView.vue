<template>
  <ModulePageShell
    title="课表发布"
    subtitle="课表批次预发布/正式发布/作废重发，及发布通知回执历史（t_aa_schedule_publish）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/schedule')">课表批次 / 排课</button>
    </template>

    <div class="mp-stack">
      <AppSectionCard title="待发布 / 已发布批次">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无课表批次" description="请先到「课表批次/排课」页新建批次并排课" />
        <DataTable v-else :columns="columns" :rows="rows" row-key="batchId">
          <template #cell-status="{ row }">
            <AppStatusTag :type="scheduleBatchColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          </template>
          <template #cell-actions="{ row }">
            <button v-if="row.status === 'DRAFT'" class="mp-link" @click="act(row, 'pre')">预发布</button>
            <button v-if="row.status === 'PRE_PUBLISHED'" class="mp-link" @click="act(row, 'pub')">发布</button>
            <button v-if="row.status === 'PUBLISHED'" class="mp-link aa-danger" @click="openVoid(row)">作废重发</button>
            <span v-if="row.status === 'ARCHIVED'" class="aa-archived">已作废</span>
          </template>
        </DataTable>
        <p class="mp-note">发布后课表项不可直改；如需调整走「作废重发」（原因必填，留审计+发布记录），再新建批次重排。</p>
      </AppSectionCard>

      <AppSectionCard title="发布记录（发布/作废历史留痕）">
        <LoadingState v-if="recLoading" />
        <EmptyState v-else-if="!records.length" title="暂无发布记录" />
        <DataTable v-else :columns="recColumns" :rows="records" row-key="recordId">
          <template #cell-action="{ row }">
            <AppStatusTag :type="row.action === 'PUBLISH' ? 'success' : 'danger'" dot>
              {{ row.action === 'PUBLISH' ? '发布' : '作废重发' }}
            </AppStatusTag>
          </template>
        </DataTable>
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="voidDlg.visible"
      title="作废重发课表批次"
      type="danger"
      confirm-text="确认作废"
      :require-reason="true"
      reason-label="作废原因"
      :submitting="voidDlg.submitting"
      @confirm="doVoid"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 课表发布（/admin/academic-affairs/schedule/publish）：13B 课表管理 Tier1 R2。
 * 发布/预发布/作废重发动作复用既有 schedule-batches 端点（与「课表批次/排课」页同一批 API，不重复实现）；
 * 本页新增能力是发布记录历史（GET /schedule/publish-records，t_aa_schedule_publish）。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { SCHEDULE_BATCH_STATUS, scheduleBatchColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaSchedulePublishView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [],
      recLoading: true, records: [],
      voidDlg: { visible: false, submitting: false, batchId: '' },
      columns: [
        { key: 'batchName', title: '批次名称' },
        { key: 'status', title: '状态' },
        { key: 'publishAt', title: '发布时间' },
        { key: 'actions', title: '操作', width: '200px' }
      ],
      recColumns: [
        { key: 'batchId', title: '批次ID' },
        { key: 'action', title: '动作' },
        { key: 'operatorName', title: '操作人' },
        { key: 'notifiedCount', title: '通知教师数' },
        { key: 'note', title: '备注' },
        { key: 'createdAt', title: '时间' }
      ]
    }
  },
  created() { this.load(); this.loadRecords() },
  methods: {
    scheduleBatchColor,
    statusLabel(s) { return SCHEDULE_BATCH_STATUS[s] || s || '' },
    async act(row, kind) {
      const fn = kind === 'pre' ? academicAffairsApi.prePublishSchedule : academicAffairsApi.publishSchedule
      const res = await fn(row.batchId)
      if (res.code === 0) {
        toast.success(kind === 'pre' ? '已预发布' : '已发布，已通知师生')
        this.load(); this.loadRecords()
      } else {
        toast.error(res.message || '操作失败')
      }
    },
    openVoid(row) { this.voidDlg = { visible: true, submitting: false, batchId: row.batchId } },
    async doVoid(payload) {
      const reason = (payload && payload.reason) || ''
      this.voidDlg.submitting = true
      const res = await academicAffairsApi.voidReissueSchedule(this.voidDlg.batchId, reason)
      this.voidDlg.submitting = false
      if (res.code === 0) {
        this.voidDlg.visible = false
        toast.success('已作废')
        this.load(); this.loadRecords()
      } else {
        toast.error(res.message || '作废失败')
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getScheduleBatches({ page: 1, pageSize: 50 })
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    async loadRecords() {
      this.recLoading = true
      const res = await academicAffairsApi.getSchedulePublishRecords({ page: 1, pageSize: 50 })
      if (res.code === 0) this.records = res.data.list
      this.recLoading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-danger { color: var(--danger-600, #f53f3f); }
.aa-archived { color: var(--text-400, #8a9099); font-size: 13px; }
</style>
