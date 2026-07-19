<template>
  <view class="login">
    <view class="login__hero">
      <view class="login__orb" />
      <view class="login__logo">
        <image v-if="brand.logo" :src="brand.logo" mode="aspectFit" class="login__logo-img" />
        <text v-else>{{ logoText }}</text>
      </view>
      <text class="login__appname">{{ brand.platformShortName || brand.platformName }}</text>
      <text class="login__appsub">{{ brand.slogan }}</text>
    </view>

    <view class="login__panel">
      <view class="login__feats">
        <view class="login__feat">
          <view class="icon-grid__badge g1">▤</view>
          <text class="login__feat-lb">教务</text>
        </view>
        <view class="login__feat">
          <view class="icon-grid__badge g5">◈</view>
          <text class="login__feat-lb">学工</text>
        </view>
        <view class="login__feat">
          <view class="icon-grid__badge g3">💼</view>
          <text class="login__feat-lb">实习</text>
        </view>
        <view class="login__feat">
          <view class="icon-grid__badge g2">✎</view>
          <text class="login__feat-lb">毕业设计</text>
        </view>
      </view>

      <!-- 迎新批次限时入口：仅批次开放期显示，凭录取通知书编号（学号）登录，批次结束自动隐藏 -->
      <view v-if="orientationBatch.open" class="login__oe" @click="focusOrientationLogin">
        <view class="login__oe-top">
          <text class="login__oe-badge">新生专属</text>
          <text class="login__oe-count">距报到截止 {{ orientationBatch.daysLeft }} 天</text>
        </view>
        <text class="login__oe-title">{{ orientationBatch.batchName }}</text>
        <text class="login__oe-sub">凭录取通知书编号（学号）一键报到</text>
        <view class="login__oe-go">›</view>
      </view>
      <view v-if="orientationBatch.open" class="login__oe-divider"><text class="t-xs t-tertiary">已有账号，直接登录</text></view>

      <view class="login__welcome">
        <text class="login__welcome-tt">欢迎使用{{ brand.platformShortName || brand.platformName }}</text>
        <text class="login__welcome-sub">登录后即可查看课表成绩、实习与毕设进度{{ '\n' }}接收学校通知，掌上办事一站直达</text>
      </view>

      <!-- 微信一键登录（仅小程序端；已绑定 openid 直接登录，未绑定引导绑定校园账号） -->
      <!-- #ifdef MP-WEIXIN -->
      <button class="login__wxbtn" :disabled="wxLoading" @click="wechatLogin">
        {{ wxLoading ? '登录中…' : '微信一键登录' }}
      </button>
      <!-- #endif -->

      <!-- 账号密码登录（真实校验：POST /api/v1/auth/login） -->
      <view class="login__divider"><text class="t-xs t-tertiary">账号密码登录</text></view>
      <input v-model="account.loginName" :focus="loginNameFocus" class="login__input" placeholder="请输入学号 / 工号" placeholder-class="login__ph" />
      <input v-model="account.password" class="login__input" type="password" password placeholder="请输入密码" placeholder-class="login__ph" />
      <button class="login__smsbtn" :disabled="accLoading" @click="onAccountLogin">
        {{ accLoading ? '登录中…' : '登 录' }}
      </button>

      <view class="login__agree" @click="agree = !agree">
        <view class="login__abox" :class="{ 'is-on': agree }">
          <text v-if="agree" class="login__abox-check">✓</text>
        </view>
        <text class="login__agree-tx">我已阅读并同意<text class="login__agree-link">《用户协议》</text>和<text class="login__agree-link">《隐私政策》</text></text>
      </view>
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
      agree: false,
      account: { loginName: '', password: '' },
      accLoading: false,
      // 微信一键登录 + 首次绑定
      wxLoading: false,
      binding: false,
      wxToken: '',
      bindForm: { loginName: '', password: '' },
      bindLoading: false,
      // 迎新批次限时入口（公开接口，登录前查询；查询失败按未开放处理，不阻断正常登录）
      orientationBatch: { open: false, batchName: '', daysLeft: 0 },
      loginNameFocus: false
    }
  },
  onLoad() {
    studentApi.getOrientationBatchStatus().then((d) => {
      if (d && d.open) this.orientationBatch = { open: true, batchName: d.batchName, daysLeft: d.daysLeft }
    }).catch(() => {})
  },
  computed: {
    logoText() {
      return (this.brand.schoolShortName || this.brand.schoolName || '校').slice(0, 1)
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
        ACADEMIC: ROLE.ACADEMIC, COLLEGE_ADMIN: ROLE.COLLEGE_ADMIN,
        GD_DEFENSE_EXPERT: ROLE.GD_DEFENSE_EXPERT
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
      if (!this.agree) { toast('请先勾选并同意《用户协议》和《隐私政策》'); return }
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
      if (!this.agree) { toast('请先勾选并同意《用户协议》和《隐私政策》'); return }
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
    },
    /** 迎新入口卡：新生尚未有正式账号前不支持独立通道登录（需学校预建学号账号），
     * 引导其使用下方账号密码登录，账号即录取通知书上的学号。 */
    focusOrientationLogin() {
      toast('请使用录取通知书上的学号 + 初始密码登录；未收到账号请联系辅导员')
      this.loginNameFocus = false
      this.$nextTick(() => { this.loginNameFocus = true })
    }
  }
}
</script>

