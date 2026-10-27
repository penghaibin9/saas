<template>
  <ModulePageShell title="学校表单配置与版本" subtitle="明确选择目标学校后维护配置；此处不代办学生业务，也不读取业务表单提交内容。" :role-name="canManage ? '已授权表单维护' : '表单只读'" data-scope-name="当前所选学校的表单配置">
    <section class="mp-card bf-selector">
      <label>搜索学校<input v-model.trim="keyword" class="mp-input" :disabled="busy" placeholder="学校名称或编码" @keyup.enter="searchSchools" /></label>
      <button class="mp-btn" :disabled="busy || searching" @click="searchSchools">{{ searching ? '查询中…' : '查询学校' }}</button>
      <label>目标学校<select v-model="tenantId" class="mp-input" :disabled="busy" @change="loadDefinitions"><option value="">请选择学校</option><option v-for="school in schools" :key="school.tenantId" :value="school.tenantId">{{ school.tenantName }} · {{ school.tenantCode }}</option></select></label>
      <p v-if="hasMore" class="mp-note">当前仅列出前30所匹配学校，请缩小查询范围。</p>
      <p v-if="schoolError" role="alert">{{ schoolError }}</p>
    </section>
    <ErrorState v-if="error" :description="error" @retry="loadDefinitions" />
    <LoadingState v-else-if="loading" />
    <EmptyState v-else-if="!tenantId" title="先选择目标学校" description="不会默认使用最近访问的学校。" />
    <template v-else>
      <p role="status">当前学校：{{ tenantName }}。{{ canManage ? '发布或停用前需要核对版本、影响和原因。' : '当前身份仅可查看、预览和校验，不能发布或停用。' }}</p>
      <section class="mp-card bf-pad"><h2>来源合规能力目录</h2><p>这里核对平台已登记的来源能力，不读取学生业务事实，也不生成当前学校“合规通过”的结论。具体评估仍由所属业务模块按原权限执行。</p><div v-if="sourcesError" role="alert">{{ sourcesError }}<button class="mp-btn" @click="loadSources">重新读取目录</button></div><p v-else-if="sourcesLoading">正在读取来源能力…</p><table v-else class="mp-audit"><thead><tr><th>业务域</th><th>已登记能力</th><th>技术来源</th></tr></thead><tbody><tr v-for="source in sources" :key="source.providerCode"><td>{{ source.domainName }}</td><td>{{ sourceModeLabel(source) }}</td><td><details><summary>实施人员使用</summary><p>来源标识：{{ source.providerCode }}</p><p>规则来源：{{ source.ruleSource }}</p></details></td></tr></tbody></table></section>
      <div class="bf-layout">
        <section class="mp-card bf-definitions"><h2>表单定义</h2><button v-for="item in definitions" :key="item.id" :disabled="busy" class="mp-btn" @click="selectDefinition(item)">{{ item.formName }}</button><p v-if="!definitions.length">本次读取成功，未返回表单定义。</p></section>
        <div class="bf-workspace">
          <BusinessFormVersionWorkbench v-if="selected" :form-code="selected.formCode" :versions="versions" :can-manage="canManage" :busy="busy" @preview="preview" @validate="validateVersion" @impact="showImpact" @publish="prepare('publish', $event)" @disable="prepare('disable', $event)" />
          <div v-if="selected" class="bf-pagination"><span>共 {{ versionTotal }} 个历史版本 · 第 {{ versionPage }} 页</span><button class="mp-btn" :disabled="busy || versionPage <= 1" @click="selectDefinition(selected, versionPage - 1)">上一页</button><button class="mp-btn" :disabled="busy || versionPage * 50 >= versionTotal" @click="selectDefinition(selected, versionPage + 1)">下一页</button></div>
          <p v-else>选择一个表单定义查看版本。</p>
          <p v-if="receipt" role="status">{{ receipt }}</p>
          <section v-if="impact" class="mp-card bf-pad"><h3>版本影响</h3><p>新增字段 {{ impact.addedFields?.length || 0 }} 项，移除字段 {{ impact.removedFields?.length || 0 }} 项；{{ impact.adapterChanged ? '业务适配器有变化' : '业务适配器未变化' }}。</p><details><summary>实施人员使用：完整影响明细</summary><pre>{{ JSON.stringify(impact, null, 2) }}</pre></details></section>
          <section v-if="previewVersion" class="mp-card bf-pad"><h3>只读结构预览</h3><p>预览不提交业务，不代替学校角色的实际办理。</p><fieldset disabled><SchemaBusinessForm :form-version="previewVersion" :model-value="{}" :client-type="previewClient" /></fieldset></section>
        </div>
      </div>
    </template>
    <WorkspaceConfirmDialog :visible="!!pending" :title="pending?.action === 'publish' ? '发布表单配置版本' : '停用表单配置版本'" require-reason reason-label="变更原因（不少于5个字）" :submitting="busy" :confirm-disabled="uncertain || !canManage || (!!pending?.dynamicPolicyCount && !policyAcknowledged)" @update:visible="closePending" @confirm="submit">
      <template v-if="pending"><p>学校：{{ pending.tenantName }}；表单：{{ pending.formName }}；第 {{ pending.versionNo }} 版。</p><p>仅变更此学校的配置版本；学校业务提交仍由原业务接口验证权限和状态。</p><label v-if="pending.dynamicPolicyCount"><input v-model="policyAcknowledged" type="checkbox" :disabled="busy" />已核对 {{ pending.dynamicPolicyCount }} 项动态生效策略引用</label><p v-if="writeError" role="alert">{{ writeError }}</p><button v-if="uncertain" class="mp-btn" :disabled="busy" @click="reconcile">重新读取核对结果</button></template>
    </WorkspaceConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { matchPermission } from '@/config/navPlan'
