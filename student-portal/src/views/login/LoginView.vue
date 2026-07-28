<template>
  <main class="login-page">
    <section class="brand-panel" aria-labelledby="student-login-title">
      <div class="brand-mark">
        <span v-if="!brandLogo">校</span><img v-else :src="brandLogo" alt="">
        <strong>{{ platformName }}</strong><small>学生服务门户</small>
      </div>
      <div class="brand-copy">
        <p class="eyebrow">学生个人服务入口</p>
        <h1 id="student-login-title">校园里的每件事，<br>都能找到进度和结果。</h1>
        <p class="lead">查课表与成绩、提交材料、办理申请、查看审批进度。登录后只呈现与你本人相关的信息和待办。</p>
        <div class="capabilities"><span>统一办事入口</span><span>全过程进度可查</span><span>消息与结果直达</span></div>
      </div>
      <div class="service-map" aria-label="学生服务能力">
        <div><b>办事务</b><small>申请、补交、修改</small></div>
        <i /><div><b>交材料</b><small>上传、替换、归档</small></div>
        <i /><div><b>查结果</b><small>成绩、审批、证明</small></div>
        <i /><div><b>看进度</b><small>当前节点和下一步</small></div>
      </div>
    </section>

    <section class="form-panel">
      <div class="login-card">
        <p class="card-eyebrow">STUDENT PORTAL</p>
        <h2>学生登录</h2>
        <p class="card-intro">使用学校分配的学号、手机号或统一身份账号进入个人服务门户。</p>
        <div class="entry-note"><span />登录后仅展示本人数据和本人事项</div>

        <form @submit.prevent="doLogin">
          <label for="student-account">学号 / 手机号</label>
          <input id="student-account" v-model.trim="loginName" autocomplete="username" placeholder="请输入学号或手机号">
          <div class="label-row"><label for="student-password">密码</label><button class="text-button" type="button" @click="forgotPassword">忘记密码</button></div>
          <div class="password-field">
            <input id="student-password" v-model="password" :type="showPwd ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入密码">
            <button type="button" class="eye-button" :aria-label="showPwd ? '隐藏密码' : '显示密码'" @click="showPwd = !showPwd">{{ showPwd ? '隐藏' : '显示' }}</button>
          </div>
          <label class="remember"><input v-model="remember" type="checkbox">记住账号</label>

          <details class="tenant-details">
            <summary>切换学校或填写学校编码</summary>
            <label for="student-tenant">学校编码 <small>仅多校同账号时填写</small></label>
            <input id="student-tenant" v-model.trim="tenantCode" autocomplete="organization" placeholder="请输入学校编码">
          </details>

          <label class="agreement"><input v-model="agree" type="checkbox">我已阅读并同意学校提供的用户协议与隐私政策</label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button class="submit-button" :disabled="loading" type="submit">{{ loading ? '登录中…' : '进入学生服务门户' }}</button>
        </form>
        <p class="help-text">首次登录、学号更正或账号无法关联本人档案，请联系辅导员或学校管理员。</p>
      </div>
      <footer><span>技术支持：湖南跃科信息工程有限公司</span><a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">湘ICP备2026031107号</a></footer>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '../../stores/session'
import { usePortalConfigStore } from '../../stores/portalConfig'
import { useUiStore } from '../../stores/ui'

const REMEMBER_KEY = 'student_portal_login_name'
const router = useRouter()
const route = useRoute()
const session = useSessionStore()
const cfg = usePortalConfigStore()
const ui = useUiStore()

const loginName = ref('')
const password = ref('')
const tenantCode = ref(typeof route.query.tenant === 'string' ? route.query.tenant : '')
const error = ref('')
const loading = ref(false)
const showPwd = ref(false)
const remember = ref(false)
const agree = ref(false)
const platformName = computed(() => cfg.brand?.platformName || cfg.portalName || '学生服务门户')
const brandLogo = computed(() => cfg.brand?.logo || '')

