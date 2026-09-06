<template>
  <SystemWorkspaceFrame title="访问排查" subtitle="选择老师、功能与具体对象，查看服务端给出的拒绝原因和判定证据。" :ctx="ctx">
    <template #actions><button type="button" class="sw-btn" @click="$router.push('/admin/system/iam?surface=diagnostics')">治理概览与高级排查</button></template>
    <div class="sw-inspector-grid">
      <section class="sw-card sw-pad sw-stack">
        <h2>选择排查对象</h2>
        <form class="sw-row" @submit.prevent="searchActors(1)"><label class="sw-field" style="flex:1">学校成员<input v-model="actorKeyword" class="sw-input" aria-label="搜索排查成员" placeholder="输入姓名或工号后查询" @input="actor = null" /></label><button type="submit" class="sw-btn" :disabled="actors.loading">查询成员</button></form>
        <div v-if="actor" class="sw-alert" data-testid="selected-access-actor"><b>{{ actor.name }}</b> / {{ actor.loginName || actor.userNo }}<small class="sw-code"> · 账号 {{ actor.id }}</small></div>
        <p v-if="actors.loading" role="status">正在查询成员…</p>
        <p v-else-if="actors.error" class="sw-alert sw-alert--error" role="alert">{{ actors.error }}</p>
        <div v-else-if="actors.searched && !actor" class="sw-stack"><div class="sw-picker-list"><button v-for="row in actors.rows" :key="row.id" type="button" class="sw-choice" @click="actor = row"><b>{{ row.name }}</b><small>{{ row.loginName || row.userNo }} · {{ row.statusLabel }}</small></button><p v-if="!actors.rows.length" class="sw-muted">没有符合条件的教职工。</p></div>
          <div class="sw-pager"><span>共 {{ actors.total }} 位 · 第 {{ actors.page }} 页</span><div class="sw-row"><button type="button" class="sw-btn" :disabled="actors.page <= 1" @click="searchActors(actors.page - 1)">上一页</button><button type="button" class="sw-btn" :disabled="actors.page * actors.pageSize >= actors.total" @click="searchActors(actors.page + 1)">下一页</button></div></div></div>
        <label class="sw-field">排查功能<select v-model="permissionCode" class="sw-input" aria-label="排查功能" :disabled="catalogLoading"><option value="">{{ catalogLoading ? '正在读取权限目录…' : '请选择学校权限' }}</option><option v-for="item in permissions" :key="item.permissionCode" :value="item.permissionCode">{{ item.label || item.permissionCode }}</option></select><small class="sw-code">{{ permissionCode }}</small></label>
        <p v-if="catalogError" class="sw-alert sw-alert--error" role="alert">{{ catalogError }}<button type="button" class="sw-btn" @click="loadCatalog">重新读取权限</button></p>
        <label class="sw-field">具体业务对象类型<select v-model="resourceType" class="sw-input" aria-label="业务对象类型"><option value="STUDENT">学生主档</option><option value="INTERN_STUDENT">实习学生</option><option value="GRADUATION_STUDENT">毕设学生</option><option value="USER">教职工账号</option><option value="CLASS">班级</option><option value="MAJOR">专业</option><option value="COLLEGE">学院</option></select></label>
        <template v-if="isAccountResource">
          <form class="sw-row" @submit.prevent="searchResources(1)"><label class="sw-field" style="flex:1">查找业务对象<input v-model="resourceKeyword" class="sw-input" placeholder="姓名 / 学号 / 工号" aria-label="搜索业务对象" @input="resource = null" /></label><button type="submit" class="sw-btn" :disabled="resources.loading">查询对象</button></form>
          <p v-if="resources.loading" role="status">正在读取业务对象…</p><p v-else-if="resources.error" class="sw-alert sw-alert--error" role="alert">{{ resources.error }}</p>
          <div v-else-if="resources.searched && !resource" class="sw-stack"><div class="sw-picker-list"><button v-for="row in resources.rows" :key="row.id" type="button" class="sw-choice" :disabled="resourceType !== 'USER' && (!row.profileBound || !row.studentId)" @click="chooseResource(row)"><b>{{ row.name }}</b><small>{{ row.studentNo || row.loginName }} · {{ resourceType !== 'USER' && (!row.profileBound || !row.studentId) ? '主档绑定未取得，不能用于排查' : row.orgName || '本校对象' }}</small></button><p v-if="!resources.rows.length" class="sw-muted">没有符合条件的对象。</p></div>
            <div class="sw-pager"><span>共 {{ resources.total }} 项 · 第 {{ resources.page }} 页</span><div class="sw-row"><button type="button" class="sw-btn" :disabled="resources.page <= 1" @click="searchResources(resources.page - 1)">上一页</button><button type="button" class="sw-btn" :disabled="resources.page * resources.pageSize >= resources.total" @click="searchResources(resources.page + 1)">下一页</button></div></div></div>
        </template>
        <label v-else class="sw-field">选择组织对象<select class="sw-input" aria-label="组织业务对象" :value="resource?.id || ''" @change="chooseOrgResource($event.target.value)"><option value="">请选择具体组织</option><option v-for="row in organizations.filter(item => item.type === resourceType)" :key="row.id" :value="row.id">{{ row.name }}</option></select></label>
        <div v-if="resource" class="sw-alert" data-testid="selected-access-resource"><b>{{ resource.label }}</b><small class="sw-code"> · {{ resource.type }} / {{ resource.id }}</small></div>
        <label class="sw-field">核对数据范围目标<select v-model="targetKey" class="sw-input" aria-label="数据范围目标"><option value="">请选择具体范围</option><option v-for="row in targets" :key="`${row.type}:${row.id}`" :value="`${row.type}:${row.id}`">{{ typeLabel(row.type) }} · {{ row.name }}</option></select></label>
        <p v-if="orgError" class="sw-alert">{{ orgError }}<button type="button" class="sw-link" @click="loadOrganizations">重新读取组织</button></p>
        <p class="sw-muted">选人和组织读取沿用各自权限。没有查询权时不会自动授予权限，也不把显示名称当作编号。</p>
        <p v-if="validationError" class="sw-alert sw-alert--error" role="alert">{{ validationError }}</p>
        <div class="sw-savebar"><span class="sw-muted">只读排查，不修改角色或业务数据</span><button type="button" class="sw-btn sw-btn--primary" data-testid="A033-query" :disabled="!canQuery" @click="explain">{{ querying ? '正在查询…' : '开始访问排查' }}</button></div>
      </section>
      <section class="sw-card sw-pad sw-stack" aria-live="polite" data-testid="access-conclusion">
        <h2>排查结论</h2>
        <div v-if="querying" class="sw-state" role="status">正在读取当前选择的真实判定…</div>
        <div v-else-if="queryError" class="sw-alert sw-alert--error" role="alert"><b>本次排查未取得结果</b><p>{{ queryError }}</p><p>历史结论不再用于当前选择。</p></div>
        <div v-else-if="!result" class="sw-state"><h3>{{ stale ? '选择已变更，请重新查询' : '选择对象后开始排查' }}</h3><p class="sw-muted">身份权限通过，不代表可以访问任意业务对象。</p></div>
        <template v-else>
          <div class="sw-alert" :class="result.allowed === true && result.finalDecision === 'ALLOW' ? 'sw-alert--success' : 'sw-alert--warning'" data-testid="access-decision"><b>{{ result.allowed === true && result.finalDecision === 'ALLOW' ? '此对象访问通过' : '此对象访问未通过' }}</b><p>{{ result.message || '请核对下方角色与数据范围判定。' }}</p><small class="sw-code">{{ result.reasonCode }}</small></div>
          <p class="sw-muted">{{ result.subject?.realName || result.subject?.loginName }} · {{ permission?.label || permissionCode }}</p>
          <div v-for="role in result.roles || []" :key="role.roleId" class="sw-card sw-pad sw-stack">
            <div class="sw-between"><b>{{ role.roleName }}</b><span class="sw-tag" :class="role.decision?.allowed === true ? 'sw-tag--green' : 'sw-tag--orange'">{{ role.decision?.allowed === true ? '通过' : '未通过' }}</span></div>
            <p>身份权限：{{ role.decision?.iamAllowed === true ? '通过' : '未通过' }} · 数据范围：{{ role.decision?.dataScope || '未取得' }}</p>
            <p class="sw-code">{{ role.decision?.reasonCode }}</p>
            <details><summary>展开服务端判定证据</summary><pre class="sw-evidence">{{ evidence(role.decision) }}</pre></details>
            <button type="button" class="sw-link" @click="$router.push({ path: '/admin/system/roles', query: { roleId: String(role.roleId), tab: 'permissions' } })">核对这个角色的权限 →</button>
          </div>
        </template>
      </section>
    </div>
  </SystemWorkspaceFrame>
