<template>
  <main class="login-page">
    <section class="brand-panel" aria-labelledby="login-title">
      <div class="brand-mark"><span>校</span>{{ platformName }}</div>
      <div class="brand-copy">
        <p class="eyebrow">教师 · 管理人员工作入口</p>
        <h1 id="login-title">把每天要办的事，<br>放在一个工作台里。</h1>
        <p class="lead">统一进入教务、学工、岗位实习与毕业设计。登录后按岗位和数据范围自动呈现待办、预警与业务入口。</p>
        <div class="capabilities" aria-label="工作台能力">
          <span>按岗位匹配权限</span><span>跨业务统一待办</span><span>PC 与小程序协同</span>
        </div>
      </div>
      <div class="workspace-art" aria-hidden="true">
        <i class="art-card art-card--one" /><i class="art-card art-card--two" /><i class="art-card art-card--three" />
        <i class="art-line" />
      </div>
    </section>

    <section class="form-panel">
      <div class="login-card">
        <p class="card-eyebrow">STAFF SIGN IN</p>
        <h2>教师 / 管理人员登录</h2>
        <p class="card-intro">使用学校开通的工号、手机号或统一身份账号进入管理工作台。</p>
        <div class="entry-note"><span />当前入口仅面向教师和管理人员</div>

        <form @submit.prevent="doLogin">
          <label for="staff-account">工号 / 手机号</label>
          <input id="staff-account" v-model.trim="form.loginName" autocomplete="username" placeholder="请输入工号或手机号">

          <div class="label-row"><label for="staff-password">密码</label><button type="button" class="text-button" @click="onForgot">忘记密码</button></div>
          <div class="password-field">
            <input id="staff-password" v-model="form.password" :type="pwdVisible ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入密码">
            <button type="button" class="eye-button" :aria-label="pwdVisible ? '隐藏密码' : '显示密码'" @click="pwdVisible = !pwdVisible">{{ pwdVisible ? '隐藏' : '显示' }}</button>
          </div>

          <label class="remember"><input v-model="remember" type="checkbox">记住账号</label>

          <details class="tenant-details">
            <summary>切换学校或填写学校编码</summary>
            <label for="staff-tenant">学校编码 <small>仅多校同账号时填写</small></label>
            <input id="staff-tenant" v-model.trim="form.tenantCode" autocomplete="organization" placeholder="请输入学校编码">
          </details>

          <label class="agreement"><input v-model="agree" type="checkbox">我已阅读并同意学校提供的用户协议与隐私政策</label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button class="submit-button" type="submit" :disabled="loading">{{ loading ? '登录中…' : '进入教师工作台' }}</button>
        </form>
        <p class="help-text">首次登录或账号未开通，请联系本校系统管理员。</p>
      </div>

      <footer>
        <span>技术支持：湖南跃科信息工程有限公司</span>
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">湘ICP备2026031107号</a>
      </footer>
    </section>
  </main>
</template>

<script>
import { DEFAULT_PLATFORM_NAME } from '@/config/portalConfig'
import { isPlatformSuperAdmin, loginWithPassword } from '@/services/http/client'
import { toast } from '@/utils/toast'

const REMEMBER_KEY = 'staff_login_name'

