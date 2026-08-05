<template>
  <div class="ff">
    <div v-for="f in fields" :key="f.key" class="ff__item" :class="{ 'ff__item--full': f.full }">
      <label class="ff__label">
        {{ f.label }}<span v-if="f.required" class="ff__req">*</span>
        <span v-if="f.lockNote" class="ff__lock">{{ f.lockNote }}</span>
      </label>
      <AppSelect
        v-if="f.type === 'select'"
        :model-value="modelValue[f.key] ?? ''"
        :options="f.options || []"
        :placeholder="f.placeholder || '请选择'"
        :disabled="f.disabled"
        :status="errors[f.key] ? 'error' : 'default'"
        @update:model-value="update(f.key, $event)"
      />
      <AppCheckboxGroup
        v-else-if="f.type === 'checkbox-group'"
        :model-value="modelValue[f.key] || []"
        :options="f.options || []"
        :disabled="f.disabled"
        size="compact"
        @update:model-value="update(f.key, $event)"
      />
      <AppTextarea
        v-else-if="f.type === 'textarea'"
        :model-value="modelValue[f.key] ?? ''"
        :rows="f.rows || 3"
        :disabled="f.disabled"
        :placeholder="f.placeholder || '请输入'"
        :status="errors[f.key] ? 'error' : 'default'"
        @update:model-value="update(f.key, $event)"
      />
      <div v-else-if="f.type === 'color'" class="ff__color">
        <input type="color" :value="modelValue[f.key] || '#2563eb'" :disabled="f.disabled" @input="update(f.key, $event.target.value)" />
        <span class="ff__color-v">{{ modelValue[f.key] }}</span>
      </div>
      <AppTextInput
        v-else
        :model-value="modelValue[f.key] ?? ''"
        :type="f.type === 'tel' ? 'tel' : 'text'"
        :disabled="f.disabled"
        :placeholder="f.placeholder || '请输入'"
        :maxlength="f.maxlength || 0"
        :status="errors[f.key] ? 'error' : 'default'"
        @update:model-value="update(f.key, $event)"
      />
      <div v-if="errors[f.key]" class="ff__err">{{ errors[f.key] }}</div>
      <div v-else-if="f.hint" class="ff__hint">{{ f.hint }}</div>
    </div>
  </div>
</template>

<script>
import { AppCheckboxGroup, AppSelect, AppTextInput, AppTextarea } from '@/components/common'

/**
 * FormFields — 系统管理模块局部组件：schema 驱动的表单渲染器。
 * fields: [{ key, label, type: text|select|textarea|checkbox-group|color, options?, required?,
 *            placeholder?, hint?, disabled?, lockNote?（不可编辑说明）, full?（占整行） }]
 * v-model 为表单值对象；errors 为 { key: message } 校验错误。
 * 校验用 validateRequired(fields, value) 静态方法（页面提交前调用）。
 */
export default {
  name: 'SystemFormFields',
  components: { AppCheckboxGroup, AppSelect, AppTextInput, AppTextarea },
  props: {
    modelValue: { type: Object, required: true },
    fields: { type: Array, default: () => [] },
    errors: { type: Object, default: () => ({}) }
  },
  emits: ['update:modelValue'],
  methods: {
    update(key, value) {
      this.$emit('update:modelValue', { ...this.modelValue, [key]: value })
    }
  },
  validateRequired(fields, value) {
    const errors = {}
    fields.forEach((f) => {
      if (!f.required) return
      const v = value[f.key]
      if (f.type === 'checkbox-group' ? !(v && v.length) : !v) errors[f.key] = f.label + '为必填项'
    })
    return errors
  }
}
</script>

<style scoped>
.ff {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3) var(--space-4);
}
.ff__item--full {
  grid-column: 1 / -1;
}
.ff__item {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.ff__label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.ff__req {
  color: var(--danger-600);
}
.ff__lock {
  font-weight: var(--font-weight-normal);
  color: var(--text-tertiary);
}
.ff__color {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.ff__color-v {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  font-variant-numeric: var(--font-numeric);
}
.ff__err {
  font-size: var(--font-size-xs);
  color: var(--danger-600);
}
.ff__hint {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
</style>
