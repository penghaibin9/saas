<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="补考重修 / 免修" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view v-if="applicationNotice" class="card"><text>{{ applicationNotice }}</text><button v-if="pendingApplication" class="btn" @click="load">核对本人记录</button></view>
        <view v-if="showRetake || (showExemption && !resubmitExemptionId)" class="card stack-sm">
          <input v-model="optionKeyword" class="mk__input" placeholder="搜索课程名称或课程代码" @confirm="searchOptions" />
          <button class="btn" :disabled="submitting || !!pendingApplication" @click="searchOptions">查询可申请课程</button>
          <text v-if="targetId" class="mk__sub">当前已定位待办课程。查询可查看其他课程。</text>
          <view class="mk__pages">
            <button v-if="optionPage > 1" class="btn" :disabled="submitting || !!pendingApplication" @click="changeOptionPage(optionPage - 1)">上一页课程</button>
            <text>可选课程第 {{ optionPage }} 页</text>
            <button v-if="opts.retakePagination?.hasMore || opts.exemptionPagination?.hasMore" class="btn" :disabled="submitting || !!pendingApplication" @click="changeOptionPage(optionPage + 1)">下一页课程</button>
          </view>
        </view>
        <view v-if="opts.identityDebtCount" class="mk__debt card">
          <text class="mk__debt-title">有 {{ opts.identityDebtCount }} 条历史成绩需要学校核对课程信息</text>
          <text class="mk__sub">这些成绩暂不能用于重修或免修，请联系教务处处理。</text>
        </view>

        <view class="section-head">
          <text class="section-head__title">我的重修申请</text>
          <text class="section-head__more" @click="toggleForm('retake')">{{ showRetake ? '收起' : '+ 新增报名' }}</text>
        </view>

        <view class="card stack-sm" v-if="showRetake" :class="{ 'is-target': !!targetId }">
          <text class="mk__hint">从本人未通过的正式成绩中选择重修课程。</text>
          <picker mode="selector" :range="retakeLabels" :value="retakeIndex" @change="onRetakePick">
            <view class="mk__input">{{ retakeLabels[retakeIndex] || '请选择挂科成绩' }}</view>
          </picker>
          <textarea :disabled="submitting || !!pendingApplication" class="mk__textarea" v-model="retakeForm.reason" :maxlength="200" placeholder="申请说明（选填）" placeholder-class="mk__ph" />
          <text v-if="retakeForm.gradeId && !retakeAvailable" class="mk__reason">原选成绩已不在当前可申请列表，请重新选择；已填写说明仍保留。</text>
          <button class="btn btn-primary" :disabled="!retakeAvailable || submitting || !!pendingApplication" @click="submitRetake">
            {{ submitting ? '提交中…' : '提交重修报名' }}
          </button>
        </view>

        <view class="list-group" v-if="d.retakes.length">
          <view v-for="r in d.retakes" :key="r.applyId" class="list-row">
            <view class="flex-1">
              <text class="t-md">{{ r.courseName }}</text>
              <text class="mk__sub">{{ r.termCode || '学期待核对' }}{{ r.retakeCount != null ? ' · 第' + r.retakeCount + '次重修' : '' }}</text>
              <text v-if="r.reviewReason" class="mk__reason">{{ r.reviewReason }}</text>
            </view>
            <MobileStatusTag :status="r.status" :label="retakeStatusLabel(r.status)" />
          </view>
        </view>
        <AcademicPageState v-else state="empty" title="暂无重修申请" description="点击右上角从挂科成绩列表报名。" />
        <view v-if="showRetakePagination" class="mk__pages">
          <button v-if="retakePage > 1" class="btn" :disabled="state === 'loading'" @click="changeRetakePage(retakePage - 1)">上一页</button>
          <text>重修申请第 {{ retakePage }}/{{ retakePageCount }} 页，共 {{ d.retakePagination.total }} 条</text>
          <button v-if="d.retakePagination.hasMore" class="btn" :disabled="state === 'loading'" @click="changeRetakePage(retakePage + 1)">下一页</button>
        </view>

        <view class="section-head">
          <text class="section-head__title">我的免修申请</text>
          <text class="section-head__more" @click="toggleForm('exemption')">{{ showExemption ? '收起' : '+ 申请免修' }}</text>
        </view>

        <view class="card stack-sm" v-if="showExemption">
          <text class="mk__hint">{{ resubmitExemptionId ? '请补充或替换材料后重新提交，原申请课程和办理学期不能修改。' : '从学校提供的可申请课程中选择。材料要求请联系教务老师核对。' }}</text>
          <picker mode="selector" :range="exLabels" :value="exIndex" :disabled="!!resubmitExemptionId" @change="onExPick">
            <view class="mk__input">{{ exemptionPickLabel }}</view>
          </picker>
          <textarea :disabled="submitting || !!pendingApplication" class="mk__textarea" v-model="exForm.reason" :maxlength="200" placeholder="免修理由（选填）" placeholder-class="mk__ph" />
          <AcademicMaterials v-if="!readHidden" :key="materialScopeEpoch" :files="materials" purpose="AA_EXEMPTION" :disabled="submitting || !!pendingApplication" @update:files="materials = $event" @busy="materialBusy = $event" @forbidden="clearForbiddenMakeup(); state = 'forbidden'" />
          <text v-if="exForm.courseId && !exemptionAvailable" class="mk__reason">原选课程已不在当前可申请列表，请重新选择；申请内容仍保留。</text>
          <button class="btn btn-primary" :disabled="!exemptionAvailable || submitting || !!pendingApplication || !materialsReady" @click="submitExemption">
            {{ submitting ? '提交中…' : (resubmitExemptionId ? '重新提交免修申请' : '提交免修申请') }}
          </button>
        </view>

        <view class="list-group" v-if="d.exemptions.length">
          <view v-for="e in d.exemptions" :key="e.exemptionId" class="list-row mk__exemption-row">
            <view class="flex-1">
              <text class="t-md">{{ e.courseName }}</text>
              <text class="mk__sub">{{ e.termCode || '—' }}</text>
              <text v-if="e.returnReason" class="mk__reason">退回原因：{{ e.returnReason }}</text>
              <button v-if="e.canResubmit" class="btn btn-ghost mk__resubmit" :disabled="submitting || !!pendingApplication" @click="beginExemptionResubmit(e)">补充材料后重新提交</button>
            </view>
            <MobileStatusTag :status="e.status" :label="exemptionStatusLabel(e.status, e.currentNode)" />
          </view>
        </view>
        <AcademicPageState v-else state="empty" title="暂无免修申请" description="点击右上角选择课程发起免修。" />
        <view v-if="showExemptionPagination" class="mk__pages">
          <button v-if="exemptionPage > 1" class="btn" :disabled="state === 'loading'" @click="changeExemptionPage(exemptionPage - 1)">上一页</button>
          <text>免修申请第 {{ exemptionPage }}/{{ exemptionPageCount }} 页，共 {{ d.exemptionPagination.total }} 条</text>
          <button v-if="d.exemptionPagination.hasMore" class="btn" :disabled="state === 'loading'" @click="changeExemptionPage(exemptionPage + 1)">下一页</button>
        </view>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'
