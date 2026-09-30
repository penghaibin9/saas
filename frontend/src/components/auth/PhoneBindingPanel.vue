<template>
  <section class="phone-self" aria-label="本人手机号登录凭据">
    <h3>本人手机号登录</h3>
    <p>原账号和密码始终保留。联系方式、导入号码未经过本人验证，不能用于登录。</p>
    <p v-if="state.binding">当前：{{ state.binding.state === 'VERIFIED' ? '已验证 ' + state.binding.phoneMasked : state.binding.state === 'REVOKED' ? '已撤销，原账号可用' : '未绑定' }}<br>待核验号码：{{ state.binding.candidatePhoneMasked || '未登记' }}</p>
    <p v-if="state.error" role="alert" class="phone-self-error">{{ state.error }}</p>
    <p v-if="state.note" role="status">{{ state.note }}</p>
    <p v-if="state.busy" role="status">正在办理，请勿重复提交…</p>
    <template v-if="state.step === 'READY'">
      <p v-if="state.binding.verificationBlocked">{{ state.binding.verificationBlocked }}</p>
      <label>本次本人手机号<input v-model.trim="state.phone" inputmode="tel" autocomplete="off" maxlength="20" :disabled="state.busy" placeholder="本人使用的 11 位手机号"></label>
      <label>当前登录密码<input v-model="state.currentPassword" type="password" autocomplete="current-password" maxlength="128" :disabled="state.busy"></label>
      <div class="phone-self-actions">
        <button v-if="state.binding.allowedActions?.verify" type="button" :disabled="state.busy" @click="flow.begin('BIND_PHONE')">验证密码并办理绑定</button>
        <button v-if="state.binding.allowedActions?.change" type="button" :disabled="state.busy" @click="flow.begin('CHANGE_PHONE')">验证密码并办理换号</button>
        <button v-if="state.binding.allowedActions?.registerCandidate && state.binding.state !== 'VERIFIED'" type="button" :disabled="state.busy" @click="flow.registerCandidate()">仅登记待核验号码</button>
        <button v-if="state.binding.allowedActions?.revoke" type="button" :disabled="state.busy" @click="flow.begin('REVOKE_PHONE')">验证密码并办理解绑</button>
      </div>
    </template>
    <template v-if="['REAUTHENTICATED', 'CODE_SENT', 'VERIFIED'].includes(state.step)">
      <p>本次填写：{{ state.phone || '撤销当前已验证号码' }} · 验证流程剩余 {{ seconds }} 秒</p>
      <button v-if="state.step === 'REAUTHENTICATED'" type="button" :disabled="state.busy || !seconds" @click="flow.send()">请求短信验证码</button>
      <template v-if="state.step === 'CODE_SENT'"><label>短信验证码<input v-model.trim="state.code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" :disabled="state.busy"></label><button type="button" :disabled="state.busy || !seconds" @click="flow.verify()">验证本次号码</button></template>
      <template v-if="state.step === 'VERIFIED'"><p>确认后旧手机号不能再登录或找回，当前及其他设备需重新登录；原账号和密码不变。</p><label v-if="state.purpose === 'REVOKE_PHONE'">解绑原因<input v-model.trim="state.reason" maxlength="300" :disabled="state.busy"></label><button type="button" :disabled="state.busy || !seconds" @click="flow.confirm()">确认生效并退出旧会话</button></template>
    </template>
    <button v-if="state.step === 'UNCERTAIN'" type="button" :disabled="state.busy" @click="flow.checkResult()">查询原办理结果</button>
    <template v-if="state.step === 'COMMITTED'"><p v-if="state.result.cacheRecoveryRequired || state.result.refreshCleanupRequired">安全变更已提交，部分缓存清理待恢复；不要再次变更号码。</p><button type="button" @click="$emit('changed')">返回登录</button></template>
    <button v-else-if="!['UNCERTAIN', 'SUBMITTING', 'SESSION_CHANGED'].includes(state.step)" type="button" :disabled="state.busy" @click="flow.load()">{{ state.step === 'READY' ? '重新读取状态' : '取消本次证明并重新读取' }}</button>
  </section>
</template>

<script>
import { request, currentSessionGeneration } from '@/services/http/client'
import { createPhoneBindingFlow, phoneBindingState } from '../../../../shared/phoneBindingFlow.mjs'
export default {
  props: { contextKey: { type: String, default: '' } }, emits: ['changed'],
  data() { return { state: phoneBindingState(), flow: null, clock: Date.now(), timer: null } },
  computed: { seconds() { return Math.max(0, Math.floor(this.state.expiresAt - this.clock / 1000)) } },
  watch: { contextKey() { this.start() } },
  mounted() { this.start(); this.timer = setInterval(() => { this.clock = Date.now(); this.flow?.checkSession() }, 1000) },
  beforeUnmount() { clearInterval(this.timer); this.flow?.dispose() },
  methods: { start() { this.flow?.dispose(); this.state = phoneBindingState(); this.flow = createPhoneBindingFlow(this.state, { request, sessionKey: currentSessionGeneration }); this.flow.load() } }
}
</script>

<style scoped>
.phone-self { border:1px solid #dce3ed; border-radius:10px; padding:16px; margin:16px 0; color:#23354c; }.phone-self h3 { margin:0 0 10px; }.phone-self p { font-size:13px; line-height:1.65; overflow-wrap:anywhere; }.phone-self label { display:grid; gap:6px; margin:10px 0; font-size:13px; }.phone-self input { padding:10px; border:1px solid #cbd5e1; border-radius:6px; min-width:0; max-width:100%; font:inherit; }.phone-self button { padding:10px; margin:6px 6px 0 0; background:#eef4ff; border:1px solid #cbd5e1; border-radius:6px; color:#2454a0; cursor:pointer; }.phone-self button:disabled { opacity:.5; cursor:default; }.phone-self-actions { display:flex; flex-wrap:wrap; }.phone-self .phone-self-error { color:#b42318; }
</style>
