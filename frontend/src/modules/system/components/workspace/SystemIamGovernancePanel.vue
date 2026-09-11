<template>
  <ModulePageShell
    title="学校权限工作区"
    subtitle="角色、模板、成员、权限、数据范围、委托、安全变更与访问解释使用同一套学校权限真值"
    role-name="学校系统管理员 / 安全管理员"
    data-scope-name="当前学校租户"
  >
    <div class="iam-page">
      <section class="hero card">
        <div>
          <p class="eyebrow">学校权限管理工作区</p>
          <h3>学校管理员管理学校身份，不接管企业成员权限</h3>
          <p class="muted">企业管理员、人力资源人员、企业导师及企业实习权限由企业成员和访问授权功能管理，不能在这里随意分配给学校用户。</p>
        </div>
        <AppButton :loading="loading" @click="load">刷新</AppButton>
      </section>

      <section v-if="activeSurface" class="focus card" aria-live="polite">
        <div><span>当前子工作区</span><strong>{{ activeSurface.label }}</strong><small>{{ activeSurface.description }}</small></div>
        <AppButton variant="primary" @click="go(activeSurface.targetPath)">进入{{ activeSurface.label }}</AppButton>
      </section>

      <div v-if="error" class="error card">{{ error }}</div>

      <template v-else>
        <section class="metrics">
          <article class="card"><strong>{{ summary.roleCount || 0 }}</strong><span>学校角色</span></article>
          <article class="card"><strong>{{ summary.memberCount || 0 }}</strong><span>学校成员</span></article>
          <article class="card"><strong>{{ catalog.customRoleAssignablePermissions?.length || 0 }}</strong><span>自定义角色可分配权限</span></article>
          <article class="card"><strong>{{ summary.customRoleMissingProvenanceCount || 0 }}</strong><span>缺少模板来源的自定义角色</span></article>
          <article class="card"><strong>{{ catalog.enterprisePermissionCount || 0 }}</strong><span>企业权限（仅可见，不可学校分配）</span></article>
        </section>

        <section v-if="summary.customRoleMissingProvenanceCount" class="warning card">
          <strong>存在自定义角色来源缺口</strong>
          <span>这些角色仍以角色权限为运行时真值，但无法证明来自哪个角色模板版本；发布或回滚前必须先修复来源登记。</span>
        </section>

        <section class="surface-grid">
          <button v-for="item in surfaces" :key="item.key" class="surface card" @click="go(item.path)">
            <strong>{{ item.label }}</strong><span>{{ item.description }}</span><small>进入工作区 →</small>
          </button>
        </section>

        <section class="card permission-catalog" data-testid="permission-catalog-workspace">
          <header class="permission-catalog__header">
            <div><h3>学校可分配权限目录</h3><p class="muted">按业务域和功能分组查找；中文名称用于办理，权限编码用于核对。</p></div>
            <div class="permission-catalog__tools">
              <label class="permission-search"><span class="sr-only">搜索权限</span><input v-model.trim="permissionKeyword" placeholder="搜索权限名称或权限编码" /></label>
              <div class="permission-filters" aria-label="权限风险筛选">
                <button v-for="filter in permissionRiskFilters" :key="filter.value" type="button" :class="{ active: permissionRiskFilter === filter.value }" @click="permissionRiskFilter = filter.value">
                  {{ filter.label }} <b>{{ permissionFilterCount(filter.value) }}</b>
                </button>
              </div>
            </div>
          </header>

          <div class="recruitment-box">
            <strong>常用专题 · 招聘季学校侧权限</strong>
            <span v-for="item in catalog.internshipRecruitmentPermissions || []" :key="item.permissionCode" class="permission-chip">{{ permissionDisplayLabel(item) }}</span>
            <span v-if="!(catalog.internshipRecruitmentPermissions || []).length" class="danger-text">招聘季权限未进入权限目录，禁止继续配置</span>
          </div>

          <div class="permission-browser">
            <nav class="permission-domains" aria-label="权限业务域">
              <h4>业务域导航</h4>
              <button v-for="domain in permissionDomains" :key="domain.key" type="button" :class="{ active: activePermissionDomain === domain.key }" @click="selectPermissionDomain(domain.key)">
                <span>{{ domain.label }}</span><b>{{ domain.count }}</b>
              </button>
            </nav>

            <div class="permission-groups">
              <header class="permission-groups__summary">
                <div><h4>{{ activePermissionDomainLabel }} <span>（{{ visiblePermissionCount }} 项）</span></h4><p>{{ activePermissionDomainDescription }}</p></div>
                <div><button type="button" @click="setAllFeatureGroups(true)">展开全部</button><i aria-hidden="true" /> <button type="button" @click="setAllFeatureGroups(false)">收起全部</button></div>
              </header>

              <section v-for="group in permissionFeatureGroups" :key="group.key" class="permission-feature">
                <button type="button" class="permission-feature__head" :aria-expanded="isFeatureGroupOpen(group.key)" @click="toggleFeatureGroup(group.key)">
                  <strong>{{ group.label }}</strong><b>{{ group.rows.length }}</b><small>{{ group.description }}</small>
                  <span class="permission-feature__toggle">{{ isFeatureGroupOpen(group.key) ? '收起' : '展开' }}</span>
                </button>
                <div v-if="isFeatureGroupOpen(group.key)" class="permission-rows">
                  <div class="permission-row permission-row--head"><span>权限名称</span><span>权限编码</span><span>风险等级</span><span>自定义角色</span></div>
                  <div v-for="item in group.rows" :key="item.permissionCode" class="permission-row">
                    <span class="permission-row__name"><strong>{{ permissionDisplayLabel(item) }}</strong><small>{{ permissionDescription(item) }}</small></span>
                    <code>{{ item.permissionCode }}</code>
                    <span><b class="risk-pill" :class="`risk-pill--${riskTone(item.riskLevel)}`">{{ riskLevelLabel(item.riskLevel) }}</b></span>
                    <span>{{ item.customRoleAssignable ? '可分配' : '仅系统策略' }}</span>
                  </div>
                </div>
              </section>
              <div v-if="!permissionFeatureGroups.length" class="permission-empty"><b>没有匹配的权限</b><p>可更换业务域、风险条件或搜索关键词。</p></div>
            </div>
          </div>
        </section>

        <section class="card">
          <header class="section-head"><div><h3>学校角色模板</h3><p class="muted">已发布模板不可修改；自定义角色始终固定到来源版本，升级前需先查看本校影响。</p></div><button class="link" @click="go('/admin/system/roles?tab=templates')">进入模板管理</button></header>
          <div class="table-wrap">
            <table>
              <thead><tr><th>模板</th><th>当前版本</th><th>权限数</th><th>本校已绑定角色</th><th>来源版本分布</th><th>权限摘要</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="item in templates" :key="`${item.templateCode}-${item.templateVersion}`">
                  <td><strong>{{ roleLabel(item.templateCode, item.templateName) }}</strong></td>
                  <td>第 {{ item.templateVersion }} 版</td>
                  <td>{{ item.permissions?.length || 0 }}</td>
                  <td>{{ item.schoolPinnedCustomRoleCount || 0 }}</td>
                  <td>{{ (item.schoolPinnedSourceVersions || []).map((v) => `第 ${v} 版`).join('、') || '—' }}</td>
                  <td>{{ item.permissionDigest ? '已生成' : '—' }}</td>
                  <td><button class="link" :disabled="impactLoading === item.id" @click="loadTemplateImpact(item)">影响</button></td>
                </tr>
                <tr v-if="!templates.length"><td colspan="7" class="muted">暂无已发布学校角色模板</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="templateImpact" class="card impact-card">
          <header class="section-head">
            <div><h3>模板影响 · {{ roleLabel(templateImpact.templateCode) }} 第 {{ templateImpact.templateVersion }} 版</h3><p class="muted">只计算当前学校租户；不会展示其他学校已绑定角色。自动升级固定为关闭。</p></div>
            <button class="link" @click="templateImpact = null">关闭</button>
          </header>
          <div class="impact-summary">
            <span>受影响的已绑定角色：<strong>{{ templateImpact.affectedPinnedCustomRoleCount || 0 }}</strong></span>
            <span>当前发布版本：<strong>第 {{ templateImpact.currentPublishedTemplateVersion || '—' }} 版</strong></span>
            <span>自动升级：<strong>{{ templateImpact.automaticUpgrade ? '是' : '否' }}</strong></span>
          </div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>角色</th><th>来源模板版本</th><th>角色版本</th><th>运行时漂移</th><th>若切到此版本将新增</th><th>将移除</th></tr></thead>
              <tbody>
                <tr v-for="role in templateImpact.roles || []" :key="role.roleCode">
                  <td><strong>{{ roleLabel(role.roleCode, role.roleName) }}</strong><small v-if="role.runtimeRoleMissing" class="danger-text">运行时角色缺失</small></td>
                  <td>第 {{ role.sourceTemplateVersion }} 版</td><td>第 {{ role.roleVersion ?? '—' }} 版</td>
                  <td>{{ deltaText(role.runtimeVsRecorded) }}</td><td>{{ listText(role.wouldAdd) }}</td><td>{{ listText(role.wouldRemove) }}</td>
                </tr>
                <tr v-if="!(templateImpact.roles || []).length"><td colspan="6" class="muted">本校没有绑定到该模板的自定义角色。</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section id="access-explain" class="card explain-card">
          <header class="section-head"><div><h3>访问解释</h3><p class="muted">解释“某个学校成员为什么能或不能访问具体对象”。身份权限通过不等于业务最终允许；数据范围目标与业务对象上下文会交给权威业务守卫裁决，缺失上下文时后端将继续按拒绝处理。</p></div></header>
          <form class="explain-form" @submit.prevent="explainAccess">
            <label>学校成员编号<input v-model.trim="explain.userId" required inputmode="numeric" placeholder="例如 1024" /></label>
            <label>模块<input v-model.trim="explain.moduleKey" required /></label>
            <label>权限
              <select v-model="explain.permissionCode" required>
                <option v-for="item in explainPermissionOptions" :key="item.permissionCode" :value="item.permissionCode">{{ permissionDisplayLabel(item) }}</option>
              </select>
            </label>
            <label>数据范围目标类型
              <select v-model="explain.scopeTargetType" required>
                <option value="COLLEGE">学院</option><option value="MAJOR">专业</option><option value="CLASS">班级</option><option value="TERMINAL">终端范围</option>
              </select>
            </label>
            <label>数据范围目标编号<input v-model.trim="explain.scopeTargetId" required placeholder="学院、专业或班级编号" /></label>
            <label>业务对象类型
              <select v-model="explain.resourceType" required>
                <option value="STUDENT">学生</option><option value="INTERN_STUDENT">实习学生</option><option value="GRADUATION_STUDENT">毕设学生</option><option value="USER">用户</option><option value="CLASS">班级</option><option value="MAJOR">专业</option><option value="COLLEGE">学院</option><option value="BUILDING">楼栋</option><option value="DORM_BUILDING">宿舍楼</option>
              </select>
            </label>
            <label>业务对象编号<input v-model.trim="explain.resourceId" required placeholder="被解释的具体对象编号" /></label>
            <AppButton variant="primary" type="submit" :loading="explaining">解释访问</AppButton>
          </form>

          <div v-if="explainResult" class="decision" :class="decisionClass">
            <div class="decision-head"><strong>{{ decisionTitle }}</strong><span>{{ reasonCodeLabel(explainResult.reasonCode) }}</span></div>
            <p>{{ explainResult.message || decisionMessage }}</p>
            <p v-if="explainResult.subject" class="muted">成员：{{ explainResult.subject.realName || explainResult.subject.loginName }} · {{ explainResult.subject.loginName }} · {{ memberStatusLabel(explainResult.subject.status) }}</p>
            <div class="context-evidence">
              <span>最终裁决：<strong>{{ decisionLabel(explainResult.finalDecision) }}</strong></span>
              <span>数据范围：<strong>{{ scopeTypeLabel(explainResult.scopeTargetType) }}：{{ explainResult.scopeTargetId || '—' }}</strong></span>
              <span>业务对象：<strong>{{ resourceTypeLabel(explainResult.resourceType) }}</strong> · {{ explainResult.resourceIdSupplied ? '编号已提供' : '编号缺失' }}</span>
            </div>
            <div v-if="explainResult.catalog" class="enterprise-warning">该权限不是学校可分配权限。企业成员授权必须回到企业成员与访问授权功能办理。</div>
            <div v-if="explainResult.roles?.length" class="table-wrap">
              <table class="explain-table">
                <thead><tr><th>角色</th><th>身份权限</th><th>模板来源</th><th>配置偏移</th><th>升级影响</th><th>原因 / 数据范围</th><th>真实证据</th></tr></thead>
                <tbody>
                  <tr v-for="role in explainResult.roles" :key="role.roleId">
                    <td><strong>{{ roleLabel(role.roleCode, role.roleName) }}</strong><small>{{ roleTypeLabel(role.roleType) }} · 第 {{ role.roleVersion }} 版</small></td>
                    <td>{{ role.decision?.iamAllowed ? '通过' : '未通过' }}</td>
                    <td>{{ provenanceText(role.templateProvenance) }}</td>
                    <td :class="{ 'danger-text': role.drift?.detected }">{{ driftText(role.drift) }}</td>
                    <td>{{ impactText(role.templateImpact) }}</td>
                    <td><span>{{ reasonCodeLabel(role.decision?.reasonCode) }}</span><small>{{ scopeText(role.decision?.dataScope) }}</small></td>
                    <td class="actions"><button class="link" @click="loadRoleEvidence(role, 'members', 1)">成员</button><button class="link" @click="loadRoleEvidence(role, 'audit', 1)">审计</button></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </section>

        <section v-if="roleEvidence" class="card evidence-card">
          <header class="section-head">
            <div><h3>{{ roleEvidence.title }}</h3><p class="muted">服务端真实分页：每页 {{ roleEvidence.pageSize }} 条，总数 {{ roleEvidence.total }}。不会把前 50 条预览数据当作完整结果。</p></div>
            <button class="link" @click="roleEvidence = null">关闭</button>
          </header>
          <div class="table-wrap">
            <table v-if="roleEvidence.type === 'members'">
              <thead><tr><th>用户编号</th><th>姓名</th><th>登录名</th><th>状态</th></tr></thead>
              <tbody><tr v-for="item in roleEvidence.items" :key="item.id"><td class="mono">{{ item.id }}</td><td>{{ item.name }}</td><td class="mono">{{ item.loginName }}</td><td>{{ memberStatusLabel(item.status) }}</td></tr></tbody>
            </table>
            <table v-else>
              <thead><tr><th>时间</th><th>操作</th><th>操作者</th><th>结果</th><th>问题编号</th><th>详情</th></tr></thead>
              <tbody><tr v-for="item in roleEvidence.items" :key="item.id"><td>{{ item.createdAt || '—' }}</td><td>{{ auditRecord(item).displayAction }}</td><td>{{ item.operatorName || item.operatorId || '—' }}</td><td>{{ auditRecord(item).displayResult }}</td><td class="mono">{{ item.traceId || '—' }}</td><td class="detail">{{ detailSummary(item.detail) }}</td></tr></tbody>
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
import { roleDisplayLabel, permissionDisplayLabel } from '@/modules/system/utils/permissionLabels'
import { AppButton } from '@/components/ui'
import { ModulePageShell } from '@/components/business'
import { schoolIamApi } from '@/modules/system/api/schoolIam.api'
import { toast } from '@/utils/toast'
import { presentAuditRecord } from '@/utils/presentationSafety'

