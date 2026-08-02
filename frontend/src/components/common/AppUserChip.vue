<template>
  <!-- 全局用户胶囊：真实身份切换 + 退出。embedded=true 嵌顶栏。 -->
  <div
    v-if="user"
    class="uchip"
    :class="{ 'is-open': open, 'uchip--topbar': embedded }"
  >
    <div class="uchip__cluster">
      <button
        class="uchip__btn"
        type="button"
        :aria-expanded="open"
        title="查看账号与切换身份"
        @click.stop="toggleOpen"
      >
        <span class="uchip__avatar">{{ (user.realName || '?').slice(0, 1) }}</span>
        <span class="uchip__info">
          <span class="uchip__name">{{ user.realName }}</span>
          <span class="uchip__role">{{ roleLabel || '未识别角色' }}</span>
        </span>
        <span class="uchip__caret" aria-hidden="true">▾</span>
      </button>

      <!-- 常显入口：避免「只显示名字」导致找不到切换 -->
      <button
        class="uchip__switch"
        type="button"
        :disabled="!!switchingId"
        :title="switchHint"
        @click.stop="toggleOpen"
      >
        {{ switchButtonLabel }}
      </button>
    </div>

    <div v-if="open" class="uchip__menu" role="menu" @click.stop>
      <div class="uchip__meta">
        <div class="uchip__meta-name">{{ user.realName }}</div>
        <div class="uchip__meta-sub">{{ roleLabel }}</div>
        <div v-if="scopeLabel" class="uchip__meta-sub">数据范围 · {{ scopeLabel }}</div>
        <div v-if="tenantName" class="uchip__meta-sub">{{ tenantName }}</div>
      </div>

      <div v-if="contextsLoading" class="uchip__hint">正在加载可用身份…</div>
      <div v-else-if="contextsError" class="uchip__hint is-err">{{ contextsError }}</div>
      <template v-else-if="contexts.length">
        <div class="uchip__identity-head">
          <div>
            <strong>身份与工作台</strong>
            <span>{{ user.realName }}共有 {{ contexts.length }} 个可用身份</span>
          </div>
          <span class="uchip__identity-count">{{ contexts.length }}</span>
        </div>
        <button
          v-for="c in contexts"
          :key="c.contextId"
          type="button"
          class="uchip__ctx"
          :class="{ 'is-active': isActive(c), 'is-busy': switchingId === c.contextId }"
          :disabled="!!switchingId || isActive(c)"
          @click="pickContext(c)"
        >
          <span class="uchip__ctx-main">
            <span class="uchip__ctx-name">{{ contextTitle(c) }}</span>
            <span v-if="contextScope(c)" class="uchip__ctx-scope">{{ contextScope(c) }}</span>
          </span>
          <span v-if="isActive(c)" class="uchip__badge">当前工作台</span>
          <span v-else-if="switchingId === c.contextId" class="uchip__badge">切换中</span>
          <span v-else class="uchip__badge is-go">进入工作台 →</span>
        </button>
        <p v-if="contexts.length < 2" class="uchip__hint">
          本账号目前只有一个可用身份，无法切换。需要多身份请在系统管理里给该账号再挂角色。
        </p>
      </template>
      <div v-else class="uchip__hint">未获取到可用身份列表，请刷新后重试</div>

      <button class="uchip__logout" type="button" :disabled="loading || !!switchingId" @click="doLogout">
        {{ loading ? '正在退出…' : '退出登录' }}
      </button>
    </div>

    <button
      v-if="embedded"
      class="uchip__exit"
      type="button"
      :disabled="loading || !!switchingId"
      :title="loading ? '正在退出…' : '退出当前登录'"
      @click="doLogout"
    >
      {{ loading ? '退出中' : '退出' }}
    </button>
  </div>
</template>

<script>
/**
 * AppUserChip — 顶栏账号胶囊。
 * 身份列表：GET /auth/me.contexts；切换：POST /auth/switch-role（真实令牌轮换，非演示假切）。
 * 切换成功后整页刷新，保证菜单/数据范围/工作台按新身份重建。
 */
import {
  currentUserFromToken,
  fetchMyAuthContexts,
  getToken,
  logoutRemote,
  switchAuthContext
} from '@/services/http/client'
import { toast } from '@/utils/toast'

