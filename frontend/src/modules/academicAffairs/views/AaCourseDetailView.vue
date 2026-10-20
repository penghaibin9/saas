<template>
  <ModulePageShell
    title="课程版本档案"
    :subtitle="course ? (course.courseCode + ' · ' + course.credit + ' 学分') : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="returnToSource">返回来源工作区</AppButton>
      <AppButton v-if="course && editable" @click="$router.push(`/admin/academic-affairs/courses/${courseId}/edit`)">编辑</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="course" class="mp-stack">
      <AaObjectContext :name="course.courseName" :identity="course.courseCode + ' · 版本 v' + course.version" :status="statusLabel(course.status)" :owner="course.ownerTeacherName || ''" source="读取选中课程的稳定身份与具体版本；新版本不改写旧引用" />
      <AaOperationReceipt :receipt="receipt" />
      <div class="aa-a-course-grid">
      <AppSectionCard title="课程信息">
        <AppDescriptionList :items="descItems" :columns="2">
          <template #status="{ item }">
            <AppStatusTag :type="reviewStatusColor(item.raw)" dot>{{ statusLabel(item.raw) }}</AppStatusTag>
          </template>
        </AppDescriptionList>
      </AppSectionCard>

        <AppSectionCard title="版本被哪些业务引用">
          <LoadingState v-if="loadingRefs" /><ErrorState v-else-if="referencesError" :description="referencesError" @retry="loadReferences" />
          <p v-else-if="!references?.length" class="mp-note">当前未查询到培养方案引用；不代表其它业务均无引用。</p>
          <div v-else class="aa-refs"><div v-for="r in references" :key="r.programId"><button class="mp-link" @click="$router.push('/admin/academic-affairs/programs/' + r.programId)">{{ r.programName }}</button><p>版本 {{ r.version ?? '未提供' }} · {{ statusLabel(r.status) }}</p></div></div>
          <p class="mp-note">当前接口提供培养方案引用。教学任务和正式成绩引用证据尚未提供。</p>
        </AppSectionCard>
      </div>
      <AppSectionCard title="审核办理">
        <div class="aa-review-btns">
          <AppButton v-if="canSubmit(course.status) && hasPermission('academicAffairs.course.manage')" variant="primary" :loading="acting" @click="doSubmit">提交审核</AppButton>
          <template v-if="inReview(course.status) && hasPermission('academicAffairs.course.approve')">
            <AppButton variant="primary" @click="openReview('APPROVE')">{{ course.status === 'COLLEGE_REVIEW' ? '学院审核通过' : '教务审核通过' }}</AppButton>
            <AppButton @click="openReview('RETURN')">退回</AppButton>
          </template>
          <span v-if="course.status === 'ENABLED'" class="aa-hint">课程已启用，可被培养方案引用</span>
        </div>
        <p class="mp-note">草稿提交后依次进入学院审核、教务审核，通过后启用。退回时请填写不少于 5 字的修改意见。</p>
      </AppSectionCard>

      <AppSectionCard title="课程材料">
        <LoadingState v-if="materialsLoading" />
        <ErrorState v-else-if="materialsError" :description="materialsError" @retry="loadMaterials" />
        <EmptyState
          v-else-if="!materials.length"
          title="暂无可在线阅读的课程材料"
          description="课程材料附件会在通过文件中心安全校验后显示；无附件的登记项仍在课程材料控制台维护。"
        />
        <div v-else class="aa-material-reader-list">
          <div v-for="material in materials" :key="material.materialId || material.fileId" class="aa-material-reader-item">
            <div class="aa-material-reader-meta">
              <div>
                <strong>{{ material.title || material.fileName }}</strong>
                <span>{{ material.materialTypeLabel || '课程材料' }}<template v-if="material.uploader"> · {{ material.uploader }}</template></span>
              </div>
              <AppStatusTag :type="material.canPreview ? 'success' : 'default'" dot>{{ material.statusText || '状态未知' }}</AppStatusTag>
            </div>
            <FilePreviewer
              :file="material"
              inline
              :provider="materialPreviewProvider"
              :allow-download="material.canDownload"
              :download-handler="downloadCourseMaterial"
              @error="onMaterialPreviewError"
            />
          </div>
        </div>
        <p class="mp-note">选择材料在线阅读；具备下载权限的材料可保存到本地。</p>
      </AppSectionCard>

      <AppSectionCard title="停用管理">
        <div class="aa-review-btns">
          <AppButton v-if="course.status === 'ENABLED' && hasPermission('academicAffairs.course.approve')" :loading="acting" @click="doDisable">停用课程</AppButton>
          <AppButton v-if="course.status === 'DISABLED' && hasPermission('academicAffairs.course.approve')" variant="primary" :loading="acting" @click="doEnable">重新启用</AppButton>
          <AppButton :loading="loadingRefs" @click="loadReferences">查看引用情况</AppButton>
        </div>
        <p class="mp-note">停用前请查看引用情况。仍被审核中、已发布、已启用或已冻结培养方案引用的课程，需要先处理相关引用。</p>
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
 * Tier1「课程停用」续工：新增启用/停用按钮 + 被引用查询（停用被拦截时提示具体方案）。
 * W5 Document Preview：课程材料统一接 FilePreviewer inline Reader；courseId+materialId 业务票据锁住附件关系。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppDescriptionList } from '@/components/common'
