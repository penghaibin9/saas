<template>
  <!-- 全局用户胶囊：已登录且非登录页时显示，提供退出登录 -->
  <div
    v-if="user"
    class="uchip"
    :class="{ 'is-open': open, 'uchip--topbar': embedded }"
  >
    <!-- 顶栏模式：身份展示 + 始终可见的「退出」按钮 -->
    <template v-if="embedded">
      <div class="uchip__identity">
        <span class="uchip__avatar">{{ (user.realName || '?').slice(0, 1) }}</span>
        <span class="uchip__info">
          <span class="uchip__name">{{ user.realName }}</span>
          <span class="uchip__role">{{ roleLabel }}</span>
        </span>
      </div>
      <button
        class="uchip__exit"
        type="button"
        :disabled="loading"
        :title="loading ? '正在退出…' : '退出当前登录'"
        @click="doLogout"
      >
        {{ loading ? '退出中' : '退出' }}
      </button>
    </template>

    <!-- 悬浮兜底模式：下拉菜单退出 -->
    <template v-else>
      <button
        class="uchip__btn"
        type="button"
        :aria-expanded="open"
        @click="open = !open"
      >
        <span class="uchip__avatar">{{ (user.realName || '?').slice(0, 1) }}</span>
        <span class="uchip__name">{{ user.realName }}</span>
        <span class="uchip__caret">▾</span>
      </button>
      <div v-if="open" class="uchip__menu" @click.stop>
        <div class="uchip__meta">
          <div class="uchip__meta-name">{{ user.realName }}</div>
          <div class="uchip__meta-sub">{{ roleLabel }}</div>
          <div v-if="tenantName" class="uchip__meta-sub">{{ tenantName }}</div>
        </div>
        <button class="uchip__logout" type="button" :disabled="loading" @click="doLogout">
          {{ loading ? '正在退出…' : '退出登录' }}
        </button>
      </div>
    </template>
  </div>
</template>

<script>
/**
 * AppUserChip — 全局登录态胶囊（P12：强制登录后全站唯一退出入口）。
 * embedded=true 时嵌入 BasePortalLayout 顶栏；否则右上角悬浮（仅无顶栏页面兜底）。
 * 退出：调 /auth/logout（jti 拉黑 + 吊销 refresh）→ 清本地令牌 → 回登录页。
 */
import { currentUserFromToken, getToken, logoutRemote } from '@/services/http/client'
import { toast } from '@/utils/toast'

const ROLE_LABEL = {
  SCHOOL_ADMIN: '学校管理员', COLLEGE_ADMIN: '学院管理员', COUNSELOR: '辅导员/指导教师',
  GD_MENTOR: '毕设导师', INTERN_MENTOR: '实习指导教师', ACADEMIC_TEACHER: '教务老师',
  EMPLOYMENT_TEACHER: '就业老师', STUDENT: '学生', PLATFORM_SUPER_ADMIN: '平台超级管理员'
}

export default {
  name: 'AppUserChip',
  props: {
    /** 嵌入顶栏时使用与 bpl-role 一致的内联样式 */
    embedded: { type: Boolean, default: false }
  },
  data() {
    return { open: false, loading: false, tick: 0 }
  },
  computed: {
    user() {
      // tick 用于路由变化后强制重算（token 变化无响应式）
      void this.tick
      if (this.$route && (this.$route.path === '/login' || this.$route.meta?.public)) return null
      if (!getToken()) return null
      return currentUserFromToken()
    },
    roleLabel() {
      return ROLE_LABEL[this.user?.currentRoleCode] || this.user?.currentRoleCode || ''
    },
    tenantName() {
      const tid = this.user?.tenantId
      if (tid === '1000000000000000003') return '演示职业技术学校（只读演示）'
      if (tid === '1000000000000000004') return '沙箱职校（可写体验）'
      if (tid === '1000000000000000004') return '体验沙箱学校（运营平台可恢复）'
      return ''
    }
  },
  watch: {
    $route() {
      this.open = false
      this.tick++
    }
  },
  mounted() {
    document.addEventListener('click', this.onOutside)
  },
  beforeUnmount() {
    document.removeEventListener('click', this.onOutside)
  },
  methods: {
    onOutside(e) {
      if (!this.$el || this.$el === e.target || this.$el.contains?.(e.target)) return
      this.open = false
    },
    async doLogout() {
      if (this.loading) return
      this.loading = true
      try {
        await logoutRemote() // 服务端令牌失效 + 本地清空（离线也会清本地）
        toast.success('已退出登录')
      } finally {
        this.loading = false
        this.open = false
        this.tick++
        this.$router.replace('/login')
      }
    }
  }
}
</script>

