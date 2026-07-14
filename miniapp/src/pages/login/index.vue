<template>
  <view class="login">
    <view class="login__bg" />
    <view class="login__hero">
      <MobileBrandHeader center :side="tab" />
      <text class="login__slogan">{{ brand.slogan }}</text>
    </view>

    <view class="login__card card">
      <!-- 学生 / 教师入口切换 -->
      <view class="login__switch">
        <view
          class="login__switch-item"
          :class="{ 'is-active': tab === 'student' }"
          @click="tab = 'student'"
        >
          <text class="login__switch-icon">🎓</text>
          <text>我是学生</text>
        </view>
        <view
          class="login__switch-item is-teacher"
          :class="{ 'is-active': tab === 'teacher' }"
          @click="tab = 'teacher'"
        >
          <text class="login__switch-icon">🧑‍🏫</text>
          <text>我是老师</text>
        </view>
      </view>

      <view class="login__desc">
        <text class="t-sm t-secondary">{{ tab === 'student'
          ? '学生端：查档案 · 交材料 · 看进度 · 提申请 · 收通知'
          : '教师端：看待办 · 批审批 · 看风险 · 处理异常 · 查学生' }}</text>
      </view>

      <!-- 微信一键登录（仅小程序端；已绑定 openid 直接登录，未绑定引导绑定校园账号） -->
      <!-- #ifdef MP-WEIXIN -->
      <button class="btn btn-block login__wxbtn" :disabled="wxLoading" @click="wechatLogin">
        <text class="login__wxbtn-icon">✔</text>{{ wxLoading ? '登录中…' : '微信一键登录' }}
      </button>
      <!-- #endif -->

      <!-- 账号密码登录（真实校验：POST /api/v1/auth/login） -->
      <view class="login__divider"><text class="t-xs t-tertiary">账号密码登录</text></view>
      <input v-model="account.loginName" class="login__input" placeholder="请输入账号" placeholder-class="login__ph" />
      <input v-model="account.password" class="login__input" type="password" password placeholder="请输入密码" placeholder-class="login__ph" />
      <button class="btn btn-block login__btn login__btn--acc" :disabled="accLoading" @click="onAccountLogin">
        {{ accLoading ? '登录中…' : '登 录' }}
      </button>

    </view>

    <view class="login__foot">
      <text class="t-xs t-tertiary">{{ brand.copyright }}</text>
    </view>

    <!-- 微信首次绑定校园账号 -->
    <view v-if="binding" class="login__bindmask" @click.self="cancelBind">
      <view class="login__bind card">
        <text class="login__bind-tt">首次使用请绑定校园账号</text>
        <text class="login__bind-sub">用学号/工号 + 密码绑定一次，之后微信一键登录免密</text>
        <input v-model="bindForm.loginName" class="login__input" placeholder="学号 / 工号" placeholder-class="login__ph" />
        <input v-model="bindForm.password" class="login__input" type="password" password placeholder="密码" placeholder-class="login__ph" />
        <button class="btn btn-block login__btn--acc" :disabled="bindLoading" @click="submitBind">
          {{ bindLoading ? '绑定中…' : '绑定并登录' }}
        </button>
        <text class="login__bind-cancel" @click="cancelBind">取消</text>
      </view>
    </view>
  </view>
</template>

<script>
import { tenantBrandConfig, ROLE } from '@/config'
import { useSessionStore } from '@/stores/session'
import { studentApi } from '@/services/studentApi'
import { relaunch, toast } from '@/utils/nav'
import { realRequest, setRefreshToken, setToken } from '@/services/request'

