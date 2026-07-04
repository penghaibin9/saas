<template>
  <div class="base-portal-layout thw" :class="themeClass">
    <!-- 顶栏 56px 玻璃：品牌 → ⌘K 搜索 → 主题 → 环境标 → 数据范围镜片 → 通知 → 角色胶囊 -->
    <header class="bpl-topbar">
      <div class="bpl-brand">
        <slot name="logo">
          <span class="bpl-logo">{{ logoText }}</span>
        </slot>
        <span class="bpl-brand__info">
          <span class="bpl-brand__nm">{{ brandLine1 }}</span>
          <span v-if="brandLine2" class="bpl-brand__sch">{{ brandLine2 }}</span>
        </span>
      </div>
      <div class="bpl-cmdk">
        <svg class="bpl-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="11" cy="11" r="7" />
          <path d="M21 21l-4.3-4.3" />
        </svg>
        <span class="bpl-cmdk__tx">搜索学生、功能…</span>
        <kbd>⌘K</kbd>
      </div>
      <div class="bpl-top-r">
        <div class="bpl-thdots" title="主题皮肤 themePreference">
          <span
            v-for="t in themeOptions"
            :key="t.key"
            class="bpl-thdot"
            :class="['bpl-thdot--' + t.key, { 'is-on': theme === t.key }]"
            :title="t.label"
            @click="setTheme(t.key)"
          />
        </div>
        <span v-if="envLabel" class="bpl-env">{{ envLabel }}</span>
        <span v-if="scopeName" class="bpl-scope">
          <svg class="bpl-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z" />
          </svg>
          数据范围 · {{ scopeName }}
        </span>
        <slot name="header-right" />
        <span v-if="ctx" class="bpl-bell">
          <svg class="bpl-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <path d="M18 8a6 6 0 10-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.7 21a2 2 0 01-3.4 0" />
          </svg>
          <span v-if="pendingCount" class="bpl-bell__b">{{ pendingCount }}</span>
        </span>
        <div v-if="roleName" class="bpl-role">
          <span class="bpl-role__av">{{ userChar }}</span>
          <span class="bpl-role__info">
            <span class="bpl-role__nm">{{ userName }}</span>
            <span class="bpl-role__ur">{{ roleName }}</span>
          </span>
        </div>
        <slot name="user" />
      </div>
    </header>

    <div class="bpl-body">
      <!-- 左一级 82px 深蓝渐变图标轨（菜单数据消费 config/adminMenu.js，本组件不写死业务菜单） -->
      <aside v-if="railItems.length" class="bpl-rail">
        <div
          v-for="item in railItems"
          :key="item.key"
          class="bpl-rail__item"
          :class="{ 'is-on': item.key === railActiveKey }"
          @click="onRailSelect(item)"
        >
          <span v-if="item.badge" class="bpl-rail__badge">{{ item.badge }}</span>
          <svg class="bpl-rail__ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <path v-for="(d, i) in railIcon(item.key)" :key="i" :d="d" />
          </svg>
          <span class="bpl-rail__lb">{{ item.label }}</span>
        </div>
        <div class="bpl-rail__sp" />
      </aside>

      <!-- 左二级 196px 浅色业务导航（分组小标题 + 计数徽标）；无 ctx 时回退为旧版单栏菜单 -->
      <aside class="bpl-aside" :class="{ 'is-hidden': hideAside, 'bpl-aside--subnav': !!ctx }">
        <slot name="menu">
          <div v-if="ctx && subtitle" class="bpl-aside__head">
            <div class="bpl-aside__title">{{ subtitle }}</div>
            <div v-if="scopeName" class="bpl-aside__meta">{{ scopeName }}</div>
          </div>
          <nav class="bpl-menu">
            <template v-for="item in menus" :key="item.key">
              <div v-if="item.section" class="bpl-menu__sec">{{ item.section }}</div>
              <a
                class="bpl-menu__item"
                :class="{ 'is-active': item.key === activeKey, 'is-disabled': item.disabled }"
                :title="item.disabled ? item.disabledTip || '即将上线' : ''"
                href="javascript:void(0)"
                @click="onSelect(item)"
              >
                <AppIcon v-if="item.icon" :name="item.icon" class="bpl-menu__icon" />
                <span class="bpl-menu__label">{{ item.label }}</span>
                <span v-if="item.badge" class="bpl-menu__badge">{{ item.badge }}</span>
                <span v-if="item.disabled" class="bpl-menu__soon">即将上线</span>
                <span v-if="item.readonly" class="bpl-menu__readonly">只读</span>
              </a>
            </template>
          </nav>
        </slot>
      </aside>

      <!-- 内容区：业务页面必须渲染在此容器内（router-view 由使用方放入默认插槽） -->
      <main class="bpl-main">
        <slot />
      </main>
    </div>

    <footer v-if="$slots.footer" class="bpl-footer">
      <slot name="footer" />
    </footer>
  </div>
