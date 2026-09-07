<template>
  <section class="trw" aria-labelledby="rules-workspace-title">
    <header class="trw__header">
      <div><h3 id="rules-workspace-title">学校规则变更</h3><p>{{ tenant.tenantName }} · {{ tenant.tenantCode }} <span v-if="base">· 覆盖版本 {{ base.overrideVersion }}</span></p></div>
      <span class="trw__badge">{{ phaseLabel }}</span>
    </header>
    <p v-if="!mayWrite()" class="trw__notice">当前身份只读；规则写入仍由后端平台超级管理员权限控制。</p>
    <p v-if="error" class="trw__error" role="alert">{{ error }}</p>
    <template v-if="base">
      <template v-if="phase === 'edit'">
        <div class="trw__toolbar">
          <label class="trw__search"><span>查找规则</span><input v-model="search" type="search" placeholder="输入业务名称或规则名称" /></label>
          <span role="status" aria-live="polite">已修改 {{ delta.changes.length }} 项<span v-if="Object.keys(delta.errors).length"> · {{ Object.keys(delta.errors).length }} 项输入待修正</span></span>
        </div>
        <div class="trw__layout">
          <nav class="trw__groups" aria-label="规则业务分组"><button v-for="group in groupKeys" :key="group" type="button" :aria-pressed="selectedGroup === group" @click="selectedGroup = group; search = ''">{{ groupLabel(group) }}<span>{{ Object.keys(base.rules[group]).length }}</span></button></nav>
          <div class="trw__fields">
            <p v-if="!visibleFields.length" class="trw__notice">{{ search ? '没有匹配的规则，请调整搜索词。' : '当前分组没有规则项。' }}</p>
            <div v-for="field in visibleFields" :key="field.path" class="trw__field" :class="{ 'is-changed': isChanged(field.path) }">
              <div><label :for="field.path">{{ fieldLabel(field.key) }}</label><small>{{ groupLabel(field.group) }} · {{ hasOverride(field) ? '学校覆盖' : '继承默认' }}<span v-if="isChanged(field.path)"> · 本次修改</span></small></div>
              <div class="trw__value">
                <label v-if="field.kind === 'boolean'" class="trw__boolean"><input :id="field.path" v-model="draft[field.group][field.key]" type="checkbox" :disabled="!mayWrite()" /><span>{{ draft[field.group][field.key] ? '开启' : '关闭' }}</span></label>
                <input v-else-if="field.kind === 'integer'" :id="field.path" v-model="draft[field.group][field.key]" type="number" min="0" max="1000000" step="1" :disabled="!mayWrite()" :aria-invalid="Boolean(delta.errors[field.path])" :aria-describedby="delta.errors[field.path] ? field.path + '-error' : undefined" />
                <textarea v-else-if="field.kind === 'list'" :id="field.path" v-model="draft[field.group][field.key]" rows="2" :disabled="!mayWrite()" placeholder="每行一项，也可用逗号分隔" />
                <input v-else-if="field.kind === 'text'" :id="field.path" v-model="draft[field.group][field.key]" type="text" :disabled="!mayWrite()" />
                <span v-else :id="field.path" class="trw__readonly">{{ ruleValueLabel(field.original) }}</span>
                <small v-if="delta.errors[field.path]" :id="field.path + '-error'" class="trw__error">{{ delta.errors[field.path] }}</small>
              </div>
            </div>
          </div>
        </div>
        <div v-if="mayWrite()" class="trw__edit-footer">
          <label for="rules-change-reason">变更原因 <small>5–500 个字符</small><textarea id="rules-change-reason" v-model="reason" rows="2" maxlength="500" placeholder="说明本次为什么修改，保存时一并提交审计原因" /></label>
          <div class="trw__actions"><button type="button" class="trw__primary" :disabled="!delta.changes.length || Object.keys(delta.errors).length > 0" @click="review">核对 {{ delta.changes.length }} 项修改</button><button v-if="protectNavigation" type="button" @click="discardAsked = true">放弃本页修改</button></div>
          <div v-if="discardAsked" class="trw__notice" role="alert">只放弃本页草稿，不修改服务器配置。<button type="button" @click="resetDraft">确认放弃</button><button type="button" @click="discardAsked = false">继续编辑</button></div>
        </div>
      </template>
      <template v-else>
        <div v-if="prepared" class="trw__review">
          <h4>{{ phase === 'review' ? '核对本次规则修改' : '本次提交记录' }}</h4>
          <p>{{ tenant.tenantName }} · 学校编码 {{ tenant.tenantCode }} · 基于版本 {{ prepared.expectedVersion }}</p>
          <p>原因：{{ prepared.reason }}</p>
          <p class="trw__notice">只提交下列变化；其余规则保留原来的继承或覆盖关系。这是提交内容核对，不是后端影响预演。</p>
          <div class="trw__table"><table><caption class="trw__sr-only">本次规则变更前后对照</caption><thead><tr><th scope="col">规则</th><th scope="col">修改前</th><th scope="col">本次修改</th><th v-if="latest" scope="col">重新读取的值</th></tr></thead><tbody><tr v-for="item in readbackRows" :key="item.group + '.' + item.key"><th scope="row">{{ fieldLabel(item.key) }}<small>{{ groupLabel(item.group) }}</small></th><td>{{ ruleValueLabel(item.before) }}</td><td>{{ ruleValueLabel(item.after) }}</td><td v-if="latest">{{ ruleValueLabel(item.current) }}<small>{{ item.matches ? '与本次内容一致' : '与本次内容不同' }}</small></td></tr></tbody></table></div>
        </div>
        <div v-if="phase === 'review'" class="trw__actions"><button type="button" class="trw__primary" :disabled="!mayWrite() || busy" @click="submit">确认保存规则</button><button type="button" :disabled="busy" @click="phase = 'edit'; prepared = null">返回修改</button></div>
        <p v-if="busy" class="trw__notice" role="status">{{ phase === 'saving' ? '正在提交规则，请勿重复操作…' : '正在重新读取当前配置…' }}</p>
        <div v-if="phase === 'saved'" class="trw__success" role="status"><strong>规则保存成功，服务器回执已核对</strong><p>覆盖版本 {{ base.overrideVersion }} · 共 {{ prepared.changes.length }} 项。此回执不代表已经验证所有业务端的运行效果。</p><button type="button" @click="beginNext">完成本次变更</button></div>
        <div v-if="phase === 'conflict' || phase === 'uncertain'" class="trw__notice" role="alert">
          <strong>{{ phase === 'conflict' ? '版本冲突，已停止提交' : '保存结果尚未确认，请勿重复提交' }}</strong>
          <p>{{ phase === 'conflict' ? '保留了本页修改记录。先读取当前版本，再决定是否重新编辑；不会自动合并或覆盖。' : '请求可能已在服务器生效。下面只能重新读取，不能重放本次写入；读到相同值也不代表取得了本次审计回执。' }}</p>
          <p v-if="latest">已重新读取覆盖版本 {{ latest.overrideVersion }}，请对照上表核验。</p>
          <div class="trw__actions"><button type="button" :disabled="busy" @click="inspectCurrent">{{ busy ? '正在读取…' : '重新读取当前配置（不写入）' }}</button><button v-if="phase === 'conflict' && latest" type="button" :disabled="busy || !mayWrite()" @click="acceptLatest">放弃旧草稿，按当前版本重新编辑</button></div>
        </div>
      </template>
    </template>
  </section>