export default {
  name: 'LoginView',
  data() {
    return {
      platformName: DEFAULT_PLATFORM_NAME,
      pwdVisible: false,
      remember: false,
      agree: false,
      loading: false,
      error: '',
      form: { tenantCode: '', loginName: '', password: '' }
    }
  },
  mounted() {
    this.form.tenantCode = String(this.$route.query.tenant || '').trim()
    try {
      const saved = localStorage.getItem(REMEMBER_KEY) || ''
      if (saved) {
        this.form.loginName = saved
        this.remember = true
      }
    } catch {
      // 隐私模式可能禁用本地存储，不影响登录。
    }
  },
  methods: {
    async doLogin() {
      this.error = ''
      if (!this.agree) {
        this.error = '请先勾选同意用户协议与隐私政策'
        return
      }
      if (!this.form.loginName || !this.form.password) {
        this.error = '请输入工号 / 手机号和密码'
        return
      }
      this.loading = true
      try {
        const data = await loginWithPassword(this.form.loginName, this.form.password, this.form.tenantCode)
        try {
          if (this.remember) localStorage.setItem(REMEMBER_KEY, this.form.loginName)
          else localStorage.removeItem(REMEMBER_KEY)
        } catch {
          // 记住账号失败不阻断真实认证链路。
        }
        toast.success(`欢迎，${data.displayName}（${data.currentRole.roleName}）`)
        const redirect = typeof this.$route.query.redirect === 'string' ? this.$route.query.redirect : ''
        this.$router.push(isPlatformSuperAdmin() ? '/admin/platform/overview' : (redirect || '/workbench'))
      } catch (e) {
        this.error = e?.message || '登录失败，请稍后重试'
      } finally {
        this.loading = false
      }
    },
    onForgot() {
      toast.info('请联系本校系统管理员重置密码')
    }
  }
}
</script>

