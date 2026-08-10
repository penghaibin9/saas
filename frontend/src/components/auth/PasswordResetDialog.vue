<template>
  <div class="reset-mask" @click.self="$emit('close')">
    <section class="reset-dialog" role="dialog" aria-modal="true" aria-labelledby="teacher-reset-title">
      <button class="close" type="button" aria-label="关闭" @click="$emit('close')">×</button>
      <p class="eyebrow">SELF-SERVICE RESET</p>
      <h2 id="teacher-reset-title">教师自助重置密码</h2>
      <p class="intro">验证码只发送到学校档案中已绑定的手机号；多次失败后再联系学校管理员。</p>
      <ol class="steps"><li :class="{ on: step >= 1 }">验证账号</li><li :class="{ on: step >= 2 }">短信验证</li><li :class="{ on: step >= 3 }">设置新密码</li></ol>

      <form v-if="step === 1" @submit.prevent="requestCode">
        <label for="teacher-reset-account">工号 / 登录账号</label>
        <input id="teacher-reset-account" v-model.trim="form.loginName" autocomplete="username" placeholder="请输入工号或登录账号">
        <label for="teacher-reset-tenant">学校编码 <small>多校同账号时填写</small></label>
        <input id="teacher-reset-tenant" v-model.trim="form.tenantCode" autocomplete="organization" placeholder="可选">
        <LoginCaptcha visible v-model="captcha.code" :image="captcha.image" :loading="captcha.loading" input-id="teacher-reset-captcha" @refresh="loadCaptcha" />
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary" :disabled="loading" type="submit">{{ loading ? '发送中…' : '发送短信验证码' }}</button>
      </form>

      <form v-else-if="step === 2" @submit.prevent="verifyCode">
        <label for="teacher-sms-code">短信验证码</label>
        <input id="teacher-sms-code" v-model.trim="form.smsCode" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="6 位数字验证码">
        <p class="note">若账号存在且已绑定手机号，短信会在几分钟内送达，系统不会展示完整手机号。</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary" :disabled="loading" type="submit">{{ loading ? '验证中…' : '验证并继续' }}</button>
        <button class="secondary" :disabled="countdown > 0 || loading" type="button" @click="restart">{{ countdown > 0 ? `${countdown} 秒后可重新发送` : '重新获取验证码' }}</button>
      </form>

      <form v-else @submit.prevent="confirmReset">
        <label for="teacher-new-password">新密码</label>
        <input id="teacher-new-password" v-model="form.newPassword" type="password" autocomplete="new-password" maxlength="128" placeholder="至少 8 位，建议使用长密码">
        <label for="teacher-confirm-password">再次输入新密码</label>
        <input id="teacher-confirm-password" v-model="form.confirmPassword" type="password" autocomplete="new-password" maxlength="128" placeholder="请再次输入">
        <p class="note">重置成功后，其他设备上的旧登录会失效。</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary" :disabled="loading" type="submit">{{ loading ? '重置中…' : '确认重置密码' }}</button>
      </form>
    </section>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import LoginCaptcha from './LoginCaptcha.vue'
import { confirmPasswordReset, issueLoginCaptcha, requestPasswordResetCode, verifyPasswordResetCode } from '@/services/http/client'

const props = defineProps({ loginName: { type: String, default: '' }, tenantCode: { type: String, default: '' } })
const emit = defineEmits(['close', 'done'])
const step = ref(1)
const error = ref('')
const loading = ref(false)
const countdown = ref(0)
const nonce = `teacher-reset-${Date.now()}-${Math.random()}`
const form = reactive({ loginName: props.loginName, tenantCode: props.tenantCode, smsCode: '', requestId: '', resetToken: '', newPassword: '', confirmPassword: '' })
const captcha = reactive({ id: '', code: '', image: '', loading: false })
let timer = null