</template>

<script>
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { platformControlHardeningApi } from '@/modules/platform/api/platformControlHardening.api'
import { isPlatformRoot } from '@/security/platformAccessGate'
import { getPermissionPatterns, getRbacLoadFailed } from '@/security/permissionGate'
import { PLATFORM_RULE_GROUP_LABELS, PLATFORM_RULE_LABELS } from '@/modules/platform/constants/platform-display.constants'
import { rulesSnapshot, editableDraft, ruleKind, ruleChanges, prepareRules, verifiedRulesReceipt, compareRuleReadback, ruleValueLabel } from '@/modules/platform/utils/tenantRuleDraft.mjs'

export default {
  name: 'TenantRulesWorkspace',
  props: { tenant: { type: Object, required: true }, projection: { type: Object, required: true } },
  emits: ['activity'],
  data() { return { base: null, draft: {}, reason: '', search: '', selectedGroup: '', phase: 'edit', prepared: null, latest: null, busy: false, error: '', requestEpoch: 0, discardAsked: false } },
  computed: {
    groupKeys() { return Object.keys(this.base?.rules || {}) },
    delta() { return this.base ? ruleChanges(this.base.rules, this.draft) : { changes: [], patch: {}, errors: {} } },
    protectNavigation() { return this.busy || ['review', 'conflict', 'uncertain'].includes(this.phase) || (this.phase === 'edit' && (this.delta.changes.length > 0 || Object.keys(this.delta.errors).length > 0 || Boolean(this.reason.trim()))) },
    activity() { return { protected: this.protectNavigation, busy: this.busy, phase: this.phase } },
    phaseLabel() { return ({ edit: '编辑草稿', review: '待核对', saving: '正在保存', saved: '已保存', conflict: '版本冲突', uncertain: '待核验' })[this.phase] || '待核验' },
    visibleFields() {
      if (!this.base) return []
      const keyword = this.search.trim().toLocaleLowerCase()
      return this.groupKeys.flatMap(group => Object.entries(this.base.rules[group]).map(([key, original]) => ({ group, key, path: `${group}.${key}`, original, kind: ruleKind(original) })))
        .filter(field => keyword ? `${this.groupLabel(field.group)} ${this.fieldLabel(field.key)} ${field.path}`.toLocaleLowerCase().includes(keyword) : field.group === this.selectedGroup)
    },
    readbackRows() { return !this.prepared ? [] : this.latest ? compareRuleReadback(this.prepared, this.latest) : this.prepared.changes }
  },
  watch: {
    activity: { immediate: true, handler(value) { this.$emit('activity', value) } },
    'tenant.tenantId'() { this.initialize() },
    projection(value, old) { if (value !== old) this.initialize() }
  },
  created() { this.initialize() },
  mounted() { window.addEventListener('beforeunload', this.beforeUnload) },
  beforeUnmount() { this.requestEpoch += 1; window.removeEventListener('beforeunload', this.beforeUnload); this.prepared = null; this.draft = {}; this.reason = ''; this.latest = null },
  methods: {
    ruleValueLabel,
    mayWrite() { return isPlatformRoot() && Array.isArray(getPermissionPatterns()) && !getRbacLoadFailed() },
    groupLabel(group) { return PLATFORM_RULE_GROUP_LABELS[group] || '其他规则' },
    fieldLabel(key) { return PLATFORM_RULE_LABELS[key] || '待命名规则项' },
    hasOverride(field) { return Object.hasOwn(this.base.override[field.group] || {}, field.key) },
    isChanged(path) { return this.delta.changes.some(item => `${item.group}.${item.key}` === path) },
    beforeUnload(event) { if (this.protectNavigation) { event.preventDefault(); event.returnValue = '' } },
    initialize() {
      this.requestEpoch += 1; this.base = null; this.draft = {}; this.prepared = null; this.latest = null; this.busy = false; this.error = ''; this.reason = ''; this.phase = 'edit'; this.discardAsked = false
      try { this.base = rulesSnapshot(this.projection, this.tenant.tenantId); this.resetDraft() }
      catch (error) { this.error = error.message }
    },
    resetDraft() {
      if (this.busy || !this.base) return
      this.draft = editableDraft(this.base.rules); this.reason = ''; this.prepared = null; this.latest = null; this.error = ''; this.phase = 'edit'; this.discardAsked = false
      this.selectedGroup = this.groupKeys.includes(this.selectedGroup) ? this.selectedGroup : this.groupKeys[0] || ''
    },
    review() {
      if (this.busy || this.phase !== 'edit' || !this.base || !this.mayWrite()) return
      this.error = ''
      try { this.prepared = prepareRules(this.base, this.draft, this.reason); this.phase = 'review' }
      catch (error) { this.error = error.message }
    },
    isCurrent(epoch, tenantId) { return epoch === this.requestEpoch && tenantId === this.tenant.tenantId },
    async submit() {
      if (this.busy || this.phase !== 'review' || !this.prepared || !this.mayWrite()) return
      const request = this.prepared
      try {
        if (JSON.stringify(prepareRules(this.base, this.draft, this.reason)) !== JSON.stringify(request)) throw new Error('内容或版本已变化，请重新核对')
      } catch (error) { this.phase = 'edit'; this.prepared = null; this.error = error.message; return }
      const epoch = ++this.requestEpoch
      this.busy = true; this.phase = 'saving'; this.error = ''; this.latest = null
      try {
        const res = await platformControlHardeningApi.putRules(request.tenantId, request.rules, request.expectedVersion, request.reason)
        if (!this.isCurrent(epoch, request.tenantId)) return
        if (res?.code !== 0) {
          this.phase = res?.bizCode === 'DATA_CONFLICT' || res?.code === 409 ? 'conflict' : 'uncertain'
          this.error = res?.message || '未取得保存结果'; return
        }
        this.base = verifiedRulesReceipt(res.data, request)
        this.draft = editableDraft(this.base.rules); this.phase = 'saved'; this.reason = ''
      } catch (error) {
        if (this.isCurrent(epoch, request.tenantId)) { this.phase = 'uncertain'; this.error = error?.message || '请求中断，请先核对当前配置' }
      } finally { if (this.isCurrent(epoch, request.tenantId)) this.busy = false }
    },
    async inspectCurrent() {
      if (this.busy || !['conflict', 'uncertain'].includes(this.phase) || !this.prepared) return
      const tenantId = this.tenant.tenantId, epoch = ++this.requestEpoch
      this.busy = true; this.error = ''; this.latest = null
      try {
        const res = await platformControlApi.getRules(tenantId)
        if (!this.isCurrent(epoch, tenantId)) return
        if (res?.code !== 0) throw new Error(res?.message || '当前配置读取失败')
        const snapshot = rulesSnapshot(res.data, tenantId)
        if (snapshot.overrideVersion < this.prepared.expectedVersion) throw new Error('读取版本早于提交基线，不能据此继续办理')
        this.latest = snapshot
      } catch (error) { if (this.isCurrent(epoch, tenantId)) this.error = error?.message || '当前配置读取失败' }
      finally { if (this.isCurrent(epoch, tenantId)) this.busy = false }
    },
    acceptLatest() { if (!this.busy && this.phase === 'conflict' && this.latest && this.mayWrite()) { this.base = this.latest; this.resetDraft() } },
    beginNext() { if (!this.busy && this.phase === 'saved') this.resetDraft() }
  }
}
</script>

