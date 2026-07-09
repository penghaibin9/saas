/**
 * 高校业务选择器（第三阶段·第三组）——基于 AppRemoteSelect 的预设包装。
 *
 * ⚠️ 全部 partial（部分完成）：仅统一 UI 与调用规范（options 本地选项 / remoteSearch 远程搜索预留 /
 *    single 单选 / multiple 多选 / dataScopeHint 数据范围提示）。未接真实后端前不得标 implemented。
 *    数据范围过滤必须由后端按数据范围返回，前端不得自行放大可见范围。
 *
 * 用法：
 *   <AppStudentPicker v-model="stuId" :remote-search="searchStudents" data-scope-hint="仅本班学生" />
 *   <AppTeacherPicker v-model="ids" multiple :options="teacherOptions" />
 */
import { h } from 'vue'
import AppRemoteSelect from './AppRemoteSelect.vue'

function makePicker(name, presets) {
  return {
    name,
    inheritAttrs: false,
    props: {
      modelValue: { type: [String, Number, Array], default: '' },
      multiple: { type: Boolean, default: false },
      placeholder: { type: String, default: presets.placeholder },
      searchPlaceholder: { type: String, default: presets.searchPlaceholder },
      dataScopeHint: { type: String, default: presets.dataScopeHint || '' }
    },
    emits: ['update:modelValue', 'change', 'search'],
    render() {
      return h(AppRemoteSelect, {
        ...this.$attrs,
        modelValue: this.modelValue,
        multiple: this.multiple,
        placeholder: this.placeholder,
        searchPlaceholder: this.searchPlaceholder,
        dataScopeHint: this.dataScopeHint,
        'onUpdate:modelValue': (v) => this.$emit('update:modelValue', v),
        onChange: (v, i) => this.$emit('change', v, i),
        onSearch: (k) => this.$emit('search', k)
      })
    }
  }
}

export const AppStudentPicker = makePicker('AppStudentPicker', {
  placeholder: '选择学生', searchPlaceholder: '按学号 / 姓名搜索', dataScopeHint: '仅显示你数据范围内的学生'
})
export const AppTeacherPicker = makePicker('AppTeacherPicker', {
  placeholder: '选择教师', searchPlaceholder: '按工号 / 姓名搜索', dataScopeHint: '按你的管理范围显示教师'
})
export const AppMentorPicker = makePicker('AppMentorPicker', {
  placeholder: '选择指导教师', searchPlaceholder: '按工号 / 姓名搜索', dataScopeHint: '毕设 / 实习导师库'
})
export const AppClassPicker = makePicker('AppClassPicker', {
  placeholder: '选择班级', searchPlaceholder: '按班级名称搜索', dataScopeHint: '仅显示你负责的班级'
})
export const AppMajorPicker = makePicker('AppMajorPicker', {
  placeholder: '选择专业', searchPlaceholder: '按专业名称搜索'
})
export const AppCollegePicker = makePicker('AppCollegePicker', {
  placeholder: '选择学院', searchPlaceholder: '按学院名称搜索'
})
export const AppCoursePicker = makePicker('AppCoursePicker', {
  placeholder: '选择课程', searchPlaceholder: '按课程名 / 课程号搜索'
})
export const AppRolePicker = makePicker('AppRolePicker', {
  placeholder: '选择角色', searchPlaceholder: '按角色名称搜索', dataScopeHint: '不能超过你自身权限的角色'
})
export const AppTenantPicker = makePicker('AppTenantPicker', {
  placeholder: '选择学校 / 租户', searchPlaceholder: '按学校名称搜索', dataScopeHint: '平台级，仅运营方可见'
})
export const AppCompanyPicker = makePicker('AppCompanyPicker', {
  placeholder: '选择企业', searchPlaceholder: '按企业名称搜索', dataScopeHint: '实习合作企业库'
})
export const AppPositionPicker = makePicker('AppPositionPicker', {
  placeholder: '选择岗位', searchPlaceholder: '按岗位名称搜索', dataScopeHint: '企业岗位库'
})
export const AppBatchPicker = makePicker('AppBatchPicker', {
  placeholder: '选择批次', searchPlaceholder: '按批次名称搜索'
})
