<template>
  <ForcePasswordChangeView v-if="$route.query.forcePasswordChange === '1'" />
  <main v-else class="login-page">
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
        <p class="card-intro">{{ form.identifierType === 'PHONE' ? '使用本人已验证的手机号与原密码登录。' : '使用学校开通的工号或统一账号。' }}</p>

        <form @submit.prevent="doLogin">
          <div class="login-modes" role="group" aria-label="登录方式">
            <button v-for="mode in [{ value: 'ACCOUNT', label: '账号登录' }, { value: 'PHONE', label: '手机号登录' }]" :key="mode.value" type="button" :disabled="loading" :aria-pressed="form.identifierType === mode.value" @click="form.identifierType = mode.value">{{ mode.label }}</button>
          </div>
          <label for="staff-account">{{ form.identifierType === 'PHONE' ? '已验证手机号' : '账号' }}</label>
          <div class="identity-field">
            <User class="field-icon" aria-hidden="true" />
            <input :disabled="loading" id="staff-account" v-model.trim="form.loginName" autocomplete="username" :inputmode="form.identifierType === 'PHONE' ? 'tel' : 'text'" :placeholder="form.identifierType === 'PHONE' ? '请输入本人已验证的手机号' : '请输入工号或统一账号'">
          </div>

          <div class="label-row"><label for="staff-password">密码</label><button type="button" class="text-button" @click="onForgot">忘记密码</button></div>
          <div class="password-field">
            <Lock class="field-icon" aria-hidden="true" />
            <input :disabled="loading" id="staff-password" v-model="form.password" :type="pwdVisible ? 'text' : 'password'" autocomplete="current-password" placeholder="请输入登录密码">
            <button type="button" class="eye-button" :aria-label="pwdVisible ? '隐藏密码' : '显示密码'" @click="pwdVisible = !pwdVisible"><ViewIcon aria-hidden="true" />{{ pwdVisible ? '隐藏' : '显示' }}</button>
          </div>

          <LoginCaptcha :visible="captcha.required" v-model="captcha.code" :image="captcha.image" :loading="captcha.loading" @refresh="refreshCaptcha" />

          <label class="remember"><input :disabled="loading" v-model="remember" type="checkbox">记住账号</label>

          <details class="tenant-details">
            <summary>切换学校或填写学校编码</summary>
            <label for="staff-tenant">学校编码 <small>仅多校同账号时填写</small></label>
            <input :disabled="loading" id="staff-tenant" v-model.trim="form.tenantCode" autocomplete="organization" placeholder="请输入学校编码">
          </details>

          <label class="agreement"><input :disabled="loading" v-model="agree" type="checkbox">我已阅读并同意学校提供的用户协议与隐私政策</label>
          <p v-if="error" class="error" role="alert">{{ error }}</p>
          <button class="submit-button" type="submit" :disabled="loading">{{ loading ? '登录中…' : '进入教师工作台' }}</button>
        </form>
        <p class="help-text">首次登录或账号未开通，请联系本校系统管理员。</p>
      </div>

      <footer>
        <span>技术支持：湖南跃科信息工程有限公司</span>
        <a href="https://beian.miit.gov.cn/" rel="noopener noreferrer">湘ICP备2026031107号</a>
      </footer>
    </section>
    <PasswordResetDialog v-if="resetVisible" :login-name="form.loginName" :tenant-code="form.tenantCode" :identifier-type="form.identifierType" @close="resetVisible = false" @done="resetDone" />
  </main>
</template>

<script>
import { DEFAULT_PLATFORM_NAME } from '@/config/portalConfig'
import { User, Lock, View as ViewIcon } from '@element-plus/icons-vue'
import { isPlatformSuperAdmin, issueLoginCaptcha, loginWithPassword } from '@/services/http/client'
import LoginCaptcha from '@/components/auth/LoginCaptcha.vue'
import PasswordResetDialog from '@/components/auth/PasswordResetDialog.vue'
import ForcePasswordChangeView from '@/views/ForcePasswordChangeView.vue'
import { toast } from '@/utils/toast'
import { createIdentityCaptcha } from '../../../shared/identityCaptcha.mjs'

const REMEMBER_KEY = 'staff_login_name'
const TENANT_KEY = 'staff_tenant_code'

