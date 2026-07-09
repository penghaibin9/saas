/**
 * 高校业务选择器（第三阶段·第三组）
 * 基座 AppRemoteSelect + 12 个实体 Picker（预设包装）+ 组织级联 + 学年/学期。
 * 全部 partial：UI 与调用规范就绪，真实后端由业务方注入 remoteSearch / data。
 */
export { default as AppRemoteSelect } from './AppRemoteSelect.vue'
export { default as AppOrgCascader } from './AppOrgCascader.vue'
export { default as AppAcademicYearPicker } from './AppAcademicYearPicker.vue'
export { default as AppTermPicker } from './AppTermPicker.vue'
export {
  AppStudentPicker,
  AppTeacherPicker,
  AppMentorPicker,
  AppClassPicker,
  AppMajorPicker,
  AppCollegePicker,
  AppCoursePicker,
  AppRolePicker,
  AppTenantPicker,
  AppCompanyPicker,
  AppPositionPicker,
  AppBatchPicker
} from './entityPickers'
