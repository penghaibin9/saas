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
          <article class="card"><strong>{{ summary.customRoleMissingProvenanceCount || 0 }}</strong><span>缺少模板来源的 CUSTOM Role</span></article>
          <article class="card"><strong>{{ catalog.enterprisePermissionCount || 0 }}</strong><span>企业权限（仅可见，不可学校分配）</span></article>
        </section>

        <section v-if="summary.customRoleMissingProvenanceCount" class="warning card">
          <strong>存在 CUSTOM Role provenance 缺口</strong>
          <span>这些角色仍以 RolePermission 为运行时真值，但无法证明来自哪个 RoleTemplate 版本；发布/回滚前必须先修复来源登记。</span>
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
          <header class="section-head"><div><h3>学校角色模板</h3><p class="muted">已发布模板 immutable；CUSTOM Role 永远 pinned 到来源版本，升级前先看本校 impact。</p></div><button class="link" @click="go('/admin/system/roles?tab=templates')">进入模板管理</button></header>
          <div class="table-wrap">
            <table>
              <thead><tr><th>模板</th><th>当前版本</th><th>权限数</th><th>本校 pinned Role</th><th>来源版本分布</th><th>Permission Digest</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="item in templates" :key="`${item.templateCode}-${item.templateVersion}`">
                  <td><strong>{{ item.templateName || item.templateCode }}</strong><small class="mono">{{ item.templateCode }}</small></td>
                  <td>v{{ item.templateVersion }}</td>
                  <td>{{ item.permissions?.length || 0 }}</td>
                  <td>{{ item.schoolPinnedCustomRoleCount || 0 }}</td>
                  <td class="mono">{{ (item.schoolPinnedSourceVersions || []).map((v) => `v${v}`).join('、') || '—' }}</td>
                  <td class="mono muted">{{ item.permissionDigest || '—' }}</td>
                  <td><button class="link" :disabled="impactLoading === item.id" @click="loadTemplateImpact(item)">影响</button></td>
                </tr>
                <tr v-if="!templates.length"><td colspan="7" class="muted">暂无已发布学校角色模板</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="templateImpact" class="card impact-card">
          <header class="section-head">
            <div><h3>模板影响 · {{ templateImpact.templateCode }} v{{ templateImpact.templateVersion }}</h3><p class="muted">只计算当前学校租户；不会展示其他学校 pinned roles。自动升级固定为 false。</p></div>
            <button class="link" @click="templateImpact = null">关闭</button>
          </header>
          <div class="impact-summary">
            <span>受影响 pinned Role：<strong>{{ templateImpact.affectedPinnedCustomRoleCount || 0 }}</strong></span>
            <span>当前发布版本：<strong>v{{ templateImpact.currentPublishedTemplateVersion || '—' }}</strong></span>
            <span>自动升级：<strong>{{ templateImpact.automaticUpgrade ? '是' : '否' }}</strong></span>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>角色</th><th>来源模板版本</th><th>Role version</th><th>运行时漂移</th><th>若切到此版本将新增</th><th>将移除</th></tr></thead>
              <tbody>
                <tr v-for="role in templateImpact.roles || []" :key="role.roleCode">
                  <td><strong>{{ role.roleCode }}</strong><small v-if="role.runtimeRoleMissing" class="danger-text">运行时 Role 缺失</small></td>
                  <td>v{{ role.sourceTemplateVersion }}</td><td>v{{ role.roleVersion ?? '—' }}</td>
                  <td>{{ deltaText(role.runtimeVsRecorded) }}</td><td>{{ listText(role.wouldAdd) }}</td><td>{{ listText(role.wouldRemove) }}</td>
                </tr>
                <tr v-if="!(templateImpact.roles || []).length"><td colspan="6" class="muted">本校没有 pinned 到该模板的 CUSTOM Role。</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="access-explain" class="card explain-card">
          <header class="section-head"><div><h3>Access Explain</h3><p class="muted">解释“某个学校成员为什么能/不能管理招聘季”，同时展示 RoleTemplate provenance、drift、升级 impact、真实成员分页与 SecurityAuditLog。IAM 通过不等于业务最终允许；学院/批次/关系仍由 Internship Domain Guard 裁决。</p></div></header>
          <form class="explain-form" @submit.prevent="explainAccess">
            <label>学校成员 User ID<input v-model.trim="explain.userId" required inputmode="numeric" placeholder="例如 1024" /></label>
            <label>模块<input v-model.trim="explain.moduleKey" required /></label>
            <label>权限
              <select v-model="explain.permissionCode" required>
                <option v-for="item in explainPermissionOptions" :key="item.permissionCode" :value="item.permissionCode">{{ item.permissionCode }}</option>
              </select>
            </label>
            <AppButton variant="primary" type="submit" :loading="explaining">解释访问</AppButton>
          </form>

          <div v-if="explainResult" class="decision" :class="decisionClass">
            <div class="decision-head"><strong>{{ decisionTitle }}</strong><span class="mono">{{ explainResult.reasonCode || '—' }}</span></div>
            <p>{{ explainResult.message || decisionMessage }}</p>
            <p v-if="explainResult.subject" class="muted">成员：{{ explainResult.subject.realName || explainResult.subject.loginName }} · {{ explainResult.subject.loginName }} · {{ explainResult.subject.status }}</p>
            <div v-if="explainResult.catalog" class="enterprise-warning">该权限不是学校可分配权限。企业成员授权必须回 EnterpriseMember / AccessGrant。</div>
            <div v-if="explainResult.roles?.length" class="table-wrap">
              <table class="explain-table">
                <thead><tr><th>角色</th><th>IAM</th><th>模板来源</th><th>Drift</th><th>升级 Impact</th><th>原因 / Scope</th><th>真值证据</th></tr></thead>
                <tbody>
                  <tr v-for="role in explainResult.roles" :key="role.roleId">
                    <td><strong>{{ role.roleName }}</strong><small class="mono">{{ role.roleCode }} · {{ role.roleType }} · role v{{ role.roleVersion }}</small></td>
                    <td>{{ role.decision?.iamAllowed ? '通过' : '未通过' }}</td>
                    <td>{{ provenanceText(role.templateProvenance) }}</td>
                    <td :class="{ 'danger-text': role.drift?.detected }">{{ driftText(role.drift) }}</td>
                    <td>{{ impactText(role.templateImpact) }}</td>
                    <td><span class="mono">{{ role.decision?.reasonCode || '—' }}</span><small>{{ scopeText(role.decision?.dataScope) }}</small></td>
                    <td class="actions"><button class="link" @click="loadRoleEvidence(role, 'members', 1)">成员</button><button class="link" @click="loadRoleEvidence(role, 'audit', 1)">审计</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section v-if="roleEvidence" class="card evidence-card">
          <header class="section-head">
            <div><h3>{{ roleEvidence.title }}</h3><p class="muted">接口真分页：pageSize={{ roleEvidence.pageSize }}，总数 {{ roleEvidence.total }}。不会把前 50 条 preview 冒充完整结果。</p></div>
            <button class="link" @click="roleEvidence = null">关闭</button>
          </header>
          <div class="table-wrap">
            <table v-if="roleEvidence.type === 'members'">
              <thead><tr><th>User ID</th><th>姓名</th><th>登录名</th><th>状态</th></tr></thead>
              <tbody><tr v-for="item in roleEvidence.items" :key="item.id"><td class="mono">{{ item.id }}</td><td>{{ item.name }}</td><td class="mono">{{ item.loginName }}</td><td>{{ item.status }}</td></tr></tbody>
            </table>
            <table v-else>
              <thead><tr><th>时间</th><th>操作</th><th>操作者</th><th>结果</th><th>traceId</th><th>detail</th></tr></thead>
              <tbody><tr v-for="item in roleEvidence.items" :key="item.id"><td>{{ item.createdAt || '—' }}</td><td>{{ item.action }}</td><td>{{ item.operatorName || item.operatorId || '—' }}</td><td>{{ item.result }}</td><td class="mono">{{ item.traceId || '—' }}</td><td class="mono detail">{{ compactJson(item.detail) }}</td></tr></tbody>
            </table>
          </div>
          <div class="pager">
            <AppButton variant="secondary" :disabled="roleEvidence.page <= 1 || evidenceLoading" @click="changeEvidencePage(-1)">上一页</AppButton>
            <span>第 {{ roleEvidence.page }} / {{ evidencePages }} 页</span>
            <AppButton variant="secondary" :disabled="roleEvidence.page >= evidencePages || evidenceLoading" @click="changeEvidencePage(1)">下一页</AppButton>
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
    summary: {}, catalog: {}, templates: [], loading: false, error: '', permissionKeyword: '',
    explaining: false, explainResult: null, templateImpact: null, impactLoading: '',
    roleEvidence: null, evidenceLoading: false,
    explain: { userId: '', moduleKey: 'internship', permissionCode: 'internship.recruitment.manage' },
    surfaces: [
      { key: 'roles', label: '角色', description: '唯一 Role / RolePermission Authority', path: '/admin/system/roles' },
      { key: 'templates', label: '角色模板', description: 'immutable version、provenance、drift 与 impact', path: '/admin/system/roles?tab=templates' },
      { key: 'members', label: '成员与业务身份', description: '角色成员、来源与复核', path: '/admin/system/role-assignments' },
      { key: 'permissions', label: '菜单与操作权限', description: '只从权威 Permission Catalog 分配', path: '/admin/system/roles?tab=permissions' },
      { key: 'dataScopes', label: '数据范围', description: '结构化 Scope，不用字符串角色猜范围', path: '/admin/system/scopes' },
      { key: 'delegations', label: '委托', description: '临时授权与工作移交', path: '/admin/system/delegations' },
      { key: 'securityChanges', label: '安全变更', description: '草稿、激活、回滚与审计', path: '/admin/system/security-changes' },
      { key: 'accessExplain', label: 'Access Explain', description: '解释权限、Scope、模板漂移、成员与审计证据', path: '#access-explain' }
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
    evidencePages() {
      if (!this.roleEvidence) return 1
      return Math.max(1, Math.ceil(Number(this.roleEvidence.total || 0) / Number(this.roleEvidence.pageSize || 50)))
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
    listText(items) { return (items || []).length ? items.join('、') : '无' },
    compactJson(value) {
      try { return JSON.stringify(value || {}) } catch { return '{}' }
    },
    deltaText(delta) {
      if (!delta) return '—'
      const added = delta.addedInRuntime || []
      const removed = delta.removedFromRuntime || []
      if (!added.length && !removed.length) return '无运行时漂移'
      return `运行时 +${added.length} / -${removed.length}`
    },
    provenanceText(value) {
      if (!value) return '—'
      if (value.provenanceStatus === 'LEGACY_SYSTEM_ROLE') return `SYSTEM legacy · ${value.upgradePolicy}`
      if (value.provenanceStatus === 'MISSING_CUSTOM_ROLE_SOURCE') return 'CUSTOM · 来源登记缺失'
      const current = value.currentTemplateVersion == null ? '当前模板缺失' : `当前 v${value.currentTemplateVersion}`
      return `${value.sourceTemplateCode || '—'} v${value.sourceTemplateVersion ?? '—'} · ${current} · ${value.upgradePolicy || 'DERIVED_PINNED'}`
    },
    driftText(value) {
      if (!value) return '—'
      if (value.notApplicableReason) return value.b8RetirementPending ? `B8 待退 wildcard：${this.listText(value.wildcards)}` : value.notApplicableReason
      if (value.provenanceMissing) return '来源缺失，无法证明模板链'
      const runtime = value.runtimeVsRecorded || {}
      const runtimeChanged = (runtime.addedInRuntime || []).length + (runtime.removedFromRuntime || []).length
      if (!value.detected) return '无漂移'
      return `模板版本漂移=${value.templateVersionDrift ? '是' : '否'}；运行时差异 ${runtimeChanged} 项`
    },
    impactText(value) {
      if (!value) return '—'
      if (value.status !== 'READY') return value.status || '—'
      return `目标 v${value.targetTemplateVersion ?? '—'}：+${(value.wouldAdd || []).length} / -${(value.wouldRemove || []).length}；自动升级=否`
    },
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
    async loadTemplateImpact(item) {
      this.impactLoading = item.id
      const res = await schoolIamApi.templateImpact(item.id)
      this.impactLoading = ''
      if (res.code !== 0) return toast.error(res.message)
      this.templateImpact = res.data
    },
    async loadRoleEvidence(role, type, page = 1) {
      this.evidenceLoading = true
      const pageSize = 50
      const res = type === 'audit'
        ? await schoolIamApi.roleAudit(role.roleId, page, pageSize)
        : await schoolIamApi.roleMembers(role.roleId, page, pageSize)
      this.evidenceLoading = false
      if (res.code !== 0) return toast.error(res.message)
      const data = res.data || {}
      this.roleEvidence = {
        role,
        type,
        title: `${role.roleName} · ${type === 'audit' ? 'SecurityAuditLog' : '角色成员'}`,
        items: data.items || [],
        total: Number(data.total || 0),
        page: Number(data.page || page),
        pageSize: Number(data.pageSize || pageSize)
      }
    },
    changeEvidencePage(delta) {
      if (!this.roleEvidence) return
      const next = Math.max(1, Math.min(this.evidencePages, this.roleEvidence.page + delta))
      if (next !== this.roleEvidence.page) this.loadRoleEvidence(this.roleEvidence.role, this.roleEvidence.type, next)
    },
    async explainAccess() {
      const id = Number(this.explain.userId)
      if (!Number.isInteger(id) || id <= 0) return toast.error('请输入有效的学校成员 User ID')
      this.explaining = true
      const res = await schoolIamApi.accessExplain(id, this.explain)
      this.explaining = false
      if (res.code !== 0) return toast.error(res.message)
      this.explainResult = res.data
      this.roleEvidence = null
    }
  }
}
</script>