onMounted(() => {
  try {
    const saved = localStorage.getItem(REMEMBER_KEY) || ''
    if (saved) {
      loginName.value = saved
      remember.value = true
    }
  } catch {
    // 隐私模式可能禁用本地存储，不影响登录。
  }
})

function forgotPassword() {
  ui.notify('请联系辅导员或学校管理员重置密码')
}

async function doLogin() {
  error.value = ''
  if (!agree.value) {
    error.value = '请先勾选同意用户协议与隐私政策'
    return
  }
  if (!loginName.value || !password.value) {
    error.value = '请输入学号 / 手机号和密码'
    return
  }
  loading.value = true
  try {
    await session.login(loginName.value, password.value, tenantCode.value || undefined)
    try {
      if (remember.value) localStorage.setItem(REMEMBER_KEY, loginName.value)
      else localStorage.removeItem(REMEMBER_KEY)
    } catch {
      // 记住账号失败不阻断真实认证链路。
    }
    cfg.reset()
    await cfg.load()
    const redirect = route.query.redirect
    router.replace(typeof redirect === 'string' ? redirect : '/home')
  } catch (e) {
    error.value = e?.notStudent ? '该账号不是学生账号，请使用教师端入口' : (e?.message || '登录失败，请稍后重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
* { box-sizing: border-box; }
.login-page { min-height: 100vh; display: grid; grid-template-columns: minmax(0, 1.08fr) minmax(480px, .92fr); color: #10233f; background: #f4f7fb; font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
.brand-panel { position: relative; min-height: 100vh; overflow: hidden; padding: clamp(32px, 5vw, 72px); color: #fff; background: linear-gradient(142deg, #174a78, #1b708f 58%, #1a9a9a); }
.brand-panel::before { content: ""; position: absolute; inset: 0; opacity: .22; background-image: radial-gradient(circle at 1px 1px, rgba(255,255,255,.4) 1px, transparent 0); background-size: 28px 28px; mask-image: linear-gradient(#000, transparent 82%); }
.brand-mark { position: relative; z-index: 1; display: grid; grid-template-columns: 40px auto; grid-template-rows: auto auto; column-gap: 12px; align-items: center; }.brand-mark span,.brand-mark img { grid-row: 1 / 3; display: grid; place-items: center; width: 40px; height: 40px; border: 1px solid rgba(255,255,255,.34); border-radius: 12px; background: rgba(255,255,255,.14); }.brand-mark strong { font-size: 14px; }.brand-mark small { color: rgba(255,255,255,.68); font-size: 11px; }
.brand-copy { position: relative; z-index: 1; max-width: 650px; margin-top: clamp(80px, 13vh, 130px); }.eyebrow,.card-eyebrow { margin: 0 0 18px; font-size: 12px; font-weight: 750; letter-spacing: .14em; }.eyebrow { color: #d9f4f1; }.brand-copy h1 { margin: 0; font-size: clamp(38px, 4.4vw, 60px); line-height: 1.18; letter-spacing: -.04em; }.lead { max-width: 600px; margin: 24px 0 0; color: rgba(255,255,255,.82); font-size: 16px; line-height: 1.9; }
.capabilities { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 32px; }.capabilities span { padding: 9px 14px; border: 1px solid rgba(255,255,255,.23); border-radius: 999px; background: rgba(255,255,255,.09); font-size: 12px; }
.service-map { position: absolute; left: clamp(32px, 5vw, 72px); right: clamp(32px, 5vw, 72px); bottom: 54px; z-index: 1; display: flex; align-items: center; max-width: 670px; padding: 16px 18px; border: 1px solid rgba(255,255,255,.22); border-radius: 18px; background: rgba(13,76,98,.25); backdrop-filter: blur(8px); }.service-map div { min-width: 100px; }.service-map b,.service-map small { display: block; }.service-map b { font-size: 13px; }.service-map small { margin-top: 4px; color: rgba(255,255,255,.65); font-size: 10px; }.service-map i { flex: 1; height: 1px; margin: 0 10px; background: rgba(255,255,255,.3); }
.form-panel { min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 20px; padding: 30px; background: radial-gradient(circle at 50% 0, #eaf8f5, transparent 42%), #f4f7fb; }.login-card { width: min(430px, 100%); padding: 34px 38px 30px; border: 1px solid #e2e8f0; border-radius: 20px; background: #fff; box-shadow: 0 24px 70px -38px rgba(16,35,63,.35); }
.card-eyebrow { margin-bottom: 8px; color: #0f766e; }.login-card h2 { margin: 0; font-size: 26px; }.card-intro { margin: 10px 0 18px; color: #718096; font-size: 13px; line-height: 1.65; }.entry-note { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; padding: 9px 11px; border-radius: 9px; color: #40536d; background: #eaf8f5; font-size: 12px; }.entry-note span { width: 7px; height: 7px; border-radius: 50%; background: #0f9f6e; }
form > label,.tenant-details label,.label-row label { display: block; margin: 14px 0 7px; color: #34465f; font-size: 12px; font-weight: 650; }input:not([type=checkbox]) { width: 100%; height: 44px; padding: 0 13px; border: 1px solid #dbe3ed; border-radius: 9px; outline: none; color: #10233f; font: inherit; }.password-field { position: relative; }.password-field input { padding-right: 58px; }.eye-button { position: absolute; right: 10px; top: 0; height: 44px; border: 0; color: #536780; background: none; cursor: pointer; }input:focus { border-color: #15948b; box-shadow: 0 0 0 3px rgba(21,148,139,.12); }
.label-row { display: flex; align-items: flex-end; justify-content: space-between; }.text-button { border: 0; color: #0f766e; background: none; cursor: pointer; font-size: 12px; }.remember,.agreement { display: flex; align-items: flex-start; gap: 8px; font-weight: 400; cursor: pointer; }.remember input,.agreement input { margin: 2px 0 0; accent-color: #15948b; }.agreement { color: #718096; line-height: 1.5; }
.tenant-details { margin-top: 14px; padding: 11px 13px; border: 1px solid #e5eaf1; border-radius: 10px; background: #f8fafc; }.tenant-details summary { color: #536780; cursor: pointer; font-size: 12px; }.tenant-details small { margin-left: 5px; color: #94a3b8; font-weight: 400; }.error { margin: 12px 0 0; padding: 9px 11px; border-radius: 8px; color: #b42318; background: #fff1f0; font-size: 12px; }.submit-button { width: 100%; height: 46px; margin-top: 16px; border: 0; border-radius: 10px; color: #fff; background: linear-gradient(135deg, #15948b, #0f766e); font-size: 14px; font-weight: 700; cursor: pointer; }.submit-button:disabled { opacity: .65; cursor: wait; }
.help-text { margin: 18px 0 0; color: #8290a3; text-align: center; font-size: 11px; }footer { display: flex; gap: 12px; color: #8290a3; font-size: 11px; }footer a { color: inherit; text-decoration: none; }
@media (max-width: 980px) { .login-page { grid-template-columns: 1fr; }.brand-panel { display: none; }.form-panel { min-height: 100vh; }.login-card { width: 440px; } }
@media (max-width: 520px) { .form-panel { width: 100%; min-width: 0; justify-content: flex-start; padding: 28px 16px 18px; }.login-card { width: 100%; padding: 27px 22px 24px; border-radius: 16px; }.login-card h2 { font-size: 23px; }footer { margin-top: auto; flex-direction: column; align-items: center; gap: 3px; } }
@media (max-height: 780px) and (min-width: 981px) { .brand-copy { margin-top: 55px; }.service-map { bottom: 25px; }.form-panel { padding: 18px 30px; }.login-card { padding-top: 25px; padding-bottom: 22px; }.card-intro,.entry-note { margin-bottom: 12px; }form > label,.tenant-details label,.label-row label { margin-top: 10px; }.tenant-details { margin-top: 10px; }.submit-button { margin-top: 12px; } }
</style>