const ROLE_LABEL = {
  SCHOOL_ADMIN: '学校管理员',
  COLLEGE_ADMIN: '学院管理员',
  COUNSELOR: '辅导员',
  GD_MENTOR: '毕设导师',
  INTERN_MENTOR: '实习指导教师',
  ACADEMIC_TEACHER: '任课教师',
  ACADEMIC_ADMIN: '教务老师',
  EMPLOYMENT_TEACHER: '就业老师',
  STUDENT_AFFAIRS_ADMIN: '学工管理员',
  STUDENT_AFFAIRS: '学工管理员',
  PSYCHOLOGY_TEACHER: '心理老师',
  FUNDING_TEACHER: '资助老师',
  YOUTH_LEAGUE: '团委老师',
  DORM_MANAGER: '宿管',
  GRADUATION_ADMIN: '毕设管理员',
  GD_REVIEWER: '毕设评阅人',
  GD_DEFENSE_SECRETARY: '答辩秘书',
  GD_DEFENSE_EXPERT: '答辩专家',
  LEADER: '校领导',
  SYS_ADMIN: '系统管理员',
  SECURITY_AUDITOR: '安全审计',
  ORG_PERSONNEL: '组织人事',
  STUDENT: '学生',
  PLATFORM_SUPER_ADMIN: '平台超级管理员'
}

