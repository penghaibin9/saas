<template>
  <view class="mini-login" :class="{ 'is-teacher': isTeacher }">
    <view class="hero">
      <view class="hero__glow" />
      <view class="brand">
        <image v-if="brand.logo" :src="brand.logo" class="brand__logo-img" mode="aspectFit" />
        <text v-else class="brand__logo">{{ logoText }}</text>
        <view><text class="brand__name">{{ platformName }}</text><text class="brand__sub">{{ isTeacher ? '教师与管理人员专用' : '学生个人服务入口' }}</text></view>
      </view>
      <view class="hero__copy">
        <text class="hero__eyebrow">{{ isTeacher ? '移动工作台' : '掌上服务门户' }}</text>
        <text class="hero__title">{{ isTeacher ? '审批、核验与现场处置，\n随时都能完成。' : '办事务、交材料、查结果，\n进度随时看得见。' }}</text>
        <text class="hero__desc">{{ isTeacher ? '登录后按岗位呈现待办、风险提醒、我的学生与移动业务入口。' : '登录后只展示与你本人相关的课表、成绩、申请、实习、毕设与消息。' }}</text>
      </view>
    </view>

    <view class="auth-card">
      <view class="auth-card__head">
        <view><text class="auth-card__title">{{ isTeacher ? '教师端登录' : '学生端登录' }}</text><text class="auth-card__sub">优先使用微信一键登录，首次使用需绑定一次校园账号。</text></view>
        <text class="entry-badge">{{ isTeacher ? '教师端' : '学生端' }}</text>
      </view>

      <!-- #ifdef MP-WEIXIN -->
      <button class="wx-button" :disabled="wxLoading" @click="wechatLogin">{{ wxLoading ? '登录中…' : '微信一键登录' }}</button>
      <!-- #endif -->
      <view class="divider"><view /><text>其他登录方式</text><view /></view>

      <text class="section-title">使用{{ isTeacher ? '工号' : '学号' }}和密码登录</text>
      <input v-model="account.loginName" class="field" :placeholder="isTeacher ? '工号 / 手机号' : '学号 / 手机号'" placeholder-class="field__placeholder" />
      <input v-model="account.password" class="field" type="password" password placeholder="密码" placeholder-class="field__placeholder" />
      <view class="tenant-box" @click="tenantOpen = !tenantOpen">
        <view><text class="tenant-box__title">学校编码</text><text class="tenant-box__hint">仅多校同账号时填写</text></view><text>{{ tenantOpen ? '收起' : '填写' }}</text>
      </view>
      <input v-if="tenantOpen" v-model="account.tenantCode" class="field field--tenant" placeholder="请输入学校编码" placeholder-class="field__placeholder" />

      <button class="account-button" :disabled="accLoading" @click="onAccountLogin">{{ accLoading ? '登录中…' : (isTeacher ? '进入教师工作台' : '进入学生首页') }}</button>
      <view class="agreement" @click="agree = !agree"><view class="agreement__box" :class="{ on: agree }"><text v-if="agree">✓</text></view><text>我已阅读并同意学校提供的用户协议与隐私政策</text></view>
    </view>

    <view v-if="orientationBatch.open" class="orientation-card" @click="focusAccount">
      <text class="orientation-card__badge">迎新入口开放</text>
      <text class="orientation-card__title">{{ orientationBatch.batchName }}</text>
      <text class="orientation-card__desc">距截止 {{ orientationBatch.daysLeft }} 天，使用学校分配的学号登录办理</text>
    </view>

    <view class="feature-row">
      <view v-for="item in features" :key="item.title"><text class="feature-row__mark">{{ item.mark }}</text><text class="feature-row__title">{{ item.title }}</text><text class="feature-row__sub">{{ item.sub }}</text></view>
    </view>
    <view class="role-note"><text>{{ isTeacher ? '登录后进入岗位工作台' : '仅展示本人数据' }}</text><text>{{ isTeacher ? '辅导员、指导教师、教务人员等按角色匹配首页与数据范围。' : '服务事项、材料、进度与消息都与当前账号本人关联。' }}</text></view>
    <text class="switch-entry" @click="switchEntry">切换身份</text>
    <view class="footer"><text>技术支持：湖南跃科信息工程有限公司</text><text>湘ICP备2026031107号</text></view>

    <view v-if="binding" class="bind-mask" @click.self="cancelBind">
      <view class="bind-sheet">
        <view class="bind-sheet__handle" />
        <text class="bind-sheet__title">首次使用请绑定{{ isTeacher ? '教师' : '学生' }}账号</text>
        <text class="bind-sheet__sub">使用{{ isTeacher ? '工号' : '学号' }}或手机号与密码绑定一次，后续即可微信一键登录。</text>
        <input v-model="bindForm.loginName" class="field" :placeholder="isTeacher ? '工号 / 手机号' : '学号 / 手机号'" placeholder-class="field__placeholder" />
        <input v-model="bindForm.password" class="field" type="password" password placeholder="密码" placeholder-class="field__placeholder" />
        <input v-model="bindForm.tenantCode" class="field" placeholder="学校编码（仅多校同账号时填写）" placeholder-class="field__placeholder" />
        <button class="account-button" :disabled="bindLoading" @click="submitBind">{{ bindLoading ? '绑定中…' : '绑定并登录' }}</button>
        <text class="bind-sheet__cancel" @click="cancelBind">取消</text>
      </view>
    </view>
  </view>
