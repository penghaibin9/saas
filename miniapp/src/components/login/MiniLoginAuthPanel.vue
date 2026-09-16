<template>
  <view class="mini-login" :class="{ 'mini-login--teacher': isTeacher }">
    <view class="hero" :style="{ paddingTop: heroTop + 'px' }">
      <image class="hero__art" :src="isTeacher ? '/static/teacher-shell/campus-header.png' : '/static/login/student-campus.png'" mode="aspectFill" />
      <view class="brand">
        <image v-if="brand.logo" :src="brand.logo" class="brand__logo-img" mode="aspectFit" />
        <text v-else class="brand__logo">{{ logoText }}</text>
        <view class="brand__copy"><text class="brand__name">{{ platformName }}</text><text class="brand__sub">{{ isTeacher ? '教师与管理人员专用' : '学生个人服务入口' }}</text></view>
      </view>
      <view class="hero__copy">
        <text class="hero__eyebrow">{{ isTeacher ? '移动工作台' : '掌上服务门户' }}</text>
        <text class="hero__title">{{ isTeacher ? '审批、核验与现场处置，\n随时都能完成。' : '办事务、交材料、查结果，\n进度随时看得见。' }}</text>
        <text class="hero__desc">{{ isTeacher ? '登录后按岗位呈现待办、风险提醒、我的学生与移动业务入口。' : '登录后只展示与你本人相关的课表、成绩、申请、实习、毕设与消息。' }}</text>
      </view>
    </view>

    <view class="auth-card">
      <view class="login-modes" :class="{ 'login-modes--teacher': isTeacher }" role="group" aria-label="登录方式">
        <button v-for="mode in identifierOptions" :key="mode.value" role="button" class="login-mode" :class="{ 'login-mode--active': account.identifierType === mode.value }" :aria-pressed="account.identifierType === mode.value" :disabled="accLoading || wxLoading" @click="onIdentifierTypeChange(mode.value)" plain><text class="login-mode__label">{{ mode.label }}</text></button>
      </view>
      <text class="mode-hint">{{ account.identifierType === 'PHONE' ? '使用本人已验证的手机号与原密码登录' : (isTeacher ? '使用学校开通的工号或统一账号' : '使用学校分配的学号或统一账号') }}</text>
      <view class="login-field">
        <image class="login-field__icon" :src="loginIcon('user', 'gray')" mode="aspectFit" />
        <input :disabled="accLoading || wxLoading" v-model="account.loginName" class="field" :type="account.identifierType === 'PHONE' ? 'tel' : 'text'" :aria-label="account.identifierType === 'PHONE' ? '已验证手机号' : (isTeacher ? '工号或统一账号' : '学号或统一账号')" :placeholder="account.identifierType === 'PHONE' ? '请输入本人已验证的手机号' : (isTeacher ? '请输入工号或统一账号' : '请输入学号或统一账号')" placeholder-class="field__placeholder" />
      </view>
      <view class="login-field">
        <image class="login-field__icon" src="/static/login/lock.png" mode="aspectFit" />
        <input :disabled="accLoading || wxLoading" v-model="account.password" class="field" type="text" :password="!passwordVisible" aria-label="密码" placeholder="密码" placeholder-class="field__placeholder" @confirm="onAccountLogin" />
        <button class="password-toggle" :aria-label="passwordVisible ? '隐藏密码' : '显示密码'" :disabled="accLoading || wxLoading" @click="passwordVisible = !passwordVisible" plain><image class="password-toggle__icon" :src="passwordVisible ? '/static/login/eye.png' : '/static/login/eye-off.png'" mode="aspectFit" /></button>
      </view>
      <button class="forgot-entry" @click="openPasswordReset" plain>忘记密码？短信验证后自助重置</button>
      <view v-if="accountCaptcha.required" class="captcha-row"><input v-model="accountCaptcha.code" class="field captcha-row__input" type="number" maxlength="6" placeholder="图形验证码" /><image class="captcha-row__image" :src="accountCaptcha.image" mode="aspectFill" @click="loadCaptcha('account')" /></view>
      <button class="tenant-box" :disabled="accLoading || wxLoading" :aria-expanded="tenantOpen" @click="tenantOpen = !tenantOpen" plain>
        <image class="login-field__icon" :src="loginIcon('building-bank', 'gray')" mode="aspectFit" />
        <view class="tenant-box__copy"><text class="tenant-box__title">学校编码</text><text class="tenant-box__hint">仅多校同账号时填写</text></view><image class="tenant-box__arrow" :class="{ 'tenant-box__arrow--open': tenantOpen }" :src="loginIcon('chevron-right', 'gray')" mode="aspectFit" />
      </button>
      <input :disabled="accLoading || wxLoading" v-if="tenantOpen" v-model="account.tenantCode" class="field field--tenant" placeholder="请输入学校编码" placeholder-class="field__placeholder" />

      <view class="agreement">
        <button class="agreement-toggle" role="checkbox" :aria-checked="agree" aria-label="同意用户协议与隐私政策" @click="agree = !agree" plain><view class="agreement__box" :class="{ 'agreement__box--checked': agree }"><image class="agreement__check" v-if="agree" :src="loginIcon('check', 'white')" mode="aspectFit" /></view></button>
        <view class="agreement__copy"><text @click="agree = !agree">我已阅读并同意学校提供的</text><text class="agreement__link" @click.stop="openDoc('terms')">《用户协议》</text><text @click="agree = !agree">与</text><text class="agreement__link" @click.stop="openDoc('privacy')">《隐私政策》</text></view>
      </view>
      <button class="account-button" :class="{ 'account-button--teacher': isTeacher, 'is-disabled': accLoading }" :disabled="accLoading || wxLoading" plain @click="onAccountLogin">{{ accLoading ? '登录中…' : (isTeacher ? '进入教师工作台' : '进入学生首页') }}</button>
      <button v-if="!isTeacher" class="newcomer-entry" @click="openOrientationActivation" plain>
        <image class="newcomer-entry__icon" :src="loginIcon('school', 'teal')" mode="aspectFit" />
        <view class="newcomer-entry__content"><text class="newcomer-entry__badge">新生首次使用</text><text class="newcomer-entry__title">录取身份核验并激活账号</text></view>
        <image class="tenant-box__arrow" :src="loginIcon('chevron-right', 'teal')" mode="aspectFit" />
      </button>
    </view>

    <view class="feature-row">
      <view v-for="item in features" :key="item.title" class="feature-row__item"><image class="feature-row__mark" :src="item.icon === 'scan' ? '/static/login/scan.png' : loginIcon(item.icon, isTeacher ? 'blue' : 'teal')" mode="aspectFit" /><text class="feature-row__title">{{ item.title }}</text><text class="feature-row__sub">{{ item.sub }}</text></view>
    </view>
    <button class="role-switch-link" @click="switchEntry" plain><image class="role-switch-icon" src="/static/login/switch-horizontal.png" mode="aspectFit" /><text>切换身份</text></button>
    <view class="footer"><text>技术支持：湖南跃科信息工程有限公司</text><text>湘ICP备2026031107号</text></view>

    <view v-if="binding" class="bind-mask" @click.self="cancelBind">
      <view class="bind-sheet">
        <view class="bind-sheet__handle" />
        <text class="bind-sheet__title">首次使用请绑定{{ isTeacher ? '教师' : '学生' }}账号</text>
        <text class="bind-sheet__sub">使用{{ isTeacher ? '工号' : '学号' }}或手机号与密码绑定一次，后续即可微信一键登录。</text>
        <input v-model="bindForm.loginName" class="field" :placeholder="isTeacher ? '工号 / 手机号' : '学号 / 手机号'" placeholder-class="field__placeholder" />
        <input v-model="bindForm.password" class="field" type="password" password placeholder="密码" placeholder-class="field__placeholder" />
        <view v-if="bindCaptcha.required" class="captcha-row"><input v-model="bindCaptcha.code" class="field captcha-row__input" type="number" maxlength="6" placeholder="图形验证码" /><image class="captcha-row__image" :src="bindCaptcha.image" mode="aspectFill" @click="loadCaptcha('bind')" /></view>
        <input v-model="bindForm.tenantCode" class="field" placeholder="学校编码（仅多校同账号时填写）" placeholder-class="field__placeholder" />
        <view v-if="bindingApprovalRequired">
          <text class="bind-sheet__sub">为防止密码泄露后被他人绑定微信，请由学校通过独立渠道核验身份。不要向任何人提供校园密码。</text>
          <button class="bind-sheet__cancel" plain @click="copyWxBindingRequest">复制本次微信绑定凭证</button>
          <input v-model="bindingApprovalToken" class="field" type="password" password maxlength="128" placeholder="粘贴学校核验后提供的一次性批准码" />
          <text class="bind-sheet__sub">批准码 5 分钟内有效且只能使用一次；只通过学校确认的安全渠道传递，勿发送到群聊。</text>
        </view>
        <button class="account-button" :class="{ 'account-button--teacher': isTeacher, 'is-disabled': bindLoading }" :disabled="bindLoading" plain @click="submitBind">{{ bindLoading ? '绑定中…' : '绑定并登录' }}</button>
        <text class="bind-sheet__cancel" @click="cancelBind">取消</text>
      </view>
    </view>
  </view>
