<template>
  <SystemWorkspaceFrame :title="pageTitle" subtitle="选角色，核对权限与范围，再配置成员。" :ctx="ctx">
    <template #actions>
      <button type="button" class="sw-btn" :disabled="busy" @click="$router.push('/admin/system/iam?surface=diagnostics')">治理概览</button>
      <button type="button" class="sw-btn" :disabled="busy" @click="refresh">刷新目录</button>
      <button v-if="can('createRole')" type="button" class="sw-btn sw-btn--primary" :disabled="busy" data-testid="A012-open" @click="openCreate">＋ 新增角色</button>
    </template>
    <div v-if="flash" class="sw-alert" :class="mutationBlocked ? 'sw-alert--warning' : ''" role="status">{{ flash }}
      <button v-if="mutationBlocked" type="button" class="sw-btn sw-space" @click="recheckMutation">重新读取角色目录</button>
    </div>
    <section v-if="form" class="sw-card sw-pad sw-stack" data-testid="role-form">
      <div class="sw-between"><div><h2>{{ form.id ? '修改角色名称' : '创建学校自定义角色' }}</h2><p class="sw-muted">{{ form.id ? '角色编码、权限与数据范围分别管理，此处只保存名称。' : '选择已发布的学校模板作为来源；创建后继续配置权限，不自动授予模板全部权限。' }}</p></div>
        <button type="button" class="sw-btn" :disabled="busy" @click="closeForm">返回</button></div>
      <div class="sw-form">
        <label class="sw-field">角色名称<input v-model="form.name" class="sw-input" maxlength="100" aria-label="角色名称" :disabled="busy" /></label>
        <label class="sw-field">角色编码<input v-model="form.code" class="sw-input" maxlength="50" :readonly="!!form.id" :disabled="busy" placeholder="留空由系统生成" /></label>
        <template v-if="!form.id">
          <label class="sw-field">已发布来源模板<select v-model="form.sourceTemplateCode" aria-label="已发布来源模板" class="sw-input" :disabled="busy || sourceLoading"><option value="">{{ sourceLoading ? '正在读取模板…' : '请选择模板' }}</option>
            <option v-for="item in sourceTemplates" :key="item.id" :value="item.templateCode">{{ item.templateName || item.templateCode }} · 第 {{ item.templateVersion }} 版</option></select></label>
          <label class="sw-field">默认数据范围<select v-model="form.scopeCode" aria-label="默认数据范围" class="sw-input" :disabled="busy"><option v-for="item in scopeOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
        </template>
      </div>
      <p v-if="formError" class="sw-alert sw-alert--error" role="alert">{{ formError }}</p>
      <div class="sw-savebar"><p class="sw-muted">{{ form.id ? '名称修改沿用现有接口；不声称此接口已具备版本比较。' : '新角色初始无权限，成员不会自动加入。' }}</p>
        <button type="button" class="sw-btn sw-btn--primary" :disabled="busy || mutationBlocked || (!form.id && (sourceLoading || !sourceTemplates.length))" data-testid="A012-save" @click="saveForm">{{ form.id ? '保存名称' : '创建并继续配置' }}</button></div>
    </section>
    <template v-else>
      <div v-if="mode === 'roles' || mode === 'templates'" class="sw-tabs" role="tablist" aria-label="角色目录类型">
        <button type="button" role="tab" :aria-selected="mode === 'roles'" @click="showCatalog('roles')">学校角色</button>
        <button type="button" role="tab" :aria-selected="mode === 'templates'" @click="showCatalog('templates')">已发布模板</button>
      </div>
      <RoleTemplatesPanel v-if="mode === 'templates'" :ctx="ctx" @create="openCreate" @busy="auxBusy = $event" />
      <template v-else-if="mode === 'roles'">
        <form class="sw-card sw-pad sw-row" @submit.prevent="search">
          <input v-model="filters.keyword" class="sw-input" style="flex:1;min-width:180px" placeholder="搜索角色名称 / 编码" aria-label="搜索学校角色" />
          <select v-model="filters.type" class="sw-input" style="width:auto" aria-label="角色类型"><option value="">全部角色</option><option value="CUSTOM">自定义角色</option><option value="BUILTIN">预设角色</option></select>
          <select v-model="filters.status" class="sw-input" style="width:auto" aria-label="角色状态"><option value="">全部状态</option><option value="ENABLED">启用中</option><option value="DEPRECATED">已停用</option></select>
          <button type="submit" class="sw-btn" :disabled="busy || listing.loading">查询</button><button type="button" class="sw-btn" :disabled="busy" @click="clearFilters">重置</button>
        </form>
        <div v-if="listing.loading" class="sw-state" role="status">正在读取学校角色…</div>
        <div v-else-if="listing.error" class="sw-alert sw-alert--error" role="alert">{{ listing.error }}<button type="button" class="sw-btn" @click="loadRoles">重试</button></div>
        <div v-else-if="!listing.rows.length" class="sw-card sw-state"><h2>没有符合条件的角色</h2><p class="sw-muted">调整筛选，或从已发布模板建立本校角色。</p></div>
        <div v-else class="sw-role-grid">
          <article v-for="row in listing.rows" :key="row.id" class="sw-card sw-role-card" :data-role-id="row.id" data-testid="role-card">
            <div class="sw-between"><div class="sw-row"><span class="sw-symbol" aria-hidden="true">◇</span><div><h3>{{ row.name }}</h3><p class="sw-muted">{{ row.statusLabel }}</p></div></div><span class="sw-tag" :class="row.type === 'CUSTOM' ? 'sw-tag--blue' : ''">{{ row.typeLabel }}</span></div>
            <div class="sw-code">{{ row.code }}</div>
            <div class="sw-role-stats"><div><strong>{{ countLabel(row.memberCount) }}</strong><small>角色成员</small></div><div><strong style="font-size:15px;padding-top:5px">{{ scopeLabel(row.scopeCode) }}</strong><small>默认范围</small></div><div><strong>{{ countLabel(row.version) }}</strong><small>当前版本</small></div></div>
            <div class="sw-row"><button type="button" class="sw-btn" :class="row.type === 'CUSTOM' ? 'sw-btn--primary' : ''" @click="openRole(row.id, 'permissions')">{{ row.type === 'CUSTOM' ? '配置权限' : '查看权限' }}</button><button type="button" class="sw-btn" @click="openRole(row.id, 'members')">管理成员</button><button type="button" class="sw-link" @click="openRole(row.id, 'details')">详情与维护</button></div>
          </article>
        </div>
        <div v-if="!listing.loading && !listing.error" class="sw-pager"><span>共 {{ listing.total }} 个角色 · 第 {{ listing.page }} 页</span><div class="sw-row">
          <button type="button" class="sw-btn" :disabled="listing.page <= 1" @click="changePage(-1)">上一页</button><button type="button" class="sw-btn" :disabled="listing.page * listing.pageSize >= listing.total" @click="changePage(1)">下一页</button></div></div>
      </template>
      <section v-else class="sw-card sw-workbench" data-testid="role-workbench">
        <aside class="sw-context" aria-label="选择学校角色">
          <div class="sw-kicker">选择学校角色</div>
          <form @submit.prevent="search"><input v-model="filters.keyword" class="sw-input" placeholder="角色名称 / 编码" aria-label="工作区查找角色" :disabled="busy" /><button type="submit" class="sw-link sw-space" :disabled="busy">查询角色</button></form>
          <p v-if="listing.loading" class="sw-muted sw-space" role="status">正在读取角色目录…</p>
          <p v-else-if="listing.error" class="sw-alert sw-alert--error" role="alert">{{ listing.error }}<button type="button" class="sw-link" @click="loadRoles">重试</button></p>
          <div v-else class="sw-context-list">
            <button v-if="selectedRole && !listing.rows.some(row => String(row.id) === selectedId)" type="button" class="sw-choice" aria-current="true"><b>{{ selectedRole.name }}</b><small>当前角色 · 不在本页筛选结果中</small></button>
            <button v-for="row in listing.rows" :key="row.id" type="button" class="sw-choice" :aria-current="String(row.id) === selectedId" :disabled="busy" @click="openRole(row.id, activeTab)"><b>{{ row.name }}</b><small>{{ row.typeLabel }} · {{ countLabel(row.memberCount) }} 位成员</small></button>
            <p v-if="!listing.rows.length" class="sw-muted sw-space">目录没有匹配的角色。</p>
          </div>
          <div class="sw-pager"><button type="button" class="sw-btn" :disabled="listing.loading || listing.page <= 1 || busy" aria-label="角色目录上一页" @click="changePage(-1)">‹</button><span>{{ listing.page }} / {{ Math.max(1, Math.ceil(listing.total / listing.pageSize)) }}</span><button type="button" class="sw-btn" :disabled="listing.loading || listing.page * listing.pageSize >= listing.total || busy" aria-label="角色目录下一页" @click="changePage(1)">›</button></div>
          <button type="button" class="sw-link sw-space" :disabled="busy" @click="showCatalog('roles')">← 返回角色目录</button>
        </aside>
        <div class="sw-workcontent">
          <template v-if="selectedId">
            <div class="sw-worktitle"><div><h2>{{ selectedRole?.name || '正在读取当前角色' }}</h2><p>{{ selectedRole?.code || selectedId }}<span v-if="selectedRole?.version != null"> · 当前版本 {{ selectedRole.version }}</span></p></div><span v-if="selectedRole" class="sw-tag" :class="selectedRole.type === 'CUSTOM' ? 'sw-tag--blue' : ''">{{ selectedRole.typeLabel }}</span></div>
            <div class="sw-tabs" role="tablist" aria-label="角色办理步骤" style="margin-bottom:20px">
              <button v-for="tab in tabs" :key="tab.key" type="button" role="tab" :aria-selected="activeTab === tab.key" :disabled="busy" @click="openRole(selectedId, tab.key)">{{ tab.label }}<span v-if="tab.key === 'members' && selectedRole?.memberCount != null" class="sw-tag">{{ selectedRole.memberCount }}</span></button>
            </div>
            <RolePermissionPanel ref="permissionPanel" :key="`${contextKey}:${selectedId}:permissions`" v-show="activeTab === 'permissions' || activeTab === 'scope'" :ctx="ctx" :role-id="selectedId" :tab="activeTab" :locked="mutationBusy || memberBusy"
              @loaded="setDetail" @saved="onPermissionSaved" @dirty="permissionDirty = $event" @busy="permissionBusy = $event" />
            <RoleMembersPanel v-if="membersVisited" ref="membersPanel" :key="`${contextKey}:${selectedId}:members`" v-show="activeTab === 'members' || activeTab === 'audit'" :ctx="ctx" :role-id="selectedId" :tab="activeTab" :locked="mutationBusy || permissionBusy"
              @dirty="memberDirty = $event" @busy="memberBusy = $event" @count="setMemberCount" />
            <section v-if="activeTab === 'details'" class="sw-stack">
              <div v-if="!detail" class="sw-alert">角色详情尚未完整读取。请在菜单与操作页重试后，再执行维护。</div>
              <template v-else>
                <div class="sw-form"><div><small class="sw-muted">角色编码</small><p>{{ detail.code }}</p></div><div><small class="sw-muted">类型 / 状态</small><p>{{ detail.typeLabel }} · {{ detail.statusLabel }}</p></div><div><small class="sw-muted">默认范围</small><p>{{ scopeLabel(detail.scopeCode) }}</p></div><div><small class="sw-muted">成员总数</small><p>{{ countLabel(detail.memberCount) }} 位（完整清单见成员页）</p></div></div>
                <details v-if="detail.description"><summary>查看角色来源说明</summary><p class="sw-code">{{ detail.description }}</p></details>
                <div class="sw-row"><button v-if="detail.type === 'CUSTOM' && can('editRole')" type="button" class="sw-btn" :disabled="busy || mutationBlocked" @click="openRename">修改名称</button>
                  <button v-if="can('copyRole')" type="button" class="sw-btn" :disabled="busy || mutationBlocked" @click="prepareMutation('copy')">复制为自定义角色</button>
                  <button v-if="can('exportRoleConfig')" type="button" class="sw-btn" :disabled="busy" @click="exportRole">导出角色配置</button>
                  <button v-if="detail.type === 'CUSTOM' && detail.status === 'ENABLED' && can('deprecateRole')" type="button" class="sw-btn sw-btn--danger" :disabled="busy || mutationBlocked" @click="prepareMutation('disable')">停用角色</button></div>
                <p class="sw-muted">停用前必须先改派现有成员；历史记录保留，后端会再次核对。</p>
              </template>
            </section>
          </template>
          <div v-else class="sw-state"><h2>请选择一个学校角色</h2><p class="sw-muted">读取成功后，在左侧选择角色即可开始办理。</p></div>
        </div>
      </section>
    </template>
    <AppConfirmDialog :visible="!!pendingMutation" :title="pendingMutation === 'disable' ? '停用当前自定义角色？' : '复制当前角色？'"
      :message="pendingMutation === 'disable' ? '已有成员必须先改派。停用后该角色不可再分配，历史记录继续保留。' : '复制权限与默认范围，固定来源模板版本；成员不复制。'"
      :type="pendingMutation === 'disable' ? 'danger' : 'warning'" :require-reason="pendingMutation === 'disable'"
      :confirm-text="pendingMutation === 'disable' ? '确认停用角色' : '确认复制角色'" :submitting="mutationBusy" :confirm-disabled="mutationBlocked"
      @update:visible="closeMutation" @confirm="performMutation" />
  </SystemWorkspaceFrame>
