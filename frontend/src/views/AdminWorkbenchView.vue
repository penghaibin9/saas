<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="工作台"
    :menus="[]"
    :ctx="{
      tenantBrandConfig: { schoolName: auth.schoolName },
      currentRole: { roleType: viewAsRoleType, userName: auth.displayName, roleName: currentRoleTypeLabel }
    }"
    @menu-select="go($event.path)"
  >
    <template #header-right>
      <label class="awb-viewas">
        <span class="awb-viewas__label">视角</span>
        <select v-model="viewAsRoleType">
          <option v-for="r in roleTypeOptions" :key="r.value" :value="r.value">{{ r.label }}</option>
        </select>
      </label>
    </template>

    <!-- 左侧：一级分组 + 二级模块导航（数据全部来自 config/adminMenu.js，本页不写死菜单） -->
    <template #menu>
      <nav class="awb-nav">
        <div v-for="group in visibleMenu" :key="group.key" class="awb-nav__group">
          <div class="awb-nav__group-label">{{ group.label }}</div>
          <a
            v-for="leaf in group.children"
            :key="leaf.key"
            class="awb-nav__item"
            href="javascript:void(0)"
            @click="go(leaf.path)"
          >
            {{ leaf.label }}
          </a>
        </div>
      </nav>
    </template>

    <!-- 内容区：玻璃 Hero + 模块入口（与左侧同一数据源） -->
    <div class="awb-body">
      <section class="awb-hb">
        <div class="awb-hb__grid" />
        <div class="awb-hb__top">
          <h1 class="awb-hb__hi">你好，{{ auth.displayName }}</h1>
          <span class="awb-hb__num">
            当前可进入 <strong>{{ leafCount }}</strong> 个功能模块
          </span>
        </div>
        <div class="awb-hb__chips">
          <span class="awb-chip awb-chip--hot">
            <svg class="awb-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z" />
            </svg>
            当前视角 · {{ currentRoleTypeLabel }}
          </span>
          <span class="awb-hb__school">{{ auth.schoolName }}</span>
        </div>
        <div class="awb-orbit">
          <div
            v-for="group in visibleMenu"
            :key="group.key"
            class="awb-orbit__n"
            @click="go(group.children[0] && group.children[0].path)"
          >
            <div class="awb-orbit__dot">{{ group.children.length }}</div>
            <div class="awb-orbit__lb">{{ group.label }}</div>
          </div>
        </div>
        <div class="awb-hb__meta">
          <span>菜单与可见性 · config/adminMenu.js × 当前视角</span>
          <span>品牌信息来自租户配置</span>
        </div>
      </section>

      <div class="awb-notice">
        <svg class="awb-ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 8h.01M12 11v5" />
        </svg>
        <span class="awb-notice__tx">
          当前视角：{{ currentRoleTypeLabel }} · 可进入 {{ leafCount }} 个模块。左侧导航或下方卡片均可进入。
        </span>
      </div>

      <section v-for="group in visibleMenu" :key="group.key" class="awb-group">
        <div class="awb-group__title">
          <span class="awb-group__t">{{ group.label }}</span>
          <span class="awb-group__n">{{ group.children.length }} 个入口</span>
        </div>
        <div class="awb-cards">
          <button
            v-for="leaf in group.children"
            :key="leaf.key"
            type="button"
            class="awb-card"
            @click="go(leaf.path)"
          >
            <span class="awb-card__ic">{{ leaf.label.charAt(0) }}</span>
            <span class="awb-card__inf">
              <span class="awb-card__name">{{ leaf.label }}</span>
              <span class="awb-card__path">{{ leaf.path }}</span>
            </span>
            <span class="awb-card__go">进入 →</span>
          </button>
        </div>
      </section>

      <p class="awb-devnote">
        开发辅助入口：<a href="javascript:void(0)" @click="go('/dev/components')">/dev/components 组件预览</a>
      </p>
    </div>
  </BasePortalLayout>
</template>

