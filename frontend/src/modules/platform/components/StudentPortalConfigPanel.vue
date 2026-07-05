<template>
  <div class="spcfg">
    <div class="spcfg__tid">
      <label class="spcfg__field">
        <span>真实租户ID（写入真实后端；平台租户列表若为 mock 数据，请在此填入该学校的真实 DB 租户 ID，切勿用 mock ID 写库）</span>
        <span class="spcfg__tidrow">
          <input v-model.trim="realTenantId" class="spcfg__input" placeholder="如 1000000000000000003" />
          <button class="spcfg__btn" @click="load">加载该租户配置</button>
        </span>
      </label>
    </div>

    <div class="spcfg__main">
      <label class="spcfg__switch">
        <input v-model="form.enabled" type="checkbox" /> 启用学生 PC 门户
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
          <input v-model="form.modules[m]" type="checkbox" /> {{ moduleLabels[m] || m }}
        </label>
      </div>
    </div>

    <div class="spcfg__block">
      <div class="spcfg__bt">功能开关（关闭后即使前端隐藏，后端也会返回 403）</div>
      <div class="spcfg__switches">
        <label v-for="f in featureKeys" :key="f" class="spcfg__chk">
          <input v-model="form.features[f]" type="checkbox" /> {{ featureLabels[f] || f }}
        </label>
      </div>
    </div>

    <details class="spcfg__preview">
      <summary>预览最终配置（提交后由后端按「默认 &lt; 套餐 &lt; 租户 &lt; 总开关」合并）</summary>
      <pre>{{ previewText }}</pre>
    </details>

    <div class="spcfg__ops">
      <button class="spcfg__btn spcfg__btn--primary" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存配置' }}</button>
      <button class="spcfg__btn" @click="restore">恢复默认</button>
      <button class="spcfg__btn" @click="previewPortal">预览学生门户</button>
      <button class="spcfg__btn" @click="copyUrl">复制门户地址</button>
    </div>
    <div class="spcfg__msg" :class="msgClass">{{ msg }}</div>
  </div>
</template>

<script>
import { studentPortalConfigApi } from '@/modules/platform/api/studentPortalConfig.api'

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
        messageReceipt: '消息回执', materialCenter: '材料中心', workItems: '自助办理', aiAssistant: 'AI 助手'
      },
      packages: [
        { code: 'trial', name: '试用版' }, { code: 'standard', name: '标准版' },
        { code: 'professional', name: '专业版' }, { code: 'private', name: '私有部署' }
      ],
      form: makeDefaults(),
      realTenantId: String(this.tenantId || ''),
      saving: false,
      msg: '',
      msgClass: ''
    }
  },
  computed: {
    effectiveTenantId() {
      return this.realTenantId || this.tenantId
    },
    pkgName() {
      return (this.packages.find((p) => p.code === this.form.requiredPackage) || {}).name || ''
    },
    previewText() {
      return JSON.stringify(this.form, null, 2)
    }
  },
  watch: {
    tenantId(v) { this.realTenantId = String(v || ''); this.load() }
  },
  created() { this.load() },
  methods: {
    async load() {
      if (!this.effectiveTenantId) { this.form = makeDefaults(); return }
      try {
        const cfg = await studentPortalConfigApi.get(this.effectiveTenantId)
        const d = makeDefaults()
        this.form = {
          enabled: !!cfg.enabled,
          portalName: cfg.portalName || d.portalName,
          portalUrl: cfg.portalUrl || d.portalUrl,
          requiredPackage: (cfg.package && cfg.package.code) || d.requiredPackage,
          modules: { ...d.modules, ...(cfg.modules || {}) },
          features: { ...d.features, ...(cfg.features || {}) }
        }
      } catch (e) {
        this.form = makeDefaults()
        this.setMsg('读取配置失败，已载入默认值：' + (e.message || ''), 'warn')
      }
    },
    async save() {
      if (!this.effectiveTenantId) { this.setMsg('请先填写真实租户ID', 'err'); return }
      this.saving = true
      this.msg = ''
      try {
        await studentPortalConfigApi.save(this.effectiveTenantId, this.form)
        this.setMsg('保存成功（后端已写审计 TENANT_STUDENT_PORTAL_CONFIG）', 'ok')
      } catch (e) {
        this.setMsg('保存失败：' + (e.message || '请检查权限或网络'), 'err')
      } finally {
        this.saving = false
      }
    },
    restore() {
      this.form = makeDefaults()
      this.setMsg('已恢复默认（未保存，点击「保存配置」后生效）', 'warn')
    },
    previewPortal() {
      window.open(this.form.portalUrl || '/portal/', '_blank')
    },
    async copyUrl() {
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
.spcfg__preview pre { background: #0d1117; color: #c9d1d9; padding: 12px; border-radius: 8px; overflow: auto; max-height: 220px; font-size: 12px; }
.spcfg__ops { display: flex; gap: 10px; flex-wrap: wrap; }
.spcfg__btn { height: 34px; padding: 0 14px; border: 1px solid #dcdfe6; background: #fff; border-radius: 6px; cursor: pointer; }
.spcfg__btn--primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.spcfg__msg { margin-top: 10px; font-size: 13px; min-height: 18px; }
.spcfg__msg--ok { color: #00b42a; }
.spcfg__msg--warn { color: #ff7d00; }
.spcfg__msg--err { color: #f53f3f; }
</style>
