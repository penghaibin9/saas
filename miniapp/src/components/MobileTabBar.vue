<template>
  <view class="mtabbar">
    <view
      v-for="item in tabs"
      :key="item.key"
      class="mtabbar__item"
      :class="{ 'is-active': item.key === active }"
      @click="onTap(item)"
    >
      <view class="mtabbar__icon">
        <text>{{ item.icon }}</text>
        <text v-if="item.badge" class="mtabbar__badge">{{ item.badge > 99 ? '99+' : item.badge }}</text>
      </view>
      <text class="mtabbar__label">{{ item.label }}</text>
    </view>
  </view>
</template>

<script>
/**
 * MobileTabBar 自定义底部导航
 * 因学生端/教师端底部导航不同（一个工程多角色），不使用原生 tabBar。
 * 学生端：首页｜服务｜消息｜我的（日程合入首页卡片，V1 精简）
 * 教师端：工作台｜待办｜消息｜我的（学生入口在工作台/待办内）
 */
import { relaunch } from '@/utils/nav'

const STUDENT_TABS = [
  { key: 'home', label: '首页', icon: '⌂', route: '/pages/student/home/index' },
  { key: 'service', label: '服务', icon: '▦', route: '/pages/student/campus-service/index' },
  { key: 'message', label: '消息', icon: '✉', route: '/pages/student/messages/index' },
  { key: 'me', label: '我的', icon: '☺', route: '/pages/student/me/index' }
]
const TEACHER_TABS = [
  { key: 'workbench', label: '工作台', icon: '⌂', route: '/pages/teacher/workbench/index' },
  { key: 'todo', label: '待办', icon: '✔', route: '/pages/teacher/todos/index' },
  { key: 'message', label: '消息', icon: '✉', route: '/pages/teacher/messages/index' },
  { key: 'me', label: '我的', icon: '☺', route: '/pages/teacher/me/index' }
]

export default {
  name: 'MobileTabBar',
  props: {
    side: { type: String, default: 'student' }, // student | teacher
    active: { type: String, required: true },
    badges: { type: Object, default: () => ({}) } // { message: 3, todo: 8 }
  },
  computed: {
    tabs() {
      const base = this.side === 'teacher' ? TEACHER_TABS : STUDENT_TABS
      return base.map((t) => ({ ...t, badge: this.badges[t.key] || 0 }))
    }
  },
  methods: {
    onTap(item) {
      if (item.key === this.active) return
      relaunch(item.route)
    }
  }
}
</script>

<style scoped>
.mtabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: var(--z-bar);
  display: flex;
  background: var(--bg-card);
  border-top: 1px solid var(--border-light);
  box-shadow: var(--shadow-bar);
  padding-bottom: calc(env(safe-area-inset-bottom));
}
.mtabbar__item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 7px 0 6px;
  color: var(--text-tertiary);
}
.mtabbar__item.is-active { color: var(--brand-primary); }
.mtabbar__icon { position: relative; font-size: 22px; line-height: 1; }
.mtabbar__label { font-size: 11px; }
.mtabbar__badge {
  position: absolute;
  top: -6px;
  right: -12px;
  min-width: 15px;
  height: 15px;
  padding: 0 4px;
  border-radius: var(--radius-full);
  background: var(--danger-500);
  color: #fff;
  font-size: 10px;
  line-height: 15px;
  text-align: center;
}
</style>
