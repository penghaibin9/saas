<template>
  <SystemWorkspaceFrame title="模块与业务开关" subtitle="平台授权只读；学校在已获授权范围内逐项启停。" :ctx="ctx">
    <template #actions><button type="button" class="sw-btn" :disabled="loading || submitting" @click="load">刷新状态</button></template>
    <div v-if="receipt" class="sw-alert" role="status">{{ receipt }}</div>
    <div v-if="!canWrite" class="sw-alert">当前身份只可查看，不能修改学校开关。</div>
    <div v-if="loading" class="sw-state" role="status">正在读取本校模块授权…</div>
    <div v-else-if="error" class="sw-alert sw-alert--error" role="alert">{{ error }}<button type="button" class="sw-btn" @click="load">重新读取</button></div>
    <div v-else-if="!items.length" class="sw-card sw-state">当前没有返回学校可见模块。</div>
    <div v-else class="sw-role-grid" data-testid="capability-grid">
      <article v-for="item in items" :key="item.capabilityKey" class="sw-card sw-pad sw-stack sw-capability-card" :data-capability="item.capabilityKey">
        <div class="sw-capability-head"><span class="sw-symbol"><AppIcon name="workbench" :size="22" /></span><h2>{{ item.label }}</h2><span class="sw-tag" :class="item.allowed ? 'sw-tag--green' : 'sw-tag--orange'">{{ item.allowed ? '当前可用' : '当前不可用' }}</span></div>
        <p class="sw-code">{{ item.capabilityKey }} · 版本 {{ countLabel(item.version) }}</p>
        <dl class="cap-state-grid"><div><dt>平台授权</dt><dd>{{ boolLabel(item.entitled) }}</dd></div><div><dt>学校开关</dt><dd>{{ boolLabel(item.schoolEnabled, '已启用', '已关闭') }}</dd></div><div><dt>准备就绪</dt><dd>{{ boolLabel(item.ready) }}</dd></div><div><dt>当前可用</dt><dd>{{ boolLabel(item.allowed) }}</dd></div></dl>
        <p class="sw-muted" :title="item.reasonCode || ''">{{ item.reasonText || (item.expiresAt ? `启用至 ${item.expiresAt}` : item.reasonCode === 'OK' ? '各项状态正常' : '状态说明未取得，请刷新核对') }}</p>
        <div class="sw-between cap-footer"><span class="sw-muted">学校开关</span><button type="button" class="cap-switch" role="switch" :aria-checked="item.schoolEnabled === true"
          :aria-label="`${item.label}学校开关`" :disabled="!canWrite || submitting || uncertain || !validItem(item) || (!item.schoolEnabled && (!item.entitled || (item.dependencyUnmet || []).length > 0))"
          :title="!canWrite ? '只读身份' : !item.entitled ? '未授权，不能由学校开通' : ''" @click="prepare(item)"><span /></button></div>
      </article>
    </div>
    <WorkspaceConfirmDialog :visible="!!pending" :title="pendingEnabled ? '启用学校模块' : '停用前核对影响'" :type="pendingEnabled ? 'warning' : 'danger'" size="wide"
      :confirm-text="pendingEnabled ? '确认启用' : '确认停用'" require-reason reason-label="调整原因" :initial-reason="lastReason" :submitting="submitting" :confirm-disabled="!canConfirm" @update:visible="close" @confirm="submit">
      <div v-if="pending" class="sw-stack">
        <p><b>{{ pending.label }}</b> · 原学校开关 {{ pending.schoolEnabled ? '已启用' : '已关闭' }} · 版本 {{ pending.version }}</p>
        <p v-if="pendingEnabled" class="sw-alert">仅调整学校开关，不更改商业授权、成员权限或历史数据；启用后仍需核对准备状态。</p>
        <template v-else>
          <p v-if="impactState === 'loading'" role="status">正在取得当前模块停用影响，暂不能确认…</p>
          <div v-else-if="impactState === 'error'" class="sw-alert sw-alert--error" role="alert" data-testid="impact-error"><b>停用影响未取得，不能继续确认</b><p>{{ impactError }}</p><button type="button" class="sw-btn sw-space" @click="loadImpact">重试影响查询</button></div>
          <template v-else-if="impact">
            <div class="sw-form"><div v-for="(label, key) in countLabels" :key="key"><small>{{ label }}</small><h2>{{ countLabel(impact.counts?.[key]) }}</h2></div></div>
            <p class="sw-alert sw-alert--warning">{{ impact.countsExact === true ? '按服务端返回口径统计。' : '这是非精确统计，历史来源标识不完整可能少计；未知不是零。' }} {{ impact.note }}</p>
            <p v-if="impact.cascadeDisabled?.length">连带不可用：{{ impact.cascadeDisabled.map(row => row.label).join('、') }}</p>
            <details><summary>展开菜单、接口与涉及角色</summary><p class="sw-code">菜单：{{ (impact.menus || []).join('、') || '未返回' }}</p><p class="sw-code">接口：{{ (impact.apis || []).join('、') || '未返回' }}</p><p class="sw-code">角色：{{ (impact.affectedRoles || []).join('、') || '未返回' }}</p></details>
          </template>
        </template>
        <div v-if="uncertain" class="sw-alert sw-alert--warning" role="alert"><b>先读取当前状态，再决定后续操作</b><p>{{ writeError }}</p><button type="button" class="sw-btn sw-space" :disabled="submitting" @click="reconcile">重新读取并核对</button></div>
        <p v-if="reconcileNote" class="sw-alert">{{ reconcileNote }}</p>
      </div>
    </WorkspaceConfirmDialog>
  </SystemWorkspaceFrame>
