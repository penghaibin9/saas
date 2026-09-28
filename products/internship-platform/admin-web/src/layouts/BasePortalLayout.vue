<template>
  <div class="ipl-shell">
    <header class="ipl-header">
      <div>
        <strong class="ipl-brand">{{ title }}</strong>
        <span class="ipl-subtitle">{{ subtitle }}</span>
      </div>
      <div class="ipl-user">
        <span v-if="ctx?.currentRole?.roleName">{{ ctx.currentRole.roleName }}</span>
        <span v-if="ctx?.dataScope?.scopeName" class="ipl-scope">{{ ctx.dataScope.scopeName }}</span>
        <button type="button" @click="logout">退出</button>
      </div>
    </header>
    <div class="ipl-body">
      <aside class="ipl-nav" aria-label="岗位实习功能导航">
        <section v-for="m in modules" :key="m.key" class="ipl-nav-group">
          <button type="button" class="ipl-nav-title" :class="{ active: activeModule === m.key }" @click="select(m)">
            {{ m.label }}
          </button>
          <div v-if="activeModule === m.key || moduleContainsRoute(m)" class="ipl-nav-leaves">
            <button
              v-for="item in m.children"
              :key="item.path"
              type="button"
              class="ipl-nav-leaf"
              :class="{ active: isActive(item) }"
              @click="select(item)"
            >{{ item.label }}</button>
          </div>
        </section>
      </aside>
      <main class="ipl-main"><slot /></main>
    </div>
    <footer v-if="$slots.footer" class="ipl-footer"><slot name="footer" /></footer>
  </div>
</template>

<script>
import { getVisibleNavPlan, navRefMatches } from '@/config/navPlan'
import { logoutRemote } from '@/services/http/client'

export default {
  name: 'BasePortalLayout',
  props: {
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    menus: { type: Array, default: () => [] },
    activeKey: { type: String, default: '' },
    hideAside: { type: Boolean, default: false },
    workspace: { type: Boolean, default: false },
    hideGlobalWorkbench: { type: Boolean, default: false },
    workspaceNavigate: { type: Function, default: (path) => path },
    ctx: { type: Object, default: null }
  },
  emits: ['menu-select', 'menu-disabled'],
  computed: {
    modules() {
      return getVisibleNavPlan({
        permissionPatterns: this.ctx?.permissionPatterns || null,
        ctxKey: this.ctx?.ctxKey || ''
      }).find((g) => g.key === 'internship')?.children || []
    },
    activeModule() {
      return this.modules.find((m) => this.moduleContainsRoute(m))?.key || this.modules[0]?.key || ''
    }
  },
  methods: {
    moduleContainsRoute(m) {
      return (m.children || []).some((item) => this.isActive(item))
    },
    isActive(item) {
      if (!item?.path) return false
      if (navRefMatches(this.$route.fullPath, item.path)) return true
      return (item.workspacePaths || []).some((path) => navRefMatches(this.$route.fullPath, path))
    },
    select(item) {
      if (!item?.path || item.disabled) {
        if (item?.disabled) this.$emit('menu-disabled', item)
        return
      }
      this.$emit('menu-select', item)
      const target = this.workspaceNavigate ? this.workspaceNavigate(item.path) : item.path
      const resolved = this.$router.resolve(target)
      if (resolved.fullPath !== this.$route.fullPath) this.$router.push(target).catch(() => {})
    },
    async logout() {
      await logoutRemote()
      this.$router.replace('/login').catch(() => {})
    }
  }
}
</script>

<style scoped>
.ipl-shell { min-height: 100vh; background: #f4f7fb; }
.ipl-header { height: 64px; padding: 0 22px; display: flex; align-items: center; justify-content: space-between; background: #fff; border-bottom: 1px solid #e2e8f0; position: sticky; top: 0; z-index: 30; }
.ipl-brand { font-size: 17px; color: #0f172a; }
.ipl-subtitle { margin-left: 12px; padding-left: 12px; border-left: 1px solid #cbd5e1; color: #64748b; font-size: 14px; }
.ipl-user { display: flex; align-items: center; gap: 10px; color: #475569; font-size: 13px; }
.ipl-scope { padding: 3px 8px; border-radius: 999px; background: #eef2ff; color: #3730a3; }
.ipl-user button { border: 1px solid #cbd5e1; border-radius: 7px; padding: 6px 10px; background: #fff; cursor: pointer; }
.ipl-body { display: grid; grid-template-columns: 218px minmax(0, 1fr); min-height: calc(100vh - 64px); }
.ipl-nav { padding: 16px 10px; background: #0f2746; color: #dbeafe; }
.ipl-nav-group + .ipl-nav-group { margin-top: 6px; }
.ipl-nav-title, .ipl-nav-leaf { width: 100%; border: 0; text-align: left; cursor: pointer; }
.ipl-nav-title { padding: 10px 12px; border-radius: 8px; background: transparent; color: #dbeafe; font-weight: 700; }
.ipl-nav-title.active { background: rgba(255,255,255,.12); color: #fff; }
.ipl-nav-leaves { padding: 5px 0 5px 10px; display: grid; gap: 3px; }
.ipl-nav-leaf { padding: 8px 10px; border-radius: 7px; background: transparent; color: #a9c8eb; font-size: 13px; }
.ipl-nav-leaf:hover, .ipl-nav-leaf.active { color: #fff; background: rgba(37,99,235,.42); }
.ipl-main { min-width: 0; padding: 0; }
.ipl-footer { padding: 12px 22px; border-top: 1px solid #e2e8f0; background: #fff; }
</style>
