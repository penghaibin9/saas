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
        <label class="aa-field"><span class="req">课程编码</span><input v-model.trim="form.courseCode" class="aa-input" maxlength="30" placeholder="如 CS101" /></label>
        <label class="aa-field"><span class="req">课程名称</span><input v-model.trim="form.courseName" class="aa-input" maxlength="60" /></label>
        <label class="aa-field"><span>英文名称</span><input v-model.trim="form.courseNameEn" class="aa-input" maxlength="120" /></label>
        <label class="aa-field"><span class="req">课程类别</span>
          <select v-model="form.category" class="aa-input">
            <option v-for="(l, v) in COURSE_CATEGORY" :key="v" :value="v">{{ l }}</option>
          </select>
        </label>
        <label class="aa-field"><span class="req">课程性质</span>
          <select v-model="form.nature" class="aa-input">
            <option v-for="(l, v) in COURSE_NATURE" :key="v" :value="v">{{ l }}</option>
          </select>
        </label>
        <label class="aa-field"><span class="req">学分</span><input v-model.number="form.credit" type="number" min="0" step="0.5" class="aa-input" /></label>
        <label class="aa-field"><span>总学时</span><input v-model.number="form.hoursTotal" type="number" min="0" class="aa-input" /></label>
        <label class="aa-field"><span>理论学时</span><input v-model.number="form.hoursTheory" type="number" min="0" class="aa-input" /></label>
        <label class="aa-field"><span>实践学时</span><input v-model.number="form.hoursPractice" type="number" min="0" class="aa-input" /></label>
        <label class="aa-field"><span>实验学时</span><input v-model.number="form.hoursExperiment" type="number" min="0" class="aa-input" /></label>
        <label class="aa-field"><span>上机学时</span><input v-model.number="form.hoursComputer" type="number" min="0" class="aa-input" /></label>
        <label class="aa-field"><span>考核方式</span>
          <select v-model="form.examMode" class="aa-input">
            <option v-for="(l, v) in EXAM_MODE" :key="v" :value="v">{{ l }}</option>
          </select>
        </label>
        <label class="aa-field"><span>先修课程编码</span><input v-model.trim="prereqText" class="aa-input" placeholder="多个用逗号分隔" /></label>
        <label class="aa-field aa-field--check"><input v-model="form.isCore" type="checkbox" /> 核心课程</label>
      </div>
      <div v-if="formError" class="aa-err">{{ formError }}</div>
      <div class="aa-actions">
        <button class="mp-btn" @click="goBack">取消</button>
        <button class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">{{ submitting ? '保存中…' : '保存' }}</button>
      </div>
    </AppSectionCard>
  </ModulePageShell>
</template>

<script>
/** 课程新建/编辑（/admin/academic-affairs/courses/new | /:id/edit）：POST/PUT /academic-affairs/courses。 */
import { ModulePageShell, LoadingState } from '@/components/business'
import { AppSectionCard } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { COURSE_CATEGORY, COURSE_NATURE, EXAM_MODE } from '@/modules/academicAffairs/constants/course-program'
import { toast } from '@/utils/toast'

const EMPTY = () => ({
  courseCode: '', courseName: '', courseNameEn: '', category: 'MAJOR_CORE', nature: 'REQUIRED',
  credit: 0, hoursTotal: null, hoursTheory: null, hoursPractice: null, hoursExperiment: null,
  hoursComputer: null, examMode: 'EXAM', isCore: false, prerequisiteCodes: []
})

export default {
  name: 'AaCourseFormView',
  components: { ModulePageShell, LoadingState, AppSectionCard },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { COURSE_CATEGORY, COURSE_NATURE, EXAM_MODE, loading: false, submitting: false, formError: '', prereqText: '', form: EMPTY() }
  },
  computed: {
    courseId() { return this.$route.params.id },
    isEdit() { return !!this.courseId }
  },
  created() {
    if (this.isEdit) this.loadCourse()
  },
  methods: {
    goBack() {
      this.$router.push(this.isEdit ? `/admin/academic-affairs/courses/${this.courseId}` : '/admin/academic-affairs/courses')
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
          hoursComputer: d.hoursComputer, examMode: d.examMode, isCore: d.isCore,
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
        toast.error(res.message || '保存失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-grid { display: grid; grid-template-columns: repeat(2, minmax(240px, 1fr)); gap: 14px 24px; }
.aa-field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-field--check { flex-direction: row; align-items: center; gap: 8px; }
.aa-field .req::before { content: '*'; color: var(--danger-600, #f53f3f); margin-right: 4px; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-err { margin-top: 12px; color: var(--danger-600, #f53f3f); font-size: 13px; }
.aa-actions { margin-top: 20px; display: flex; gap: 12px; }
</style>
