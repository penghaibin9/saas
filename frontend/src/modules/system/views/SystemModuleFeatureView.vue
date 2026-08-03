<template>
  <ModulePageShell
    title="模块授权与业务开关"
    subtitle="平台授权只读 · 学校在已购范围内逐项启停 · 停用前先看影响"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'refresh', label: '刷新' }]" @action="load" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <section v-for="group in groups" :key="group.name" class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">{{ group.name }}</span></header>
          <div class="mp-card__body">
            <div v-for="item in group.items" :key="item.capabilityKey" class="cap-row">
              <div class="cap-row__main">
                <span class="cap-row__label">{{ item.label }}</span>
                <span class="cap-row__key">{{ item.capabilityKey }}</span>
              </div>
              <div class="cap-row__states">
                <span :class="stateClass(item.entitled)">已授权 {{ item.entitled ? '是' : '否' }}</span>
                <span :class="stateClass(item.schoolEnabled)">学校启用 {{ item.schoolEnabled ? '是' : '否' }}</span>
                <span :class="stateClass(item.ready)">准备就绪 {{ item.ready ? '是' : '否' }}</span>
                <span :class="stateClass(item.allowed)">当前可用 {{ item.allowed ? '是' : '否' }}</span>
              </div>
              <div class="cap-row__reason">
                <span v-if="item.reasonCode !== 'OK'" class="mp-note">
                  {{ item.reasonCode }} · {{ item.reasonText || reasonFallback(item) }}
                </span>
                <span v-else-if="item.expiresAt" class="mp-note">启用至 {{ item.expiresAt }}</span>
                <span v-else class="mp-note">正常</span>
              </div>
              <div class="cap-row__ops">
                <button
                  v-if="item.schoolEnabled"
                  class="cap-btn"
                  :disabled="busyKey === item.capabilityKey"
                  @click="askDisable(item)"
                >停用</button>
                <button
                  v-else
                  class="cap-btn cap-btn--primary"
                  :disabled="!item.entitled || busyKey === item.capabilityKey"
                  :title="!item.entitled ? '当前套餐未授权，请联系平台开通' : ''"
                  @click="askEnable(item)"
                >启用</button>
              </div>
            </div>
          </div>
        </section>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="confirmOpen"
      :type="pendingEnabled ? 'info' : 'warning'"
      :title="pendingEnabled ? '启用该模块？' : '停用该模块？'"
      :message="confirmMessage"
      :confirm-text="pendingEnabled ? '确认启用' : '确认停用'"
      require-reason
      reason-label="调整原因"
      :submitting="submitting"
      @confirm="doSubmit"
    >
      <div v-if="!pendingEnabled && impact" class="cap-impact">
        <p v-if="impact.cascadeDisabled && impact.cascadeDisabled.length" class="cap-impact__warn">
          连带不可用：{{ impact.cascadeDisabled.map((i) => i.label).join('、') }}
        </p>
        <ul class="cap-impact__list">
          <li>菜单入口：{{ (impact.menus || []).join('、') || '无' }}</li>
          <li>后端接口：{{ (impact.apis || []).join('、') || '无' }}</li>
          <li>涉及角色：{{ (impact.affectedRoles || []).length }} 个</li>
          <li>影响用户：{{ fmtCount(impact.counts && impact.counts.affectedUsers) }}</li>
          <li>在途流程：{{ fmtCount(impact.counts && impact.counts.runningWorkflows) }}</li>
          <li>待办任务：{{ fmtCount(impact.counts && impact.counts.pendingTodos) }}</li>
          <li>关联文件：{{ fmtCount(impact.counts && impact.counts.fileBindings) }}</li>
        </ul>
        <p class="mp-note">{{ impact.note }}</p>
      </div>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, LoadingState, ErrorState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemModuleFeatureView',
  components: { ModulePageShell, ModuleToolbar, LoadingState, ErrorState, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      items: [],
      confirmOpen: false,
      submitting: false,
      busyKey: '',
      pending: null,
      pendingEnabled: false,
      impact: null
    }
  },
  computed: {
    groups() {
      const byGroup = new Map()
      this.items.forEach((item) => {
        const name = item.schoolGroup || '其他'
        if (!byGroup.has(name)) byGroup.set(name, [])
        byGroup.get(name).push(item)
      })
      return Array.from(byGroup.entries()).map(([name, items]) => ({ name, items }))
    },
    confirmMessage() {
      if (!this.pending) return ''
      return this.pendingEnabled
        ? `启用「${this.pending.label}」后，相关菜单与接口将对已授权角色开放。`
        : `停用「${this.pending.label}」后，前端入口隐藏且后端直接拒绝；历史数据保留，恢复后可继续使用。`
    }
  },
  created() { this.load() },
  methods: {
    stateClass(on) {
      return on ? 'cap-tag cap-tag--on' : 'cap-tag cap-tag--off'
    },
    reasonFallback(item) {
      return (item.dependencyUnmet || []).length ? '依赖能力不可用' : ''
    },
    fmtCount(value) {
      return value === null || value === undefined ? '未知（统计不可用）' : value
    },
    askEnable(item) {
      this.pending = item
      this.pendingEnabled = true
      this.impact = null
      this.confirmOpen = true
    },
    async askDisable(item) {
      this.pending = item
      this.pendingEnabled = false
      this.impact = null
      this.busyKey = item.capabilityKey
      const res = await systemApi.getCapabilityImpact(item.capabilityKey)
      this.busyKey = ''
      if (res.code === 0) this.impact = res.data
      else toast.error(res.message)
      this.confirmOpen = true
    },
    async doSubmit({ reason }) {
      if (!this.pending) return
      this.submitting = true
      const res = await systemApi.setCapabilitySetting(this.pending.capabilityKey, {
        enabled: this.pendingEnabled,
        reason,
        expectedVersion: this.pending.version
      })
      this.submitting = false
      if (res.code === 0) {
        toast.success('模块开关已更新')
        this.confirmOpen = false
        this.pending = null
        await this.load()
      } else {
        toast.error(res.message)
        if (res.bizCode === 'DATA_CONFLICT') {
          this.confirmOpen = false
          await this.load()
        }
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await systemApi.listCapabilitySettings()
      if (res.code === 0) this.items = (res.data && res.data.list) || []
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.cap-row {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) minmax(280px, 1.4fr) minmax(180px, 1.2fr) auto;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) 0;
  border-bottom: 1px solid var(--border-light);
}
.cap-row__label { font-weight: var(--font-weight-medium); }
.cap-row__key { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.cap-row__states { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.cap-tag {
  padding: 1px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  border: 1px solid var(--border-light);
}
.cap-tag--on { color: var(--color-success); }
.cap-tag--off { color: var(--color-danger); }
.cap-btn {
  padding: 4px 12px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
  background: var(--bg-container);
  cursor: pointer;
}
.cap-btn:disabled { cursor: not-allowed; opacity: 0.5; }
.cap-btn--primary { border-color: var(--color-primary); color: var(--color-primary); }
.cap-impact__warn { color: var(--color-danger); }
.cap-impact__list { margin: var(--space-2) 0; padding-left: var(--space-4); }
</style>
