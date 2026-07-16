<template>
  <div class="app-date" :class="{ 'is-disabled': disabled, 'is-invalid': !!errorText }">
    <label v-if="label" class="app-date__label">
      {{ label }}<i v-if="required">*</i>
      <span v-if="hint" class="app-date__hint-inline">{{ hint }}</span>
    </label>
    <div class="app-date__row">
      <el-config-provider :locale="zhCn">
        <el-date-picker
          type="date"
          :model-value="inner || null"
          value-format="YYYY-MM-DD"
          :placeholder="placeholder"
          :disabled="disabled"
          :clearable="clearable"
          :disabled-date="disabledDate"
          :aria-label="label || placeholder"
          @update:model-value="onPick"
        />
      </el-config-provider>
    </div>
    <p v-if="errorText" class="app-date__err">{{ errorText }}</p>
  </div>
</template>

<script>
/**
 * AppDatePicker — 单日期选择（YYYY-MM-DD）。
 * 内部使用 Element Plus DatePicker 日历弹层（一次点开、点日即选），对外 API 与旧版完全一致；
 * 业务页只允许用本组件，不得直接引 el-date-picker。
 */
import { ElDatePicker, ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/es/components/date-picker/style/css'
import 'element-plus/es/components/config-provider/style/css'
import { toDateInputValue, formatDate, isEmptyDate } from '@/utils/dateUtils'

export default {
  name: 'AppDatePicker',
  components: { ElDatePicker, ElConfigProvider },
  props: {
    modelValue: { type: [String, Date], default: '' },
    label: { type: String, default: '' },
    hint: { type: String, default: '' },
    placeholder: { type: String, default: '请选择日期' },
    required: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    clearable: { type: Boolean, default: true },
    showEmptyHint: { type: Boolean, default: false },
    min: { type: String, default: '' },
    max: { type: String, default: '' },
    /** 与配对结束日联动：开始不能晚于 end */
    endValue: { type: [String, Date], default: '' },
    /** 与配对开始日联动：结束不能早于 start */
    startValue: { type: [String, Date], default: '' },
    role: { type: String, default: 'single' } // single | start | end
  },
  emits: ['update:modelValue', 'change', 'clear'],
  data() {
    return { zhCn }
  },
  computed: {
    inner() {
      return toDateInputValue(this.modelValue)
    },
    errorText() {
      if (this.role === 'start' && !isEmptyDate(this.modelValue) && !isEmptyDate(this.endValue)) {
        const a = formatDate(this.modelValue, '')
        const b = formatDate(this.endValue, '')
        if (a && b && a > b) return '开始时间不能晚于结束时间'
      }
      if (this.role === 'end' && !isEmptyDate(this.modelValue) && !isEmptyDate(this.startValue)) {
        const a = formatDate(this.startValue, '')
        const b = formatDate(this.modelValue, '')
        if (a && b && b < a) return '结束时间不能早于开始时间'
      }
      return ''
    }
  },
  methods: {
    onPick(v) {
      const val = v || ''
      this.$emit('update:modelValue', val)
      this.$emit('change', val)
      if (!val) this.$emit('clear')
    },
    disabledDate(date) {
      const s = formatDate(date, '')
      if (!s) return false
      if (this.min && s < String(this.min).slice(0, 10)) return true
      if (this.max && s > String(this.max).slice(0, 10)) return true
      return false
    }
  }
}
</script>

<style scoped>
.app-date { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.app-date__label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary, #64748b);
  display: flex; align-items: center; gap: 4px;
}
.app-date__label i { color: var(--danger-600, #dc2626); font-style: normal; }
.app-date__hint-inline { font-weight: 400; color: var(--text-tertiary, #94a3b8); margin-left: 4px; }
.app-date__row { display: flex; align-items: center; min-width: 0; }
.app-date__row :deep(.el-date-editor.el-input) { --el-date-editor-width: 100%; width: 100%; }
.app-date.is-invalid :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--danger-600, #dc2626) inset;
}
.app-date__err { margin: 0; font-size: 12px; color: var(--danger-600, #dc2626); }
</style>
