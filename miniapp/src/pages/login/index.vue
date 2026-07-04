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

      <button class="btn btn-primary btn-block login__btn" :class="{ 'is-teacher': tab === 'teacher' }" @click="onLogin">
        {{ tab === 'student' ? '进入学生端（模拟登录）' : '进入教师端（模拟登录）' }}
      </button>
      <view class="login__wx" @click="onLogin">
        <text class="login__wx-icon">◍</text>
        <text class="t-sm t-secondary">微信一键登录（演示）</text>
      </view>
    </view>

    <view class="login__foot">
      <text class="t-xs t-tertiary">当前为演示环境 · 数据均为 mock，不接后端</text>
      <text class="t-xs t-tertiary">{{ brand.copyright }}</text>
    </view>
  </view>
</template>

<script>
import { tenantBrandConfig, ROLE } from '@/config'
import { useSessionStore } from '@/stores/session'
import { relaunch, toast } from '@/utils/nav'

export default {
  data() {
    return { brand: tenantBrandConfig, tab: 'student' }
  },
  methods: {
    onLogin() {
      const session = useSessionStore()
      if (this.tab === 'student') {
        session.login(ROLE.STUDENT)
        toast('欢迎回来，' + session.mockUser.name)
        relaunch('/pages/student/home/index')
      } else {
        // 教师：先建立教师会话（默认辅导员身份），再进入身份选择页
        session.login(ROLE.COUNSELOR)
        relaunch('/pages/role-switch/index')
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
</style>
