<template>
  <div class="app-dt" :class="{ 'is-disabled': disabled, 'is-invalid': !!errorText }">
    <label v-if="label" class="app-dt__label">
      {{ label }}<i v-if="required">*</i>
      <span v-if="hint" class="app-dt__hint-inline">{{ hint }}</span>
    </label>
    <div class="app-dt__row">
      <el-config-provider :locale="zhCn">
        <el-date-picker
          type="datetime"
          :model-value="inner || null"
          value-format="YYYY-MM-DD[T]HH:mm"
          time-format="HH:mm"
          :placeholder="placeholder"
          :disabled="disabled"
          :clearable="clearable"
          :disabled-date="disabledDate"
          :aria-label="label || placeholder"
          @update:model-value="onPick"
        />
      </el-config-provider>
    </div>
    <p v-if="errorText" class="app-dt__err">{{ errorText }}</p>
  </div>
</template>

<script>
/**
 * AppDateTimePicker — 日期+时间（YYYY-MM-DDTHH:mm，对齐 datetime-local）。
 * 内部使用 Element Plus DatePicker（datetime 模式，含「此刻/确定」面板），对外 API 与旧版一致；
 * 业务页只允许用本组件，不得直接引 el-date-picker。
 */
import { ElDatePicker, ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/es/components/date-picker/style/css'
import 'element-plus/es/components/config-provider/style/css'
import { toDateTimeInputValue, parseDate, isEmptyDate, formatDate } from '@/utils/dateUtils'

export default {
  name: 'AppDateTimePicker',
  components: { ElDatePicker, ElConfigProvider },
  props: {
    modelValue: { type: [String, Date], default: '' },
    label: { type: String, default: '' },
    hint: { type: String, default: '' },
    placeholder: { type: String, default: '请选择日期时间' },
    required: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    clearable: { type: Boolean, default: true },
    showEmptyHint: { type: Boolean, default: false },
    min: { type: String, default: '' },
    max: { type: String, default: '' },
    endValue: { type: [String, Date], default: '' },
    startValue: { type: [String, Date], default: '' },
    role: { type: String, default: 'single' }
  },
  emits: ['update:modelValue', 'change', 'clear'],
  data() {
    return { zhCn }
  },
  computed: {
    inner() {
      return toDateTimeInputValue(this.modelValue)
    },
    errorText() {
      const cur = parseDate(this.modelValue)
      if (!cur) return ''
      if (this.role === 'start' && !isEmptyDate(this.endValue)) {
        const end = parseDate(this.endValue)
        if (end && cur.getTime() > end.getTime()) return '开始时间不能晚于结束时间'
      }
      if (this.role === 'end' && !isEmptyDate(this.startValue)) {
        const start = parseDate(this.startValue)
        if (start && cur.getTime() < start.getTime()) return '结束时间不能早于开始时间'
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
.app-dt { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.app-dt__label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary, #64748b);
  display: flex; align-items: center; gap: 4px;
}
.app-dt__label i { color: var(--danger-600, #dc2626); font-style: normal; }
.app-dt__hint-inline { font-weight: 400; color: var(--text-tertiary, #94a3b8); margin-left: 4px; }
.app-dt__row { display: flex; align-items: center; min-width: 0; }
.app-dt__row :deep(.el-date-editor.el-input) { --el-date-editor-width: 100%; width: 100%; }
.app-dt.is-invalid :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--danger-600, #dc2626) inset;
}
.app-dt__err { margin: 0; font-size: 12px; color: var(--danger-600, #dc2626); }
</style>
