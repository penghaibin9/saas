<template>
  <div class="spcfg">
    <div class="spcfg__tid">
      <strong>{{ effectiveTenantId ? '正在配置当前所选学校' : '请先从租户列表选择学校' }}</strong>
      <p class="spcfg__muted">{{ effectiveTenantId ? '配置将应用于租户上下文中的学校。' : '未选择学校时不可保存，避免配置写入错误范围。' }}</p>
    </div>

    <p v-if="loading" role="status">正在读取学校门户配置…</p>
    <div v-else-if="loadError" role="alert" class="spcfg__msg--err">
      <p>{{ loadError }}；未载入可保存的默认值。</p>
      <button type="button" class="spcfg__btn" :disabled="saving" @click="load">重新读取配置</button>
    </div>
    <div v-if="uncertain" role="alert" class="spcfg__msg--warn">
      <p>保存结果尚未确认，请勿重复提交。重新读取只查询，不重放保存。</p>
      <button type="button" class="spcfg__btn" :disabled="loading || saving" @click="load">只读取当前配置</button>
      <button v-if="inspected && ready" type="button" class="spcfg__btn" :disabled="loading || saving" @click="finishVerification">已核对，结束本次记录</button>
    </div>
    <fieldset v-if="ready && form" class="spcfg__fields" :disabled="saving || uncertain">
    <div class="spcfg__main">
      <label class="spcfg__switch">
        <input v-model="form.enabled" type="checkbox" /> 启用学生电脑门户
      </label>
      <span class="spcfg__muted">当前套餐：{{ pkgName }}（超出套餐上限的功能，学生端最终一律关闭）</span>
    </div>

    <div class="spcfg__grid">
      <label class="spcfg__field"><span>门户名称</span><input v-model="form.portalName" class="spcfg__input" /></label>
      <label class="spcfg__field"><span>访问地址</span><input v-model="form.portalUrl" class="spcfg__input" placeholder="/portal/" /></label>
      <label class="spcfg__field"><span>套餐</span>
        <select v-model="form.requiredPackage" class="spcfg__input">
          <option v-for="p in packages" :key="p.code" :value="p.code">{{ p.name }}</option>
        </select>
      </label>
    </div>

    <div class="spcfg__block">
      <div class="spcfg__bt">模块开关</div>
      <div class="spcfg__switches">
        <label v-for="m in moduleKeys" :key="m" class="spcfg__chk">
          <input v-model="form.modules[m]" type="checkbox" /> {{ moduleLabel(m) }}
        </label>
      </div>
    </div>

    <div class="spcfg__block">
      <div class="spcfg__bt">功能开关（关闭后该功能不可访问）</div>
      <div class="spcfg__switches">
        <label v-for="f in featureKeys" :key="f" class="spcfg__chk">
          <input v-model="form.features[f]" type="checkbox" /> {{ featureLabel(f) }}
        </label>
      </div>
    </div>

    <details class="spcfg__preview">
      <summary>最终配置预览（当前草稿，保存后以服务器返回为准）</summary>
      <dl class="spcfg__summary">
        <div><dt>门户状态</dt><dd>{{ form.enabled ? '已启用' : '已关闭' }}</dd></div>
        <div><dt>门户名称</dt><dd>{{ form.portalName || '未设置' }}</dd></div>
        <div><dt>访问地址</dt><dd>{{ form.portalUrl || '未设置' }}</dd></div>
        <div><dt>当前套餐</dt><dd>{{ pkgName || '套餐待确认' }}</dd></div>
        <div><dt>已启用模块</dt><dd>{{ enabledModuleLabels }}</dd></div>
        <div><dt>已启用功能</dt><dd>{{ enabledFeatureLabels }}</dd></div>
      </dl>
    </details>

    <div class="spcfg__ops">
      <button type="button" class="spcfg__btn spcfg__btn--primary" :disabled="!canSave" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button>
      <button type="button" class="spcfg__btn" @click="restore">恢复默认</button>
      <button type="button" class="spcfg__btn" @click="previewPortal">预览学生门户</button>
      <button type="button" class="spcfg__btn" @click="copyUrl">复制门户地址</button>
    </div>
    </fieldset>
    <div role="status" aria-live="polite" class="spcfg__msg" :class="msgClass">{{ msg }}</div>
  </div>
</template>

<script>
import { studentPortalConfigApi } from '@/modules/platform/api/studentPortalConfig.api'
import { normalizeUiError, safeEnumLabel } from '@/utils/presentationSafety'

const MODULE_KEYS = ['dashboard', 'profile', 'orientation', 'campusService', 'academic', 'internship', 'graduation', 'employment', 'messages']
const FEATURE_KEYS = ['upload', 'export', 'proofDownload', 'profileCorrection', 'messageReceipt', 'materialCenter', 'workItems', 'aiAssistant']