</template>

<script>
import { AppIcon } from '@/components/ui'
import { getVisibleAdminMenu, findActiveMenu } from '@/config/adminMenu'

/**
 * BasePortalLayout 门户壳基座（PC-UI v2 · 视觉母版 docs/ui/pc-ui-v2/00-基准-管理端v6三主题.dc.html）
 * 依据 V2.1 §6.2：StudentPortalLayout 与 EnterprisePortalLayout 必须基于本组件复用，
 * 禁止复制布局壳改名，禁止企业导师端使用 AdminLayout。
 *
 * 铁律：本组件不写死任何业务菜单；一级图标轨数据消费 config/adminMenu.js 的
 * getVisibleAdminMenu(ctx)（由使用方以可选 prop `ctx` 注入角色上下文）。
 *
 * Props（V1 全部保留，只新增可选项）:
 *  - title:    门户名称（无 ctx 时作为品牌第一行回退显示）
 *  - subtitle: 副标题 / 模块名（有 ctx 时作为左二级导航标题）
 *  - menus:    [{ key, label, icon?, path?, badge?, section?, disabled?, readonly? }]
 *  - activeKey: 当前激活菜单 key
 *  - hideAside: 是否隐藏侧边菜单
 *  - ctx:      （新增，可选）模块上下文 { tenantBrandConfig, currentRole, dataScope }，
 *              注入后启用一级图标轨 / 数据范围镜片 / 角色胶囊；品牌名来自 tenantBrandConfig
 *  - productName:（新增，可选）产品名，默认「高校学生全生命周期管理平台」
 * Emits:
 *  - menu-select(item)：菜单/图标轨点击（使用方在此做 router.push(item.path)）
 * Slots:
 *  - logo / header-right / user / menu / default / footer（与 V1 完全一致）
 */

/* 一级图标轨图标（视觉资源，非业务配置；键与 adminMenu 分组 key 对应） */
const RAIL_ICONS = {
  home: ['M3 11l9-7 9 7', 'M5 10v10h14V10'],
  workbench: ['M9 11l3 3 8-8', 'M20 12v6a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h9'],
  'student-center': ['M9 8a3.2 3.2 0 100 .01', 'M3.5 20c0-3 2.5-5 5.5-5s5.5 2 5.5 5', 'M16 8h5M16 12h5'],
  practice: ['M3 7h18v13H3z', 'M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2'],
  'data-center': ['M4 20V10M10 20V4M16 20v-8M22 20H2'],
  system: [
    'M12 15a3 3 0 100-6 3 3 0 000 6z',
    'M19 12a7 7 0 00-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 00-2-1.2L14 3h-4l-.4 2.6a7 7 0 00-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 005 12a7 7 0 00.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 002 1.2L10 21h4l.4-2.6a7 7 0 002-1.2l2.4 1 2-3.4-2-1.6z'
  ],
  platform: ['M7 18a4.5 4.5 0 01-.4-9 6 6 0 0111.7 1.7A3.9 3.9 0 0117 18H7z']
}

const THEME_OPTIONS = [
  { key: 'e', label: '皓白极简' },
  { key: 'f', label: '墨白极简' },
  { key: 'a', label: '学院蓝' },
  { key: 'b', label: '商务蓝' },
  { key: 'd', label: '护眼绿' },
  { key: 'c', label: '雅灰' }
]

function readThemePreference() {
  try {
    return window.localStorage.getItem('themePreference') || 'a'
  } catch {
    return 'a'
  }
}