<style scoped>
* { box-sizing: border-box; }
.login-page { min-height: 100vh; display: grid; grid-template-columns: minmax(0, 1.08fr) minmax(480px, .92fr); color: #10233f; background: #f4f7fb; font-family: system-ui, -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
.brand-panel { position: relative; min-height: 100vh; overflow: hidden; padding: clamp(32px, 5vw, 72px); color: #fff; background: linear-gradient(140deg, #173f91 0%, #2563eb 58%, #2f75ef 100%); }
.brand-panel::before { content: ""; position: absolute; inset: 0; opacity: .24; background-image: linear-gradient(rgba(255,255,255,.13) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.13) 1px, transparent 1px); background-size: 44px 44px; mask-image: linear-gradient(to bottom, #000, transparent 80%); }
.brand-mark { position: relative; z-index: 1; display: flex; align-items: center; gap: 12px; font-size: 15px; font-weight: 650; }
.brand-mark span { display: grid; place-items: center; width: 38px; height: 38px; border: 1px solid rgba(255,255,255,.35); border-radius: 11px; background: rgba(255,255,255,.14); }
.brand-copy { position: relative; z-index: 1; max-width: 650px; margin-top: clamp(84px, 14vh, 138px); }
.eyebrow,.card-eyebrow { margin: 0 0 18px; font-size: 12px; font-weight: 750; letter-spacing: .14em; }
.eyebrow { color: #dce9ff; }.brand-copy h1 { margin: 0; font-size: clamp(38px, 4.5vw, 62px); line-height: 1.18; letter-spacing: -.04em; }
.lead { max-width: 600px; margin: 24px 0 0; color: rgba(255,255,255,.82); font-size: 16px; line-height: 1.9; }
.capabilities { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 34px; }.capabilities span { padding: 9px 14px; border: 1px solid rgba(255,255,255,.24); border-radius: 999px; background: rgba(255,255,255,.1); font-size: 12px; }
.workspace-art { position: absolute; right: 4%; bottom: 3%; width: 390px; height: 210px; opacity: .7; }.art-card { position: absolute; width: 150px; height: 88px; border: 1px solid rgba(255,255,255,.36); border-radius: 16px; background: linear-gradient(145deg, rgba(255,255,255,.22), rgba(255,255,255,.05)); box-shadow: 0 22px 50px rgba(15,47,112,.25); transform: skewY(-8deg); }.art-card--one { left: 8px; top: 74px; }.art-card--two { left: 122px; top: 30px; }.art-card--three { right: 0; top: 92px; }.art-line { position: absolute; left: 18px; right: 0; bottom: 28px; height: 1px; background: rgba(255,255,255,.45); transform: rotate(-7deg); }
.form-panel { min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 20px; padding: 30px; background: radial-gradient(circle at 50% 0, #eef5ff, transparent 42%), #f4f7fb; }
.login-card { width: min(430px, 100%); padding: 34px 38px 30px; border: 1px solid #e2e8f0; border-radius: 20px; background: #fff; box-shadow: 0 24px 70px -38px rgba(16,35,63,.35); }
.card-eyebrow { margin-bottom: 8px; color: #2f70ea; }.login-card h2 { margin: 0; font-size: 26px; }.card-intro { margin: 10px 0 18px; color: #718096; font-size: 13px; line-height: 1.65; }
.entry-note { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; padding: 9px 11px; border-radius: 9px; color: #40536d; background: #eef5ff; font-size: 12px; }.entry-note span { width: 7px; height: 7px; border-radius: 50%; background: #2563eb; }
form > label,.tenant-details label,.label-row label { display: block; margin: 14px 0 7px; color: #34465f; font-size: 12px; font-weight: 650; }
input:not([type=checkbox]) { width: 100%; height: 44px; padding: 0 13px; border: 1px solid #dbe3ed; border-radius: 9px; outline: none; color: #10233f; font: inherit; }.password-field { position: relative; }.password-field input { padding-right: 58px; }.eye-button { position: absolute; right: 10px; top: 0; height: 44px; border: 0; color: #536780; background: none; cursor: pointer; }
input:focus { border-color: #2f70ea; box-shadow: 0 0 0 3px rgba(47,112,234,.12); }.label-row { display: flex; align-items: flex-end; justify-content: space-between; }.text-button { border: 0; color: #2563eb; background: none; cursor: pointer; font-size: 12px; }
.remember,.agreement { display: flex; align-items: flex-start; gap: 8px; font-weight: 400; cursor: pointer; }.remember input,.agreement input { margin: 2px 0 0; accent-color: #2563eb; }.agreement { color: #718096; line-height: 1.5; }
.tenant-details { margin-top: 14px; padding: 11px 13px; border: 1px solid #e5eaf1; border-radius: 10px; background: #f8fafc; }.tenant-details summary { color: #536780; cursor: pointer; font-size: 12px; }.tenant-details small { margin-left: 5px; color: #94a3b8; font-weight: 400; }
.error { margin: 12px 0 0; padding: 9px 11px; border-radius: 8px; color: #b42318; background: #fff1f0; font-size: 12px; }.submit-button { width: 100%; height: 46px; margin-top: 16px; border: 0; border-radius: 10px; color: #fff; background: linear-gradient(135deg, #2f70ea, #1f56c9); font-size: 14px; font-weight: 700; cursor: pointer; }.submit-button:disabled { opacity: .65; cursor: wait; }
.help-text { margin: 18px 0 0; color: #8290a3; text-align: center; font-size: 11px; }footer { display: flex; gap: 12px; color: #8290a3; font-size: 11px; }footer a { color: inherit; text-decoration: none; }
@media (max-width: 980px) { .login-page { grid-template-columns: 1fr; }.brand-panel { display: none; }.form-panel { min-height: 100vh; }.login-card { width: 440px; } }
@media (max-width: 520px) { .form-panel { width: 100%; min-width: 0; justify-content: flex-start; padding: 28px 16px 18px; }.login-card { width: 100%; padding: 27px 22px 24px; border-radius: 16px; }.login-card h2 { font-size: 23px; }footer { margin-top: auto; flex-direction: column; align-items: center; gap: 3px; } }
@media (max-height: 780px) and (min-width: 981px) { .brand-copy { margin-top: 60px; }.workspace-art { transform: scale(.8); transform-origin: right bottom; }.form-panel { padding: 18px 30px; }.login-card { padding-top: 25px; padding-bottom: 22px; }.card-intro { margin-bottom: 12px; }.entry-note { margin-bottom: 12px; }form > label,.tenant-details label,.label-row label { margin-top: 10px; }.tenant-details { margin-top: 10px; }.submit-button { margin-top: 12px; } }
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
</style>
