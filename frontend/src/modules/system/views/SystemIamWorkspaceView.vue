<template>
  <ModulePageShell
    title="学校 IAM 工作区"
    subtitle="角色、模板、成员、权限、数据范围、委托、安全变更与 Access Explain 使用同一套学校权限真值"
    role-name="学校系统管理员 / 安全管理员"
    data-scope-name="当前学校租户"
  >
    <div class="iam-page">
      <section class="hero card">
        <div>
          <p class="eyebrow">B7 · School IAM Workspace</p>
          <h3>学校管理员管学校身份，不接管企业成员 IAM</h3>
          <p class="muted">企业 `COMPANY_ADMIN / HR / MENTOR` 与 `enterprise.internship.*` 由 EnterpriseMember / AccessGrant 管理，不能在这里随便加给学校用户。</p>
        </div>
        <AppButton :loading="loading" @click="load">刷新</AppButton>
      </section>

      <div v-if="error" class="error card">{{ error }}</div>

      <template v-else>
        <section class="metrics">
          <article class="card"><strong>{{ summary.roleCount || 0 }}</strong><span>学校角色</span></article>
          <article class="card"><strong>{{ summary.memberCount || 0 }}</strong><span>学校成员</span></article>
          <article class="card"><strong>{{ catalog.customRoleAssignablePermissions?.length || 0 }}</strong><span>自定义角色可分配权限</span></article>
          <article class="card"><strong>{{ catalog.enterprisePermissionCount || 0 }}</strong><span>企业权限（仅可见，不可学校分配）</span></article>
        </section>

        <section class="surface-grid">
          <button v-for="item in surfaces" :key="item.key" class="surface card" @click="go(item.path)">
            <strong>{{ item.label }}</strong><span>{{ item.description }}</span><small>进入工作区 →</small>
          </button>
        </section>

        <section class="card">
          <header class="section-head">
            <div><h3>学校可分配 Permission Catalog</h3><p class="muted">此处来自 Control Plane 权威目录；`enterprise.internship.*` 不出现在可分配清单。</p></div>
            <label class="search">搜索<input v-model.trim="permissionKeyword" placeholder="permissionCode / 模块 / Feature" /></label>
          </header>
          <div class="recruitment-box">
            <strong>岗位实习 · 招聘季学校侧权限</strong>
            <span v-for="item in catalog.internshipRecruitmentPermissions || []" :key="item.permissionCode" class="permission-chip">{{ item.permissionCode }}</span>
            <span v-if="!(catalog.internshipRecruitmentPermissions || []).length" class="danger-text">招聘季权限未进入 Catalog，禁止继续配置</span>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>permissionCode</th><th>模块 / Feature</th><th>风险</th><th>自定义角色</th></tr></thead>
              <tbody>
                <tr v-for="item in filteredPermissions" :key="item.permissionCode">
                  <td class="mono">{{ item.permissionCode }}</td><td>{{ item.moduleKey }} / {{ item.featureKey || '—' }}</td><td>{{ item.riskLevel }}</td><td>{{ item.customRoleAssignable ? '可分配' : '仅系统策略' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="card">
          <header class="section-head"><div><h3>学校角色模板</h3><p class="muted">只展示已发布学校模板；版本不可变，自定义角色升级策略固定为 DERIVED_PINNED。</p></div><button class="link" @click="go('/admin/system/roles?tab=templates')">进入模板管理</button></header>
          <div class="table-wrap">
            <table>
              <thead><tr><th>模板</th><th>版本</th><th>权限数</th><th>Permission Digest</th><th>升级策略</th></tr></thead>
              <tbody>
                <tr v-for="item in templates" :key="`${item.templateCode}-${item.templateVersion}`">
                  <td><strong>{{ item.templateName || item.templateCode }}</strong><small class="mono">{{ item.templateCode }}</small></td>
                  <td>v{{ item.templateVersion }}</td><td>{{ item.permissions?.length || 0 }}</td><td class="mono muted">{{ item.permissionDigest || '—' }}</td><td>{{ item.customRoleUpgradePolicy }}</td>
                </tr>
                <tr v-if="!templates.length"><td colspan="5" class="muted">暂无已发布学校角色模板</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="access-explain" class="card explain-card">
          <header class="section-head"><div><h3>Access Explain</h3><p class="muted">解释“某个学校成员为什么能/不能管理招聘季”。IAM 通过不等于业务最终允许；学院/批次/关系仍由 Internship Domain Guard 裁决。</p></div></header>
          <form class="explain-form" @submit.prevent="explainAccess">
            <label>学校成员 User ID<input v-model.trim="explain.userId" required inputmode="numeric" placeholder="例如 1024" /></label>
            <label>模块<input v-model.trim="explain.moduleKey" required value="internship" /></label>
            <label>权限
              <select v-model="explain.permissionCode" required>
                <option v-for="item in explainPermissionOptions" :key="item.permissionCode" :value="item.permissionCode">{{ item.permissionCode }}</option>
              </select>
            </label>
            <AppButton variant="primary" type="submit" :loading="explaining">解释访问</AppButton>
          </form>

          <div v-if="explainResult" class="decision" :class="decisionClass">
            <div class="decision-head">
              <strong>{{ decisionTitle }}</strong>
              <span class="mono">{{ explainResult.reasonCode || '—' }}</span>
            </div>
            <p>{{ explainResult.message || decisionMessage }}</p>
            <p v-if="explainResult.subject" class="muted">成员：{{ explainResult.subject.realName || explainResult.subject.loginName }} · {{ explainResult.subject.loginName }} · {{ explainResult.subject.status }}</p>
            <div v-if="explainResult.catalog" class="enterprise-warning">该权限不是学校可分配权限。企业成员授权必须回 EnterpriseMember / AccessGrant。</div>
            <div v-if="explainResult.roles?.length" class="table-wrap">
              <table>
                <thead><tr><th>角色</th><th>类型</th><th>IAM</th><th>拒绝/状态原因</th><th>数据范围</th></tr></thead>
                <tbody>
                  <tr v-for="role in explainResult.roles" :key="role.roleId">
                    <td><strong>{{ role.roleName }}</strong><small class="mono">{{ role.roleCode }}</small></td><td>{{ role.roleType }}</td>
                    <td>{{ role.decision?.iamAllowed ? '通过' : '未通过' }}</td><td class="mono">{{ role.decision?.reasonCode || '—' }}</td><td>{{ scopeText(role.decision?.dataScope) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { ModulePageShell } from '@/components/business'
import { schoolIamApi } from '@/modules/system/api/schoolIam.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemIamWorkspaceView',
  components: { AppButton, ModulePageShell },
  data: () => ({
    summary: {}, catalog: {}, templates: [], loading: false, error: '', permissionKeyword: '', explaining: false, explainResult: null,
    explain: { userId: '', moduleKey: 'internship', permissionCode: 'internship.recruitment.manage' },
    surfaces: [
      { key: 'roles', label: '角色', description: '唯一 Role / RolePermission Authority', path: '/admin/system/roles' },
      { key: 'templates', label: '角色模板', description: '已发布 immutable version 与模板来源', path: '/admin/system/roles?tab=templates' },
      { key: 'members', label: '成员与业务身份', description: '角色成员、来源与复核', path: '/admin/system/role-assignments' },
      { key: 'permissions', label: '菜单与操作权限', description: '只从权威 Permission Catalog 分配', path: '/admin/system/roles?tab=permissions' },
      { key: 'dataScopes', label: '数据范围', description: '结构化 Scope，不用字符串角色猜范围', path: '/admin/system/scopes' },
      { key: 'delegations', label: '委托', description: '临时授权与工作移交', path: '/admin/system/delegations' },
      { key: 'securityChanges', label: '安全变更', description: '草稿、激活、回滚与审计', path: '/admin/system/security-changes' },
      { key: 'accessExplain', label: 'Access Explain', description: '解释模块、权限、Scope 与 Domain Guard 边界', path: '#access-explain' }
    ]
  }),
  computed: {
    filteredPermissions() {
      const q = this.permissionKeyword.toLowerCase()
      return (this.catalog.customRoleAssignablePermissions || []).filter((item) => !q || [item.permissionCode, item.moduleKey, item.featureKey, item.label].some((value) => String(value || '').toLowerCase().includes(q)))
    },
    explainPermissionOptions() {
      const items = this.catalog.assignablePermissions || []
      return items.length ? items : [{ permissionCode: 'internship.recruitment.manage' }]
    },
    decisionClass() {
      if (this.explainResult?.allowed) return 'allow'
      if (this.explainResult?.iamAllowed && this.explainResult?.finalDecision === 'NOT_EVALUATED') return 'pending'
      return 'deny'
    },
    decisionTitle() {
      if (this.explainResult?.allowed) return '最终允许'
      if (this.explainResult?.iamAllowed && this.explainResult?.finalDecision === 'NOT_EVALUATED') return 'IAM 已通过，业务最终裁决未执行'
      return '拒绝'
    },
    decisionMessage() {
      if (this.explainResult?.reasonCode === 'MODULE_NOT_ENTITLED') return '学校未购买或未获得该模块授权。'
      if (this.explainResult?.reasonCode === 'PERMISSION_DENIED') return '当前有效角色不包含该权限。'
      if (this.explainResult?.reasonCode === 'PERMISSION_NOT_SCHOOL_ASSIGNABLE') return '该权限不属于学校 IAM 分配面。'
      return '请根据 reasonCode 与角色判定链处理。'
    }
  },
  created() { this.load() },
  methods: {
    scopeText(value) {
      if (!value) return '待业务 Scope 裁决'
      return typeof value === 'string' ? value : JSON.stringify(value)
    },
    go(path) {
      if (path.startsWith('#')) return document.querySelector(path)?.scrollIntoView({ behavior: 'smooth' })
      this.$router.push(path)
    },
    async load() {
      this.loading = true; this.error = ''
      const [summary, catalog, templates] = await Promise.all([schoolIamApi.summary(), schoolIamApi.permissionCatalog(), schoolIamApi.roleTemplates()])
      this.loading = false
      const failed = [summary, catalog, templates].find((item) => item.code !== 0)
      if (failed) { this.error = failed.message; return }
      this.summary = summary.data || {}
      this.catalog = catalog.data || {}
      this.templates = templates.data?.items || []
    },
    async explainAccess() {
      const id = Number(this.explain.userId)
      if (!Number.isInteger(id) || id <= 0) return toast.error('请输入有效的学校成员 User ID')
      this.explaining = true
      const res = await schoolIamApi.accessExplain(id, this.explain)
      this.explaining = false
      if (res.code !== 0) return toast.error(res.message)
      this.explainResult = res.data
    }
  }
}
</script>

<style scoped>
.iam-page{display:grid;gap:16px}.card{background:var(--surface,#fff);border:1px solid var(--card-b,#e5e6eb);border-radius:12px;padding:18px}.hero,.section-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.eyebrow{margin:0 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;color:var(--primary,#2563eb)}h3{margin:0 0 6px}.muted{color:var(--text-secondary,#646a73)}.metrics,.surface-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metrics article{display:grid;gap:4px}.metrics strong{font-size:26px}.surface{display:grid;gap:6px;text-align:left;cursor:pointer}.surface strong{font-size:15px}.surface span{color:#646a73;min-height:38px}.surface small{color:#2563eb}.search{display:grid;gap:5px;font-size:12px}.search input,.explain-form input,.explain-form select{height:36px;border:1px solid var(--card-b,#e5e6eb);border-radius:8px;padding:0 10px}.recruitment-box{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:12px;margin:14px 0;background:#f5f8ff;border-radius:9px}.permission-chip{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;padding:4px 7px;background:white;border:1px solid #dbe7ff;border-radius:7px}.danger-text{color:#b42318}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:720px}th,td{padding:10px;border-bottom:1px solid var(--card-b,#e5e6eb);text-align:left;vertical-align:top}td small{display:block}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}.link{border:0;background:transparent;color:#2563eb;cursor:pointer}.explain-form{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr)) auto;gap:10px;align-items:end;margin:14px 0}.explain-form label{display:grid;gap:5px;font-size:13px}.decision{border-radius:10px;padding:14px;border-left:4px solid #dc2626;background:#fff7f7}.decision.pending{border-left-color:#d97706;background:#fffbeb}.decision.allow{border-left-color:#16a34a;background:#f0fdf4}.decision-head{display:flex;justify-content:space-between;gap:12px}.decision p{margin:7px 0}.enterprise-warning{padding:10px;border-radius:8px;background:#fff2f0;color:#b42318}.error{color:#b42318;background:#fff2f0}@media(max-width:900px){.explain-form{grid-template-columns:1fr}.hero,.section-head{display:grid}}
</style>
