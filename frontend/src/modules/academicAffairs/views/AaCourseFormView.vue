<template>
  <ModulePageShell
    :title="isEdit ? '编辑课程' : '新建课程'"
    subtitle="课程为草稿态，保存后可提交两级审核；已启用课程的改动会强制生成新版本"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="goBack">返回</button>
    </template>

    <LoadingState v-if="loading" />
    <AppSectionCard v-else title="课程信息">
      <div class="aa-grid">
        <AppFormItem label="课程编码" required hint="大写字母(1-4位)+数字(3-8位)，如 CS101">
          <AppTextInput v-model="form.courseCode" :maxlength="30" placeholder="如 CS101" />
        </AppFormItem>
        <AppFormItem label="课程名称" required>
          <AppTextInput v-model="form.courseName" :maxlength="60" />
        </AppFormItem>
        <AppFormItem label="英文名称">
          <AppTextInput v-model="form.courseNameEn" :maxlength="120" />
        </AppFormItem>
        <AppFormItem label="课程类别" required>
          <AppSelect v-model="form.category" :options="categoryOptions" />
        </AppFormItem>
        <AppFormItem label="课程性质" required>
          <AppSelect v-model="form.nature" :options="natureOptions" />
        </AppFormItem>
        <AppFormItem label="学分" required>
          <AppNumberInput v-model="form.credit" :min="0" :step="0.5" />
        </AppFormItem>
        <AppFormItem label="总学时" hint="留空或与理论+实践+实验+上机之和一致">
          <AppNumberInput v-model="form.hoursTotal" :min="0" />
        </AppFormItem>
        <AppFormItem label="理论学时"><AppNumberInput v-model="form.hoursTheory" :min="0" /></AppFormItem>
        <AppFormItem label="实践学时"><AppNumberInput v-model="form.hoursPractice" :min="0" /></AppFormItem>
        <AppFormItem label="实验学时"><AppNumberInput v-model="form.hoursExperiment" :min="0" /></AppFormItem>
        <AppFormItem label="上机学时"><AppNumberInput v-model="form.hoursComputer" :min="0" /></AppFormItem>
        <AppFormItem label="考核方式">
          <AppSelect v-model="form.examMode" :options="examModeOptions" />
        </AppFormItem>
        <AppFormItem label="开课单位" hint="学院管理员只能选择本学院">
          <AppCollegePicker v-model="form.ownerCollegeId" :options="collegeOptions" clearable />
        </AppFormItem>
        <AppFormItem label="课程负责人" hint="须为本校在职教师">
          <AppTeacherPicker v-model="form.ownerTeacherId" :remote-search="searchTeachers" clearable />
        </AppFormItem>
        <AppFormItem label="先修课程编码">
          <AppTextInput v-model="prereqText" placeholder="多个用逗号分隔" />
        </AppFormItem>
        <AppFormItem label="课程简介" layout="vertical" class="aa-field--full">
          <AppTextarea v-model="form.description" :maxlength="500" :rows="3" placeholder="选填，≤500 字，用于课程库检索与展示" />
        </AppFormItem>
        <AppFormItem label="核心课程" class="aa-field--check">
          <label class="aa-check"><input v-model="form.isCore" type="checkbox" /> 核心课/学位课</label>
        </AppFormItem>
        <AppFormItem label="全校通用" class="aa-field--check" hint="勾选后不可再选具体适用专业">
          <label class="aa-check"><input v-model="form.isAllMajor" type="checkbox" @change="onAllMajorChange" /> 全校各专业通用</label>
        </AppFormItem>
        <AppFormItem label="适用专业" layout="vertical" class="aa-field--full" v-if="!form.isAllMajor">
          <AppMajorPicker v-model="form.applicableMajors" multiple :options="majorOptions" />
        </AppFormItem>
      </div>
      <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      <div class="aa-actions">
        <button class="mp-btn" @click="goBack">取消</button>
        <button class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">{{ submitting ? '保存中…' : '保存' }}</button>
      </div>
    </AppSectionCard>
  </ModulePageShell>
</template>

<script>
/** 课程新建/编辑（/admin/academic-affairs/courses/new | /:id/edit）：POST/PUT /academic-affairs/courses。
 * Tier1「新增课程/课程负责人」续工：补齐开课单位/课程负责人/课程简介/适用专业(全校通用)字段，
 * 复用 AppTeacherPicker（远程搜索真实在职教师）/ AppCollegePicker/AppMajorPicker（本校启用学院专业，静态选项）。 */