import FilePreviewer from '@/components/file/FilePreviewer.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { courseMaterialReaderApi } from '@/modules/academicAffairs/api/course-material-reader.api'
import { REVIEW_STATUS, EXAM_MODE, reviewStatusColor, inReview, canSubmit } from '@/modules/academicAffairs/constants/course-program'
import AaObjectContext from '../components/parallel-a/AaObjectContext.vue'
import AaOperationReceipt from '../components/parallel-a/AaOperationReceipt.vue'
import { isDeniedResult, isConflictResult } from '../components/parallel-a/resultState'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'

export default {
  name: 'AaCourseDetailView',
  components: { AaObjectContext, AaOperationReceipt, ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppConfirmDialog, AppDescriptionList, FilePreviewer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      revision: 0, receipt: null, referencesError: '', loading: true, error: '', course: null, acting: false, loadingRefs: false, references: null,
      materialsLoading: false, materialsError: '', materials: [],
      materialPreviewProvider: null,
      dlg: { visible: false, title: '', type: 'primary', confirmText: '确认', requireReason: false, submitting: false, action: '' }
    }
  },
  computed: {
    courseId() { return this.$route.params.id },
    editable() { return this.course && ['DRAFT', 'RETURNED', 'ENABLED'].includes(this.course.status) && this.hasPermission('academicAffairs.course.manage') },
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
        { label: '总学时', value: `${c.hoursTotal ?? '—'}（理论${c.hoursTheory ?? '未提供'}/实践${c.hoursPractice ?? '未提供'}）` },
        { label: '考核方式', value: this.examLabel(c.examMode) },
        { label: '核心课程', value: c.isCore ? '是' : '否' },
        { label: '课程负责人', value: c.ownerTeacherId ? (c.ownerTeacherName || '负责人姓名未提供') : '未指定' },
        { label: '适用专业', value: this.applicableMajorText },
        { label: '版本', value: 'v' + c.version },
        { label: '先修课程', value: (c.prerequisiteCodes || []).join('、') || '无', span: 2 },
        { label: '课程简介', value: c.description || '无', span: 2 }
      ]
    }
  },
  watch: { courseId() { this.revision++; this.course = null; this.materials = []; this.references = null; this.receipt = null; this.dlg.visible = false; this.materialPreviewProvider = courseMaterialReaderApi.createPreviewProvider(this.courseId); this.load() } },
  beforeUnmount() { this.revision++ },
  created() {
    this.materialPreviewProvider = courseMaterialReaderApi.createPreviewProvider(this.courseId)
    this.load()
  },
  methods: {
    reviewStatusColor, inReview, canSubmit,
    handleActionError(res, fallback) {
      if (isDeniedResult(res)) { this.revision++; this.course = null; this.materials = []; this.references = null; this.dlg.visible = false; this.receipt = null; this.error = '当前操作权限或数据范围已变化，已清除先前对象内容。'; return }
      this.receipt = { title: isConflictResult(res) ? '业务事实已变化' : '本次办理未确认', object: this.course?.courseName || '当前对象', status: isConflictResult(res) ? '请保留输入并重新核对' : '未确认完成', pending: true, next: res.message || fallback }
      toast.error(res.message || fallback)
    },
    hasPermission(key) { return matchPermission(this.ctx.permissionPatterns || [], key) },
    returnToSource() { const to = this.$route.query.returnTo; this.$router.push(typeof to === 'string' && /^\/admin\/academic-affairs\/(programs|courses)(\/|\?|$)/.test(to) ? to : '/admin/academic-affairs/courses') },
    async confirmReadback(title, id) { await this.load(); if (String(id) !== String(this.courseId)) return; this.receipt = { title, object: this.course?.courseName || '当前课程', status: this.course ? this.statusLabel(this.course.status) : '结果待确认', time: this.course?.updatedAt, pending: !this.course || !!this.error, next: '请核对当前版本和正式状态，再继续办理培养方案引用。' } },
    statusLabel(s) { return REVIEW_STATUS[s] || (s ? '状态待确认' : '') },
    examLabel(m) { return EXAM_MODE[m] || m || '' },
    async doSubmit() {
      if (this.acting || !this.course || !['DRAFT','RETURNED'].includes(this.course.status) || !this.hasPermission('academicAffairs.course.manage')) return
      const id = this.courseId
      this.acting = true
      const res = await academicAffairsApi.submitCourse(this.courseId)
      this.acting = false
      if (res.code === 0) { await this.confirmReadback('提交请求已处理', id) }
      else { this.handleActionError(res, '提交失败') }
    },
    async doDisable() {
      if (this.acting || !this.course || !['ENABLED'].includes(this.course.status) || !this.hasPermission('academicAffairs.course.approve')) return
      const id = this.courseId
      this.acting = true
      const res = await academicAffairsApi.disableCourse(this.courseId)
      this.acting = false
      if (res.code === 0) { await this.confirmReadback('停用请求已处理', id) }
      else { this.handleActionError(res, '停用失败（可能仍被培养方案引用）') }
    },
    async doEnable() {
      if (this.acting || !this.course || !['DISABLED'].includes(this.course.status) || !this.hasPermission('academicAffairs.course.approve')) return
      const id = this.courseId
      this.acting = true
      const res = await academicAffairsApi.enableCourse(this.courseId)
      this.acting = false
      if (res.code === 0) { await this.confirmReadback('启用请求已处理', id) }
      else { this.handleActionError(res, '启用失败') }
    },
    async loadReferences() {
      const id = this.courseId; const revision = this.revision
      this.loadingRefs = true; this.referencesError = ''; this.references = null
      try { const res = await academicAffairsApi.getCourseReferences(id); if (revision !== this.revision || id !== this.courseId) return; if (res.code === 0) this.references = res.data.items || []; else this.referencesError = res.message || '引用查询失败' }
      catch (error) { if (revision === this.revision) this.referencesError = error?.message || '引用查询失败' }
      finally { if (revision === this.revision) this.loadingRefs = false }
    },
    async loadMaterials() {
      const id = this.courseId; const revision = this.revision
      this.materialsLoading = true; this.materialsError = ''; this.materials = []
      try { const rows = await courseMaterialReaderApi.list(id); if (revision === this.revision && id === this.courseId) this.materials = rows }
      catch (error) { if (revision === this.revision) this.materialsError = error?.message || '课程材料加载失败' }
      finally { if (revision === this.revision) this.materialsLoading = false }
    },
    downloadCourseMaterial(material) {
      return courseMaterialReaderApi.download(this.courseId, material)
    },
    onMaterialPreviewError(error) {
      toast.error(error?.message || '课程材料预览失败')
    },
    openReview(action) {
      if (!this.course || !inReview(this.course.status) || !this.hasPermission('academicAffairs.course.approve')) return
      this.dlg = {
        visible: true, action,
        title: action === 'APPROVE' ? '审核通过' : '退回课程',
        type: action === 'APPROVE' ? 'primary' : 'warning',
        confirmText: action === 'APPROVE' ? '确认通过' : '确认退回',
        requireReason: action === 'RETURN', submitting: false
      }
    },
    async doReview(payload) {
      if (this.dlg.submitting || !this.course || !inReview(this.course.status) || !this.hasPermission('academicAffairs.course.approve')) return
      const id = this.courseId
      const reason = (payload && payload.reason) || ''
      this.dlg.submitting = true
      const res = await academicAffairsApi.reviewCourse(this.courseId, this.dlg.action, reason)
      this.dlg.submitting = false
      if (res.code === 0) { this.dlg.visible = false; await this.confirmReadback('审核请求已处理', id) }
      else { this.handleActionError(res, '处理失败') }
    },
    async load() {
      const revision = ++this.revision; const id = this.courseId
      this.loading = true; this.error = ''; this.course = null; this.references = null; this.materials = []
      try {
        const res = await academicAffairsApi.getCourse(id)
        if (revision !== this.revision || id !== this.courseId) return
        if (res.code === 0) { this.course = res.data; await Promise.all([this.loadMaterials(), this.loadReferences()]) }
        else this.error = res.message || '课程读取失败'
      } catch (error) { if (revision === this.revision) this.error = error?.message || '课程读取失败，请重试' }
      finally { if (revision === this.revision) this.loading = false }
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
.aa-material-reader-list { display: grid; gap: 14px; }
.aa-material-reader-item { display: grid; gap: 8px; }
.aa-material-reader-meta { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.aa-material-reader-meta > div { min-width: 0; display: grid; gap: 3px; }
.aa-material-reader-meta strong { color: var(--text-900, #1f2329); font-size: 14px; }
.aa-material-reader-meta span { color: var(--text-500, #646a73); font-size: 12px; }
.aa-a-course-grid{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:16px;align-items:start}.aa-a-course-grid>*{min-width:0}.aa-refs p{font-size:12px;color:var(--text-500,#68788c)}.aa-review-btns{flex-wrap:wrap}@media(max-width:1100px){.aa-a-course-grid{grid-template-columns:minmax(0,1fr)}}
</style>
