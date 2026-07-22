/**
 * 高校业务选择器——基于 AppRemoteSelect 的语义包装。
 * 教务中心由布局注入统一适配器，页面只声明实体与 query；其它模块仍可传本地 options 或显式 remoteSearch。
 * 数据范围过滤必须由后端按当前身份返回，前端不得自行放大可见范围。
 *
 * 用法：
 *   <AppStudentPicker v-model="stuId" data-scope-hint="仅本班学生" />
 *   <AppTeacherPicker v-model="ids" multiple :options="teacherOptions" />
 */
import { h } from 'vue'
import AppRemoteSelect from './AppRemoteSelect.vue'

function makePicker(name, presets) {
  return {
    name,
    inheritAttrs: false,
    inject: {
      appPickerAdapters: { default: () => ({}) }
    },
    props: {
      modelValue: { type: [String, Number, Array], default: '' },
      multiple: { type: Boolean, default: false },
      placeholder: { type: String, default: presets.placeholder },
      searchPlaceholder: { type: String, default: presets.searchPlaceholder },
      dataScopeHint: { type: String, default: presets.dataScopeHint || '' },
      options: { type: Array, default: () => [] },
      remoteSearch: { type: Function, default: null },
      resolveByValue: { type: Function, default: null },
      query: { type: Object, default: () => ({}) },
      loadOnOpen: { type: Boolean, default: true }
    },
    emits: ['update:modelValue', 'change', 'search'],
    render() {
      const adapter = this.appPickerAdapters?.[presets.adapterKey || presets.key]
      const search = this.remoteSearch || (!this.options.length && adapter?.search
        ? (keyword) => adapter.search(keyword, this.query)
        : null)
      const resolve = this.resolveByValue || (adapter?.resolve
        ? (value) => adapter.resolve(value, this.query)
        : null)
      return h(AppRemoteSelect, {
        ...this.$attrs,
        modelValue: this.modelValue,
        multiple: this.multiple,
        options: this.options,
        remoteSearch: search,
        resolveByValue: resolve,
        loadOnOpen: this.loadOnOpen,
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
  key: 'student',
  placeholder: '选择学生', searchPlaceholder: '按学号 / 姓名搜索', dataScopeHint: '仅显示你数据范围内的学生'
})
export const AppTeacherPicker = makePicker('AppTeacherPicker', {
  key: 'teacher',
  placeholder: '选择教师', searchPlaceholder: '按工号 / 姓名搜索', dataScopeHint: '按你的管理范围显示教师'
})
export const AppMentorPicker = makePicker('AppMentorPicker', {
  key: 'mentor', adapterKey: 'teacher',
  placeholder: '选择指导教师', searchPlaceholder: '按工号 / 姓名搜索', dataScopeHint: '毕设 / 实习导师库'
})
export const AppClassPicker = makePicker('AppClassPicker', {
  key: 'class',
  placeholder: '选择班级', searchPlaceholder: '按班级名称搜索', dataScopeHint: '仅显示你负责的班级'
})
export const AppMajorPicker = makePicker('AppMajorPicker', {
  key: 'major',
  placeholder: '选择专业', searchPlaceholder: '按专业名称搜索'
})
export const AppCollegePicker = makePicker('AppCollegePicker', {
  key: 'college',
  placeholder: '选择学院', searchPlaceholder: '按学院名称搜索'
})
export const AppCoursePicker = makePicker('AppCoursePicker', {
  key: 'course',
  placeholder: '选择课程', searchPlaceholder: '按课程名 / 课程号搜索'
})
export const AppRolePicker = makePicker('AppRolePicker', {
  key: 'role',
  placeholder: '选择角色', searchPlaceholder: '按角色名称搜索', dataScopeHint: '不能超过你自身权限的角色'
})
export const AppTenantPicker = makePicker('AppTenantPicker', {
  key: 'tenant',
  placeholder: '选择学校 / 租户', searchPlaceholder: '按学校名称搜索', dataScopeHint: '平台级，仅运营方可见'
})
export const AppCompanyPicker = makePicker('AppCompanyPicker', {
  key: 'company',
  placeholder: '选择企业', searchPlaceholder: '按企业名称搜索', dataScopeHint: '实习合作企业库'
})
export const AppPositionPicker = makePicker('AppPositionPicker', {
  key: 'position',
  placeholder: '选择岗位', searchPlaceholder: '按岗位名称搜索', dataScopeHint: '企业岗位库'
})
export const AppBatchPicker = makePicker('AppBatchPicker', {
  key: 'batch',
  placeholder: '选择批次', searchPlaceholder: '按批次名称搜索'
})

export const AppTermEntityPicker = makePicker('AppTermEntityPicker', {
  key: 'termEntity', placeholder: '选择学期', searchPlaceholder: '按学年 / 学期名称搜索'
})
export const AppTermCodePicker = makePicker('AppTermCodePicker', {
  key: 'termCode', placeholder: '选择学期', searchPlaceholder: '按学年 / 学期名称搜索'
})
export const AppTeachingTaskPicker = makePicker('AppTeachingTaskPicker', {
  key: 'teachingTask', placeholder: '选择教学任务', searchPlaceholder: '按课程 / 班级 / 教师搜索'
})
export const AppTeachingClassPicker = makePicker('AppTeachingClassPicker', {
  key: 'teachingClass', placeholder: '选择教学班', searchPlaceholder: '按教学班 / 课程搜索'
})
export const AppClassroomPicker = makePicker('AppClassroomPicker', {
  key: 'classroom', placeholder: '选择教室', searchPlaceholder: '按楼栋 / 教室编号搜索'
})
export const AppLabPicker = makePicker('AppLabPicker', {
  key: 'lab', placeholder: '选择实训室', searchPlaceholder: '按实训室名称 / 编号搜索'
})
export const AppEquipmentPicker = makePicker('AppEquipmentPicker', {
  key: 'equipment', placeholder: '选择设备', searchPlaceholder: '按设备名称 / 资产编号搜索'
})
export const AppTimeSlotPicker = makePicker('AppTimeSlotPicker', {
  key: 'timeSlot', placeholder: '选择节次', searchPlaceholder: '按节次名称 / 序号搜索'
})
export const AppScheduleBatchPicker = makePicker('AppScheduleBatchPicker', {
  key: 'scheduleBatch', placeholder: '选择课表批次', searchPlaceholder: '按批次名称搜索'
})
export const AppGradeTaskPicker = makePicker('AppGradeTaskPicker', {
  key: 'gradeTask', placeholder: '选择成绩录入任务', searchPlaceholder: '按课程 / 班级 / 学期搜索'
})
export const AppGradeRecordPicker = makePicker('AppGradeRecordPicker', {
  key: 'gradeRecord', placeholder: '选择学生成绩记录', searchPlaceholder: '按学生姓名 / 学号搜索'
})
export const AppGraduationBatchPicker = makePicker('AppGraduationBatchPicker', {
  key: 'graduationBatch', placeholder: '选择毕业审核批次', searchPlaceholder: '按批次名称搜索'
})
export const AppRegistrationBatchPicker = makePicker('AppRegistrationBatchPicker', {
  key: 'registrationBatch', placeholder: '选择注册批次', searchPlaceholder: '按批次名称搜索'
})
export const AppExamBatchPicker = makePicker('AppExamBatchPicker', {
  key: 'examBatch', placeholder: '选择考试批次', searchPlaceholder: '按批次名称搜索'
})
export const AppProgramPicker = makePicker('AppProgramPicker', {
  key: 'program', placeholder: '选择培养方案', searchPlaceholder: '按方案名称 / 专业搜索'
})
export const AppSelectionBatchPicker = makePicker('AppSelectionBatchPicker', {
  key: 'selectionBatch', placeholder: '选择选课批次', searchPlaceholder: '按批次名称搜索'
})
export const AppMakeupBatchPicker = makePicker('AppMakeupBatchPicker', {
  key: 'makeupBatch', placeholder: '选择补考批次', searchPlaceholder: '按批次名称 / 学期搜索'
})
export const AppArchiveBatchPicker = makePicker('AppArchiveBatchPicker', {
  key: 'archiveBatch', placeholder: '选择归档批次', searchPlaceholder: '按批次名称 / 学期搜索'
})
export const AppRiskOwnerPicker = makePicker('AppRiskOwnerPicker', {
  key: 'riskOwner', placeholder: '选择风险责任人', searchPlaceholder: '按姓名 / 工号搜索', dataScopeHint: '仅显示可处置学工风险的在职人员'
})
export const AppAidBatchPicker = makePicker('AppAidBatchPicker', {
  key: 'aidBatch', placeholder: '选择困难认定批次', searchPlaceholder: '按批次名称 / 学年搜索'
})
export const AppFundingProjectPicker = makePicker('AppFundingProjectPicker', {
  key: 'fundingProject', placeholder: '选择资助项目', searchPlaceholder: '按项目名称搜索'
})
export const AppFundingBatchPicker = makePicker('AppFundingBatchPicker', {
  key: 'fundingBatch', placeholder: '选择资助批次', searchPlaceholder: '按学年 / 项目搜索'
})
export const AppStudentArchiveBatchPicker = makePicker('AppStudentArchiveBatchPicker', {
  key: 'studentArchiveBatch', placeholder: '选择学生归档批次', searchPlaceholder: '按批次名称 / 年度搜索'
})
export const AppCounselorAssessmentPeriodPicker = makePicker('AppCounselorAssessmentPeriodPicker', {
  key: 'counselorAssessmentPeriod', placeholder: '选择考评周期', searchPlaceholder: '按周期名称搜索'
})
export const AppDormBuildingPicker = makePicker('AppDormBuildingPicker', {
  key: 'dormBuilding', placeholder: '选择宿舍楼栋', searchPlaceholder: '按楼栋名称搜索'
})
export const AppDormRoomPicker = makePicker('AppDormRoomPicker', {
  key: 'dormRoom', placeholder: '选择宿舍房间', searchPlaceholder: '按房间号搜索'
})
export const AppDormBedPicker = makePicker('AppDormBedPicker', {
  key: 'dormBed', placeholder: '选择宿舍床位', searchPlaceholder: '按床位号搜索'
})
export const AppGraduationCandidateStudentPicker = makePicker('AppGraduationCandidateStudentPicker', {
  key: 'candidateStudent', placeholder: '选择学生', searchPlaceholder: '按学号 / 姓名搜索'
})
export const AppGraduationStudentPicker = makePicker('AppGraduationStudentPicker', {
  key: 'graduationStudent', placeholder: '选择毕设学生', searchPlaceholder: '按学号 / 姓名搜索', dataScopeHint: '仅显示当前数据范围内的毕业设计学生'
})
export const AppGraduationMentorPicker = makePicker('AppGraduationMentorPicker', {
  key: 'graduationMentor', placeholder: '选择毕业设计导师', searchPlaceholder: '按工号 / 姓名搜索'
})
export const AppAvailableGraduationMentorPicker = makePicker('AppAvailableGraduationMentorPicker', {
  key: 'availableMentor', placeholder: '选择可分配导师', searchPlaceholder: '按工号 / 姓名搜索', dataScopeHint: '仅显示已认证且未满员的导师'
})
export const AppGraduationDesignBatchPicker = makePicker('AppGraduationDesignBatchPicker', {
  key: 'graduationBatch', placeholder: '选择毕业设计批次', searchPlaceholder: '按批次名称 / 编号搜索'
})
export const AppGraduationTopicPicker = makePicker('AppGraduationTopicPicker', {
  key: 'graduationTopic', placeholder: '选择毕业设计题目', searchPlaceholder: '按题目 / 导师搜索'
})
export const AppDefenseGroupPicker = makePicker('AppDefenseGroupPicker', {
  key: 'defenseGroup', placeholder: '选择答辩组', searchPlaceholder: '按组名 / 日期 / 地点搜索'
})
export const AppInternshipCandidateStudentPicker = makePicker('AppInternshipCandidateStudentPicker', {
  key: 'candidateInternshipStudent', placeholder: '选择学生', searchPlaceholder: '按学号 / 姓名搜索'
})
export const AppInternshipStudentPicker = makePicker('AppInternshipStudentPicker', {
  key: 'internshipStudent', placeholder: '选择实习学生', searchPlaceholder: '按学号 / 姓名搜索'
})
export const AppUnassignedInternshipStudentPicker = makePicker('AppUnassignedInternshipStudentPicker', {
  key: 'unassignedInternshipStudent', placeholder: '选择待匹配学生', searchPlaceholder: '按学号 / 姓名搜索'
})
export const AppInternshipPositionPicker = makePicker('AppInternshipPositionPicker', {
  key: 'internshipPosition', placeholder: '选择已发布岗位', searchPlaceholder: '按岗位 / 企业搜索'
})
export const AppInternshipEnterprisePicker = makePicker('AppInternshipEnterprisePicker', {
  key: 'internshipEnterprise', placeholder: '选择合作企业', searchPlaceholder: '按企业名称搜索'
})
export const AppInternshipAdvisorPicker = makePicker('AppInternshipAdvisorPicker', {
  key: 'internshipAdvisor', placeholder: '选择校内指导教师', searchPlaceholder: '按姓名 / 账号搜索'
})
export const AppInternshipBatchPicker = makePicker('AppInternshipBatchPicker', {
  key: 'internshipBatch', placeholder: '选择实习批次', searchPlaceholder: '按批次名称 / 编号搜索'
})
export const AppEnterpriseMentorPicker = makePicker('AppEnterpriseMentorPicker', {
  key: 'enterpriseMentor', placeholder: '选择企业导师', searchPlaceholder: '按姓名 / 电话搜索'
})