export default {
  name: 'LoginView',
  components: { LoginCaptcha, PasswordResetDialog, ForcePasswordChangeView, User, Lock, ViewIcon },
  data() {
    return {
      platformName: DEFAULT_PLATFORM_NAME,
      pwdVisible: false,
      remember: false,
      agree: false,
      loading: false,
      error: '',
      resetVisible: false,
      captcha: { required: false, id: '', code: '', image: '', loading: false, nonce: '' },
      form: { tenantCode: '', loginName: '', password: '', identifierType: 'ACCOUNT' }
    }
  },
  created() {
    this.captchaFlow = createIdentityCaptcha(this.captcha, { identity: () => ({ scene: 'PASSWORD_LOGIN', tenantCode: this.form.tenantCode || undefined, identifierType: this.form.identifierType, identifier: this.form.loginName, clientType: 'PC' }), issue: issueLoginCaptcha, error: message => { this.error = message } })
  },
  watch: {
    'form.loginName': { handler() { this.captchaFlow.invalidate() }, flush: 'sync' },
    'form.tenantCode': { handler() { this.captchaFlow.invalidate() }, flush: 'sync' },
    'form.identifierType': { handler() { this.captchaFlow.invalidate(); this.form.loginName = ''; this.form.password = '' }, flush: 'sync' }
  },
  beforeUnmount() { this.captchaFlow.dispose(); this.form.password = '' },
  mounted() {
    this.form.tenantCode = String(this.$route.query.tenant || '').trim()
    try {
      const saved = localStorage.getItem(REMEMBER_KEY) || ''
      if (saved) {
        this.form.loginName = saved
        this.remember = true
      }
      if (!this.form.tenantCode) this.form.tenantCode = localStorage.getItem(TENANT_KEY) || ''
    } catch {
      // 隐私模式可能禁用本地存储，不影响登录。
    }
  },
  methods: {
    async refreshCaptcha() {
      return this.captchaFlow.load()
    },
    async requireCaptcha(error) {
      const code = error?.bizCode || ''
      if (!code.startsWith('CAPTCHA_') && !error?.details?.captchaRequired) return false
      this.captcha.required = true; await this.refreshCaptcha(); return true
    },
    async doLogin() {
      if (this.loading) return
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
        await this.captchaFlow.ensureNonce()
        if (this.captcha.required && (!this.captcha.id || this.captcha.code.length !== 6)) { this.error = '请输入图中 6 位验证码'; return }
        const data = await loginWithPassword(this.form.loginName, this.form.password, this.form.tenantCode, { captchaId: this.captcha.id, captchaCode: this.captcha.code, clientNonce: this.captcha.nonce, clientType: 'PC', identifierType: this.form.identifierType })
        try {
          if (this.remember && this.form.identifierType === 'ACCOUNT') localStorage.setItem(REMEMBER_KEY, this.form.loginName)
          else localStorage.removeItem(REMEMBER_KEY)
          if (this.form.tenantCode) localStorage.setItem(TENANT_KEY, this.form.tenantCode)
          else localStorage.removeItem(TENANT_KEY)
        } catch {
          // 记住账号失败不阻断真实认证链路。
        }
        if (data?.user?.mustChangePassword) {
          // 前端跳转只负责体验；真正不可绕过的强制门禁在后端 get_current_user。
          toast.info('首次登录需要先修改初始密码')
          await this.$router.replace({ path: '/login', query: { forcePasswordChange: '1' } })
          return
        }
        toast.success(`欢迎，${data.displayName}（${data.currentRole.roleName}）`)
        const redirect = typeof this.$route.query.redirect === 'string' ? this.$route.query.redirect : ''
        this.$router.push(isPlatformSuperAdmin() ? '/admin/platform/overview' : (redirect || '/workbench'))
      } catch (e) {
        await this.requireCaptcha(e)
        this.error = e?.message || '登录失败，请稍后重试'
      } finally {
        this.loading = false
      }
    },
    onForgot() {
      if (this.loading) return
      this.resetVisible = true
    },
    resetDone(loginName, identifierType) {
      if (identifierType) this.form.identifierType = identifierType
      this.form.loginName = loginName || this.form.loginName
      this.form.password = ''
      this.resetVisible = false
      toast.success('密码已重置，请使用新密码登录')
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
.login-modes { display: grid; grid-template-columns: 1fr 1fr; padding: 4px; margin: 22px 0 24px; border-radius: 14px; background: #eaf1fc; }
.login-modes button { min-height: 44px; border: 0; border-radius: 10px; background: transparent; color: #61718a; font: inherit; font-size: 15px; font-weight: 650; cursor: pointer; }
.login-modes button[aria-pressed="true"] { color: #2563eb; background: #fff; box-shadow: 0 2px 8px #234a8310; }
.login-modes button:hover { color: #1f56c9; }
.login-modes button:focus-visible,.eye-button:focus-visible,.text-button:focus-visible,.submit-button:focus-visible { outline: 3px solid #93b9ff; outline-offset: 3px; }
.login-modes button:disabled { cursor: wait; opacity: .65; }
.identity-field,.password-field { position: relative; }
.field-icon { position: absolute; z-index: 1; left: 14px; top: 15px; width: 20px; height: 20px; color: #7a8ba3; pointer-events: none; }
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
.login-card { width: min(480px, 100%); padding: 32px 38px 28px; }
.card-intro { font-size: 14px; margin: 12px 0 20px; }
form > label,.label-row label { font-size: 14px; margin-top: 20px; }
.identity-field input,.password-field input { height: 50px; padding-left: 44px; font-size: 15px; background: #fafbfd; }
.password-field input { padding-right: 82px; }
.eye-button { display: flex; align-items: center; gap: 5px; height: 50px; font: inherit; font-size: 13px; }
.eye-button svg { width: 18px; height: 18px; }
form > .remember,form > .agreement { display: flex; font-weight: 400; }
.remember input,.agreement input { width: 16px; height: 16px; flex-shrink: 0; }
form > .agreement { font-size: 12px; line-height: 1.7; }
.tenant-details { margin-top: 20px; padding: 14px; }
.tenant-details summary,.text-button { font-size: 13px; }
.submit-button { height: 50px; font-size: 16px; margin-top: 20px; }
.help-text { font-size: 12px; line-height: 1.6; }
@media (max-width: 520px) { .login-card { padding: 26px 22px; }.login-modes button { font-size: 14px; }.login-card h2 { font-size: 23px; } }
</style>
