<template>
  <div class="ff">
    <div v-for="f in fields" :key="f.key" class="ff__item" :class="{ 'ff__item--full': f.full }">
      <label class="ff__label">
        {{ f.label }}<span v-if="f.required" class="ff__req">*</span>
        <span v-if="f.lockNote" class="ff__lock">{{ f.lockNote }}</span>
      </label>
      <select
        v-if="f.type === 'select'"
        class="ff__control"
        :disabled="f.disabled"
        :value="modelValue[f.key] ?? ''"
        @change="update(f.key, $event.target.value)"
      >
        <option value="" disabled>请选择</option>
        <option v-for="o in f.options || []" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
      <div v-else-if="f.type === 'checkbox-group'" class="ff__checks">
        <label v-for="o in f.options || []" :key="o.value" class="ff__check">
          <input
            type="checkbox"
            :checked="(modelValue[f.key] || []).includes(o.value)"
            @change="toggleMulti(f.key, o.value, $event.target.checked)"
          />
          {{ o.label }}
        </label>
      </div>
      <textarea
        v-else-if="f.type === 'textarea'"
        class="ff__control ff__control--area"
        :disabled="f.disabled"
        :placeholder="f.placeholder || '请输入'"
        :value="modelValue[f.key] ?? ''"
        @input="update(f.key, $event.target.value)"
      />
      <div v-else-if="f.type === 'color'" class="ff__color">
        <input type="color" :value="modelValue[f.key] || '#2563eb'" :disabled="f.disabled" @input="update(f.key, $event.target.value)" />
        <span class="ff__color-v">{{ modelValue[f.key] }}</span>
      </div>
      <input
        v-else
        type="text"
        class="ff__control"
        :disabled="f.disabled"
        :placeholder="f.placeholder || '请输入'"
        :value="modelValue[f.key] ?? ''"
        @input="update(f.key, $event.target.value)"
      />
      <div v-if="errors[f.key]" class="ff__err">{{ errors[f.key] }}</div>
      <div v-else-if="f.hint" class="ff__hint">{{ f.hint }}</div>
    </div>
  </div>
</template>

<script>
/**
 * FormFields — 系统管理模块局部组件：schema 驱动的表单渲染器。
 * fields: [{ key, label, type: text|select|textarea|checkbox-group|color, options?, required?,
 *            placeholder?, hint?, disabled?, lockNote?（不可编辑说明）, full?（占整行） }]
 * v-model 为表单值对象；errors 为 { key: message } 校验错误。
 * 校验用 validateRequired(fields, value) 静态方法（页面提交前调用）。
 */
export default {
  name: 'SystemFormFields',
  props: {
    modelValue: { type: Object, required: true },
    fields: { type: Array, default: () => [] },
    errors: { type: Object, default: () => ({}) }
  },
  emits: ['update:modelValue'],
  methods: {
    update(key, value) {
      this.$emit('update:modelValue', { ...this.modelValue, [key]: value })
    },
    toggleMulti(key, value, checked) {
      const cur = [...(this.modelValue[key] || [])]
      const next = checked ? [...cur, value] : cur.filter((v) => v !== value)
      this.update(key, next)
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
.ff__control {
  height: 34px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font: inherit;
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
}
.ff__control:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.ff__control:disabled {
  background: var(--bg-section-blue);
  color: var(--text-tertiary);
  cursor: not-allowed;
}
.ff__control--area {
  height: auto;
  min-height: 72px;
  padding: var(--space-2);
  resize: vertical;
}
.ff__checks {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2) var(--space-3);
  padding: var(--space-1) 0;
}
.ff__check {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
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
