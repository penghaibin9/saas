<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="成绩认定/课程替代" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view v-if="applicationNotice" class="card"><text>{{ applicationNotice }}</text><button v-if="pendingApplication" class="btn" @click="load">核对本人记录</button></view>
        <view class="section-head">
          <text class="section-head__title">我的认定申请</text>
          <text class="section-head__more" @click="toggleForm">{{ showForm ? '收起' : '+ 新增申请' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <text class="rg__group">校外/原修课程</text>
          <input :disabled="submitting || !!pendingApplication" class="rg__input" v-model="form.sourceCourseName" placeholder="原课程名称（必填）" placeholder-class="rg__ph" />
          <view class="rg__row">
            <input :disabled="submitting || !!pendingApplication" class="rg__input rg__half" type="number" v-model="form.sourceScore" placeholder="原成绩（≥60）" placeholder-class="rg__ph" />
            <input :disabled="submitting || !!pendingApplication" class="rg__input rg__half" type="digit" v-model="form.sourceCredit" placeholder="原学分" placeholder-class="rg__ph" />
          </view>
          <input :disabled="submitting || !!pendingApplication" class="rg__input" v-model="form.sourceOrigin" placeholder="来源说明（原专业/原学校/证书折算）" placeholder-class="rg__ph" />
          <text class="rg__group">替代的校内计划课程</text>
          <view class="rg__search"><input :disabled="submitting || !!pendingApplication" class="rg__input" v-model.trim="courseKeyword" placeholder="按课程名称或代码搜索" placeholder-class="rg__ph" @confirm="searchCourses" /><button class="btn" :disabled="courseLoading" @click="searchCourses">搜索</button></view>
          <view v-if="courseError" class="rg__course-state"><text>{{ courseError }}</text><button class="btn btn-ghost" @click="loadRecognitionCourses(false)">重试</button></view>
          <view v-else-if="courseLoading && !courseOptions.length" class="rg__course-state"><text>正在读取本人培养计划课程…</text></view>
          <view v-else-if="courseOptions.length" class="rg__courses">
            <view v-for="course in courseOptions" :key="course.courseId" :class="['rg__course', { 'is-selected': form.targetCourseId === course.courseId }]" @click="selectCourse(course)">
              <text class="t-md">{{ course.courseCode }} · {{ course.courseName }}</text><text class="rg__sub">{{ course.version || '培养方案版本未标注' }}</text>
            </view>
            <button v-if="courseOptions.length < courseTotal" class="btn" :disabled="courseLoading" @click="loadRecognitionCourses(true)">{{ courseLoading ? '读取中…' : '加载更多课程' }}</button>
          </view>
          <view v-else class="rg__course-state"><text>没有可用于本次认定的培养计划课程。可调整关键词重试，或联系教务老师核对培养方案。</text></view>
          <view class="rg__target"><text>{{ selectedCourse ? selectedCourse.courseCode + ' · ' + selectedCourse.courseName + ' · ' + (selectedCourse.version || '版本未标注') : '尚未选择目标课程' }}</text></view><text class="rg__sub">提交使用所选课程的正式 ID；课程名称与版本只帮助你核对，不按同名课程猜测。</text>
          <textarea :disabled="submitting || !!pendingApplication" class="rg__textarea" v-model="form.reason" :maxlength="200" placeholder="申请理由（选填）" placeholder-class="rg__ph" />
          <AcademicMaterials v-if="!readHidden" :key="materialScopeEpoch" :files="materials" purpose="AA_RECOGNITION" :disabled="submitting || !!pendingApplication" @update:files="materials = $event" @busy="materialBusy = $event" @forbidden="clearForbiddenRecognition(); state = 'forbidden'" />
          <button class="btn btn-primary" :disabled="!canSubmit || submitting || !!pendingApplication" @click="submit">
            {{ submitting ? '提交中…' : '提交认定申请' }}
          </button>
        </view>

        <view class="list-group" v-if="d.items && d.items.length">
          <view v-for="r in d.items" :key="r.recognitionId" class="list-row rg__item">
            <view class="flex-1">
              <text class="t-md">{{ r.sourceCourseName }} → {{ r.targetCourseName }}</text>
              <text class="rg__sub">{{ r.sourceScore }} 分 · {{ r.sourceCredit != null ? r.sourceCredit + ' 学分' : '学分未填' }} · {{ r.sourceOrigin || '来源未注明' }}</text>
              <text v-if="r.reviewReason && r.status === 'REJECTED'" class="rg__reason">{{ r.reviewReason }}</text>
            </view>
            <MobileStatusTag :status="r.status" />
          </view>
        </view>
        <view v-if="d.total > 0 || historyPage > 1" class="rg__pager">
          <button class="btn rg__pager-button" :disabled="historyPage <= 1 || isPaging" @click="previousPage">上一页</button>
          <text>第 {{ historyPage }} / {{ historyPageCount }} 页，共 {{ d.total }} 条</text>
          <button class="btn rg__pager-button" :disabled="!d.hasMore || isPaging" @click="nextPage">下一页</button>
        </view>
        <text class="rg__sub">认定申请通过前，不改变正式成绩。材料随申请提交，审核结果以本人记录为准。</text>
        <AcademicPageState v-if="!d.items.length" state="empty" title="暂无认定申请" description="这里显示学校正式受理的认定申请；新申请需先取得你的目标课程选项。" />
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { academicApplicationPage } from './application-page'
import AcademicMaterials from './AcademicMaterials.vue'
import { savePending } from './pending-ledger'
const isForbidden = error => Number(error?.httpStatus || error?.statusCode) === 403 || /^403/.test(String(error?.code || '')) || error?.code === 'NO_PERMISSION'
const RECOGNITION_PAGE_SIZE = 20

function normalizeRecognitionPage(result, requestedPage) {
  const items = result?.items
  const page = result?.page
  const pageSize = result?.pageSize
  const total = result?.total
  const hasMore = result?.hasMore
  if (!Array.isArray(items) || !Number.isSafeInteger(page) || page !== requestedPage || page < 1
    || pageSize !== RECOGNITION_PAGE_SIZE || !Number.isSafeInteger(total) || total < 0
    || typeof hasMore !== 'boolean' || items.length > pageSize
    || (items.length > 0 && total < ((page - 1) * pageSize) + items.length)
    || hasMore !== page * pageSize < total) {
    throw new Error('认定记录分页信息无法核对')
  }
  return { ...result, items, page, pageSize, total, hasMore }
}


export default {
  components: { AcademicPageNav, AcademicPageState, AcademicMaterials },
mixins: [academicApplicationPage],
  created() { this.applicationScope = 'recognition' },
  data() {
    return {
      d: null, state: 'loading', showForm: false, submitting: false, materials: [], materialBusy: false, materialScopeEpoch: 0, academicDraftFields: ['form', 'showForm', 'materials'], historyPage: 1,
      courseKeyword: '', courseOptions: [], coursePage: 1, courseTotal: 0, courseLoading: false, courseError: '', courseEpoch: 0,
      form: { sourceCourseName: '', sourceScore: '', sourceCredit: '', sourceOrigin: '', targetCourseName: '', targetCourseId: '', reason: '' }
    }
  },
  computed: {
    canSubmit() {
      const s = Number(this.form.sourceScore)
      const credit = this.form.sourceCredit === '' || (Number.isFinite(Number(this.form.sourceCredit)) && Number(this.form.sourceCredit) >= 0 && Number(this.form.sourceCredit) <= 30)
      const targetId = this.form.targetCourseId
      return this.form.sourceCourseName.trim() && typeof targetId === 'string' && /^[1-9]\d*$/.test(targetId) && !!this.selectedCourse && s >= 60 && s <= 100 && credit && !this.materialBusy && !!this.materialIds
    },
    selectedCourse() { return this.courseOptions.find(course => course.courseId === this.form.targetCourseId) || null },
    historyPageCount() { return this.d?.total ? Math.ceil(this.d.total / RECOGNITION_PAGE_SIZE) : 1 },
    isPaging() { return this.state === 'loading' },
    materialIds() {
      const ids = this.materials.map(file => String(file?.fileId || '').trim())
      return ids.every(id => /^[1-9]\d*$/.test(id)) && new Set(ids).size === ids.length && this.materials.every(file => file?.readyForBusiness === true) ? ids : null
    }
  },
  onLoad() { this.load() },
  onHide() { this.materialBusy = false; this.materialScopeEpoch++; this.courseEpoch++; this.courseLoading = false },
  methods: {
    restorePendingDraft(pending) { this.form = { ...this.form, ...pending.body, sourceScore: String(pending.body.sourceScore), sourceCredit: pending.body.sourceCredit == null ? '' : String(pending.body.sourceCredit) }; this.materials = (pending.body.attachmentFileIds || []).map(fileId => this.materials.find(file => String(file.fileId) === String(fileId)) || { fileId: String(fileId), readyForBusiness: false }); this.materialScopeEpoch++; this.showForm = true },
    resetAcademicContext() { this.courseEpoch++; this.courseOptions=[]; this.courseTotal=0; this.courseError=''; this.courseLoading=false; this.materialScopeEpoch++; this.historyPage=1; this.clearApplicationContext(); this.finishApplication() },
    clearForbiddenRecognition() {
      const hadPending = this.protectPendingReference()
      this.d = null; this.courseEpoch++; this.courseOptions = []; this.courseTotal = 0; this.courseLoading = false; this.courseError = ''; this.historyPage = 1
      this.showForm = false; this.materials = []; this.materialBusy = false; this.materialScopeEpoch++
      this.form = { sourceCourseName: '', sourceScore: '', sourceCredit: '', sourceOrigin: '', targetCourseName: '', targetCourseId: '', reason: '' }
      this.submitting = false; this.applicationNotice = hadPending ? '当前无权核对本人认定记录；本次提交仍待核实。' : ''
      savePending('draft:' + this.applicationScope, null)
    },
    finishApplication() { this.showForm = false; this.materials = []; this.materialBusy = false; this.materialScopeEpoch++; this.form = { sourceCourseName: '', sourceScore: '', sourceCredit: '', sourceOrigin: '', targetCourseName: '', targetCourseId: '', reason: '' } },
    toggleForm(){this.showForm=!this.showForm;if(this.showForm&&!this.courseOptions.length)this.loadRecognitionCourses(false)},
    searchCourses(){this.form.targetCourseId='';this.form.targetCourseName='';return this.loadRecognitionCourses(false)},
    selectCourse(course){if(this.submitting||this.pendingApplication)return;this.form.targetCourseId=course.courseId;this.form.targetCourseName=course.courseName},
    previousPage() { return this.historyPage > 1 ? this.load(this.historyPage - 1) : Promise.resolve(null) },
    nextPage() { return this.d?.hasMore ? this.load(this.historyPage + 1) : Promise.resolve(null) },
    async loadRecognitionCourses(more=false){
      if(this.courseLoading||typeof studentApi.getRecognitionCourses!=='function')return
      const identity=currentSessionGeneration(),readEpoch=this.readEpoch,epoch=++this.courseEpoch,page=more?this.coursePage+1:1
      const current=()=>identity===currentSessionGeneration()&&readEpoch===this.readEpoch&&epoch===this.courseEpoch&&!this.readHidden
      this.courseLoading=true;this.courseError=''
      try{const data=await studentApi.getRecognitionCourses({keyword:this.courseKeyword||undefined,page,pageSize:20});if(!current())return;if(!Array.isArray(data?.items))throw Error('课程候选无法核对')
        const items=data.items.filter(item=>typeof item?.courseId==='string'&&/^[1-9]\d*$/.test(item.courseId)&&item.courseName).map(item=>({courseId:item.courseId,courseCode:String(item.courseCode||'代码未标注'),courseName:String(item.courseName),version:String(item.version||'')}))
        this.courseOptions=more?[...this.courseOptions,...items.filter(item=>!this.courseOptions.some(old=>old.courseId===item.courseId))]:items;this.coursePage=page;this.courseTotal=Number.isFinite(data.total)?data.total:this.courseOptions.length
      }catch(error){if(current()){if(isForbidden(error)){this.clearForbiddenRecognition();this.state='forbidden'}this.courseError='目标课程读取失败，请重新核对权限后重试。'}}finally{if(current())this.courseLoading=false}
    },
    load(requested = this.pendingApplication ? 1 : this.historyPage) {
      this.courseEpoch++; this.courseLoading = false
      const requestedPage = this.readIdentity !== currentSessionGeneration() ? 1 : Number(requested)
      if (!Number.isSafeInteger(requestedPage) || requestedPage < 1) return Promise.resolve(null)
      return this.readAcademic(async () => {
        const identity = currentSessionGeneration(); const epoch = this.readEpoch
        try { return await studentApi.getMyRecognition({ page: requestedPage, pageSize: RECOGNITION_PAGE_SIZE }) }
        catch (error) { if (isForbidden(error) && epoch === this.readEpoch && identity === currentSessionGeneration() && !this.readHidden) this.clearForbiddenRecognition(); throw error }
      }, (d) => {
        const data = normalizeRecognitionPage(d, requestedPage)
        this.d = data; this.historyPage = data.page
        this.acceptApplication(data.items, 'recognitionId', (row, body) => !!this.pendingApplication?.returnedId && row.sourceCourseName === body.sourceCourseName && typeof body.targetCourseId === 'string' && String(row.targetCourseId || '') === body.targetCourseId && Number(row.sourceScore) === body.sourceScore && (row.sourceCredit == null ? null : Number(row.sourceCredit)) === (body.sourceCredit ?? null) && (row.sourceOrigin || '') === (body.sourceOrigin || '') && (row.reason || '') === (body.reason || '') && JSON.stringify((row.attachmentFileIds || []).map(String).sort()) === JSON.stringify((body.attachmentFileIds || []).map(String).sort()))
        if(this.showForm&&!this.courseOptions.length)this.loadRecognitionCourses(false)
      })
    },
    submit() {
      if (!this.canSubmit || this.submitting || this.pendingApplication) return
      const body = {
        sourceCourseName: this.form.sourceCourseName.trim(),
        sourceScore: Number(this.form.sourceScore),
        sourceCredit: this.form.sourceCredit ? Number(this.form.sourceCredit) : undefined,
        sourceOrigin: this.form.sourceOrigin.trim() || undefined,
        targetCourseId: this.form.targetCourseId,
        targetCourseName: this.selectedCourse.courseName,
        reason: this.form.reason.trim() || undefined,
        attachmentFileIds: this.materialIds
      }
      return this.sendApplication({ title: '提交成绩认定申请', body, send: frozen => studentApi.submitRecognition(frozen), rows: this.d.items, idKey: 'recognitionId' })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.rg__target { padding: 12px; background: var(--fill-50, #f5f7fa); border-radius: 8px; font-size: 14px; }
.rg__search { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-2); }
.rg__courses { display: grid; gap: var(--space-2); max-height: 320px; overflow-y: auto; }
.rg__course { padding: 11px 12px; border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-card); }
.rg__course.is-selected { border-color: var(--primary-600); background: var(--primary-50); }
.rg__course-state { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); padding: 12px; border-radius: var(--radius-md); background: var(--fill-50); color: var(--text-secondary); font-size: var(--font-size-sm); }
.rg__group { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); font-weight: 600; margin-top: var(--space-1); }
.rg__input { width: 100%; height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.rg__row { display: flex; gap: var(--space-2); }
.rg__half { flex: 1; }
.rg__textarea { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.rg__ph { color: var(--text-tertiary); }
.rg__item { align-items: flex-start; }
.rg__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.rg__reason { display: block; font-size: var(--font-size-xs); color: var(--danger-600); margin-top: 4px; }
.rg__pager { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); margin: var(--space-4) 0; color: var(--text-secondary); font-size: var(--font-size-sm); }
.rg__pager-button { flex: 1; margin: 0; }
</style>
