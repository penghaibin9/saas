<template>
  <ModulePageShell
    title="产品身份与权限"
    subtitle="统一发布模块、权限、导航与学校角色模板真值；招聘季仍属于岗位实习，不新增第二套顶层模块"
    role-name="平台负责人 / 安全审计"
    data-scope-name="平台控制面"
  >
    <div class="iam-page">
      <section class="hero card">
        <div>
          <p class="eyebrow">全局标准 · 产品身份与权限</p>
          <h3>控制“发布哪一版真值”，不在页面里另造权限目录</h3>
          <p class="muted">源数据来自代码审查后的模块清单、权限目录与已发布角色模板。发布前强制执行影响分析、版本锁定和近期登录复核及二次认证。</p>
        </div>
        <AppButton :loading="loading" @click="load">刷新真值</AppButton>
      </section>

      <div v-if="error" class="error card">{{ error }}</div>

      <template v-else>
        <section class="metrics">
          <article class="card"><strong>{{ modules.length }}</strong><span>顶层模块</span></article>
          <article class="card"><strong>{{ permissions.length }}</strong><span>权威权限</span></article>
          <article class="card"><strong>{{ templates.length }}</strong><span>已发布角色模板</span></article>
          <article class="card"><strong>{{ releases.length }}</strong><span>身份与权限版本</span></article>
        </section>

        <section class="guard card" :class="internshipHealthy ? 'is-ok' : 'is-bad'">
          <strong>{{ internshipHealthy ? '岗位实习模块边界正常' : '岗位实习模块边界异常，禁止发布' }}</strong>
          <span>要求：岗位实习顶层模块恰好 1 个；招聘季、企业门户、学生选岗只能作为子页面或功能。</span>
        </section>

        <section class="card">
          <header class="section-head">
            <div><h3>代码真值</h3><p class="muted">部署提交：{{ source.provenance?.deployedCommitSha || '当前环境未提供' }} · 导航摘要：{{ source.navigationDigest || '—' }} · 源数据摘要：{{ source.sourceDigest || '—' }}</p></div>
            <div class="tabs">
              <button :class="{ active: tab === 'modules' }" @click="tab = 'modules'">模块 / 导航</button>
              <button :class="{ active: tab === 'permissions' }" @click="tab = 'permissions'">权限目录</button>
              <button :class="{ active: tab === 'templates' }" @click="tab = 'templates'">角色模板</button>
            </div>
          </header>

          <div v-if="tab === 'modules'" class="table-wrap">
            <table>
              <thead><tr><th>模块编码</th><th>名称</th><th>学校可见</th><th>平台专用</th><th>前端入口</th></tr></thead>
              <tbody>
                <tr v-for="item in modules" :key="item.moduleKey">
                  <td class="mono">{{ item.moduleKey }}</td>
                  <td>{{ item.moduleName || item.name || item.label || '—' }}</td>
                  <td>{{ item.schoolVisible ? '是' : '否' }}</td>
                  <td>{{ item.platformOnly ? '是' : '否' }}</td>
                  <td class="muted">{{ routePrefixes(item.moduleKey) }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-else-if="tab === 'permissions'">
            <div class="toolbar">
              <input v-model.trim="permissionKeyword" placeholder="搜索权限编码、模块或功能" />
              <select v-model="permissionPlane"><option value="">全部所属端</option><option value="TENANT">学校端</option><option value="PLATFORM">平台端</option></select>
            </div>
            <div class="table-wrap">
              <table>
                <thead><tr><th>权限编码</th><th>所属端</th><th>模块 / 功能</th><th>风险</th><th>学校可分配</th></tr></thead>
                <tbody>
                  <tr v-for="item in filteredPermissions" :key="item.permissionCode">
                    <td class="mono">{{ item.permissionCode }}</td><td>{{ platformEnumLabel(item.plane, '所属端待确认') }}</td>
                    <td>{{ item.moduleKey }} / {{ item.featureKey || '—' }}</td><td>{{ platformEnumLabel(item.riskLevel, '风险等级待确认') }}</td>
                    <td>{{ item.tenantAssignable ? '是' : '否' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div v-else class="table-wrap">
            <table>
              <thead><tr><th>模板</th><th>版本</th><th>权限</th><th>生产菜单</th><th>权限摘要</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="item in templates" :key="`${item.templateCode}-${item.templateVersion}`">
                  <td class="mono">{{ item.templateCode }}</td><td>第 {{ item.templateVersion }} 版</td><td>{{ item.permissionCount }}</td><td>{{ item.menuCount }}</td><td class="mono muted">{{ item.permissionDigest || '—' }}</td><td><button class="link" @click="selectedTemplate = item">权限 / 菜单预览</button></td>
                </tr>
                <tr v-if="!templates.length"><td colspan="6" class="muted">暂无已发布学校角色模板</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="selectedTemplate" class="card">
          <header class="section-head"><div><h3>{{ selectedTemplate.templateCode }} · 第 {{ selectedTemplate.templateVersion }} 版</h3><p class="muted">菜单由权限集合自动投影，不存在第二套菜单访问控制表。</p></div><div><button class="link" @click="startTemplateDraft(selectedTemplate)">创建新版本草稿</button><button class="link" @click="selectedTemplate = null">关闭</button></div></header>
          <div class="preview-grid">
            <div><strong>权限配置</strong><code v-for="code in selectedTemplate.permissionCodes || []" :key="code">{{ code }}</code></div>
            <div><strong>生产菜单预览</strong><span v-for="item in selectedTemplate.menuPreview || []" :key="item.surfaceKey">{{ item.label }}<small>{{ item.path }}</small></span></div>
          </div>
        </section>

        <section v-if="templateDraft" class="card template-editor">
          <header class="section-head"><div><h3>学校标准角色模板草稿 · {{ templateDraft.templateCode }}</h3><p class="muted">只能从已启用的学校端权限目录中选择；版本发布后不可修改。</p></div><button class="link" @click="templateDraft = null">关闭</button></header>
          <div class="toolbar"><input v-model.trim="templateKeyword" placeholder="搜索权限编码、模块或功能" /><span>已选 {{ templateDraft.permissionCodes.length }} 项</span></div>
          <div class="permission-picker">
            <label v-for="item in templatePermissionOptions" :key="item.permissionCode"><input v-model="templateDraft.permissionCodes" type="checkbox" :value="item.permissionCode" /><span>{{ item.label || item.permissionCode }}<code>{{ item.permissionCode }}</code></span></label>
          </div>
          <label class="editor-reason">变更 / 发布原因<textarea v-model.trim="templateDraft.reason" rows="3" minlength="5" placeholder="至少 5 个字符" /></label>
          <div v-if="templateDraft.impact" class="impact-grid"><div><strong>新增权限</strong><p>{{ join(templateDraft.impact.addedPermissions) }}</p></div><div><strong>移除权限</strong><p>{{ join(templateDraft.impact.removedPermissions) }}</p></div><div><strong>新增菜单</strong><p>{{ join(templateDraft.impact.menuAdded) }}</p></div><div><strong>移除菜单</strong><p>{{ join(templateDraft.impact.menuRemoved) }}</p></div></div>
          <div class="actions"><AppButton variant="primary" :loading="saving === 'template'" @click="saveTemplateDraft">{{ templateDraft.id ? '保存草稿' : '创建草稿' }}</AppButton><AppButton v-if="templateDraft.id" :loading="saving === 'template-impact'" @click="loadTemplateDraftImpact">影响分析</AppButton><AppButton v-if="templateDraft.id && templateDraft.impact" variant="danger" :loading="saving === 'template-publish'" @click="publishTemplateDraft">二次认证后发布</AppButton></div>
        </section>

        <section class="card">
          <header class="section-head"><div><h3>创建发布草稿</h3><p class="muted">草稿会锁定当前源数据摘要；源真值变化后旧草稿将自动拒绝发布。</p></div></header>
          <form class="release-form" @submit.prevent="createRelease">
            <label>部署提交（服务端真值）<input :value="source.provenance?.deployedCommitSha || '当前环境未提供'" readonly /></label>
            <label>发布原因<input v-model.trim="draft.reason" required minlength="5" placeholder="说明本次模块/权限/模板变更目的" /></label>
            <AppButton variant="primary" type="submit" :loading="saving === 'create'">创建草稿</AppButton>
          </form>
        </section>

        <section class="card">
          <header class="section-head"><div><h3>发布版本与影响分析</h3><p class="muted">发布必须使用该草稿的当前版本号；已发布版本不可再次修改。</p></div></header>
          <div class="table-wrap">
            <table>
              <thead><tr><th>版本</th><th>状态</th><th>来源提交摘要</th><th>原因</th><th>操作</th></tr></thead>
              <tbody>
                <tr v-for="item in releases" :key="item.id">
                  <td><span class="mono">{{ item.id }}</span><small>第 {{ item.version }} 版</small></td>
                  <td><span class="badge" :class="item.status === 'PUBLISHED' ? 'published' : 'draft'">{{ platformStatusLabel(item.status) }}</span></td>
                  <td class="mono muted">{{ item.sourceCommitSha || '—' }}</td><td>{{ item.reason || '—' }}</td>
                  <td class="actions">
                    <button class="link" @click="loadImpact(item)">影响</button>
                    <button v-if="item.status === 'DRAFT'" class="link danger" :disabled="saving === item.id" @click="publish(item)">发布</button>
                  </td>
                </tr>
                <tr v-if="!releases.length"><td colspan="5" class="muted">还没有身份与权限发布版本</td></tr>
              </tbody>
            </table>
          </div>
        </section>

        <section v-if="impact" class="card impact">
          <header class="section-head"><h3>影响分析 · {{ impact.releaseId }}</h3><button class="link" @click="impact = null">关闭</button></header>
          <div class="impact-grid">
            <div><strong>新增模块</strong><p>{{ join(impact.addedModules) }}</p></div><div><strong>移除模块</strong><p>{{ join(impact.removedModules) }}</p></div>
            <div><strong>新增权限</strong><p>{{ join(impact.addedPermissions) }}</p></div><div><strong>移除权限</strong><p>{{ join(impact.removedPermissions) }}</p></div>
            <div><strong>模板变化</strong><p>{{ join(impact.changedRoleTemplates) }}</p></div><div><strong>岗位实习顶层模块数</strong><p>{{ impact.internshipModuleCount }}</p></div>
          </div>
          <p v-if="impact.secondRecruitmentModule" class="error-inline">检测到第二套招聘顶层模块，发布将被拒绝。</p>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { ModulePageShell } from '@/components/business'
import { productIamApi } from '@/modules/platform/api/productIam.api'
import { platformEnumLabel, platformStatusLabel } from '@/modules/platform/constants/platform-display.constants'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformProductIamView',
  components: { AppButton, ModulePageShell },
  data: () => ({ source: {}, releases: [], error: '', loading: false, saving: '', tab: 'modules', permissionKeyword: '', permissionPlane: '', impact: null, selectedTemplate: null, templateDraft: null, templateKeyword: '', draft: { reason: '' } }),
  computed: {
    modules() { return this.source.modules || [] },
    permissions() { return this.source.permissions || [] },
    templates() { return this.source.roleTemplates || [] },
    templatePermissionOptions() {
      const q = this.templateKeyword.toLowerCase()
      return this.permissions.filter((item) => item.plane === 'TENANT' && item.lifecycle === 'ACTIVE' && item.tenantAssignable && item.customRoleAssignable && !String(item.permissionCode).startsWith('system.') && (!q || [item.permissionCode, item.moduleKey, item.featureKey, item.label].some((value) => String(value || '').toLowerCase().includes(q))))
    },
    internshipHealthy() {
      const internship = this.modules.filter((item) => item.moduleKey === 'internship')
      const forbidden = this.modules.some((item) => ['recruitment', 'recruitmentcenter', 'enterpriserecruitment'].includes(String(item.moduleKey || '').toLowerCase()))
      return internship.length === 1 && !forbidden
    },
    filteredPermissions() {
      const q = this.permissionKeyword.toLowerCase()
      return this.permissions.filter((item) => {
        if (this.permissionPlane && item.plane !== this.permissionPlane) return false
        if (!q) return true
        return [item.permissionCode, item.moduleKey, item.featureKey, item.label].some((value) => String(value || '').toLowerCase().includes(q))
      })
    }
  },
  created() { this.load() },
  methods: {
    platformEnumLabel,
    platformStatusLabel,
    join(items) { return (items || []).length ? items.join('、') : '无' },
    routePrefixes(moduleKey) {
      const row = (this.source.navigation || []).find((item) => item.moduleKey === moduleKey)
      return (row?.frontendRoutePrefixes || []).join('、') || '—'
    },
    startTemplateDraft(item) {
      this.templateDraft = { templateCode: item.templateCode, templateName: item.templateCode, permissionCodes: [...(item.permissionCodes || [])], reason: '', id: '', version: 0, permissionDigest: '', impact: null }
      this.templateKeyword = ''
    },
    async saveTemplateDraft() {
      if (this.templateDraft.reason.length < 5) return toast.error('模板变更原因至少 5 个字符')
      this.saving = 'template'
      const body = { permissionCodes: this.templateDraft.permissionCodes, reason: this.templateDraft.reason, expectedVersion: this.templateDraft.version, templateName: this.templateDraft.templateName }
      const res = this.templateDraft.id ? await productIamApi.updateTemplateDraft(this.templateDraft.templateCode, this.templateDraft.id, body) : await productIamApi.createTemplateDraft(this.templateDraft.templateCode, body)
      this.saving = ''
      if (res.code !== 0) return toast.error(res.message)
      this.templateDraft = { ...this.templateDraft, ...res.data, permissionCodes: res.data.permissions || res.data.permissionCodes || [], impact: null }
      toast.success('角色模板草稿已保存')
    },
    async loadTemplateDraftImpact() {
      this.saving = 'template-impact'
      const res = await productIamApi.templateImpact(this.templateDraft.templateCode, this.templateDraft.id)
      this.saving = ''
      if (res.code !== 0) return toast.error(res.message)
      this.templateDraft.impact = res.data
    },
    async publishTemplateDraft() {
      if (!this.templateDraft.impact) return toast.error('请先刷新影响分析')
      this.saving = 'template-publish'
      const res = await productIamApi.publishTemplate(this.templateDraft.templateCode, this.templateDraft.id, { expectedVersion: this.templateDraft.version, reason: this.templateDraft.reason, permissionDigest: this.templateDraft.permissionDigest, sourceDigest: this.templateDraft.impact.sourceDigest, navigationDigest: this.templateDraft.impact.navigationDigest })
      this.saving = ''
      if (res.code !== 0) return toast.error(res.message)
      toast.success('标准角色模板已发布；SYSTEM Role runtime 将读取新版本')
      this.templateDraft = null; await this.load()
    },
    async load() {
      this.loading = true; this.error = ''
      const [source, releases] = await Promise.all([productIamApi.source(), productIamApi.releases()])
      this.loading = false
      const failed = [source, releases].find((item) => item.code !== 0)
      if (failed) { this.error = failed.message; return }
      this.source = source.data || {}
      this.releases = releases.data?.items || []
    },
    async createRelease() {
      this.saving = 'create'
      const requestId = globalThis.crypto?.randomUUID?.() || `product-iam-${Date.now()}-${Math.random().toString(16).slice(2)}`
      const res = await productIamApi.createRelease({ ...this.draft, requestId })
      this.saving = ''
      if (res.code !== 0) return toast.error(res.message)
      toast.success('产品身份与权限草稿已冻结当前代码真值')
      this.draft = { reason: '' }
      await this.load()
    },
    async loadImpact(item) {
      const res = await productIamApi.impact(item.id)
      if (res.code !== 0) return toast.error(res.message)
      this.impact = res.data
    },
    async publish(item) {
      await this.loadImpact(item)
      if (!this.impact || this.impact.secondRecruitmentModule || this.impact.internshipModuleCount !== 1) return toast.error('模块边界异常，禁止发布')
      this.saving = item.id
      const res = await productIamApi.publish(item.id, item.version)
      this.saving = ''
      if (res.code !== 0) return toast.error(res.message)
      toast.success('产品身份与权限已发布')
      await this.load()
    }
  }
}
</script>

<style scoped>
.iam-page{display:grid;gap:16px}.card{background:var(--surface,#fff);border:1px solid var(--card-b,#e5e6eb);border-radius:12px;padding:18px}.hero,.section-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.eyebrow{margin:0 0 6px;font-size:12px;font-weight:700;letter-spacing:.08em;color:var(--primary,#2563eb)}h3{margin:0 0 6px}.muted{color:var(--text-secondary,#646a73)}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.metrics article{display:grid;gap:4px}.metrics strong{font-size:26px}.guard{display:grid;gap:4px;border-left:4px solid #16a34a}.guard.is-bad{border-left-color:#dc2626}.tabs{display:flex;gap:6px;flex-wrap:wrap}.tabs button,.link{border:0;background:transparent;cursor:pointer}.tabs button{padding:7px 10px;border-radius:7px}.tabs button.active{background:#eef4ff;color:#1d4ed8}.toolbar,.release-form{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}.toolbar input,.toolbar select,.release-form input{height:36px;border:1px solid var(--card-b,#e5e6eb);border-radius:8px;padding:0 10px}.release-form label{display:grid;gap:5px;min-width:240px;flex:1;font-size:13px}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;min-width:760px}th,td{padding:10px;border-bottom:1px solid var(--card-b,#e5e6eb);text-align:left;vertical-align:top}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}td small{display:block;color:#8a8f98}.badge{padding:3px 7px;border-radius:999px;font-size:12px}.badge.published{background:#ecfdf3;color:#067647}.badge.draft{background:#fff7ed;color:#c2410c}.actions{white-space:nowrap}.link{color:#2563eb;padding:4px 6px}.link.danger{color:#b42318}.impact-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}.impact-grid div{padding:12px;border-radius:8px;background:#f7f8fa}.impact-grid p{margin:5px 0 0;overflow-wrap:anywhere}.error,.error-inline{color:#b42318}.error{background:#fff2f0}
.preview-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:14px}.preview-grid>div{display:flex;flex-direction:column;gap:7px;padding:12px;border:1px solid var(--card-b,#e5e6eb);border-radius:9px;max-height:420px;overflow:auto}.preview-grid code,.preview-grid span{padding:7px;border-radius:6px;background:#f7f8fa;overflow-wrap:anywhere}.preview-grid small{display:block;color:#8a8f98;margin-top:3px}@media(max-width:800px){.preview-grid{grid-template-columns:1fr}}
.template-editor{display:grid;gap:14px}.permission-picker{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:7px;max-height:480px;overflow:auto;padding:10px;border:1px solid var(--card-b,#e5e6eb);border-radius:9px}.permission-picker label{display:flex;gap:8px;align-items:flex-start;padding:8px;background:#f7f8fa;border-radius:7px}.permission-picker code{display:block;font-size:11px;color:#646a73;overflow-wrap:anywhere}.editor-reason{display:grid;gap:6px}.editor-reason textarea{border:1px solid var(--card-b,#e5e6eb);border-radius:8px;padding:9px}.template-editor>.actions{display:flex;gap:8px;flex-wrap:wrap}
</style>
