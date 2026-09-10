<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="补考重修 / 免修" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view v-if="applicationNotice" class="card"><text>{{ applicationNotice }}</text><button v-if="pendingApplication" class="btn" @click="load">核对本人记录</button></view>
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
          <view v-for="r in d.retakes.slice(0, listLimit)" :key="r.applyId" class="list-row">
            <view class="flex-1">
              <text class="t-md">{{ r.courseName }}</text>
              <text class="mk__sub">{{ r.termCode || '学期待核对' }}{{ r.retakeCount != null ? ' · 第' + r.retakeCount + '次重修' : '' }}</text>
              <text v-if="r.reviewReason" class="mk__reason">{{ r.reviewReason }}</text>
            </view>
            <MobileStatusTag :status="r.status" />
          </view>
        </view>
        <AcademicPageState v-else state="empty" title="暂无重修申请" description="点击右上角从挂科成绩列表报名。" />

        <view class="section-head">
          <text class="section-head__title">我的免修申请</text>
          <text class="section-head__more" @click="toggleForm('exemption')">{{ showExemption ? '收起' : '+ 申请免修' }}</text>
        </view>

        <view class="card stack-sm" v-if="showExemption">
          <text class="mk__hint">从学校提供的可申请课程中选择。材料要求请联系教务老师核对。</text>
          <picker mode="selector" :range="exLabels" :value="exIndex" @change="onExPick">
            <view class="mk__input">{{ exLabels[exIndex] || '请选择课程' }}</view>
          </picker>
          <textarea :disabled="submitting || !!pendingApplication" class="mk__textarea" v-model="exForm.reason" :maxlength="200" placeholder="免修理由（选填）" placeholder-class="mk__ph" />
          <AcademicMaterials v-if="!readHidden" :key="materialScopeEpoch" :files="materials" purpose="AA_EXEMPTION" :disabled="submitting || !!pendingApplication" @update:files="materials = $event" @busy="materialBusy = $event" @forbidden="clearForbiddenMakeup(); state = 'forbidden'" />
          <text v-if="exForm.courseId && !exemptionAvailable" class="mk__reason">原选课程已不在当前可申请列表，请重新选择；申请内容仍保留。</text>
          <button class="btn btn-primary" :disabled="!exemptionAvailable || submitting || !!pendingApplication || !materialsReady" @click="submitExemption">
            {{ submitting ? '提交中…' : '提交免修申请' }}
          </button>
        </view>

        <view class="list-group" v-if="d.exemptions.length">
          <view v-for="e in d.exemptions.slice(0, listLimit)" :key="e.exemptionId" class="list-row">
            <view class="flex-1">
              <text class="t-md">{{ e.courseName }}</text>
              <text class="mk__sub">{{ e.termCode || '—' }}</text>
              <text v-if="e.returnReason" class="mk__reason">{{ e.returnReason }}</text>
            </view>
            <MobileStatusTag :status="e.status" />
          </view>
        </view>
        <AcademicPageState v-else state="empty" title="暂无免修申请" description="点击右上角选择课程发起免修。" />
        <button v-if="d.retakes.length > listLimit || d.exemptions.length > listLimit" class="btn" @click="listLimit += 20">查看更多办理记录</button>
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

