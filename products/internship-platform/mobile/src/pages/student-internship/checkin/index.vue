<template>
  <view class="mobile-page mobile-student page-wrap">
    <MobileNavBar variant="brand" title="实习签到" show-back />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad" v-if="i">
        <view class="card ci__current">
          <view class="row-between"><text class="ci__date">{{ currentDateLabel }}</text><MobileStatusTag :label="i.historyMode ? '历史记录' : i.checkin.done ? '今日已签到' : '今日未签到'" :type="i.checkin.done ? 'success' : 'info'" /></view>
          <text class="ci__post">{{ i.post || '当前实习岗位' }}</text>
          <text v-if="i.company" class="ci__company">{{ i.company }}</text>
          <text class="ci__place">{{ preflightRule?.place || i.checkin.place || '签到地点未设置' }}</text>
          <text class="ci__help">{{ ruleSummary }}</text>
        </view>

        <template v-if="!i.historyMode">
        <view class="card ci__photo">
          <view class="row-between">
            <view class="flex-1">
              <text class="ci__label">现场照片</text>
              <text class="ci__help">仅用现场相机拍摄，保留原图；签到时生成时间与位置水印。</text>
              <text v-if="photoFileName" class="ci__help">{{ photoFileName }}</text>
            </view>
            <button class="mobile-control btn btn-ghost" :disabled="photoUploading || checkingIn" @click="capturePhoto">
              {{ photoUploading ? '上传中…' : (photoFileId ? '重新拍摄' : '现场拍照') }}
            </button>
          </view>
        </view>

        <view class="card ci__options">
          <button class="mobile-control ci__options-toggle" :aria-expanded="optionsOpen" @click="optionsOpen = !optionsOpen">{{ optionsOpen ? '收起选项' : overseas ? '备注与境外签到（已开启）' : '备注与境外签到' }}</button>
          <view v-if="optionsOpen" class="stack ci__options-body">
            <view><text class="ci__label">备注（选填）</text><textarea v-model="checkinNote" class="mobile-textarea ci__textarea" maxlength="500" :disabled="checkingIn || i.historyMode" placeholder="今天的岗位任务或到岗情况" /></view>
            <view class="ci__overseas"><text class="ci__label">境外签到</text><switch :checked="overseas" @change="overseas = !!$event.detail.value" /></view>
            <template v-if="overseas"><text class="ci__help">境外按国际通用坐标记录，定位不一致时由教师人工核验。</text><input v-model.trim="countryRegion" class="mobile-input ci__input" placeholder="国家或地区" /></template>
          </view>
        </view>

        <button class="mobile-control btn btn-primary ci__submit" :disabled="i.historyMode || i.checkin.done || checkingIn || photoUploading" @click="checkin">{{ i.historyMode ? '历史记录，仅可查看' : i.checkin.done ? '今日已签到' : checkingIn ? '签到中…' : '签到' }}</button>
        <text v-if="lastResultNote" class="ci__note">{{ lastResultNote }}</text>
        <text class="ci__note">仅签到时采集一次定位，不后台定位；异常由教师人工核验。</text>

        </template>
        <view class="section-head">
          <text class="section-head__title">签到记录</text>
          <picker class="mobile-picker" mode="date" fields="month" :value="calendarMonth + '-01'" @change="changeMonth">
            <text class="ci__month">{{ calendarMonth }} ▾</text>
          </picker>
        </view>
        <view class="card ci__calendar">
          <view class="ci__summary" v-if="calendarData">
            <text>签到 {{ calendarData.summary?.CHECKIN || 0 }}</text>
            <text>缺卡 {{ calendarData.summary?.ABSENT || 0 }}</text>
            <text>补卡 {{ calendarData.summary?.MAKEUP || 0 }}</text>
            <text>请假 {{ calendarData.summary?.LEAVE || 0 }}</text>
            <text>免签 {{ calendarData.summary?.EXEMPT || 0 }}</text>
          </view>
          <button class="mobile-control ci__calendar-toggle" :aria-expanded="calendarOpen" @click="calendarOpen = !calendarOpen">{{ calendarOpen ? '收起日历' : calendarData?.summary?.ABSENT ? '查看缺卡并补卡' : '查看日历' }}</button>
          <template v-if="calendarOpen">
          <view class="ci__week-head"><text v-for="w in weekLabels" :key="w">{{ w }}</text></view>
          <view class="ci__days">
            <view v-for="blank in calendarLeadBlanks" :key="'b'+blank" class="ci__day is-blank" />
            <button v-for="d in calendarDays" :key="d.date" class="mobile-control ci__day" :class="['is-' + String(d.status || '').toLowerCase(), { 'is-selected': selectedDate === d.date }]" :aria-label="d.date + '，' + calendarDetailLabel(d.status)" :aria-pressed="selectedDate === d.date" @click="selectedDate = d.date">
              <text class="ci__day-num">{{ d.day }}</text><text class="ci__day-status">{{ calendarStatusLabel(d.status) }}</text>
            </button>
          </view>
          </template>
          <view v-if="selectedCalendarDay" class="ci__day-detail stack" role="status"><text class="card-title">{{ selectedCalendarDay.date }} · {{ calendarDetailLabel(selectedCalendarDay.status) }}</text><text v-if="selectedCalendarDay.time">签到时间：{{ selectedCalendarDay.time }}</text><text v-if="selectedCalendarDay.reason || selectedCalendarDay.note">{{ selectedCalendarDay.reason || selectedCalendarDay.note }}</text><text v-if="!selectedCalendarDay.canApplyMakeup && !selectedCalendarDay.photoFileId && !selectedCalendarDay.watermarkedFileId" class="ci__help">本日状态按实习日历记录，无需在此重复办理。</text><button v-if="selectedCalendarDay.canApplyMakeup" class="mobile-control btn btn-primary" @click="openMakeup(selectedCalendarDay)">为这一天申请补卡</button><button v-if="selectedCalendarDay.photoFileId" class="mobile-control btn btn-ghost" @click="openPhoto(selectedCalendarDay, true)">查看现场原图</button><button v-if="selectedCalendarDay.watermarkedFileId" class="mobile-control btn btn-ghost" @click="openPhoto(selectedCalendarDay, false)">查看水印照片</button></view>
        </view>

        <ReportFilePreview ref="checkinPreview" />
        <view class="section-head"><text class="section-head__title">免签申请</text></view>
        <view class="card ci__exempt">
          <button v-if="!i.historyMode" class="mobile-control btn btn-ghost ci__exempt-toggle" @click="exemptionOpen = !exemptionOpen">
            {{ exemptionOpen ? '收起申请表' : '申请免签' }}
          </button>
          <view v-if="!i.historyMode && exemptionOpen" class="stack-sm ci__exempt-form">
            <text v-if="exemptionBase">原免签申请 {{ exemptionBase.id }} · 第{{ exemptionBase.version }}版 · {{ exemptionBase.statusLabel }}</text>
            <MobileInlineAlert v-if="exemptionError" type="warning" :description="exemptionError" />
            <view v-if="exemptionConflict" class="stack-sm"><text>原输入和版本已保留，请先核对原单。</text><button class="mobile-control btn btn-ghost" @click="rereadExemption">核对最新免签原单</button><template v-if="exemptionLatest"><text>最新第{{ exemptionLatest.version }}版 · {{ exemptionLatest.statusLabel }} · {{ exemptionLatest.reason }}</text><button class="mobile-control btn btn-ghost" @click="adoptExemption">采用已核对原单，替换未保存内容</button></template></view>
            <view class="ci__pair">
              <picker class="mobile-picker" mode="date" :value="exemptionForm.startDate" @change="exemptionForm.startDate = $event.detail.value">
                <view class="ci__picker">{{ exemptionForm.startDate || '开始日期' }}</view>
              </picker>
              <picker class="mobile-picker" mode="date" :value="exemptionForm.endDate" @change="exemptionForm.endDate = $event.detail.value">
                <view class="ci__picker">{{ exemptionForm.endDate || '结束日期' }}</view>
              </picker>
            </view>
            <textarea v-model="exemptionForm.reason" class="mobile-textarea ci__textarea" maxlength="500" placeholder="请填写免签理由（至少5字）" />
            <view class="row-between">
              <text class="ci__help">{{ exemptionEvidenceName || '可上传免签佐证附件' }}</text>
              <button class="mobile-control btn btn-ghost" :disabled="exemptionUploading" @click="pickExemptionEvidence">{{ exemptionUploading ? '上传中…' : '上传佐证' }}</button>
            </view>
            <button v-if="exemptionForm.evidenceFileId" class="mobile-control btn btn-ghost" :disabled="exemptionSubmitting || exemptionUploading" @click="refreshExemptionEvidence">刷新材料安全检查</button>
            <button class="mobile-control btn btn-primary" :disabled="exemptionSubmitting || exemptionUploading || exemptionConflict" @click="submitExemption">{{ exemptionSubmitting ? '提交中…' : exemptionBase ? '原单补正重交' : '提交指导老师审核' }}</button>
          </view>

          <view v-if="exemptions.length" class="ci__exempt-list">
            <view v-for="item in exemptions" :key="item.id" class="ci__exempt-row">
              <view class="flex-1">
                <text class="ci__exempt-date">{{ item.startDate }} ～ {{ item.endDate }}</text>
                <text class="ci__help">{{ item.reason }}</text>
                <text v-if="item.reviewComment" class="ci__review">审核意见：{{ item.reviewComment }}</text>
              </view>
              <view class="ci__exempt-side">
                <MobileStatusTag :label="item.statusLabel" :type="exemptionTone(item.status)" />
                <button v-if="['REJECTED','WITHDRAWN'].includes(item.status) && !i.historyMode" class="mobile-control ci__withdraw" :disabled="exemptionSubmitting || exemptionUploading" @click="editExemption(item)">原单补正</button>
                <button v-if="item.status === 'PENDING'" class="mobile-control ci__withdraw" :disabled="exemptionSubmitting" @click="withdrawExemption(item)">撤回</button>
              </view>
            </view>
          </view>
          <text v-else class="ci__help">暂无免签申请。</text>
        </view>
      </view>
    </MobileGlobalState>
    <MobilePrivacyGate />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { chooseSingleFile, uploadBusinessFile, fileSdk } from '@/services/fileApi'