</template>

<script>
import { tenantBrandConfig, roleKeyFromBackendRole } from '@/config'
import { useSessionStore } from '@/stores/session'
import { studentApi } from '@/services/studentApi'
import { clearTokens, commitNewSessionTokens, realRequest } from '@/services/request'
import { go, relaunch, toast } from '@/utils/nav'
import { getLastTenantCode, saveLastTenantCode } from '@/utils/tenantPreference'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { createIdentityCaptcha } from '../../../../shared/identityCaptcha.mjs'
import { getStatusBarHeight } from '@/utils/deviceInfo'
import { shellIcon } from '../student-shell-icons.mjs'

export default {
  name: 'MiniLoginAuthPanel',
  props: {
    entry: { type: String, required: true, validator: (value) => ['student', 'teacher'].includes(value) }
  },
  data() {
    const rememberedTenantCode = getLastTenantCode()
    return {
      brand: tenantBrandConfig,
      agree: false,
      heroTop: 76,
      passwordVisible: false,
      tenantOpen: !!rememberedTenantCode,
      account: { tenantCode: rememberedTenantCode, loginName: '', password: '', identifierType: 'ACCOUNT' },
      loginAlive: true,
      loginAttempt: 0,
      accLoading: false,
      wxLoading: false,
      binding: false,
      wxToken: '',
      bindForm: { tenantCode: rememberedTenantCode, loginName: '', password: '' },
      accountCaptcha: { required: false, id: '', code: '', image: '', nonce: '' },
      bindCaptcha: { required: false, id: '', code: '', image: '', nonce: `mini-bind-${Date.now()}-${Math.random()}` },
      bindLoading: false,
      bindingApprovalRequired: false,
      bindingApprovalToken: ''
    }
  },
  computed: {
    isTeacher() { return this.entry === 'teacher' },
    platformName() { return this.brand.platformShortName || this.brand.platformName || '校园服务平台' },
    logoText() { return (this.brand.schoolShortName || this.brand.schoolName || '校').slice(0, 1) },
    features() {
      return this.isTeacher
        ? [{ icon: 'file-text', title: '移动审批', sub: '待办直达' }, { icon: 'scan', title: '扫码核验', sub: '迎新与现场' }, { icon: 'shield-check', title: '风险处置', sub: '提醒与跟进' }]
        : [{ icon: 'file-text', title: '办事务', sub: '申请与补交' }, { icon: 'clock', title: '看进度', sub: '节点与结果' }, { icon: 'bell', title: '收消息', sub: '通知直达' }]
    },
    identifierOptions() { return [{ label: '账号登录', value: 'ACCOUNT' }, { label: '手机号登录', value: 'PHONE' }] }
  },
  created() {
    this.accountCaptchaFlow = createIdentityCaptcha(this.accountCaptcha, { identity: () => ({ scene: 'PASSWORD_LOGIN', tenantCode: this.account.tenantCode.trim() || undefined, identifierType: this.account.identifierType, identifier: this.account.loginName.trim(), clientType: this.isTeacher ? 'TEACHER_MINI' : 'STUDENT_MINI' }), issue: data => realRequest('/auth/captcha', { method: 'POST', auth: false, data }), error: toast })
    this.loginAlive = true
    // 登录前没有可信学校上下文；批次信息留给认证后的学生服务查询。
  },
  beforeUnmount() { this.invalidateLogin(); this.accountCaptchaFlow.dispose() },
  mounted() {
    // Leave the navigation capsule to WeChat and place content below its actual bounds.
    let capsuleBottom = 0
    try { capsuleBottom = uni.getMenuButtonBoundingClientRect?.().bottom || 0 } catch (_) { /* Other hosts have no capsule. */ }
    this.heroTop = Math.max(getStatusBarHeight() + 44, capsuleBottom + 10)
    // #ifdef H5
    this.heroTop = 24
    // #endif
  },
  watch: {
    'account.loginName': { handler() { this.accountCaptchaFlow?.invalidate() }, flush: 'sync' },
    'account.tenantCode': { handler() { this.accountCaptchaFlow?.invalidate() }, flush: 'sync' },
    'account.identifierType': { handler() { this.accountCaptchaFlow?.invalidate(); this.account.loginName = ''; this.account.password = ''; this.passwordVisible = false }, flush: 'sync' }
  },
  methods: {
    loginIcon(name, tone) { return shellIcon(name, tone) },
    invalidateLogin() {
      this.loginAlive = false
      this.loginAttempt++
      this.accLoading = false
      this.wxLoading = false
      this.bindLoading = false
      this.account.password = ''
      this.passwordVisible = false
      this.cancelBind()
    },
    isLoginCurrent(attempt) { return this.loginAlive && attempt === this.loginAttempt },
    loadCaptcha(target) {
      if (target === 'account') return this.accountCaptchaFlow.load()
      const box = target === 'bind' ? this.bindCaptcha : this.accountCaptcha
      const form = target === 'bind' ? this.bindForm : this.account
      const scene = target === 'bind' ? 'WX_BIND' : 'PASSWORD_LOGIN'
      const identity = target === 'account' ? { identifierType: form.identifierType, identifier: form.loginName.trim() } : { loginName: form.loginName.trim() }
      return realRequest('/auth/captcha', { method: 'POST', auth: false, data: { scene, tenantCode: form.tenantCode.trim() || undefined, ...identity, clientNonce: box.nonce, clientType: this.isTeacher ? 'TEACHER_MINI' : 'STUDENT_MINI' } })
        .then((d) => { box.id = d.captchaId; box.image = d.imageDataUrl; box.code = '' })
        .catch((e) => toast(e?.message || '验证码加载失败'))
    },
    handleCaptchaError(error, target) {
      if (!(String(error?.bizCode || '').startsWith('CAPTCHA_') || error?.details?.captchaRequired)) return false
      const box = target === 'bind' ? this.bindCaptcha : this.accountCaptcha; box.required = true; this.loadCaptcha(target); return true
    },
    assertEntryRole(data) {
      const roleCode = data?.currentRole?.roleCode || ''
      const matches = this.isTeacher ? roleCode !== 'STUDENT' : roleCode === 'STUDENT'
      if (matches) return true
      clearTokens()
      useSessionStore().logout()
      toast(this.isTeacher ? '该账号为学生账号，请使用学生端小程序。' : '该账号不是学生账号，请使用教师端小程序。')
      return false
    },
    completeLogin(data, attempt = this.loginAttempt) {
      if (!this.isLoginCurrent(attempt)) return
      if (!this.assertEntryRole(data)) return
      const roleCode = data.currentRole?.roleCode || ''
      const roleKey = roleKeyFromBackendRole(roleCode)
      // 未识别的角色编码禁止默认落到辅导员：会让该账号看到与自己身份不符的菜单和数据范围，
      // 并在几乎每个业务动作上收到 403，还误导为"系统故障"。失败关闭，提示联系管理员配置。
      if (!roleKey) {
        clearTokens()
        useSessionStore().logout()
        toast('账号角色未配置或暂不支持，请联系学校管理员')
        return
      }
      const session = useSessionStore()
      // 先轮换逻辑会话代次，再清空旧账号投影并建立新身份。这样旧账号的迟到请求、
      // 页面缓存和资料读取不会在 A 退出 / B 登录的临界窗口重新写回界面。
      const generation = commitNewSessionTokens(data.accessToken, data.refreshToken || '')
      session.login(roleKey, { skipRealLogin: true })
      session.applyRealUser(data)
      const stillCurrent = () => this.isLoginCurrent(attempt) && generation === currentSessionGeneration()
      const goHome = () => { if (stillCurrent()) relaunch(this.isTeacher ? '/pages/teacher/workbench/index' : '/pages/student/home/index') }
      // 临时密码仅允许进入既有强制改密路由；提前查询业务资料会被服务器拒绝，
      // 并可能与请求层改密跳转形成重复导航。
      if (session.mustChangePassword) {
        goHome()
        return
      }
      if (!this.isTeacher) {
        studentApi.getProfile()
          .then((profile) => { if (stillCurrent()) session.hydrateStudentProfile(profile) })
          .catch((error) => {
            if (stillCurrent()) toast(error?.message || '已登录，但个人资料暂时加载失败，请在首页重试')
          })
          .finally(goHome)
      } else {
        goHome()
      }
    },
    async onAccountLogin() {
      if (!this.loginAlive || this.accLoading || this.wxLoading || this.bindLoading || this.binding) return
      if (!this.agree) { toast('请先勾选同意用户协议与隐私政策'); return }
      if (!this.account.loginName.trim() || !this.account.password) { toast(`请输入${this.isTeacher ? '工号' : '学号'} / 手机号和密码`); return }
      const attempt = ++this.loginAttempt
      this.accLoading = true
      try {
      await this.accountCaptchaFlow.ensureNonce()
      if (!this.isLoginCurrent(attempt)) return
      if (this.accountCaptcha.required && (!this.accountCaptcha.id || !/^[0-9]{6}$/.test(this.accountCaptcha.code))) { toast('请输入图中 6 位验证码'); return }
      await realRequest('/auth/login', {
        method: 'POST',
        auth: false,
        data: {
          ...(this.account.identifierType === 'PHONE' ? { identifierType: 'PHONE', identifier: this.account.loginName.trim() } : { loginName: this.account.loginName.trim() }),
          password: this.account.password,
          tenantCode: this.account.tenantCode.trim() || undefined,
          clientType: this.isTeacher ? 'TEACHER_MINI' : 'STUDENT_MINI',
          captchaId: this.accountCaptcha.id || undefined, captchaCode: this.accountCaptcha.code || undefined, clientNonce: this.accountCaptcha.nonce
        }
      }).then((data) => {
        if (!this.isLoginCurrent(attempt)) return
        saveLastTenantCode(this.account.tenantCode)
        this.completeLogin(data, attempt)
      }).catch((error) => { if (!this.isLoginCurrent(attempt)) return; this.handleCaptchaError(error, 'account'); toast(error?.message || '登录失败，请稍后重试') }).finally(() => { if (this.isLoginCurrent(attempt)) this.accLoading = false })
      } catch (error) { if (this.isLoginCurrent(attempt)) toast(error?.message || '登录失败，请重新提交') } finally { if (this.isLoginCurrent(attempt)) this.accLoading = false }
    },
    onIdentifierTypeChange(value) { if (!this.accLoading && !this.wxLoading && this.identifierOptions.some(mode => mode.value === value)) this.account.identifierType = value },
    wechatLogin() {
      if (!this.loginAlive || this.wxLoading || this.accLoading || this.bindLoading || this.binding) return
      if (!this.agree) { toast('请先勾选同意用户协议与隐私政策'); return }
      const attempt = ++this.loginAttempt
      this.wxLoading = true
      uni.login({
        provider: 'weixin',
        success: (result) => {
          if (!this.isLoginCurrent(attempt)) return
          if (!result?.code) { toast('微信授权失败，请重试'); this.wxLoading = false; return }
          realRequest('/auth/wx-login', {
            method: 'POST', auth: false,
            data: { code: result.code, clientType: this.isTeacher ? 'TEACHER_MINI' : 'STUDENT_MINI' }
          })
            .then((data) => {
              if (!this.isLoginCurrent(attempt)) return
              if (data?.needBind) {
                this.bindingApprovalRequired = false
                this.bindingApprovalToken = ''
                this.wxToken = data.wxToken
                this.binding = true
              } else if (data?.needSelectTenant) {
                this.selectWxTenant(data, attempt)
              } else {
                this.completeLogin(data, attempt)
              }
            })
            .catch((error) => { if (this.isLoginCurrent(attempt)) toast(error?.message || '微信登录失败，请稍后重试') })
            .finally(() => { if (this.isLoginCurrent(attempt)) this.wxLoading = false })
        },
        fail: () => { if (this.isLoginCurrent(attempt)) { toast('微信授权失败，请重试'); this.wxLoading = false } }
      })
    },
    selectWxTenant(data, attempt = this.loginAttempt) {
      if (!this.isLoginCurrent(attempt)) return
      const accounts = data?.accounts || []
      if (!accounts.length) { toast('未找到可登录的学校账号'); return }
      uni.showActionSheet({
        itemList: accounts.map((item) => `${item.tenantName} · ${item.displayName}`),
        success: ({ tapIndex }) => {
          if (!this.isLoginCurrent(attempt)) return
          const selected = accounts[tapIndex]
          if (!selected) return
          realRequest('/auth/wx-select', {
            method: 'POST', auth: false,
            data: {
              wxToken: data.wxToken, tenantCode: selected.tenantCode,
              clientType: this.isTeacher ? 'TEACHER_MINI' : 'STUDENT_MINI'
            }
          })
            .then((loginData) => {
              if (!this.isLoginCurrent(attempt)) return
              saveLastTenantCode(selected.tenantCode)
              this.completeLogin(loginData, attempt)
            }).catch((error) => { if (this.isLoginCurrent(attempt)) toast(error?.message || '学校账号登录失败，请重试') })
        }
      })
    },
    submitBind() {
      if (this.bindLoading || !this.wxToken) return
      if (!this.bindForm.loginName.trim() || !this.bindForm.password) { toast(`请输入${this.isTeacher ? '工号' : '学号'} / 手机号和密码`); return }
      this.bindLoading = true
      const requestToken = this.wxToken
      const attempt = this.loginAttempt
      realRequest('/auth/wx-bind', {
        method: 'POST',
        auth: false,
        data: {
          wxToken: this.wxToken,
          tenantCode: this.bindForm.tenantCode.trim() || null,
          loginName: this.bindForm.loginName.trim(),
          password: this.bindForm.password,
          bindingApprovalToken: this.bindingApprovalToken.trim() || undefined,
          clientType: this.isTeacher ? 'TEACHER_MINI' : 'STUDENT_MINI',
          captchaId: this.bindCaptcha.id || undefined, captchaCode: this.bindCaptcha.code || undefined, clientNonce: this.bindCaptcha.nonce
        }
      }).then((data) => {
        if (!this.isLoginCurrent(attempt) || !this.binding || this.wxToken !== requestToken) return
        saveLastTenantCode(this.bindForm.tenantCode)
        this.binding = false
        this.wxToken = ''
        this.bindForm.password = ''
        this.bindingApprovalToken = ''
        this.bindingApprovalRequired = false
        this.completeLogin(data, attempt)
      })
        .catch((error) => {
          if (!this.isLoginCurrent(attempt) || !this.binding || this.wxToken !== requestToken) return
          const code = String(error?.bizCode || '')
          if (code === 'WX_BIND_APPROVAL_REQUIRED' || code === 'WX_BIND_APPROVAL_INVALID') {
            this.bindingApprovalRequired = true
            if (code === 'WX_BIND_APPROVAL_INVALID') this.bindingApprovalToken = ''
          }
          this.handleCaptchaError(error, 'bind')
          toast(error?.message || '绑定失败，请检查账号密码')
        })
        .finally(() => { if (this.isLoginCurrent(attempt)) this.bindLoading = false })
    },
    cancelBind() {
      this.binding = false
      this.wxToken = ''
      this.bindingApprovalRequired = false
      this.bindingApprovalToken = ''
      this.bindForm = { tenantCode: getLastTenantCode(), loginName: '', password: '' }
    },
    copyWxBindingRequest() {
      if (!this.wxToken) { toast('本次微信凭证已失效，请取消后重新发起微信登录'); return }
      const requestToken = this.wxToken
      uni.showModal({
        title: '仅交给学校指定核验人员',
        content: '将复制短时微信绑定凭证，不包含校园密码。仅通过学校确认的安全渠道发送，请勿群发或交给陌生人。',
        success: ({ confirm }) => {
          if (!confirm || this.wxToken !== requestToken) return
          uni.setClipboardData({ data: requestToken,
            success: () => toast('已复制，请在凭证有效期内联系学校核验'),
            fail: () => toast('复制失败，请重试') })
        }
      })
    },
    openOrientationActivation() {
      const tenantCode = encodeURIComponent(this.account.tenantCode.trim() || getLastTenantCode())
      go(`/pages/student/orientation/activate/index${tenantCode ? `?tenantCode=${tenantCode}` : ''}`)
    },
    switchEntry() { this.invalidateLogin(); relaunch('/pages/login/index') },
    openPasswordReset() { if (!this.accLoading && !this.wxLoading) go(`/pages/login/reset/index?entry=${this.isTeacher ? 'teacher' : 'student'}&identifierType=${this.account.identifierType}`) },
    // 正文已内置在小程序包内（见 config/legalDocs.js），无需依赖外链和业务域名配置，
    // 因此任何环境下都能打开，不会再出现"未配置链接"的死路。
    openDoc(kind) {
      go(`/pages/common/legal-doc/index?kind=${kind === 'terms' ? 'terms' : 'privacy'}`)
    }
  }
}
</script>

