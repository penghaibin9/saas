<template>
  <div class="af">
    <div class="af__fields">
      <label
        v-for="f in fields"
        :key="f.key"
        class="af__field"
        :class="{ 'af__field--range': f.type === 'daterange' || f.type === 'date-range' }"
      >
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
        <AppDatePicker
          v-else-if="f.type === 'date'"
          class="af__date"
          :model-value="modelValue[f.key] ?? ''"
          :placeholder="f.placeholder || '全部时间'"
          :clearable="f.clearable !== false"
          :show-empty-hint="false"
          @update:model-value="update(f.key, $event)"
        />
        <AppDateRangePicker
          v-else-if="f.type === 'daterange' || f.type === 'date-range'"
          class="af__range"
          :model-value="rangeValue(f)"
          mode="filter"
          :empty-label="f.emptyLabel || '全部时间'"
          :memory-key="f.memoryKey || ''"
          :show-shortcuts="f.showShortcuts !== false"
          :with-time="!!f.withTime"
          @update:model-value="updateRange(f, $event)"
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
 * fields: [{ key, label, type: 'select'|'text'|'date'|'daterange', options?, placeholder?,
 *            startKey?, endKey?, memoryKey?, emptyLabel?, showShortcuts?, withTime? }]
 * date / daterange 统一走公共日期底座；空日期=不限制，文案「全部时间」。
 */
import { AppButton } from '@/components/ui'
import { AppDatePicker, AppDateRangePicker } from '@/components/common/date'

export default {
  name: 'AdvancedFilter',
  components: { AppButton, AppDatePicker, AppDateRangePicker },
  props: {
    modelValue: { type: Object, required: true },
    fields: { type: Array, default: () => [] }
  },
  emits: ['update:modelValue', 'search', 'reset'],
  methods: {
    update(key, value) {
      this.$emit('update:modelValue', { ...this.modelValue, [key]: value })
    },
    rangeValue(f) {
      const startKey = f.startKey || (f.key + 'Start')
      const endKey = f.endKey || (f.key + 'End')
      // 也支持整体对象挂在 f.key 上
      if (this.modelValue[f.key] && typeof this.modelValue[f.key] === 'object') {
        return {
          start: this.modelValue[f.key].start || '',
          end: this.modelValue[f.key].end || ''
        }
      }
      return {
        start: this.modelValue[startKey] || '',
        end: this.modelValue[endKey] || ''
      }
    },
    updateRange(f, range) {
      const startKey = f.startKey || (f.key + 'Start')
      const endKey = f.endKey || (f.key + 'End')
      if (f.asObject) {
        this.$emit('update:modelValue', {
          ...this.modelValue,
          [f.key]: { start: range.start || '', end: range.end || '' }
        })
        return
      }
      this.$emit('update:modelValue', {
        ...this.modelValue,
        [startKey]: range.start || '',
        [endKey]: range.end || ''
      })
    }
  }
}
</script>

<style scoped>
.af {
  background: var(--card);
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
.af__field--range {
  min-width: 320px;
  flex: 1 1 360px;
}
.af__label {
  font-size: var(--font-size-xs);
  color: var(--t3);
}
.af__control {
  height: 38px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--t1);
  font-size: var(--font-size-base);
  padding: 0 var(--space-3);
  outline: none;
  transition:
    border-color 0.12s ease,
    box-shadow 0.12s ease;
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
.af__date :deep(.app-date__label),
.af__range :deep(.app-dr__label) {
  display: none;
}
.af__ops {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}
</style>