</template>

<script>
import SystemWorkspaceFrame from '@/modules/system/components/workspace/SystemWorkspaceFrame.vue'
import RolePermissionPanel from '@/modules/system/components/workspace/RolePermissionPanel.vue'
import RoleMembersPanel from '@/modules/system/components/workspace/RoleMembersPanel.vue'
import RoleTemplatesPanel from '@/modules/system/components/workspace/RoleTemplatesPanel.vue'
import AppConfirmDialog from '@/modules/system/components/workspace/WorkspaceConfirmDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { schoolIamApi } from '@/modules/system/api/schoolIam.api'
import * as wc from '@/modules/system/utils/workspaceContract'
const WORK_TABS = ['permissions', 'scope', 'members', 'audit', 'details']
export default {
  name: 'SystemRoleListView',
  components: { SystemWorkspaceFrame, RolePermissionPanel, RoleMembersPanel, RoleTemplatesPanel, AppConfirmDialog },
  props: { ctx: { type: Object, required: true }, surface: { type: String, default: 'roles' } },
  data() { return { fence: null, listing: { rows: [], total: 0, page: 1, pageSize: 9, loading: true, error: '' }, filters: { keyword: '', type: '', status: '' }, appliedFilters: { keyword: '', type: '', status: '' }, detail: null, form: null, formOriginal: '', formError: '', sourceTemplates: [], sourceLoading: false, permissionDirty: false, memberDirty: false, permissionBusy: false, memberBusy: false, mutationBusy: false, auxBusy: false, mutationBlocked: false, pendingMutation: '', flash: '', membersVisited: false } },
  computed: {
    contextKey() { return wc.contextFingerprint(this.ctx) },
    selectedId() { return String(this.$route.query.roleId || '') },
    activeTab() { const value = String(this.$route.query.tab || ''); return WORK_TABS.includes(value) ? value : this.surface === 'members' ? 'members' : 'permissions' },
    mode() {
      const tab = String(this.$route.query.tab || '')
      if (WORK_TABS.includes(tab) || this.selectedId || ['permissions', 'members'].includes(this.surface)) return 'workbench'
      return tab === 'templates' || this.surface === 'templates' ? 'templates' : 'roles'
    },
    pageTitle() { return this.mode === 'templates' ? '学校角色与模板' : this.mode === 'roles' ? '学校角色与成员' : ({ permissions: '菜单与操作权限', scope: '角色默认数据范围', members: '角色成员', audit: '角色操作留痕', details: '角色详情与维护' }[this.activeTab]) },
    selectedRole() { return this.detail && String(this.detail.id) === this.selectedId ? this.detail : this.listing.rows.find(row => String(row.id) === this.selectedId) },
    busy() { return this.permissionBusy || this.memberBusy || this.mutationBusy || this.auxBusy },
    dirty() { return this.permissionDirty || this.memberDirty || (!!this.form && JSON.stringify(this.form) !== this.formOriginal) },
    scopeOptions() { return this.ctx.statusOptions?.scopeTypes || [] },
    tabs() { return [{ key: 'permissions', label: '菜单与操作' }, { key: 'scope', label: '数据范围' }, { key: 'members', label: '成员' }, { key: 'audit', label: '留痕记录' }, { key: 'details', label: '详情与维护' }] }
  },
  watch: {
    selectedId() { this.detail = null; this.permissionDirty = false; this.memberDirty = false; this.permissionBusy = false; this.memberBusy = false; this.membersVisited = ['members', 'audit'].includes(this.activeTab) },
    activeTab(value) { if (['members', 'audit'].includes(value)) this.membersVisited = true },
    mode() { this.ensureSelection() },
    contextKey() {
      this.fence.invalidate(); this.detail = null; this.form = null; this.permissionDirty = false; this.memberDirty = false
      this.permissionBusy = false; this.memberBusy = false; this.mutationBusy = false; this.auxBusy = false; this.mutationBlocked = false; this.pendingMutation = ''; this.sourceTemplates = []; this.sourceLoading = false; this.formError = ''; this.flash = ''; this.filters = { keyword: '', type: '', status: '' }; this.appliedFilters = { ...this.filters }; this.listing.rows = []; this.listing.page = 1; this.loadRoles()
    }
  },
  created() { this.fence = wc.createRequestFence(); this.membersVisited = ['members', 'audit'].includes(this.activeTab); this.loadRoles() },
  mounted() { window.addEventListener('beforeunload', this.beforeUnload) },
  beforeUnmount() { this.fence.invalidate(); window.removeEventListener('beforeunload', this.beforeUnload) },
  beforeRouteLeave(to) { return this.canLeave(to) },
  beforeRouteUpdate(to) { return this.canLeave(to) },
  methods: {
    can(key) { return wc.actionAllowed(this.ctx, key) },
    countLabel: wc.countLabel,
    scopeLabel(code) { return this.scopeOptions.find(item => item.value === code)?.label || '范围待核对' },
    beforeUnload(event) { if (this.dirty || this.busy) { event.preventDefault(); event.returnValue = '' } },
    canLeave(to) {
      if (this.busy) { this.flash = '当前操作尚未返回结果，请等待后再切换。'; return false }
      const sameObject = to.path === this.$route.path && String(to.query.roleId || '') === this.selectedId && !!this.selectedId
      if (sameObject && wc.isRoleWorkspaceRoute(to) && !this.form) return true
      return !this.dirty || window.confirm('存在尚未保存的修改。确认放弃并离开当前角色？')
    },
    async loadRoles() {
      const current = this.fence.start('roles'); this.listing.loading = true; this.listing.error = ''
      try {
        const data = wc.paged(wc.unwrap(await systemApi.getRoles({ ...this.appliedFilters, page: this.listing.page, pageSize: this.listing.pageSize })), 'list')
        if (!current()) return false
        this.listing = { ...data, loading: false, error: '' }; this.ensureSelection(); return true
      } catch (error) { if (current()) { this.listing.loading = false; this.listing.error = error.message || '角色目录读取失败' }; return false }
    },
    ensureSelection() {
      if (this.mode === 'workbench' && !this.selectedId && !this.listing.loading && !this.listing.error && this.listing.rows.length) {
        this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, roleId: String(this.listing.rows[0].id) }, hash: this.$route.hash })
      }
    },
    search() { if (this.busy) return; this.appliedFilters = { ...this.filters, keyword: this.filters.keyword.trim() }; this.listing.page = 1; this.loadRoles() },
    clearFilters() { this.filters = { keyword: '', type: '', status: '' }; this.search() },
    changePage(delta) { if (this.busy || this.listing.loading) return; this.listing.page = Math.max(1, this.listing.page + delta); this.loadRoles() },
    refresh() { if (!this.busy) this.loadRoles() },
    showCatalog(mode) {
      const query = { ...this.$route.query }; delete query.roleId; delete query.tab
      if (this.$route.path === '/admin/system/iam') query.surface = mode
      else if (mode === 'templates') query.tab = 'templates'
      this.$router.push({ path: this.$route.path, query })
    },
    openRole(id, tab) { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, roleId: String(id), tab: WORK_TABS.includes(tab) ? tab : 'permissions' }, hash: '' }) },
    setDetail(value) { if (String(value?.id) === this.selectedId) this.detail = value },
    setMemberCount(total) { if (this.detail) this.detail = { ...this.detail, memberCount: total }; const row = this.listing.rows.find(item => String(item.id) === this.selectedId); if (row) row.memberCount = total },
    onPermissionSaved() { this.permissionDirty = false; this.loadRoles() },
    async openCreate(templateCode = '') {
      if (!this.can('createRole') || this.busy || (this.dirty && !window.confirm('放弃当前尚未保存的修改，开始创建角色？'))) return
      this.permissionDirty = false; this.memberDirty = false
      this.form = { id: '', name: '', code: '', sourceTemplateCode: typeof templateCode === 'string' ? templateCode : '', scopeCode: 'ASSIGNED' }
      this.formOriginal = JSON.stringify(this.form); this.formError = ''; this.sourceLoading = true; this.sourceTemplates = []
      const current = this.fence.start('sources')
      try {
        const data = wc.unwrap(await schoolIamApi.roleTemplates())
        if (!current()) return
        if (!Array.isArray(data?.items)) throw new Error('来源模板目录结构异常')
        this.sourceTemplates = data.items
      } catch (error) { if (current()) this.formError = error.message || '来源模板读取失败' }
      finally { if (current()) this.sourceLoading = false }
    },
    openRename() {
      if (!this.detail || this.detail.type !== 'CUSTOM' || !this.can('editRole') || this.busy) return
      if (this.dirty && !window.confirm('放弃尚未保存的权限或成员选择，修改名称？')) return
      this.permissionDirty = false; this.memberDirty = false
      this.form = { id: this.selectedId, name: this.detail.name, code: this.detail.code }
      this.formOriginal = JSON.stringify(this.form); this.formError = ''
    },
    closeForm() {
      if (this.busy || (JSON.stringify(this.form) !== this.formOriginal && !window.confirm('放弃尚未保存的角色表单？'))) return
      this.form = null; this.formError = ''; this.permissionDirty = false; this.memberDirty = false
    },
    async saveForm() {
      if (!this.form || this.busy || this.mutationBlocked || !this.can(this.form.id ? 'editRole' : 'createRole')) return
      const value = { ...this.form, name: this.form.name.trim(), code: this.form.code.trim().toUpperCase() }
      if (value.name.length < 2) { this.formError = '角色名称至少 2 个字'; return }
      if (!value.id && value.code && !/^[A-Z][A-Z0-9_]{2,49}$/.test(value.code)) { this.formError = '角色编码为 3—50 位大写字母、数字或下划线，首位为字母'; return }
      if (!value.id && !this.sourceTemplates.some(item => item.templateCode === value.sourceTemplateCode)) { this.formError = '请选择当前已发布的学校来源模板'; return }
      this.mutationBusy = true; const current = this.fence.start('mutation')
      try {
        const data = wc.unwrap(await (value.id ? systemApi.updateRole(value.id, { name: value.name }) : systemApi.createRole({ name: value.name, ...(value.code ? { code: value.code } : {}), sourceTemplateCode: value.sourceTemplateCode, scopeCode: value.scopeCode })))
        if (!current()) return
        if (!data?.id) throw new Error('未取得角色编号，请查询目录核对本次结果')
        this.form = null; this.permissionDirty = false; this.memberDirty = false; this.flash = value.id ? '角色名称已保存。' : '角色已创建，请继续配置权限与成员。'
        this.mutationBusy = false; await this.loadRoles(); if (current()) this.openRole(data.id, 'permissions')
      } catch (error) { if (current()) { this.mutationBlocked = true; this.formError = error.message; this.flash = '本次写入结果需要核对，已阻止连续重复提交。' } }
      finally { if (current()) this.mutationBusy = false }
    },
    prepareMutation(kind) { if (!this.detail || this.busy || this.mutationBlocked || !this.can(kind === 'copy' ? 'copyRole' : 'deprecateRole')) return; if (this.dirty) { this.flash = '请先保存或还原当前权限和成员选择，再执行角色维护。'; return }; this.pendingMutation = kind },
    closeMutation(visible) { if (!visible && !this.mutationBusy) this.pendingMutation = '' },
    async performMutation({ reason }) {
      const kind = this.pendingMutation
      if (!kind || !this.detail || this.busy || this.mutationBlocked || !this.can(kind === 'copy' ? 'copyRole' : 'deprecateRole')) return
      this.mutationBusy = true; const current = this.fence.start('mutation')
      try {
        const result = wc.unwrap(await (kind === 'copy' ? systemApi.copyRole(this.selectedId) : systemApi.deprecateRole(this.selectedId, { reason })))
        if (!current()) return
        if (!result?.id) throw new Error('角色回执不完整，请重新读取核对')
        this.pendingMutation = ''; this.flash = kind === 'copy' ? '已复制为自定义角色，成员未复制。' : '角色已停用，历史记录保留。'
        this.mutationBusy = false; await this.loadRoles()
        if (!current()) return
        if (kind === 'copy' && result?.id) this.openRole(result.id, 'permissions')
        else this.$refs.permissionPanel?.load(false)
      } catch (error) { if (current()) { this.mutationBlocked = true; this.flash = `请重新读取并核对本次结果：${error.message}`; this.pendingMutation = '' } }
      finally { if (current()) this.mutationBusy = false }
    },
    async recheckMutation() { if (this.busy) return; if (await this.loadRoles()) { this.mutationBlocked = false; this.flash = '已重新读取角色目录，请核对当前结果后再决定后续操作。'; this.$refs.permissionPanel?.load(true) } },
    async exportRole() {
      if (!this.can('exportRoleConfig') || this.busy || !this.selectedId) return
      this.mutationBusy = true; const current = this.fence.start('export')
      try { wc.unwrap(await systemApi.exportRoleConfig(this.selectedId)); if (current()) this.flash = '角色配置下载已交给浏览器，不包含成员清单。' }
      catch (error) { if (current()) this.flash = error.message || '角色配置下载失败' }
      finally { if (current()) this.mutationBusy = false }
    }
  }
}
</script>