function makeDefaults() {
  return {
    enabled: true,
    portalName: '学生服务门户',
    portalUrl: '/portal/',
    requiredPackage: 'standard',
    modules: Object.fromEntries(MODULE_KEYS.map((k) => [k, true])),
    features: Object.fromEntries(FEATURE_KEYS.map((k) => [k, k !== 'aiAssistant']))
  }
}

export default {
  name: 'StudentPortalConfigPanel',
  props: { tenantId: { type: [String, Number], default: '' } },
  data() {
    return {
      moduleKeys: MODULE_KEYS,
      featureKeys: FEATURE_KEYS,
      moduleLabels: {
        dashboard: '首页概览', profile: '我的档案', orientation: '迎新报到', campusService: '在校服务',
        academic: '学业过程', internship: '岗位实习', graduation: '毕业设计', employment: '就业服务', messages: '消息中心'
      },
      featureLabels: {
        upload: '大文件上传', export: '导出', proofDownload: '证明下载', profileCorrection: '信息更正',
        messageReceipt: '消息回执', materialCenter: '材料中心', workItems: '自助办理', aiAssistant: '智能助手'
      },
      packages: [
        { code: 'trial', name: '试用版' }, { code: 'standard', name: '标准版' },
        { code: 'professional', name: '专业版' }, { code: 'private', name: '私有部署' }
      ],
      form: null, baseline: null, ready: false, loading: true, loadError: '', epoch: 0,
      uncertain: false, inspected: false,
      saving: false,
      msg: '',
      msgClass: ''
    }
  },
  computed: {
    effectiveTenantId() {
      return typeof this.tenantId === 'string' && /^[1-9]\d*$/.test(this.tenantId) ? this.tenantId : Number.isSafeInteger(this.tenantId) && this.tenantId > 0 ? String(this.tenantId) : ''
    },
    dirty() { return this.ready && JSON.stringify(this.form) !== JSON.stringify(this.baseline) },
    busy() { return this.loading || this.saving },
    canSave() { return this.ready && this.effectiveTenantId && !this.busy && !this.uncertain && this.dirty },
    protectNavigation() { return this.saving || this.dirty || this.uncertain },
    pkgName() {
      return (this.packages.find((p) => p.code === this.form?.requiredPackage) || {}).name || ''
    },
    enabledModuleLabels() {
      const labels = this.moduleKeys.filter((key) => this.form?.modules[key]).map(this.moduleLabel)
      return labels.join('、') || '未启用'
    },
    enabledFeatureLabels() {
      const labels = this.featureKeys.filter((key) => this.form?.features[key]).map(this.featureLabel)
      return labels.join('、') || '未启用'
    }
  },
  watch: {
    tenantId() { this.epoch++; this.saving = false; this.uncertain = false; this.inspected = false; this.load() }
  },
  created() { this.load() },
  mounted() { window.addEventListener('beforeunload', this.beforeUnload) },
  beforeUnmount() { this.epoch++; window.removeEventListener('beforeunload', this.beforeUnload) },
  methods: {
    moduleLabel(key) { return safeEnumLabel({ value: key, dictionary: this.moduleLabels, unknownLabel: '未识别模块（请联系平台管理员）' }) },
    featureLabel(key) { return safeEnumLabel({ value: key, dictionary: this.featureLabels, unknownLabel: '未识别功能（请联系平台管理员）' }) },
    current(epoch, id) { return epoch === this.epoch && id === this.effectiveTenantId },
    beforeUnload(event) { if (this.protectNavigation) { event.preventDefault(); event.returnValue = '' } },
    acceptedConfig(cfg) {
      if (!cfg || typeof cfg.enabled !== 'boolean' || typeof cfg.portalName !== 'string' || typeof cfg.portalUrl !== 'string' || !this.packages.some(p => p.code === cfg.package?.code)) throw new Error('门户配置结构不完整')
      for (const [name, keys] of [['modules', MODULE_KEYS], ['features', FEATURE_KEYS]]) {
        if (!cfg[name] || Array.isArray(cfg[name]) || keys.some(key => typeof cfg[name][key] !== 'boolean')) throw new Error('门户开关数据未完整取得')
      }
      return { enabled: cfg.enabled, portalName: cfg.portalName, portalUrl: cfg.portalUrl, requiredPackage: cfg.package.code,
        modules: Object.fromEntries(MODULE_KEYS.map(key => [key, cfg.modules[key]])), features: Object.fromEntries(FEATURE_KEYS.map(key => [key, cfg.features[key]])) }
    },
    async load() {
      if (this.saving) return
      const id = this.effectiveTenantId, epoch = ++this.epoch
      this.ready = false; this.loading = true; this.loadError = ''; this.msg = ''; this.form = null; this.baseline = null; this.inspected = false
      try {
        if (!id) throw new Error('请先选择有效学校')
        const cfg = await studentPortalConfigApi.get(id)
        if (!this.current(epoch, id)) return
        this.form = this.acceptedConfig(cfg); this.baseline = JSON.parse(JSON.stringify(this.form)); this.ready = true
        if (this.uncertain) { this.inspected = true; this.setMsg('已读取当前配置；这不是上次保存的执行回执，请核对后再继续。', 'warn') }
      } catch (e) {
        if (this.current(epoch, id)) this.loadError = normalizeUiError(e, { fallback: '读取配置失败，请重试' }).userMessage
      } finally { if (this.current(epoch, id)) this.loading = false }
    },
    async save() {
      if (!this.canSave) return
      const id = this.effectiveTenantId, epoch = ++this.epoch
      const body = JSON.parse(JSON.stringify(this.form))
      this.saving = true; this.msg = ''; this.inspected = false
      try {
        const cfg = await studentPortalConfigApi.save(id, body)
        if (!this.current(epoch, id)) return
        this.form = this.acceptedConfig(cfg); this.baseline = JSON.parse(JSON.stringify(this.form))
        this.setMsg('配置保存响应已核对，当前显示服务器返回值；未单独验证审计与所有业务端的生效结果。', 'ok')
      } catch (e) {
        if (this.current(epoch, id)) { this.uncertain = true; this.setMsg(normalizeUiError(e, { fallback: '保存结果未确认，请先读取核对' }).userMessage, 'err') }
      } finally { if (this.current(epoch, id)) this.saving = false }
    },
    restore() {
      if (!this.ready || this.busy || this.uncertain) return
      this.form = makeDefaults()
      this.setMsg('已恢复默认（未保存，点击「保存配置」后生效）', 'warn')
    },
    finishVerification() { if (this.inspected && this.ready && !this.busy) { this.uncertain = false; this.inspected = false } },
    previewPortal() {
      if (!this.ready) return
      try {
        const address = this.form.portalUrl
        if (typeof address !== 'string' || /[\u0000-\u0020\\]/.test(address)) throw new Error('门户地址无效')
        const target = new URL(address, window.location.origin)
        if (!['https:', 'http:'].includes(target.protocol) || target.username || target.password || address.startsWith('//')) throw new Error('门户地址必须是站内路径或 HTTP(S) 地址')
        window.open(target.href, '_blank', 'noopener,noreferrer')
      } catch (e) { this.setMsg(e.message, 'err') }
    },
    async copyUrl() {
      if (!this.ready) return
      try {
        await navigator.clipboard.writeText(this.form.portalUrl || '/portal/')
        this.setMsg('门户地址已复制', 'ok')
      } catch {
        this.setMsg('复制失败，请手动复制：' + (this.form.portalUrl || '/portal/'), 'warn')
      }
    },
    setMsg(m, t) {
      this.msg = m
      this.msgClass = 'spcfg__msg--' + t
    }
  }
}
</script>