</template>
<script>
import AppIcon from '@/components/ui/AppIcon.vue'
import SystemWorkspaceFrame from '../components/workspace/SystemWorkspaceFrame.vue'
import WorkspaceConfirmDialog from '../components/workspace/WorkspaceConfirmDialog.vue'
import { systemApi } from '../api/system.api'
import { matchPermission } from '@/config/navPlan'
import { contextFingerprint, createRequestFence, unwrap, capabilityCanConfirm, countLabel } from '../utils/workspaceContract'
export default {
  name: 'SystemModuleFeatureView', components: { AppIcon, SystemWorkspaceFrame, WorkspaceConfirmDialog }, props: { ctx: { type: Object, required: true } },
  data() { return { items: [], loading: true, error: '', fence: null, pending: null, pendingEnabled: false, pendingContext: '', impact: null, impactState: 'idle', impactError: '', submitting: false, uncertain: false, writeError: '', receipt: '', lastReason: '', reconcileNote: '', countLabels: { affectedUsers: '受影响用户', runningWorkflows: '进行中流程', pendingTodos: '待办任务', fileBindings: '关联文件' } } },
  computed: {
    contextKey() { return contextFingerprint(this.ctx) },
    canWrite() { return Array.isArray(this.ctx.permissionPatterns) && matchPermission(this.ctx.permissionPatterns, 'systemAdmin.config.manage') },
    canConfirm() { return !this.uncertain && capabilityCanConfirm({ canWrite: this.canWrite, busy: this.submitting, item: this.pending, enabled: this.pendingEnabled, impactState: this.impactState, impact: this.impact, contextMatches: this.pendingContext === this.contextKey }) }
  },
  watch: { contextKey() { this.fence.invalidate(); this.pending = null; this.submitting = false; this.uncertain = false; this.items = []; this.receipt = ''; this.lastReason = ''; this.load() } },
  created() { this.fence = createRequestFence(); this.load() }, beforeUnmount() { this.fence.invalidate() },
  beforeRouteLeave() { return !this.submitting },
  methods: {
    countLabel,
    boolLabel(value, yes = '是', no = '否') { return value === true ? yes : value === false ? no : '未取得' },
    validItem(item) { return typeof item.schoolEnabled === 'boolean' && Number.isInteger(item.version) && item.version >= 0 },
    async load() {
      if (this.submitting) return false
      const current = this.fence.start('list'); this.loading = true; this.error = ''
      try { const data = unwrap(await systemApi.listCapabilitySettings()); if (!current()) return false; if (!Array.isArray(data?.list)) throw new Error('模块列表结构不完整'); this.items = data.list; if (!this.pending) this.uncertain = false; return true }
      catch (error) { if (current()) this.error = error.message; return false }
      finally { if (current()) this.loading = false }
    },
    prepare(item) {
      if (!this.canWrite || this.submitting || this.uncertain || !this.validItem(item)) return
      this.pending = { ...item }; this.pendingEnabled = !item.schoolEnabled; this.pendingContext = this.contextKey
      this.lastReason = ''; this.writeError = ''; this.reconcileNote = ''; this.impact = null; this.impactState = 'idle'
      if (!this.pendingEnabled) this.loadImpact()
    },
    close(visible) { if (!visible && !this.submitting) { this.fence.start('impact'); this.pending = null; this.impact = null; if (this.uncertain) this.receipt = '上次写入结果需要核对；再次操作前请先刷新模块状态。' } },
    async loadImpact() {
      if (!this.pending || this.pendingEnabled || this.submitting) return
      const key = this.pending.capabilityKey, current = this.fence.start('impact')
      this.impact = null; this.impactState = 'loading'; this.impactError = ''
      try { const data = unwrap(await systemApi.getCapabilityImpact(key)); if (!current() || key !== this.pending?.capabilityKey) return; if (data?.capabilityKey !== key) throw new Error('影响结果与当前模块不一致'); this.impact = data; this.impactState = 'ready' }
      catch (error) { if (current()) { this.impactState = 'error'; this.impactError = error.message } }
    },
    async submit({ reason }) {
      if (!this.canConfirm || reason.trim().length < 5) return
      const key = this.pending.capabilityKey, current = this.fence.start('write')
      this.lastReason = reason.trim(); this.submitting = true; this.writeError = ''
      try {
        const data = unwrap(await systemApi.setCapabilitySetting(key, { enabled: this.pendingEnabled, expectedVersion: this.pending.version, reason: this.lastReason }))
        if (!current()) return
        if (data?.capabilityKey !== key || !this.validItem(data) || data.schoolEnabled !== this.pendingEnabled) throw new Error('回执不完整，请重新读取模块状态')
        this.receipt = `「${data.label}」学校开关已${data.schoolEnabled ? '启用' : '关闭'}，版本 ${data.version}；平台授权未改变。`
        this.pending = null; this.submitting = false; await this.load()
      } catch (error) {
        if (current()) { this.uncertain = true; this.writeError = error.message || '未取得写入结果'; this.impactState = 'idle' }
      } finally { if (current()) this.submitting = false }
    },
    async reconcile() {
      if (!this.pending || this.submitting) return
      const key = this.pending.capabilityKey, desired = this.pendingEnabled, context = this.contextKey
      if (!await this.load() || context !== this.contextKey || key !== this.pending?.capabilityKey) return
      const fresh = this.items.find(item => item.capabilityKey === key)
      if (!fresh || !this.validItem(fresh)) { this.writeError = '未取得可核对的模块状态，请再次读取'; return }
      if (fresh.schoolEnabled === desired) { this.receipt = '服务器当前开关已与目标一致；未重复提交。请到审计记录核对原操作。'; this.pending = null; this.uncertain = false; return }
      this.pending = { ...fresh }; this.uncertain = false; this.reconcileNote = '已读取最新版本并保留调整原因。请重新核对影响后明确确认；没有自动重试写入。'
      if (!desired) await this.loadImpact()
    }
  }
}
</script>
<!-- Capability presentation is scoped in workspace.css; write guards remain above. -->
