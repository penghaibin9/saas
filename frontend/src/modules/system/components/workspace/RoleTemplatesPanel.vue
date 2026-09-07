<template>
  <div class="sw-stack" data-testid="role-templates-panel">
    <div class="sw-between"><p class="sw-muted">已发布模板只读；学校角色固定来源版本，不自动跟随模板升级。</p><button type="button" class="sw-btn" :disabled="loading || busy" @click="load">刷新模板</button></div>
    <div v-if="loading" class="sw-state" role="status">正在读取学校可用模板…</div>
    <div v-else-if="error" class="sw-alert sw-alert--error" role="alert">{{ error }}<button type="button" class="sw-btn" @click="load">重新读取</button></div>
    <div v-else-if="!templates.length" class="sw-card sw-state"><h3>暂无已发布的学校模板</h3><p class="sw-muted">请联系平台管理员核对发布状态；这里不会自动初始化或伪造模板。</p></div>
    <div v-else class="sw-role-grid">
      <article v-for="item in templates" :key="item.id" class="sw-card sw-role-card">
        <div class="sw-between"><h3>{{ item.templateName || item.templateCode }}</h3><span class="sw-tag sw-tag--blue">第 {{ item.templateVersion }} 版</span></div>
        <p class="sw-code">{{ item.templateCode }}</p>
        <div class="sw-role-stats"><div><strong>{{ Array.isArray(item.permissions) ? item.permissions.length : '未取得' }}</strong><small>模板权限</small></div><div><strong>{{ countLabel(item.schoolPinnedCustomRoleCount) }}</strong><small>本校绑定角色</small></div></div>
        <div class="sw-row"><button type="button" class="sw-btn" :disabled="impactLoading || busy" @click="readImpact(item)">核对本校影响</button><button v-if="canCreate" type="button" class="sw-btn sw-btn--primary" :disabled="busy" @click="$emit('create', item.templateCode)">以此为来源创建</button></div>
      </article>
    </div>
    <section v-if="impactLoading || impactError || impact" class="sw-card sw-pad sw-stack" data-testid="template-impact">
      <div class="sw-between"><h3>模板影响 · {{ impactLabel }}</h3><button type="button" class="sw-link" @click="closeImpact">关闭</button></div>
      <p v-if="impactLoading" role="status">正在核对本校绑定角色…</p>
      <p v-else-if="impactError" class="sw-alert sw-alert--error" role="alert">{{ impactError }}<button type="button" class="sw-btn" @click="readImpact(impactTarget)">重新读取</button></p>
      <template v-else-if="impact">
        <p class="sw-alert">本校影响角色 {{ countLabel(impact.affectedPinnedCustomRoleCount) }} 个。{{ impact.automaticUpgrade === false ? '自动升级关闭；查看影响不会修改任何权限。' : '自动升级状态需核对；本页没有执行升级。' }}</p>
        <div class="sw-table-wrap"><table class="sw-table"><thead><tr><th>本校角色</th><th>来源版本 / 当前角色版本</th><th>升级将新增</th><th>升级将移除</th></tr></thead><tbody>
          <tr v-for="row in impact.roles || []" :key="row.roleCode"><td><b>{{ row.roleName || row.roleCode }}</b><small v-if="row.runtimeRoleMissing">运行角色缺失</small></td><td>{{ row.sourceTemplateVersion ?? '未取得' }} / {{ row.roleVersion ?? '未取得' }}</td><td class="sw-code">{{ codeList(row.wouldAdd) }}</td><td class="sw-code">{{ codeList(row.wouldRemove) }}</td></tr>
          <tr v-if="!(impact.roles || []).length"><td colspan="4">本校没有返回受影响的绑定角色。</td></tr>
        </tbody></table></div>
      </template>
    </section>
    <details class="sw-card sw-pad" @toggle="onGovernanceToggle" data-testid="wildcard-governance">
      <summary>通配权限治理与来源核对</summary>
      <p class="sw-muted">保留原有治理能力，只有明确确认后才执行初始化，不在打开页面时自动写入。</p>
      <p v-if="governanceLoading" role="status">正在读取治理目录…</p>
      <p v-else-if="governanceError" class="sw-alert sw-alert--error" role="alert">{{ governanceError }}</p>
      <div v-else-if="governanceLoaded" class="sw-table-wrap sw-space"><table class="sw-table"><thead><tr><th>角色 / 通配</th><th>展开数量</th><th>状态 / 说明</th></tr></thead><tbody>
        <tr v-for="item in wildcards" :key="`${item.roleCode}:${item.wildcardCode}`"><td>{{ item.roleCode }}<small class="sw-code">{{ item.wildcardCode }}</small></td><td>{{ countLabel(item.expandedCount) }}</td><td>{{ wildcardLabel(item.status) }}<small>{{ item.note }}</small></td></tr>
        <tr v-if="!wildcards.length"><td colspan="3">当前没有返回治理记录；这不等于已证明所有历史权限均已退役。</td></tr>
      </tbody></table></div>
      <p v-if="disclaimer" class="sw-muted sw-space">{{ disclaimer }}</p>
      <div class="sw-row sw-space"><button type="button" class="sw-btn" :disabled="busy || governanceLoading" @click="loadGovernance">重新读取</button><button v-if="canBootstrap" type="button" class="sw-btn" :disabled="busy || bootstrapBlocked" @click="confirmOpen = true">初始化权限治理目录</button></div>
      <p v-if="bootstrapMessage" class="sw-alert sw-space" role="status">{{ bootstrapMessage }}</p>
    </details>
    <AppConfirmDialog :visible="confirmOpen" title="初始化学校权限治理目录" message="沿用现有治理初始化接口；不修改当前角色的成员分配。请确认本次维护。" confirm-text="确认初始化" :submitting="busy" :confirm-disabled="!canBootstrap || bootstrapBlocked" @update:visible="closeConfirm" @confirm="bootstrap" />
  </div>
