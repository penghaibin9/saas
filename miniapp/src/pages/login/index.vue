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

      <button class="btn btn-primary btn-block login__btn" :class="{ 'is-teacher': tab === 'teacher' }" @click="onFillDemo">
        填入演示账号
      </button>

      <!-- 账号密码登录（真实校验：POST /api/v1/auth/login） -->
      <view class="login__divider"><text class="t-xs t-tertiary">账号密码登录</text></view>
      <input v-model="account.loginName" class="login__input" placeholder="请输入账号" placeholder-class="login__ph" />
      <input v-model="account.password" class="login__input" type="password" password placeholder="请输入密码" placeholder-class="login__ph" />
      <button class="btn btn-block login__btn login__btn--acc" :disabled="accLoading" @click="onAccountLogin">
        {{ accLoading ? '登录中…' : '登 录' }}
      </button>

      <!-- 演示账号（真实账号真实登录；点击仅填入表单，不绕过登录） -->
      <view class="login__demo">
        <text class="login__demo-tt">正式演示 · 演示职业技术学校（数据只读）</text>
        <view class="login__demo-row" @click="fillDemo('student')">
          <text class="login__demo-role">学生</text>
          <text class="login__demo-acc">student</text>
          <text class="login__demo-pwd">密码 123456</text>
        </view>
        <view class="login__demo-row" @click="fillDemo('teacher')">
          <text class="login__demo-role">教师</text>
          <text class="login__demo-acc">teacher</text>
          <text class="login__demo-pwd">密码 123456</text>
        </view>
        <text class="login__demo-tt" style="margin-top:8px;">自由体验 · 体验沙箱学校（随便操作，每晚 0 点重置）</text>
        <view class="login__demo-row" @click="fillDemo('student2')">
          <text class="login__demo-role">学生</text>
          <text class="login__demo-acc">student2</text>
          <text class="login__demo-pwd">密码 123456</text>
        </view>
        <view class="login__demo-row" @click="fillDemo('teacher2')">
          <text class="login__demo-role">教师</text>
          <text class="login__demo-acc">teacher2</text>
          <text class="login__demo-pwd">密码 123456</text>
        </view>
      </view>

      <view class="login__wx" @click="onFillDemo">
        <text class="login__wx-icon">◍</text>
        <text class="t-sm t-secondary">没有账号？先用演示账号体验</text>
      </view>
    </view>

    <!-- 试用咨询（可公开电话；无任何账号密码信息） -->
    <view class="login__trial card">
      <text class="login__trial-tt">想为学校开通正式试用？</text>
      <text class="login__trial-ph">获取试用名额 / 商务咨询：{{ trialPhone }}</text>
      <view class="login__trial-ops">
        <button class="login__trial-btn" @click="copyPhone">复制手机号</button>
        <button class="login__trial-btn login__trial-btn--tel" @click="callPhone">拨打电话</button>
      </view>
    </view>

    <view class="login__foot">
      <text class="t-xs t-tertiary">演示环境数据仅供体验 · 正式开通请联系平台服务顾问</text>
      <text class="t-xs t-tertiary">{{ brand.copyright }}</text>
    </view>
  </view>
</template>

<script>
import { tenantBrandConfig, ROLE } from '@/config'
import { useSessionStore } from '@/stores/session'
import { relaunch, toast } from '@/utils/nav'
import { realRequest, setRefreshToken, setToken } from '@/services/request'