<style scoped>
.uchip {
  position: fixed;
  top: 14px;
  right: 18px;
  z-index: 2100;
  font-family: var(--font-family-base);
}
.uchip--topbar {
  position: relative;
  top: auto;
  right: auto;
  z-index: 40;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}
.uchip__identity {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px 4px 5px;
  border-radius: 10px;
  border: 1px solid var(--pri-100, #dbeafe);
  background: rgba(255, 255, 255, 0.85);
}
.uchip__exit {
  height: 35px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid rgba(220, 38, 38, 0.22);
  background: rgba(255, 255, 255, 0.85);
  color: #dc2626;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.12s;
  flex-shrink: 0;
}
.uchip__exit:hover:not(:disabled) {
  background: #fff5f5;
  border-color: #fca5a5;
}
.uchip__exit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.uchip__btn {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 12px 5px 6px;
  border-radius: 999px;
  border: 1px solid var(--card-b, #e2e8f0);
  background: rgba(255, 255, 255, 0.96);
  cursor: pointer;
  box-shadow: 0 2px 10px -4px rgba(15, 23, 42, 0.18);
  font: inherit;
}
.uchip--topbar .uchip__btn {
  gap: 8px;
  padding: 4px 10px 4px 5px;
  border-radius: 10px;
  border: 1px solid var(--pri-100, #dbeafe);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: none;
  box-shadow: none;
  transition: all 0.12s;
}
.uchip--topbar .uchip__btn:hover,
.uchip--topbar.is-open .uchip__btn {
  border-color: var(--glow, #93c5fd);
  box-shadow: 0 0 12px var(--glow, rgba(59, 130, 246, 0.25));
}
.uchip--topbar .uchip__avatar {
  width: 27px;
  height: 27px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: var(--font-weight-semibold, 600);
}
.uchip--topbar .uchip__name {
  font-size: 12px;
  font-weight: var(--font-weight-semibold, 600);
  max-width: 108px;
}
.uchip__avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--btn-p-bg, #2563eb);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}
.uchip__identity .uchip__avatar {
  width: 27px;
  height: 27px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: var(--font-weight-semibold, 600);
}
.uchip__info {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  min-width: 0;
  text-align: left;
}
.uchip__name {
  font-size: 12.5px;
  color: var(--t1, #0f172a);
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.uchip--topbar .uchip__name {
  font-size: 12px;
  font-weight: var(--font-weight-semibold, 600);
  max-width: 108px;
}
.uchip__role {
  color: var(--pri, #2563eb);
  font-size: 10px;
  font-weight: var(--font-weight-medium, 500);
  max-width: 108px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.uchip__caret {
  font-size: 10px;
  color: var(--t3, #94a3b8);
  flex-shrink: 0;
}
.uchip__menu {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  width: 220px;
  background: #fff;
  border: 1px solid var(--card-b, #e2e8f0);
  border-radius: 12px;
  box-shadow: 0 12px 32px -12px rgba(15, 23, 42, 0.25);
  padding: 12px;
}
.uchip--topbar .uchip__menu {
  top: calc(100% + 6px);
}
.uchip__meta-name {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--t1, #0f172a);
}
.uchip__meta-sub {
  margin-top: 3px;
  font-size: 11.5px;
  color: var(--t3, #64748b);
}
.uchip__logout {
  margin-top: 10px;
  width: 100%;
  padding: 8px 0;
  border-radius: 8px;
  border: 1px solid #fecaca;
  background: #fff5f5;
  color: #dc2626;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  font: inherit;
}
.uchip__logout:hover:not(:disabled) {
  background: #fee2e2;
}
.uchip__logout:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
