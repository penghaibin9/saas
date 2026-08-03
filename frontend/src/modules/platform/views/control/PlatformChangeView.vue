<template>
  <ModulePageShell title="变更、发布、兼容性、灰度与回滚" subtitle="今日变更 · 待审批 · 高风险 · 冻结冲突 · 不兼容租户 · 失败变更"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'create', label: '＋ 创建变更' }, { key: 'freeze', label: '登记冻结期' }, { key: 'refresh', label: '刷新' }]"
                    @action="onToolbarAction" />
    </template>

    <LoadingState v-if="loading" text="正在加载变更…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else>
      <div class="pch__grid">
        <AppCard class="pch__stat"><div class="pch__stat-num">{{ overview.todayChangeCount }}</div><div class="pch__stat-label">今日变更</div></AppCard>
        <AppCard class="pch__stat"><div class="pch__stat-num">{{ overview.pendingApprovalCount }}</div><div class="pch__stat-label">待审批</div></AppCard>
        <AppCard class="pch__stat" :class="{ 'pch__stat--warn': overview.highRiskCount }"><div class="pch__stat-num">{{ overview.highRiskCount }}</div><div class="pch__stat-label">高风险</div></AppCard>
        <AppCard class="pch__stat" :class="{ 'pch__stat--warn': overview.freezeConflictCount }"><div class="pch__stat-num">{{ overview.freezeConflictCount }}</div><div class="pch__stat-label">冻结冲突</div></AppCard>
        <AppCard class="pch__stat" :class="{ 'pch__stat--warn': overview.failedChangeCount }"><div class="pch__stat-num">{{ overview.failedChangeCount }}</div><div class="pch__stat-label">失败变更</div></AppCard>
      </div>

      <AppCard v-if="showCreate" class="pch__panel">
        <AppSectionHeader title="创建变更请求" />
        <div class="pch__form">
          <input v-model.trim="form.title" class="pch__input" placeholder="变更标题" />
          <select v-model="form.changeType" class="pch__input">
            <option value="CODE">CODE</option><option value="MIGRATION">MIGRATION</option>
            <option value="PLATFORM_CONFIG">PLATFORM_CONFIG</option><option value="PACKAGE">PACKAGE</option>
            <option value="COMMON_FOUNDATION">COMMON_FOUNDATION</option><option value="HOTFIX">HOTFIX</option>
          </select>
          <input v-model.trim="form.affectedServiceCodesText" class="pch__input" placeholder="受影响服务码，逗号分隔" />
          <label class="pch__checkbox"><input type="checkbox" v-model="form.isIrreversible" /> 不可逆迁移</label>
          <textarea v-if="form.isIrreversible" v-model="form.rollbackPlan" class="pch__textarea" placeholder="替代恢复方案（不可逆迁移必填）" />
          <button class="mp-link" @click="submitCreate">创建</button>
        </div>
      </AppCard>

      <AppCard v-if="showFreeze" class="pch__panel">
        <AppSectionHeader title="登记平台全局冻结期" />
        <div class="pch__form">
          <input v-model.trim="freezeForm.title" class="pch__input" placeholder="标题" />
          <input v-model="freezeForm.startAt" type="datetime-local" class="pch__input" />
          <input v-model="freezeForm.endAt" type="datetime-local" class="pch__input" />
          <input v-model.trim="freezeForm.reason" class="pch__input" placeholder="原因" />
          <button class="mp-link" @click="submitFreeze">登记</button>
        </div>
      </AppCard>

      <AppCard class="pch__panel">
        <AppSectionHeader title="变更列表" />
        <DataTable :columns="listColumns" :rows="changes" row-key="changeId" row-clickable @row-click="selectChange">
          <template #cell-scope="{ row }">
            <div class="pch__cell-main">{{ row.title }}</div>
            <div class="pch__cell-sub">{{ row.changeType }} · {{ row.affectedServiceCodes.join('、') }}</div>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="statusTone(row.status)" :label="row.status" dot />
          </template>
        </DataTable>
      </AppCard>

      <AppCard v-if="selected" class="pch__panel">
        <AppSectionHeader :title="`变更详情：${selected.title}（${selected.status}）`" />
        <div class="pch__form">
          <button v-if="selected.status === 'DRAFT'" class="mp-link" @click="doAssess">评估</button>
          <button v-if="selected.status === 'ASSESSED'" class="mp-link" @click="doApprove">审批通过</button>
          <button v-if="selected.status === 'APPROVED'" class="mp-link" @click="doSchedule">排期</button>
          <button v-if="['SCHEDULED', 'IMPLEMENTING'].includes(selected.status)" class="mp-link" @click="doStartWave">开始下一灰度批次</button>
          <button v-if="selected.status === 'IMPLEMENTING'" class="mp-link" @click="doVerify">验证通过</button>
          <button v-if="!['VERIFIED', 'ROLLED_BACK'].includes(selected.status)" class="mp-link" @click="doRollback">回滚</button>
        </div>
        <p v-if="selected.lastError" class="pch__error">最近错误：{{ selected.lastError }}</p>

        <AppSectionHeader title="受影响租户快照" class="pch__gap" />
        <ul class="pch__list">
          <li v-for="t in selected.affectedTenants || []" :key="t.tenantId">
            租户 {{ t.tenantId }} · {{ t.impactType === 'DIRECT' ? '直接受影响' : '间接受影响' }}
          </li>
        </ul>

        <AppSectionHeader title="灰度批次" class="pch__gap" />
        <ul class="pch__list">
          <li v-for="w in selected.waves || []" :key="w.waveNo">
            第{{ w.waveNo }}批 · {{ w.tenantIds.join('、') }} ·
            <StatusTag :type="w.status === 'SUCCEEDED' ? 'success' : (w.status === 'FAILED' ? 'danger' : 'warning')" :label="w.status" dot />
            <button v-if="w.status === 'RUNNING'" class="mp-link" @click="reportWave(w, 'SUCCEEDED')">上报成功</button>
            <button v-if="w.status === 'RUNNING'" class="mp-link" @click="reportWave(w, 'FAILED')">上报失败</button>
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