</template>
<script>
import AppConfirmDialog from '@/modules/system/components/workspace/WorkspaceConfirmDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { schoolIamApi } from '@/modules/system/api/schoolIam.api'
import * as wc from '@/modules/system/utils/workspaceContract'
export default {
  name: 'RoleTemplatesPanel', components: { AppConfirmDialog }, props: { ctx: { type: Object, required: true } }, emits: ['create', 'busy'],
  data() { return { templates: [], loading: true, error: '', fence: null, impact: null, impactTarget: null, impactLabel: '', impactLoading: false, impactError: '', wildcards: [], disclaimer: '', governanceLoading: false, governanceError: '', governanceLoaded: false, busy: false, confirmOpen: false, bootstrapBlocked: false, bootstrapMessage: '' } },
  computed: { contextKey() { return wc.contextFingerprint(this.ctx) }, canCreate() { return wc.actionAllowed(this.ctx, 'createRole') }, canBootstrap() { return wc.actionAllowed(this.ctx, 'configRolePermission') } },
  watch: { contextKey() { this.fence.invalidate(); this.templates = []; this.closeImpact(); this.wildcards = []; this.disclaimer = ''; this.governanceLoaded = false; this.governanceLoading = false; this.governanceError = ''; this.busy = false; this.confirmOpen = false; this.bootstrapBlocked = false; this.bootstrapMessage = ''; this.$emit('busy', false); this.load() } },
  created() { this.fence = wc.createRequestFence(); this.load() }, beforeUnmount() { this.fence.invalidate() },
  methods: {
    countLabel: wc.countLabel,
    codeList(value) { return Array.isArray(value) ? value.join('、') || '无' : '未取得' },
    wildcardLabel(value) { return { PENDING: '待处理', PLANNED: '已排期', RETIRED: '已退役' }[value] || '状态待核对' },
    async load() {
      const current = this.fence.start('templates'); this.loading = true; this.error = ''
      try { const data = wc.unwrap(await schoolIamApi.roleTemplates()); if (!current()) return; if (!Array.isArray(data?.items)) throw new Error('模板目录结构异常'); this.templates = data.items }
      catch (error) { if (current()) this.error = error.message || '模板读取失败' }
      finally { if (current()) this.loading = false }
    },
    async readImpact(item) {
      if (!item?.id || this.busy) return
      const current = this.fence.start('impact'); this.impactTarget = item; this.impactLabel = `${item.templateName || item.templateCode} · 第 ${item.templateVersion} 版`; this.impact = null; this.impactError = ''; this.impactLoading = true
      try { const data = wc.unwrap(await schoolIamApi.templateImpact(item.id)); if (!current()) return; if (!data || data.templateCode !== item.templateCode || Number(data.templateVersion) !== Number(item.templateVersion) || !Array.isArray(data.roles)) throw new Error('影响结果与当前模板不一致'); this.impact = data }
      catch (error) { if (current()) this.impactError = error.message || '影响读取失败' }
      finally { if (current()) this.impactLoading = false }
    },
    closeImpact() { this.fence.start('impact'); this.impact = null; this.impactTarget = null; this.impactLoading = false; this.impactError = '' },
    onGovernanceToggle(event) { if (event.target.open && !this.governanceLoaded && !this.governanceLoading) this.loadGovernance() },
    async loadGovernance() {
      const current = this.fence.start('governance'); this.governanceLoading = true; this.governanceError = ''
      try { const data = wc.unwrap(await systemApi.getWildcardRetirement()); if (!current()) return; if (!Array.isArray(data?.items)) throw new Error('治理目录结构异常'); this.wildcards = data.items; this.disclaimer = data.disclaimer || ''; this.governanceLoaded = true }
      catch (error) { if (current()) this.governanceError = error.message || '治理目录读取失败' }
      finally { if (current()) this.governanceLoading = false }
    },
    closeConfirm(visible) { if (!this.busy) this.confirmOpen = visible },
    async bootstrap() {
      if (!this.canBootstrap || this.busy || this.bootstrapBlocked) return
      const current = this.fence.start('bootstrap'); this.busy = true; this.$emit('busy', true)
      try { wc.unwrap(await systemApi.bootstrapPermissionGovernance()); if (!current()) return; this.bootstrapMessage = '已收到初始化回执，请核对最新治理目录。'; this.confirmOpen = false; await this.loadGovernance() }
      catch (error) { if (current()) { this.bootstrapMessage = `结果需核对：${error.message}。本次不会自动重试。`; this.bootstrapBlocked = true; this.confirmOpen = false } }
      finally { if (current()) { this.busy = false; this.$emit('busy', false) } }
    }
  }
}
</script>