function startCountdown(seconds) {
  clearInterval(timer); countdown.value = Number(seconds) || 60
  timer = setInterval(() => { if (countdown.value > 0) countdown.value -= 1; else clearInterval(timer) }, 1000)
}
async function loadCaptcha() {
  error.value = ''
  if (!form.loginName) { error.value = '请先填写工号或登录账号'; return }
  captcha.loading = true
  try {
    const data = await issueLoginCaptcha({ scene: 'PASSWORD_RESET', tenantCode: form.tenantCode || undefined, loginName: form.loginName, clientNonce: nonce, clientType: 'TEACHER_PC' })
    captcha.id = data.captchaId; captcha.image = data.imageDataUrl; captcha.code = ''
  } catch (e) { error.value = e?.message || '图形验证码加载失败，请稍后重试' } finally { captcha.loading = false }
}
async function requestCode() {
  error.value = ''
  if (!form.loginName) { error.value = '请输入工号或登录账号'; return }
  if (!captcha.id) { await loadCaptcha(); return }
  if (!/^\d{6}$/.test(captcha.code)) { error.value = '请输入图中 6 位验证码'; return }
  loading.value = true
  try {
    const data = await requestPasswordResetCode({ tenantCode: form.tenantCode || undefined, loginName: form.loginName, captchaId: captcha.id, captchaCode: captcha.code, clientNonce: nonce, clientType: 'TEACHER_PC' })
    form.requestId = data.requestId; step.value = 2; startCountdown(data.retryAfter)
  } catch (e) { error.value = e?.message || '验证码发送失败，请稍后重试'; await loadCaptcha() } finally { loading.value = false }
}
async function verifyCode() {
  error.value = ''
  if (!/^\d{6}$/.test(form.smsCode)) { error.value = '请输入 6 位短信验证码'; return }
  loading.value = true
  try {
    const data = await verifyPasswordResetCode({ requestId: form.requestId, code: form.smsCode, clientNonce: nonce, clientType: 'TEACHER_PC' })
    form.resetToken = data.resetToken; step.value = 3
  } catch (e) { error.value = e?.message || '短信验证码无效，请重新获取' } finally { loading.value = false }
}
async function confirmReset() {
  error.value = ''
  if (form.newPassword.length < 8) { error.value = '新密码至少 8 位'; return }
  if (form.newPassword !== form.confirmPassword) { error.value = '两次输入的新密码不一致'; return }
  loading.value = true
  try {
    await confirmPasswordReset({ resetToken: form.resetToken, newPassword: form.newPassword, confirmPassword: form.confirmPassword })
    emit('done', form.loginName)
  } catch (e) { error.value = e?.message || '密码重置失败，请重新验证' } finally { loading.value = false }
}
async function restart() {
  step.value = 1; form.smsCode = ''; error.value = ''; captcha.id = ''; captcha.image = ''; captcha.code = ''
  await nextTick(); await loadCaptcha()
}
onMounted(() => { if (form.loginName) loadCaptcha() })
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
*{box-sizing:border-box}.reset-mask{position:fixed;z-index:1000;inset:0;display:grid;place-items:center;padding:18px;background:rgba(15,35,62,.52);backdrop-filter:blur(4px)}.reset-dialog{position:relative;width:min(460px,100%);max-height:calc(100vh - 36px);overflow:auto;padding:30px;border-radius:20px;background:#fff;box-shadow:0 28px 80px rgba(15,35,62,.28)}.close{position:absolute;top:14px;right:16px;border:0;color:#718096;background:none;font-size:26px;cursor:pointer}.eyebrow{margin:0 0 6px;color:#2563eb;font-size:11px;font-weight:750;letter-spacing:.12em}.reset-dialog h2{margin:0;color:#10233f;font-size:24px}.intro{margin:9px 0 18px;color:#718096;font-size:12px;line-height:1.6}.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:0 0 20px;padding:0;list-style:none}.steps li{padding:7px 4px;border-radius:7px;color:#94a3b8;background:#f4f7fb;text-align:center;font-size:10px}.steps li.on{color:#1f56c9;background:#eef4ff;font-weight:650}label{display:block;margin:13px 0 7px;color:#34465f;font-size:12px;font-weight:650}label small{color:#94a3b8;font-weight:400}input{width:100%;height:44px;padding:0 13px;border:1px solid #dbe3ed;border-radius:9px;outline:none;font:inherit}input:focus{border-color:#2f70ea;box-shadow:0 0 0 3px rgba(47,112,234,.12)}.primary,.secondary{width:100%;height:44px;margin-top:16px;border-radius:9px;cursor:pointer}.primary{border:0;color:#fff;background:linear-gradient(135deg,#2f70ea,#1f56c9);font-weight:700}.secondary{border:1px solid #cdd8e5;color:#40536d;background:#fff}.primary:disabled,.secondary:disabled{opacity:.6;cursor:wait}.error,.note{margin:12px 0 0;padding:9px 11px;border-radius:8px;font-size:11px;line-height:1.55}.error{color:#b42318;background:#fff1f0}.note{color:#536780;background:#f4f7fb}@media(max-width:520px){.reset-mask{align-items:end;padding:0}.reset-dialog{width:100%;max-height:92vh;padding:25px 21px calc(22px + env(safe-area-inset-bottom));border-radius:22px 22px 0 0}}
</style>
