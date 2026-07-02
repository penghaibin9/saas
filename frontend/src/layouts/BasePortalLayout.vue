<template>
  <div class="base-portal-layout">
    <!-- 顶部栏 -->
    <header class="bpl-header">
      <div class="bpl-header__brand">
        <slot name="logo">
          <span class="bpl-header__logo-dot"><span /></span>
        </slot>
        <span class="bpl-header__title">{{ title }}</span>
        <span v-if="subtitle" class="bpl-header__subtitle">{{ subtitle }}</span>
      </div>
      <div class="bpl-header__right">
        <!-- 消息 / 待办 / 用户信息由使用方传入 -->
        <slot name="header-right" />
        <slot name="user" />
      </div>
    </header>

    <div class="bpl-body">
      <!-- 左侧轻菜单：必须通过 menus prop 或 menu slot 传入，本组件不写死任何业务菜单 -->
      <aside class="bpl-aside" :class="{ 'is-hidden': hideAside }">
        <slot name="menu">
          <nav class="bpl-menu">
            <a
              v-for="item in menus"
              :key="item.key"
              class="bpl-menu__item"
              :class="{ 'is-active': item.key === activeKey, 'is-disabled': item.disabled }"
              :title="item.disabled ? item.disabledTip || '即将上线' : ''"
              href="javascript:void(0)"
              @click="onSelect(item)"
            >
              <span v-if="item.icon" class="bpl-menu__icon">{{ item.icon }}</span>
              <span class="bpl-menu__label">{{ item.label }}</span>
              <span v-if="item.badge" class="bpl-menu__badge">{{ item.badge }}</span>
              <span v-if="item.disabled" class="bpl-menu__soon">即将上线</span>
              <span v-if="item.readonly" class="bpl-menu__readonly">只读</span>
            </a>
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
/**
 * BasePortalLayout 门户壳基座
 * 依据 V2.1 §6.2：StudentPortalLayout 与 EnterprisePortalLayout 必须基于本组件复用，
 * 禁止复制布局壳改名，禁止企业导师端使用 AdminLayout。
 *
 * 铁律：本组件不写死任何业务菜单（毕业设计、岗位实习、企业评价等均由使用方传入）。
 *
 * Props:
 *  - title:    门户名称（如学校名 + 门户名，由使用方传入）
 *  - subtitle: 副标题 / 身份说明
 *  - menus:    [{ key, label, icon?, path?, badge?, disabled?, readonly? }]
 *  - activeKey: 当前激活菜单 key
 *  - hideAside: 是否隐藏侧边菜单（移动窄屏等场景）
 * Emits:
 *  - menu-select(item)：菜单点击（使用方在此做 router.push(item.path)）
 * Slots:
 *  - logo / header-right / user / menu（完全自定义菜单区）/ default（内容区，放 router-view）/ footer
 */
export default {
  name: 'BasePortalLayout',
  props: {
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    menus: { type: Array, default: () => [] },
    activeKey: { type: String, default: '' },
    hideAside: { type: Boolean, default: false }
  },
  emits: ['menu-select', 'menu-disabled'],
  methods: {
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
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--page-gradient);
  font-family: var(--font-family-base);
  color: var(--text-primary);
}
.bpl-header {
  height: 64px;
  background: var(--bg-elevated);
  border-bottom: 1px solid var(--border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--page-padding-pc);
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
  box-shadow: var(--shadow-header);
}
.bpl-header__brand {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 0;
}
.bpl-header__logo-dot {
  width: 34px;
  height: 34px;
  border-radius: var(--radius-lg);
  background: var(--primary-600);
  flex-shrink: 0;
  display: grid;
  place-items: center;
  box-shadow: var(--shadow-sm);
}
.bpl-header__logo-dot span {
  width: 12px;
  height: 12px;
  border: 3px solid var(--text-inverse);
  border-radius: var(--radius-sm);
}
.bpl-header__title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  white-space: nowrap;
}
.bpl-header__subtitle {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  border-left: 1px solid var(--border-base);
  padding-left: var(--space-3);
  white-space: nowrap;
}
.bpl-header__right {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.bpl-body {
  flex: 1;
  display: flex;
  min-height: 0;
}
.bpl-aside {
  width: 240px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-right: 1px solid var(--border-base);
  padding: var(--space-4) var(--space-3);
}
.bpl-aside.is-hidden {
  display: none;
}
.bpl-menu {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.bpl-menu__item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 0 var(--space-3);
  height: 40px;
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  text-decoration: none;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
  position: relative;
}
.bpl-menu__item:hover {
  background: var(--primary-50);
  color: var(--text-primary);
}
.bpl-menu__item.is-active {
  background: var(--primary-50);
  color: var(--primary-600);
  font-weight: var(--font-weight-medium);
  box-shadow: inset 3px 0 0 var(--primary-600);
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
  color: var(--text-tertiary);
  background: var(--gray-100);
  border-radius: var(--radius-sm);
  padding: 0 4px;
  line-height: 16px;
  white-space: nowrap;
}
.bpl-menu__icon {
  width: 16px;
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
  font-size: var(--font-size-base);
}
.bpl-menu__badge {
  min-width: 18px;
  height: 18px;
  padding: 0 6px;
  border-radius: var(--radius-full);
  background: var(--danger-500);
  color: var(--text-inverse);
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  line-height: 18px;
  text-align: center;
}
.bpl-menu__readonly {
  font-size: var(--font-size-xs);
  color: var(--info-600);
  background: var(--info-50);
  border-radius: var(--radius-sm);
  padding: 0 var(--space-1);
}
.bpl-main {
  flex: 1;
  min-width: 0;
  padding: var(--page-padding-pc);
  overflow: auto;
  background: var(--bg-page);
}
.bpl-footer {
  background: var(--bg-card);
  border-top: 1px solid var(--border-base);
  padding: var(--space-3) var(--page-padding-pc);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
@media (max-width: 900px) {
  .bpl-aside {
    display: none;
  }
  .bpl-main {
    padding: var(--page-padding-mobile);
  }
  .bpl-header {
    padding: 0 var(--page-padding-mobile);
  }
  .bpl-header__subtitle {
    display: none;
  }
}
</style>
