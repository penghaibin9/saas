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
        <AppDescriptionList :items="descItems" :columns="2">
          <template #status="{ item }">
            <AppStatusTag :type="reviewStatusColor(item.raw)" dot>{{ statusLabel(item.raw) }}</AppStatusTag>
          </template>
        </AppDescriptionList>
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

      <AppSectionCard title="停用管理">
        <div class="aa-review-btns">
          <button v-if="course.status === 'ENABLED'" class="mp-btn" :disabled="acting" @click="doDisable">停用课程</button>
          <button v-if="course.status === 'DISABLED'" class="mp-btn mp-btn--primary" :disabled="acting" @click="doEnable">重新启用</button>
          <button class="mp-btn" :disabled="loadingRefs" @click="loadReferences">{{ loadingRefs ? '查询中…' : '查看引用情况' }}</button>
        </div>
        <p class="mp-note">课程被在途审核中或已发布/启用/冻结的培养方案引用时，停用会被拦截（400）。</p>
        <div v-if="references" class="aa-refs">
          <EmptyState v-if="!references.length" title="暂无培养方案引用该课程" description="" />
          <ul v-else>
            <li v-for="r in references" :key="r.programId">{{ r.programName }} · {{ statusLabel(r.status) }}</li>
          </ul>
        </div>
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="dlg.visible"
      :title="dlg.title"
      :type="dlg.type"
      :confirm-text="dlg.confirmText"
      :require-reason="dlg.requireReason"
      phrase-scene-key="aa.review.return"
      reason-label="审核意见"
      :submitting="dlg.submitting"
      @confirm="doReview"
    />
  </ModulePageShell>
</template>

<script>
/** 课程详情 + 两级审核 + 停用管理（/admin/academic-affairs/courses/:id）。
 * Tier1「课程停用」续工：新增启用/停用按钮 + 被引用查询（停用被拦截时提示具体方案）。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppDescriptionList } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { REVIEW_STATUS, EXAM_MODE, reviewStatusColor, inReview, canSubmit } from '@/modules/academicAffairs/constants/course-program'
import { toast } from '@/utils/toast'

export default {
  name: 'AaCourseDetailView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag, AppConfirmDialog, AppDescriptionList },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', course: null, acting: false, loadingRefs: false, references: null,
      dlg: { visible: false, title: '', type: 'primary', confirmText: '确认', requireReason: false, submitting: false, action: '' }
    }
  },
  computed: {
    courseId() { return this.$route.params.id },
    editable() { return this.course && ['DRAFT', 'RETURNED', 'ENABLED'].includes(this.course.status) },
    applicableMajorText() {
      if (!this.course) return ''
      if (this.course.isAllMajor) return '全校通用'
      const n = (this.course.applicableMajors || []).length
      return n > 0 ? `${n} 个专业` : '未设置'
    },
    descItems() {
      const c = this.course
      if (!c) return []
      return [
        { label: '课程编码', value: c.courseCode },
        { key: 'status', label: '状态', raw: c.status },
        { label: '类别', value: c.categoryLabel },
        { label: '性质', value: c.natureLabel },
        { label: '学分', value: c.credit },
        { label: '总学时', value: `${c.hoursTotal ?? '—'}（理论${c.hoursTheory ?? 0}/实践${c.hoursPractice ?? 0}）` },
        { label: '考核方式', value: this.examLabel(c.examMode) },
        { label: '核心课程', value: c.isCore ? '是' : '否' },
        { label: '课程负责人', value: c.ownerTeacherId ? ('教师 #' + c.ownerTeacherId) : '未指定' },
        { label: '适用专业', value: this.applicableMajorText },
        { label: '版本', value: 'v' + c.version },
        { label: '先修课程', value: (c.prerequisiteCodes || []).join('、') || '无', span: 2 },
        { label: '课程简介', value: c.description || '无', span: 2 }
      ]
    }
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
    async doDisable() {
      if (this.acting) return
      this.acting = true
      const res = await academicAffairsApi.disableCourse(this.courseId)
      this.acting = false
      if (res.code === 0) { toast.success('已停用'); this.load() }
      else { toast.error(res.message || '停用失败（可能仍被培养方案引用）') }
    },
    async doEnable() {
      if (this.acting) return
      this.acting = true
      const res = await academicAffairsApi.enableCourse(this.courseId)
      this.acting = false
      if (res.code === 0) { toast.success('已启用'); this.load() }
      else { toast.error(res.message || '启用失败') }
    },
    async loadReferences() {
      this.loadingRefs = true
      const res = await academicAffairsApi.getCourseReferences(this.courseId)
      this.loadingRefs = false
      if (res.code === 0) this.references = res.data.items || []
      else toast.error(res.message || '查询失败')
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
      this.references = null
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
.aa-refs { margin-top: 12px; }
.aa-refs ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aa-refs li { font-size: 13px; color: var(--text-700, #4e5969); padding: 6px 0; border-bottom: 1px solid var(--border-100, #f0f1f2); }
</style>