export default {
  data() {
    return {
      brand: tenantBrandConfig,
      tab: 'student',
      account: { loginName: '', password: '' },
      accLoading: false,
      // 微信一键登录 + 首次绑定
      wxLoading: false,
      binding: false,
      wxToken: '',
      bindForm: { loginName: '', password: '' },
      bindLoading: false
    }
  },
  methods: {
    /** 登录完成的共享收口：账号密码 / 微信一键 / 微信绑定 三条路径成功后都走这里，保证一致 */
    completeLogin(d) {
      setToken(d.accessToken)
      setRefreshToken(d.refreshToken || '')
      const session = useSessionStore()
      const roleCode = (d.currentRole && d.currentRole.roleCode) || 'STUDENT'
      const map = {
        STUDENT: ROLE.STUDENT, COUNSELOR: ROLE.COUNSELOR,
        GD_MENTOR: ROLE.MENTOR, MENTOR: ROLE.MENTOR,
        INTERN_MENTOR: ROLE.INTERN_MENTOR, EMPLOYMENT: ROLE.EMPLOYMENT,
        ACADEMIC: ROLE.ACADEMIC, COLLEGE_ADMIN: ROLE.COLLEGE_ADMIN
      }
      // skipRealLogin：已持有真实登录令牌，session 只建 UI 会话，绝不再发起任何登录覆盖 token
      session.login(map[roleCode] || (roleCode === 'STUDENT' ? ROLE.STUDENT : ROLE.COUNSELOR),
        { skipRealLogin: true })
      session.applyRealUser(d)
      toast('欢迎，' + d.displayName + (d.tenantName ? '（' + d.tenantName + '）' : ''))
      const goHome = () => relaunch(roleCode === 'STUDENT'
        ? '/pages/student/home/index' : '/pages/teacher/workbench/index')
      // 学生：进入首页前先拉真实档案覆盖展示对象（姓名/学号/班级），避免首页/个人中心显示演示数据
      if (roleCode === 'STUDENT') {
        studentApi.getProfile().then((prof) => session.hydrateStudentProfile(prof)).catch(() => {}).finally(goHome)
      } else {
        goHome()
      }
    },
    /** 账号密码登录（真实校验；成功后按角色进入对应端） */
    onAccountLogin() {
      if (!this.account.loginName || !this.account.password) {
        toast('请输入账号与密码')
        return
      }
      this.accLoading = true
      realRequest('/auth/login', {
        method: 'POST', auth: false,
        data: { loginName: this.account.loginName.trim(), password: this.account.password }
      }).then((d) => this.completeLogin(d))
        .catch((e) => { toast((e && e.message) || '登录失败，请稍后重试') })
        .finally(() => { this.accLoading = false })
    },
    /** 微信一键登录：wx.login 拿 code → /auth/wx-login；已绑定直接登录，未绑定弹绑定表单 */
    wechatLogin() {
      if (this.wxLoading) return
      this.wxLoading = true
      uni.login({
        provider: 'weixin',
        success: (res) => {
          if (!res || !res.code) { toast('微信授权失败，请重试'); this.wxLoading = false; return }
          realRequest('/auth/wx-login', { method: 'POST', auth: false, data: { code: res.code } })
            .then((d) => {
              if (d && d.needBind) {
                this.wxToken = d.wxToken
                this.binding = true
              } else {
                this.completeLogin(d)
              }
            })
            .catch((e) => { toast((e && e.message) || '微信登录失败，请稍后重试') })
            .finally(() => { this.wxLoading = false })
        },
        fail: () => { toast('微信授权失败，请重试'); this.wxLoading = false }
      })
    },
    /** 首次绑定：学号/工号 + 密码 → /auth/wx-bind，绑定 openid 后免密登录 */
    submitBind() {
      if (this.bindLoading) return
      if (!this.bindForm.loginName || !this.bindForm.password) {
        toast('请输入学号/工号与密码')
        return
      }
      this.bindLoading = true
      realRequest('/auth/wx-bind', {
        method: 'POST', auth: false,
        data: { wxToken: this.wxToken, loginName: this.bindForm.loginName.trim(), password: this.bindForm.password }
      }).then((d) => { this.binding = false; this.completeLogin(d) })
        .catch((e) => { toast((e && e.message) || '绑定失败，请检查账号密码') })
        .finally(() => { this.bindLoading = false })
    },
    cancelBind() {
      this.binding = false
      this.wxToken = ''
      this.bindForm = { loginName: '', password: '' }
    }
  }
}
</script>

<style scoped>
.login { min-height: 100vh; padding: 0 var(--page-padding-mobile); position: relative; }
.login__bg {
  position: absolute; top: 0; left: 0; right: 0; height: 320px;
  background: var(--brand-gradient); border-bottom-left-radius: 32px; border-bottom-right-radius: 32px;
}
.login__hero {
  position: relative; padding-top: 88px; padding-bottom: 40px;
  display: flex; flex-direction: column; align-items: center; gap: var(--space-3);
}
.login__hero :deep(.mbh__platform) { color: #fff; }
.login__hero :deep(.mbh__school) { color: rgba(255,255,255,0.9); }
.login__slogan { color: rgba(255,255,255,0.92); font-size: var(--font-size-sm); }
.login__card { position: relative; margin-top: var(--space-2); padding: var(--space-5); }
.login__switch { display: flex; gap: var(--space-3); }
.login__switch-item {
  flex: 1; display: flex; flex-direction: column; align-items: center; gap: var(--space-1);
  padding: var(--space-4) 0; border-radius: var(--radius-lg);
  border: 1px solid var(--border-base); color: var(--text-secondary); font-size: var(--font-size-md);
}
.login__switch-icon { font-size: 26px; }
.login__switch-item.is-active { border-color: var(--brand-primary); background: var(--primary-50); color: var(--brand-primary); }
.login__switch-item.is-teacher.is-active { border-color: var(--teacher-600); background: var(--teacher-50); color: var(--teacher-700); }
.login__desc { margin: var(--space-4) 0; text-align: center; }
.login__btn { margin-top: var(--space-2); height: 46px; }
.login__wxbtn {
  margin-top: var(--space-4); height: 46px; background: var(--success-500); color: #fff;
  display: flex; align-items: center; justify-content: center; gap: var(--space-2); font-size: var(--font-size-md);
}
.login__wxbtn[disabled] { opacity: 0.6; }
.login__wxbtn-icon { font-size: 18px; }
.login__foot { margin-top: var(--space-6); display: flex; flex-direction: column; align-items: center; gap: 4px; }
.login__divider { display: flex; align-items: center; justify-content: center; margin: var(--space-4) 0 var(--space-2); }
.login__input {
  width: 100%; box-sizing: border-box; height: 44px; margin-top: var(--space-3);
  padding: 0 var(--space-4); border-radius: var(--radius-lg);
  border: 1px solid var(--border-base); background: var(--bg-card); font-size: var(--font-size-md);
}
.login__ph { color: var(--text-tertiary); }
.login__btn--acc { margin-top: var(--space-3); height: 44px; background: var(--bg-card); color: var(--brand-primary); border: 1px solid var(--brand-primary); }
.login__bindmask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; padding: var(--page-padding-mobile); z-index: 100;
}
.login__bind { width: 100%; max-width: 340px; padding: var(--space-5); }
.login__bind-tt { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.login__bind-sub { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 6px; }
.login__bind-cancel { display: block; text-align: center; margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--text-tertiary); }
</style>
