<template>
  <view class="mtabbar" :class="{ 'mtabbar--student': side === 'student', 'mtabbar--teacher': side === 'teacher' }">
    <view
      v-for="item in tabs"
      :key="item.key"
      class="mtabbar__item"
      :class="{ 'is-active': item.key === selectedKey }"
      @click="onTap(item)"
    >
      <view class="mtabbar__icon">
        <MobileShellIcon :name="studentIcon(item.key)" :tone="item.key === selectedKey ? 'blue' : 'gray'" :size="25" />
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
 * 教师端：工作台｜服务大厅｜消息｜我的（完整待办保留在工作台内）
 */
import { relaunch } from '@/utils/nav'

const STUDENT_TABS = [
  { key: 'home', label: '首页', icon: '⌂', route: '/pages/student/home/index' },
  { key: 'service', label: '服务大厅', icon: '▦', route: '/pages/student/campus-service/index' },
  { key: 'message', label: '消息', icon: '✉', route: '/pages/student/messages/index' },
  { key: 'me', label: '我的', icon: '☺', route: '/pages/student/me/index' }
]
const TEACHER_TABS = [
  { key: 'workbench', label: '工作台', icon: '⌂', route: '/pages/teacher/workbench/index' },
  { key: 'service', label: '服务大厅', icon: '▦', route: '/pages/teacher/services/index' },
  { key: 'message', label: '消息', icon: '✉', route: '/pages/teacher/messages/index' },
  { key: 'me', label: '我的', icon: '☺', route: '/pages/teacher/me/index' }
]

export default {
  name: 'MobileTabBar',
  props: {
    side: { type: String, default: 'student' }, // student | teacher
    active: { type: String, required: true },
    badges: { type: Object, default: () => ({}) }, // { message: 3, todo: 8 }
    beforeNavigate: { type: Function, default: null }
  },
  computed: {
    selectedKey() { return this.side === 'teacher' && this.active === 'todo' ? 'workbench' : this.active === 'messages' ? 'message' : this.active },
    tabs() {
      const base = this.side === 'teacher' ? TEACHER_TABS : STUDENT_TABS
      return base.map((t) => ({ ...t, badge: this.badges[t.key] || (this.side === 'teacher' && t.key === 'workbench' ? this.badges.todo : 0) || 0 }))
    }
  },
  methods: {
    studentIcon(key) { return { home: 'home', workbench: 'home', service: 'layout-grid', message: 'mail', me: 'user' }[key] },
    async onTap(item) {
      if (item.key === this.active) return
      if (this.beforeNavigate && !await this.beforeNavigate()) return
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
.mtabbar--student, .mtabbar--teacher { box-shadow: none; border-top-color: #edf0f5; }
.mtabbar--student .mtabbar__item, .mtabbar--teacher .mtabbar__item { min-height: 58px; padding: 8px 0 7px; box-sizing: border-box; gap: 4px; }
.mtabbar--student .mtabbar__label, .mtabbar--teacher .mtabbar__label { font-size: 12px; line-height: 17px; }
.mtabbar--student .mtabbar__item.is-active, .mtabbar--teacher .mtabbar__item.is-active { color: #1671f8; }
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