export default {
  data() {
    return {
      brand: tenantBrandConfig,
      tab: 'student',
      trialPhone: '13549666867',
      account: { loginName: '', password: '' },
      accLoading: false
    }
  },
  methods: {
    /** 账号密码登录（真实校验；成功后按角色进入对应端） */
    onAccountLogin() {
      if (!this.account.loginName || !this.account.password) {
        toast('请输入账号与密码')
        return
      }
      this.accLoading = true
      realRequest('/auth/login', {
        method: 'POST',
        auth: false,
        data: { loginName: this.account.loginName.trim(), password: this.account.password }
      }).then((d) => {
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
        relaunch(roleCode === 'STUDENT' ? '/pages/student/home/index' : '/pages/teacher/workbench/index')
      }).catch((e) => {
        toast((e && e.message) || '登录失败，请稍后重试')
      }).finally(() => {
        this.accLoading = false
      })
    },
    /** 点演示账号仅自动填入表单——不绕过登录，仍需点「登 录」走真实 /auth/login */
    fillDemo(login) {
      this.account.loginName = login
      this.account.password = '123456'
      this.tab = login.indexOf('student') === 0 ? 'student' : 'teacher'
    },
    /** 旧「进入演示环境」入口 → 现在只填入对应演示账号，真实登录 */
    onFillDemo() {
      toast('演示环境已改为真实账号登录，已为你填入账号，请点「登 录」')
      this.fillDemo(this.tab === 'student' ? 'student' : 'teacher')
    },
    copyPhone() {
      uni.setClipboardData({ data: this.trialPhone, success: () => toast('手机号已复制') })
    },
    callPhone() {
      // #ifdef H5
      window.location.href = 'tel:' + this.trialPhone
      // #endif
      // #ifndef H5
      uni.makePhoneCall({ phoneNumber: this.trialPhone, fail: () => {} })
      // #endif
    },
    async onLogin() {
      if (this.demoLoading) return
      this.demoLoading = true
      try {
        const session = useSessionStore()
        if (this.tab === 'student') {
          await session.login(ROLE.STUDENT) // 等 token 就绪再进首页，首屏即真实数据
          toast('欢迎回来，' + session.mockUser.name)
          relaunch('/pages/student/home/index')
        } else {
          // 教师：先建立教师会话（默认辅导员身份），再进入身份选择页
          await session.login(ROLE.COUNSELOR)
          relaunch('/pages/role-switch/index')
        }
      } catch (e) {
        if (e && e.biz && (e.code === 403001 || e.code === 403002)) {
          toast('演示登录已关闭，请使用下方账号密码登录')
        } else {
          toast((e && e.message) || '进入失败，请稍后重试')
        }
      } finally {
        this.demoLoading = false
      }
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
.login__btn.is-teacher { background: var(--teacher-600); }
.login__wx { display: flex; align-items: center; justify-content: center; gap: var(--space-2); margin-top: var(--space-4); }
.login__wx-icon { color: var(--success-500); font-size: 20px; }
.login__foot { margin-top: var(--space-6); display: flex; flex-direction: column; align-items: center; gap: 4px; }
.login__divider { display: flex; align-items: center; justify-content: center; margin: var(--space-4) 0 var(--space-2); }
.login__input {
  width: 100%; box-sizing: border-box; height: 44px; margin-top: var(--space-3);
  padding: 0 var(--space-4); border-radius: var(--radius-lg);
  border: 1px solid var(--border-base); background: var(--bg-card); font-size: var(--font-size-md);
}
.login__ph { color: var(--text-tertiary); }
.login__btn--acc { margin-top: var(--space-3); height: 44px; background: var(--bg-card); color: var(--brand-primary); border: 1px solid var(--brand-primary); }
.login__demo { margin-top: var(--space-4); padding: var(--space-3); border-radius: var(--radius-lg); background: var(--primary-50); border: 1px dashed var(--primary-100); }
.login__demo-tt { display: block; font-size: var(--font-size-xs); color: var(--text-secondary); margin-bottom: var(--space-2); }
.login__demo-row { display: flex; align-items: center; gap: var(--space-2); padding: 6px 4px; }
.login__demo-role { font-size: var(--font-size-xs); color: var(--text-tertiary); width: 52px; flex-shrink: 0; }
.login__demo-acc { font-size: var(--font-size-sm); color: var(--brand-primary); font-weight: 600; }
.login__demo-pwd { margin-left: auto; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.login__trial { position: relative; margin-top: var(--space-4); padding: var(--space-4); display: flex; flex-direction: column; gap: var(--space-2); }
.login__trial-tt { font-size: var(--font-size-md); font-weight: 600; color: var(--text-primary); }
.login__trial-ph { font-size: var(--font-size-sm); color: var(--text-secondary); }
.login__trial-ops { display: flex; gap: var(--space-3); margin-top: var(--space-1); }
.login__trial-btn {
  flex: 1; height: 38px; line-height: 38px; font-size: var(--font-size-sm);
  border-radius: var(--radius-md); border: 1px solid var(--primary-100);
  background: var(--primary-50); color: var(--brand-primary); padding: 0;
}
.login__trial-btn::after { border: none; }
.login__trial-btn--tel { background: var(--brand-primary); color: #fff; border-color: var(--brand-primary); }
</style>
