<template>
  <section class="tlw" aria-labelledby="tenant-lifecycle-title">
    <header class="tlw__header"><div><h3 id="tenant-lifecycle-title">生命周期与环境维护</h3><p>先核对学校与影响，再确认执行。续费与套餐变更请通过合同订单办理。</p></div><span class="tlw__version">当前版本 {{ version === null ? '未取得' : version }}</span></header>
    <p v-if="!choices.length" class="tlw__muted">当前职责没有可办理的变更操作。</p>
    <template v-else>
      <div class="tlw__choices" aria-label="选择办理事项"><button v-for="item in choices" :key="item.key" type="button" :aria-pressed="action === item.key" :disabled="locked" @click="choose(item.key)">{{ item.label }}</button></div>
      <form v-if="action" class="tlw__form" @submit.prevent="prepare">
        <div class="tlw__context"><strong>{{ tenant.tenantName }}</strong><span>{{ tenant.tenantCode }} · {{ statusLabel(tenant.status) }}</span></div>
        <div class="tlw__steps" aria-label="办理进度"><span :class="{ 'is-current': phase === 'edit' }">1 填写原因</span><span :class="{ 'is-current': phase === 'preview' }">2 核对影响</span><span :class="{ 'is-current': receipt || phase === 'uncertain' }">3 执行回执</span></div>
        <label v-if="action === 'extend-trial'">延长试用<select v-model="days" :disabled="locked" @change="invalidatePreview"><option :value="7">7 天</option><option :value="30">30 天</option></select></label>
        <label>变更原因 <span class="tlw__muted">（至少 5 个字符）</span><textarea v-model="reason" rows="3" minlength="5" maxlength="500" :disabled="locked" @input="invalidatePreview" placeholder="填写本次办理原因，便于后续追溯" /></label>
        <p v-if="maintenance" class="tlw__warning">环境恢复会清理现场新增数据。该既有维护接口不提供后端影响预览或版本锁；下方只核对学校身份，不代表可撤销。</p>
        <p v-if="error" class="tlw__error" role="alert">{{ error }}</p>
        <div v-if="phase === 'edit'" class="tlw__actions"><button type="submit" class="tlw__primary" :disabled="busy || version === null">{{ busy ? '正在核对…' : maintenance ? '核对维护对象' : '查看变更影响' }}</button><button type="button" :disabled="busy" @click="cancel">取消</button></div>
        <section v-if="phase === 'preview' && preview" class="tlw__preview" aria-label="变更影响确认">
          <h4>{{ maintenance ? '环境维护确认' : '后端变更预览' }}</h4>
          <p>{{ selectedLabel }} · {{ tenant.tenantName }} · 校验版本 {{ preparedBody.expectedVersion }}</p>
          <p v-if="!maintenance"><strong>{{ statusLabel(preview.fromStatus) }}</strong> → <strong>{{ statusLabel(preview.toStatus) }}</strong></p>
          <ul v-if="preview.warnings?.length"><li v-for="(warning, index) in preview.warnings" :key="index">{{ warning }}</li></ul>
          <label>输入学校编码 <strong>{{ tenant.tenantCode }}</strong> 确认对象<input v-model="confirmation" :disabled="busy" autocomplete="off" spellcheck="false" /></label>
          <div class="tlw__actions"><button type="button" class="tlw__danger" :disabled="busy || confirmation !== tenant.tenantCode" @click="execute">{{ busy ? '正在执行…' : `确认${selectedLabel}` }}</button><button type="button" :disabled="busy" @click="invalidatePreview">返回修改</button></div>
        </section>
        <section v-if="receipt" class="tlw__receipt" role="status" aria-live="polite">
          <h4>{{ maintenance ? '维护接口已返回成功' : receipt.cacheRecoveryRequired ? '业务已生效，权限缓存待恢复' : '变更已生效' }}</h4>
          <p v-if="!maintenance">业务版本 {{ receipt.version }} · {{ receipt.cacheInvalidated ? '缓存刷新完成' : '请勿重新执行业务变更' }}</p>
          <p v-if="receipt.warning">{{ receipt.warning }}</p>
          <div class="tlw__actions"><button v-if="receipt.cacheRecoveryRequired && can('platform.operations.manage')" type="button" class="tlw__primary" :disabled="busy" @click="recover">{{ busy ? '正在恢复…' : '仅恢复权限缓存' }}</button><span v-else-if="receipt.cacheRecoveryRequired" class="tlw__muted">请由具备运维权限的人员恢复缓存，不要重做业务操作。</span><button v-if="!receipt.cacheRecoveryRequired" type="button" :disabled="busy" @click="$emit('changed')">完成并刷新学校状态</button></div>
        </section>
        <section v-if="phase === 'uncertain'" class="tlw__warning" role="alert"><strong>尚未取得可信执行回执</strong><p>变更可能已经提交。请先刷新学校状态并核对审计，不要重复点击执行。</p><button type="button" @click="$emit('changed')">重新读取学校状态</button></section>
      </form>
    </template>
  </section>