const REASON_LABELS = { MODULE_NOT_ENTITLED: '模块未授权', PERMISSION_DENIED: '权限不足', PERMISSION_NOT_SCHOOL_ASSIGNABLE: '学校不可分配', SCOPE_DENIED: '超出数据范围', RESOURCE_NOT_FOUND: '业务对象不存在', ALLOWED: '允许访问', ROLE_INACTIVE: '角色未生效' }
const DECISION_LABELS = { ALLOW: '允许', DENY: '拒绝', NOT_EVALUATED: '待业务裁决', PENDING: '待确认' }
const SCOPE_TYPE_LABELS = { COLLEGE: '学院', MAJOR: '专业', CLASS: '班级', TERMINAL: '终端范围', TENANT: '全校', SELF: '本人' }
const RESOURCE_TYPE_LABELS = { STUDENT: '学生', INTERN_STUDENT: '实习学生', GRADUATION_STUDENT: '毕设学生', USER: '用户', CLASS: '班级', MAJOR: '专业', COLLEGE: '学院', BUILDING: '楼栋', DORM_BUILDING: '宿舍楼' }
const ROLE_TYPE_LABELS = { SYSTEM: '系统角色', CUSTOM: '自定义角色', TEMPLATE: '模板角色', BUSINESS: '业务角色' }
const RISK_LEVEL_LABELS = { LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险', CRITICAL: '重大风险' }
const MODULE_LABELS = { internship: '实习管理', student: '学生管理', academic: '教务管理', graduation: '毕业管理', system: '系统管理', platform: '平台管理' }
const PERMISSION_DOMAINS = [
  { key: 'all', label: '全部权限', description: '查看学校可分配的全部权限。' },
  { key: 'system', label: '系统与身份', description: '账号安全、身份核验、登录控制、角色权限与审计。' },
  { key: 'student', label: '学工管理', description: '学生事务、迎新、资助、宿舍与日常管理。' },
  { key: 'academic', label: '教务管理', description: '教学运行、课程、考试、成绩与学籍办理。' },
  { key: 'internship', label: '岗位实习', description: '实习安排、招聘季、过程管理与风险处置。' },
  { key: 'graduation', label: '毕业设计', description: '课题、指导、评阅、答辩与归档。' },
  { key: 'employment', label: '就业管理', description: '就业去向、材料核验、跟进与统计。' }
]
const FEATURE_LABELS = {
  phone: ['手机号治理与认证', '管理手机号登录凭据、本人验证和安全策略。'],
  identity: ['身份核验', '身份、账号与本人关系核验相关权限。'],
  role: ['权限与角色管理', '角色、成员、权限分配与回收相关权限。'],
  audit: ['审计与合规', '登录日志、敏感操作和安全审计相关权限。'],
  import: ['导入与数据交换', '模板、导入任务、校验与结果查看相关权限。'],
  recruitment: ['招聘季管理', '招聘季、企业邀请与岗位投递相关权限。'],
  default: ['业务办理权限', '本业务域下的查看、办理与管理权限。']
}

export default {
  name: 'SystemIamWorkspaceView',
  components: { AppButton, ModulePageShell },
  data: () => ({
    summary: {}, catalog: {}, templates: [], loading: false, error: '', permissionKeyword: '',
    activePermissionDomain: 'system', permissionRiskFilter: 'all', openPermissionGroups: [],
    explaining: false, explainResult: null, templateImpact: null, impactLoading: '',
    roleEvidence: null, evidenceLoading: false,
    explain: {
      userId: '', moduleKey: 'internship', permissionCode: 'internship.recruitment.manage',
      scopeTargetType: 'COLLEGE', scopeTargetId: '', resourceType: 'STUDENT', resourceId: ''
    },
    surfaces: [
      { key: 'roles', label: '角色', description: '统一管理角色与角色权限', path: '/admin/system/iam?surface=roles', targetPath: '/admin/system/roles?tab=members' },
      { key: 'templates', label: '角色模板', description: '管理不可变版本、来源、配置偏移与升级影响', path: '/admin/system/iam?surface=templates', targetPath: '/admin/system/roles?tab=templates' },
      { key: 'members', label: '成员与业务身份', description: '角色成员、来源与复核', path: '/admin/system/role-assignments' },
      { key: 'permissions', label: '菜单与操作权限', description: '只从权威权限目录分配', path: '/admin/system/iam?surface=permissions', targetPath: '/admin/system/roles?tab=permissions' },
      { key: 'dataScopes', label: '数据范围', description: '使用结构化范围，不根据角色名称猜测范围', path: '/admin/system/scopes' },
      { key: 'delegations', label: '委托', description: '临时授权与工作移交', path: '/admin/system/delegations' },
      { key: 'securityChanges', label: '安全变更', description: '草稿、激活、回滚与审计', path: '/admin/system/security-changes' },
      { key: 'accessExplain', label: '访问解释', description: '解释权限、数据范围、模板偏移、成员与审计证据', path: '#access-explain' }
    ]
  }),
  computed: {
    activeSurface() {
      const key = String(this.$route.query.surface || '')
      return this.surfaces.find((item) => item.key === key) || null
    },
    allCatalogPermissions() { return this.catalog.customRoleAssignablePermissions || [] },
    filteredPermissions() {
      const q = this.permissionKeyword.toLowerCase()
      return this.allCatalogPermissions.filter((item) => {
        const matchesDomain = this.activePermissionDomain === 'all' || this.permissionDomainKey(item) === this.activePermissionDomain
        const risk = String(item.riskLevel || '').toUpperCase()
        const matchesRisk = this.permissionRiskFilter === 'all' || (this.permissionRiskFilter === 'high' ? ['HIGH', 'CRITICAL'].includes(risk) : !['HIGH', 'CRITICAL'].includes(risk))
        const matchesKeyword = !q || [item.permissionCode, item.moduleKey, item.featureKey, item.label, item.featureLabel].some((value) => String(value || '').toLowerCase().includes(q))
        return matchesDomain && matchesRisk && matchesKeyword
      })
    },
    permissionRiskFilters() { return [{ value: 'all', label: '全部' }, { value: 'high', label: '高风险' }, { value: 'normal', label: '中低风险' }] },
    permissionDomains() {
      return PERMISSION_DOMAINS.map(domain => ({ ...domain, count: domain.key === 'all' ? this.allCatalogPermissions.length : this.allCatalogPermissions.filter(item => this.permissionDomainKey(item) === domain.key).length })).filter(domain => domain.key === 'all' || domain.count)
    },
    activePermissionDomainMeta() { return PERMISSION_DOMAINS.find(domain => domain.key === this.activePermissionDomain) || PERMISSION_DOMAINS[0] },
    activePermissionDomainLabel() { return this.activePermissionDomainMeta.label },
    activePermissionDomainDescription() { return this.activePermissionDomainMeta.description },
    visiblePermissionCount() { return this.filteredPermissions.length },
    permissionFeatureGroups() {
      const groups = new Map()
      this.filteredPermissions.forEach(item => {
        const feature = this.permissionFeatureMeta(item)
        if (!groups.has(feature.key)) groups.set(feature.key, { ...feature, rows: [] })
        groups.get(feature.key).rows.push(item)
      })
      return [...groups.values()]
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
      if (this.explainResult?.iamAllowed && this.explainResult?.finalDecision === 'NOT_EVALUATED') return '身份权限已通过，业务最终裁决未执行'
      return '拒绝'
    },
    decisionMessage() {
      if (this.explainResult?.reasonCode === 'MODULE_NOT_ENTITLED') return '学校未购买或未获得该模块授权。'
      if (this.explainResult?.reasonCode === 'PERMISSION_DENIED') return '当前有效角色不包含该权限。'
      if (this.explainResult?.reasonCode === 'PERMISSION_NOT_SCHOOL_ASSIGNABLE') return '该权限不属于学校权限分配范围。'
      return '请根据判定原因与角色判定链处理。'
    }
  },
  created() { this.load() },
  methods: {
    roleLabel: roleDisplayLabel,
    auditRecord(row) { return presentAuditRecord(row) },
    permissionDisplayLabel(item) { return permissionDisplayLabel(item?.permissionCode, item?.label) },
    moduleFeatureLabel(item) {
      const moduleLabel = MODULE_LABELS[String(item?.moduleKey || '').toLowerCase()] || '业务模块'
      return item?.featureLabel ? `${moduleLabel} / ${item.featureLabel}` : moduleLabel
    },
    permissionDomainKey(item) {
      const raw = `${item?.moduleKey || ''} ${item?.permissionCode || ''}`.toLowerCase()
      if (/internship|recruitment/.test(raw)) return 'internship'
      if (/graduation|thesis|defense/.test(raw)) return 'graduation'
      if (/employment/.test(raw)) return 'employment'
      if (/academic|course|grade|exam|schedule|teaching/.test(raw)) return 'academic'
      if (/studentaffairs|student_affairs|orientation|campus|dorm|aid|funding|discipline/.test(raw)) return 'student'
      return 'system'
    },
    permissionFeatureMeta(item) {
      const raw = `${item?.featureKey || ''} ${item?.permissionCode || ''}`.toLowerCase()
      let type = 'default'
      if (/phone|mobile|credential|recover/.test(raw)) type = 'phone'
      else if (/identity|account|user/.test(raw)) type = 'identity'
      else if (/role|permission|scope|delegat/.test(raw)) type = 'role'
      else if (/audit|log|security/.test(raw)) type = 'audit'
      else if (/import|export|exchange|sync/.test(raw)) type = 'import'
      else if (/recruit/.test(raw)) type = 'recruitment'
      const [fallbackLabel, fallbackDescription] = FEATURE_LABELS[type]
      const serverLabel = String(item?.featureLabel || '').trim()
      const displayParts = this.permissionDisplayLabel(item).split('·').map(value => value.trim()).filter(Boolean)
      const displayFeature = displayParts.length > 2 ? displayParts.slice(1, -1).join(' · ') : ''
      const label = /[㐀-鿿]/.test(serverLabel) ? serverLabel : (type === 'default' && displayFeature ? displayFeature : fallbackLabel)
      const description = type === 'default' && displayFeature ? `${displayFeature}相关的查看、办理与管理权限。` : fallbackDescription
      return { key: `${this.permissionDomainKey(item)}:${type}:${label}`, label, description }
    },
    permissionDescription(item) {
      const value = String(item?.description || item?.featureDescription || '').trim()
      return /[㐀-鿿]/.test(value) ? value : this.moduleFeatureLabel(item)
    },
    permissionFilterCount(filter) {
      const source = this.activePermissionDomain === 'all' ? this.allCatalogPermissions : this.allCatalogPermissions.filter(item => this.permissionDomainKey(item) === this.activePermissionDomain)
      if (filter === 'high') return source.filter(item => ['HIGH', 'CRITICAL'].includes(String(item.riskLevel || '').toUpperCase())).length
      if (filter === 'normal') return source.filter(item => !['HIGH', 'CRITICAL'].includes(String(item.riskLevel || '').toUpperCase())).length
      return source.length
    },
    selectPermissionDomain(key) {
      this.activePermissionDomain = key; this.openPermissionGroups = []
      this.$nextTick(() => { if (this.permissionFeatureGroups[0]) this.openPermissionGroups = [this.permissionFeatureGroups[0].key] })
    },
    isFeatureGroupOpen(key) { return this.openPermissionGroups.includes(key) },
    toggleFeatureGroup(key) { this.openPermissionGroups = this.isFeatureGroupOpen(key) ? this.openPermissionGroups.filter(item => item !== key) : [...this.openPermissionGroups, key] },
    setAllFeatureGroups(open) { this.openPermissionGroups = open ? this.permissionFeatureGroups.map(group => group.key) : [] },
    riskTone(value) { const risk = String(value || '').toUpperCase(); return risk === 'CRITICAL' ? 'critical' : risk === 'HIGH' ? 'high' : risk === 'MEDIUM' ? 'medium' : 'low' },
    riskLevelLabel(value) { return RISK_LEVEL_LABELS[String(value || '').toUpperCase()] || '风险待确认' },
    reasonCodeLabel(value) { return REASON_LABELS[value] || (value ? '其他判定原因' : '—') },
    decisionLabel(value) { return DECISION_LABELS[value] || (value ? '裁决待确认' : '—') },
    scopeTypeLabel(value) { return SCOPE_TYPE_LABELS[value] || (value ? '其他数据范围' : '—') },
    resourceTypeLabel(value) { return RESOURCE_TYPE_LABELS[value] || (value ? '其他业务对象' : '—') },
    roleTypeLabel(value) { return ROLE_TYPE_LABELS[value] || (value ? '其他角色类型' : '—') },
    detailSummary(value) {
      if (!value) return '无补充详情'
      if (typeof value === 'string' && /[\u3400-\u9fff]/.test(value)) return value
      if (typeof value === 'object') return `已记录 ${Object.keys(value).length} 项结构化详情`
      return '已记录补充详情'
    },
    memberStatusLabel(status) {
      return { ACTIVE: '正常', DISABLED: '已停用', LOCKED: '已锁定', EXPIRED: '已过期' }[status] || '状态待确认'
    },
    listText(items) { return (items || []).length ? items.map(code => permissionDisplayLabel(code)).join('、') : '无' },
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
      if (value.provenanceStatus === 'LEGACY_SYSTEM_ROLE') return '历史系统角色'
      if (value.provenanceStatus === 'MISSING_CUSTOM_ROLE_SOURCE') return '自定义角色 · 来源登记缺失'
      const current = value.currentTemplateVersion == null ? '当前模板缺失' : `当前第 ${value.currentTemplateVersion} 版`
      return `来源第 ${value.sourceTemplateVersion ?? '—'} 版 · ${current} · 固定来源版本`
    },
    driftText(value) {
      if (!value) return '—'
      if (value.notApplicableReason) return value.b8RetirementPending ? `待移除通配权限：${this.listText(value.wildcards)}` : '不适用'
      if (value.provenanceMissing) return '来源缺失，无法证明模板链'
      const runtime = value.runtimeVsRecorded || {}
      const runtimeChanged = (runtime.addedInRuntime || []).length + (runtime.removedFromRuntime || []).length
      if (!value.detected) return '无漂移'
      return `模板版本漂移=${value.templateVersionDrift ? '是' : '否'}；运行时差异 ${runtimeChanged} 项`
    },
    impactText(value) {
      if (!value) return '—'
      if (value.status !== 'READY') return '影响分析待完成'
      return `目标第 ${value.targetTemplateVersion ?? '—'} 版：新增 ${(value.wouldAdd || []).length} 项，移除 ${(value.wouldRemove || []).length} 项；自动升级已关闭`
    },
    scopeText(value) {
      if (!value) return '待业务数据范围裁决'
      return typeof value === 'string' && /[\u3400-\u9fff]/.test(value) ? value : '已记录数据范围'
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
      if (!this.permissionDomains.some(domain => domain.key === this.activePermissionDomain)) this.activePermissionDomain = this.permissionDomains.find(domain => domain.key !== 'all')?.key || 'all'
      this.$nextTick(() => { if (!this.openPermissionGroups.length && this.permissionFeatureGroups[0]) this.openPermissionGroups = [this.permissionFeatureGroups[0].key] })
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
        title: `${role.roleName} · ${type === 'audit' ? '安全审计日志' : '角色成员'}`,
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
      if (!Number.isInteger(id) || id <= 0) return toast.error('请输入有效的学校成员编号')
      if (!this.explain.scopeTargetType || !this.explain.scopeTargetId || !this.explain.resourceType || !this.explain.resourceId) {
        return toast.error('访问解释必须提供完整的数据范围目标与业务对象信息')
      }
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
.iam-page{display:grid;gap:16px}.card{background:var(--surface,#fff);border:1px solid var(--card-b,#e5e6eb);border-radius:12px;padding:18px}.hero,.section-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.eyebrow{margin:0 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;color:var(--primary,#2563eb)}h3{margin:0 0 6px}.muted{color:var(--text-secondary,#646a73)}.metrics,.surface-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.metrics article{display:grid;gap:4px}.metrics strong{font-size:26px}.surface{display:grid;gap:6px;text-align:left;cursor:pointer}.surface strong{font-size:15px}.surface span{color:#646a73;min-height:38px}.surface small{color:#2563eb}.warning{display:grid;gap:5px;border-left:4px solid #d97706;background:#fffbeb}.search{display:grid;gap:5px;font-size:12px}.search input,.explain-form input,.explain-form select{height:36px;border:1px solid var(--card-b,#e5e6eb);border-radius:8px;padding:0 10px}.recruitment-box{display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:12px;margin:14px 0;background:#f5f8ff;border-radius:9px}.permission-chip{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;padding:4px 7px;background:white;border:1px solid #dbe7ff;border-radius:7px}.danger-text{color:#b42318}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:780px}.explain-table{min-width:1260px}th,td{padding:10px;border-bottom:1px solid var(--card-b,#e5e6eb);text-align:left;vertical-align:top}td small{display:block;margin-top:3px}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}.detail{max-width:420px;overflow-wrap:anywhere}.link{border:0;background:transparent;color:#2563eb;cursor:pointer}.actions{white-space:nowrap}.actions .link{margin-right:6px}.impact-summary,.pager,.context-evidence{display:flex;gap:18px;flex-wrap:wrap;align-items:center;padding:10px 0}.context-evidence{margin:8px 0;border-top:1px solid var(--card-b,#e5e6eb);border-bottom:1px solid var(--card-b,#e5e6eb)}.pager{justify-content:flex-end}.explain-form{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:10px;align-items:end;margin:14px 0}.explain-form label{display:grid;gap:5px;font-size:13px}.decision{border-radius:10px;padding:14px;border-left:4px solid #dc2626;background:#fff7f7}.decision.pending{border-left-color:#d97706;background:#fffbeb}.decision.allow{border-left-color:#16a34a;background:#f0fdf4}.decision-head{display:flex;justify-content:space-between;gap:12px}.decision p{margin:7px 0}.enterprise-warning{padding:10px;border-radius:8px;background:#fff2f0;color:#b42318}.error{color:#b42318;background:#fff2f0}@media(max-width:900px){.explain-form{grid-template-columns:1fr}.hero,.section-head{display:grid}}
.permission-catalog{padding:20px}.permission-catalog__header{display:flex;justify-content:space-between;gap:24px;align-items:flex-start}.permission-catalog__header h3{font-size:20px}.permission-catalog__tools{display:grid;justify-items:end;gap:10px;min-width:min(100%,610px)}.permission-search{width:min(100%,390px)}.permission-search input{box-sizing:border-box;width:100%;height:40px;padding:0 13px;border:1px solid #c9d8f4;border-radius:8px;background:#fff;color:var(--text-primary,#1f2937);font:inherit}.permission-search input:focus{outline:2px solid #2563eb;outline-offset:1px}.permission-filters{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.permission-filters button,.permission-groups__summary button{border:1px solid #d7e2f6;border-radius:7px;background:#fff;color:#45617f;padding:7px 11px;cursor:pointer}.permission-filters button.active{border-color:#2f68d9;background:#edf4ff;color:#1f5bc1}.permission-filters b{margin-left:4px}.permission-browser{display:grid;grid-template-columns:190px minmax(0,1fr);gap:18px;margin-top:16px}.permission-domains{padding:12px 8px;border-radius:10px;background:#f6f9fe}.permission-domains h4{margin:4px 10px 10px;font-size:14px}.permission-domains button{display:flex;width:100%;justify-content:space-between;gap:12px;padding:11px 10px;border:0;border-radius:8px;background:transparent;color:#526b88;font:inherit;text-align:left;cursor:pointer}.permission-domains button:hover{background:#eef4ff}.permission-domains button.active{background:#e7f0ff;color:#1f5bc1;font-weight:650}.permission-domains b{font-size:12px}.permission-groups{min-width:0}.permission-groups__summary{display:flex;justify-content:space-between;gap:16px;align-items:center;padding:13px 15px;border-radius:9px;background:#f2f6fc}.permission-groups__summary h4{margin:0 0 4px;font-size:16px}.permission-groups__summary h4 span{font-size:13px;color:#526b88}.permission-groups__summary p{margin:0;color:#667b96;font-size:13px}.permission-groups__summary>div:last-child{display:flex;align-items:center;white-space:nowrap}.permission-groups__summary i{width:1px;height:18px;background:#d8e1ef}.permission-groups__summary button{border:0;background:transparent;color:#2563eb;padding:6px 9px}.permission-feature{margin-top:10px;border:1px solid #dae4f3;border-radius:9px;overflow:hidden}.permission-feature__head{display:grid;grid-template-columns:auto auto minmax(160px,1fr) auto;align-items:center;gap:10px;width:100%;padding:12px 15px;border:0;background:#f7f9fd;color:#18304f;text-align:left;cursor:pointer}.permission-feature__head:hover{background:#eff5ff}.permission-feature__head>b{display:grid;place-items:center;min-width:24px;height:22px;padding:0 6px;border-radius:11px;background:#e5eefc;color:#335b91;font-size:12px}.permission-feature__head small{color:#70829a}.permission-feature__toggle{color:#2563eb;font-size:12px}.permission-rows{background:#fff}.permission-row{display:grid;grid-template-columns:minmax(250px,1.5fr) minmax(220px,1fr) 120px 110px;gap:16px;align-items:center;min-height:52px;padding:8px 16px;border-top:1px solid #e5ebf4}.permission-row--head{min-height:34px;background:#f9fbfe;color:#657991;font-size:12px;font-weight:650}.permission-row__name{display:grid;gap:3px}.permission-row__name strong{font-size:14px;color:#172b4d}.permission-row__name small{color:#72839a;font-size:12px}.permission-row code{overflow-wrap:anywhere;color:#587090;font-size:12px}.risk-pill{display:inline-flex;padding:4px 8px;border-radius:999px;font-size:12px;font-weight:600}.risk-pill--low{background:#eaf8f0;color:#197a49}.risk-pill--medium{background:#fff4d8;color:#a15c00}.risk-pill--high{background:#ffebe8;color:#c33b2d}.risk-pill--critical{background:#ffe1e1;color:#b42318}.permission-empty{padding:48px 20px;text-align:center;color:#667b96}.permission-empty p{margin:6px 0}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(max-width:1100px){.permission-catalog__header{display:grid}.permission-catalog__tools{justify-items:stretch;min-width:0}.permission-search{width:100%}.permission-filters{justify-content:flex-start}.permission-browser{grid-template-columns:1fr}.permission-domains{display:flex;gap:6px;overflow:auto}.permission-domains h4{display:none}.permission-domains button{flex:0 0 auto;width:auto}.permission-row{grid-template-columns:minmax(220px,1.5fr) minmax(180px,1fr) 100px 90px}}
@media(max-width:760px){.permission-groups__summary{align-items:flex-start;flex-direction:column}.permission-feature__head{grid-template-columns:auto minmax(0,1fr) auto}.permission-feature__head small{grid-column:1/-1}.permission-row,.permission-row--head{grid-template-columns:1fr}.permission-row--head{display:none}.permission-row{gap:6px;padding:12px}.permission-row code{order:2}.explain-form{grid-template-columns:1fr}.hero,.section-head{display:grid}}
.permission-catalog{order:-1}.permission-catalog__tools{display:flex;align-items:center;justify-content:flex-end;min-width:0}.permission-search{width:min(100%,300px)}.permission-filters{flex-wrap:nowrap}.permission-catalog .permission-chip{font-family:inherit}
@media(max-width:1100px){.permission-catalog__tools{justify-content:flex-start;width:100%}.permission-search{width:min(100%,360px)}}
@media(max-width:760px){.permission-catalog__tools{align-items:stretch;flex-direction:column}.permission-search{width:100%}.permission-filters{flex-wrap:wrap}}
</style>
