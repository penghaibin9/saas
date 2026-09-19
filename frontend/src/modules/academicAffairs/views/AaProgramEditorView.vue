<template>
  <AaOpeningPlanDiffView v-if="isOpeningPlan" :ctx="ctx" />
  <ModulePageShell
    v-else
    title="方案完整编制"
    :subtitle="program ? `年级 ${program.gradeYear || '—'} · v${program.version} · ${validation?.conclusion || '等待校验'}` : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="returnToSource">返回来源工作区</AppButton>
      <AppButton :loading="validationLoading" @click="loadValidation">运行校验</AppButton>
      <AppButton @click="$router.push('/admin/academic-affairs/programs/opening-plan')">开课差异</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="program">
      <AaObjectContext :name="program.programName" :identity="[program.gradeYear && (program.gradeYear + '级'), '版本 v' + program.version].filter(Boolean).join(' · ')" :status="statusLabel(program.status)" :owner="program.currentAssigneeName || program.ownerName || ''" source="当前方案的课程、绑定与版本以正式记录为准" />
      <AaOperationReceipt :receipt="receipt" />
      <div class="aa-program-layout">
      <aside class="aa-program-nav">
        <div class="aa-nav-title">编制步骤</div>
        <button v-for="item in steps" :key="item.key" :class="{ active: activeStep === item.key }" @click="activeStep = item.key">
          <span>{{ item.index }}</span><b>{{ item.label }}</b>
        </button>
        <div class="aa-nav-links">
          <button @click="openConsole('creditRequirements')">学分要求</button>
          <button @click="openConsole('graduationRequirements')">毕业要求</button>
          <button @click="openConsole('practiceSegments')">实践环节</button>
          <button @click="openConsole('versions')">版本与变更</button>
        </div>
      </aside>

      <main class="aa-program-main mp-stack">
        <div class="aa-credit-bar">
          <div class="aa-credit-cell"><span>流程状态</span><b><AppStatusTag :type="reviewStatusColor(program.status)" :label="statusLabel(program.status)" dot /></b></div>
          <div class="aa-credit-cell"><span>毕业总学分</span><b>{{ program.totalCredits ?? '未设置' }}</b></div>
          <div class="aa-credit-cell"><span>课程学分</span><b>{{ validation?.courseCreditSum ?? program.creditSum }}</b></div>
          <div class="aa-credit-cell"><span>实践学分</span><b>{{ validation?.practiceCreditSum ?? '—' }}</b></div>
          <div class="aa-credit-cell" :class="qualityClass"><span>质量结论</span><b>{{ validation ? (validation.canSubmit ? '可提交' : `${validation.counts.blocker}项阻断`) : '未校验' }}</b></div>
        </div>

        <AppInlineAlert
          v-if="validation && !validation.canSubmit"
          type="warning"
          title="方案暂不能提交审核"
          :description="`请先处理右侧 ${validation.counts.blocker} 个阻断项；提醒项可在确认制度口径后保留。`"
        />

        <AppSectionCard v-show="activeStep === 'basic'" title="① 基本信息">
          <template #header-extra>
            <button v-if="editable && !showEdit" class="mp-link" @click="openEdit">编辑</button>
          </template>
          <div v-if="editable && showEdit" class="aa-add-panel">
            <input v-model.trim="editForm.programName" class="aa-input aa-input--wide" placeholder="方案名称" />
            <input v-model.number="editForm.totalCredits" type="number" min="0.5" step="0.5" class="aa-input aa-input--sm" placeholder="毕业总学分" />
            <AppButton variant="primary" :disabled="!editForm.programName" :loading="savingEdit" @click="saveEdit">保存</AppButton>
            <AppButton @click="showEdit = false">取消</AppButton>
          </div>
          <div v-else class="aa-facts">
            <div><span>方案名称</span><b>{{ program.programName }}</b></div>
            <div><span>适用年级</span><b>{{ program.gradeYear || '未设置' }}</b></div>
            <div><span>专业ID</span><b>{{ program.majorId || '未设置' }}</b></div>
            <div><span>版本</span><b>v{{ program.version }}</b></div>
          </div>
        </AppSectionCard>

        <AppSectionCard v-show="activeStep === 'courses'" title="② 课程结构">
          <template v-if="editable" #header-extra>
            <button class="mp-link" @click="showAdd = !showAdd">{{ showAdd ? '收起' : '＋ 从课程库添加' }}</button>
          </template>
          <div v-if="showAdd && editable" class="aa-add-panel">
            <AppCoursePicker v-model="addForm.courseId" :remote-search="searchProgramCourses" placeholder="选择已启用课程（显示版本）" @change="onPickCourse" />
            <input v-model.number="addForm.openTermNo" type="number" min="1" max="12" class="aa-input aa-input--sm" placeholder="开课学期" />
            <input v-model.trim="addForm.module" class="aa-input aa-input--sm" placeholder="课程模块" />
            <AppButton variant="primary" :disabled="!canAddCourse" :loading="adding" @click="addCourse">添加</AppButton>
          </div>
          <EmptyState v-if="!program.courses.length" title="方案内暂无课程" description="从课程库添加课程并设置开课学期、模块和学分快照" />
          <div class="aa-table-scroll" role="region" aria-label="数据表格，可横向滚动" tabindex="0" v-else>