</template>

<script>
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { platformControlHardeningApi } from '@/modules/platform/api/platformControlHardening.api'
import { canEnterRoute, getPermissionPatterns, getRbacLoadFailed } from '@/security/permissionGate'
import { isPlatformRoot } from '@/security/platformAccessGate'
import { wholeNumber, statusLabel } from '@/modules/platform/utils/tenantWorkspace.mjs'

const ACTIONS = { enable: '启用学校', disable: '停用学校', 'extend-trial': '延长试用', expire: '标记到期', 'reset-demo-data': '恢复样例学校数据', 'reset-sandbox-data': '恢复沙箱数据' }
export default {
  name: 'TenantLifecycleWorkspace',
  props: { tenant: { type: Object, required: true }, tenant360: { type: Object, default: () => ({}) } },
  emits: ['changed'],
  data() { return { action: '', reason: '', days: 7, confirmation: '', phase: 'edit', busy: false, preview: null, preparedBody: null, error: '', receipt: null, requestEpoch: 0, attempted: false } },
  computed: {
    version() { return wholeNumber(this.tenant360.version ?? this.tenant.version) },
    maintenance() { return this.action === 'reset-demo-data' || this.action === 'reset-sandbox-data' },
    selectedLabel() { return ACTIONS[this.action] || '' },
    locked() { return this.busy || this.attempted },
    choices() {
      const keys = []
      if (this.can('platform.commercial.manage') && ['active', 'trial', 'expired', 'disabled'].includes(this.tenant.status)) {
        keys.push(this.tenant.status === 'disabled' ? 'enable' : 'disable')
        if (this.tenant.status === 'trial') keys.push('extend-trial')
        if (['active', 'trial'].includes(this.tenant.status)) keys.push('expire')
      }
      if (this.rootMaintenanceAllowed()) {
        if (this.tenant.tenantCode === 'demo-school') keys.push('reset-demo-data')
        if (this.tenant.tenantCode === 'sandbox-school') keys.push('reset-sandbox-data')
      }
      return keys.map(key => ({ key, label: ACTIONS[key] }))
    }
  },
  watch: { 'tenant.tenantId'() { this.cancel(true) }, 'tenant.version'() { if (!this.locked) this.invalidatePreview() }, 'tenant360.version'() { if (!this.locked) this.invalidatePreview() } },
  beforeUnmount() { this.requestEpoch += 1 },
  methods: {
    statusLabel,
    can(key) { return Array.isArray(getPermissionPatterns()) && !getRbacLoadFailed() && canEnterRoute({ moduleCode: 'PLATFORM', permissionKey: key }) },
    rootMaintenanceAllowed() { return isPlatformRoot() && Array.isArray(getPermissionPatterns()) && !getRbacLoadFailed() },
    allowed() {
      if (this.action === 'reset-demo-data') return this.rootMaintenanceAllowed() && this.tenant.tenantCode === 'demo-school'
      if (this.action === 'reset-sandbox-data') return this.rootMaintenanceAllowed() && this.tenant.tenantCode === 'sandbox-school'
      return this.can('platform.commercial.manage') && ['enable', 'disable', 'extend-trial', 'expire'].includes(this.action)
    },
    choose(action) {
      if (this.locked || !this.choices.some(item => item.key === action)) return
      this.cancel(); this.action = action
    },
    cancel(force = false) {
      if (this.locked && !force) return
      this.requestEpoch += 1; this.action = ''; this.reason = ''; this.days = 7; this.confirmation = ''; this.phase = 'edit'
      this.busy = false; this.preview = null; this.preparedBody = null; this.error = ''; this.receipt = null; this.attempted = false
    },
    invalidatePreview() {
      if (this.attempted) return
      this.requestEpoch += 1; this.preview = null; this.preparedBody = null; this.confirmation = ''; this.error = ''; this.phase = 'edit'; this.busy = false
    },
    current(epoch, id) { return epoch === this.requestEpoch && id === String(this.tenant.tenantId) },
    async prepare() {
      if (this.locked || !this.allowed()) return
      this.error = ''
      if (this.version === null) { this.error = '未取得可信版本，请先刷新学校状态'; return }
      if (this.reason.trim().length < 5) { this.error = '请填写至少 5 个字符的变更原因'; return }
      const id = String(this.tenant.tenantId), epoch = ++this.requestEpoch
      const body = { reason: this.reason.trim(), expectedVersion: this.version }
      if (this.action === 'extend-trial') body.days = Number(this.days)
      this.busy = true; this.preview = null; this.preparedBody = null
      try {
        if (this.maintenance) {
          const fresh = await platformControlApi.getTenant(id)
          if (!this.current(epoch, id)) return
          if (fresh?.code !== 0 || String(fresh.data?.tenantId) !== id || fresh.data?.tenantCode !== this.tenant.tenantCode || wholeNumber(fresh.data?.tenant360?.version ?? fresh.data?.version) !== body.expectedVersion) throw new Error('学校身份或版本已变化，请刷新后重新核对')
          this.preview = { warnings: ['现场新增数据会被清理。此项为既有环境维护命令，不支持后端版本锁。'] }
        } else {
          const res = await platformControlApi.previewTenantTransition(id, this.action, body)
          if (!this.current(epoch, id)) return
          if (res?.code !== 0) throw new Error(res?.message || '变更预览失败')
          if (!res.data || String(res.data.tenantId) !== id || res.data.action !== this.action || wholeNumber(res.data.expectedVersion) !== body.expectedVersion || typeof res.data.fromStatus !== 'string' || typeof res.data.toStatus !== 'string' || (res.data.warnings != null && !Array.isArray(res.data.warnings))) throw new Error('未取得完整影响预览，已阻止提交')
          this.preview = res.data
        }
        this.preparedBody = Object.freeze({ ...body }); this.confirmation = ''; this.phase = 'preview'
      } catch (error) { if (this.current(epoch, id)) { this.preview = null; this.preparedBody = null; this.error = error?.message || '核对失败，请重试' } }
      finally { if (this.current(epoch, id)) this.busy = false }
    },
    async execute() {
      if (this.locked || this.phase !== 'preview' || !this.preview || !this.preparedBody || !this.allowed()) return
      if (!this.tenant.tenantCode || this.confirmation !== this.tenant.tenantCode) return
      if (this.preparedBody.expectedVersion !== this.version || this.preparedBody.reason !== this.reason.trim() || (this.action === 'extend-trial' && this.preparedBody.days !== Number(this.days))) { this.invalidatePreview(); this.error = '内容或版本已变化，请重新预览'; return }
      const id = String(this.tenant.tenantId), epoch = ++this.requestEpoch, action = this.action
      this.attempted = true; this.busy = true; this.error = ''
      try {
        let res
        if (action === 'reset-sandbox-data') res = await platformControlApi.resetSandboxData(id)
        else if (action === 'reset-demo-data') res = await platformControlApi.tenantAction(id, action, { reason: this.preparedBody.reason })
        else res = await platformControlApi.applyTenantTransition(id, action, { ...this.preparedBody })
        if (!this.current(epoch, id)) return
        if (res?.code !== 0) { this.error = res?.message || '未取得执行结果'; this.phase = 'uncertain'; return }
        if (this.maintenance) this.receipt = { cacheRecoveryRequired: false }
        else {
          const data = res.data
          if (!data || String(data.tenantId) !== id || data.runtimeMaterialized !== true || wholeNumber(data.version) === null || typeof data.cacheInvalidated !== 'boolean' || typeof data.cacheRecoveryRequired !== 'boolean' || data.cacheInvalidated === data.cacheRecoveryRequired) { this.phase = 'uncertain'; return }
          this.receipt = data
        }
        this.phase = 'receipt'; this.preview = null
      } catch (error) { if (this.current(epoch, id)) { this.error = error?.message || '请求中断'; this.phase = 'uncertain' } }
      finally { if (this.current(epoch, id)) this.busy = false }
    },
    async recover() {
      if (this.busy || !this.receipt?.cacheRecoveryRequired || !this.can('platform.operations.manage')) return
      const id = String(this.tenant.tenantId), epoch = ++this.requestEpoch
      this.busy = true; this.error = ''
      try {
        const res = await platformControlHardeningApi.recoverTenantAuthCache(id)
        if (!this.current(epoch, id)) return
        const data = res?.data
        if (res?.code !== 0 || !data || String(data.tenantId) !== id || data.runtimeMaterialized !== true || wholeNumber(data.version) === null || typeof data.cacheInvalidated !== 'boolean' || typeof data.cacheRecoveryRequired !== 'boolean' || data.cacheInvalidated === data.cacheRecoveryRequired) throw new Error(res?.message && res.code !== 0 ? res.message : '未取得可信缓存恢复回执')
        this.receipt = { ...this.receipt, ...data }
      } catch (error) { if (this.current(epoch, id)) this.error = error?.message || '缓存恢复失败；请勿重做业务操作' }
      finally { if (this.current(epoch, id)) this.busy = false }
    }
  }
}
</script>