<script>
/**
 * AdminWorkbenchView — PC 管理端工作台（`/` 默认入口）。
 * PC-10-MODULE-MENU-BRIDGE-P0-FIX：只做菜单桥接——
 * 菜单树唯一来源为 config/adminMenu.js（getVisibleAdminMenu），本页不写死任何模块清单；
 * 品牌名来自 security auth 上下文（mock），不硬编码学校名；
 * 「视角」切换仅用于演示角色类型可见性差异（平台运营仅 PLATFORM 视角可见），默认取当前登录角色类型。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { getVisibleAdminMenu, ROLE_TYPE } from '@/config/adminMenu'
import { getAuthContext } from '@/security/auth/auth.context'

/** 角色类型显示名（角色"类型"字典，非租户角色名硬编码） */
const ROLE_TYPE_LABELS = {
  [ROLE_TYPE.SCHOOL_ADMIN]: '学校管理视角',
  [ROLE_TYPE.ACADEMIC_STAFF]: '教务视角',
  [ROLE_TYPE.COUNSELOR]: '辅导员视角',
  [ROLE_TYPE.AUDITOR]: '审计视角',
  [ROLE_TYPE.PLATFORM]: '平台运营视角'
}

export default {
  name: 'AdminWorkbenchView',
  components: { BasePortalLayout },
  data() {
    const auth = getAuthContext()
    return {
      auth,
      /* 默认视角 = 当前登录角色类型（mock 为 SCHOOL_ADMIN），普通学校角色默认看不到平台运营 */
      viewAsRoleType: (auth.roles && auth.roles[0]) || ROLE_TYPE.SCHOOL_ADMIN
    }
  },
  computed: {
    brandTitle() {
      return (this.auth.schoolName || '管理端') + ' · 管理端'
    },
    platformName() {
      return 'PC 管理端工作台'
    },
    roleTypeOptions() {
      return Object.keys(ROLE_TYPE_LABELS).map((value) => ({ value, label: ROLE_TYPE_LABELS[value] }))
    },
    currentRoleTypeLabel() {
      return ROLE_TYPE_LABELS[this.viewAsRoleType] || this.viewAsRoleType
    },
    visibleMenu() {
      return getVisibleAdminMenu({ currentRole: { roleType: this.viewAsRoleType } })
    },
    leafCount() {
      return this.visibleMenu.reduce((n, g) => n + g.children.length, 0)
    }
  },
  methods: {
    go(path) {
      if (path && path !== this.$route.path) this.$router.push(path)
    }
  }
}
</script>

