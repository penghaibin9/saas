<template>
  <ModulePageShell title="告警与事件中心" subtitle="当前P0/P1 · 受影响租户 · 未确认告警 · 更新时间 · 通知覆盖"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'create', label: '＋ 登记事件' }, { key: 'refresh', label: '刷新' }]"
                    @action="onToolbarAction" />
    </template>

    <LoadingState v-if="loading" text="正在加载事件…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else>
      <div class="pin__grid">
        <AppCard class="pin__stat" :class="{ 'pin__stat--warn': overview.p0p1ActiveCount }"><div class="pin__stat-num">{{ overview.p0p1ActiveCount }}</div><div class="pin__stat-label">当前 P0/P1</div></AppCard>
        <AppCard class="pin__stat"><div class="pin__stat-num">{{ overview.activeCount }}</div><div class="pin__stat-label">进行中事件</div></AppCard>
        <AppCard class="pin__stat" :class="{ 'pin__stat--warn': overview.unacknowledgedCount }"><div class="pin__stat-num">{{ overview.unacknowledgedCount }}</div><div class="pin__stat-label">未确认</div></AppCard>
      </div>

      <AppCard v-if="showCreate" class="pin__panel">
        <AppSectionHeader title="登记事件" />
        <div class="pin__form">
          <input v-model.trim="form.title" class="pin__input" placeholder="事件标题" />
          <select v-model="form.severity" class="pin__input">
            <option value="P0">P0</option><option value="P1">P1</option>
            <option value="P2">P2</option><option value="P3">P3</option>
          </select>
          <input v-model.trim="form.affectedServiceCodesText" class="pin__input" placeholder="受影响服务码，逗号分隔" />
          <button class="mp-link" @click="submitCreate">创建（受影响租户按当前依赖图快照一次）</button>
        </div>
      </AppCard>

      <AppCard class="pin__panel">
        <AppSectionHeader title="事件列表" />
        <DataTable :columns="listColumns" :rows="incidents" row-key="incidentId" row-clickable @row-click="selectIncident">
          <template #cell-scope="{ row }">
            <div class="pin__cell-main">{{ row.title }}</div>
            <div class="pin__cell-sub">{{ row.severity }} · {{ row.affectedServiceCodes.join('、') }}</div>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="statusTone(row.status)" :label="row.status" dot />
          </template>
        </DataTable>
      </AppCard>

      <AppCard v-if="selected" class="pin__panel">
        <AppSectionHeader :title="`事件详情：${selected.title}`" />
        <div class="pin__form">
          <select v-model="nextStatus" class="pin__input">
            <option v-for="s in statusOptions" :key="s" :value="s">{{ s }}</option>
          </select>
          <button class="mp-link" @click="advanceStatus">推进状态</button>
          <button v-if="selected.status === 'RESOLVED'" class="mp-link" @click="requestProblem">申请转Problem</button>
        </div>
        <p v-if="selected.problemConversionRequestedAt" class="pin__note">
          已于 {{ selected.problemConversionRequestedAt }} 申请转 Problem（PLAT-10 尚未建卡，仅登记申请）
        </p>

        <AppSectionHeader title="受影响租户（创建时快照，不随后续依赖图变化改写）" class="pin__gap" />
        <ul class="pin__list">
          <li v-for="t in selected.affectedTenants" :key="t.tenantId">
            租户 {{ t.tenantId }} · {{ t.impactType === 'DIRECT' ? '直接受影响' : '间接受影响' }}
          </li>
        </ul>

        <AppSectionHeader title="时间线更新（内部记录与对外文案分开维护）" class="pin__gap" />
        <div class="pin__form">
          <textarea v-model="updateForm.externalMessage" class="pin__textarea" placeholder="对外文案（学校侧可见）" />
          <textarea v-model="updateForm.internalNote" class="pin__textarea" placeholder="内部记录（仅平台侧可见，不对外）" />
          <button class="mp-link" @click="submitUpdate">保存更新</button>
        </div>
        <ul class="pin__list">
          <li v-for="u in selected.updates" :key="u.updateId">
            #{{ u.updateSeq }} {{ u.statusAtUpdate }} · {{ u.externalMessage }}
            <StatusTag :type="u.published ? 'success' : 'default'" :label="u.published ? '已发布' : '草稿'" dot />
            <button v-if="!u.published" class="mp-link" @click="publishUpdate(u)">发布并通知</button>
            <span v-if="u.notificationResult" class="pin__note">
              通知结果：{{ Object.keys(u.notificationResult).length }} 个租户
            </span>
          </li>
        </ul>
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
import { AppCard, AppSectionHeader } from '@/components/ui'
import { DataTable, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

const STATUS_ORDER = ['DETECTED', 'ACKNOWLEDGED', 'MITIGATING', 'MONITORING', 'RESOLVED']

export default {
  name: 'PlatformIncidentView',
  components: { AppCard, AppSectionHeader, DataTable, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  data() {
    return {
      loading: true,
      error: '',
      overview: {},
      incidents: [],
      selected: null,
      showCreate: false,
      nextStatus: 'ACKNOWLEDGED',
      form: { title: '', severity: 'P1', affectedServiceCodesText: '' },
      updateForm: { externalMessage: '', internalNote: '' },
      listColumns: [
        { key: 'scope', title: '事件' },
        { key: 'status', title: '状态' }
      ]
    }
  },
  computed: {
    statusOptions() {
      if (!this.selected) return STATUS_ORDER
      const idx = STATUS_ORDER.indexOf(this.selected.status)
      return STATUS_ORDER.slice(idx)
    }
  },
  created() { this.load() },
  methods: {
    statusTone(s) {
      return { DETECTED: 'danger', ACKNOWLEDGED: 'warning', MITIGATING: 'warning', MONITORING: 'warning', RESOLVED: 'success' }[s] || 'default'
    },
    onToolbarAction(action) {
      if (action === 'create') this.showCreate = !this.showCreate
      if (action === 'refresh') this.load()
    },
    async submitCreate() {
      if (!this.form.title || !this.form.affectedServiceCodesText) return toast.error('标题与受影响服务必填')
      const codes = this.form.affectedServiceCodesText.split(',').map((s) => s.trim()).filter(Boolean)
      const res = await platformControlApi.createIncident({
        title: this.form.title, severity: this.form.severity, affectedServiceCodes: codes
      })
      if (res.code === 0) {
        toast.success('事件已登记')
        this.showCreate = false
        await this.load()
        this.selected = res.data
      } else toast.error(res.message)
    },
    async selectIncident(row) {
      const res = await platformControlApi.getIncident(row.incidentId)
      if (res.code === 0) { this.selected = res.data; this.nextStatus = this.statusOptions[1] || this.selected.status }
      else toast.error(res.message)
    },
    async advanceStatus() {
      const res = await platformControlApi.transitionIncidentStatus(this.selected.incidentId, this.nextStatus)
      if (res.code === 0) { toast.success('状态已更新'); await this.selectIncident({ incidentId: this.selected.incidentId }); await this.load() }
      else toast.error(res.message)
    },
    async requestProblem() {
      const res = await platformControlApi.requestIncidentProblemConversion(this.selected.incidentId)
      if (res.code === 0) { toast.success('已登记转Problem申请'); this.selected = res.data }
      else toast.error(res.message)
    },
    async submitUpdate() {
      if (!this.updateForm.externalMessage) return toast.error('对外文案必填')
      const res = await platformControlApi.addIncidentUpdate(this.selected.incidentId, { ...this.updateForm })
      if (res.code === 0) {
        toast.success('更新已保存')
        this.updateForm = { externalMessage: '', internalNote: '' }
        await this.selectIncident({ incidentId: this.selected.incidentId })
      } else toast.error(res.message)
    },
    async publishUpdate(u) {
      const res = await platformControlApi.publishIncidentUpdate(this.selected.incidentId, u.updateId)
      if (res.code === 0) { toast.success('已发布通知'); await this.selectIncident({ incidentId: this.selected.incidentId }) }
      else toast.error(res.message)
    },
    async load() {
      this.loading = true
      this.error = ''
      const [overview, list] = await Promise.all([
        platformControlApi.getIncidentsOverview(),
        platformControlApi.listIncidents()
      ])
      if (overview.code === 0) this.overview = overview.data || {}
      else this.error = overview.message
      if (list.code === 0) this.incidents = list.data.items || []
      else if (!this.error) this.error = list.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
.pin__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.pin__stat { padding: var(--space-4); }
.pin__stat--warn { border-color: var(--color-danger); }
.pin__stat-num { font-size: 26px; font-weight: var(--font-weight-bold); color: var(--t1); }
.pin__stat-label { margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.pin__panel { padding: var(--space-4); margin-bottom: var(--space-3); }
.pin__cell-main { font-weight: var(--font-weight-medium); }
.pin__cell-sub { font-size: var(--font-size-xs); color: var(--text-secondary); }
.pin__form { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: flex-start; margin-bottom: var(--space-3); }
.pin__input { padding: 6px 10px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); min-width: 160px; }
.pin__textarea { padding: 6px 10px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); min-width: 260px; min-height: 60px; }
.pin__gap { margin-top: var(--space-4); }
.pin__list { list-style: none; padding: 0; margin: 0; }
.pin__list li { padding: 4px 0; font-size: var(--font-size-sm); border-bottom: 1px solid var(--border-light); }
.pin__note { color: var(--text-secondary); font-size: var(--font-size-xs); }
</style>
