<template>
  <div class="pt">
    <div v-for="mod in tree" :key="mod.key" class="pt__module">
      <div class="pt__module-head">
        <label class="pt__check pt__check--module">
          <input
            type="checkbox"
            :disabled="readonly"
            :checked="isModuleChecked(mod)"
            @change="toggleModule(mod, $event.target.checked)"
          />
          {{ mod.label }}
        </label>
        <span class="mp-note">{{ moduleSummary(mod) }}</span>
      </div>
      <div v-for="menu in mod.children" :key="menu.key" class="pt__menu">
        <label class="pt__check">
          <input
            type="checkbox"
            :disabled="readonly"
            :checked="menuKeys.includes(menu.key)"
            @change="toggleMenu(menu, $event.target.checked)"
          />
          {{ menu.label }}
        </label>
        <div v-if="menu.children && menu.children.length" class="pt__buttons">
          <label v-for="btn in menu.children" :key="btn.key" class="pt__btn" :class="{ 'is-off': !menuKeys.includes(menu.key) }">
            <input
              type="checkbox"
              :disabled="readonly || !menuKeys.includes(menu.key)"
              :checked="buttonKeys.includes(btn.key)"
              @change="toggleButton(btn.key, $event.target.checked)"
            />
            {{ btn.label }}
            <code class="pt__code">{{ btn.key }}</code>
          </label>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * PermissionTreeEditor — 系统管理模块局部组件：模块→菜单→按钮 三级权限勾选树。
 * v-model:menuKeys / v-model:buttonKeys 受控；readonly 用于「按角色预览」只读态。
 * 联动规则：取消菜单会同时取消其下按钮；按钮勾选前必须先勾选所属菜单。
 */
export default {
  name: 'PermissionTreeEditor',
  props: {
    tree: { type: Array, default: () => [] },
    menuKeys: { type: Array, default: () => [] },
    buttonKeys: { type: Array, default: () => [] },
    readonly: { type: Boolean, default: false }
  },
  emits: ['update:menuKeys', 'update:buttonKeys'],
  methods: {
    isModuleChecked(mod) {
      return mod.children.length > 0 && mod.children.every((m) => this.menuKeys.includes(m.key))
    },
    moduleSummary(mod) {
      const on = mod.children.filter((m) => this.menuKeys.includes(m.key)).length
      return `已授权 ${on} / ${mod.children.length} 个菜单`
    },
    toggleModule(mod, checked) {
      let menus = [...this.menuKeys]
      let buttons = [...this.buttonKeys]
      mod.children.forEach((menu) => {
        menus = menus.filter((k) => k !== menu.key)
        if (checked) menus.push(menu.key)
        else buttons = buttons.filter((k) => !(menu.children || []).some((b) => b.key === k))
      })
      this.$emit('update:menuKeys', menus)
      this.$emit('update:buttonKeys', buttons)
    },
    toggleMenu(menu, checked) {
      let menus = this.menuKeys.filter((k) => k !== menu.key)
      if (checked) menus = [...menus, menu.key]
      this.$emit('update:menuKeys', menus)
      if (!checked) {
        this.$emit('update:buttonKeys', this.buttonKeys.filter((k) => !(menu.children || []).some((b) => b.key === k)))
      }
    },
    toggleButton(key, checked) {
      const next = checked ? [...this.buttonKeys, key] : this.buttonKeys.filter((k) => k !== key)
      this.$emit('update:buttonKeys', next)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pt {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.pt__module {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.pt__module-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-section-blue);
  border-bottom: 1px solid var(--border-light);
}
.pt__menu {
  padding: var(--space-2) var(--space-3) var(--space-2) var(--space-6);
  border-bottom: 1px dashed var(--border-light);
}
.pt__menu:last-child {
  border-bottom: none;
}
.pt__check {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}
.pt__check--module {
  font-weight: var(--font-weight-semibold);
}
.pt__buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-4);
  padding: var(--space-2) 0 0 var(--space-5);
}
.pt__btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.pt__btn.is-off {
  opacity: 0.5;
}
.pt__code {
  font-size: 10px;
  color: var(--primary-600);
  background: var(--primary-50);
  border-radius: var(--radius-sm);
  padding: 0 var(--space-1);
}
</style>
