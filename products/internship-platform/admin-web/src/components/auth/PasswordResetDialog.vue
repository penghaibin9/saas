<template>
  <div class="reset-mask" @click.self="$emit('close')">
    <section class="reset-dialog" role="dialog" aria-modal="true" aria-labelledby="teacher-reset-title">
      <button class="close" type="button" aria-label="关闭" @click="$emit('close')">×</button>
      <p class="eyebrow">SELF-SERVICE RESET</p>
      <h2 id="teacher-reset-title">教师自助重置密码</h2>
      <p class="intro">仅支持本人已验证的独立登录手机号。联系方式、家长号码和 Excel 登记号码不能直接找回密码；不符合条件请联系学校独立核验。</p>
      <ol class="steps"><li :class="{ on: step >= 1 }">验证账号</li><li :class="{ on: step >= 2 }">短信验证</li><li :class="{ on: step >= 3 }">设置新密码</li></ol>

      <form v-if="step === 1" @submit.prevent="requestCode">
        <label for="teacher-reset-type">验证方式</label>
        <select id="teacher-reset-type" v-model="form.identifierType" :disabled="loading"><option value="PHONE">已验证手机号</option><option value="ACCOUNT">原工号 / 账号</option></select>
        <label for="teacher-reset-account">{{ form.identifierType === 'PHONE' ? '已验证手机号' : '工号 / 登录账号' }}</label>
        <input id="teacher-reset-account" v-model.trim="form.loginName" :disabled="loading" autocomplete="username" placeholder="请输入所选方式对应的号码或账号">
        <label for="teacher-reset-tenant">学校编码 <small>多校同账号时填写</small></label>
        <input id="teacher-reset-tenant" v-model.trim="form.tenantCode" :disabled="loading" autocomplete="organization" placeholder="可选">
        <LoginCaptcha visible v-model="captcha.code" :image="captcha.image" :loading="captcha.loading" input-id="teacher-reset-captcha" @refresh="loadCaptcha" />
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary" :disabled="loading" type="submit">{{ loading ? '发送中…' : '发送短信验证码' }}</button>
      </form>

      <form v-else-if="step === 2" @submit.prevent="verifyCode">
        <label for="teacher-sms-code">短信验证码</label>
        <input id="teacher-sms-code" v-model.trim="form.smsCode" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="6 位数字验证码">
        <p class="note">请求只会投递到本人已验证的登录手机号；是否符合条件不会在此页面公开，也不承诺即时送达。</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary" :disabled="loading" type="submit">{{ loading ? '验证中…' : '验证并继续' }}</button>
        <button class="secondary" :disabled="countdown > 0 || loading" type="button" @click="restart">{{ countdown > 0 ? `${countdown} 秒后可重新发送` : '重新获取验证码' }}</button>
      </form>

      <form v-else-if="step === 3" @submit.prevent="confirmReset">
        <label for="teacher-new-password">新密码</label>
        <input id="teacher-new-password" v-model="form.newPassword" type="password" autocomplete="new-password" maxlength="128" placeholder="至少 8 位，建议使用长密码">
        <label for="teacher-confirm-password">再次输入新密码</label>
        <input id="teacher-confirm-password" v-model="form.confirmPassword" type="password" autocomplete="new-password" maxlength="128" placeholder="请再次输入">
        <p class="note">重置成功后，其他设备上的旧登录会失效。</p>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <button class="primary" :disabled="loading" type="submit">{{ loading ? '重置中…' : '确认重置密码' }}</button>
      </form>
      <div v-else>
        <p class="note">{{ note }}</p><p v-if="error" class="error" role="alert">{{ error }}</p>
        <button v-if="step === 4" class="primary" :disabled="loading" @click="checkResult">查询原重置结果</button>
        <button v-else class="primary" @click="$emit('done', form.loginName, form.identifierType)">返回登录</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, toRefs, watch } from 'vue'
import LoginCaptcha from './LoginCaptcha.vue'
import { request } from '@/services/http/client'
import { createResetFlow, resetFlowState } from '../../../../shared/passwordResetFlow.mjs'

const props = defineProps({ loginName: { type: String, default: '' }, tenantCode: { type: String, default: '' }, identifierType: { type: String, default: 'ACCOUNT' } })
defineEmits(['close', 'done'])
const state = reactive(resetFlowState({ loginName: props.loginName, tenantCode: props.tenantCode, identifierType: props.identifierType }))
const { step, error, loading, countdown, form, captcha, note } = toRefs(state)
const flow = createResetFlow(state, { request, clientType: 'TEACHER_PC' })
const { loadCaptcha, requestCode, verifyCode, confirmReset, restart, checkResult } = flow
watch(() => [form.value.loginName, form.value.tenantCode, form.value.identifierType], () => flow.identityChanged(), { flush: 'sync' })
let timer
onMounted(() => { if (form.value.loginName) loadCaptcha(); timer = setInterval(flow.tick, 1000) })
onBeforeUnmount(() => { clearInterval(timer); flow.dispose() })
</script>

<style scoped>
*{box-sizing:border-box}.reset-mask{position:fixed;z-index:1000;inset:0;display:grid;place-items:center;padding:18px;background:rgba(15,35,62,.52);backdrop-filter:blur(4px)}.reset-dialog{position:relative;width:min(460px,100%);max-height:calc(100vh - 36px);overflow:auto;padding:30px;border-radius:20px;background:#fff;box-shadow:0 28px 80px rgba(15,35,62,.28)}.close{position:absolute;top:14px;right:16px;border:0;color:#718096;background:none;font-size:26px;cursor:pointer}.eyebrow{margin:0 0 6px;color:#2563eb;font-size:11px;font-weight:750;letter-spacing:.12em}.reset-dialog h2{margin:0;color:#10233f;font-size:24px}.intro{margin:9px 0 18px;color:#718096;font-size:12px;line-height:1.6}.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:0 0 20px;padding:0;list-style:none}.steps li{padding:7px 4px;border-radius:7px;color:#94a3b8;background:#f4f7fb;text-align:center;font-size:10px}.steps li.on{color:#1f56c9;background:#eef4ff;font-weight:650}label{display:block;margin:13px 0 7px;color:#34465f;font-size:12px;font-weight:650}label small{color:#94a3b8;font-weight:400}input{width:100%;height:44px;padding:0 13px;border:1px solid #dbe3ed;border-radius:9px;outline:none;font:inherit}input:focus{border-color:#2f70ea;box-shadow:0 0 0 3px rgba(47,112,234,.12)}.primary,.secondary{width:100%;height:44px;margin-top:16px;border-radius:9px;cursor:pointer}.primary{border:0;color:#fff;background:linear-gradient(135deg,#2f70ea,#1f56c9);font-weight:700}.secondary{border:1px solid #cdd8e5;color:#40536d;background:#fff}.primary:disabled,.secondary:disabled{opacity:.6;cursor:wait}.error,.note{margin:12px 0 0;padding:9px 11px;border-radius:8px;font-size:11px;line-height:1.55}.error{color:#b42318;background:#fff1f0}.note{color:#536780;background:#f4f7fb}@media(max-width:520px){.reset-mask{align-items:end;padding:0}.reset-dialog{width:100%;max-height:92vh;padding:25px 21px calc(22px + env(safe-area-inset-bottom));border-radius:22px 22px 0 0}}
</style>