<style scoped>
.trw{border:1px solid var(--card-b,#e5eaf2);border-radius:12px;background:var(--bg-card,#fff);padding:20px;color:var(--t1,#1c2844);min-width:0}.trw h3,.trw h4{margin:0;font-size:16px}.trw h4{font-size:15px}.trw p{margin:8px 0;font-size:13px;line-height:1.65;color:var(--text-secondary,#63748b)}.trw__header,.trw__toolbar,.trw__actions{display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}.trw__header{align-items:flex-start}.trw__badge{border-radius:6px;padding:5px 10px;background:var(--pri-bg,#edf1ff);color:var(--pri,#3c5cdb);font-size:12px}.trw__toolbar{margin:18px 0;font-size:13px;color:var(--text-secondary,#63748b)}.trw__search{display:flex;align-items:center;gap:10px;max-width:100%}.trw__search input{width:280px;max-width:100%}.trw__layout{display:grid;grid-template-columns:175px minmax(0,1fr);gap:24px}.trw__groups{display:flex;flex-direction:column;gap:6px;align-self:start}.trw__groups button{display:flex;justify-content:space-between;text-align:left;gap:8px;border:0;background:transparent}.trw__groups button[aria-pressed=true]{background:var(--pri-bg,#edf1ff);color:var(--pri,#3c5cdb)}.trw__groups span{font-size:12px}.trw__field{display:grid;grid-template-columns:minmax(0,1fr) minmax(160px,42%);align-items:center;gap:14px;padding:13px 12px;border-bottom:1px solid var(--card-b,#edf0f6)}.trw__field.is-changed{background:var(--pri-bg,#f2f5ff);border-radius:8px}.trw__field label{font-size:13px;line-height:1.6}.trw small{display:block;margin-top:5px;font-size:12px;line-height:1.5;color:var(--text-secondary,#63748b)}.trw input:not([type=checkbox]),.trw textarea{box-sizing:border-box;width:100%;padding:9px 10px;border:1px solid var(--card-b,#dce3ee);border-radius:7px;background:var(--bg-input,#fff);color:var(--t1,#1c2844);font:inherit;font-size:13px}.trw textarea{resize:vertical;line-height:1.6}.trw__boolean{display:flex;align-items:center;gap:9px}.trw__boolean input{width:17px;height:17px;accent-color:var(--pri,#3c5cdb)}.trw__edit-footer{margin-top:20px;padding-top:18px;border-top:1px solid var(--card-b,#e5eaf2)}.trw__edit-footer>label{display:block;max-width:780px;font-size:13px}.trw__edit-footer small{display:inline;margin-left:8px}.trw__edit-footer textarea{display:block;margin-top:8px}.trw__actions{justify-content:flex-start;margin-top:16px}.trw button{border:1px solid var(--card-b,#dce3ee);border-radius:8px;padding:9px 13px;color:var(--t1,#1c2844);background:var(--bg-card,#fff);font:inherit;font-size:13px;cursor:pointer}.trw .trw__primary{background:var(--pri,#3c5cdb);color:white;border-color:transparent}.trw :disabled{opacity:.55;cursor:not-allowed}.trw :is(button,input,textarea):focus-visible{outline:2px solid var(--pri,#3c5cdb);outline-offset:3px}.trw__notice,.trw__success{border-radius:8px;background:var(--pri-bg,#f2f5ff);padding:13px 15px;margin-top:14px;line-height:1.7;font-size:13px}.trw__notice button,.trw__success button{margin:8px 8px 0 0}.trw__success{border-left:3px solid var(--success-600,#157b61)}.trw__error{color:var(--danger-600,#b42318)!important}.trw__readonly{font-size:12px;color:var(--text-secondary,#63748b)}.trw__review{margin-top:20px}.trw__table{max-width:100%;overflow:auto;margin-top:16px}.trw table{width:100%;border-collapse:collapse;font-size:13px;text-align:left}.trw td,.trw th{padding:12px;border-bottom:1px solid var(--card-b,#e5eaf2);max-width:280px;overflow-wrap:anywhere;vertical-align:top}.trw thead{background:var(--pri-bg,#f5f7fb);color:var(--text-secondary,#63748b)}.trw tbody th{font-weight:500}.trw__sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}@media(max-width:850px){.trw__layout{grid-template-columns:1fr;gap:12px}.trw__groups{flex-direction:row;flex-wrap:wrap}.trw__groups button{gap:8px}.trw__field{grid-template-columns:1fr}.trw__search{width:100%}.trw__search input{flex:1;min-width:0}.trw{padding:14px}}
</style>