import { toast } from '@/utils/nav'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { checkinCalendarLabel, checkinReceipt, checkinLocationPolicy } from '@/services/checkinPresentation.mjs'
import ReportFilePreview from '@/components/ReportFilePreview.vue'

export default {
  components: { ReportFilePreview },
  data() {
    const now = new Date()
    return {
      selectedDate:'', i: null, state: 'loading', error: '', requestedBatch: '', hidden: false,
      generation: currentSessionGeneration(), loadSequence: 0, checkinSequence: 0,
      checkingIn: false, checkinKey: '', checkinNote: '', lastResultNote: '', preflightRule: null,
      photoFileId: '', photoFileName: '', photoUploading: false, photoSequence: 0, disposed: false,
      overseas: false, countryRegion: '', optionsOpen: false, calendarOpen: false,
      timezoneName: this.detectTimezone(),
      calendarMonth: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
      calendarData: null, calendarDays: [], weekLabels: ['一', '二', '三', '四', '五', '六', '日'],
      exemptions: [], exemptionOpen: false, exemptionSubmitting: false, exemptionUploading: false,
      exemptionBase: null, exemptionSequence: 0, exemptionError: '', exemptionConflict: false, exemptionLatest: null, exemptionFile: null,
      exemptionEvidenceName: '',
      exemptionForm: { startDate: '', endDate: '', reason: '', evidenceFileId: '' }
    }
  },
  computed: {
    selectedCalendarDay() { return this.calendarDays.find(day => day.date === this.selectedDate) || null },
    currentDateLabel() {
      const now = new Date()
      try { return now.toLocaleDateString('zh-CN', { timeZone: this.calendarData?.timezoneName || this.timezoneName, year: 'numeric', month: 'long', day: 'numeric' }) }
      catch { return `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日` }
    },
    ruleSummary() {
      if (!this.preflightRule) return '围栏以岗位配置为准'
      if (!this.preflightRule.configured) return '岗位未配置围栏，本次只留痕'
      return `${this.preflightRule.radiusM} 米围栏 · 定位误差须不超过 ${this.preflightRule.maxAccuracyM} 米`
    },
    calendarLeadBlanks() {
      if (!this.calendarDays.length) return 0
      const d = new Date(this.calendarDays[0].date + 'T00:00:00')
      return (d.getDay() + 6) % 7
    }
  },
  onLoad(query = {}) { this.requestedBatch = String(query.batchId || ''); this.load() },
  onShow() {
    const reload = this.hidden || this.generation !== currentSessionGeneration()
    this.hidden = false
    if (this.generation !== currentSessionGeneration()) this.resetAccount()
    if (reload) this.load()
  },
  onHide() { this.pause() },
  onUnload() { this.disposed = true; this.pause(); this.resetAccount() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    async openPhoto(day, original = false) {
      if (this.disposed || this.hidden || this.state !== 'ready' || this.generation !== currentSessionGeneration()) return
      const current = this.calendarDays.find(item => item.date === day.date)
      if (!current) return
      const fileId = String((original ? current.photoFileId : current.watermarkedFileId) || '')
      if (!fileId) return
      await this.$refs?.checkinPreview?.open({ fileId, fileName: `${current.date}签到${original ? '原图' : '水印'}.jpg` })
    },
    detectTimezone() {
      try { return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai' }
      catch (e) { return 'Asia/Shanghai' }
    },
    calendarStatusLabel: checkinCalendarLabel,
    calendarDetailLabel(status) { return status === 'FUTURE' ? '未到签到日期' : status === 'OUTSIDE' ? '实习期间外' : this.calendarStatusLabel(status) },
    pause() { this.hidden = true; this.loadSequence++; this.checkinSequence++; this.checkingIn = false; this.exemptionSequence++; if (this.exemptionSubmitting || this.exemptionUploading) { this.exemptionConflict = true; this.exemptionError = '离页时结果未确认，原输入已保留，请核对免签原单' }; this.exemptionSubmitting = false; this.exemptionUploading = false; this.$refs?.checkinPreview?.reset() },
    resetAccount() {
      this.photoSequence++
      this.loadSequence++; this.checkinSequence++; this.generation = currentSessionGeneration()
      this.selectedDate = ''; this.i = null; this.calendarData = null; this.calendarDays = []; this.exemptions = []
      this.requestedBatch = ''; this.checkinKey = ''; this.checkinNote = ''; this.lastResultNote = ''; this.preflightRule = null
      this.photoFileId = ''; this.photoFileName = ''; this.photoUploading = false; this.checkingIn = false
      this.overseas = false; this.countryRegion = ''; this.exemptionEvidenceName = ''; this.exemptionOpen = false
      this.exemptionSequence++; this.exemptionBase = null; this.exemptionError = ''; this.exemptionConflict = false; this.exemptionLatest = null; this.exemptionFile = null
      this.exemptionForm = { startDate: '', endDate: '', reason: '', evidenceFileId: '' }
    },
    exemptionTone(status) { return status === 'APPROVED' ? 'success' : status === 'REJECTED' ? 'danger' : status === 'WITHDRAWN' ? 'default' : 'warning' },
    async load(done) {
      this.$refs?.checkinPreview?.reset()
      if (this.hidden) return
      if (this.generation !== currentSessionGeneration()) this.resetAccount()
      const sequence = ++this.loadSequence, generation = currentSessionGeneration()
      const current = () => !this.hidden && sequence === this.loadSequence && generation === currentSessionGeneration()
      this.state = 'loading'
      this.error = ''; this.selectedDate = ''; this.i = null; this.calendarData = null; this.calendarDays = []; this.exemptions = []
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatch)
        if (!current()) return
        if (!dashboard?.batchId || !dashboard?.recordId) {
          this.state = 'empty'
          this.error = '请从实习首页选择本人的批次后进入签到。'
          return
        }
        if (this.requestedBatch && String(dashboard.batchId) !== this.requestedBatch) throw { code: 404001 }
        const [calendar, exemptions] = await Promise.all([
          studentApi.getCheckinCalendar(this.calendarMonth, this.timezoneName, dashboard.batchId),
          studentApi.getCheckinExemptions(dashboard.batchId, dashboard.recordId)
        ])
        if (!current()) return
        this.i = dashboard
        this.calendarData = calendar
        this.calendarDays = calendar?.days || []
        this.exemptions = Array.isArray(exemptions) ? exemptions : exemptions?.items || []
        this.state = 'ready'
      } catch (e) {
        if (!current()) return
        const error = normalizeError(e)
        this.state = error.pageState || 'error'; this.error = error.text
        toast(error.text)
      } finally { if (done) done() }
    },
    async changeMonth(e) {
      this.selectedDate = ''; this.calendarMonth = String(e.detail.value || '').slice(0, 7)
      await this.load()
    },
    capturePhoto() {
      if (this.photoUploading || this.checkingIn || this.disposed || this.hidden || !this.i || this.i.historyMode || this.generation !== currentSessionGeneration()) return
      const generation = currentSessionGeneration(), sequence = ++this.photoSequence
      const batch = this.i.batchId, record = this.i.recordId
      const owned = () => !this.disposed && generation === currentSessionGeneration() && sequence === this.photoSequence
      const current = () => owned() && batch === this.i?.batchId && record === this.i?.recordId
      this.photoUploading = true
      uni.chooseImage({
        count: 1,
        sourceType: ['camera'],
        sizeType: ['original'],
        success: async (res) => {
          if (!current()) { if (owned()) this.photoUploading = false; return }
          try {
            const path = (res.tempFilePaths || [])[0]
            const source = (res.tempFiles || [])[0] || {}
            if (!path) return
            const uploaded = await uploadBusinessFile({
              path, name: source.name || `checkin-${Date.now()}.jpg`, size: source.size || 0
            }, { bizType: 'INTERNSHIP_CHECKIN_PHOTO' })
            if (!current()) return
            this.photoFileId = uploaded.fileId
            this.photoFileName = uploaded.fileName || '现场照片已上传'
            toast('现场原图已上传，签到时由服务器生成水印图')
          } catch (e) { if (current()) toast(normalizeError(e).text) }
          finally { if (owned()) this.photoUploading = false }
        },
        fail: () => { if (owned()) this.photoUploading = false }
      })
    },
    async pickExemptionEvidence() {
      if (this.exemptionUploading || this.exemptionSubmitting || this.hidden || this.exemptionConflict) return
      const current = this.exemptionCurrent(++this.exemptionSequence)
      this.exemptionUploading = true
      try {
        const file = await chooseSingleFile()
        if (!file || !current()) return
        const uploaded = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_CHECKIN_EXEMPTION' })
        if (!current()) return
        this.exemptionForm.evidenceFileId = uploaded.fileId
        this.exemptionFile = uploaded
        this.exemptionEvidenceName = uploaded.fileName || file.name || '免签佐证'
        if (uploaded.readyForBusiness !== true) this.exemptionError = '材料已接收，安全检查未完成；输入已保留，请刷新材料状态'
      } catch (e) { if (current()) this.exemptionError = normalizeError(e).text }
      finally { if (current()) this.exemptionUploading = false }
    },
    exemptionCurrent(sequence) {
      const generation = currentSessionGeneration(), batch = this.i?.batchId, record = this.i?.recordId
      return () => !this.hidden && generation === currentSessionGeneration() && sequence === this.exemptionSequence && batch === this.i?.batchId && record === this.i?.recordId
    },
    editExemption(item) {
      if (this.hidden || this.i?.historyMode || this.exemptionSubmitting || this.exemptionUploading || !['REJECTED','WITHDRAWN'].includes(item.status)) return
      this.exemptionSequence++; this.exemptionBase = {...item}; this.exemptionOpen = true; this.exemptionConflict = false; this.exemptionLatest = null; this.exemptionError = ''; this.exemptionFile = null
      this.exemptionForm = { startDate:item.startDate, endDate:item.endDate, reason:item.reason, evidenceFileId:String(item.evidenceFileId || '') }
      this.exemptionEvidenceName = item.evidenceFileId ? '原单佐证材料' : ''
    },
    async refreshExemptionEvidence() {
      if (this.hidden || this.exemptionUploading || this.exemptionSubmitting) return false
      if (!this.exemptionForm.evidenceFileId) return true
      const current = this.exemptionCurrent(this.exemptionSequence), id = String(this.exemptionForm.evidenceFileId)
      this.exemptionFile = null
      try { const meta = await fileSdk.metadata(id); if (!current() || id !== String(this.exemptionForm.evidenceFileId)) return false; if (String(meta.fileId) !== id) throw new Error('材料编号不一致，请重新核对'); this.exemptionFile = meta; this.exemptionError = meta.readyForBusiness === true ? '' : '材料安全检查未完成，输入已保留，请稍后刷新'; return meta.readyForBusiness === true }
      catch (error) { if (current()) this.exemptionError = error?.message || '材料安全状态读取失败'; return false }
    },
    async rereadExemption() {
      if (this.hidden || this.exemptionSubmitting || this.exemptionUploading) return
      const current = this.exemptionCurrent(this.exemptionSequence)
      try { const rows = await studentApi.getCheckinExemptions(this.i.batchId, this.i.recordId); if (!current()) return; this.exemptions = rows || []; this.exemptionLatest = this.exemptions.find(row => String(row.id) === String(this.exemptionBase?.id)) || null; this.exemptionError = this.exemptionLatest ? '' : '未找到可核对原单，填写内容仍保留' }
      catch (error) { if (current()) this.exemptionError = normalizeError(error).text }
    },
    adoptExemption() { if (!this.exemptionLatest || this.exemptionSubmitting || this.exemptionUploading) return; this.editExemption(this.exemptionLatest) },
    async submitExemption() {
      if (this.exemptionSubmitting || this.exemptionUploading || this.hidden || this.i?.historyMode || this.exemptionConflict || this.generation !== currentSessionGeneration()) return
      const f = this.exemptionForm
      if (!f.startDate || !f.endDate) return toast('请选择免签起止日期')
      if (f.startDate > f.endDate) return toast('免签结束日期不能早于开始日期')
      if (String(f.reason || '').trim().length < 5) return toast('免签理由不少于5个字')
      const current = this.exemptionCurrent(++this.exemptionSequence)
      if (!await this.refreshExemptionEvidence() || !current()) return
      this.exemptionSubmitting = true; this.exemptionError = ''
      try {
        await studentApi.applyCheckinExemption({
          batchId: this.i.batchId, internshipId: this.i.recordId,
          startDate: f.startDate, endDate: f.endDate,
          reason: String(f.reason || '').trim(), evidenceFileId: f.evidenceFileId || ''
          ,...(this.exemptionBase ? {id:this.exemptionBase.id, expectedVersion:this.exemptionBase.version} : {})
        })
        if (!current()) return
        toast('免签申请已提交')
        this.exemptionForm = { startDate: '', endDate: '', reason: '', evidenceFileId: '' }
        this.exemptionEvidenceName = ''
        this.exemptionOpen = false
        this.exemptionBase = null; this.exemptionFile = null
        await this.load()
      } catch (e) { if (current()) { this.exemptionError = normalizeError(e).text; if (normalizeError(e).kind === 'conflict') { this.exemptionConflict = true; this.exemptionLatest = null } } }
      finally { if (current()) this.exemptionSubmitting = false }
    },
    withdrawExemption(item) {
      uni.showModal({
        title: '撤回免签申请', content: '确认撤回这份待审核免签申请？',
        confirmText: '确认撤回', cancelText: '暂不撤回',
        success: async (r) => {
          if (!r.confirm) return
          this.exemptionSubmitting = true
          try {
            await studentApi.withdrawCheckinExemption(item.id, {
              batchId: this.i.batchId, internshipId: this.i.recordId, expectedVersion: item.version
            })
            toast('免签申请已撤回')
            await this.load()
          } catch (e) { toast(normalizeError(e).text) }
          finally { this.exemptionSubmitting = false }
        }
      })
    },
    openMakeup(day) {
      uni.navigateTo({ url: '/pages/student-internship/makeup/index?date=' + encodeURIComponent(day.date) })
    },
    checkin() {
      if (this.state !== 'ready' || !this.i || this.hidden || this.generation !== currentSessionGeneration()) return
      if (this.i.historyMode) return toast('当前历史批次仅可查看签到记录')
      if (this.i.checkin.done) return toast('当地日期今日已签到')
      if (this.checkingIn || this.photoUploading) return
      const generation = currentSessionGeneration(), batch = this.i.batchId, record = this.i.recordId
      uni.showModal({
        title: '实习签到',
        confirmText: '确认签到', cancelText: '暂不签到',
        content: this.photoFileId
          ? '将采集一次定位，并把服务器时间和位置写入现场照片水印。确认签到？'
          : '本次未拍现场照片，将只记录服务器时间与定位。确认签到？',
        success: (r) => {
          if (!r.confirm || this.checkingIn || this.hidden || generation !== currentSessionGeneration() || batch !== this.i?.batchId || record !== this.i?.recordId) return
          this.beginCheckin()
        }
      })
    },
    async beginCheckin() {
      if (this.checkingIn || this.photoUploading || this.hidden || this.generation !== currentSessionGeneration() || this.state !== 'ready' || !this.i || this.i.historyMode || this.i.checkin.done) return
      const generation = currentSessionGeneration(), sequence = ++this.checkinSequence
      const batch = this.i.batchId, record = this.i.recordId
      const locationPolicy = checkinLocationPolicy(this.overseas)
      const current = () => !this.hidden && generation === currentSessionGeneration() && sequence === this.checkinSequence && batch === this.i?.batchId && record === this.i?.recordId
      this.checkingIn = true
      this.checkinKey = this.checkinKey || `mp-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
      let preflight
      try {
        preflight = await studentApi.getCheckinPreflight(this.timezoneName, this.i.batchId)
        if (!current()) return
        this.preflightRule = preflight.rule || null
      } catch (e) {
        if (!current()) return
        this.checkingIn = false
        return toast(normalizeError(e).text)
      }

      const submit = async (loc = {}) => {
        if (!current()) return
        try {
          const res = await studentApi.submitCheckin({
            ...loc,
            batchId: this.i.batchId,
            idempotencyKey: this.checkinKey,
            checkinToken: preflight.token,
            photoFileId: this.photoFileId || '',
            note: String(this.checkinNote || '').trim(),
            timezoneName: this.timezoneName,
            countryRegion: this.countryRegion || '',
            coordinateSystem: locationPolicy.coordinateSystem,
            locationProvider: locationPolicy.locationProvider,
            capturedAt: new Date().toISOString()
          })
          if (!current()) return
          const receipt = checkinReceipt(res)
          if (!receipt) {
            toast('签到回执暂无法核对，请重新读取日历；未确认前请保留备注和照片')
            return
          }
          this.checkinKey = ''
          this.lastResultNote = receipt.summary
          this.checkinNote = ''
          this.photoFileId = ''
          this.photoFileName = ''
          uni.showModal({ title: receipt.title, content: receipt.content, showCancel: false, confirmText: '知道了' })
          await this.load()
        } catch (e) {
          if (!current()) return
          if (e?.bizCode === 'DATA_CONFLICT' || normalizeError(e).kind === 'conflict') {
            toast('签到记录或状态已变化，请重新读取日历核对')
            await this.load()
          } else toast(normalizeError(e).text)
        } finally { if (!this.hidden && generation === currentSessionGeneration() && sequence === this.checkinSequence) this.checkingIn = false }
      }

      let attempts = 0
      let best = null
      const locate = () => uni.getLocation({
        type: locationPolicy.type,
        success: (p) => {
          if (!current()) return
          attempts += 1
          const loc = {
            lat: p.latitude, lng: p.longitude, gpsAccuracy: p.accuracy,
            address: p.address || p.name || ''
          }
          if (!best || Number(loc.gpsAccuracy || Infinity) < Number(best.gpsAccuracy || Infinity)) best = loc
          const maxAccuracy = Number(this.preflightRule?.maxAccuracyM || 200)
          if ((!p.accuracy || Number(p.accuracy) > maxAccuracy) && attempts < 3) {
            this.lastResultNote = `定位精度不足，正在重新定位（${attempts}/3）…`
            locate()
            return
          }
          submit(best)
        },
        fail: (err) => {
          if (!current()) return
          if (this.photoFileId) {
            this.checkingIn = false
            toast('已拍现场照片时必须获取一次位置，才能生成位置水印')
            return
          }
          const msg = String(err?.errMsg || '')
          if (/auth\s*deny|authorize|permission/i.test(msg)) {
            uni.showModal({
              title: '未获得定位权限',
              content: '可去设置开启定位；如不上传现场照片，也可继续无定位签到并进入人工核验。',
              confirmText: '去设置', cancelText: '无定位签到',
              success: (choice) => {
                if (!current()) return
                if (!choice.confirm) return submit({})
                uni.openSetting({
                  success: (res) => { if (current()) res?.authSetting?.['scope.userLocation'] ? locate() : submit({}) },
                  fail: () => { if (current()) submit({}) }
                })
              }
            })
            return
          }
          submit({})
        }
      })
      locate()
    }
  }
}
</script>

<style scoped>
.ci__map{padding:0;overflow:hidden}.ci__map-bg{height:120px;background:linear-gradient(135deg,var(--primary-50),var(--primary-100));position:relative;display:flex;align-items:center;justify-content:center}.ci__map-pin{width:32px;height:32px;border-radius:var(--radius-full);background:var(--brand-primary);box-shadow:0 0 0 8px rgba(37,99,235,.14)}.ci__map-loc{display:block;padding:var(--space-3);font-size:var(--font-size-sm);color:var(--text-secondary);text-align:center}.ci__overseas{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 var(--space-3) var(--space-3)}.ci__label{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.ci__help{display:block;margin-top:3px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-tertiary)}.ci__input,.ci__picker,.ci__textarea{box-sizing:border-box;width:100%;border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;font-size:var(--font-size-sm)}.ci__input{margin:0 var(--space-3) var(--space-3);width:calc(100% - 2 * var(--space-3))}.ci__photo{margin-top:var(--space-3);padding:var(--space-3)}.ci__circle{width:132px;height:132px;border-radius:var(--radius-full);margin:var(--space-6) auto var(--space-2);display:flex;flex-direction:column;align-items:center;justify-content:center}.ci__circle.is-todo{background:var(--brand-gradient);box-shadow:0 14px 30px -12px rgba(37,99,235,.6)}.ci__circle.is-todo .ci__circle-num{color:#fff;font-size:17px;font-weight:var(--font-weight-semibold)}.ci__circle.is-todo .ci__circle-lb{color:rgba(255,255,255,.85);font-size:var(--font-size-xs);margin-top:4px}.ci__circle.is-done{background:var(--success-50);border:3px solid var(--success-500)}.ci__circle.is-done .ci__circle-num{color:var(--success-600);font-size:28px;font-weight:var(--font-weight-semibold)}.ci__circle.is-done .ci__circle-lb{color:var(--success-600);font-size:var(--font-size-xs);margin-top:4px}.ci__note{display:block;text-align:center;margin-bottom:var(--space-2)}.ci__month{font-size:var(--font-size-sm);color:var(--brand-primary)}.ci__calendar{padding:var(--space-3)}.ci__summary{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:4px;margin-bottom:12px}.ci__summary text{text-align:center;font-size:10px;color:var(--text-secondary)}.ci__week-head,.ci__days{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:5px}.ci__week-head text{text-align:center;font-size:10px;color:var(--text-tertiary);padding-bottom:5px}.ci__day{min-height:56px;padding:5px 2px;border:1px solid var(--border-light);border-radius:8px;background:var(--gray-50);text-align:center}.ci__day.is-blank{border:0;background:transparent}.ci__day-num{display:block;font-size:12px;color:var(--text-primary)}.ci__day-status{display:block;margin-top:4px;font-size:9px;color:var(--text-tertiary)}.ci__day.is-checkin,.ci__day.is-makeup{background:var(--success-50)}.ci__day.is-absent{background:var(--danger-50)}.ci__day.is-exempt,.ci__day.is-leave{background:var(--warning-50)}.ci__day.is-future,.ci__day.is-outside{opacity:.45}.ci__day-action{margin:3px auto 0;padding:1px 4px;min-height:0;line-height:1.5;border:0;background:transparent;color:var(--brand-primary);font-size:9px}.ci__day-action::after{border:none}.ci__exempt{padding:var(--space-3);margin-bottom:var(--space-6)}.ci__exempt-toggle{margin-bottom:10px}.ci__pair{display:grid;grid-template-columns:1fr 1fr;gap:8px}.ci__textarea{min-height:88px}.ci__exempt-list{margin-top:12px;border-top:1px solid var(--border-light)}.ci__exempt-row{display:flex;gap:10px;padding:10px 0;border-bottom:1px solid var(--border-light)}.ci__exempt-date{display:block;font-size:var(--font-size-sm);font-weight:600}.ci__review{display:block;margin-top:3px;font-size:var(--font-size-xs);color:var(--warning-700)}.ci__exempt-side{display:flex;flex-direction:column;align-items:flex-end;gap:5px}.ci__withdraw{margin:0;padding:2px 4px;min-height:0;border:0;background:transparent;color:var(--danger-600);font-size:10px}.ci__withdraw::after{border:none}
.ci__current{display:flex;flex-direction:column;gap:6px}.ci__date{font-size:var(--font-size-base);color:var(--text-secondary)}.ci__post{display:block;font-size:var(--font-size-lg);font-weight:600;color:var(--text-primary);margin-top:8px}.ci__company,.ci__place{display:block;font-size:var(--font-size-base);color:var(--text-secondary);line-height:1.5;overflow-wrap:anywhere}
.ci__options{margin-top:var(--space-3);padding:0 var(--space-3)}.ci__options-toggle,.ci__calendar-toggle{width:100%;min-height:44px;margin:0;padding:8px 0;background:transparent;color:var(--brand-primary);font-size:var(--font-size-base)}.ci__options-toggle::after,.ci__calendar-toggle::after{border:0}.ci__options-body{padding-bottom:var(--space-3)}.ci__overseas{padding:0}.ci__input{margin:0;width:100%;height:44px}
.ci__submit{width:100%;min-height:48px;margin:var(--space-4) 0 var(--space-2);font-size:var(--font-size-md)}.ci__note{font-size:var(--font-size-base);line-height:1.6;text-align:left;color:var(--text-secondary);margin:6px 0}.ci__label{font-size:var(--font-size-base)}.ci__help,.ci__review,.ci__input,.ci__picker,.ci__textarea{font-size:var(--font-size-base);overflow-wrap:anywhere}.ci__photo .btn{flex-shrink:0;min-height:44px;font-size:var(--font-size-base)}
.ci__month{display:inline-flex;align-items:center;min-height:44px;font-size:var(--font-size-base)}.ci__summary text,.ci__week-head text,.ci__day-num,.ci__day-status{font-size:var(--font-size-base)}.ci__week-head,.ci__days{gap:3px}.ci__day{padding:5px 0}.ci__day-status{line-height:1.4;overflow-wrap:anywhere}.ci__day-action{width:100%;min-height:44px;padding:6px 0;font-size:var(--font-size-base);box-sizing:border-box}.ci__withdraw{min-height:44px;font-size:var(--font-size-base)}
.ci__calendar{padding:8px}.ci__day{margin:0;min-width:44px;min-height:56px!important;display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:var(--radius-md);line-height:1.5}.ci__day::after{border:0}.ci__day.is-selected{outline:2px solid var(--brand-primary);outline-offset:-2px}.ci__day-detail{margin-top:16px;padding-top:16px;border-top:1px solid var(--border-base)}
</style>
