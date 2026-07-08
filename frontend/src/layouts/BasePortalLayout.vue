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
      <div class="bpl-search">
        <!-- ① 学生搜索框（仅管理端有 ctx 时显示；后端按数据范围返回） -->
        <div v-if="ctx" class="bpl-cmdk bpl-cmdk--stu" :class="{ 'is-open': stuOpen }">
          <svg class="bpl-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.3-4.3" />
          </svg>
          <input
            ref="stuInput"
            v-model="stuQuery"
            class="bpl-cmdk__input"
            type="text"
            placeholder="搜学生（姓名 / 学号）"
            @focus="stuOpen = true"
            @keydown.enter.prevent="pickFirstStu"
            @keydown.esc.prevent="stuOpen = false"
            @blur="closeStuSoon"
          />
          <div v-if="stuOpen && stuQuery.trim().length >= 2" class="bpl-cmdk__panel" @mousedown.prevent>
            <template v-if="stuResults.length">
              <div class="bpl-cmdk__grp">学生</div>
              <a
                v-for="s in stuResults"
                :key="'stu-' + s.id"
                class="bpl-cmdk__opt"
                href="javascript:void(0)"
                @click="pickStu(s)"
              >
                <span class="bpl-cmdk__opt-lb">{{ s.name }}</span>
                <span class="bpl-cmdk__opt-pt">{{ s.no }}{{ s.sub ? ' · ' + s.sub : '' }}</span>
              </a>
            </template>
            <div v-else-if="stuSearching" class="bpl-cmdk__loading">正在搜索学生…</div>
            <div v-else class="bpl-cmdk__empty">未找到「{{ stuQuery }}」相关学生</div>
          </div>
        </div>

        <!-- ② 功能 / 帮助搜索框（功能页面 + 帮助文档 + 业务流程图） -->
        <div class="bpl-cmdk bpl-cmdk--fn" :class="{ 'is-open': fnOpen }">
          <svg class="bpl-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.3-4.3" />
          </svg>
          <input
            ref="fnInput"
            v-model="fnQuery"
            class="bpl-cmdk__input"
            type="text"
            placeholder="搜功能、帮助文档、流程图"
            @focus="fnOpen = true"
            @keydown.enter.prevent="pickFirstFn"
            @keydown.down.prevent="moveFn(1)"
            @keydown.up.prevent="moveFn(-1)"
            @keydown.esc.prevent="fnOpen = false"
            @blur="closeFnSoon"
          />
          <kbd>⌘K</kbd>
          <div v-if="fnOpen" class="bpl-cmdk__panel" @mousedown.prevent>
            <template v-if="fnResults.length">
              <template v-for="grp in fnGrouped" :key="grp.kind">
                <div class="bpl-cmdk__grp">{{ grp.kind }}</div>
                <a
                  v-for="r in grp.items"
                  :key="r._idx"
                  class="bpl-cmdk__opt"
                  :class="{ 'is-active': r._idx === fnActive, 'is-disabled': r.disabled }"
                  href="javascript:void(0)"
                  @click="pickFn(r)"
                  @mouseenter="fnActive = r._idx"
                >
                  <span class="bpl-cmdk__opt-lb">{{ r.label }}</span>
                  <span v-if="r.badge" class="bpl-planbadge" :class="'bpl-planbadge--' + (r.disabled ? 'planned' : 'partial')">{{ r.badge }}</span>
                </a>
              </template>
            </template>
            <div v-else class="bpl-cmdk__empty">未找到「{{ fnQuery }}」相关功能或帮助</div>
          </div>
        </div>
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
        <!-- 顶栏用户身份/退出由全局 AppUserChip 统一承载（见 App.vue），
             此处不再渲染重复的角色胶囊，避免与右上角悬浮胶囊重影。 -->
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
        <!-- navPlan 驱动的「完整二级 + 三级」施工地图（12 个业务模块 layout：有 ctx、无自定义 #menu）。
             implemented/partial 可点；planned 灰色「待施工」不可点，点击仅 toast；角色可见性见 isPlannerView。 -->
        <nav v-if="ctx && !$slots.menu" class="bpl-tree">
          <div class="bpl-submods__label">{{ planGroupLabel }}</div>
          <template v-for="m in planMods" :key="m.key">
            <!-- 二级模块（有 children 显示展开箭头） -->
            <a
              class="bpl-submods__item bpl-tree__mod"
              :class="{ 'is-active': m.key === planActiveModKey, 'is-disabled': m.disabled && !m.children.length }"
              href="javascript:void(0)"
              @click="onTreeMod(m)"
            >
              <span
                v-if="m.children.length"
                class="bpl-tree__caret"
                :class="{ 'is-open': isExpanded(m.key) }"
              >▸</span>
              <span v-else class="bpl-tree__caret bpl-tree__caret--sp" />
              <span class="bpl-submods__lb" :title="m.label">{{ m.label }}</span>
              <span v-if="m.badge && m.status !== 'planned'" class="bpl-planbadge" :class="'bpl-planbadge--' + m.status">{{ m.badge }}</span>
            </a>
            <!-- 三级页面（展开时缩进显示） -->
            <div v-if="m.children.length && isExpanded(m.key)" class="bpl-tree__leaves">
              <a
                v-for="leaf in m.children"
                :key="leafKey(m, leaf)"
                class="bpl-menu__item bpl-tree__leaf"
                :class="{ 'is-active': isLeafActive(m, leaf), 'is-disabled': leaf.disabled }"
                href="javascript:void(0)"
                @click="onPlanLeaf(leaf, m)"
              >
                <span class="bpl-menu__label" :title="leaf.label">{{ leaf.label }}</span>
                <span v-if="leaf.badge && leaf.status !== 'planned'" class="bpl-planbadge" :class="'bpl-planbadge--' + leaf.status">{{ leaf.badge }}</span>
              </a>
            </div>
          </template>
        </nav>
        <slot v-else name="menu">
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
import { getVisibleAdminMenu, findActiveMenu, SEARCH_ALIASES } from '@/config/adminMenu'
import { searchHelp } from '@/config/helpContent'
import { getVisibleNavPlan, findActiveInPlan, searchNavPlan, navRefMatches } from '@/config/navPlan'
import { toast } from '@/utils/toast'

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
  /* 6 个新一级模块图标（PC-NAV-6MODULE-REGROUP）；旧 key 保留以兼容任何遗留引用 */
  home: ['M3 11l9-7 9 7', 'M5 10v10h14V10'],
  workbench: ['M3 11l9-7 9 7', 'M5 10v10h14V10'], // 工作台 · home
  'student-affairs': ['M9 8a3.2 3.2 0 100 .01', 'M3.5 20c0-3 2.5-5 5.5-5s5.5 2 5.5 5', 'M16 8h5M16 12h5'], // 学工中心 · users
  'academic-affairs': ['M12 6.5C10.5 5 8 4.5 4 5v13c4-.5 6.5 0 8 1.5', 'M12 6.5C13.5 5 16 4.5 20 5v13c-4-.5-6.5 0-8 1.5'], // 教务中心 · book-open
  graduation: ['M22 10L12 5 2 10l10 5 10-5z', 'M6 12v5c0 2 2.7 3.5 6 3.5s6-1.5 6-3.5v-5'], // 毕业设计中心 · graduation-cap
  internship: ['M3 7h18v13H3z', 'M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2'], // 岗位实习中心 · briefcase
  /* 旧分组 key（重组前）保留，避免遗留引用取不到图标 */
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
      themeOptions: THEME_OPTIONS,
      /* ① 学生搜索框（后端按数据范围返回） */
      stuQuery: '',
      stuOpen: false,
      stuResults: [],
      stuSearching: false,
      stuTimer: null,
      stuSeq: 0,
      stuBlurTimer: null,
      /* ② 功能 / 帮助搜索框（功能页面 + 帮助文档 + 业务流程图） */
      fnQuery: '',
      fnOpen: false,
      fnActive: 0,
      fnBlurTimer: null,
      /* 侧栏树：各二级模块的展开状态 { modKey: true/false }（未记录时默认展开当前路由所属二级） */
      expandedMods: {},
      /* 三级菜单被点击的唯一 leafKey（用于同 path 多叶子的点击反馈/高亮跟随；路由切换后失效自动回退路由匹配） */
      clickedLeafKey: ''
    }
  },
  computed: {
    /** 当前角色可见的一级模块 key 集合（用于把搜索结果限制在有权限的范围内） */
    visibleGroupKeys() {
      return new Set(getVisibleAdminMenu(this.ctx).map((g) => g.key))
    },
    /** 功能/帮助搜索结果：旧名兼容 + 完整目录(navPlan) + 帮助文档/流程图；planned 显示「待施工」不跳转 */
    fnResults() {
      const inScope = (p) => {
        const gk = findActiveMenu(p).groupKey
        return !gk || this.visibleGroupKeys.has(gk)
      }
      const q = this.fnQuery.trim().toLowerCase()
      const out = []
      // 旧一级名兼容（数据中心/学生中心/教学实践/权限与流程 → 新归属）
      const pool = SEARCH_ALIASES.filter((a) => inScope(a.path))
      const matched = !q
        ? pool.slice(0, 4)
        : pool.filter(
            (a) =>
              a.label.toLowerCase().includes(q) ||
              a.keywords.some((k) => {
                const kk = k.toLowerCase()
                return kk.includes(q) || q.includes(kk)
              })
          )
      matched.forEach((a) => out.push({ kind: '功能/页面', label: a.label, to: a.path, disabled: false, badge: '' }))
      // 完整目录（navPlan）：implemented/partial 可跳；planned/未开通「待施工/未开通」不跳
      if (q) {
        for (const r of searchNavPlan(this.fnQuery)) {
          const kind =
            r.status === 'planned' ? '规划 · 待施工'
              : r.status === 'partial' ? '页面 · 待补强'
                : r.status === 'unauthorized' ? '未开通' : '功能/页面'
          out.push({ kind, label: r.trail, to: r.disabled ? null : r.path, disabled: r.disabled, badge: r.badge })
        }
      }
      // 帮助文档 / 业务流程图
      searchHelp(q).forEach((h) => out.push({ kind: h.kind, label: h.title, to: '/admin/help?topic=' + h.id, disabled: false, badge: '' }))
      // 去重（label+to）后截断
      const seen = new Set()
      const dedup = out.filter((r) => {
        const k = r.label + '|' + r.to
        if (seen.has(k)) return false
        seen.add(k)
        return true
      })
      return dedup.slice(0, 16).map((r, i) => ({ ...r, _idx: i }))
    },
    /** 按类别分组，供面板分区渲染 */
    fnGrouped() {
      const order = ['功能/页面', '页面 · 待补强', '规划 · 待施工', '未开通', '帮助文档', '业务流程图']
      const map = {}
      this.fnResults.forEach((r) => {
        ;(map[r.kind] = map[r.kind] || []).push(r)
      })
      return order.filter((k) => map[k]).map((k) => ({ kind: k, items: map[k] }))
    },
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
      // 一级图标轨 = adminMenu.js 的 6 个一级模块（工作台已作为第一个分组，
      // 其首叶「我的工作台」指向 /；不再额外合成 home，避免出现两个「工作台」）。
      if (!this.ctx) return []
      return getVisibleAdminMenu(this.ctx).map((group) => {
        const first = group.children[0]
        return {
          key: group.key,
          label: group.label,
          path: first ? first.path : '',
          badge: group.badge
        }
      })
    },
    railActiveKey() {
      // 依路径定位一级模块；根路径 / 命中「工作台」首叶，未知路径兜底高亮工作台。
      const path = this.$route ? this.$route.path : ''
      return findActiveMenu(path).groupKey || 'workbench'
    },
    /* ── navPlan 驱动的侧栏（完整二级/三级施工地图；planned 灰色不可点） ── */
    isPlannerView() {
      // 管理员/开发者视角可见 planned/unauthorized；普通业务角色只见 implemented/partial
      if (import.meta.env && import.meta.env.DEV) return true
      const rt =
        (this.ctx && this.ctx.currentRole && (this.ctx.currentRole.roleType || this.ctx.currentRole.roleCode)) || ''
      return rt === 'SCHOOL_ADMIN' || rt === 'PLATFORM' || rt === 'PLATFORM_SUPER_ADMIN'
    },
    currentPath() {
      return this.$route ? this.$route.path : ''
    },
    currentNavRef() {
      if (!this.$route) return ''
      return this.$route.fullPath.split('#')[0]
    },
    planActive() {
      return findActiveInPlan(this.currentPath, this.currentNavRef)
    },
    planGroup() {
      const gk = this.railActiveKey
      return getVisibleNavPlan({ includePlanned: this.isPlannerView }).find((g) => g.key === gk) || null
    },
    planGroupLabel() {
      return this.planGroup ? this.planGroup.label : ''
    },
    planMods() {
      return this.planGroup ? this.planGroup.children : []
    },
    planActiveModKey() {
      return this.planActive.modKey || (this.planMods[0] && this.planMods[0].key) || ''
    },
    /* 按当前路由定位应高亮的唯一三级叶子：取「最具体」匹配（路径越长越具体、带 query 精确匹配优先），
       避免形如 /admin/graduation 的看板叶子用前缀规则抢占所有子页；同 path 多叶子取其中第一个。 */
    routeActiveLeafKey() {
      let best = { key: '', score: -1 }
      for (const m of this.planMods) {
        for (const leaf of (m.children || [])) {
          if (leaf.disabled || !leaf.path) continue
          if (!navRefMatches(this.currentNavRef, leaf.path)) continue
          const score = leaf.path.length + (leaf.path.indexOf('?') >= 0 ? 1000 : 0)
          if (score > best.score) best = { key: m.key + '/' + leaf.label, score }
        }
      }
      return best.key
    },
    /* 生效高亮：优先「用户刚点且该叶子仍在当前路由上」的 leafKey（点击反馈/同 path 兄弟切换），
       否则回退路由首个匹配叶子；始终只有一个叶子高亮。 */
    effectiveActiveLeafKey() {
      const ck = this.clickedLeafKey
      if (ck) {
        for (const m of this.planMods) {
          for (const leaf of (m.children || [])) {
            if (m.key + '/' + leaf.label === ck) {
              return leaf.path && navRefMatches(this.currentNavRef, leaf.path) ? ck : this.routeActiveLeafKey
            }
          }
        }
      }
      return this.routeActiveLeafKey
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
    },
    /* ── ② 功能 / 帮助搜索框 ── */
    pickFn(r) {
      if (!r) return
      if (r.disabled) {
        toast.info(r.badge === '未开通' ? '该功能未开通' : '该功能待施工，敬请期待')
        return
      }
      if (!r.to) return
      this.fnQuery = ''
      this.fnOpen = false
      if (this.$router && r.to !== this.$route.fullPath) this.$router.push(r.to)
    },
    pickFirstFn() {
      const list = this.fnResults
      if (list.length) this.pickFn(list[this.fnActive] || list[0])
    },
    moveFn(delta) {
      const n = this.fnResults.length
      if (!n) return
      this.fnActive = (this.fnActive + delta + n) % n
    },
    closeFnSoon() {
      this.fnBlurTimer = setTimeout(() => {
        this.fnOpen = false
      }, 150)
    },
    onGlobalKeydown(e) {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault()
        this.fnOpen = true
        this.$nextTick(() => this.$refs.fnInput && this.$refs.fnInput.focus())
      }
    },
    /* ── ① 学生搜索框（后端按数据范围过滤，越权搜不到） ── */
    queueStuSearch(q) {
      clearTimeout(this.stuTimer)
      const kw = (q || '').trim()
      if (!this.ctx || kw.length < 2) {
        this.stuResults = []
        this.stuSearching = false
        return
      }
      this.stuSearching = true
      this.stuTimer = setTimeout(() => this.doStuSearch(kw), 320)
    },
    async doStuSearch(kw) {
      const seq = ++this.stuSeq
      try {
        // 动态引入，避免通用壳在顶层耦合学生业务模块
        const { studentApi } = await import('@/modules/student/api/student.api')
        const res = await studentApi.getStudents({ keyword: kw, pageSize: 6 })
        if (seq !== this.stuSeq) return
        const list = (res && res.code === 0 && res.data && res.data.list) || []
        this.stuResults = list.map((s) => ({
          id: s.studentId,
          name: s.name,
          no: s.studentNo,
          sub: [s.className, s.grade ? s.grade + '级' : ''].filter(Boolean).join(' · ')
        }))
      } catch {
        if (seq === this.stuSeq) this.stuResults = []
      } finally {
        if (seq === this.stuSeq) this.stuSearching = false
      }
    },
    pickFirstStu() {
      if (this.stuResults.length) this.pickStu(this.stuResults[0])
    },
    pickStu(s) {
      if (!s || !s.id) return
      this.stuQuery = ''
      this.stuOpen = false
      this.stuResults = []
      const p = '/admin/student/' + s.id
      if (this.$router && p !== this.$route.path) this.$router.push(p)
    },
    closeStuSoon() {
      this.stuBlurTimer = setTimeout(() => {
        this.stuOpen = false
      }, 150)
    },
    /* 二级模块是否展开：未手动记录时，默认展开「当前路由所属二级」 */
    isExpanded(key) {
      if (key in this.expandedMods) return this.expandedMods[key]
      return key === this.planActive.modKey
    },
    toggleMod(key) {
      this.expandedMods = { ...this.expandedMods, [key]: !this.isExpanded(key) }
    },
    /* 点二级模块：有三级则展开/折叠；implemented/partial 同时跳转；planned/未开通（且无三级）仅 toast */
    onTreeMod(m) {
      if (!m) return
      if (m.children && m.children.length) this.toggleMod(m.key)
      if (m.disabled) {
        if (!m.children || !m.children.length) {
          toast.info(m.badge === '未开通' ? '该模块未开通' : '该功能待施工，敬请期待')
        }
        return
      }
      // 精确比较目标与当前完整 URL：避免 /admin/graduation 这类「前缀」被 navRefMatches
      // 判为「已在此」而跳过跳转（导致从子页点看板/总览时点了不动）。
      if (m.path && m.path !== this.currentNavRef) this.$router.push(m.path)
    },
    navRefMatches,
    /* 叶子唯一标识（与模板 :key 一致）：同 path 多叶子也能各自区分高亮/点击。 */
    leafKey(m, leaf) {
      return m.key + '/' + leaf.label
    },
    /* 三级高亮：一律按唯一 leafKey 匹配，保证任何路由下最多一个叶子高亮，
       杜绝「同 path 多叶子全部连成一片高亮」。 */
    isLeafActive(m, leaf) {
      return !leaf.disabled && this.leafKey(m, leaf) === this.effectiveActiveLeafKey
    },
    /* 点三级页面：implemented/partial 跳转（含 query 的 panel 切换），planned/未开通仅 toast。
       无论 path 是否已匹配，都记下被点叶子的 leafKey → 高亮跟随点击移动，杜绝「再点不动无反馈」。 */
    onPlanLeaf(leaf, m) {
      if (!leaf) return
      if (leaf.disabled) {
        toast.info(leaf.badge === '未开通' ? '该功能未开通' : '该功能待施工，敬请期待')
        return
      }
      if (m) this.clickedLeafKey = this.leafKey(m, leaf)
      // 精确比较：只要目标与当前完整 URL 不同就跳转，避免 /admin/graduation 这类前缀路径
      // 被 navRefMatches 判为「已在此」而跳过跳转（这是「点毕设总览看不了东西」的真因）。
      if (leaf.path && leaf.path !== this.currentNavRef) this.$router.push(leaf.path)
    }
  },
  watch: {
    fnQuery() {
      this.fnActive = 0
    },
    stuQuery(q) {
      this.queueStuSearch(q)
    }
  },
  mounted() {
    window.addEventListener('keydown', this.onGlobalKeydown)
  },
  beforeUnmount() {
    window.removeEventListener('keydown', this.onGlobalKeydown)
    if (this.stuBlurTimer) clearTimeout(this.stuBlurTimer)
    if (this.stuTimer) clearTimeout(this.stuTimer)
    if (this.fnBlurTimer) clearTimeout(this.fnBlurTimer)
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
.bpl-search {
  flex: 1;
  min-width: 0;
  display: flex;
  gap: 8px;
  margin: 0 14px;
  max-width: 640px;
}
.bpl-cmdk--stu {
  flex: 0 1 210px;
}
.bpl-cmdk--fn {
  flex: 1;
}
.bpl-cmdk {
  min-width: 0;
  height: 34px;
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
  overflow: visible;
  position: relative;
}
.bpl-cmdk.is-open {
  border-color: var(--glow);
  background: #fff;
  box-shadow: 0 0 0 3px var(--pri-bg);
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
.bpl-cmdk__input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-family: inherit;
  font-size: 12.5px;
  color: var(--t1);
  padding: 0;
}
.bpl-cmdk__input::placeholder {
  color: var(--t3);
}
.bpl-cmdk__panel {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  background: var(--bg-card, #fff);
  border: 1px solid var(--card-b);
  border-radius: 12px;
  box-shadow: var(--s2, 0 12px 32px -8px rgba(15, 23, 42, 0.25));
  padding: 6px;
  z-index: 50;
  max-height: 360px;
  overflow-y: auto;
  white-space: normal;
}
.bpl-cmdk__opt {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  text-decoration: none;
  cursor: pointer;
}
.bpl-cmdk__opt:hover,
.bpl-cmdk__opt.is-active {
  background: var(--pri-bg);
}
.bpl-cmdk__opt-lb {
  font-size: 13px;
  font-weight: var(--font-weight-medium);
  color: var(--t1);
  white-space: nowrap;
}
.bpl-cmdk__opt-pt {
  margin-left: auto;
  font-size: 11px;
  color: var(--t3);
  font-variant-numeric: var(--font-numeric);
  white-space: nowrap;
}
.bpl-cmdk__empty {
  padding: 12px 10px;
  font-size: 12.5px;
  color: var(--t3);
  text-align: center;
}
.bpl-cmdk__grp {
  font-size: 10.5px;
  font-weight: var(--font-weight-bold);
  letter-spacing: 0.06em;
  color: var(--t3);
  padding: 8px 10px 4px;
}
.bpl-cmdk__loading {
  padding: 10px;
  font-size: 12px;
  color: var(--t3);
  text-align: center;
}
.bpl-top-r {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  /* 为右上角全局悬浮的退出胶囊（AppUserChip · fixed）让出空间，避免相互压叠 */
  margin-right: 144px;
  flex-shrink: 0;
}
@media (max-width: 900px) {
  .bpl-top-r {
    margin-right: 120px;
  }
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
/* 二级模块切换区（同一级下的兄弟模块，如 学工中心 → 学生画像/数字迎新/在校服务） */
.bpl-submods {
  padding-bottom: 10px;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--dv);
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.bpl-submods__label {
  font-size: 10.5px;
  font-weight: var(--font-weight-bold);
  letter-spacing: 0.08em;
  color: var(--t3);
  padding: 2px 8px 6px;
}
.bpl-submods__item {
  display: block;
  padding: 8px 10px;
  border-radius: 9px;
  font-size: 13px;
  color: var(--t2);
  font-weight: var(--font-weight-medium);
  text-decoration: none;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}
.bpl-submods__item:hover {
  background: var(--pri-bg);
  color: var(--t1);
}
.bpl-submods__item.is-active {
  background: var(--pri-bg);
  color: var(--pri);
  font-weight: var(--font-weight-semibold);
}
.bpl-submods__item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.bpl-submods__lb {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
/* planned / partial / unauthorized 灰显与徽标（施工地图） */
.bpl-submods__item.is-disabled,
.bpl-menu__item.is-disabled {
  color: var(--text-disabled, #9aa4b2);
  cursor: not-allowed;
}
.bpl-submods__item.is-disabled:hover {
  background: transparent;
  color: var(--text-disabled, #9aa4b2);
}
.bpl-planbadge {
  flex-shrink: 0;
  font-size: 10px;
  line-height: 15px;
  padding: 0 6px;
  border-radius: 8px;
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}
.bpl-planbadge--planned,
.bpl-planbadge--unauthorized {
  color: #94a3b8;
  background: rgba(148, 163, 184, 0.14);
  border: 1px solid rgba(148, 163, 184, 0.28);
}
.bpl-planbadge--partial {
  color: #b45309;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.28);
}
/* 侧栏树：二级箭头 + 三级缩进 */
.bpl-tree {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.bpl-tree__caret {
  flex-shrink: 0;
  width: 12px;
  font-size: 10px;
  color: var(--t3);
  transition: transform 0.15s ease;
  display: inline-block;
  text-align: center;
}
.bpl-tree__caret.is-open {
  transform: rotate(90deg);
}
.bpl-tree__caret--sp {
  visibility: hidden;
}
/* ══ 侧栏施工地图：二级(分组标题) ↔ 三级(具体页面) 强层级区分 ══ */
/* 二级模块：像“分组标题”——更大更粗、颜色最深、组间留白，箭头醒目 */
.bpl-tree .bpl-tree__mod {
  font-size: 13.5px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
  margin-top: 8px;
  padding-top: 9px;
  padding-bottom: 9px;
}
.bpl-tree .bpl-tree__mod:first-of-type {
  margin-top: 2px;
}
.bpl-tree .bpl-tree__mod .bpl-tree__caret {
  font-size: 11px;
  color: var(--t2);
}
.bpl-tree .bpl-tree__mod .bpl-submods__lb {
  letter-spacing: 0.01em;
}
.bpl-tree .bpl-tree__mod.is-disabled {
  color: var(--text-disabled, #9aa4b2);
  font-weight: var(--font-weight-semibold);
}
/* 三级容器：整组明显右缩进 + 左侧竖引导线 */
.bpl-tree__leaves {
  display: flex;
  flex-direction: column;
  gap: 1px;
  margin: 1px 0 7px 16px;
  /* 竖引导线：同侧栏分隔线同色系，加深到清晰可见 */
  border-left: 1.5px solid rgba(120, 144, 190, 0.42);
}
/* 三级页面：小字浅色 + 与竖线相连的长横向连接符（├── 树形），明显缩进、一眼看出是子级 */
.bpl-tree .bpl-tree__leaf {
  position: relative;
  padding: 6px 10px 6px 34px;
  font-size: 12.5px;
  font-weight: 400;
  color: var(--t3);
}
.bpl-tree .bpl-tree__leaf::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  width: 24px;
  height: 1.5px;
  background: rgba(120, 144, 190, 0.42);
}
.bpl-tree .bpl-tree__leaf:hover {
  color: var(--t1);
}
.bpl-tree .bpl-tree__leaf.is-disabled {
  color: var(--text-disabled, #9aa4b2);
}
.bpl-tree .bpl-tree__leaf.is-disabled::before {
  opacity: 0.45;
}
.bpl-tree .bpl-tree__leaf.is-active {
  color: var(--pri);
  font-weight: var(--font-weight-medium);
}
.bpl-tree .bpl-tree__leaf.is-active::before {
  background: var(--pri);
}
.bpl-menu__item {
  display: flex;
  align-items: center;
  gap: 6px;
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
