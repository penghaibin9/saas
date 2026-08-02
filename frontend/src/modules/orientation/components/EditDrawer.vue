<template>
  <AppDrawer
    :visible="visible"
    :title="title"
    mode="modal"
    :size="fields.length > 6 ? 'large' : 'medium'"
    @update:visible="$emit('update:visible', $event)"
  >
    <form class="ed" @submit.prevent="onSubmit">
      <label v-for="f in fields" :key="f.key" class="ed__field">
        <span class="ed__label">
          {{ f.label }}<span v-if="f.required" class="ed__required">*</span>
        </span>
        <AppSelect
          v-if="f.type === 'select'"
          v-model="form[f.key]"
          :options="f.options || []"
          :placeholder="f.placeholder || '请选择'"
          :disabled="f.disabled"
          :status="errors[f.key] ? 'error' : 'default'"
        />
        <AppDatePicker
          v-else-if="f.type === 'date'"
          v-model="form[f.key]"
          :disabled="f.disabled"
          :placeholder="f.placeholder || '请选择日期'"
        />
        <AppTextarea
          v-else-if="f.type === 'textarea'"
          v-model="form[f.key]"
          :rows="f.rows || 3"
          :placeholder="f.placeholder || '请输入'"
          :disabled="f.disabled"
          :status="errors[f.key] ? 'error' : 'default'"
        />
        <AppNumberInput
          v-else-if="f.type === 'number'"
          v-model="form[f.key]"
          :min="f.min ?? -Infinity"
          :max="f.max ?? Infinity"
          :step="f.step ?? 1"
          :precision="f.precision ?? null"
          :controls="f.controls !== false"
          :placeholder="f.placeholder || '请输入'"
          :disabled="f.disabled"
          :status="errors[f.key] ? 'error' : 'default'"
        />
        <AppTextInput
          v-else
          v-model="form[f.key]"
          :type="f.type === 'tel' ? 'tel' : 'text'"
          :placeholder="f.placeholder || '请输入'"
          :disabled="f.disabled"
          :maxlength="f.maxlength || 0"
          :status="errors[f.key] ? 'error' : 'default'"
        />
        <span v-if="errors[f.key]" class="ed__error">{{ errors[f.key] }}</span>
      </label>
    </form>
    <template #footer>
      <div class="ed__footer">
        <AppButton variant="ghost" @click="$emit('update:visible', false)">取消</AppButton>
        <AppButton variant="primary" :loading="submitting" @click="onSubmit">{{ submitText }}</AppButton>
      </div>
    </template>
  </AppDrawer>
</template>

<script>
/**
 * EditDrawer — 通用新增/编辑抽屉（模块局部组件）。
 * Props:
 *  - fields: [{ key, label, type: 'text'|'select'|'date'|'number'|'textarea', options?, required?, placeholder?, disabled? }]
 *    字段定义来自 mock/api（fieldColumns / statusOptions），不在组件内写死业务字段。
 *  - model: 编辑时传入原记录（null = 新增）
 * Emits: submit(formData)
 */
import { AppDrawer, AppButton } from '@/components/ui'
import { AppDatePicker, AppSelect, AppTextInput, AppNumberInput, AppTextarea } from '@/components/common'

export default {
  name: 'EditDrawer',
  components: { AppDrawer, AppButton, AppDatePicker, AppSelect, AppTextInput, AppNumberInput, AppTextarea },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, required: true },
    fields: { type: Array, default: () => [] },
    model: { type: Object, default: null },
    submitting: { type: Boolean, default: false },
    submitText: { type: String, default: '保存' }
  },
  emits: ['update:visible', 'submit'],
  data() {
    return { form: {}, errors: {} }
  },
  watch: {
    visible(v) {
      if (v) this.resetForm()
    }
  },
  methods: {
    resetForm() {
      const form = {}
      this.fields.forEach((f) => {
        form[f.key] = this.model?.[f.key] ?? ''
      })
      this.form = form
      this.errors = {}
    },
    onSubmit() {
      const errors = {}
      this.fields.forEach((f) => {
        if (f.required && !String(this.form[f.key] ?? '').trim()) errors[f.key] = `${f.label}为必填项`
      })
      this.errors = errors
      if (Object.keys(errors).length) return
      this.$emit('submit', { ...this.form })
    }
  }
}
</script>

<style scoped>
.ed {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.ed__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.ed__label {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.ed__required {
  color: var(--danger-600);
  margin-left: 2px;
}
.ed__error {
  font-size: var(--font-size-xs);
  color: var(--danger-600);
}
.ed__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
}
</style>