<table  class="aa-course-table">
            <thead><tr><th>学期</th><th>模块</th><th>课程</th><th>学分</th><th>校验</th><th>来源</th></tr></thead>
            <tbody>
              <tr v-for="course in program.courses" :key="course.programCourseId" :id="`course-${course.programCourseId}`">
                <td>第 {{ course.openTermNo || '?' }} 学期</td>
                <td>{{ course.module || '未归类' }}</td>
                <td>{{ course.courseName || '未命名课程' }}<small class="aa-course-identity">{{ course.courseCode || '课程代码未提供' }} · {{ course.courseVersion != null ? 'v' + course.courseVersion : '版本未提供' }}</small></td>
                <td>{{ course.credit ?? '未设置' }}</td>
                <td><AppStatusTag :type="!validation ? 'default' : courseIssueCount(course) ? 'danger' : 'success'" :label="!validation ? '未校验' : courseIssueCount(course) ? `${courseIssueCount(course)}项` : '正常'" /></td>
                <td><button v-if="course.courseId" class="mp-link" @click="$router.push({ path: '/admin/academic-affairs/courses/' + course.courseId, query: { returnTo: $route.fullPath } })">课程档案</button><span v-else>来源未提供</span></td>
              </tr>
            </tbody>
          </table>
</div>
        </AppSectionCard>

        <AppSectionCard v-show="activeStep === 'standards'" title="③ 国家标准依据">
          <div v-if="program.nationalStandards?.length" class="aa-standard-list">
            <div v-for="standard in program.nationalStandards" :key="standard.bindingId" class="aa-standard-row">
              <div class="aa-standard-main">
                <b>{{ standard.standardCode }} · {{ standard.title }}</b>
                <small>{{ standard.versionLabel }} · {{ standard.documentType }}<span v-if="standard.isPrimary"> · 主依据</span></small>
                <details v-for="section in standard.relevantSections" :key="section.code" class="aa-standard-section">
                  <summary>{{ section.no }}. {{ section.title }}</summary><pre>{{ section.contentExcerpt }}</pre>
                </details>
              </div>
              <a v-if="standard.sourceUrl" :href="standard.sourceUrl" rel="noopener noreferrer">官方来源</a>
            </div>
          </div>
          <AppInlineAlert v-else type="warning" title="尚未绑定国家教学标准" description="请先在实施与预设中心绑定本专业国家标准；系统只提供依据和校验，不会自动生成课程。" />
          <div class="aa-standard-actions"><AppButton size="small" @click="$router.push('/admin/system/implementation/standards')">打开国家标准库</AppButton></div>
        </AppSectionCard>

        <AppSectionCard v-show="activeStep === 'review'" title="④ 审核、发布与绑定">
          <div class="aa-review-btns">
            <AppButton v-if="canSubmit(program.status) && hasPermission('academicAffairs.program.submit')" variant="primary" :disabled="!validation?.canSubmit" :loading="acting" @click="doSubmit">提交审核</AppButton>
            <template v-if="inReview(program.status) && hasPermission('academicAffairs.program.review')">
              <AppButton variant="primary" @click="openReview('APPROVE')">{{ program.status === 'COLLEGE_REVIEW' ? '学院审核通过' : '教务审核通过' }}</AppButton>
              <AppButton @click="openReview('RETURN')">退回</AppButton>
            </template>
            <template v-if="bindable">
              <input v-model.trim="bindForm.gradeYear" class="aa-input aa-input--sm" placeholder="绑定年级 如2026" maxlength="4" @input="bindForm.classId = ''" />
              <AppClassPicker
                v-model="bindForm.classId"
                class="aa-bind-class"
                :disabled="!/^\d{4}$/.test(bindForm.gradeYear)"
                :query="{ majorId: program.majorId, grade: bindForm.gradeYear, classStatus: 'NORMAL' }"
                placeholder="班级特例（可选）"
                data-scope-hint="留空=专业年级通用；选择班级=仅该班覆盖"
              />
              <AppButton variant="primary" :disabled="!/^\d{4}$/.test(bindForm.gradeYear)" :loading="acting" @click="doBind">{{ bindForm.classId ? '绑定班级特例' : '绑定年级' }}</AppButton>
            </template>
          </div>
          <p class="mp-note">提交前必须通过右侧结构化校验；留空班级时建立专业年级通用绑定，选择班级时仅建立该班特例，其他同专业年级班级继续走通用方案。</p>
        </AppSectionCard>
      </main>

      <aside class="aa-validation-panel">
        <div class="aa-validation-head">
          <div><b>方案校验</b><span v-if="validation">{{ validation.counts.blocker }}阻断 · {{ validation.counts.warning }}提醒</span></div>
          <button class="mp-link" :disabled="validationLoading" @click="loadValidation">刷新</button>
        </div>
        <LoadingState v-if="validationLoading" />
        <ErrorState v-else-if="validationError" :description="validationError" @retry="loadValidation" />
        <div v-else-if="validation" class="aa-issue-list">
          <AppInlineAlert
            :type="validation.canSubmit ? 'success' : 'warning'"
            :title="validation.conclusion"
            :description="`课程 ${validation.courseCount} 门 · 实践 ${validation.practiceCount} 项 · 有效绑定 ${validation.activeBindingCount} 条`"
          />
          <button v-for="issue in validation.issues" :key="`${issue.ruleCode}-${issue.objectId}`" class="aa-issue" :class="`is-${issue.level.toLowerCase()}`" @click="focusIssue(issue)">
            <span>{{ issue.level === 'BLOCKER' ? '阻断' : issue.level === 'WARNING' ? '提醒' : '信息' }}</span>
            <b>{{ issue.message }}</b>
            <small>{{ issue.suggestion }}</small>
          </button>
          <EmptyState v-if="!validation.issues.length" title="校验通过" description="当前没有阻断项或提醒项" />
        </div>
      </aside>
      </div>
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
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppCoursePicker, AppClassPicker, AppInlineAlert } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { programQualityApi } from '@/modules/academicAffairs/api/program-quality.api'
import { REVIEW_STATUS, reviewStatusColor, inReview, canSubmit } from '@/modules/academicAffairs/constants/course-program'
import AaObjectContext from '../components/parallel-a/AaObjectContext.vue'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'
import AaOpeningPlanDiffView from './AaOpeningPlanDiffView.vue'

