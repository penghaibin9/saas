<template>
  <ModulePageShell
    title="课表发布"
    subtitle="课表批次预发布/正式发布/作废重发，及发布通知回执历史（t_aa_schedule_publish）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次 / 排课</AppButton>
    </template>

    <div class="mp-stack">
      <AppSectionCard v-if="gate.visible" title="发布门禁检查">
        <LoadingState v-if="gate.loading" />
        <template v-else-if="gate.summary">
          <div class="aa-gate-head">
            <div>
              <strong>{{ gate.batch?.batchName }}</strong>
              <p>发布动作只认服务端同一套课表完整性闸门；检查未通过时不会写入发布状态。</p>
            </div>
            <AppStatusTag :type="gate.summary.complete ? 'success' : 'danger'" dot>
              {{ gate.summary.complete ? '全部通过' : '存在阻断项' }}
            </AppStatusTag>
          </div>
          <div class="aa-gate-grid">
            <div v-for="item in gateChecklist" :key="item.label" :class="['aa-gate-item', item.ok ? 'is-ok' : 'is-blocked']">
              <span>{{ item.ok ? '✓' : '!' }}</span>
              <div><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></div>
            </div>
          </div>
          <p v-if="gate.summary.pendingTeacherObjections" class="aa-gate-warning">
            教师异议待处理 {{ gate.summary.pendingTeacherObjections }} 条；当前不是技术硬门禁，但建议正式发布前处理完毕。
          </p>
          <div class="aa-gate-actions">
            <AppButton @click="gate.visible = false">收起检查</AppButton>
            <AppButton v-if="!gate.summary.complete" @click="openWorkbench(gate.batch)">返回排课工作台处理</AppButton>
            <AppButton
              v-else-if="gate.intent !== 'view'"
              variant="primary"
              :loading="gate.submitting"
              @click="confirmGateAction"
            >{{ gate.intent === 'pub' ? '确认正式发布并通知师生' : '确认进入预发布' }}</AppButton>
          </div>
        </template>
      </AppSectionCard>

      <AppSectionCard title="待发布 / 已发布批次">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无课表批次" description="请先到「课表批次/排课」页新建批次并排课" />
        <DataTable v-else :columns="columns" :rows="rows" row-key="batchId">
          <template #cell-status="{ row }">
            <AppStatusTag :type="scheduleBatchColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
          </template>
          <template #cell-actions="{ row }">
            <div class="aa-actions">
              <button v-if="row.status === 'DRAFT'" class="mp-link" @click="openGate(row, 'pre')">检查并预发布</button>
              <button v-if="row.status === 'PRE_PUBLISHED'" class="mp-link" @click="openGate(row, 'pub')">检查并正式发布</button>
              <button v-if="row.status === 'PUBLISHED'" class="mp-link" @click="openGate(row, 'view')">复核发布门禁</button>
              <button v-if="row.status === 'PUBLISHED'" class="mp-link" @click="openPublished(row)">查看已发布课表</button>
              <button v-if="row.status === 'PUBLISHED'" class="mp-link" @click="openChangeLedger(row)">调停课台账</button>
              <button v-if="row.status === 'PUBLISHED'" class="mp-link aa-danger" @click="openVoid(row)">作废重发（重大纠错）</button>
              <span v-if="row.status === 'ARCHIVED'" class="aa-archived">已作废</span>
            </div>
          </template>
        </DataTable>
        <p class="mp-note">发布后课表不可直接修改。日常单课位调课、停课、补课走「调停课」审批；只有整批课表存在重大错误、必须整体重排时，才使用危险操作「作废重发」。</p>
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
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { SCHEDULE_BATCH_STATUS, scheduleBatchColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaSchedulePublishView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [],
      recLoading: true, records: [],
      gate: { visible: false, loading: false, submitting: false, batch: null, summary: null, intent: 'pre' },
      voidDlg: { visible: false, submitting: false, batchId: '' },
      columns: [
        { key: 'batchName', title: '批次名称' },
        { key: 'status', title: '状态' },
        { key: 'publishAt', title: '发布时间' },
        { key: 'actions', title: '操作', width: '420px' }
      ],
      recColumns: [
        { key: 'action', title: '动作' },
        { key: 'operatorName', title: '操作人' },
        { key: 'notifiedCount', title: '通知教师数' },
        { key: 'note', title: '备注' },
        { key: 'createdAt', title: '时间' }
      ]
    }
  },
  computed: {
    gateChecklist() {
      const row = this.gate.summary || {}
      return [
        { label: '教学任务可排', ok: row.totalTasks > 0 && !row.invalidTaskCount, detail: `任务 ${row.totalTasks || 0} 个 · 配置异常 ${row.invalidTaskCount || 0} 个` },
        { label: '应排节次完整', ok: !row.missingTaskCount && !row.overScheduledTaskCount, detail: `应排 ${row.expectedSessions || 0} 节 · 已排 ${row.scheduledSessions || 0} 节 · 漏排 ${row.missingTaskCount || 0} 个任务` },
        { label: '课位关联有效', ok: !row.orphanItemCount && !row.invalidCoordinateItemCount, detail: `孤立课位 ${row.orphanItemCount || 0} · 周次坐标异常 ${row.invalidCoordinateItemCount || 0}` },
        { label: '硬冲突清零', ok: !row.hardConflicts, detail: `硬冲突 ${row.hardConflicts || 0} · 软冲突 ${row.softConflicts || 0}` }
      ]
    }
  },
  created() { this.load(); this.loadRecords() },
  methods: {
    scheduleBatchColor,
    statusLabel(s) { return SCHEDULE_BATCH_STATUS[s] || s || '' },
    openPublished(row) { this.$router.push(`/admin/academic-affairs/schedule/${row.batchId}/views`) },
    openChangeLedger(row) { this.$router.push({ path: '/admin/academic-affairs/schedule-change', query: { termId: row.termId || '' } }) },
    openWorkbench(row) { this.$router.push({ path: '/admin/academic-affairs/scheduling', query: { batchId: row?.batchId || '' } }) },
    async openGate(row, intent = 'pre') {
      this.gate = { visible: true, loading: true, submitting: false, batch: row, summary: null, intent }
      const response = await academicAffairsApi.getScheduleSummary(row.batchId)
      this.gate.loading = false
      if (response.code === 0) this.gate.summary = response.data
      else {
        this.gate.visible = false
        toast.error(response.message || '发布门禁检查失败')
      }
    },
    async confirmGateAction() {
      if (!this.gate.summary?.complete || !this.gate.batch) return
      this.gate.submitting = true
      await this.act(this.gate.batch, this.gate.intent)
      this.gate.submitting = false
    },
    async act(row, kind) {
      const fn = kind === 'pre' ? academicAffairsApi.prePublishSchedule : academicAffairsApi.publishSchedule
      const res = await fn(row.batchId)
      if (res.code === 0) {
        toast.success(kind === 'pre' ? '已预发布' : '已发布，已通知师生')
        this.gate.visible = false
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
.aa-actions { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; }
.aa-gate-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.aa-gate-head p { margin: 6px 0 0; color: var(--text-500, #86909c); font-size: 13px; }
.aa-gate-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-top: 14px; }
.aa-gate-item { display: flex; gap: 10px; padding: 12px; border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; background: var(--bg-100, #f7f8fa); }
.aa-gate-item > span { width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; flex: 0 0 auto; font-weight: 700; }
.aa-gate-item div { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.aa-gate-item small { color: var(--text-500, #86909c); line-height: 1.5; }
.aa-gate-item.is-ok > span { color: var(--success-700, #15803d); background: var(--success-100, #dcfce7); }
.aa-gate-item.is-blocked { border-color: var(--danger-200, #fecaca); background: var(--danger-50, #fef2f2); }
.aa-gate-item.is-blocked > span { color: var(--danger-700, #b91c1c); background: var(--danger-100, #fee2e2); }
.aa-gate-warning { margin: 12px 0 0; padding: 10px 12px; border-radius: 8px; color: var(--warning-700, #b45309); background: var(--warning-50, #fffbeb); font-size: 13px; }
.aa-gate-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 14px; }
@media (max-width: 760px) { .aa-gate-grid { grid-template-columns: 1fr; } .aa-gate-head { flex-direction: column; } }
</style>