export default {
  name: 'BasePortalLayout',
  components: { AppIcon },
  props: {
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    menus: { type: Array, default: () => [] },
    activeKey: { type: String, default: '' },
    hideAside: { type: Boolean, default: false },
    /* v2 新增（可选）：角色上下文，注入后启用统一壳的一级图标轨与身份区 */
    ctx: { type: Object, default: null },
    /* v2 新增（可选）：产品名（命名规范：高校学生全生命周期管理平台） */
    productName: { type: String, default: '高校学生全生命周期管理平台' }
  },
  emits: ['menu-select', 'menu-disabled'],
  data() {
    return {
      theme: readThemePreference(),
      themeOptions: THEME_OPTIONS
    }
  },
  computed: {
    themeClass() {
      return this.theme ? 'th-' + this.theme : ''
    },
    envLabel() {
      return import.meta.env && import.meta.env.DEV ? 'DEV' : ''
    },
    schoolName() {
      return (this.ctx && this.ctx.tenantBrandConfig && this.ctx.tenantBrandConfig.schoolName) || ''
    },
    brandLine1() {
      return this.ctx ? this.productName : this.title
    },
    brandLine2() {
      return this.ctx ? this.schoolName : this.subtitle
    },
    logoText() {
      const src = this.schoolName || this.title || ''
      return src ? src.charAt(0) : '校'
    },
    scopeName() {
      const ds = this.ctx && this.ctx.dataScope
      return (ds && (ds.scopeName || ds.scopeLabel || ds.name)) || ''
    },
    userName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.userName) || ''
    },
    userChar() {
      return this.userName ? this.userName.charAt(0) : ''
    },
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    pendingCount() {
      return (this.ctx && this.ctx.pendingCount) || 0
    },
    railItems() {
      if (!this.ctx) return []
      const items = [{ key: 'home', label: '工作台', path: '/' }]
      for (const group of getVisibleAdminMenu(this.ctx)) {
        const first = group.children[0]
        items.push({
          key: group.key,
          label: group.key === 'workbench' && first ? first.label : group.label,
          path: first ? first.path : '',
          badge: group.badge
        })
      }
      return items
    },
    railActiveKey() {
      const path = this.$route ? this.$route.path : ''
      if (!path || path === '/') return 'home'
      return findActiveMenu(path).groupKey
    }
  },
  methods: {
    railIcon(key) {
      return RAIL_ICONS[key] || RAIL_ICONS.home
    },
    setTheme(key) {
      this.theme = key
      try {
        window.localStorage.setItem('themePreference', key)
      } catch {
        /* 忽略隐私模式下的存储失败 */
      }
    },
    onRailSelect(item) {
      if (!item.path) return
      this.$emit('menu-select', { key: item.key, label: item.label, path: item.path })
    },
    onSelect(item) {
      if (item.disabled) {
        this.$emit('menu-disabled', item)
        return
      }
      this.$emit('menu-select', item)
    }
  }
}
</script>