<style scoped>
.mini-login { min-height: 100vh; padding-bottom: calc(18px + env(safe-area-inset-bottom)); color: #172b4d; background: #fff; }
.hero { position: relative; overflow: hidden; padding: 76px 20px 8px; background: #f3fbf9; }
.hero__art { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
.brand { position: relative; display: flex; align-items: center; gap: 10px; }
.brand__logo,.brand__logo-img { display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; flex-shrink: 0; border-radius: 10px; color: #fff; background: #00846b; font-size: 23px; font-weight: 600; }
.mini-login--teacher .brand__logo { background: #1677ff; }
.brand__logo-img { background: #fff; }
.brand__copy { display: flex; flex-direction: column; min-width: 0; }
.brand__name { font-size: 16px; line-height: 1.4; font-weight: 600; }
.brand__sub { margin-top: 2px; color: #62738e; font-size: 12px; line-height: 1.4; }
.hero__copy { position: relative; display: flex; flex-direction: column; min-width: 0; margin-top: 13px; }
.hero__eyebrow { color: #62738e; font-size: 12px; line-height: 1.5; }
.hero__title { display: block; margin-top: 5px; font-size: 20px; font-weight: 700; line-height: 1.4; white-space: pre-line; overflow-wrap: anywhere; }
.hero__desc { display: block; margin-top: 5px; color: #62738e; font-size: 12px; line-height: 1.6; }
.auth-card { position: relative; margin: 0 20px; }
.login-modes { display: flex; margin: 0 0 7px; }
.login-mode { position: relative; flex: 1; min-width: 0; min-height: 44px; margin: 0; padding: 0 8px; display: flex; align-items: center; justify-content: center; border-radius: 0; background: transparent; color: #62738e; font-size: 15px; font-weight: 600; line-height: 1.4; }
.login-mode--active { color: #00846b; }
.login-mode__label { padding: 6px 0; border-bottom: 2px solid transparent; }
.login-mode--active .login-mode__label { border-bottom-color: #00846b; }
.mini-login--teacher .login-mode--active { color: #1677ff; }
.mini-login--teacher .login-mode--active .login-mode__label { border-bottom-color: #1677ff; }
.mode-hint { display: block; color: #62738e; font-size: 12px; line-height: 1.5; margin: 0 0 8px; }
.login-field { display: flex; align-items: center; min-height: 44px; margin-top: 8px; padding-left: 12px; border-radius: 9px; background: #f2f5f9; }
.login-field__icon { width: 21px; height: 21px; flex-shrink: 0; }
.field { box-sizing: border-box; width: 100%; height: 44px; margin-top: 8px; padding: 0 12px; border: 1px solid #dce4ed; border-radius: 9px; color: #172b4d; background: #f2f5f9; font-size: 14px; }
.login-field .field { flex: 1; width: 0; min-width: 0; margin: 0; border: 0; background: transparent; }
.field__placeholder { color: #738098; }
.password-toggle { display: flex; align-items: center; justify-content: center; width: 44px; height: 44px; flex-shrink: 0; margin: 0; padding: 0; background: transparent; }
.password-toggle__icon { width: 20px; height: 20px; }
.forgot-entry { display: flex; align-items: center; justify-content: flex-end; min-height: 36px; margin: 0; padding: 0; color: #00846b; background: transparent; text-align: right; font-size: 12px; line-height: 1.5; }
.mini-login--teacher .forgot-entry { color: #1677ff; }
.tenant-box { display: flex; align-items: center; gap: 10px; box-sizing: border-box; width: 100%; min-height: 40px; margin: 0; padding: 7px 10px; border: 1px solid #e0e7f0; border-radius: 8px; background: #f9fbfd; color: #62738e; text-align: left; font-size: 12px; line-height: 1.5; }
.tenant-box__copy { display: flex; align-items: center; flex: 1; min-width: 0; gap: 8px; flex-wrap: wrap; }
.tenant-box__title { color: #172b4d; font-size: 13px; font-weight: 600; }
.tenant-box__hint { color: #738098; font-size: 11px; }
.tenant-box__arrow { width: 16px; height: 16px; flex-shrink: 0; }
.tenant-box__arrow--open { transform: rotate(90deg); }
.agreement { display: flex; align-items: center; gap: 3px; margin: 3px 0; color: #62738e; font-size: 11px; line-height: 1.7; }
.agreement-toggle { display: flex; justify-content: flex-start; align-items: center; flex-shrink: 0; width: 28px; min-height: 44px; margin: 0; padding: 0; background: transparent; }
.agreement__box { box-sizing: border-box; display: flex; align-items: center; justify-content: center; width: 18px; height: 18px; border: 1px solid #76849c; border-radius: 50%; }
.agreement__check { width: 14px; height: 14px; }
.agreement__box--checked { border-color: #00846b; background: #00846b; }
.mini-login--teacher .agreement__box--checked { border-color: #1677ff; background: #1677ff; }
.agreement__copy { flex: 1; min-width: 0; }
.agreement__link { color: #00846b; }
.mini-login--teacher .agreement__link { color: #1677ff; }
.account-button { display: flex; align-items: center; justify-content: center; min-height: 44px; margin: 0; padding: 8px 12px; border: 0; border-radius: 8px; color: #fff; background: #00846b; font-size: 15px; font-weight: 500; line-height: 1.4; }
.account-button--teacher { background: #1677ff; }
.is-disabled { opacity: .62; }
.newcomer-entry { display: flex; align-items: center; gap: 10px; min-height: 44px; box-sizing: border-box; width: 100%; margin: 8px 0 0; padding: 7px 12px; border: 1px solid #cfede6; border-radius: 8px; background: #f0faf7; text-align: left; line-height: 1.4; }
.newcomer-entry__icon { width: 25px; height: 25px; flex-shrink: 0; }
.newcomer-entry__content { display: flex; flex-direction: column; flex: 1; min-width: 0; }
.newcomer-entry__badge { color: #00846b; font-size: 12px; font-weight: 600; }
.newcomer-entry__title { margin-top: 2px; color: #62738e; font-size: 11px; }
.feature-row { display: flex; margin: 18px 20px 0; }
.feature-row__item { display: flex; flex: 1; min-width: 0; flex-direction: column; align-items: center; padding: 6px 3px; }
.feature-row__mark { width: 24px; height: 24px; }
.feature-row__title { margin-top: 5px; font-size: 12px; font-weight: 600; line-height: 1.5; }
.feature-row__sub { margin-top: 1px; color: #738098; font-size: 11px; line-height: 1.5; }
.role-switch-link { display: flex; align-items: center; justify-content: center; gap: 7px; min-height: 44px; margin: 2px auto 0; padding: 0 12px; background: transparent; color: #172b4d; font-size: 13px; line-height: 1.5; }
.role-switch-icon { width: 20px; height: 20px; }
.footer { display: flex; flex-direction: column; align-items: center; gap: 3px; margin-top: 6px; padding: 0 20px; color: #738098; font-size: 10px; line-height: 1.5; }
.login-mode,.password-toggle,.forgot-entry,.agreement-toggle,.role-switch-link { border: 0; }
.bind-mask { position: fixed; z-index: 1000; inset: 0; display: flex; align-items: flex-end; background: rgba(16,35,63,.46); }
.bind-sheet { box-sizing: border-box; max-height: 90vh; overflow-y: auto; width: 100%; padding: 13px 20px calc(20px + env(safe-area-inset-bottom)); border-radius: 24px 24px 0 0; background: #fff; }
.bind-sheet__handle { width: 42px; height: 4px; margin: 0 auto 16px; border-radius: 4px; background: #d9e0e8; }
.bind-sheet__title,.bind-sheet__sub,.bind-sheet__cancel { display: block; }
.bind-sheet__title { font-size: 18px; font-weight: 700; }
.bind-sheet__sub { margin: 7px 0 4px; color: #62738e; font-size: 12px; line-height: 1.55; }
.bind-sheet__cancel { padding: 15px 0 3px; color: #62738e; text-align: center; font-size: 12px; }
.bind-sheet .account-button { margin-top: 12px; }
.captcha-row { display: flex; align-items: center; gap: 12px; margin-top: 8px; }
.captcha-row__input { flex: 1; min-width: 0; margin: 0; }
.captcha-row__image { width: 130px; height: 44px; border: 1px solid #dbe3ed; border-radius: 8px; background: #f8fafc; }
/* #ifdef H5 */
@media (min-width: 520px) { .mini-login { width: 390px; margin: 0 auto; } }
/* #endif */
</style>
