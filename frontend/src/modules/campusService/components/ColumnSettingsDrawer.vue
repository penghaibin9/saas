<template>
  <AppDrawer :visible="visible" title="表格列设置" @update:visible="onClose">
    <p class="acs-note">勾选需要展示的列；带锁的列为固定列不可隐藏。含「敏感」标记的列默认隐藏，展示后仍为脱敏形态。</p>
    <label v-for="c in columns" :key="c.key" class="acs-item" :class="{ 'is-locked': c.locked }">
      <input type="checkbox" :checked="localKeys.includes(c.key)" :disabled="c.locked" @change="toggle(c.key, $event.target.checked)" />
      <span>
        {{ c.title }}
        <i v-if="c.locked" class="acs-tag">固定</i>
        <i v-if="c.sensitive" class="acs-tag acs-tag--sensitive">敏感</i>
      </span>
    </label>
    <template #footer>
      <AppButton variant="ghost" @click="reset">恢复默认</AppButton>
      <AppButton variant="primary" @click="apply">应用</AppButton>
    </template>
  </AppDrawer>
</template>

<script>
/**
 * ColumnSettingsDrawer — 表格列设置抽屉（模块局部组件）。
 * 列配置来自 api 的 fieldColumns（含 locked / default / sensitive 标记），页面不写死列。
 */
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppButton } from '@/components/ui'

export default {
  name: 'CampusServiceColumnSettingsDrawer',
  components: { AppDrawer, AppButton },
  props: {
    visible: { type: Boolean, default: false },
    columns: { type: Array, default: () => [] },
    visibleKeys: { type: Array, default: () => [] }
  },
  emits: ['update:visible', 'update:visibleKeys'],
  data() {
    return { localKeys: [] }
  },
  watch: {
    visible(v) {
      if (v) this.localKeys = [...this.visibleKeys]
    }
  },
  methods: {
    onClose() {
      this.$emit('update:visible', false)
    },
    toggle(key, checked) {
      this.localKeys = checked ? [...this.localKeys, key] : this.localKeys.filter((k) => k !== key)
    },
    reset() {
      this.localKeys = this.columns.filter((c) => c.locked || c.default).map((c) => c.key)
    },
    apply() {
      const locked = this.columns.filter((c) => c.locked).map((c) => c.key)
      const merged = [...new Set([...locked, ...this.localKeys])]
      this.$emit('update:visibleKeys', merged)
      this.onClose()
    }
  }
}
</script>

<style scoped>
.acs-note {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin: 0 0 var(--space-3);
  line-height: var(--line-height-base);
}
.acs-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--border-light);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.acs-item.is-locked {
  color: var(--text-tertiary);
}
.acs-tag {
  font-style: normal;
  font-size: var(--font-size-xs);
  color: var(--gray-600);
  background: var(--gray-100);
  border-radius: var(--radius-full);
  padding: 0 var(--space-2);
  margin-left: var(--space-1);
}
.acs-tag--sensitive {
  color: var(--danger-600);
  background: var(--danger-50);
}
</style>