</template>

<script>
import { tenantBrandConfig, ROLE } from '@/config'
import { useSessionStore } from '@/stores/session'
import { studentApi } from '@/services/studentApi'
import { clearTokens, realRequest, setRefreshToken, setToken } from '@/services/request'
import { relaunch, toast } from '@/utils/nav'

const ROLE_MAP = {
  STUDENT: ROLE.STUDENT,
  COUNSELOR: ROLE.COUNSELOR,
  GD_MENTOR: ROLE.MENTOR,
  MENTOR: ROLE.MENTOR,
  INTERN_MENTOR: ROLE.INTERN_MENTOR,
  EMPLOYMENT: ROLE.EMPLOYMENT,
  ACADEMIC: ROLE.ACADEMIC,
  COLLEGE_ADMIN: ROLE.COLLEGE_ADMIN,
  GD_DEFENSE_EXPERT: ROLE.GD_DEFENSE_EXPERT
}

export default {
  name: 'MiniLoginAuthPanel',
  props: {
    entry: { type: String, required: true, validator: (value) => ['student', 'teacher'].includes(value) }
  },
  data() {
    return {
      brand: tenantBrandConfig,
      agree: false,
      tenantOpen: false,
      account: { tenantCode: '', loginName: '', password: '' },
      accLoading: false,
      wxLoading: false,
      binding: false,
      wxToken: '',
      bindForm: { tenantCode: '', loginName: '', password: '' },
      bindLoading: false,
      orientationBatch: { open: false, batchName: '', daysLeft: 0 }
    }
  },
  computed: {
    isTeacher() { return this.entry === 'teacher' },
    platformName() { return this.brand.platformShortName || this.brand.platformName || '校园服务平台' },
    logoText() { return (this.brand.schoolShortName || this.brand.schoolName || '校').slice(0, 1) },
    features() {
      return this.isTeacher
        ? [{ mark: '审', title: '移动审批', sub: '待办直达' }, { mark: '核', title: '扫码核验', sub: '迎新与现场' }, { mark: '险', title: '风险处置', sub: '提醒与跟进' }]
        : [{ mark: '办', title: '办事务', sub: '申请与补交' }, { mark: '进', title: '看进度', sub: '节点与结果' }, { mark: '信', title: '收消息', sub: '通知直达' }]
    }
  },
  created() {
    if (!this.isTeacher) {
      studentApi.getOrientationBatchStatus().then((data) => {
        if (data?.open) this.orientationBatch = { open: true, batchName: data.batchName || '', daysLeft: data.daysLeft }
      }).catch(() => {})
    }
  },
  methods: {
    assertEntryRole(data) {
      const roleCode = data?.currentRole?.roleCode || ''
      const matches = this.isTeacher ? roleCode !== 'STUDENT' : roleCode === 'STUDENT'
      if (matches) return true
      clearTokens()
      useSessionStore().logout()
      toast(this.isTeacher ? '该账号为学生账号，请使用学生端小程序。' : '该账号不是学生账号，请使用教师端小程序。')
      return false
    },
    completeLogin(data) {
      if (!this.assertEntryRole(data)) return
      setToken(data.accessToken)
      setRefreshToken(data.refreshToken || '')
      const session = useSessionStore()
      const roleCode = data.currentRole?.roleCode || ''
      const roleKey = ROLE_MAP[roleCode] || ROLE.COUNSELOR
      session.login(roleKey, { skipRealLogin: true })
      session.applyRealUser(data)
      const goHome = () => relaunch(this.isTeacher ? '/pages/teacher/workbench/index' : '/pages/student/home/index')
      if (!this.isTeacher) {
        studentApi.getProfile().then((profile) => session.hydrateStudentProfile(profile)).catch(() => {}).finally(goHome)
      } else {
        goHome()
      }
    },
    onAccountLogin() {
      if (!this.agree) { toast('请先勾选同意用户协议与隐私政策'); return }
      if (!this.account.loginName.trim() || !this.account.password) { toast(`请输入${this.isTeacher ? '工号' : '学号'} / 手机号和密码`); return }
      this.accLoading = true
      realRequest('/auth/login', {
        method: 'POST',
        auth: false,
        data: {
          loginName: this.account.loginName.trim(),
          password: this.account.password,
          tenantCode: this.account.tenantCode.trim() || undefined
        }
      }).then(this.completeLogin).catch((error) => toast(error?.message || '登录失败，请稍后重试')).finally(() => { this.accLoading = false })
    },
    wechatLogin() {
      if (this.wxLoading) return
      if (!this.agree) { toast('请先勾选同意用户协议与隐私政策'); return }
      this.wxLoading = true
      uni.login({
        provider: 'weixin',
        success: (result) => {
          if (!result?.code) { toast('微信授权失败，请重试'); this.wxLoading = false; return }
          realRequest('/auth/wx-login', { method: 'POST', auth: false, data: { code: result.code } })
            .then((data) => {
              if (data?.needBind) {
                this.wxToken = data.wxToken
                this.binding = true
              } else if (data?.needSelectTenant) {
                this.selectWxTenant(data)
              } else {
                this.completeLogin(data)
              }
            })
            .catch((error) => toast(error?.message || '微信登录失败，请稍后重试'))
            .finally(() => { this.wxLoading = false })
        },
        fail: () => { toast('微信授权失败，请重试'); this.wxLoading = false }
      })
    },
    selectWxTenant(data) {
      const accounts = data?.accounts || []
      if (!accounts.length) { toast('未找到可登录的学校账号'); return }
      uni.showActionSheet({
        itemList: accounts.map((item) => `${item.tenantName} · ${item.displayName}`),
        success: ({ tapIndex }) => {
          const selected = accounts[tapIndex]
          if (!selected) return
          realRequest('/auth/wx-select', { method: 'POST', auth: false, data: { wxToken: data.wxToken, tenantCode: selected.tenantCode } })
            .then(this.completeLogin).catch((error) => toast(error?.message || '学校账号登录失败，请重试'))
        }
      })
    },
    submitBind() {
      if (this.bindLoading) return
      if (!this.bindForm.loginName.trim() || !this.bindForm.password) { toast(`请输入${this.isTeacher ? '工号' : '学号'} / 手机号和密码`); return }
      this.bindLoading = true
      realRequest('/auth/wx-bind', {
        method: 'POST',
        auth: false,
        data: {
          wxToken: this.wxToken,
          tenantCode: this.bindForm.tenantCode.trim() || null,
          loginName: this.bindForm.loginName.trim(),
          password: this.bindForm.password
        }
      }).then((data) => { this.binding = false; this.completeLogin(data) })
        .catch((error) => toast(error?.message || '绑定失败，请检查账号密码'))
        .finally(() => { this.bindLoading = false })
    },
    cancelBind() {
      this.binding = false
      this.wxToken = ''
      this.bindForm = { tenantCode: '', loginName: '', password: '' }
    },
    focusAccount() { toast('请使用学校分配的学号和密码登录办理迎新事项') },
    switchEntry() { relaunch('/pages/login/index') }
  }
}
</script>