<style scoped>
.spcfg__fields { border: 0; padding: 0; margin: 0; min-width: 0; }
.spcfg :disabled { cursor: not-allowed; }
.spcfg__tid { margin-bottom: 14px; }
.spcfg__tidrow { display: flex; gap: 10px; align-items: center; }
.spcfg__tidrow .spcfg__input { flex: 1; }
.spcfg__main { display: flex; align-items: center; gap: 16px; margin-bottom: 14px; flex-wrap: wrap; }
.spcfg__switch { font-weight: 600; }
.spcfg__muted { color: #86909c; font-size: 12px; }
.spcfg__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 16px; }
.spcfg__field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.spcfg__input { height: 34px; border: 1px solid #dcdfe6; border-radius: 6px; padding: 0 10px; }
.spcfg__block { margin-bottom: 16px; }
.spcfg__bt { font-weight: 600; margin-bottom: 10px; font-size: 14px; }
.spcfg__switches { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
.spcfg__chk { font-size: 13px; }
.spcfg__preview { margin: 8px 0 16px; }
.spcfg__summary { display: grid; gap: 8px; margin: 10px 0 0; padding: 12px; border-radius: 8px; background: #f7f8fa; font-size: 12px; }
.spcfg__summary div { display: grid; grid-template-columns: 90px 1fr; gap: 12px; }
.spcfg__summary dt { color: #86909c; }
.spcfg__summary dd { margin: 0; color: #1d2129; }
.spcfg__ops { display: flex; gap: 10px; flex-wrap: wrap; }
.spcfg__btn { height: 34px; padding: 0 14px; border: 1px solid #dcdfe6; background: #fff; border-radius: 6px; cursor: pointer; }
.spcfg__btn--primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.spcfg__msg { margin-top: 10px; font-size: 13px; min-height: 18px; }
.spcfg__msg--ok { color: #00b42a; }
.spcfg__msg--warn { color: #ff7d00; }
.spcfg__msg--err { color: #f53f3f; }
</style>
