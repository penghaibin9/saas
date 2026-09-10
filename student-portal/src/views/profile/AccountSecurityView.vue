<template>
  <main class="account-security">
    <header><h1>我的账号与安全</h1><p>{{ session.user?.realName || '当前学生' }} · 本人办理</p><RouterLink to="/home">返回学生工作台</RouterLink></header>
    <p>原学号 / 账号始终保留。手机号须本人验证，学校导入和联系方式不能直接用于登录。</p>
    <p v-if="state.binding">登录号码：{{ state.binding.phoneMasked || '未绑定' }} · 候选：{{ state.binding.candidatePhoneMasked || '未登记' }}</p>
    <p v-if="state.error" role="alert" class="security-error">{{ state.error }}</p><p v-if="state.note" role="status">{{ state.note }}</p>
    <p v-if="state.busy" role="status">正在处理，请勿重复提交…</p>
    <template v-if="state.step === 'READY'">
      <p v-if="state.binding.verificationBlocked">{{ state.binding.verificationBlocked }}</p>
      <label>本人手机号<input v-model.trim="state.phone" inputmode="tel" autocomplete="off" maxlength="20" :disabled="state.busy"></label>
      <label>当前密码<input v-model="state.currentPassword" type="password" autocomplete="current-password" maxlength="128" :disabled="state.busy"></label>
      <div class="security-actions">
        <button v-if="state.binding.allowedActions?.verify" :disabled="state.busy" @click="flow.begin('BIND_PHONE')">验证密码并绑定</button>
        <button v-if="state.binding.allowedActions?.change" :disabled="state.busy" @click="flow.begin('CHANGE_PHONE')">验证密码并换号</button>
        <button v-if="state.binding.allowedActions?.registerCandidate && state.binding.state !== 'VERIFIED'" :disabled="state.busy" @click="flow.registerCandidate()">仅登记待验证号码</button>
        <button v-if="state.binding.allowedActions?.revoke" :disabled="state.busy" @click="flow.begin('REVOKE_PHONE')">验证密码并解绑</button>
      </div>
    </template>
    <template v-if="['REAUTHENTICATED', 'CODE_SENT', 'VERIFIED'].includes(state.step)">
      <p>本次：{{ state.phone || '撤销当前号码' }} · 有效期剩余 {{ seconds }} 秒</p>
      <button v-if="state.step === 'REAUTHENTICATED'" :disabled="state.busy || !seconds" @click="flow.send()">请求短信验证码</button>
      <template v-if="state.step === 'CODE_SENT'"><label>短信验证码<input v-model.trim="state.code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" :disabled="state.busy"></label><button :disabled="state.busy || !seconds" @click="flow.verify()">验证本次号码</button></template>
      <template v-if="state.step === 'VERIFIED'"><p>确认后旧手机号不能登录或找回，旧设备会话失效；原账号及密码仍可使用。</p><label v-if="state.purpose === 'REVOKE_PHONE'">解绑原因<input v-model.trim="state.reason" maxlength="300" :disabled="state.busy"></label><button :disabled="state.busy || !seconds" @click="flow.confirm()">确认生效并退出旧会话</button></template>
    </template>
    <button v-if="state.step === 'UNCERTAIN'" :disabled="state.busy" @click="flow.checkResult()">查询原办理结果</button>
    <template v-if="state.step === 'COMMITTED'"><p v-if="state.result.cacheRecoveryRequired || state.result.refreshCleanupRequired">安全变更已提交，部分缓存清理待恢复，请勿重复操作。</p><button @click="relogin">返回学生登录</button></template>
    <button v-else-if="!['UNCERTAIN', 'SUBMITTING', 'SESSION_CHANGED'].includes(state.step)" :disabled="state.busy" @click="flow.load()">取消证明 / 重新读取</button>
    <p>丢号且忘记密码、家长或共用号码请联系学校进行身份核验，不要向他人提供密码或验证码。</p>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../../stores/session'
import { request, currentSessionGeneration } from '../../services/request'
import { createPhoneBindingFlow, phoneBindingState } from '../../../../shared/phoneBindingFlow.mjs'
const session = useSessionStore(), router = useRouter(), state = reactive(phoneBindingState()), clock = ref(Date.now())
const flow = createPhoneBindingFlow(state, { request, sessionKey: currentSessionGeneration })
const seconds = computed(() => Math.max(0, Math.floor(state.expiresAt - clock.value / 1000)))
watch(() => [session.user?.userId, session.user?.tenantId, session.user?.activeContextId], () => flow.checkSession())
let timer
onMounted(() => { flow.load(); timer = setInterval(() => { clock.value = Date.now(); flow.checkSession() }, 1000) })
onBeforeUnmount(() => { clearInterval(timer); flow.dispose() })
async function relogin() { flow.dispose(); await session.logout(); await router.replace('/login') }
</script>

<style scoped>
.account-security { width:min(660px, calc(100% - 32px)); box-sizing:border-box; margin:24px auto; padding:24px; border:1px solid #dce3ed; border-radius:14px; background:#fff; color:#23354c; }.account-security h1 { font-size:23px; }.account-security p { font-size:14px; line-height:1.8; overflow-wrap:anywhere; }.account-security label { display:grid; gap:8px; margin:16px 0; }.account-security input { border:1px solid #cbd5e1; border-radius:6px; padding:11px; min-width:0; font:inherit; }.account-security button { border:1px solid #cbd5e1; background:#eef4ff; color:#2454a0; border-radius:6px; padding:11px; margin:5px 8px 5px 0; cursor:pointer; }.account-security button:disabled { opacity:.5; cursor:default; }.security-actions { display:flex; flex-wrap:wrap; }.security-error { color:#b42318; }
</style>