<style scoped>
.mini-login { min-height: 100vh; padding-bottom: calc(26px + env(safe-area-inset-bottom)); color: #10233f; background: #f4f7fb; }
.hero { position: relative; overflow: hidden; min-height: 284px; padding: calc(28px + env(safe-area-inset-top)) 22px 48px; color: #fff; background: linear-gradient(155deg, #174a78, #1b708f 60%, #1a9a9a); border-radius: 0 0 34px 34px; }.is-teacher .hero { background: linear-gradient(155deg, #163d88, #205bc5 60%, #2877df); }.hero__glow { position: absolute; width: 260px; height: 260px; right: -100px; top: -100px; border: 1px solid rgba(255,255,255,.22); border-radius: 50%; box-shadow: 0 0 0 55px rgba(255,255,255,.035); }
.brand { position: relative; display: flex; align-items: center; gap: 11px; }.brand__logo,.brand__logo-img { display: flex; align-items: center; justify-content: center; width: 38px; height: 38px; border: 1px solid rgba(255,255,255,.32); border-radius: 11px; background: rgba(255,255,255,.14); }.brand view { display: flex; flex-direction: column; }.brand__name { font-size: 14px; font-weight: 600; }.brand__sub { margin-top: 2px; color: rgba(255,255,255,.67); font-size: 10px; }
.hero__copy { position: relative; display: flex; flex-direction: column; min-width: 0; margin-top: 32px; }.hero__eyebrow { font-size: 11px; font-weight: 600; letter-spacing: 2px; opacity: .72; }.hero__title { display: block; max-width: 100%; margin-top: 10px; font-size: 24px; font-weight: 700; line-height: 1.35; white-space: pre-line; word-break: break-all; }.hero__desc { display: block; max-width: 330px; margin-top: 12px; color: rgba(255,255,255,.76); font-size: 12px; line-height: 1.7; white-space: normal; word-break: break-all; }
.auth-card { position: relative; margin: -25px 16px 0; padding: 22px 20px; border: 1px solid #e4eaf1; border-radius: 22px; background: #fff; box-shadow: 0 18px 45px -28px rgba(16,35,63,.45); }.auth-card__head { display: flex; justify-content: space-between; gap: 14px; }.auth-card__head > view { flex: 1; min-width: 0; display: flex; flex-direction: column; }.auth-card__title { font-size: 20px; font-weight: 700; }.auth-card__sub { display: block; margin-top: 6px; color: #718096; font-size: 11px; line-height: 1.5; white-space: normal; word-break: break-all; }.entry-badge { flex: none; align-self: flex-start; padding: 5px 9px; border-radius: 999px; color: #0f766e; background: #eaf8f5; font-size: 10px; }.is-teacher .entry-badge { color: #1f56c9; background: #eef4ff; }
button::after { border: none; }.wx-button,.account-button { display: flex; align-items: center; justify-content: center; height: 47px; margin: 18px 0 0; border: 0; border-radius: 11px; color: #fff; background: #07c160; font-size: 14px; font-weight: 600; }.account-button { background: linear-gradient(135deg, #15948b, #0f766e); }.is-teacher .account-button { background: linear-gradient(135deg, #2f70ea, #1f56c9); }.wx-button[disabled],.account-button[disabled] { opacity: .62; }
.divider { display: flex; align-items: center; gap: 11px; margin: 18px 0; color: #9aa7b8; font-size: 10px; }.divider view { flex: 1; height: 1px; background: #e7ebf0; }.section-title { display: block; margin-bottom: 10px; color: #40536d; font-size: 12px; font-weight: 600; }.field { box-sizing: border-box; width: 100%; height: 46px; margin-top: 10px; padding: 0 13px; border: 1px solid #dce4ed; border-radius: 10px; color: #10233f; background: #f9fbfd; font-size: 13px; }.field__placeholder { color: #9aa7b8; }.field--tenant { margin-top: 8px; }
.tenant-box { display: flex; align-items: center; justify-content: space-between; margin-top: 10px; padding: 10px 12px; border-radius: 10px; background: #f8fafc; color: #536780; font-size: 11px; }.tenant-box view { display: flex; flex-direction: column; }.tenant-box__title { color: #40536d; font-size: 12px; font-weight: 600; }.tenant-box__hint { margin-top: 2px; color: #9aa7b8; font-size: 9px; }
.agreement { display: flex; align-items: flex-start; gap: 8px; margin-top: 14px; color: #7c899a; font-size: 10px; line-height: 1.6; }.agreement__box { flex: none; display: flex; align-items: center; justify-content: center; width: 16px; height: 16px; border: 1px solid #d9e0e8; border-radius: 4px; color: #fff; }.agreement__box.on { border-color: #15948b; background: #15948b; }.is-teacher .agreement__box.on { border-color: #2563eb; background: #2563eb; }
.orientation-card,.role-note { display: flex; flex-direction: column; margin: 12px 16px 0; padding: 15px 17px; border: 1px solid #bfe7df; border-radius: 15px; background: #effaf7; }.orientation-card__badge { color: #0f766e; font-size: 10px; font-weight: 600; }.orientation-card__title { margin-top: 5px; font-size: 14px; font-weight: 700; }.orientation-card__desc { margin-top: 4px; color: #536780; font-size: 10px; }
.feature-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; margin: 14px 16px 0; }.feature-row > view { display: flex; flex-direction: column; align-items: center; padding: 14px 5px; border: 1px solid #e7ecf2; border-radius: 14px; background: #fff; }.feature-row__mark { display: flex; align-items: center; justify-content: center; width: 31px; height: 31px; border-radius: 10px; color: #0f766e; background: #eaf8f5; font-size: 12px; font-weight: 700; }.is-teacher .feature-row__mark { color: #1f56c9; background: #eef4ff; }.feature-row__title { margin-top: 7px; font-size: 11px; font-weight: 600; }.feature-row__sub { margin-top: 2px; color: #8b98aa; font-size: 9px; }
.role-note { border-color: #e7ecf2; background: #fff; }.role-note text:first-child { font-size: 12px; font-weight: 600; }.role-note text:last-child { margin-top: 5px; color: #7f8da0; font-size: 10px; line-height: 1.6; }.switch-entry { display: block; margin: 17px auto 0; color: #536780; text-align: center; font-size: 11px; }.footer { display: flex; flex-direction: column; align-items: center; gap: 3px; margin-top: 17px; color: #9aa7b8; font-size: 9px; }
.bind-mask { position: fixed; z-index: 1000; inset: 0; display: flex; align-items: flex-end; background: rgba(16,35,63,.46); }.bind-sheet { width: 100%; padding: 13px 20px calc(20px + env(safe-area-inset-bottom)); border-radius: 24px 24px 0 0; background: #fff; }.bind-sheet__handle { width: 42px; height: 4px; margin: 0 auto 16px; border-radius: 4px; background: #d9e0e8; }.bind-sheet__title,.bind-sheet__sub,.bind-sheet__cancel { display: block; }.bind-sheet__title { font-size: 18px; font-weight: 700; }.bind-sheet__sub { margin: 7px 0 4px; color: #718096; font-size: 11px; line-height: 1.55; }.bind-sheet__cancel { padding: 15px 0 3px; color: #718096; text-align: center; font-size: 12px; }
@media (min-width: 520px) { .mini-login { width: 430px; min-height: 100vh; margin: 0 auto; box-shadow: 0 0 35px rgba(16,35,63,.12); } }
</style>
