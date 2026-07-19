<template>
  <div class="app-dr" :class="{ 'is-filter': mode === 'filter' }">
    <label v-if="label" class="app-dr__label">
      {{ label }}<i v-if="required">*</i>
      <span v-if="hint" class="app-dr__hint-inline">{{ hint }}</span>
    </label>

    <div class="app-dr__body">
      <el-config-provider :locale="zhCn">
        <el-date-picker
          :type="withTime ? 'datetimerange' : 'daterange'"
          :model-value="rangeValue"
          :value-format="withTime ? 'YYYY-MM-DD[T]HH:mm' : 'YYYY-MM-DD'"
          time-format="HH:mm"
          range-separator="至"
          :start-placeholder="startPlaceholder"
          :end-placeholder="endPlaceholder"
          :disabled="disabled"
          :clearable="clearable"
          :shortcuts="mode === 'filter' && showShortcuts ? rangeShortcuts : []"
          unlink-panels
          :aria-label="label || emptyLabel"
          @update:model-value="onPick"
        />
      </el-config-provider>

      <p v-if="mode === 'filter' && !hasValue" class="app-dr__empty">{{ emptyLabel }}</p>
      <p v-if="rangeError" class="app-dr__err">{{ rangeError }}</p>
    </div>
  </div>
</template>

<script>
/**
 * AppDateRangePicker — 日期范围。
 * 内部使用 Element Plus DatePicker（daterange 双月面板 + 左侧快捷项侧栏，点两下选完一个区间）。
 * mode=filter：默认空=不限日期（文案「全部时间」），支持快捷项与页面记忆。
 * v-model: { start, end }；对外 API 与旧版一致，业务页不得直接引 el-date-picker。
 */
import { ElDatePicker, ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/es/components/date-picker/style/css'
import 'element-plus/es/components/config-provider/style/css'
import {
  FILTER_SHORTCUTS,
  FILTER_EMPTY_LABEL,
  validateRange,
  isEmptyDate,
  parseDate,
  loadFilterMemory,
  saveFilterMemory,
  clearFilterMemory
} from '@/utils/dateUtils'

export default {
  name: 'AppDateRangePicker',
  components: { ElDatePicker, ElConfigProvider },
  props: {
    modelValue: {
      type: Object,
      default: () => ({ start: '', end: '' })
    },
    label: { type: String, default: '' },
    hint: { type: String, default: '' },
    required: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    clearable: { type: Boolean, default: true },
    withTime: { type: Boolean, default: false },
    /** filter | form */
    mode: { type: String, default: 'filter' },
    emptyLabel: { type: String, default: FILTER_EMPTY_LABEL },
    showShortcuts: { type: Boolean, default: true },
    /** 当前页面记忆 key，如 graduation.students.dateRange */
    memoryKey: { type: String, default: '' },
    restoreMemory: { type: Boolean, default: true }
  },
  emits: ['update:modelValue', 'change', 'clear'],
  data() {
    return { zhCn }
  },
  computed: {
    start() { return (this.modelValue && this.modelValue.start) || '' },
    end() { return (this.modelValue && this.modelValue.end) || '' },
    hasValue() { return !isEmptyDate(this.start) || !isEmptyDate(this.end) },
    rangeValue() {
      return this.hasValue ? [this.start || '', this.end || ''] : null
    },
    startPlaceholder() {
      return this.mode === 'filter' ? this.emptyLabel : '开始日期'
    },
    endPlaceholder() {
      return this.mode === 'filter' ? this.emptyLabel : '结束日期'
    },
    /** FILTER_SHORTCUTS（字符串区间）→ el shortcuts（Date 区间）；「清空」由输入框清空图标承担，不进侧栏 */
    rangeShortcuts() {
      return FILTER_SHORTCUTS.filter((s) => s.key !== 'clear').map((s) => ({
        text: s.label,
        value: () => {
          const r = s.range()
          return [parseDate(r.start) || new Date(), parseDate(r.end) || new Date()]
        }
      }))
    },
    rangeError() {
      const r = validateRange(this.start, this.end)
      return r.ok ? '' : r.message
    }
  },
  created() {
    if (this.restoreMemory && this.memoryKey && this.mode === 'filter' && !this.hasValue) {
      const mem = loadFilterMemory(this.memoryKey)
      if (mem && (mem.start || mem.end)) {
        this.emitValue({ start: mem.start || '', end: mem.end || '' })
      }
    }
  },
  methods: {
    emitValue(next) {
      const v = { start: next.start || '', end: next.end || '' }
      this.$emit('update:modelValue', v)
      this.$emit('change', v)
      if (this.memoryKey && this.mode === 'filter') {
        if (!v.start && !v.end) clearFilterMemory(this.memoryKey)
        else saveFilterMemory(this.memoryKey, v)
      }
    },
    onPick(v) {
      if (!v || !v.length) {
        this.emitValue({ start: '', end: '' })
        this.$emit('clear')
        return
      }
      this.emitValue({ start: v[0] || '', end: v[1] || '' })
    }
  }
}
</script>

<style scoped>
.app-dr { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.app-dr__label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary, #64748b);
  display: flex; align-items: center; gap: 4px;
}
.app-dr__label i { color: var(--danger-600, #dc2626); font-style: normal; }
.app-dr__hint-inline { font-weight: 400; color: var(--text-tertiary, #94a3b8); margin-left: 4px; }
.app-dr__body { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.app-dr__body :deep(.el-date-editor) { max-width: 100%; }
.app-dr__empty { margin: 0; font-size: 12px; color: var(--text-tertiary, #94a3b8); }
.app-dr__err { margin: 0; font-size: 12px; color: var(--danger-600, #dc2626); }
</style>
