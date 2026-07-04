<template>
  <div class="af">
    <div class="af__fields">
      <label v-for="f in fields" :key="f.key" class="af__field">
        <span class="af__label">{{ f.label }}</span>
        <select
          v-if="f.type === 'select'"
          class="af__control"
          :value="modelValue[f.key] ?? ''"
          @change="update(f.key, $event.target.value)"
        >
          <option value="">全部</option>
          <option v-for="o in f.options || []" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
        <input
          v-else-if="f.type === 'date'"
          type="date"
          class="af__control"
          :value="modelValue[f.key] ?? ''"
          @change="update(f.key, $event.target.value)"
        />
        <input
          v-else
          type="text"
          class="af__control af__control--text"
          :placeholder="f.placeholder || '请输入'"
          :value="modelValue[f.key] ?? ''"
          @input="update(f.key, $event.target.value)"
          @keyup.enter="$emit('search')"
        />
      </label>
    </div>
    <div class="af__ops">
      <AppButton variant="primary" @click="$emit('search')">查询</AppButton>
      <AppButton variant="ghost" @click="$emit('reset')">重置</AppButton>
      <slot name="ops" />
    </div>
  </div>
</template>

<script>
/**
 * AdvancedFilter — 高级筛选区（通用受控组件）。
 * Props:
 *  - modelValue: 筛选值对象（v-model）
 *  - fields: [{ key, label, type: 'select'|'text'|'date', options?: [{value,label}], placeholder? }]
 *    字段字典由业务 api 的 statusOptions 提供，本组件不写死任何业务选项。
 * Emits: update:modelValue / search / reset
 */
import { AppButton } from '@/components/ui'

export default {
  name: 'AdvancedFilter',
  components: { AppButton },
  props: {
    modelValue: { type: Object, required: true },
    fields: { type: Array, default: () => [] }
  },
  emits: ['update:modelValue', 'search', 'reset'],
  methods: {
    update(key, value) {
      this.$emit('update:modelValue', { ...this.modelValue, [key]: value })
    }
  }
}
</script>

<style scoped>
/* 母版筛选区：玻璃卡 + fb-in 输入 */
.af {
  background: var(--card);
  backdrop-filter: blur(10px);
  border: 1px solid var(--card-b);
  border-radius: var(--r);
  padding: var(--space-3) var(--space-4);
  box-shadow: var(--s1);
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  flex-wrap: wrap;
}
.af__fields {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
  flex: 1;
  min-width: 0;
}
.af__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 130px;
}
.af__label {
  font-size: var(--font-size-xs);
  color: var(--t3);
}
.af__control {
  height: 34px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--t1);
  font-size: 13px;
  padding: 0 var(--space-3);
  outline: none;
  transition: all 0.12s;
}
.af__control:hover {
  border-color: var(--glow);
}
.af__control:focus {
  border-color: var(--pri);
  box-shadow: 0 0 0 3px var(--pri-bg);
}
.af__control--text {
  min-width: 180px;
}
.af__ops {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
</style>