export default {
  name: 'AppUserChip',
  props: {
    embedded: { type: Boolean, default: false }
  },
  data() {
    return {
      open: false,
      loading: false,
      tick: 0,
      contexts: [],
      activeContextId: '',
      scopeLabel: '',
      contextsLoading: false,
      contextsError: '',
      switchingId: '',
      loadedOnce: false
    }
  },
  computed: {
    user() {
      void this.tick
      if (this.$route && (this.$route.path === '/login' || this.$route.meta?.public)) return null
      if (!getToken()) return null
      return currentUserFromToken()
    },
    roleLabel() {
      const code = this.user?.currentRoleCode
      return ROLE_LABEL[code] || code || ''
    },
    tenantName() {
      const tid = this.user?.tenantId
      if (tid === '1000000000000000003') return '演示职业技术学校（只读演示）'
      if (tid === '1000000000000000007') return '体验沙箱学校（运营平台可恢复）'
      return this.user?.tenantName || ''
    },
    switchHint() {
      if (!this.loadedOnce) return '打开身份列表'
      if (this.contexts.length > 1) return `本账号有 ${this.contexts.length} 个身份，点击切换`
      return '查看当前账号的身份与数据范围'
    },
    switchButtonLabel() {
      if (!this.loadedOnce) return '身份列表'
      return `身份列表 · ${this.contexts.length}`
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
    // 进页就预拉身份，方便一眼知道有没有可切项
    this.loadContexts()
  },
  beforeUnmount() {
    document.removeEventListener('click', this.onOutside)
  },
  methods: {
    onOutside(e) {
      if (!this.$el || this.$el === e.target || this.$el.contains?.(e.target)) return
      this.open = false
    },
    async toggleOpen() {
      this.open = !this.open
      if (this.open) await this.loadContexts()
    },
    async loadContexts() {
      this.contextsLoading = true
      this.contextsError = ''
      try {
        const data = await fetchMyAuthContexts()
        this.contexts = (data.contexts || []).filter((c) => c && c.enabled !== false)
        this.activeContextId = data.activeContextId || this.user?.activeContextId || ''
        const cr = data.currentRole || {}
        this.scopeLabel = cr.scopeLabel || cr.dataScope || ''
        this.loadedOnce = true
      } catch (e) {
        this.contexts = []
        this.contextsError = (e && e.message) || '身份列表加载失败'
      } finally {
        this.contextsLoading = false
        this.tick++
      }
    },
    contextTitle(c) {
      return c.contextName || c.roleName || ROLE_LABEL[c.roleCode || c.contextType] || c.roleCode || c.contextType || c.contextId
    },
    contextScope(c) {
      return c.scopeLabel || ''
    },
    isActive(c) {
      if (!c) return false
      if (this.activeContextId && c.contextId === this.activeContextId) return true
      const code = this.user?.currentRoleCode
      return !!(code && (c.roleCode === code || c.contextType === code) && this.contexts.length === 1)
    },
    async pickContext(c) {
      if (!c || !c.contextId || this.switchingId || this.isActive(c)) return
      this.switchingId = c.contextId
      try {
        const data = await switchAuthContext(c.contextId, 'PC')
        const name = this.contextTitle(c)
        toast.success(`已切换为「${data.contextName || name}」`)
        this.open = false
        // 身份切换后统一进入新身份的工作台，避免停留在旧身份才有权限的业务深页。
        window.location.replace('/workbench')
      } catch (e) {
        toast.error((e && e.message) || '身份切换失败')
        this.switchingId = ''
      }
    },
    async doLogout() {
      if (this.loading) return
      this.loading = true
      try {
        await logoutRemote()
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
.uchip__cluster {
  display: flex;
  align-items: center;
  gap: 4px;
}
.uchip__btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px 4px 5px;
  border-radius: 10px;
  border: 1px solid var(--pri-100, #dbeafe);
  background: rgba(255, 255, 255, 0.85);
  cursor: pointer;
  font: inherit;
  transition: all 0.12s;
}
.uchip:not(.uchip--topbar) .uchip__btn {
  gap: 7px;
  padding: 5px 12px 5px 6px;
  border-radius: 999px;
  border: 1px solid var(--card-b, #e2e8f0);
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 2px 10px -4px rgba(15, 23, 42, 0.18);
}
.uchip--topbar .uchip__btn:hover,
.uchip--topbar.is-open .uchip__btn {
  border-color: var(--glow, #93c5fd);
  box-shadow: 0 0 12px var(--glow, rgba(59, 130, 246, 0.25));
}
.uchip__switch {
  height: 35px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
  flex-shrink: 0;
}
.uchip__switch:hover:not(:disabled) {
  background: #dbeafe;
  border-color: #60a5fa;
}
.uchip__switch:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.uchip__avatar {
  width: 27px;
  height: 27px;
  border-radius: 8px;
  background: var(--btn-p-bg, #2563eb);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}
.uchip__info {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  min-width: 0;
  text-align: left;
}
.uchip__name {
  font-size: 12px;
  font-weight: 600;
  color: var(--t1, #0f172a);
  max-width: 108px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.uchip__role {
  color: var(--pri, #2563eb);
  font-size: 10px;
  font-weight: 500;
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
.uchip__menu {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  width: 300px;
  max-height: min(70vh, 420px);
  overflow: auto;
  background: #fff;
  border: 1px solid var(--card-b, #e2e8f0);
  border-radius: 12px;
  box-shadow: 0 12px 32px -12px rgba(15, 23, 42, 0.25);
  padding: 12px;
  z-index: 50;
}
.uchip:not(.uchip--topbar) .uchip__menu {
  top: calc(100% + 8px);
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
.uchip__sec {
  margin: 12px 0 6px;
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
  letter-spacing: 0.02em;
}
.uchip__identity-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 12px 0 8px;
  padding: 10px 11px;
  border-radius: 10px;
  background: var(--pri-50, #eff6ff);
  border: 1px solid var(--pri-100, #dbeafe);
}
.uchip__identity-head > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}
.uchip__identity-head strong {
  color: var(--t1, #0f172a);
  font-size: 12.5px;
}
.uchip__identity-head span {
  color: var(--t3, #64748b);
  font-size: 10.5px;
}
.uchip__identity-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  border-radius: 9px;
  background: var(--pri, #2563eb);
  color: #fff !important;
  font-size: 14px !important;
  font-weight: 800;
}
.uchip__ctx {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  margin-bottom: 4px;
  border-radius: 8px;
  border: 1px solid #e8eef5;
  background: #f8fafc;
  cursor: pointer;
  font: inherit;
}
.uchip__ctx:hover:not(:disabled) {
  border-color: #93c5fd;
  background: #eff6ff;
}
.uchip__ctx.is-active {
  border-color: #93c5fd;
  background: #eff6ff;
  cursor: default;
}
.uchip__ctx:disabled:not(.is-active) {
  opacity: 0.65;
  cursor: wait;
}
.uchip__ctx-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.uchip__ctx-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}
.uchip__ctx-scope {
  font-size: 11px;
  color: #64748b;
}
.uchip__badge {
  flex-shrink: 0;
  font-size: 11px;
  color: #2563eb;
  font-weight: 600;
}
.uchip__badge.is-go {
  color: #1d4ed8;
}
.uchip__hint {
  margin: 6px 0 0;
  font-size: 11.5px;
  color: #64748b;
  line-height: 1.45;
}
.uchip__hint.is-err {
  color: #dc2626;
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