export default {
  components: { AcademicPageNav, AcademicPageState, AcademicMaterials },
mixins: [academicApplicationPage],
  created() { this.applicationScope = 'makeup' },
  data() {
    return {
      d: null, materials: [], materialBusy: false, materialScopeEpoch: 0, academicDraftFields: ['retakeForm', 'exForm', 'showRetake', 'showExemption', 'materials'],
      opts: { retakeOptions: [], exemptionOptions: [], identityDebtCount: 0 },
      state: 'loading', submitting: false,
      showRetake: false, showExemption: false,
      retakeIndex: 0, exIndex: 0,
      retakeForm: { gradeId: '', termCode: '', reason: '' },
      exForm: { courseId: '', termCode: '', reason: '', materialFileIds: [] },
      targetId: ''
    }
  },
  computed: {
    retakeAvailable() { return !!this.retakeForm.gradeId && this.opts.retakeOptions.some(row => String(row.gradeId) === String(this.retakeForm.gradeId)) },
    exemptionAvailable() { return !!this.exForm.courseId && this.opts.exemptionOptions.some(row => String(row.courseId) === String(this.exForm.courseId)) },
    materialIds() {
      const ids = this.materials.map(file => String(file?.fileId || '').trim())
      return ids.every(id => /^[1-9]\d*$/.test(id)) && new Set(ids).size === ids.length && this.materials.every(file => file?.readyForBusiness === true) ? ids : null
    },
    materialsReady() { return !this.materialBusy && !!this.materialIds },
    selectedExemption() { return this.opts.exemptionOptions.find(row => String(row.courseId) === String(this.exForm.courseId)) || null },
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
      this.retakeForm = { gradeId: '', termCode: '', reason: '' }; this.exForm = { courseId: '', termCode: '', reason: '', materialFileIds: [] }
      this.targetId = ''; this.submitting = false
      this.applicationNotice = hadPending ? '当前无权核对补考重修记录；本次办理仍待核实。' : ''
      savePending('draft:' + this.applicationScope, null)
    },
    load() {
      return this.readAcademic(async () => {
        const identity = currentSessionGeneration(); const epoch = this.readEpoch
        try { return await Promise.all([studentApi.getMyMakeup(), studentApi.getMakeupOptions()]) }
        catch (error) { if (isForbidden(error) && epoch === this.readEpoch && identity === currentSessionGeneration() && !this.readHidden) this.clearForbiddenMakeup(); throw error }
      }, ([d, opts]) => {
          if (!d || !Array.isArray(d.retakes) || !Array.isArray(d.exemptions) || !opts || !Array.isArray(opts.retakeOptions) || !Array.isArray(opts.exemptionOptions)) throw new Error('补考重修信息无法核对')
          this.d = d
          this.opts = opts || { retakeOptions: [], exemptionOptions: [], identityDebtCount: 0 }
          this.syncPickDefaults()
          if (this.pendingApplication && this.pendingApplication.kind === 'retake') {
            this.acceptApplication(d.retakes, 'applyId', (row, body) => !!this.pendingApplication.returnedId && String(row.originGradeId || '') === String(body.gradeId))
          } else if (this.pendingApplication) {
            this.acceptApplication(d.exemptions, 'exemptionId', (row, body) => !!this.pendingApplication.returnedId && String(row.course?.id || row.courseId || '') === String(body.courseId))
          }
        })
    },
    resetAcademicContext() { this.clearApplicationContext(); this.materials = []; this.materialBusy = false; this.materialScopeEpoch++; this.opts = { retakeOptions: [], exemptionOptions: [], identityDebtCount: 0 }; this.targetId = ''; this.retakeForm = { gradeId: '', termCode: '', reason: '' }; this.exForm = { courseId: '', termCode: '', reason: '', materialFileIds: [] }; this.showRetake = false; this.showExemption = false },
    finishApplication(kind) { if (kind === 'retake') { this.retakeForm.reason = ''; this.showRetake = false } else { this.exForm.reason = ''; this.showExemption = false; this.materials = []; this.materialBusy = false; this.materialScopeEpoch++ } },
    syncPickDefaults() {
      if (this.retakeForm.gradeId || this.exForm.courseId) {
        this.retakeIndex = (this.opts.retakeOptions || []).findIndex(row => String(row.gradeId) === String(this.retakeForm.gradeId))
        this.exIndex = (this.opts.exemptionOptions || []).findIndex(row => String(row.courseId) === String(this.exForm.courseId))
        return
      }
      const rows = this.opts.retakeOptions || []
      const targetIndex = this.targetId
        ? rows.findIndex((row) => String(row.gradeId || row.sourceId || row.acadGradeId || row.id || '') === this.targetId)
        : -1
      this.retakeIndex = targetIndex >= 0 ? targetIndex : 0
      const retake = rows[this.retakeIndex]
      this.retakeForm = {
        gradeId: retake?.gradeId || '',
        termCode: retake?.termCode || '',
        reason: ''
      }
      if (targetIndex >= 0) this.showRetake = true
      const exemption = (this.opts.exemptionOptions || [])[0]
      this.exForm = {
        courseId: exemption?.courseId || '',
        termCode: exemption?.termCode || '',
        reason: '',
        materialFileIds: []
      }
      this.exIndex = 0
    },
    onRetakePick(e) {
      if (this.submitting || this.pendingApplication) return
      const index = Number(e.detail.value || 0)
      const row = (this.opts.retakeOptions || [])[index]
      if (!row) return
      this.retakeIndex = index
      this.retakeForm.gradeId = row.gradeId
      this.retakeForm.termCode = row.termCode || ''
    },
    onExPick(e) {
      if (this.submitting || this.pendingApplication || this.materialBusy) return
      const index = Number(e.detail.value || 0)
      const row = (this.opts.exemptionOptions || [])[index]
      if (!row) return
      this.exIndex = index
      this.exForm.courseId = row.courseId
      this.exForm.termCode = row.termCode || ''
      this.materials = []
      this.materialScopeEpoch++
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
        termCode: this.retakeForm.termCode,
        reason: this.retakeForm.reason.trim()
      }, send: body => studentApi.applyRetake(body), rows: this.d.retakes, idKey: 'applyId' })
    },
    submitExemption() {
      if (!this.exemptionAvailable || this.submitting || this.pendingApplication || !this.materialsReady || !this.selectedExemption) return
      return this.sendApplication({ title: '提交免修申请', kind: 'exemption', body: {
        courseId: this.exForm.courseId,
        courseName: this.selectedExemption.courseName,
        termCode: this.exForm.termCode,
        reason: this.exForm.reason.trim(),
        materialFileIds: this.materialIds
      }, send: body => studentApi.applyExemption(body), rows: this.d.exemptions, idKey: 'exemptionId' })
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
.is-target { border: 1px solid var(--brand-primary); box-shadow: 0 0 0 2px var(--brand-50); }
</style>