export default {
  name: 'AaProgramEditorView',
  components: { AaObjectContext, AaOperationReceipt, ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppConfirmDialog, AppCoursePicker, AppClassPicker, AppInlineAlert, AaOpeningPlanDiffView },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', program: null, acting: false,
      validation: null, validationLoading: false, validationError: '',
      activeStep: 'courses', requestRevision: 0, receipt: null, showAdd: false, adding: false,
      addForm: { courseId: '', courseName: '', credit: null, openTermNo: null, module: '' },
      bindForm: { gradeYear: '', classId: '' },
      showEdit: false, savingEdit: false, editForm: { programName: '', totalCredits: null },
      dlg: { visible: false, title: '', type: 'primary', confirmText: '确认', requireReason: false, submitting: false, action: '' },
      steps: [
        { key: 'basic', index: '01', label: '基本信息' },
        { key: 'courses', index: '02', label: '课程结构' },
        { key: 'standards', index: '03', label: '标准依据' },
        { key: 'review', index: '04', label: '审核发布' }
      ]
    }
  },
  computed: {
    programId() { return this.$route.params.id },
    isOpeningPlan() { return String(this.programId) === 'opening-plan' },
    editable() { return this.program && canSubmit(this.program.status) && this.hasPermission('academicAffairs.program.manage') },
    bindable() { return this.program && ['PUBLISHED', 'ENABLED'].includes(this.program.status) && this.hasPermission('academicAffairs.program.publish') },
    qualityClass() { return this.validation?.canSubmit ? 'is-ok' : 'is-warn' },
    canAddCourse() { return Boolean(this.addForm.courseId && this.addForm.openTermNo && this.addForm.module) }
  },
  watch: { programId() { this.requestRevision++; this.program = null; this.validation = null; this.receipt = null; this.showAdd = false; this.showEdit = false; if (!this.isOpeningPlan) this.load() } },
  beforeUnmount() { this.requestRevision++ },
  created() { if (!this.isOpeningPlan) this.load() },
  methods: {
    reviewStatusColor, inReview, canSubmit,
    returnToSource() { const to = this.$route.query.returnTo; this.$router.push(typeof to === 'string' && /^\/admin\/academic-affairs\/(programs|courses)(\/|\?|$)/.test(to) ? to : '/admin/academic-affairs/programs') },
    handleActionError(res, fallback) {
      if (isDeniedResult(res)) { this.requestRevision++; this.program = null; this.validation = null; this.showEdit = false; this.showAdd = false; this.dlg.visible = false; this.receipt = null; this.error = '当前操作权限或数据范围已变化，已清除先前对象内容。'; return }
      this.receipt = { title: isConflictResult(res) ? '业务事实已变化' : '本次办理未确认', object: this.program?.programName || '当前对象', status: isConflictResult(res) ? '请保留输入并重新核对' : '未确认完成', pending: true, next: res.message || fallback }
      toast.error(res.message || fallback)
    },
    hasPermission(key) { return matchPermission(this.ctx.permissionPatterns || [], key) },
    setReceipt(title, next) { this.receipt = { title, object: this.program?.programName || '当前方案', status: this.program ? this.statusLabel(this.program.status) : '正式状态待确认', time: this.program?.updatedAt, pending: !this.program || !!this.error, next } },
    statusLabel(value) { return REVIEW_STATUS[value] || (value ? '待确认' : '') },
    openConsole(tab) { this.$router.push(`/admin/academic-affairs/programs/console?tab=${tab}&programId=${this.programId}`) },
    courseIssueCount(course) {
      if (!this.validation) return 0
      return this.validation.issues.filter(issue => String(issue.objectId) === String(course.programCourseId) && ['courses', 'courseId', 'courseName', 'module', 'credit', 'openTermNo', 'hoursTotal', 'hoursTheory', 'hoursPractice'].includes(issue.fieldPath)).length
    },
    focusIssue(issue) {
      if (issue.fixRoute && !issue.fixRoute.startsWith(`/admin/academic-affairs/programs/${this.programId}`)) {
        this.$router.push(issue.fixRoute)
        return
      }
      if (issue.fieldPath?.startsWith('courses') || issue.fieldPath === 'courseId' || issue.fieldPath === 'module' || issue.fieldPath === 'credit' || issue.fieldPath === 'openTermNo') this.activeStep = 'courses'
      else if (issue.fieldPath === 'nationalStandards') this.activeStep = 'standards'
      else this.activeStep = 'basic'
      this.$nextTick(() => {
        const target = issue.objectId ? document.getElementById(`course-${issue.objectId}`) : null
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'center' })
      })
    },
    async searchProgramCourses(keyword = '') {
      const res = await academicAffairsApi.getCourses({ status: 'ENABLED', keyword, page: 1, pageSize: 50 })
      if (res.code !== 0) return []
      return (res.data?.list || []).map(course => ({
        value: String(course.courseId),
        label: course.courseName,
        desc: [course.courseCode, `v${course.version}`, `${course.credit ?? 0} 学分`].filter(Boolean).join(' · '),
        raw: course
      }))
    },
    onPickCourse(value, items) {
      const item = items?.[0]
      const course = item?.raw || item
      if (course) { this.addForm.courseName = course.courseName; this.addForm.credit = course.credit }
    },
    async addCourse() {
      if (this.adding || !this.canAddCourse || !this.editable) return
      this.adding = true
      const res = await academicAffairsApi.addProgramCourse(this.programId, {
        courseId: this.addForm.courseId,
        courseName: this.addForm.courseName,
        credit: this.addForm.credit != null ? this.addForm.credit : undefined,
        openTermNo: this.addForm.openTermNo,
        module: this.addForm.module
      })
      this.adding = false
      if (res.code === 0) {
        toast.success('已添加课程')
        this.addForm = { courseId: '', courseName: '', credit: null, openTermNo: null, module: '' }
        await this.load()
        this.activeStep = 'courses'
      } else this.handleActionError(res, '添加失败')
    },
    openEdit() {
      this.editForm = { programName: this.program.programName, totalCredits: this.program.totalCredits }
      this.showEdit = true
    },
    async saveEdit() {
      if (this.savingEdit || !this.editForm.programName || !this.editable) return
      this.savingEdit = true
      const res = await academicAffairsApi.updateProgram(this.programId, {
        programName: this.editForm.programName,
        totalCredits: this.editForm.totalCredits != null && this.editForm.totalCredits !== '' ? this.editForm.totalCredits : undefined
      })
      this.savingEdit = false
      if (res.code === 0) { this.showEdit = false; await this.load(); this.setReceipt('草稿保存请求已处理', '继续核验课程结构，提交前重新运行方案校验。') }
      else this.handleActionError(res, '保存失败')
    },
    async loadValidation() {
      if (this.isOpeningPlan) return
      const id = this.programId; const revision = this.requestRevision
      this.validationLoading = true
      this.validationError = ''
      const res = await programQualityApi.validate(id)
      if (id !== this.programId || revision !== this.requestRevision) return
      if (res.code === 0) this.validation = res.data
      else { this.validation = null; this.validationError = res.message || '方案校验失败' }
      this.validationLoading = false
    },
    async doSubmit() {
      if (this.acting || !this.program || !canSubmit(this.program.status) || !this.hasPermission('academicAffairs.program.submit')) return
      const id = this.programId
      this.acting = true
      await this.loadValidation()
      if (id !== this.programId) { this.acting = false; return }
      if (!this.validation?.canSubmit) { this.acting = false; toast.error('请先处理方案阻断项'); return }
      this.acting = true
      const res = await academicAffairsApi.submitProgram(this.programId)
      this.acting = false
      if (res.code === 0) { await this.load(); this.setReceipt('提交请求已处理', '按当前正式状态跟踪学院和教务审核；尚未发布不能生成正式教学任务。') }
      else { this.handleActionError(res, '提交失败'); await this.loadValidation() }
    },
    openReview(action) {
      if (!this.program || !inReview(this.program.status) || !this.hasPermission('academicAffairs.program.review')) return
      this.dlg = { visible: true, action, title: action === 'APPROVE' ? '审核通过' : '退回方案', type: action === 'APPROVE' ? 'primary' : 'warning', confirmText: action === 'APPROVE' ? '确认通过' : '确认退回', requireReason: action === 'RETURN', submitting: false }
    },
    async doReview(payload) {
      if (this.dlg.submitting || !this.program || !inReview(this.program.status) || !this.hasPermission('academicAffairs.program.review')) return
      const reason = payload?.reason || ''
      this.dlg.submitting = true
      const res = await academicAffairsApi.reviewProgram(this.programId, this.dlg.action, reason)
      this.dlg.submitting = false
      if (res.code === 0) { this.dlg.visible = false; await this.load(); this.setReceipt('审核请求已处理', '请核对正式状态；发布后继续设置适用年级，旧版本仍保留。') }
      else this.handleActionError(res, '处理失败')
    },
    async doBind() {
      if (this.acting || !this.bindable || !/^\d{4}$/.test(this.bindForm.gradeYear)) return
      this.acting = true
      const classId = this.bindForm.classId || undefined
      const res = await academicAffairsApi.bindProgramGrade(this.programId, this.bindForm.gradeYear, classId)
      this.acting = false
      if (res.code === 0) {
        toast.success(classId ? `已绑定 ${this.bindForm.gradeYear} 级班级特例` : `已绑定 ${this.bindForm.gradeYear} 级通用方案`)
        this.bindForm = { gradeYear: '', classId: '' }
        await this.load()
      } else this.handleActionError(res, '绑定失败')
    },
    async load() {
      const revision = ++this.requestRevision
      const id = this.programId
      this.loading = true; this.error = ''; this.validationError = ''
      this.program = null; this.validation = null
      try {
        const [programRes, validationRes] = await Promise.all([academicAffairsApi.getProgram(id), programQualityApi.validate(id)])
        if (revision !== this.requestRevision || id !== this.programId) return
        if (programRes.code === 0) this.program = programRes.data
        else this.error = programRes.message || '加载方案失败'
        if (validationRes.code === 0 && this.program) this.validation = validationRes.data
        else this.validationError = validationRes.message || '方案校验失败'
      } catch (error) { if (revision === this.requestRevision) this.error = error?.message || '方案读取失败，请重试' }
      finally { if (revision === this.requestRevision) this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-program-layout { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 16px; align-items: start; }
.aa-program-nav, .aa-validation-panel { position: sticky; top: 16px; padding: 14px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--bg-white, #fff); }
.aa-nav-title { margin-bottom: 10px; font-size: 12px; font-weight: 700; color: var(--text-500, #64748b); }
.aa-program-nav > button { width: 100%; display: flex; align-items: center; gap: 10px; padding: 10px; border: 0; border-radius: 6px; background: transparent; text-align: left; cursor: pointer; }
.aa-program-nav > button span { color: var(--text-400, #94a3b8); font-size: 12px; }
.aa-program-nav > button.active { background: var(--primary-50, #eff6ff); color: var(--primary-700, #1d4ed8); }
.aa-nav-links { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border-200, #e5e7eb); }
.aa-nav-links button { display: block; width: 100%; padding: 7px 4px; border: 0; background: transparent; color: var(--primary-700, #1d4ed8); text-align: left; cursor: pointer; }
.aa-credit-bar { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 1px; overflow: hidden; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--border-200, #e5e7eb); }
.aa-credit-cell { padding: 12px 14px; background: var(--bg-white, #fff); }
.aa-credit-cell span, .aa-credit-cell b { display: block; }
.aa-credit-cell span { font-size: 12px; color: var(--text-500, #64748b); }
.aa-credit-cell b { margin-top: 4px; color: var(--text-900, #1f2937); }
.aa-credit-cell.is-ok b { color: var(--success-700, #047857); }
.aa-credit-cell.is-warn b { color: var(--danger-600, #dc2626); }
.aa-facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.aa-facts > div { padding: 12px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 6px; }
.aa-facts span, .aa-facts b { display: block; }
.aa-facts span { font-size: 12px; color: var(--text-500, #64748b); }
.aa-facts b { margin-top: 4px; }
.aa-add-panel { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.aa-input { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); }
.aa-input--sm { width: 150px; }
.aa-input--wide { min-width: 280px; flex: 1; }
.aa-bind-class { min-width: 260px; }
.aa-course-table { width: 100%; border-collapse: collapse; }
.aa-course-table th, .aa-course-table td { padding: 10px 12px; border-bottom: 1px solid var(--border-200, #e5e7eb); text-align: left; }
.aa-course-table th { font-size: 12px; color: var(--text-500, #64748b); }
.aa-standard-list { display: grid; gap: 12px; }
.aa-standard-row { display: flex; justify-content: space-between; gap: 16px; padding: 12px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 6px; }
.aa-standard-main b, .aa-standard-main small { display: block; }
.aa-standard-main small { margin-top: 4px; color: var(--text-500, #64748b); }
.aa-standard-section { margin-top: 8px; }
.aa-standard-section pre { max-height: 180px; overflow: auto; white-space: pre-wrap; font-family: inherit; }
.aa-standard-actions, .aa-review-btns { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; align-items: center; }
.aa-validation-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.aa-validation-head b, .aa-validation-head span { display: block; }
.aa-validation-head span { margin-top: 3px; font-size: 12px; color: var(--text-500, #64748b); }
.aa-issue-list { display: grid; gap: 8px; max-height: calc(100vh - 170px); overflow: auto; }
.aa-issue { display: block; width: 100%; padding: 10px; border: 1px solid var(--border-200, #e5e7eb); border-left-width: 4px; border-radius: 6px; background: var(--bg-white, #fff); text-align: left; cursor: pointer; }
.aa-issue span { font-size: 12px; font-weight: 700; }
.aa-issue b, .aa-issue small { display: block; margin-top: 4px; }
.aa-issue small { color: var(--text-500, #64748b); line-height: 1.5; }
.aa-issue.is-blocker { border-left-color: var(--danger-500, #ef4444); }
.aa-issue.is-warning { border-left-color: var(--warning-500, #f59e0b); }
.aa-issue.is-info { border-left-color: var(--info-500, #3b82f6); }
@media (max-width: 1200px) { .aa-program-layout { grid-template-columns: 160px minmax(0, 1fr); } .aa-validation-panel { position: static; grid-column: 1 / -1; } }
@media (max-width: 760px) { .aa-program-layout { grid-template-columns: 1fr; } .aa-program-nav { position: static; } .aa-credit-bar { grid-template-columns: repeat(2, minmax(0, 1fr)); } .aa-facts { grid-template-columns: 1fr; } }
.aa-program-nav{grid-column:1/-1;position:static;display:flex;align-items:center;flex-wrap:wrap;gap:6px;padding:0;border:0;background:transparent}.aa-nav-title{display:none}.aa-program-nav>button{width:auto;padding:9px 12px}.aa-program-nav>button span{display:none}.aa-nav-links{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 0 auto;padding:0;border:0}.aa-nav-links button{width:auto}.aa-credit-bar{grid-template-columns:repeat(5,minmax(0,1fr))}.aa-course-identity{display:block;margin-top:5px;font-size:12px;color:var(--text-500,#68788c)}.aa-course-table th{background:var(--primary-50,#edf3fc)}.aa-course-table td{height:54px}.aa-program-main{min-width:0}.aa-table-scroll{max-width:100%;overflow:auto}
@media(max-width:1100px){.aa-program-layout{grid-template-columns:minmax(0,1fr)}.aa-validation-panel{position:static;grid-column:auto}.aa-credit-bar{grid-template-columns:repeat(3,minmax(0,1fr))}}
</style>
