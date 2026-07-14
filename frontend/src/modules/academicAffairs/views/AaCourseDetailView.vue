<template>
  <ModulePageShell
    :title="course ? course.courseName : '课程详情'"
    :subtitle="course ? (course.courseCode + ' · ' + course.credit + ' 学分') : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/courses')">返回列表</button>
      <button v-if="course && editable" class="mp-btn" @click="$router.push(`/admin/academic-affairs/courses/${courseId}/edit`)">编辑</button>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="course" class="mp-stack">
      <AppSectionCard title="课程信息">
        <div class="aa-kv-grid">
          <div class="aa-kv"><span>课程编码</span><b>{{ course.courseCode }}</b></div>
          <div class="aa-kv"><span>状态</span><b><AppStatusTag :type="reviewStatusColor(course.status)" dot>{{ statusLabel(course.status) }}</AppStatusTag></b></div>
          <div class="aa-kv"><span>类别</span><b>{{ course.categoryLabel }}</b></div>
          <div class="aa-kv"><span>性质</span><b>{{ course.natureLabel }}</b></div>
          <div class="aa-kv"><span>学分</span><b>{{ course.credit }}</b></div>
          <div class="aa-kv"><span>总学时</span><b>{{ course.hoursTotal ?? '—' }}（理论{{ course.hoursTheory ?? 0 }}/实践{{ course.hoursPractice ?? 0 }}）</b></div>
          <div class="aa-kv"><span>考核方式</span><b>{{ examLabel(course.examMode) }}</b></div>
          <div class="aa-kv"><span>核心课程</span><b>{{ course.isCore ? '是' : '否' }}</b></div>
          <div class="aa-kv"><span>版本</span><b>v{{ course.version }}</b></div>
          <div class="aa-kv aa-kv--full"><span>先修课程</span><b>{{ (course.prerequisiteCodes || []).join('、') || '无' }}</b></div>
        </div>
      </AppSectionCard>

      <AppSectionCard title="审核操作">
        <div class="aa-review-btns">
          <button v-if="canSubmit(course.status)" class="mp-btn mp-btn--primary" :disabled="acting" @click="doSubmit">提交审核</button>
          <template v-if="inReview(course.status)">
            <button class="mp-btn mp-btn--primary" @click="openReview('APPROVE')">{{ course.status === 'COLLEGE_REVIEW' ? '学院审核通过' : '教务审核通过' }}</button>
            <button class="mp-btn" @click="openReview('RETURN')">退回</button>
          </template>
          <span v-if="course.status === 'ENABLED'" class="aa-hint">课程已启用，可被培养方案引用</span>
        </div>
        <p class="mp-note">两级审核：草稿提交后进入学院审核 → 教务审核 → 启用。退回原因必填不少于 5 字。</p>
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="dlg.visible"
      :title="dlg.title"
      :type="dlg.type"
      :confirm-text="dlg.confirmText"
      :require-reason="dlg.requireReason"
      reason-label="审核意见"
      :submitting="dlg.submitting"
      @confirm="doReview"
    />
  </ModulePageShell>
</template>

<script>
/** 课程详情 + 两级审核（/admin/academic-affairs/courses/:id）。 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { REVIEW_STATUS, EXAM_MODE, reviewStatusColor, inReview, canSubmit } from '@/modules/academicAffairs/constants/course-program'
import { toast } from '@/utils/toast'

export default {
  name: 'AaCourseDetailView',
  components: { ModulePageShell, LoadingState, ErrorState, AppSectionCard, AppStatusTag, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', course: null, acting: false,
      dlg: { visible: false, title: '', type: 'primary', confirmText: '确认', requireReason: false, submitting: false, action: '' }
    }
  },
  computed: {
    courseId() { return this.$route.params.id },
    editable() { return this.course && ['DRAFT', 'RETURNED', 'ENABLED'].includes(this.course.status) }
  },
  created() { this.load() },
  methods: {
    reviewStatusColor, inReview, canSubmit,
    statusLabel(s) { return REVIEW_STATUS[s] || s || '' },
    examLabel(m) { return EXAM_MODE[m] || m || '' },
    async doSubmit() {
      if (this.acting) return
      this.acting = true
      const res = await academicAffairsApi.submitCourse(this.courseId)
      this.acting = false
      if (res.code === 0) { toast.success('已提交学院审核'); this.load() }
      else { toast.error(res.message || '提交失败') }
    },
    openReview(action) {
      this.dlg = {
        visible: true, action,
        title: action === 'APPROVE' ? '审核通过' : '退回课程',
        type: action === 'APPROVE' ? 'primary' : 'warning',
        confirmText: action === 'APPROVE' ? '确认通过' : '确认退回',
        requireReason: action === 'RETURN', submitting: false
      }
    },
    async doReview(payload) {
      const reason = (payload && payload.reason) || ''
      this.dlg.submitting = true
      const res = await academicAffairsApi.reviewCourse(this.courseId, this.dlg.action, reason)
      this.dlg.submitting = false
      if (res.code === 0) { this.dlg.visible = false; toast.success('已处理'); this.load() }
      else { toast.error(res.message || '处理失败') }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getCourse(this.courseId)
      if (res.code === 0) { this.course = res.data }
      else { this.error = res.message }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-kv-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px 24px; }
.aa-kv { display: flex; gap: 12px; font-size: 14px; }
.aa-kv--full { grid-column: 1 / -1; }
.aa-kv span { color: var(--text-500, #646a73); min-width: 72px; }
.aa-kv b { color: var(--text-900, #1f2329); font-weight: 500; }
.aa-review-btns { display: flex; gap: 12px; align-items: center; }
.aa-hint { color: var(--success-600, #16a34a); font-size: 13px; }
</style>
