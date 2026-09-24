<template>
  <ModulePageShell
    :title="isEdit ? '编辑课程' : '新建课程'"
    subtitle="课程为草稿态，保存后可提交两级审核；已启用课程的改动会强制生成新版本"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="goBack">返回</AppButton>
      <AppButton variant="primary" :loading="submitting" :disabled="!canManage" @click="submit">保存课程草稿</AppButton>
    </template>

    <AppInlineAlert v-if="!canManage" type="warning" description="当前身份可查看课程，未获课程维护权限。" />
    <LoadingState v-if="loading" />
    <template v-else>
      <ol class="aa-workflow" aria-label="课程版本办理阶段">
        <li v-for="(step, index) in workflowSteps" :key="step.title" :class="{ 'is-current': index === activeWorkflowIndex, 'is-done': index < activeWorkflowIndex }">
          <span>{{ index < activeWorkflowIndex ? '✓' : index + 1 }}</span>
          <div><strong>{{ step.title }}</strong><small>{{ step.note }}</small></div>
        </li>
      </ol>

      <div class="aa-course-form-layout">
        <AppSectionCard :title="`${isEdit ? '课程版本' : '课程草稿'} · 完整表单`" class="aa-course-form-card">
          <span class="aa-draft-state">{{ isEdit ? statusLabel(loadedCourseStatus) : '尚未提交' }}</span>
          <p class="aa-form-intro">先确认稳定课程身份，再核对学分学时、开课责任与适用范围。保存后从课程档案提交审核。</p>
      <fieldset class="aa-form-group">
        <legend>基本信息</legend>
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
      </div>
      </fieldset>
      <fieldset class="aa-form-group">
        <legend>学分、学时与考核</legend>
      <div class="aa-grid">
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
      </div>
      </fieldset>
      <fieldset class="aa-form-group">
        <legend>开课责任与适用范围</legend>
      <div class="aa-grid">
        <AppFormItem label="开课单位" hint="学院管理员只能选择本学院">
          <AppCollegePicker v-model="form.ownerCollegeId" :options="collegeOptions" clearable />
        </AppFormItem>
        <AppFormItem label="课程负责人" hint="须为本校在职教师">
          <AppTeacherPicker v-model="form.ownerTeacherId" clearable />
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
      </fieldset>
      <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      <div class="aa-actions aa-form-footer">
        <AppButton @click="goBack">取消</AppButton>
        <AppButton @click="submit" :loading="submitting">保存草稿</AppButton>
        <AppButton variant="primary" :loading="submitting" @click="submit">保存课程草稿</AppButton>
      </div>
        </AppSectionCard>

        <aside class="aa-course-form-aside">
          <section class="aa-side-card">
            <h3>启动条件</h3>
            <div class="aa-ready-box">
              <p v-for="item in readinessItems" :key="item.label"><span>{{ item.label }}</span><em :class="`is-${item.tone}`">{{ item.value }}</em></p>
            </div>
            <dl>
              <dt>创建责任</dt><dd>课程负责人 / 开课学院</dd>
              <dt>交给</dt><dd>课程审核岗 → 培养方案编制岗</dd>
            </dl>
          </section>
          <section class="aa-side-card">
            <h3>前后业务</h3>
            <ul class="aa-business-chain">
              <li><strong>课程草稿</strong><span>从正式来源开始</span></li>
              <li><strong>课程审核</strong><span>继续使用既有状态机与权限</span></li>
              <li><strong>版本启用</strong><span>审核通过后才能被方案引用</span></li>
              <li><strong>方案引用</strong><span>按课程身份与具体版本追溯</span></li>
            </ul>
          </section>
        </aside>
      </div>
    </template>
  </ModulePageShell>
</template>

<script>
/** 课程新建/编辑（/admin/academic-affairs/courses/new | /:id/edit）：POST/PUT /academic-affairs/courses。
 * Tier1「新增课程/课程负责人」续工：补齐开课单位/课程负责人/课程简介/适用专业(全校通用)字段，
 * 复用接入统一适配器的 AppTeacherPicker / AppCollegePicker / AppMajorPicker。 */