import { academicApplicationPage } from './application-page'
import AcademicMaterials from './AcademicMaterials.vue'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { savePending } from './pending-ledger'

const isForbidden = error => Number(error?.httpStatus || error?.statusCode) === 403 || /^403/.test(String(error?.code || '')) || error?.code === 'NO_PERMISSION'
const PAGE_SIZE = 20
const pageNumber = value => Math.max(1, Number(value) || 1)
const pageCount = page => Math.max(1, Math.ceil(Number(page?.total || 0) / Math.max(1, Number(page?.pageSize || PAGE_SIZE))))

export default {
  components: { AcademicPageNav, AcademicPageState, AcademicMaterials },
mixins: [academicApplicationPage],
  created() { this.applicationScope = 'makeup' },
  data() {
    return {
      d: null, materials: [], materialBusy: false, materialScopeEpoch: 0, academicDraftFields: ['retakeForm', 'exForm', 'showRetake', 'showExemption', 'materials', 'resubmitExemptionId', 'resubmitExemptionCourseId', 'resubmitExemptionCourseName'],
      opts: { retakeOptions: [], exemptionOptions: [], identityDebtCount: 0 },
      state: 'loading', submitting: false,
      showRetake: false, showExemption: false,
      retakeIndex: 0, exIndex: 0,
      retakeForm: { gradeId: '', reason: '' },
      exForm: { courseId: '', reason: '', materialFileIds: [] },
      resubmitExemptionId: '', resubmitExemptionCourseId: '', resubmitExemptionCourseName: '',
      targetId: '', optionPage: 1, optionKeyword: '', appliedOptionKeyword: ''
    }
  },
  computed: {
    retakeAvailable() { return !!this.retakeForm.gradeId && this.opts.retakeOptions.some(row => String(row.gradeId) === String(this.retakeForm.gradeId)) },
    exemptionAvailable() {
      if (this.resubmitExemptionId) return String(this.exForm.courseId || '') === String(this.resubmitExemptionCourseId || '')
      return !!this.exForm.courseId && this.opts.exemptionOptions.some(row => String(row.courseId) === String(this.exForm.courseId))
    },
    materialIds() {
      const ids = this.materials.map(file => String(file?.fileId || '').trim())
      return ids.every(id => /^[1-9]\d*$/.test(id)) && new Set(ids).size === ids.length && this.materials.every(file => file?.readyForBusiness === true) ? ids : null
    },
    materialsReady() { return !this.materialBusy && !!this.materialIds },
    selectedExemption() {
      const selected = this.opts.exemptionOptions.find(row => String(row.courseId) === String(this.exForm.courseId))
      if (selected) return selected
      if (this.resubmitExemptionId && this.exForm.courseId) {
        return { courseId: this.exForm.courseId, courseName: this.resubmitExemptionCourseName || '原免修课程' }
      }
      return null
    },
    exemptionPickLabel() {
      if (this.resubmitExemptionId && this.selectedExemption) return `${this.selectedExemption.courseName || '原免修课程'}（原申请课程）`
      return this.exLabels[this.exIndex] || '请选择课程'
    },
    retakePage() { return pageNumber(this.d?.retakePagination?.page) },
    exemptionPage() { return pageNumber(this.d?.exemptionPagination?.page) },
    retakePageCount() { return pageCount(this.d?.retakePagination) },
    exemptionPageCount() { return pageCount(this.d?.exemptionPagination) },
    showRetakePagination() { return Number(this.d?.retakePagination?.total || 0) > PAGE_SIZE },
    showExemptionPagination() { return Number(this.d?.exemptionPagination?.total || 0) > PAGE_SIZE },
    retakeLabels() {
      const rows = this.opts.retakeOptions || []
      return rows.length
        ? rows.map((x) => [x.courseName, x.termCode, x.courseCode, x.courseVersion != null ? `课程版本${x.courseVersion}` : '', x.attemptNo != null ? `第${x.attemptNo}次修读` : '', x.score != null ? `${x.score}分` : '成绩待核对'].filter(Boolean).join(' · '))
        : ['暂无可报名挂科成绩']
    },
    exLabels() {
      const rows = this.opts.exemptionOptions || []
      return rows.length
        ? rows.map((x) => [x.courseName, x.termCode, x.courseCode, x.courseVersion != null ? `课程版本${x.courseVersion}` : ''].filter(Boolean).join(' · '))
        : ['暂无可申请课程']
    }
  },
  onLoad(options = {}) { this.targetId = String(options.id || ''); this.load() },
  onHide() { this.materialBusy = false; this.materialScopeEpoch++ },
  methods: {
    restorePendingDraft(pending) { if (pending.kind === 'retake') { this.retakeForm = { ...this.retakeForm, ...pending.body }; this.showRetake = true } else { this.exForm = { ...this.exForm, ...pending.body }; this.materials = (pending.body.materialFileIds || []).map(fileId => this.materials.find(file => String(file.fileId) === String(fileId)) || { fileId: String(fileId), readyForBusiness: false }); this.materialScopeEpoch++; this.showExemption = true } },
    clearForbiddenMakeup() {
      const hadPending = this.protectPendingReference()
      this.d = null; this.opts = { retakeOptions: [], exemptionOptions: [], identityDebtCount: 0 }
      this.materials = []; this.materialBusy = false; this.materialScopeEpoch++; this.showRetake = false; this.showExemption = false
      this.retakeForm = { gradeId: '', reason: '' }; this.exForm = { courseId: '', reason: '', materialFileIds: [] }
      this.resubmitExemptionId = ''; this.resubmitExemptionCourseId = ''; this.resubmitExemptionCourseName = ''
      this.targetId = ''; this.submitting = false
      this.applicationNotice = hadPending ? '当前无权核对补考重修记录；本次办理仍待核实。' : ''
      savePending('draft:' + this.applicationScope, null)
    },
    load(requestedPages = {}) {
      let resolvedPages = null
      return this.readAcademic(async () => {
        const identity = currentSessionGeneration(); const epoch = this.readEpoch
        const pending = this.pendingApplication
        const submitPage = pending && !pending.existingId
        const retakePage = pageNumber(requestedPages.retakePage || (submitPage && pending.kind === 'retake' ? 1 : this.d?.retakePagination?.page))
        const exemptionPage = pageNumber(requestedPages.exemptionPage || (submitPage && pending.kind === 'exemption' ? 1 : this.d?.exemptionPagination?.page))
        resolvedPages = { retakePage, exemptionPage }
        try {
          return await Promise.all([
            studentApi.getMyMakeup({ retakePage, retakePageSize: PAGE_SIZE, exemptionPage, exemptionPageSize: PAGE_SIZE }),
            studentApi.getMakeupOptions({ page: this.optionPage, pageSize: PAGE_SIZE,
              keyword: this.appliedOptionKeyword || undefined, gradeId: this.targetId || undefined })
          ])
        }
        catch (error) { if (isForbidden(error) && epoch === this.readEpoch && identity === currentSessionGeneration() && !this.readHidden) this.clearForbiddenMakeup(); throw error }
      }, ([d, opts]) => {
          if (!d || !Array.isArray(d.retakes) || !Array.isArray(d.exemptions) || !opts || !Array.isArray(opts.retakeOptions) || !Array.isArray(opts.exemptionOptions)) throw new Error('补考重修信息无法核对')
          if (opts.retakeOptions.length > PAGE_SIZE || opts.exemptionOptions.length > PAGE_SIZE) throw new Error('可选课程返回过多，请重试')
          const retakePagination = {
            total: Number(d.retakePagination?.total ?? d.retakes.length),
            page: pageNumber(d.retakePagination?.page ?? resolvedPages?.retakePage),
            pageSize: Number(d.retakePagination?.pageSize || PAGE_SIZE),
            hasMore: Boolean(d.retakePagination?.hasMore)
          }
          const exemptionPagination = {
            total: Number(d.exemptionPagination?.total ?? d.exemptions.length),
            page: pageNumber(d.exemptionPagination?.page ?? resolvedPages?.exemptionPage),
            pageSize: Number(d.exemptionPagination?.pageSize || PAGE_SIZE),
            hasMore: Boolean(d.exemptionPagination?.hasMore)
          }
          if (retakePagination.pageSize !== PAGE_SIZE || exemptionPagination.pageSize !== PAGE_SIZE
              || d.retakes.length > PAGE_SIZE || d.exemptions.length > PAGE_SIZE
              || retakePagination.hasMore !== retakePagination.page * PAGE_SIZE < retakePagination.total
              || exemptionPagination.hasMore !== exemptionPagination.page * PAGE_SIZE < exemptionPagination.total) {
            throw new Error('补考重修分页信息无法核对')
          }
          this.d = { ...d, retakes: d.retakes, exemptions: d.exemptions, retakePagination, exemptionPagination }
          this.opts = opts || { retakeOptions: [], exemptionOptions: [], identityDebtCount: 0 }
          this.syncPickDefaults()
          if (this.pendingApplication && this.pendingApplication.kind === 'retake') {
            this.acceptApplication(this.d.retakes, 'applyId', (row, body) => !!this.pendingApplication.returnedId && String(row.originGradeId || '') === String(body.gradeId))
          } else if (this.pendingApplication) {
            this.acceptApplication(this.d.exemptions, 'exemptionId', (row, body) => !!this.pendingApplication.returnedId && String(row.course?.id || row.courseId || '') === String(body.courseId))
          }
        })
    },
    changeRetakePage(page) { return this.load({ retakePage: page, exemptionPage: this.exemptionPage }) },
    changeExemptionPage(page) { return this.load({ retakePage: this.retakePage, exemptionPage: page }) },
    searchOptions() {
      if (this.submitting || this.pendingApplication || this.state !== 'ready') return
      this.appliedOptionKeyword = this.optionKeyword.trim()
      return this.changeOptionPage(1)
    },
    changeOptionPage(page) {
      if (this.submitting || this.pendingApplication || this.state !== 'ready') return
      this.optionPage = page; this.targetId = ''
      this.retakeForm.gradeId = ''
      if (!this.resubmitExemptionId) { this.exForm.courseId = ''; this.materials = []; this.materialScopeEpoch++ }
      return this.load()
    },
    retakeStatusLabel(status) {
      return {
        SUBMITTED: '已提交，等待教务审核',
        APPROVED: '已通过，等待编入教学班',
        ENROLLED: '已编入教学班',
        FINISHED: '重修已完成',
        REJECTED: '重修报名未通过'
      }[String(status || '').toUpperCase()] || ''
    },
    exemptionStatusLabel(status, currentNode) {
      // “退回补材料”沿用 SUBMITTED 状态以保留原审批链，但当前节点才是
      // 学生下一步的真相；不能在手机上误说成“等待教师审核”。
      if (String(currentNode || '').toUpperCase() === 'STUDENT_RESUBMIT') return '已退回，待补充材料'
      return {
        SUBMITTED: '已提交，等待任课教师审核',
        TEACHER_REVIEW: '任课教师审核中',
        COLLEGE_REVIEW: '学院审核中',
        ACADEMIC_REVIEW: '教务终审中',
        APPROVED: '免修已通过',
        REJECTED: '申请未通过',
        CANCELLED: '已取消'
      }[String(status || '').toUpperCase()] || ''
    },
    resetAcademicContext() { this.clearApplicationContext(); this.optionPage = 1; this.optionKeyword = ''; this.appliedOptionKeyword = ''; this.materials = []; this.materialBusy = false; this.materialScopeEpoch++; this.opts = { retakeOptions: [], exemptionOptions: [], identityDebtCount: 0 }; this.targetId = ''; this.retakeForm = { gradeId: '', reason: '' }; this.exForm = { courseId: '', reason: '', materialFileIds: [] }; this.resubmitExemptionId = ''; this.resubmitExemptionCourseId = ''; this.resubmitExemptionCourseName = ''; this.showRetake = false; this.showExemption = false },
    finishApplication(kind) { if (kind === 'retake') { this.retakeForm.reason = ''; this.showRetake = false } else { this.exForm.reason = ''; this.showExemption = false; this.materials = []; this.materialBusy = false; this.materialScopeEpoch++; this.resubmitExemptionId = ''; this.resubmitExemptionCourseId = ''; this.resubmitExemptionCourseName = '' } },
    syncPickDefaults() {
      if (this.retakeForm.gradeId) {
        this.retakeIndex = (this.opts.retakeOptions || []).findIndex(row => String(row.gradeId) === String(this.retakeForm.gradeId))
      } else {
        const rows = this.opts.retakeOptions || []
        const targetIndex = this.targetId
          ? rows.findIndex((row) => String(row.gradeId || row.sourceId || row.acadGradeId || row.id || '') === this.targetId)
          : -1
        this.retakeIndex = targetIndex >= 0 ? targetIndex : 0
        const retake = rows[this.retakeIndex]
        this.retakeForm = { ...this.retakeForm, gradeId: retake?.gradeId || '' }
        if (targetIndex >= 0) this.showRetake = true
      }

      if (this.exForm.courseId) {
        this.exIndex = (this.opts.exemptionOptions || []).findIndex(row => String(row.courseId) === String(this.exForm.courseId))
      } else {
        const exemption = (this.opts.exemptionOptions || [])[0]
        this.exForm = { ...this.exForm, courseId: exemption?.courseId || '', materialFileIds: [] }
        this.exIndex = 0
      }
    },
    onRetakePick(e) {
      if (this.submitting || this.pendingApplication) return
      const index = Number(e.detail.value || 0)
      const row = (this.opts.retakeOptions || [])[index]
      if (!row) return
      this.retakeIndex = index
      this.retakeForm.gradeId = row.gradeId
    },
    onExPick(e) {
      if (this.resubmitExemptionId || this.submitting || this.pendingApplication || this.materialBusy) return
      const index = Number(e.detail.value || 0)
      const row = (this.opts.exemptionOptions || [])[index]
      if (!row) return
      this.exIndex = index
      this.exForm.courseId = row.courseId
      this.materials = []
      this.materialScopeEpoch++
    },
    beginExemptionResubmit(row) {
      if (this.submitting || this.pendingApplication || !row?.canResubmit) return
      const exemptionId = String(row.exemptionId || '')
      const courseId = String(row.course?.id || row.courseId || '')
      if (!/^[1-9]\d*$/.test(exemptionId) || !/^[1-9]\d*$/.test(courseId)) {
        toast('原免修申请课程信息不完整，请联系教务处处理')
        return
      }
      this.resubmitExemptionId = exemptionId
      this.resubmitExemptionCourseId = courseId
      this.resubmitExemptionCourseName = String(row.courseName || row.course?.name || '')
      this.exForm = { courseId, reason: String(row.reason || ''), materialFileIds: [] }
      this.exIndex = (this.opts.exemptionOptions || []).findIndex(item => String(item.courseId) === courseId)
      this.materials = []
      this.materialBusy = false
      this.materialScopeEpoch++
      this.showExemption = true
      this.showRetake = false
    },
    toggleForm(kind) {
      if (this.submitting || this.materialBusy) return
      if (kind === 'retake') {
        this.showRetake = !this.showRetake
        if (this.showRetake) this.showExemption = false
      } else {
        this.showExemption = !this.showExemption
        if (this.showExemption) this.showRetake = false
      }
    },
    submitRetake() {
      if (!this.retakeAvailable || this.submitting || this.pendingApplication) return
      return this.sendApplication({ title: '提交重修报名', kind: 'retake', body: {
        gradeId: this.retakeForm.gradeId,
        reason: this.retakeForm.reason.trim()
      }, send: body => studentApi.applyRetake(body), rows: this.d.retakes, idKey: 'applyId' })
    },
    submitExemption() {
      if (!this.exemptionAvailable || this.submitting || this.pendingApplication || !this.materialsReady || !this.selectedExemption) return
      const isResubmit = !!this.resubmitExemptionId
      const body = {
        courseId: this.exForm.courseId,
        courseName: this.selectedExemption.courseName,
        reason: this.exForm.reason.trim()
      }
      // On a returned application, leaving the picker empty means "keep the
      // original frozen evidence". Selecting new files explicitly replaces it.
      if (!isResubmit || this.materials.length) body.materialFileIds = this.materialIds
      return this.sendApplication({
        title: isResubmit ? '重新提交免修申请' : '提交免修申请',
        kind: 'exemption',
        body,
        existingId: isResubmit ? this.resubmitExemptionId : '',
        send: value => isResubmit
          ? studentApi.resubmitExemption(this.resubmitExemptionId, value)
          : studentApi.applyExemption(value),
        rows: this.d.exemptions,
        idKey: 'exemptionId'
      })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.mk__input { background: var(--bg-elevated, #f5f6f8); border-radius: 8px; padding: 10px 12px; font-size: 14px; }
.mk__textarea { background: var(--bg-elevated, #f5f6f8); border-radius: 8px; padding: 10px 12px; min-height: 72px; width: 100%; box-sizing: border-box; font-size: 14px; }
.mk__ph { color: var(--t4); }
.mk__sub { display: block; color: var(--t3); font-size: 12px; margin-top: 4px; }
.mk__reason { display: block; color: var(--danger, #dc2626); font-size: 12px; margin-top: 4px; }
.mk__hint { display: block; color: var(--t3); font-size: 12px; }
.mk__debt { border: 1px solid var(--warning, #f59e0b); }
.mk__debt-title { display: block; color: var(--warning-dark, #b45309); font-size: 14px; font-weight: 600; }
.mk__pages { display:flex; align-items:center; justify-content:space-between; gap:8px; color:var(--text-tertiary); font-size:12px; }
.mk__pages .btn { margin:0; min-width:72px; }
.mk__resubmit { margin:8px 0 0; min-height:36px; line-height:34px; font-size:12px; }
.is-target { border: 1px solid var(--brand-primary); box-shadow: 0 0 0 2px var(--brand-50); }
</style>
