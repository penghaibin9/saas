<template>
  <view class="phone-self card stack-sm">
    <text class="section-head__title">本人手机号登录</text>
    <text>原学号 / 账号和密码始终保留。联系号码、学校导入号码未验证前不能登录。</text>
    <text v-if="state.binding">登录号码：{{ state.binding.phoneMasked || '未绑定' }}；候选：{{ state.binding.candidatePhoneMasked || '未登记' }}</text>
    <text v-if="state.error" class="phone-error">{{ state.error }}</text><text v-if="state.note">{{ state.note }}</text>
    <text v-if="state.busy">正在处理，请勿重复提交…</text>
    <template v-if="state.step === 'READY'">
      <text v-if="state.binding.verificationBlocked">{{ state.binding.verificationBlocked }}</text>
      <text>本次本人手机号</text><input v-model.trim="state.phone" class="phone-input" type="number" :maxlength="11" :disabled="state.busy" placeholder="本人使用的 11 位手机号" />
      <text>当前登录密码</text><input v-model="state.currentPassword" class="phone-input" password :maxlength="128" :disabled="state.busy" placeholder="验证本次办理身份" />
      <button v-if="state.binding.allowedActions?.verify" class="btn btn-primary" :disabled="state.busy" @click="flow.begin('BIND_PHONE')">验证密码并绑定</button>
      <button v-if="state.binding.allowedActions?.change" class="btn btn-primary" :disabled="state.busy" @click="flow.begin('CHANGE_PHONE')">验证密码并换号</button>
      <button v-if="state.binding.allowedActions?.registerCandidate && state.binding.state !== 'VERIFIED'" class="btn" :disabled="state.busy" @click="flow.registerCandidate()">仅登记待验证号码</button>
      <button v-if="state.binding.allowedActions?.revoke" class="btn" :disabled="state.busy" @click="flow.begin('REVOKE_PHONE')">验证密码并解绑</button>
    </template>
    <template v-if="['REAUTHENTICATED', 'CODE_SENT', 'VERIFIED'].includes(state.step)">
      <text>本次：{{ state.phone || '撤销当前号码' }} · 有效期剩余 {{ seconds }} 秒</text>
      <button v-if="state.step === 'REAUTHENTICATED'" class="btn btn-primary" :disabled="state.busy || !seconds" @click="flow.send()">请求短信验证码</button>
      <template v-if="state.step === 'CODE_SENT'"><text>短信验证码</text><input v-model.trim="state.code" class="phone-input" type="number" :maxlength="6" :disabled="state.busy" placeholder="输入收到的 6 位验证码" /><button class="btn btn-primary" :disabled="state.busy || !seconds" @click="flow.verify()">验证本次号码</button></template>
      <template v-if="state.step === 'VERIFIED'"><text>确认后旧手机号不能登录或找回，当前及其他设备需重新登录。原账号和密码保留。</text><template v-if="state.purpose === 'REVOKE_PHONE'"><text>解绑原因</text><input v-model.trim="state.reason" class="phone-input" :maxlength="300" :disabled="state.busy" /></template><button class="btn btn-primary" :disabled="state.busy || !seconds" @click="flow.confirm()">确认生效并退出旧会话</button></template>
    </template>
    <button v-if="state.step === 'UNCERTAIN'" class="btn btn-primary" :disabled="state.busy" @click="flow.checkResult()">查询原办理结果</button>
    <template v-if="state.step === 'COMMITTED'"><text v-if="state.result.cacheRecoveryRequired || state.result.refreshCleanupRequired">安全变更已提交，部分缓存清理待恢复，请勿重复操作。</text><button class="btn btn-primary" @click="$emit('changed')">返回本端登录</button></template>
    <button v-else-if="!['UNCERTAIN', 'SUBMITTING', 'SESSION_CHANGED'].includes(state.step)" class="btn" :disabled="state.busy" @click="flow.load()">取消证明 / 重新读取</button>
    <text>丢号且忘记密码请联系学校进行独立身份核验，不要向他人提供密码或验证码。</text>
  </view>
</template>

<script>
import { realRequest } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { createPhoneBindingFlow, phoneBindingState } from '../../../../shared/phoneBindingFlow.mjs'
export default {
  props: { contextKey: { type: String, default: '' } }, emits: ['changed'],
  data() { return { state: phoneBindingState(), flow: null, clock: Date.now(), timer: null } },
  computed: { seconds() { return Math.max(0, Math.floor(this.state.expiresAt - this.clock / 1000)) } },
  watch: { contextKey() { this.start() } },
  mounted() { this.start(); this.timer = setInterval(() => { this.clock = Date.now(); this.flow?.checkSession() }, 1000) },
  beforeUnmount() { clearInterval(this.timer); this.flow?.dispose() },
  methods: { start() {
    this.flow?.dispose(); this.state = phoneBindingState()
    this.flow = createPhoneBindingFlow(this.state, { sessionKey: currentSessionGeneration,
      request: (path, options) => realRequest(path, { method: options.method, data: options.body, auth: options.auth, headers: options.headers }) })
    this.flow.load()
  } }
}
</script>

<style scoped>
.phone-self { margin:12px 0; font-size:14px; line-height:1.7; }.phone-self text { overflow-wrap:anywhere; }.phone-input { height:44px; border:1px solid var(--border-base); border-radius:6px; padding:0 12px; font-size:15px; }.phone-error { color:var(--danger-600, #b42318); }
</style>
