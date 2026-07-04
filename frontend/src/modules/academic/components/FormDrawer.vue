<template>
  <AppDrawer :visible="visible" :title="title" @update:visible="onClose">
    <p v-if="note" class="afd-note">{{ note }}</p>
    <div v-for="f in fields" :key="f.key" class="afd-field">
      <label class="afd-label">{{ f.label }}<span v-if="f.required" class="afd-req">*</span></label>
      <select v-if="f.type === 'select'" class="afd-control" :value="modelValue[f.key] ?? ''" @change="update(f.key, $event.target.value)">
        <option value="" disabled>请选择</option>
        <option v-for="o in f.options || []" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
      <textarea
        v-else-if="f.type === 'textarea'"
        class="afd-control afd-control--area"
        rows="3"
        :placeholder="f.placeholder || '请输入'"
        :value="modelValue[f.key] ?? ''"
        @input="update(f.key, $event.target.value)"
      />
      <input
        v-else
        :type="f.type === 'number' ? 'number' : f.type === 'date' ? 'date' : 'text'"
        class="afd-control"
        :placeholder="f.placeholder || '请输入'"
        :value="modelValue[f.key] ?? ''"
        @input="update(f.key, $event.target.value)"
      />
      <div v-if="errors[f.key]" class="afd-error">{{ errors[f.key] }}</div>
    </div>
    <template #footer>
      <AppButton variant="ghost" @click="onClose">取消</AppButton>
      <AppButton variant="primary" :loading="submitting" @click="submit">{{ submitText }}</AppButton>
    </template>
  </AppDrawer>
</template>

<script>
/**
 * FormDrawer — 通用表单抽屉（模块局部组件，字段配置驱动，不写死业务字段）。
 * fields: [{ key, label, type: text|number|date|select|textarea, options?, required?, placeholder? }]
 */
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppButton } from '@/components/ui'

export default {
  name: 'AcademicFormDrawer',
  components: { AppDrawer, AppButton },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, required: true },
    note: { type: String, default: '' },
    fields: { type: Array, default: () => [] },
    modelValue: { type: Object, required: true },
    submitting: { type: Boolean, default: false },
    submitText: { type: String, default: '保存' }
  },
  emits: ['update:visible', 'update:modelValue', 'submit'],
  data() {
    return { errors: {} }
  },
  watch: {
    visible(v) {
      if (v) this.errors = {}
    }
  },
  methods: {
    onClose() {
      this.$emit('update:visible', false)
    },
    update(key, value) {
      this.$emit('update:modelValue', { ...this.modelValue, [key]: value })
      if (this.errors[key]) this.errors = { ...this.errors, [key]: '' }
    },
    submit() {
      const errors = {}
      for (const f of this.fields) {
        const v = this.modelValue[f.key]
        if (f.required && (v === undefined || v === null || String(v).trim() === '')) {
          errors[f.key] = `${f.label}为必填项`
        }
      }
      this.errors = errors
      if (Object.keys(errors).length) return
      this.$emit('submit')
    }
  }
}
</script>

<style scoped>
.afd-note {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  background: var(--bg-section-blue);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  margin: 0 0 var(--space-4);
  line-height: var(--line-height-base);
}
.afd-field {
  margin-bottom: var(--space-4);
}
.afd-label {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  margin-bottom: var(--space-1);
}
.afd-req {
  color: var(--danger-600);
  margin-left: 2px;
}
.afd-control {
  width: 100%;
  box-sizing: border-box;
  height: 36px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-3);
  font-family: var(--font-family-base);
}
.afd-control--area {
  height: auto;
  padding: var(--space-2) var(--space-3);
  resize: vertical;
}
.afd-control:focus {
  outline: none;
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.afd-error {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--danger-600);
}
</style>
