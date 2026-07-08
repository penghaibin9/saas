/**
 * 公共日期组件底座（V1）
 * 用法：
 *   import { AppDatePicker, AppDateRangePicker, AppDeadlinePicker, AppDateDisplay } from '@/components/common/date'
 *   import * as dateUtils from '@/utils/dateUtils'
 *
 * 规则：
 * - 筛选默认空=全部时间，不清空业务数据
 * - 截止默认 23:59
 * - 空值展示「未设置」，禁止 undefined/null
 * - 页面禁止再手写 date 格式化逻辑
 */
export { default as AppDatePicker } from './AppDatePicker.vue'
export { default as AppDateTimePicker } from './AppDateTimePicker.vue'
export { default as AppDateRangePicker } from './AppDateRangePicker.vue'
export { default as AppDeadlinePicker } from './AppDeadlinePicker.vue'
export { default as AppDateDisplay } from './AppDateDisplay.vue'
