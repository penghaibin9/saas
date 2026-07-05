<template>
  <!-- 全局用户胶囊：已登录且非登录页时右上角固定显示，提供退出登录 -->
  <div v-if="user" class="uchip" :class="{ 'is-open': open }">
    <button class="uchip__btn" @click="open = !open">
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
      <button class="uchip__logout" :disabled="loading" @click="doLogout">
        {{ loading ? '正在退出…' : '退出登录' }}
      </button>
    </div>
  </div>
</template>

<script>
/**
 * AppUserChip — 全局登录态胶囊（P12：强制登录后全站唯一退出入口）。
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
      if (tid === '1000000000000000007') return '体验沙箱学校（每晚 0 点重置）'
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
.uchip__btn {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 5px 12px 5px 6px;
  border-radius: 999px;
  border: 1px solid var(--card-b, #e2e8f0);
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  cursor: pointer;
  box-shadow: 0 2px 10px -4px rgba(15, 23, 42, 0.18);
  font: inherit;
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
}
.uchip__name {
  font-size: 12.5px;
  color: var(--t1, #0f172a);
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.uchip__caret {
  font-size: 10px;
  color: var(--t3, #94a3b8);
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