<style scoped>
.awb-ic {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

/* 左侧分组导航（母版二级导航样式） */
.awb-nav {
  display: flex;
  flex-direction: column;
}
.awb-nav__group-label {
  font-size: 10.5px;
  font-weight: var(--font-weight-bold);
  letter-spacing: 0.08em;
  color: var(--t3);
  padding: 12px 8px 5px;
}
.awb-nav__item {
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
}
.awb-nav__item:hover {
  background: var(--pri-bg);
  color: var(--pri);
}

/* 顶栏视角切换 */
.awb-viewas {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
.awb-viewas__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.awb-viewas select {
  height: 28px;
  border: 1px solid var(--card-b);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-xs);
  padding: 0 var(--space-2);
  outline: none;
}

/* 内容区 */
.awb-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* ── 玻璃 Hero：深蓝渐变 + 网格纹理 + orbit 数字站点 ── */
.awb-hb {
  position: relative;
  border-radius: 18px;
  overflow: hidden;
  background: var(--hero-grad);
  border: 1px solid var(--hero-bd);
  color: var(--hero-tx);
  padding: 24px 28px 26px;
  box-shadow: var(--hero-shadow);
}
.awb-hb__grid {
  position: absolute;
  inset: 0;
  background:
    linear-gradient(var(--hero-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--hero-grid) 1px, transparent 1px);
  background-size: 30px 30px;
  pointer-events: none;
}
.awb-hb__top {
  display: flex;
  align-items: baseline;
  gap: 14px;
  flex-wrap: wrap;
  position: relative;
}
.awb-hb__hi {
  margin: 0;
  font-size: 22px;
  font-weight: var(--font-weight-bold);
  letter-spacing: -0.01em;
}
.awb-hb__num {
  font-size: 13px;
  color: var(--hero-sub);
  white-space: nowrap;
}
.awb-hb__num strong {
  font-size: 22px;
  font-weight: var(--font-weight-bold);
  color: var(--hero-tx);
  font-variant-numeric: tabular-nums;
  margin: 0 4px;
}
.awb-hb__chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-top: 10px;
  position: relative;
}
.awb-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  background: var(--hero-chip-bg);
  border: 1px solid var(--hero-chip-bd);
  font-size: 12px;
  color: var(--hero-chip-tx);
  font-weight: var(--font-weight-medium);
  backdrop-filter: blur(4px);
  white-space: nowrap;
}
.awb-chip--hot {
  background: var(--hero-chip-hot-bg);
  border-color: var(--hero-chip-hot-bd);
  color: var(--hero-chip-hot-tx);
}
.awb-hb__school {
  font-size: 12.5px;
  color: var(--hero-sub);
  white-space: nowrap;
}
.awb-orbit {
  display: flex;
  justify-content: space-between;
  position: relative;
  margin-top: 22px;
  padding: 0 6px;
}
.awb-orbit::before {
  content: '';
  position: absolute;
  left: 36px;
  right: 36px;
  top: 23px;
  height: 2px;
  border-radius: 1px;
  background: var(--hero-line);
}
.awb-orbit__n {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  position: relative;
  z-index: 1;
  flex: 1;
  cursor: pointer;
}
.awb-orbit__dot {
  min-width: 48px;
  height: 48px;
  padding: 0 8px;
  border-radius: 24px;
  background: var(--hero-dot-bg);
  border: 1.5px solid var(--hero-dot-bd);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: var(--font-weight-bold);
  color: var(--hero-dot-tx);
  backdrop-filter: blur(4px);
  font-variant-numeric: tabular-nums;
  transition: all 0.12s;
}
.awb-orbit__n:hover .awb-orbit__dot {
  background: var(--hero-dot-hot-bg);
  border-color: var(--hero-dot-hot-bd);
  color: var(--hero-dot-hot-tx);
  box-shadow: 0 0 18px var(--glow);
}
.awb-orbit__lb {
  font-size: 11px;
  color: var(--hero-sub);
  white-space: nowrap;
}
.awb-hb__meta {
  margin-top: 12px;
  font-size: 12px;
  color: var(--hero-dim);
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  position: relative;
}

/* ── 提醒条 ── */
.awb-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 14px;
  border-radius: 11px;
  font-size: 12.5px;
  font-weight: var(--font-weight-medium);
  border: 1px solid var(--pri-100);
  background: var(--pri-bg);
  color: var(--pri);
}
.awb-notice__tx {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 模块分组卡片 ── */
.awb-group__title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: var(--space-3);
}
.awb-group__t {
  font-size: 14.5px;
  font-weight: var(--font-weight-bold);
  letter-spacing: -0.01em;
}
.awb-group__n {
  font-size: 11px;
  color: var(--t3);
}
.awb-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: var(--space-3);
}
.awb-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  background: var(--card);
  backdrop-filter: blur(10px);
  border: 1px solid var(--card-b);
  border-radius: var(--r);
  box-shadow: var(--s1);
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: all 0.15s;
}
.awb-card:hover {
  border-color: var(--glow);
  box-shadow: var(--s2);
  transform: translateY(-1px);
}
.awb-card__ic {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 14px;
  font-weight: var(--font-weight-bold);
  background: var(--btn-p-bg);
  box-shadow: 0 4px 12px -4px var(--glow);
}
.awb-card__inf {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.awb-card__name {
  font-size: 13.5px;
  font-weight: var(--font-weight-semibold);
  color: var(--t1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.awb-card__path {
  font-size: 11px;
  color: var(--t3);
  font-variant-numeric: var(--font-numeric);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.awb-card__go {
  font-size: 12px;
  color: var(--pri);
  font-weight: var(--font-weight-medium);
  white-space: nowrap;
}
.awb-devnote {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.awb-devnote a {
  color: var(--text-link);
  text-decoration: none;
}
@media (max-width: 900px) {
  .awb-orbit {
    display: none;
  }
}
</style>