</template>
<script>
import SystemWorkspaceFrame from './SystemWorkspaceFrame.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { schoolIamApi } from '@/modules/system/api/schoolIam.api'
import * as wc from '@/modules/system/utils/workspaceContract'
const emptySearch = () => ({ rows: [], page: 1, pageSize: 10, total: 0, loading: false, error: '', searched: false })
export default {
  name: 'SystemAccessInspector', components: { SystemWorkspaceFrame }, props: { ctx: { type: Object, required: true } },
  data() { return { fence: null, actorKeyword: '', resourceKeyword: '', actor: null, resource: null, resourceRow: null, actors: emptySearch(), resources: emptySearch(), permissions: [], permissionCode: '', catalogLoading: false, catalogError: '', organizations: [], orgError: '', resourceType: 'STUDENT', targetKey: '', result: null, querying: false, queryError: '', stale: false, validationError: '' } },
  computed: {
    contextKey() { return wc.contextFingerprint(this.ctx) },
    permission() { return this.permissions.find(item => item.permissionCode === this.permissionCode) },
    isAccountResource() { return ['STUDENT', 'INTERN_STUDENT', 'GRADUATION_STUDENT', 'USER'].includes(this.resourceType) },
    targets() {
      const rows = [...this.organizations]
      if (this.resourceRow && this.resourceType !== 'USER') for (const [type, field] of [['COLLEGE', 'college'], ['MAJOR', 'major'], ['CLASS', 'class']]) {
        if (this.resourceRow[`${field}Id`]) rows.push({ type, id: String(this.resourceRow[`${field}Id`]), name: this.resourceRow[`${field}Name`] || this.resourceRow[`${field}Id`] })
      }
      return [...new Map(rows.map(row => [`${row.type}:${row.id}`, row])).values()]
    },
    target() { return this.targets.find(row => `${row.type}:${row.id}` === this.targetKey) },
    queryKey() { return JSON.stringify([this.contextKey, this.actor?.id, this.permissionCode, this.permission?.moduleKey, this.targetKey, this.resource?.type, this.resource?.id, this.resourceType, this.actorKeyword, this.resourceKeyword]) },
    canQuery() { return !this.querying && !!this.actor?.id && !!this.permission?.moduleKey && !!this.resource?.id && this.resource.type === this.resourceType && !!this.target }
  },
  watch: {
    queryKey() { this.invalidateResult() },
    actorKeyword() { this.fence.start('actors'); this.actors.loading = false; this.actors.rows = []; this.actors.searched = false; this.actors.error = '' },
    resourceKeyword() { this.fence.start('resources'); this.resources.loading = false; this.resources.rows = []; this.resources.searched = false; this.resources.error = ''; this.resourceRow = null; this.targetKey = '' },
    resourceType() { this.fence.start('resources'); this.resource = null; this.resourceRow = null; this.resources = emptySearch(); this.targetKey = '' },
    contextKey() { this.reset() },
    '$route.query.userId'() { this.actor = null; this.loadInitialActor() }
  },
  created() { this.fence = wc.createRequestFence(); this.loadCatalog(); this.loadOrganizations(); this.loadInitialActor() }, beforeUnmount() { this.fence.invalidate() },
  methods: {
    typeLabel(type) { return { CLASS: '班级', MAJOR: '专业', COLLEGE: '学院' }[type] || type },
    evidence(value) { return JSON.stringify(value || {}, null, 2) },
    invalidateResult() { if (this.result || this.querying) this.stale = true; this.fence.start('explain'); this.result = null; this.querying = false; this.queryError = ''; this.validationError = '' },
    reset() { this.fence.invalidate(); this.actor = null; this.resource = null; this.resourceRow = null; this.actorKeyword = ''; this.resourceKeyword = ''; this.actors = emptySearch(); this.resources = emptySearch(); this.permissions = []; this.permissionCode = ''; this.organizations = []; this.targetKey = ''; this.result = null; this.querying = false; this.queryError = ''; this.stale = false; this.loadCatalog(); this.loadOrganizations() },
    async loadCatalog() {
      const current = this.fence.start('catalog'); this.catalogLoading = true; this.catalogError = ''
      try { const data = wc.unwrap(await schoolIamApi.permissionCatalog()); if (!current()) return; if (!Array.isArray(data?.assignablePermissions)) throw new Error('未取得学校权限目录'); this.permissions = data.assignablePermissions }
      catch (error) { if (current()) { this.catalogError = error.message || '权限目录读取失败'; this.permissions = []; this.permissionCode = '' } }
      finally { if (current()) this.catalogLoading = false }
    },
    async loadOrganizations() {
      const current = this.fence.start('org'); this.orgError = ''
      try { const rows = wc.flattenOrganizations(wc.unwrap(await systemApi.getDepartmentTree())); if (current()) this.organizations = rows }
      catch (error) { if (current()) { this.organizations = []; this.orgError = `组织目录未取得：${error.message}。已绑定学生可使用其主档返回的范围。` } }
    },
    async loadInitialActor() {
      const id = String(this.$route.query.userId || ''); if (!/^\d+$/.test(id)) return
      const current = this.fence.start('actors'); this.actors.loading = true
      try { const data = wc.unwrap(await systemApi.getUserDetail(id)); if (current()) { if (String(data?.id) !== id) throw new Error('成员详情编号不一致'); this.actor = data } }
      catch (error) { if (current()) this.actors.error = error.message || '成员详情读取失败' }
      finally { if (current()) this.actors.loading = false }
    },
    async searchAccounts(target, accountType, keyword, page) {
      const current = this.fence.start(target); this[target].loading = true; this[target].error = ''; this[target].searched = true
      try { const data = wc.paged(wc.unwrap(await systemApi.getUsers({ accountType, keyword: keyword.trim(), page, pageSize: 10 })), 'list'); if (current()) this[target] = { ...data, loading: false, error: '', searched: true } }
      catch (error) { if (current()) { this[target].loading = false; this[target].error = error.message || '对象查询失败' } }
    },
    searchActors(page) { this.actor = null; return this.searchAccounts('actors', 'STAFF', this.actorKeyword, page) },
    searchResources(page) { this.resource = null; this.resourceRow = null; this.targetKey = ''; return this.searchAccounts('resources', this.resourceType === 'USER' ? 'STAFF' : 'STUDENT', this.resourceKeyword, page) },
    chooseResource(row) { try { this.resource = wc.accessResource(row, this.resourceType); this.resourceRow = row; this.targetKey = ''; this.validationError = '' } catch (error) { this.validationError = error.message } },
    chooseOrgResource(id) { const row = this.organizations.find(item => item.id === id && item.type === this.resourceType); if (!row) { this.resource = null; return }; this.resource = wc.accessResource(row, this.resourceType); this.resourceRow = null; this.targetKey = `${row.type}:${row.id}` },
    async explain() {
      if (!this.canQuery) return
      const fingerprint = this.queryKey; const current = this.fence.start('explain')
      const payload = { moduleKey: this.permission.moduleKey, permissionCode: this.permissionCode, scopeTargetType: this.target.type, scopeTargetId: this.target.id, resourceType: this.resource.type, resourceId: this.resource.id }
      this.querying = true; this.result = null; this.queryError = ''; this.stale = false
      try { const data = wc.unwrap(await schoolIamApi.accessExplain(this.actor.id, payload)); if (!current() || fingerprint !== this.queryKey) return; if (!data || !['ALLOW', 'DENY'].includes(data.finalDecision) || typeof data.allowed !== 'boolean' || (data.allowed !== (data.finalDecision === 'ALLOW'))) throw new Error('服务端判定结果不完整或相互矛盾'); this.result = data }
      catch (error) { if (current()) this.queryError = error.message || '排查失败' }
      finally { if (current()) this.querying = false }
    }
  }
}
</script>