<style scoped>
.iam-page{display:grid;gap:16px}.card{background:var(--surface,#fff);border:1px solid var(--card-b,#e5e6eb);border-radius:12px;padding:18px}.hero,.section-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.eyebrow{margin:0 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;color:var(--primary,#2563eb)}h3{margin:0 0 6px}.muted{color:var(--text-secondary,#646a73)}.metrics,.surface-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metrics article{display:grid;gap:4px}.metrics strong{font-size:26px}.surface{display:grid;gap:6px;text-align:left;cursor:pointer}.surface strong{font-size:15px}.surface span{color:#646a73;min-height:38px}.surface small{color:#2563eb}.warning{display:grid;gap:5px;border-left:4px solid #d97706;background:#fffbeb}.search{display:grid;gap:5px;font-size:12px}.search input,.explain-form input,.explain-form select{height:36px;border:1px solid var(--card-b,#e5e6eb);border-radius:8px;padding:0 10px}.recruitment-box{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:12px;margin:14px 0;background:#f5f8ff;border-radius:9px}.permission-chip{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;padding:4px 7px;background:white;border:1px solid #dbe7ff;border-radius:7px}.danger-text{color:#b42318}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:780px}.explain-table{min-width:1260px}th,td{padding:10px;border-bottom:1px solid var(--card-b,#e5e6eb);text-align:left;vertical-align:top}td small{display:block;margin-top:3px}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}.detail{max-width:420px;overflow-wrap:anywhere}.link{border:0;background:transparent;color:#2563eb;cursor:pointer}.actions{white-space:nowrap}.actions .link{margin-right:6px}.impact-summary,.pager{display:flex;gap:18px;flex-wrap:wrap;align-items:center;padding:10px 0}.pager{justify-content:flex-end}.explain-form{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr)) auto;gap:10px;align-items:end;margin:14px 0}.explain-form label{display:grid;gap:5px;font-size:13px}.decision{border-radius:10px;padding:14px;border-left:4px solid #dc2626;background:#fff7f7}.decision.pending{border-left-color:#d97706;background:#fffbeb}.decision.allow{border-left-color:#16a34a;background:#f0fdf4}.decision-head{display:flex;justify-content:space-between;gap:12px}.decision p{margin:7px 0}.enterprise-warning{padding:10px;border-radius:8px;background:#fff2f0;color:#b42318}.error{color:#b42318;background:#fff2f0}@media(max-width:900px){.explain-form{grid-template-columns:1fr}.hero,.section-head{display:grid}}
</style>