export default {
  name: 'PlatformChangeView',
  components: { AppCard, AppSectionHeader, DataTable, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  data() {
    return {
      loading: true,
      error: '',
      overview: {},
      changes: [],
      selected: null,
      showCreate: false,
      showFreeze: false,
      form: { title: '', changeType: 'CODE', affectedServiceCodesText: '', isIrreversible: false, rollbackPlan: '' },
      freezeForm: { title: '', startAt: '', endAt: '', reason: '' },
      listColumns: [
        { key: 'scope', title: '变更' },
        { key: 'status', title: '状态' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    statusTone(s) {
      return { DRAFT: 'default', ASSESSED: 'default', APPROVED: 'warning', SCHEDULED: 'warning', IMPLEMENTING: 'warning', VERIFIED: 'success', FAILED: 'danger', ROLLED_BACK: 'danger' }[s] || 'default'
    },
    onToolbarAction(action) {
      if (action === 'create') this.showCreate = !this.showCreate
      if (action === 'freeze') this.showFreeze = !this.showFreeze
      if (action === 'refresh') this.load()
    },
    async submitCreate() {
      if (!this.form.title || !this.form.affectedServiceCodesText) return toast.error('标题与受影响服务必填')
      if (this.form.isIrreversible && !this.form.rollbackPlan) return toast.error('不可逆迁移必须填写替代恢复方案')
      const codes = this.form.affectedServiceCodesText.split(',').map((s) => s.trim()).filter(Boolean)
      const res = await platformControlApi.createChange({
        title: this.form.title, changeType: this.form.changeType, affectedServiceCodes: codes,
        isIrreversible: this.form.isIrreversible, rollbackPlan: this.form.rollbackPlan
      })
      if (res.code === 0) { toast.success('变更已创建'); this.showCreate = false; await this.load(); this.selected = res.data }
      else toast.error(res.message)
    },
    async submitFreeze() {
      if (!this.freezeForm.title || !this.freezeForm.startAt || !this.freezeForm.endAt) return toast.error('标题与起止时间必填')
      const res = await platformControlApi.createMaintenanceWindow({ ...this.freezeForm })
      if (res.code === 0) { toast.success('冻结期已登记'); this.showFreeze = false; await this.load() }
      else toast.error(res.message)
    },
    async selectChange(row) {
      const res = await platformControlApi.getChange(row.changeId)
      if (res.code === 0) this.selected = res.data
      else toast.error(res.message)
    },
    async refreshSelected() {
      if (this.selected) await this.selectChange({ changeId: this.selected.changeId })
      await this.load()
    },
    async doAssess() {
      const res = await platformControlApi.assessChange(this.selected.changeId)
      if (res.code === 0) { toast.success('已评估'); await this.refreshSelected() } else toast.error(res.message)
    },
    async doApprove() {
      const reason = window.prompt('审批意见（至少5字）')
      if (!reason) return
      const res = await platformControlApi.approveChange(this.selected.changeId, reason)
      if (res.code === 0) { toast.success('已审批'); await this.refreshSelected() } else toast.error(res.message)
    },
    async doSchedule() {
      const res = await platformControlApi.scheduleChange(this.selected.changeId)
      if (res.code === 0) { toast.success('已排期'); await this.refreshSelected() } else toast.error(res.message)
    },
    async doStartWave() {
      const waveNo = (this.selected.waves?.length || 0) + 1
      const tenantIdsText = window.prompt('本批次租户ID，逗号分隔')
      if (!tenantIdsText) return
      const tenantIds = tenantIdsText.split(',').map((s) => s.trim()).filter(Boolean)
      const res = await platformControlApi.startChangeWave(this.selected.changeId, waveNo, tenantIds)
      if (res.code === 0) { toast.success('灰度批次已开始'); await this.refreshSelected() } else toast.error(res.message)
    },
    async reportWave(wave, status) {
      const error = status === 'FAILED' ? window.prompt('失败原因') : undefined
      const res = await platformControlApi.reportChangeWave(this.selected.changeId, wave.waveNo, status, error)
      if (res.code === 0) { toast.success('已记录'); await this.refreshSelected() } else toast.error(res.message)
    },
    async doVerify() {
      const res = await platformControlApi.verifyChange(this.selected.changeId)
      if (res.code === 0) { toast.success('已验证通过'); await this.refreshSelected() } else toast.error(res.message)
    },
    async doRollback() {
      const reason = window.prompt('回滚原因（至少5字）')
      if (!reason) return
      const res = await platformControlApi.rollbackChange(this.selected.changeId, reason)
      if (res.code === 0) { toast.success('已回滚'); await this.refreshSelected() } else toast.error(res.message)
    },
    async load() {
      this.loading = true
      this.error = ''
      const [overview, list] = await Promise.all([
        platformControlApi.getChangesOverview(),
        platformControlApi.listChanges()
      ])
      if (overview.code === 0) this.overview = overview.data || {}
      else this.error = overview.message
      if (list.code === 0) this.changes = list.data.items || []
      else if (!this.error) this.error = list.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
.pch__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.pch__stat { padding: var(--space-4); }
.pch__stat--warn { border-color: var(--color-danger); }
.pch__stat-num { font-size: 26px; font-weight: var(--font-weight-bold); color: var(--t1); }
.pch__stat-label { margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.pch__panel { padding: var(--space-4); margin-bottom: var(--space-3); }
.pch__cell-main { font-weight: var(--font-weight-medium); }
.pch__cell-sub { font-size: var(--font-size-xs); color: var(--text-secondary); }
.pch__form { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; margin-bottom: var(--space-3); }
.pch__input { padding: 6px 10px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); min-width: 160px; }
.pch__textarea { padding: 6px 10px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); min-width: 260px; min-height: 60px; }
.pch__checkbox { display: flex; align-items: center; gap: 4px; font-size: var(--font-size-sm); }
.pch__gap { margin-top: var(--space-4); }
.pch__list { list-style: none; padding: 0; margin: 0; }
.pch__list li { padding: 4px 0; font-size: var(--font-size-sm); border-bottom: 1px solid var(--border-light); }
.pch__error { color: var(--color-danger); font-size: var(--font-size-sm); }
</style>
