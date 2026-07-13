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
        const goHome = () => relaunch(roleCode === 'STUDENT'
          ? '/pages/student/home/index' : '/pages/teacher/workbench/index')
        // 学生：进入首页前先拉真实档案覆盖展示对象（姓名/学号/班级），避免首页/个人中心显示演示数据；
        // 拉取失败也照常进入（首页仍显示真实姓名，学号/班级留空而非假值）
        if (roleCode === 'STUDENT') {
          studentApi.getProfile().then((prof) => session.hydrateStudentProfile(prof)).catch(() => {}).finally(goHome)
        } else {
          goHome()
        }
      }).catch((e) => {
        toast((e && e.message) || '登录失败，请稍后重试')
      }).finally(() => {
        this.accLoading = false
      })
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
</style>