<style scoped>
.tlw{border:1px solid var(--card-b,#e5eaf2);border-radius:12px;background:var(--bg-card,#fff);padding:20px;color:var(--t1,#1c2844)}.tlw__header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap}.tlw h3,.tlw h4{margin:0;font-size:16px}.tlw h4{font-size:14px}.tlw p{margin:7px 0 0;line-height:1.6;font-size:13px;color:var(--text-secondary,#65758b)}.tlw__version{font-size:12px;white-space:nowrap;color:var(--text-secondary,#65758b)}.tlw__choices,.tlw__actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}.tlw button{padding:9px 13px;border:1px solid var(--card-b,#dce3ee);border-radius:8px;background:var(--bg-card,#fff);color:var(--t1,#1c2844);font:inherit;font-size:13px;cursor:pointer}.tlw button[aria-pressed=true]{background:var(--pri-bg,#edf1ff);color:var(--pri,#3c5cdb);border-color:var(--pri,#3c5cdb)}.tlw button:disabled{opacity:.5;cursor:not-allowed}.tlw .tlw__primary{background:var(--pri,#3c5cdb);border-color:transparent;color:#fff}.tlw .tlw__danger{background:var(--danger-600,#b42318);border-color:transparent;color:#fff}.tlw__form{max-width:800px;margin-top:18px;border-top:1px solid var(--card-b,#e5eaf2);padding-top:16px}.tlw__context{display:flex;flex-wrap:wrap;gap:12px;align-items:baseline}.tlw__context span,.tlw__muted{font-size:12px;color:var(--text-secondary,#65758b)}.tlw__steps{display:flex;flex-wrap:wrap;gap:18px;font-size:12px;color:var(--text-secondary,#65758b);margin:16px 0}.tlw__steps .is-current{color:var(--pri,#3c5cdb);font-weight:650}.tlw label{display:block;font-size:13px;margin-top:14px;line-height:1.8}.tlw textarea,.tlw input,.tlw select{box-sizing:border-box;display:block;margin-top:5px;width:100%;border:1px solid var(--card-b,#dce3ee);border-radius:8px;background:var(--bg-input,#fff);color:var(--t1,#1c2844);padding:9px 11px;font:inherit;font-size:13px}.tlw select{max-width:200px}.tlw textarea{resize:vertical;min-height:90px}.tlw__preview,.tlw__receipt{border:1px solid var(--card-b,#e5eaf2);border-radius:10px;padding:16px;margin-top:16px;background:var(--pri-bg,#f5f7fb)}.tlw__warning{background:var(--warn-l,#fff5e5);color:var(--warning-700,#96530b)!important;padding:12px;border-radius:8px;margin-top:16px}.tlw__error{color:var(--danger-600,#b42318)!important}.tlw ul{padding-left:20px;font-size:13px;line-height:1.7}.tlw :is(button,textarea,input,select):focus-visible{outline:2px solid var(--pri,#3c5cdb);outline-offset:3px}
</style>