<style scoped>
.base-portal-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-page);
  font-family: var(--font-family-base);
  color: var(--text-primary);
}
.bpl-ic {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

/* ── 顶栏 56px 玻璃 ── */
.bpl-topbar {
  height: 56px;
  flex-shrink: 0;
  background: var(--topbar-bg);
  backdrop-filter: blur(18px);
  border-bottom: 1px solid var(--topbar-bd);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 10px;
  position: relative;
  z-index: 30;
}
.bpl-brand {
  display: flex;
  align-items: center;
  gap: 9px;
  flex-shrink: 0;
}
.bpl-logo {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: var(--btn-p-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: var(--font-weight-bold);
  font-size: 13px;
  box-shadow: 0 4px 12px -4px var(--glow);
  flex-shrink: 0;
}
.bpl-brand__info {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
  min-width: 0;
}
.bpl-brand__nm {
  font-size: 12.5px;
  font-weight: var(--font-weight-bold);
  white-space: nowrap;
}
.bpl-brand__sch {
  font-size: 10.5px;
  color: var(--t3);
  white-space: nowrap;
}
.bpl-cmdk {
  flex: 1;
  min-width: 120px;
  max-width: 430px;
  height: 34px;
  margin: 0 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  border-radius: 12px;
  background: rgba(237, 242, 250, 0.85);
  border: 1px solid var(--card-b);
  color: var(--t3);
  font-size: 12.5px;
  cursor: text;
  transition: all 0.12s;
  white-space: nowrap;
  overflow: hidden;
}
.bpl-cmdk:hover {
  border-color: var(--glow);
  background: #fff;
  box-shadow: 0 0 0 3px var(--pri-bg);
}
.bpl-cmdk__tx {
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
.bpl-cmdk kbd {
  margin-left: auto;
  font-family: inherit;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 5px;
  background: #fff;
  border: 1px solid var(--card-b);
  color: var(--t3);
}
.bpl-top-r {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  flex-shrink: 0;
}
.bpl-thdots {
  display: flex;
  gap: 5px;
  align-items: center;
  padding: 0 4px;
}
.bpl-thdot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
  transition: all 0.12s;
}
.bpl-thdot.is-on {
  border-color: #fff;
  box-shadow:
    0 0 0 1.5px var(--pri),
    0 0 8px var(--glow);
}
.bpl-thdot--a {
  background: linear-gradient(135deg, #60a5fa, #2f6bff);
}
.bpl-thdot--b {
  background: linear-gradient(135deg, #3e86de, #0d2a55);
}
.bpl-thdot--c {
  background: linear-gradient(135deg, #8a9ac8, #5b6c9e);
}
.bpl-thdot--d {
  background: linear-gradient(135deg, #5ca894, #3e8e7e);
}
.bpl-thdot--e {
  background: linear-gradient(135deg, #f8fafc, #cbd5e1);
  border: 1px solid #e2e8f0;
}
.bpl-thdot--f {
  background: linear-gradient(135deg, #4b5563, #111827);
}
.bpl-env {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: var(--font-weight-semibold);
  background: rgba(217, 119, 6, 0.1);
  color: var(--warning-700);
  letter-spacing: 0.4px;
  border: 1px solid rgba(217, 119, 6, 0.25);
}
.bpl-scope {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 18px;
  background: var(--pri-bg);
  border: 1px solid var(--pri-100);
  font-size: 11.5px;
  color: var(--pri);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}
.bpl-scope .bpl-ic {
  width: 13px;
  height: 13px;
}
.bpl-bell {
  position: relative;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--t3);
  cursor: pointer;
  transition: all 0.12s;
}
.bpl-bell:hover {
  background: var(--pri-bg);
  color: var(--pri);
}
.bpl-bell .bpl-ic {
  width: 17px;
  height: 17px;
}
.bpl-bell__b {
  position: absolute;
  top: 1px;
  right: 1px;
  min-width: 15px;
  height: 15px;
  border-radius: 8px;
  background: #ef4444;
  color: #fff;
  font-size: 9px;
  font-weight: var(--font-weight-bold);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
  line-height: 1;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
}
.bpl-role {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px 4px 5px;
  border-radius: 10px;
  border: 1px solid var(--pri-100);
  background: rgba(255, 255, 255, 0.85);
  cursor: default;
  transition: all 0.12s;
}
.bpl-role:hover {
  border-color: var(--glow);
  box-shadow: 0 0 12px var(--glow);
}
.bpl-role__av {
  width: 27px;
  height: 27px;
  border-radius: 8px;
  background: var(--btn-p-bg);
  color: #fff;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--font-weight-semibold);
  flex-shrink: 0;
}
.bpl-role__info {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}
.bpl-role__nm {
  color: var(--t1);
  font-size: 12px;
  font-weight: var(--font-weight-semibold);
  white-space: nowrap;
}
.bpl-role__ur {
  color: var(--pri);
  font-size: 10px;
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}

/* ── 主体 ── */
.bpl-body {
  flex: 1;
  display: flex;
  min-height: 0;
  overflow: hidden;
}

/* ── 左一级 82px 深蓝渐变图标轨 ── */
.bpl-rail {
  width: 82px;
  flex-shrink: 0;
  background: var(--rail-bg);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 0 12px;
  gap: 4px;
  position: relative;
  z-index: 10;
  overflow-y: auto;
  scrollbar-width: none;
}
.bpl-rail::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  right: 0;
  width: 1px;
  background: var(--rail-edge);
}
.bpl-rail__item {
  width: 64px;
  padding: 9px 0 7px;
  border-radius: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  color: var(--rail-tx);
  cursor: pointer;
  font-size: 10px;
  font-weight: var(--font-weight-medium);
  transition: all 0.12s;
  position: relative;
  flex-shrink: 0;
}
.bpl-rail__item:hover {
  color: var(--rail-hover-tx);
  background: var(--rail-hover-bg);
}
.bpl-rail__item.is-on {
  color: var(--rail-on-tx);
  background: var(--rail-on-bg);
  box-shadow: var(--rail-on-ring);
  font-weight: var(--font-weight-semibold);
}
.bpl-rail__ic {
  width: 19px;
  height: 19px;
}
.bpl-rail__lb {
  white-space: nowrap;
}
.bpl-rail__badge {
  position: absolute;
  top: 5px;
  right: 9px;
  min-width: 14px;
  height: 14px;
  border-radius: 7px;
  background: #f87171;
  color: #fff;
  font-size: 8.5px;
  font-weight: var(--font-weight-bold);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 3px;
  box-shadow: 0 0 8px rgba(248, 113, 113, 0.7);
}
.bpl-rail__sp {
  flex: 1;
}

/* ── 左二级业务导航 ── */
.bpl-aside {
  width: 240px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-right: 1px solid var(--dv);
  padding: var(--space-4) var(--space-3);
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--t4) transparent;
}
.bpl-aside--subnav {
  width: 196px;
  background: var(--bg-sidebar);
  padding: 16px 12px;
}
.bpl-aside.is-hidden {
  display: none;
}
.bpl-aside__head {
  padding: 2px 8px 12px;
  border-bottom: 1px solid var(--dv);
  margin-bottom: 8px;
}
.bpl-aside__title {
  font-size: 15px;
  font-weight: var(--font-weight-bold);
  letter-spacing: -0.01em;
}
.bpl-aside__meta {
  font-size: 11px;
  color: var(--t3);
  margin-top: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.bpl-menu {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.bpl-menu__sec {
  font-size: 10.5px;
  font-weight: var(--font-weight-bold);
  letter-spacing: 0.08em;
  color: var(--t3);
  padding: 12px 8px 5px;
  text-transform: uppercase;
}
.bpl-menu__item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 8px 10px;
  border-radius: 9px;
  font-size: 13px;
  color: var(--t2);
  font-weight: var(--font-weight-medium);
  text-decoration: none;
  transition:
    background 0.15s ease,
    color 0.15s ease;
  position: relative;
}
.bpl-menu__item:hover {
  background: var(--pri-bg);
  color: var(--t1);
}
.bpl-menu__item.is-active {
  background: var(--pri-bg);
  color: var(--pri);
  font-weight: var(--font-weight-semibold);
}
.bpl-menu__item.is-disabled {
  color: var(--text-disabled);
  cursor: not-allowed;
}
.bpl-menu__item.is-disabled:hover {
  background: transparent;
  color: var(--text-disabled);
}
.bpl-menu__soon {
  font-size: 10px;
  color: var(--t3);
  background: var(--gray-100);
  border-radius: var(--radius-sm);
  padding: 0 4px;
  line-height: 16px;
  white-space: nowrap;
}
.bpl-menu__icon {
  width: 15px;
  font-size: 14px;
  text-align: center;
  flex-shrink: 0;
  line-height: 1;
}
.bpl-menu__label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bpl-menu__badge {
  min-width: 17px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--err-l);
  color: var(--err);
  font-size: 10px;
  font-weight: var(--font-weight-bold);
  line-height: 16px;
  text-align: center;
}
.bpl-menu__readonly {
  font-size: var(--font-size-xs);
  color: var(--info);
  background: var(--info-l);
  border-radius: var(--radius-sm);
  padding: 0 var(--space-1);
}

/* ── 内容区（径向光晕 + 网格纹理） ── */
.bpl-main {
  flex: 1;
  min-width: 0;
  padding: 20px 24px 30px;
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: var(--t4) transparent;
  background:
    radial-gradient(1100px 380px at 12% -8%, rgba(96, 165, 250, 0.14), transparent 65%),
    radial-gradient(900px 400px at 95% 0%, rgba(147, 197, 253, 0.1), transparent 60%),
    linear-gradient(rgba(37, 99, 235, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(37, 99, 235, 0.03) 1px, transparent 1px),
    var(--bg);
  background-size:
    auto,
    auto,
    34px 34px,
    34px 34px,
    auto;
}
.bpl-main::-webkit-scrollbar {
  width: 5px;
}
.bpl-main::-webkit-scrollbar-thumb {
  background: var(--t4);
  border-radius: 3px;
}
.bpl-footer {
  background: var(--bg-card);
  border-top: 1px solid var(--card-b);
  padding: var(--space-3) var(--page-padding-pc);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}

@media (max-width: 1100px) {
  .bpl-thdots {
    display: none;
  }
}
@media (max-width: 1040px) {
  .bpl-scope {
    display: none;
  }
}
@media (max-width: 900px) {
  .bpl-rail,
  .bpl-aside {
    display: none;
  }
  .bpl-main {
    padding: var(--page-padding-mobile);
  }
  .bpl-topbar {
    padding: 0 var(--page-padding-mobile);
  }
  .bpl-brand__sch {
    display: none;
  }
}
</style>