import { ModulePageShell, LoadingState } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppSectionCard, AppFormItem, AppTextInput, AppNumberInput, AppSelect, AppTextarea,
  AppTeacherPicker, AppCollegePicker, AppMajorPicker, AppInlineAlert
} from '@/components/common'
import { academicAffairsApi, academicAffairsOrgApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { COURSE_CATEGORY, COURSE_NATURE, EXAM_MODE } from '@/modules/academicAffairs/constants/course-program'
import { matchPermission } from '@/config/navPlan'
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
    ModulePageShell, LoadingState, AppButton, AppSectionCard, AppFormItem, AppTextInput, AppNumberInput,
    AppSelect, AppTextarea, AppTeacherPicker, AppCollegePicker, AppMajorPicker, AppInlineAlert
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: false, submitting: false, formError: '', prereqText: '', loadedCourseStatus: 'DRAFT', form: EMPTY(),
      collegeOptions: [], majorOptions: []
    }
  },
  computed: {
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.course.manage') },
    courseId() { return this.$route.params.id },
    isEdit() { return !!this.courseId },
    workflowSteps() {
      return [
        { title: '课程草稿', note: '上游事实可回查' },
        { title: '课程审核', note: '按权限与状态办理' },
        { title: '版本启用', note: '通过后形成稳定版本' },
        { title: '方案引用', note: '按正式状态解锁' }
      ]
    },
    activeWorkflowIndex() {
      return { COLLEGE_REVIEW: 1, ACADEMIC_REVIEW: 1, ENABLED: 2, DISABLED: 2 }[this.loadedCourseStatus] || 0
    },
    readinessItems() {
      return [
        { label: '正式来源对象已选定', value: this.isEdit ? '已确认' : '保存时生成', tone: this.isEdit ? 'pass' : 'pending' },
        { label: '当前身份和范围有明确依据', value: this.canManage ? '已确认' : '无权限', tone: this.canManage ? 'pass' : 'blocked' },
        { label: '版本、状态和材料经过服务端复验', value: this.isEdit ? this.statusLabel(this.loadedCourseStatus) : '提交时复验', tone: 'pending' }
      ]
    },
    categoryOptions() { return Object.keys(COURSE_CATEGORY).map((k) => ({ label: COURSE_CATEGORY[k], value: k })) },
    natureOptions() { return Object.keys(COURSE_NATURE).map((k) => ({ label: COURSE_NATURE[k], value: k })) },
    examModeOptions() { return Object.keys(EXAM_MODE).map((k) => ({ label: EXAM_MODE[k], value: k })) }
  },
  created() {
    this.loadOrgOptions()
    if (this.isEdit) this.loadCourse()
  },
  methods: {
    statusLabel(value) {
      return { DRAFT: '草稿', COLLEGE_REVIEW: '学院审核中', ACADEMIC_REVIEW: '教务审核中', ENABLED: '已启用', DISABLED: '已停用' }[value] || '状态待确认'
    },
    goBack() {
      this.$router.push(this.isEdit ? `/admin/academic-affairs/courses/${this.courseId}` : '/admin/academic-affairs/courses')
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
        this.loadedCourseStatus = d.status || 'DRAFT'
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
      if (this.submitting || !this.canManage) return
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
.aa-workflow { list-style: none; margin: 0 0 16px; padding: 14px 18px; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border: 1px solid var(--border, #d8e1ee); border-radius: 12px; background: #fff; }
.aa-workflow li { position: relative; display: flex; align-items: center; gap: 10px; color: #86909c; }
.aa-workflow li:not(:last-child)::after { content: ''; position: absolute; top: 15px; right: 14px; width: calc(100% - 122px); height: 1px; background: #d8e1ee; }
.aa-workflow li > span { display: grid; place-items: center; width: 30px; height: 30px; border: 1px solid #d8e1ee; border-radius: 50%; background: #fff; font-weight: 700; }
.aa-workflow li div { display: grid; gap: 2px; }
.aa-workflow li strong { color: #4e5969; font-size: 14px; }
.aa-workflow li small { font-size: 12px; }
.aa-workflow li.is-current > span { color: #fff; border-color: var(--primary-600, #2f62c7); background: var(--primary-600, #2f62c7); }
.aa-workflow li.is-current strong { color: #173768; }
.aa-workflow li.is-done > span { color: #2f855a; border-color: #b9dfcc; background: #effaf4; }
.aa-course-form-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 16px; align-items: start; }
.aa-course-form-card { position: relative; min-width: 0; }
.aa-draft-state { position: absolute; top: 22px; right: 22px; color: #a15c08; font-size: 13px; }
.aa-grid { display: grid; grid-template-columns: repeat(2, minmax(240px, 1fr)); gap: 4px 24px; }
.aa-field--full { grid-column: 1 / -1; }
.aa-field--check { align-self: end; }
.aa-check { display: flex; align-items: center; gap: 8px; font-size: 14px; color: var(--text-700, #4e5969); height: 34px; }
.aa-actions { margin-top: 20px; display: flex; gap: 12px; }
.aa-form-footer { justify-content: flex-end; padding: 16px 20px; margin: 20px -20px -20px; border-top: 1px solid #e5ebf3; background: #f5f8fd; }
.aa-course-form-aside { display: grid; gap: 14px; }
.aa-side-card { border: 1px solid var(--border, #d8e1ee); border-radius: 12px; background: #fff; overflow: hidden; }
.aa-side-card h3 { margin: 0; padding: 14px 16px; border-bottom: 1px solid #e5ebf3; color: #1d365f; font-size: 16px; }
.aa-ready-box { margin: 16px; padding: 12px; border: 1px solid #dbe5f2; border-radius: 10px; }
.aa-ready-box p { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin: 0; padding: 8px 0; color: #4e5969; font-size: 13px; }
.aa-ready-box em { flex: 0 0 auto; padding: 3px 7px; border-radius: 5px; background: #fff3dc; color: #a15c08; font-style: normal; }
.aa-ready-box em.is-pass { background: #edf9f2; color: #237a4b; }
.aa-ready-box em.is-blocked { background: #fff0f0; color: #c93434; }
.aa-side-card dl { display: grid; grid-template-columns: 68px 1fr; gap: 8px; margin: 0; padding: 0 16px 16px; font-size: 13px; }
.aa-side-card dt { color: #86909c; }
.aa-side-card dd { margin: 0; color: #4e5969; }
.aa-business-chain { list-style: none; margin: 0; padding: 10px 16px 16px; }
.aa-business-chain li { position: relative; display: grid; gap: 3px; padding: 9px 0 9px 18px; }
.aa-business-chain li::before { content: ''; position: absolute; left: 1px; top: 16px; width: 7px; height: 7px; border-radius: 50%; background: #2f62c7; }
.aa-business-chain li:not(:last-child)::after { content: ''; position: absolute; left: 4px; top: 24px; bottom: -9px; width: 1px; background: #cbd9ed; }
.aa-business-chain strong { color: #1d365f; font-size: 13px; }
.aa-business-chain span { color: #86909c; font-size: 12px; }
@media (max-width: 1180px) { .aa-course-form-layout { grid-template-columns: 1fr; } .aa-course-form-aside { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .aa-workflow { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; } .aa-workflow li::after { display: none; } .aa-grid, .aa-course-form-aside { grid-template-columns: 1fr; } }
</style>