import { businessFormsControlApi as api } from '../../api/businessFormsControl.api'
import BusinessFormVersionWorkbench from '../../businessForms/components/BusinessFormVersionWorkbench.vue'
import SchemaBusinessForm from '../../businessForms/components/SchemaBusinessForm.vue'
import WorkspaceConfirmDialog from '@/modules/system/components/workspace/WorkspaceConfirmDialog.vue'
import { contextFingerprint } from '@/modules/system/utils/workspaceContract'
import { normalizeUiError } from '@/utils/presentationSafety'

export default {
  name: 'PlatformBusinessFormsView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, BusinessFormVersionWorkbench, SchemaBusinessForm, WorkspaceConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() { return { keyword: '', schools: [], searching: false, schoolError: '', hasMore: false, tenantId: '', tenantName: '', definitions: [], selected: null, versions: [], versionPage: 1, versionTotal: 0, previewVersion: null, impact: null, loading: false, busy: false, error: '', receipt: '', sequence: 0, searchSequence: 0, sources: [], sourcesError: '', sourcesLoading: false, sourceSequence: 0, pending: null, policyAcknowledged: false, uncertain: false, writeError: '' } },
  computed: {
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'platform.businessForms.manage') },
    contextKey() { return contextFingerprint(this.ctx) },
    previewClient() { const clients = this.previewVersion?.supported_clients || []; return clients.includes('STAFF_PC') ? 'STAFF_PC' : clients[0] || 'STAFF_PC' }
  },
  created() { this.searchSchools() },
  watch: { contextKey() { this.sequence++; this.searchSequence++; this.busy = false; this.pending = null; this.uncertain = false; this.tenantId = ''; this.schools = []; this.loadDefinitions(); this.searchSchools() } },
  beforeUnmount() { this.sequence++; this.searchSequence++; this.sourceSequence++ },
  beforeRouteLeave() { return !this.busy && !this.pending },
  methods: {
    readError(error, fallback) { return normalizeUiError(error, { fallback }).userMessage },
    sourceModeLabel(item) { if (!item.registered) return '来源尚未注册'; return ({ NATIVE_ENGINE: '来源域原生规则引擎', MATERIAL_POLICY: '来源域材料规则', EVIDENCE_ONLY: '仅有证据能力，不能判定合规通过' })[item.mode] || '能力说明待核对' },
    async loadSources() {
      const tid = this.tenantId, seq = ++this.sourceSequence
      if (!tid) return
      this.sourcesLoading = true; this.sourcesError = ''
      try { const data = await api.sources(tid); if (seq !== this.sourceSequence || tid !== this.tenantId) return; if (String(data.tenantId) !== tid || !Array.isArray(data.items)) throw Error('来源目录返回不完整'); this.sources = data.items }
      catch (e) { if (seq === this.sourceSequence) this.sourcesError = this.readError(e, '来源目录读取失败') }
      finally { if (seq === this.sourceSequence) this.sourcesLoading = false }
    },
    async searchSchools() {
      if (this.busy) return
      const seq = ++this.searchSequence; this.searching = true; this.schoolError = ''
      try { const data = await api.schools(this.keyword); if (seq !== this.searchSequence) return; if (!Array.isArray(data.items)) throw Error('学校列表返回不完整'); this.schools = data.items; this.hasMore = data.hasMore === true; this.tenantId = ''; await this.loadDefinitions() }
      catch (e) { if (seq === this.searchSequence) this.schoolError = this.readError(e, '学校查询失败') }
      finally { if (seq === this.searchSequence) this.searching = false }
    },
    async loadDefinitions() {
      if (this.busy || this.uncertain) return
      const seq = ++this.sequence, tid = this.tenantId
      this.definitions = []; this.selected = null; this.versions = []; this.versionPage = 1; this.versionTotal = 0; this.previewVersion = null; this.impact = null; this.error = ''; this.receipt = ''; this.tenantName = ''; this.loading = false; this.sourceSequence++; this.sources = []; this.sourcesError = ''; this.sourcesLoading = false
      if (!tid) return
      this.loading = true
      try { const data = await api.definitions(tid); if (seq !== this.sequence) return; if (String(data.tenantId) !== tid || !Array.isArray(data.items)) throw Error('学校上下文返回不一致，请重新选择'); this.tenantName = data.tenantName; this.definitions = data.items; this.loadSources() }
      catch (e) { if (seq === this.sequence) this.error = this.readError(e, '表单定义读取失败') }
      finally { if (seq === this.sequence) this.loading = false }
    },
    async selectDefinition(item, page = 1) {
      if (this.busy || this.uncertain) return
      const seq = ++this.sequence; this.selected = item; this.versions = []; this.previewVersion = null; this.impact = null; this.receipt = ''; this.loading = true; this.error = ''
      try { const data = await api.versions(this.tenantId, item.id, page); if (seq !== this.sequence) return; if (!Array.isArray(data.items)) throw Error('版本列表返回不完整'); this.versions = data.items; this.versionPage = data.page; this.versionTotal = data.total }
      catch (e) { if (seq === this.sequence) this.error = this.readError(e, '表单版本读取失败') }
      finally { if (seq === this.sequence) this.loading = false }
    },
    async readVersion(item, action) {
      if (this.busy) return null
      const seq = ++this.sequence, tid = this.tenantId; this.error = ''; this.busy = true
      try { const result = await api[action](tid, item.versionId); return seq === this.sequence && tid === this.tenantId ? result : null }
      catch (e) { if (seq === this.sequence) this.error = this.readError(e, '版本读取失败'); return null }
      finally { if (seq === this.sequence) this.busy = false }
    },
    async preview(item) { const data = await this.readVersion(item, 'preview'); if (data) this.previewVersion = data.formVersion },
    async validateVersion(item) { if (await this.readVersion(item, 'validate')) this.receipt = '该版本结构校验通过，不代表业务已提交。' },
    async showImpact(item) { const data = await this.readVersion(item, 'impact'); if (data) this.impact = data },
    async prepare(action, item) {
      if (!this.canManage || this.busy || this.uncertain || !Number.isInteger(item.version)) return
      const analysis = await this.readVersion(item, 'impact'); if (!analysis || !this.canManage) return
      this.impact = analysis; this.policyAcknowledged = false; this.writeError = ''
      this.pending = { action, tenantId: this.tenantId, tenantName: this.tenantName, formName: this.selected.formName, definition: this.selected, versionId: item.versionId, version: item.version, versionNo: item.versionNo, dynamicPolicyCount: action === 'publish' ? (analysis.resolveActivePolicyRefs || []).length : 0 }
    },
    closePending(visible) { if (!visible && !this.busy && !this.uncertain) this.pending = null },
    async submit({ reason }) {
      const pending = this.pending
      if (!pending || this.busy || this.uncertain || !this.canManage || pending.tenantId !== this.tenantId || (pending.dynamicPolicyCount && !this.policyAcknowledged)) return
      if (String(reason || '').trim().length < 5) { this.writeError = '变更原因不少于5个字'; return }
      const seq = this.sequence
      this.busy = true; this.writeError = ''
      try { await api[pending.action](pending.tenantId, pending.versionId, { expectedVersion: pending.version, reason: reason.trim(), resolveActiveImpactAck: pending.dynamicPolicyCount ? this.policyAcknowledged : false }); if (seq !== this.sequence || pending.tenantId !== this.tenantId) return; this.pending = null; this.busy = false; await this.selectDefinition(pending.definition); if (this.sequence !== seq + 1) return; this.receipt = pending.action === 'publish' ? '版本已发布，已重新读取当前学校的版本状态。' : '版本已停用，已重新读取当前学校的版本状态。' }
      catch (e) { if (seq === this.sequence) { this.uncertain = true; this.writeError = (this.readError(e, '操作结果未确认')) + '；保留本次对象，先重新读取核对，不自动重发。' } }
      finally { if (seq === this.sequence) this.busy = false }
    },
    async reconcile() {
      if (!this.pending || this.busy) return
      const pending = this.pending, seq = this.sequence; this.busy = true
      try { const current = await api.preview(pending.tenantId, pending.versionId); if (seq !== this.sequence || pending.tenantId !== this.tenantId) return; this.pending = null; this.uncertain = false; this.busy = false; await this.selectDefinition(pending.definition); if (this.sequence !== seq + 1) return; this.receipt = `已回读第${current.versionNo}版，请核对版本列表后决定后续操作。` }
      catch (e) { if (seq === this.sequence) this.writeError = this.readError(e, '仍无法取得结果，请稍后重试') }
      finally { if (seq === this.sequence) this.busy = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.bf-selector { padding:16px; display:flex; flex-wrap:wrap; gap:12px; align-items:end; }
.bf-selector label { display:grid; gap:6px; min-width:200px; }.bf-layout { display:grid; grid-template-columns:240px minmax(0,1fr); gap:16px; }
.bf-selector input,.bf-selector select { width:100%; min-width:0; padding:10px 12px; border:1px solid #d0d5dd; border-radius:8px; background:#fff; font:inherit; }
.bf-definitions,.bf-pad { padding:16px; }.bf-definitions { display:grid; gap:10px; align-content:start; }.bf-workspace { min-width:0; display:grid; gap:16px; overflow:auto; }
.bf-pagination { display:flex; flex-wrap:wrap; gap:12px; align-items:center; }
fieldset { border:0; padding:0; min-width:0; }pre { white-space:pre-wrap; overflow-wrap:anywhere; }h2,h3 { margin:0 0 12px; }
@media(max-width:900px){.bf-layout{grid-template-columns:1fr}.bf-selector label{min-width:0;width:100%}}
</style>
