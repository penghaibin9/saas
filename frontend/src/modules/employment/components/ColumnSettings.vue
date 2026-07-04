<template>
  <div class="cs">
    <AppButton
      variant="ghost"
      :disabled="disabled"
      :title="disabled ? disabledReason || '当前角色无此操作权限' : ''"
      @click="open = !open"
    >
      列设置
    </AppButton>
    <div v-if="open" class="cs__panel">
      <div class="cs__title">显示字段</div>
      <label v-for="c in columns" :key="c.key" class="cs__item" :class="{ 'is-locked': c.locked }">
        <input
          type="checkbox"
          :checked="selectedKeys.includes(c.key)"
          :disabled="c.locked"
          @change="toggle(c.key, $event.target.checked)"
        />
        {{ c.title }}
        <span v-if="c.sensitive" class="cs__sensitive">敏感</span>
      </label>
      <div class="cs__ops">
        <button type="button" class="cs__reset" @click="reset">恢复默认</button>
        <button type="button" class="cs__done" @click="open = false">完成</button>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * ColumnSettings — 表格列设置（模块局部组件）。
 * Props:
 *  - columns: mock/api fieldColumns 下发 [{ key, title, locked?, sensitive?, default? }]
 *  - selectedKeys(v-model): 当前显示列 key 数组
 */
import { AppButton } from '@/components/ui'

export default {
  name: 'ColumnSettings',
  components: { AppButton },
  props: {
    columns: { type: Array, default: () => [] },
    selectedKeys: { type: Array, default: () => [] },
    disabled: { type: Boolean, default: false },
    disabledReason: { type: String, default: '' }
  },
  emits: ['update:selectedKeys'],
  data() {
    return { open: false }
  },
  methods: {
    toggle(key, checked) {
      const next = checked ? [...this.selectedKeys, key] : this.selectedKeys.filter((k) => k !== key)
      this.$emit(
        'update:selectedKeys',
        this.columns.filter((c) => next.includes(c.key)).map((c) => c.key)
      )
    },
    reset() {
      this.$emit(
        'update:selectedKeys',
        this.columns.filter((c) => c.default || c.locked).map((c) => c.key)
      )
    }
  }
}
</script>

<style scoped>
.cs {
  position: relative;
  display: inline-flex;
}
.cs__panel {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 30;
  width: 220px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  padding: var(--space-3);
}
.cs__title {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
}
.cs__item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  padding: var(--space-1) 0;
  cursor: pointer;
}
.cs__item.is-locked {
  color: var(--text-tertiary);
}
.cs__sensitive {
  font-size: 10px;
  color: var(--warning-700);
  background: var(--warning-50);
  border-radius: var(--radius-full);
  padding: 0 var(--space-1);
}
.cs__ops {
  display: flex;
  justify-content: space-between;
  margin-top: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--border-light);
}
.cs__reset,
.cs__done {
  border: none;
  background: none;
  font-size: var(--font-size-xs);
  cursor: pointer;
  color: var(--text-tertiary);
}
.cs__done {
  color: var(--primary-600);
}
</style>