import { ModulePageShell, LoadingState } from '@/components/business'
import {
  AppSectionCard, AppFormItem, AppTextInput, AppNumberInput, AppSelect, AppTextarea,
  AppTeacherPicker, AppCollegePicker, AppMajorPicker, AppInlineAlert
} from '@/components/common'
import { academicAffairsApi, academicAffairsOrgApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { COURSE_CATEGORY, COURSE_NATURE, EXAM_MODE } from '@/modules/academicAffairs/constants/course-program'
import { toast } from '@/utils/toast'

const EMPTY = () => ({
  courseCode: '', courseName: '', courseNameEn: '', category: 'MAJOR_CORE', nature: 'REQUIRED',
  credit: 0, hoursTotal: null, hoursTheory: null, hoursPractice: null, hoursExperiment: null,
  hoursComputer: null, examMode: 'EXAM', ownerCollegeId: '', ownerTeacherId: '', isCore: false,
  description: '', isAllMajor: false, applicableMajors: [], prerequisiteCodes: []
})

export default {
  name: 'AaCourseFormView',
  components: {
    ModulePageShell, LoadingState, AppSectionCard, AppFormItem, AppTextInput, AppNumberInput,
    AppSelect, AppTextarea, AppTeacherPicker, AppCollegePicker, AppMajorPicker, AppInlineAlert
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: false, submitting: false, formError: '', prereqText: '', form: EMPTY(),
      collegeOptions: [], majorOptions: []
    }
  },
  computed: {
    courseId() { return this.$route.params.id },
    isEdit() { return !!this.courseId },
    categoryOptions() { return Object.keys(COURSE_CATEGORY).map((k) => ({ label: COURSE_CATEGORY[k], value: k })) },
    natureOptions() { return Object.keys(COURSE_NATURE).map((k) => ({ label: COURSE_NATURE[k], value: k })) },
    examModeOptions() { return Object.keys(EXAM_MODE).map((k) => ({ label: EXAM_MODE[k], value: k })) }
  },
  created() {
    this.loadOrgOptions()
    if (this.isEdit) this.loadCourse()
  },
  methods: {
    goBack() {
      this.$router.push(this.isEdit ? `/admin/academic-affairs/courses/${this.courseId}` : '/admin/academic-affairs/courses')
    },
    async searchTeachers(keyword) {
      const res = await academicAffairsApi.searchCourseTeachers(keyword)
      return res.code === 0 ? (res.data.items || []) : []
    },
    async loadOrgOptions() {
      const [colRes, majRes] = await Promise.all([
        academicAffairsOrgApi.listColleges({ page: 1, pageSize: 200 }),
        academicAffairsOrgApi.listMajors({ page: 1, pageSize: 500 })
      ])
      if (colRes.code === 0) {
        this.collegeOptions = (colRes.data.list || [])
          .filter((c) => c.status === 'ACTIVE')
          .map((c) => ({ label: c.collegeName, value: c.id }))
      }
      if (majRes.code === 0) {
        this.majorOptions = (majRes.data.list || [])
          .filter((m) => m.status === 'ACTIVE')
          .map((m) => ({ label: `${m.majorName}${m.collegeName ? '（' + m.collegeName + '）' : ''}`, value: m.id }))
      }
    },
    onAllMajorChange() {
      if (this.form.isAllMajor) this.form.applicableMajors = []
    },
    async loadCourse() {
      this.loading = true
      const res = await academicAffairsApi.getCourse(this.courseId)
      if (res.code === 0) {
        const d = res.data
        this.form = {
          courseCode: d.courseCode, courseName: d.courseName, courseNameEn: d.courseNameEn,
          category: d.category, nature: d.nature, credit: d.credit, hoursTotal: d.hoursTotal,
          hoursTheory: d.hoursTheory, hoursPractice: d.hoursPractice, hoursExperiment: d.hoursExperiment,
          hoursComputer: d.hoursComputer, examMode: d.examMode, ownerCollegeId: d.ownerCollegeId || '',
          ownerTeacherId: d.ownerTeacherId || '', isCore: d.isCore, description: d.description || '',
          isAllMajor: d.isAllMajor || false, applicableMajors: d.applicableMajors || [],
          prerequisiteCodes: d.prerequisiteCodes || []
        }
        this.prereqText = (d.prerequisiteCodes || []).join(',')
      } else {
        toast.error(res.message || '加载失败')
      }
      this.loading = false
    },
    validate() {
      if (!this.form.courseCode) return '请填写课程编码'
      if (!this.form.courseName) return '请填写课程名称'
      if (this.form.credit == null || this.form.credit < 0) return '学分不能为负'
      if (this.form.isAllMajor && this.form.applicableMajors.length) return '全校通用不能与具体适用专业同时选择'
      return ''
    },
    async submit() {
      if (this.submitting) return
      const err = this.validate()
      this.formError = err
      if (err) return
      this.submitting = true
      const body = {
        ...this.form,
        ownerCollegeId: this.form.ownerCollegeId || undefined,
        ownerTeacherId: this.form.ownerTeacherId || undefined,
        prerequisiteCodes: this.prereqText ? this.prereqText.split(/[,，]/).map((s) => s.trim()).filter(Boolean) : []
      }
      const res = this.isEdit
        ? await academicAffairsApi.updateCourse(this.courseId, body)
        : await academicAffairsApi.createCourse(body)
      this.submitting = false
      if (res.code === 0) {
        toast.success(this.isEdit ? '已保存' : '课程已创建')
        this.$router.push(`/admin/academic-affairs/courses/${res.data.courseId}`)
      } else {
        this.formError = res.message || '保存失败'
        toast.error(res.message || '保存失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-grid { display: grid; grid-template-columns: repeat(2, minmax(240px, 1fr)); gap: 4px 24px; }
.aa-field--full { grid-column: 1 / -1; }
.aa-field--check { align-self: end; }
.aa-check { display: flex; align-items: center; gap: 8px; font-size: 14px; color: var(--text-700, #4e5969); height: 34px; }
.aa-actions { margin-top: 20px; display: flex; gap: 12px; }
</style>
