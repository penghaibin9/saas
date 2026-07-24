<template>
  <ModulePageShell
    :title="program ? program.programName : '培养方案'"
    :subtitle="program ? ('年级 ' + (program.gradeYear || '—') + ' · v' + program.version) : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/programs')">返回列表</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="program" class="mp-stack">
      <!-- 学分汇总条 -->
      <div class="aa-credit-bar">
        <div class="aa-credit-cell"><span>状态</span><b><AppStatusTag :type="reviewStatusColor(program.status)" dot>{{ statusLabel(program.status) }}</AppStatusTag></b></div>
        <div class="aa-credit-cell"><span>毕业总学分</span><b>{{ program.totalCredits ?? '未设置' }}</b></div>
        <div class="aa-credit-cell"><span>已排学分</span><b>{{ program.creditSum }}</b></div>
        <div class="aa-credit-cell" :class="gapClass"><span>学分差额</span><b>{{ gapText }}</b></div>
        <button v-if="editable && !showEdit" class="mp-link aa-edit-entry" @click="openEdit">编辑方案信息</button>
      </div>

      <AppSectionCard title="国家标准依据">
        <div v-if="program.nationalStandards?.length" class="aa-standard-list">
          <div v-for="standard in program.nationalStandards" :key="standard.bindingId" class="aa-standard-row">
            <div class="aa-standard-main"><b>{{ standard.standardCode }} · {{ standard.title }}</b><small>{{ standard.versionLabel }} · {{ standard.documentType }}<span v-if="standard.isPrimary"> · 主依据</span></small>
              <details v-for="section in standard.relevantSections" :key="section.code" class="aa-standard-section">
                <summary>{{ section.no }}. {{ section.title }}</summary>
                <pre>{{ section.contentExcerpt }}</pre>
              </details>
            </div>
            <a v-if="standard.sourceUrl" :href="standard.sourceUrl" target="_blank" rel="noopener noreferrer">官方来源</a>
          </div>
        </div>
        <p v-else class="aa-hint">本专业尚未绑定国家教学标准。请先在“系统管理 → 实施与预设中心 → 职业教育国家标准库”绑定；绑定后会自动显示在这里，不会自动生成课程或成绩。</p>
        <div class="aa-standard-actions"><AppButton size="small" @click="$router.push('/admin/system/implementation/standards')">打开国家标准库</AppButton></div>
      </AppSectionCard>

      <!-- 方案基本信息编辑（草稿/退回态可改：名称、毕业总学分） -->
      <AppSectionCard v-if="editable && showEdit" title="编辑方案信息">
        <div class="aa-add-panel">
          <input v-model.trim="editForm.programName" class="aa-input" placeholder="方案名称" />
          <input v-model.number="editForm.totalCredits" type="number" min="0" class="aa-input aa-input--sm" placeholder="毕业总学分" />
          <AppButton variant="primary" :disabled="!editForm.programName" :loading="savingEdit" @click="saveEdit">保存</AppButton>
          <AppButton @click="showEdit = false">取消</AppButton>
        </div>
      </AppSectionCard>

      <!-- 课程明细 -->
      <AppSectionCard title="课程明细">
        <template v-if="editable" #header-extra>
          <button class="mp-link" @click="toggleAdd">{{ showAdd ? '收起' : '＋ 从课程库添加' }}</button>
        </template>

        <div v-if="showAdd && editable" class="aa-add-panel">
          <AppCoursePicker v-model="addForm.courseId" placeholder="选择已启用课程" @change="onPickCourse" />
          <input v-model.number="addForm.openTermNo" type="number" min="1" max="12" class="aa-input aa-input--sm" placeholder="开课学期" />
          <input v-model.trim="addForm.module" class="aa-input aa-input--sm" placeholder="课程模块" />
          <AppButton variant="primary" :disabled="!addForm.courseId" :loading="adding" @click="addCourse">添加</AppButton>
        </div>

        <EmptyState v-if="!program.courses.length" title="方案内暂无课程" description="从课程库添加已启用课程，构建方案课程结构" />
        <table v-else class="aa-course-table">
          <thead><tr><th>开课学期</th><th>课程模块</th><th>课程名称</th><th>学分</th></tr></thead>
          <tbody>
            <tr v-for="c in program.courses" :key="c.programCourseId">
              <td>第 {{ c.openTermNo || '?' }} 学期</td>
              <td>{{ c.module || '—' }}</td>
              <td>{{ c.courseName }}</td>
              <td>{{ c.credit }}</td>
            </tr>
          </tbody>
        </table>
      </AppSectionCard>

      <!-- 审批 / 发布 / 绑定 -->
      <AppSectionCard title="审核与发布">
        <div class="aa-review-btns">
          <AppButton v-if="canSubmit(program.status)" variant="primary" :loading="acting" @click="doSubmit">提交审核</AppButton>
          <template v-if="inReview(program.status)">
            <AppButton variant="primary" @click="openReview('APPROVE')">{{ program.status === 'COLLEGE_REVIEW' ? '学院审核通过' : '教务审核通过' }}</AppButton>
            <AppButton @click="openReview('RETURN')">退回</AppButton>
          </template>
          <template v-if="bindable">
            <input v-model.trim="bindForm.gradeYear" class="aa-input aa-input--sm" placeholder="绑定年级 如2026" />
            <AppButton variant="primary" :disabled="!bindForm.gradeYear" :loading="acting" @click="doBind">绑定年级</AppButton>
          </template>
        </div>
        <p class="mp-note">提交审核前后端会校验学分达标；两级审通过后发布，发布后可绑定年级（旧版本锁定）。</p>
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
/** 培养方案编制器（/admin/academic-affairs/programs/:id）：学分汇总 + 课程明细 + 两级审 + 绑定年级。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppCoursePicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { REVIEW_STATUS, reviewStatusColor, inReview, canSubmit } from '@/modules/academicAffairs/constants/course-program'
import { toast } from '@/utils/toast'

export default {
  name: 'AaProgramEditorView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppConfirmDialog, AppCoursePicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', program: null, acting: false,
      showAdd: false, adding: false,
      addForm: { courseId: '', courseName: '', credit: null, openTermNo: null, module: '' },
      bindForm: { gradeYear: '' },
      showEdit: false, savingEdit: false, editForm: { programName: '', totalCredits: null },
      dlg: { visible: false, title: '', type: 'primary', confirmText: '确认', requireReason: false, submitting: false, action: '' }
    }
  },
  computed: {
    programId() { return this.$route.params.id },
    editable() { return this.program && canSubmit(this.program.status) },
    bindable() { return this.program && ['PUBLISHED', 'ENABLED'].includes(this.program.status) },
    gapText() {
      if (!this.program || this.program.creditGap == null) return '未设置总学分'
      const g = this.program.creditGap
      return g === 0 ? '已达标' : (g > 0 ? `还差 ${g}` : `超出 ${-g}`)
    },
    gapClass() {
      if (!this.program || this.program.creditGap == null) return ''
      return this.program.creditGap === 0 ? 'is-ok' : (this.program.creditGap > 0 ? 'is-warn' : 'is-over')
    }
  },
  created() { this.load() },
  methods: {
    reviewStatusColor, inReview, canSubmit,
    statusLabel(s) { return REVIEW_STATUS[s] || s || '' },
    toggleAdd() {
      this.showAdd = !this.showAdd
    },
    onPickCourse(value, items) {
      const item = items?.[0]
      const c = item?.raw || item
      if (c) { this.addForm.courseName = c.courseName; this.addForm.credit = c.credit }
    },
    async addCourse() {
      if (this.adding || !this.addForm.courseId) return
      this.adding = true
      const res = await academicAffairsApi.addProgramCourse(this.programId, {
        courseId: this.addForm.courseId,
        courseName: this.addForm.courseName,
        credit: this.addForm.credit != null ? this.addForm.credit : undefined,
        openTermNo: this.addForm.openTermNo || undefined,
        module: this.addForm.module || undefined
      })
      this.adding = false
      if (res.code === 0) {
        toast.success('已添加课程')
        this.addForm = { courseId: '', courseName: '', credit: null, openTermNo: null, module: '' }
        this.load()
      } else {
        toast.error(res.message || '添加失败')
      }
    },
    openEdit() {
      this.editForm = { programName: this.program.programName, totalCredits: this.program.totalCredits }
      this.showEdit = true
    },
    async saveEdit() {
      if (this.savingEdit || !this.editForm.programName) return
      this.savingEdit = true
      const res = await academicAffairsApi.updateProgram(this.programId, {
        programName: this.editForm.programName,
        totalCredits: this.editForm.totalCredits != null && this.editForm.totalCredits !== '' ? this.editForm.totalCredits : undefined
      })
      this.savingEdit = false
      if (res.code === 0) { toast.success('已保存'); this.showEdit = false; this.load() }
      else { toast.error(res.message || '保存失败') }
    },
    async doSubmit() {
      if (this.acting) return
      this.acting = true
      const res = await academicAffairsApi.submitProgram(this.programId)
      this.acting = false
      if (res.code === 0) { toast.success('已提交审核'); this.load() }
      else { toast.error(res.message || '提交失败（可能学分未达标）') }
    },
    openReview(action) {
      this.dlg = {
        visible: true, action,
        title: action === 'APPROVE' ? '审核通过' : '退回方案',
        type: action === 'APPROVE' ? 'primary' : 'warning',
        confirmText: action === 'APPROVE' ? '确认通过' : '确认退回',
        requireReason: action === 'RETURN', submitting: false
      }
    },
    async doReview(payload) {
      const reason = (payload && payload.reason) || ''
      this.dlg.submitting = true
      const res = await academicAffairsApi.reviewProgram(this.programId, this.dlg.action, reason)
      this.dlg.submitting = false
      if (res.code === 0) { this.dlg.visible = false; toast.success('已处理'); this.load() }
      else { toast.error(res.message || '处理失败') }
    },
    async doBind() {
      if (this.acting || !this.bindForm.gradeYear) return
      this.acting = true
      const res = await academicAffairsApi.bindProgramGrade(this.programId, this.bindForm.gradeYear)
      this.acting = false
      if (res.code === 0) { toast.success(`已绑定 ${this.bindForm.gradeYear} 级`); this.bindForm.gradeYear = ''; this.load() }
      else { toast.error(res.message || '绑定失败') }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getProgram(this.programId)
      if (res.code === 0) { this.program = res.data }
      else { this.error = res.message }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-credit-bar { display: flex; align-items: center; gap: 32px; padding: 16px 20px; background: var(--fill-50, #f7f8fa); border: 1px solid var(--border-200, #e5e6eb); border-radius: 8px; }
.aa-edit-entry { margin-left: auto; }
.aa-credit-cell { display: flex; flex-direction: column; gap: 4px; }
.aa-credit-cell span { font-size: 12px; color: var(--text-500, #646a73); }
.aa-credit-cell b { font-size: 18px; color: var(--text-900, #1f2329); }
.aa-credit-cell.is-ok b { color: var(--success-600, #16a34a); }
.aa-credit-cell.is-warn b { color: var(--warning-600, #d97706); }
.aa-credit-cell.is-over b { color: var(--danger-600, #f53f3f); }
.aa-standard-list { display: grid; gap: 8px; }
.aa-standard-row { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 10px 12px; border: 1px solid var(--border-100, #f0f1f2); border-radius: 6px; }
.aa-standard-main { flex: 1; min-width: 0; }
.aa-standard-row small { display: block; margin-top: 4px; color: var(--text-400, #8a9099); }
.aa-standard-row a { white-space: nowrap; color: var(--primary-600, #165dff); }
.aa-standard-section { margin-top: 8px; border-top: 1px dashed var(--border-100, #f0f1f2); padding-top: 8px; }
.aa-standard-section summary { cursor: pointer; color: var(--primary-700, #0e42d2); font-weight: 600; }
.aa-standard-section pre { white-space: pre-wrap; word-break: break-word; margin: 8px 0 0; max-height: 260px; overflow: auto; font: inherit; line-height: 1.7; color: var(--text-700, #3c4149); }
.aa-standard-actions { margin-top: 12px; }
.aa-add-panel { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 14px; }
.aa-input { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 120px; }
.aa-hint { color: var(--text-400, #8a9099); font-size: 12px; }
.aa-course-table { width: 100%; border-collapse: collapse; }
.aa-course-table th, .aa-course-table td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }
.aa-course-table th { color: var(--text-500, #646a73); font-weight: 500; font-size: 13px; }
.aa-review-btns { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
</style>
