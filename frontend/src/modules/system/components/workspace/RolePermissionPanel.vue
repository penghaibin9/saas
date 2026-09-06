<template>
  <div class="sw-stack" data-testid="role-permission-panel">
    <section v-if="receipt" class="sw-alert" :class="receipt.kind === 'success' ? 'sw-alert--success' : 'sw-alert--warning'" role="status" data-testid="permission-receipt">
      <b>{{ receipt.title }}</b>
      <p>{{ receipt.message }}</p>
      <p class="sw-code">请求编号 {{ receipt.requestId }}<span v-if="receipt.version != null"> · 角色版本 {{ receipt.version }}</span></p>
    </section>
    <div v-if="state === 'loading'" class="sw-state" role="status">正在读取当前角色与可编辑权限…</div>
    <section v-else-if="state === 'error'" class="sw-alert sw-alert--error" role="alert" data-testid="permission-load-error">
      <b>权限数据未就绪，编辑与保存已暂停</b><p>{{ error }}</p>
      <button type="button" class="sw-btn sw-space" @click="load(true)">重新读取并核对</button>
    </section>
    <template v-else-if="draft && detail">
      <p v-if="error && !outcomeUnknown" class="sw-alert sw-alert--error" role="alert">{{ error }}</p>
      <div v-if="!editable" class="sw-alert" data-testid="permission-readonly">
        {{ detail.type === 'BUILTIN' ? '预设角色由已发布模板维护，请复制为自定义角色后再调整。' : '当前身份只可查看此角色，不能修改权限与数据范围。' }}
      </div>
      <div v-if="outcomeUnknown" class="sw-alert sw-alert--warning" role="alert" data-testid="permission-result-unknown">
        <b>请先重新读取，不要重复提交</b><p>{{ error }}</p>
        <button type="button" class="sw-btn sw-space" :disabled="saving" @click="load(true)">重新读取并保留我的选择</button>
      </div>
      <p v-if="reconcileNote" class="sw-alert sw-alert--warning" role="status">{{ reconcileNote }}</p>
      <template v-if="tab === 'scope'">
        <div class="sw-between"><h3>角色默认数据范围</h3><span class="sw-tag sw-tag--blue">{{ scopeLabel(draft.scopeCode) }}</span></div>
        <p class="sw-muted">调整默认口径不会替老师创建任职、负责班级或指导关系。</p>
        <div class="sw-scope-grid" data-testid="role-scope-options">
          <button v-for="option in scopeOptions" :key="option.value" type="button" class="sw-scope-choice"
            :aria-pressed="draft.scopeCode === option.value" :disabled="!editable || saving || outcomeUnknown"
            @click="draft.scopeCode = option.value">
            <b>{{ option.label }}</b><small class="sw-code" style="display:block;margin-top:5px">{{ option.value }}</small>
          </button>
        </div>
        <div class="sw-alert">具体范围目标未编辑，本次保存保留原有目标。需要调整任职范围时，请到角色成员与业务身份核对。</div>
      </template>
      <template v-else>
        <div class="sw-between">
          <label class="sw-field" style="flex:1;max-width:340px">查找权限
            <input v-model="keyword" class="sw-input" placeholder="功能名称或权限编码" aria-label="查找权限" />
          </label>
          <span class="sw-muted">{{ editable ? '已选' : '已生效' }} {{ selection.length }} 项权限</span>
        </div>
        <div class="sw-permission-layout">
          <div>
            <section v-for="group in filteredGroups" :key="group.key" class="sw-permission-group">
              <header class="sw-permission-head"><b>{{ group.label }}</b><span class="sw-muted">{{ group.rows.length }} 项</span></header>
              <div class="sw-permission-grid">
                <label v-for="node in group.rows" :key="node.key" class="sw-permission-row" :data-permission="node.key">
                  <input class="sw-check" type="checkbox" :checked="selection.includes(node.key)"
                    :aria-label="node.label" :disabled="!editable || saving || outcomeUnknown || (node.parentKey && !draft.menuKeys.includes(node.parentKey))"
                    @change="toggle(node, $event.target.checked)" />
                  <span><b>{{ node.label }}</b><code>{{ node.key }}</code>
                    <small v-if="node.parentKey && !draft.menuKeys.includes(node.parentKey)" class="sw-muted">先选择所属入口：{{ permissionLabel(node.parentKey) }}</small>
                  </span>
                  <small class="sw-tag" :class="highRisk(node) ? 'sw-tag--orange' : ''">{{ highRisk(node) ? '高风险操作' : node.advanced ? '后台能力' : node.selectionType === 'menu' ? '入口' : '操作' }}</small>
                </label>
              </div>
            </section>
            <div v-if="!filteredGroups.length" class="sw-state"><b>没有匹配的权限</b><p class="sw-muted">搜索只影响显示，不改变已选权限。</p></div>
          </div>
          <aside class="sw-preview" aria-label="角色菜单样式预览">
            <h3>老师将看到的入口</h3>
            <p>此处只预览选中的导航入口；实际可用性仍由服务端授权与业务范围决定。</p>
            <div class="sw-preview-menus">
              <div v-for="node in previewMenus" :key="node.key" class="sw-preview-menu">{{ node.label }}</div>
              <div v-if="!previewMenus.length" class="sw-preview-menu">未选择常规菜单入口</div>
            </div>
            <p>隐藏入口不等于撤销接口权限；后台能力不会伪装成菜单。</p>
          </aside>
        </div>
      </template>
      <details v-if="preserved.length" class="sw-card sw-pad" data-testid="readonly-preserved-permissions">
        <summary>只读保留 {{ preserved.length }} 项权限</summary>
        <div v-for="item in preserved" :key="item.permissionCode" class="sw-space">
          <b>{{ item.label || item.permissionCode }}</b><p class="sw-code">{{ item.permissionCode }}</p><p class="sw-muted">{{ item.reason }}</p>
        </div>
      </details>
      <div class="sw-savebar">
        <div><b>本次新增 {{ delta.added.length }} 项，移除 {{ delta.removed.length }} 项</b>
          <p>默认范围 {{ scopeChanged ? `${scopeLabel(base.scopeCode)} → ${scopeLabel(draft.scopeCode)}` : '保持不变' }} · 版本 {{ draft.version }}</p>
        </div>
        <div class="sw-row">
          <button type="button" class="sw-btn" :disabled="!editable || saving || outcomeUnknown || !isDirty" @click="resetDraft">还原选择</button>
          <button type="button" class="sw-btn sw-btn--primary" data-testid="A017-review" :disabled="!canReview" @click="reviewOpen = true">核对变更 →</button>
        </div>
      </div>
    </template>
    <AppConfirmDialog :visible="reviewOpen" title="核对角色权限变更" type="warning" size="wide"
      confirm-text="确认保存权限" require-reason reason-label="调整原因" :submitting="saving" :confirm-disabled="!canReview" :initial-reason="lastReason"
      @update:visible="closeReview" @confirm="save">
      <div v-if="draft && base" class="sw-stack">
        <p><b>{{ detail?.name }}</b> · 当前版本 {{ draft.version }} · 成员 {{ countLabel(detail?.memberCount) }} 人</p>
        <div class="sw-diff">
          <div><b>移除 {{ delta.removed.length }} 项</b><p v-for="code in delta.removed" :key="code" class="sw-removed">− {{ permissionLabel(code) }}</p><p v-if="!delta.removed.length">无移除</p></div>
          <div><b>新增 {{ delta.added.length }} 项</b><p v-for="code in delta.added" :key="code" class="sw-added">＋ {{ permissionLabel(code) }}</p><p v-if="!delta.added.length">无新增</p></div>
        </div>
        <p>默认范围：{{ scopeLabel(base.scopeCode) }} → {{ scopeLabel(draft.scopeCode) }}。具体目标未修改。</p>
        <p class="sw-muted">保存直接更新本校角色权限，不代表已发起另一个安全变更审批。</p>
      </div>
    </AppConfirmDialog>
  </div>
