<template>
  <ModulePageShell title="客户健康、工单、培训与续费" subtitle="健康分实时判定 · 工单 · 培训 · 续费跟进"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'refresh', label: '刷新' }]" @action="load" />
    </template>

    <LoadingState v-if="loading" text="正在加载客户成功数据…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else-if="ov">
      <div class="pcs__grid">
        <AppCard class="pcs__stat"><div class="pcs__stat-num">{{ ov.tenantCount }}</div><div class="pcs__stat-label">在库租户</div></AppCard>
        <AppCard class="pcs__stat" :class="{ 'pcs__stat--warn': ov.healthDistribution.CRITICAL }">
          <div class="pcs__stat-num">{{ ov.healthDistribution.CRITICAL }}</div><div class="pcs__stat-label">健康分 CRITICAL</div>
        </AppCard>
        <AppCard class="pcs__stat" :class="{ 'pcs__stat--warn': ov.healthDistribution.AT_RISK }">
          <div class="pcs__stat-num">{{ ov.healthDistribution.AT_RISK }}</div><div class="pcs__stat-label">健康分 AT_RISK</div>
        </AppCard>
        <AppCard class="pcs__stat"><div class="pcs__stat-num">{{ ov.openTicketsTotal }}</div><div class="pcs__stat-label">未关闭工单</div></AppCard>
        <AppCard class="pcs__stat"><div class="pcs__stat-num">{{ ov.upcomingRenewals }}</div><div class="pcs__stat-label">待跟进续费</div></AppCard>
      </div>

      <AppCard class="pcs__panel">
        <AppSectionHeader title="健康分 CRITICAL 的学校" />
        <EmptyState v-if="!ov.criticalTenants.length" text="当前无 CRITICAL 学校" compact />
        <ul v-else class="pcs__list">
          <li v-for="t in ov.criticalTenants" :key="t.tenantId">
            <span class="pcs__list-name">{{ t.tenantName }}</span>
            <span class="pcs__list-sub">{{ (t.reasons || []).join('；') }}</span>
          </li>
        </ul>
      </AppCard>

      <div class="pcs__workspace-grid">
        <AppCard class="pcs__panel">
          <AppSectionHeader title="创建客户工单" />
          <div class="pcs__form pcs__form--stack">
            <input v-model.trim="ticketForm.tenantId" class="pcs__input" placeholder="租户 ID" />
            <input v-model.trim="ticketForm.title" class="pcs__input" placeholder="工单标题" />
            <select v-model="ticketForm.severity" class="pcs__input">
              <option value="P0">P0</option><option value="P1">P1</option>
              <option value="P2">P2</option><option value="P3">P3</option>
            </select>
            <input v-model.trim="ticketForm.reporterName" class="pcs__input" placeholder="反馈人" />
            <button class="mp-link" @click="createTicket">创建工单</button>
          </div>
        </AppCard>

        <AppCard class="pcs__panel">
          <AppSectionHeader title="登记培训计划" />
          <div class="pcs__form pcs__form--stack">
            <input v-model.trim="trainingForm.tenantId" class="pcs__input" placeholder="租户 ID" />
            <input v-model.trim="trainingForm.topic" class="pcs__input" placeholder="培训主题" />
            <input v-model="trainingForm.scheduledAt" type="datetime-local" class="pcs__input" />
            <input v-model.trim="trainingForm.trainerName" class="pcs__input" placeholder="培训讲师" />
            <button class="mp-link" @click="createTraining">登记培训</button>
          </div>
        </AppCard>

        <AppCard class="pcs__panel">
          <AppSectionHeader title="创建续费跟进" />
          <div class="pcs__form pcs__form--stack">
            <input v-model.trim="renewalForm.tenantId" class="pcs__input" placeholder="租户 ID" />
            <input v-model="renewalForm.dueAt" type="datetime-local" class="pcs__input" />
            <input v-model.trim="renewalForm.ownerName" class="pcs__input" placeholder="跟进负责人" />
            <input v-model.trim="renewalForm.note" class="pcs__input" placeholder="跟进备注" />
            <button class="mp-link" @click="createRenewal">创建续费任务</button>
          </div>
        </AppCard>
      </div>

      <AppCard class="pcs__panel">
        <AppSectionHeader title="工单列表" />
        <DataTable :columns="ticketColumns" :rows="tickets" row-key="id">
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'OPEN' ? 'danger' : (row.status === 'IN_PROGRESS' ? 'warning' : 'success')" :label="row.status" />
          </template>
          <template #cell-ops="{ row }">
            <button v-if="row.status !== 'CLOSED'" class="mp-link" @click="transitionTicket(row, 'IN_PROGRESS')">处理中</button>
            <button v-if="row.status !== 'CLOSED'" class="mp-link" @click="transitionTicket(row, 'RESOLVED')">已解决</button>
            <button v-if="row.status === 'RESOLVED'" class="mp-link" @click="transitionTicket(row, 'CLOSED')">关闭</button>
          </template>
        </DataTable>
      </AppCard>

      <AppCard class="pcs__panel">
        <AppSectionHeader title="培训计划与完成记录" />
        <DataTable :columns="trainingColumns" :rows="trainings" row-key="id">
          <template #cell-status="{ row }">
            <StatusTag :type="row.status === 'COMPLETED' ? 'success' : row.status === 'CANCELLED' ? 'default' : 'warning'" :label="row.status" />
          </template>
          <template #cell-ops="{ row }">
            <button v-if="row.status === 'SCHEDULED'" class="mp-link" @click="completeTraining(row)">登记完成</button>
          </template>
        </DataTable>
        <EmptyState v-if="!trainings.length" text="暂无培训计划" compact />
      </AppCard>

      <AppCard class="pcs__panel">
        <AppSectionHeader title="续费跟进任务" />
        <DataTable :columns="renewalColumns" :rows="renewals" row-key="id">
          <template #cell-status="{ row }">
            <StatusTag :type="renewalTone(row.status)" :label="row.status" />
          </template>
          <template #cell-ops="{ row }">
            <button v-if="row.status === 'PENDING'" class="mp-link" @click="transitionRenewal(row, 'CONTACTED')">已联系</button>
            <button v-if="['PENDING','CONTACTED'].includes(row.status)" class="mp-link" @click="transitionRenewal(row, 'COMMITTED')">已承诺</button>
            <button v-if="!['RENEWED','CHURNED'].includes(row.status)" class="mp-link" @click="transitionRenewal(row, 'RENEWED')">已续费</button>
            <button v-if="!['RENEWED','CHURNED'].includes(row.status)" class="mp-link pcs__danger-link" @click="transitionRenewal(row, 'CHURNED')">流失</button>
          </template>
        </DataTable>
        <EmptyState v-if="!renewals.length" text="暂无续费跟进任务" compact />
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
/** PLAT-05 客户成功：健康分 + 工单 + 培训 + 续费全部消费真实后端 Authority。 */
import { AppCard, AppSectionHeader } from '@/components/ui'
import { DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

const iso = (value) => value ? new Date(value).toISOString() : ''
const newTraining = () => ({ tenantId: '', topic: '', scheduledAt: '', trainerName: '' })
const newRenewal = () => ({ tenantId: '', dueAt: '', ownerName: '', note: '' })

export default {
  name: 'PlatformCustomerSuccessView',
  components: { AppCard, AppSectionHeader, DataTable, EmptyState, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  data() {
    return {
      loading: true,
      error: '',
      ov: null,
      tickets: [], trainings: [], renewals: [],
      ticketForm: { tenantId: '', title: '', severity: 'P2', reporterName: '' },
      trainingForm: newTraining(),
      renewalForm: newRenewal(),
      ticketColumns: [
        { key: 'title', title: '标题' }, { key: 'tenantId', title: '租户' }, { key: 'severity', title: '优先级' },
        { key: 'status', title: '状态' }, { key: 'reporterName', title: '反馈人' }, { key: 'ops', title: '操作' }
      ],
      trainingColumns: [
        { key: 'tenantId', title: '租户' }, { key: 'topic', title: '培训主题' }, { key: 'trainerName', title: '讲师' },
        { key: 'scheduledAt', title: '计划时间' }, { key: 'attendeeCount', title: '参训人数' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ],
      renewalColumns: [
        { key: 'tenantId', title: '租户' }, { key: 'dueAt', title: '跟进截止' }, { key: 'ownerName', title: '负责人' },
        { key: 'status', title: '状态' }, { key: 'note', title: '备注' }, { key: 'ops', title: '操作' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    renewalTone(status) {
      return { PENDING: 'warning', CONTACTED: 'processing', COMMITTED: 'processing', RENEWED: 'success', CHURNED: 'danger' }[status] || 'default'
    },
    async load() {
      this.loading = true
      this.error = ''
      const [ovRes, ticketsRes, trainingsRes, renewalsRes] = await Promise.all([
        platformControlApi.getCustomerSuccessOverview(),
        platformControlApi.listSupportTickets(),
        platformControlApi.listTrainings(),
        platformControlApi.listRenewalTasks()
      ])
      this.loading = false
      const failed = [ovRes, ticketsRes, trainingsRes, renewalsRes].find((res) => res.code !== 0)
      if (failed) this.error = failed.message
      if (ovRes.code === 0) this.ov = ovRes.data
      if (ticketsRes.code === 0) this.tickets = ticketsRes.data.items || []
      if (trainingsRes.code === 0) this.trainings = trainingsRes.data.items || []
      if (renewalsRes.code === 0) this.renewals = renewalsRes.data.items || []
    },
    async createTicket() {
      if (!this.ticketForm.tenantId || !this.ticketForm.title) return toast.error('请填写租户 ID 和标题')
      const res = await platformControlApi.createSupportTicket({ ...this.ticketForm })
      if (res.code !== 0) return toast.error(res.message)
      toast.success('工单已创建')
      this.ticketForm = { tenantId: '', title: '', severity: 'P2', reporterName: '' }
      await this.load()
    },
    async transitionTicket(row, status) {
      const resolutionNote = ['RESOLVED', 'CLOSED'].includes(status) ? (window.prompt('处理结论（可留空）') || '') : ''
      const res = await platformControlApi.transitionSupportTicket(row.id, { status, resolutionNote, expectedVersion: row.version })
      if (res.code !== 0) return toast.error(res.message)
      toast.success('工单状态已更新')
      await this.load()
    },
    async createTraining() {
      if (!this.trainingForm.tenantId || !this.trainingForm.topic || !this.trainingForm.scheduledAt) return toast.error('租户、培训主题和计划时间必填')
      const res = await platformControlApi.createTraining({ ...this.trainingForm, scheduledAt: iso(this.trainingForm.scheduledAt) })
      if (res.code !== 0) return toast.error(res.message)
      toast.success('培训计划已登记')
      this.trainingForm = newTraining()
      await this.load()
    },
    async completeTraining(row) {
      const countText = window.prompt('实际参训人数', String(row.attendeeCount || 0))
      if (countText == null) return
      const attendeeCount = Number(countText)
      if (!Number.isInteger(attendeeCount) || attendeeCount < 0) return toast.error('参训人数必须是非负整数')
      const note = window.prompt('培训完成备注（可留空）') || ''
      const res = await platformControlApi.completeTraining(row.id, { attendeeCount, note, expectedVersion: row.version })
      if (res.code !== 0) return toast.error(res.message)
      toast.success('培训已标记完成')
      await this.load()
    },
    async createRenewal() {
      if (!this.renewalForm.tenantId || !this.renewalForm.dueAt) return toast.error('租户和跟进截止时间必填')
      const res = await platformControlApi.createRenewalTask({ ...this.renewalForm, dueAt: iso(this.renewalForm.dueAt) })
      if (res.code !== 0) return toast.error(res.message)
      toast.success('续费任务已创建')
      this.renewalForm = newRenewal()
      await this.load()
    },
    async transitionRenewal(row, status) {
      const note = window.prompt('本次续费跟进备注（可留空）', row.note || '')
      if (note == null) return
      const res = await platformControlApi.transitionRenewalTask(row.id, { status, note, expectedVersion: row.version })
      if (res.code !== 0) return toast.error(res.message)
      toast.success('续费任务状态已更新')
      await this.load()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pcs__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-3); }
.pcs__stat { padding: var(--space-4); }.pcs__stat--warn { border-color: var(--color-warning, #d97706); }
.pcs__stat-num { font-size: 26px; font-weight: var(--font-weight-bold); color: var(--t1); }
.pcs__stat-label { margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.pcs__panel { margin-top: var(--space-3); padding: var(--space-4); }
.pcs__workspace-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-3); }
.pcs__list { list-style: none; margin: var(--space-2) 0 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.pcs__list li { display: flex; flex-direction: column; font-size: var(--font-size-sm); }
.pcs__list-name { color: var(--t1); font-weight: var(--font-weight-bold); }
.pcs__list-sub { color: var(--text-secondary); font-size: 12px; }
.pcs__form { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-2); }
.pcs__form--stack { flex-direction: column; align-items: stretch; }
.pcs__input { min-height: 36px; padding: 6px 10px; border: 1px solid var(--border-light); border-radius: var(--radius-sm, 4px); font-size: var(--font-size-sm); }
.pcs__danger-link { color: var(--danger-600, #b42318); }
@media (max-width: 1050px) { .pcs__workspace-grid { grid-template-columns: 1fr; } }
</style>