<style scoped>
.login { min-height: 100vh; background: var(--bg-page); position: relative; }
.login__hero {
  position: relative; padding: 64px var(--page-padding-mobile) 34px;
  display: flex; flex-direction: column; align-items: center;
  background: var(--brand-gradient); overflow: hidden;
  border-bottom-left-radius: 32px; border-bottom-right-radius: 32px;
}
.login__orb {
  position: absolute; right: -70px; top: -60px; width: 230px; height: 230px; border-radius: var(--radius-full);
  background: radial-gradient(circle at 40% 40%, rgba(255,255,255,.16), transparent 64%);
}
.login__logo {
  position: relative; width: 78px; height: 78px; border-radius: 22px; background: rgba(255,255,255,.96);
  box-shadow: 0 14px 34px -10px rgba(6,30,80,.5); display: flex; align-items: center; justify-content: center;
  font-size: var(--font-size-2xl); font-weight: var(--font-weight-semibold); color: var(--brand-primary); overflow: hidden;
}
.login__logo-img { width: 66px; height: 66px; }
.login__appname { position: relative; margin-top: var(--space-4); font-size: var(--font-size-2xl); font-weight: var(--font-weight-semibold); color: #fff; letter-spacing: .1em; }
.login__appsub { position: relative; margin-top: var(--space-2); font-size: var(--font-size-sm); color: rgba(255,255,255,.85); white-space: pre-line; text-align: center; }
.login__panel {
  position: relative; margin: -22px var(--page-padding-mobile) 0; padding: var(--space-5);
  background: var(--bg-card); border-radius: 22px 22px 26px 26px; box-shadow: var(--shadow-card-float);
}
.login__feats { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-2); }
.login__feat { display: flex; flex-direction: column; align-items: center; gap: var(--space-2); }
.login__feat-lb { font-size: var(--font-size-xs); color: var(--text-secondary); white-space: nowrap; }
.login__oe {
  position: relative; margin-top: var(--space-5); border-radius: var(--radius-lg); padding: var(--space-4);
  background: var(--orientation-gradient); overflow: hidden;
  box-shadow: 0 12px 26px -12px rgba(245,122,30,.6);
}
.login__oe-top { display: flex; align-items: center; gap: var(--space-2); }
.login__oe-badge { font-size: 10px; font-weight: var(--font-weight-semibold); color: var(--orientation-700); background: #fff; padding: 2px 8px; border-radius: var(--radius-full); }
.login__oe-count { margin-left: auto; font-size: var(--font-size-xs); color: #fff; font-weight: var(--font-weight-medium); }
.login__oe-title { display: block; font-size: var(--font-size-lg); color: #fff; font-weight: var(--font-weight-semibold); margin-top: var(--space-2); }
.login__oe-sub { display: block; margin-top: 4px; font-size: var(--font-size-xs); color: rgba(255,255,255,.9); }
.login__oe-go {
  position: absolute; right: var(--space-4); bottom: var(--space-4); width: 30px; height: 30px; border-radius: var(--radius-full);
  background: rgba(255,255,255,.25); color: #fff; display: flex; align-items: center; justify-content: center; font-size: var(--font-size-lg);
}
.login__oe-divider { display: flex; align-items: center; justify-content: center; margin: var(--space-4) 0 0; }
.login__welcome { margin: var(--space-5) 0 var(--space-2); text-align: center; }
.login__welcome-tt { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.login__welcome-sub { display: block; margin-top: var(--space-2); font-size: var(--font-size-xs); color: var(--text-tertiary); line-height: 1.6; }
.login__wxbtn {
  width: 100%; margin-top: var(--space-4); height: 48px; border-radius: var(--radius-lg);
  background: var(--wechat-green); color: #fff; font-size: var(--font-size-md); font-weight: var(--font-weight-semibold);
  border: none; box-shadow: 0 8px 20px -8px rgba(7,193,96,.6);
}
.login__wxbtn[disabled] { opacity: 0.6; }
.login__divider { display: flex; align-items: center; justify-content: center; margin: var(--space-5) 0 var(--space-2); }
.login__input {
  width: 100%; box-sizing: border-box; height: 46px; margin-top: var(--space-3);
  padding: 0 var(--space-4); border-radius: var(--radius-lg);
  border: 1px solid var(--border-base); background: var(--bg-page); font-size: var(--font-size-md);
}
.login__ph { color: var(--text-tertiary); }
.login__smsbtn {
  width: 100%; margin-top: var(--space-3); height: 46px; border-radius: var(--radius-lg);
  background: var(--gray-100); color: var(--brand-primary); font-size: var(--font-size-md); font-weight: var(--font-weight-semibold);
  border: none;
}
.login__smsbtn[disabled] { opacity: 0.6; }
.login__agree { display: flex; align-items: flex-start; gap: var(--space-2); margin-top: var(--space-5); }
.login__abox {
  width: 16px; height: 16px; border-radius: var(--radius-full); border: 1.5px solid var(--border-dark);
  flex-shrink: 0; margin-top: 1px; display: flex; align-items: center; justify-content: center; background: var(--bg-card);
}
.login__abox.is-on { background: var(--wechat-green); border-color: var(--wechat-green); }
.login__abox-check { color: #fff; font-size: 10px; line-height: 1; }
.login__agree-tx { font-size: var(--font-size-xs); color: var(--text-tertiary); line-height: 1.6; }
.login__agree-link { color: var(--text-link); }
.login__foot { padding: var(--space-6) 0; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.login__bindmask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center; padding: var(--page-padding-mobile); z-index: 100;
}
.login__bind { width: 100%; max-width: 340px; padding: var(--space-5); }
.login__bind-tt { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.login__bind-sub { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 6px; }
.login__bind-cancel { display: block; text-align: center; margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--text-tertiary); }
</style>