</template>

<script>
import AppConfirmDialog from './WorkspaceConfirmDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import * as wc from '@/modules/system/utils/workspaceContract'

export default {
  name: 'RolePermissionPanel',
  components: { AppConfirmDialog },
  props: { ctx: { type: Object, required: true }, roleId: { type: String, required: true }, tab: { type: String, default: 'permissions' }, locked: { type: Boolean, default: false } },
  emits: ['loaded', 'saved', 'dirty', 'busy'],
  data() {
    return { state: 'loading', error: '', detail: null, draft: null, base: null, fence: null,
      saving: false, reviewOpen: false, outcomeUnknown: false, receipt: null, keyword: '', reconcileNote: '', lastReason: '' }
  },
  computed: {
    contextKey() { return wc.contextFingerprint(this.ctx) },
    selection() { return this.draft ? [...this.draft.menuKeys, ...this.draft.buttonKeys] : [] },
    delta() { return this.base ? wc.permissionDelta([...this.base.menuKeys, ...this.base.buttonKeys], this.selection) : { added: [], removed: [] } },
    scopeChanged() { return !!this.base && this.base.scopeCode !== this.draft?.scopeCode },
    isDirty() { return !!(this.scopeChanged || this.delta.added.length || this.delta.removed.length) },
    editable() { return this.state === 'ready' && this.detail?.type === 'CUSTOM' && wc.actionAllowed(this.ctx, 'configRolePermission') && !this.locked },
    canReview() { return this.editable && this.isDirty && !this.saving && !this.outcomeUnknown },
    preserved() { return Array.isArray(this.detail?.readOnlyPreservedPermissions) ? this.detail.readOnlyPreservedPermissions : [] },
    scopeOptions() { return this.ctx.statusOptions?.scopeTypes || [] },
    previewMenus() { return this.draft ? wc.visibleMenuPreview(this.draft.groups, this.draft.menuKeys) : [] },
    filteredGroups() {
      const keyword = this.keyword.trim().toLowerCase()
      return (this.draft?.groups || []).map(group => ({ ...group, rows: group.rows.filter(node => !keyword || `${node.label} ${node.key}`.toLowerCase().includes(keyword)) })).filter(group => group.rows.length)
    }
  },
  watch: {
    isDirty(value) { this.$emit('dirty', value) },
    contextKey() { this.fence.invalidate(); this.clear(); this.load() },
    roleId() { this.fence.invalidate(); this.clear(); this.load() }
  },
  created() { this.fence = wc.createRequestFence(); this.load() },
  beforeUnmount() { this.fence.invalidate() },
  methods: {
    countLabel: wc.countLabel,
    scopeLabel(code) { return this.scopeOptions.find(option => option.value === code)?.label || code || '未取得' },
    highRisk(node) { return ['HIGH', 'CRITICAL'].includes(String(node.riskLevel || '').toUpperCase()) },
    permissionLabel(code) { return this.draft?.groups.flatMap(group => group.rows).find(node => node.key === code)?.label || code },
    clear() { this.saving = false; this.$emit('busy', false); this.detail = null; this.draft = null; this.base = null; this.receipt = null; this.outcomeUnknown = false; this.reviewOpen = false; this.reconcileNote = ''; this.lastReason = ''; this.$emit('dirty', false) },
    async load(preserve = false) {
      if (this.saving) return
      const current = this.fence.start('read')
      const id = this.roleId
      const old = preserve && this.draft ? JSON.parse(JSON.stringify(this.draft)) : null
      this.state = 'loading'; this.error = ''; this.reviewOpen = false
      try {
        const detail = wc.unwrap(await systemApi.getRoleDetail(id))
        if (!current()) return
        const writable = detail?.type === 'CUSTOM' && wc.actionAllowed(this.ctx, 'configRolePermission')
        const next = writable
          ? wc.makePermissionDraft(wc.unwrap(await systemApi.getPermissionTree()), detail, id)
          : wc.makeReadOnlyDraft(detail, id)
        if (!current()) return
        this.base = JSON.parse(JSON.stringify(next))
        this.draft = next
        if (old && writable) {
          const nodes = next.groups.flatMap(group => group.rows)
          const menu = new Set(nodes.filter(node => node.selectionType === 'menu').map(node => node.key))
          const buttons = new Set(nodes.filter(node => node.selectionType === 'button').map(node => node.key))
          this.draft.menuKeys = old.menuKeys.filter(code => menu.has(code))
          this.draft.buttonKeys = old.buttonKeys.filter(code => buttons.has(code))
          if (this.scopeOptions.some(option => option.value === old.scopeCode)) this.draft.scopeCode = old.scopeCode
          this.reconcileNote = '已重新读取服务器版本并保留仍可编辑的选择。请核对最新差异，再决定是否保存；没有自动重试。'
        }
        this.detail = detail; this.state = 'ready'; this.outcomeUnknown = false
        this.$emit('loaded', detail)
      } catch (error) {
        if (current()) { this.state = 'error'; this.error = error.message || '权限数据读取失败' }
      }
    },
    toggle(node, checked) {
      if (!this.editable || this.saving || this.outcomeUnknown) return
      this.draft = wc.changePermission(this.draft, node, checked)
    },
    resetDraft() { if (this.canReview) { this.draft = JSON.parse(JSON.stringify(this.base)); this.reconcileNote = '' } },
    closeReview(visible) { if (!this.saving) this.reviewOpen = visible },
    async save({ reason }) {
      if (!this.canReview || this.saving) return
      let args
      try { args = wc.permissionSaveArgs(this.draft, reason, wc.newRequestId()) }
      catch (error) { this.error = error.message; this.reviewOpen = false; return }
      this.lastReason = reason.trim()
      const current = this.fence.start('write')
      this.saving = true; this.$emit('busy', true); this.error = ''
      let saved = false
      try {
        const result = wc.unwrap(await systemApi.saveRolePermissions(this.roleId, args))
        if (!current()) return
        if (!result || String(result.id) !== this.roleId || !Number.isInteger(result.version)) throw new Error('回执不完整，请读取角色详情确认结果')
        this.receipt = { kind: result.cacheInvalidated === true ? 'success' : 'warning',
          title: result.cacheInvalidated === true ? '角色权限已保存' : '权限已提交，缓存刷新需核对',
          message: result.cacheInvalidated === true ? '已收到服务端保存回执，正在重新读取角色配置。' : '权限事实已提交。请核对成员会话刷新；不要为刷新缓存再次保存同一变更。',
          requestId: args.requestId, version: result.version }
        this.base = JSON.parse(JSON.stringify(this.draft)); this.reviewOpen = false; this.reconcileNote = ''
        this.$emit('saved', result); saved = true
      } catch (error) {
        if (current()) {
          this.outcomeUnknown = true; this.error = error.message || '未取得保存结果'; this.reviewOpen = false
          this.receipt = { kind: 'warning', title: '本次保存需要重新核对', message: '尚未确认当前服务器状态，已阻止连续重复提交。', requestId: args.requestId, version: null }
        }
      } finally {
        if (current()) { this.saving = false; this.$emit('busy', false) }
      }
      if (saved && current()) await this.load(false)
    }
  }
}
</script>
