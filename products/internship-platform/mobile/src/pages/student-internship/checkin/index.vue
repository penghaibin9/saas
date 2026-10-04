<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="实习签到" show-back />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad" v-if="i">
        <view class="card ci__map">
          <view class="ci__map-bg"><view class="ci__map-pin" /></view>
          <text class="ci__map-loc">{{ preflightRule?.place || i.checkin.place || '公司位置未设置' }} · {{ ruleSummary }}</text>
          <view class="ci__overseas">
            <view><text class="ci__label">境外签到</text><text class="ci__help">境外定位按国际通用坐标记录；定位信息不一致时转人工核验，不自动判定作弊。</text></view>
            <switch :checked="overseas" @change="overseas = !!$event.detail.value" />
          </view>
          <input v-if="overseas" v-model.trim="countryRegion" class="ci__input" placeholder="国家/地区，例如日本" />
        </view>

        <view class="card ci__photo">
          <view class="row-between">
            <view class="flex-1">
              <text class="ci__label">现场照片</text>
              <text class="ci__help">{{ photoFileName || '仅允许现场相机拍摄；原图保留，时间+位置水印由服务器生成。' }}</text>
            </view>
            <button class="btn btn-ghost" :disabled="photoUploading || checkingIn" @click="capturePhoto">
              {{ photoUploading ? '上传中…' : (photoFileId ? '重新拍摄' : '现场拍照') }}
            </button>
          </view>
        </view>

        <view class="card ci__photo">
          <text class="ci__label">签到备注</text>
          <textarea v-model="checkinNote" class="ci__textarea" maxlength="500" :disabled="checkingIn || i.historyMode" placeholder="签到备注（选填，例如：今天的岗位任务与到岗情况）" />
        </view>

        <view class="ci__circle" :class="i.checkin.done ? 'is-done' : 'is-todo'" @click="checkin">
          <text v-if="i.checkin.done" class="ci__circle-num">✓</text>
          <text v-else class="ci__circle-num">{{ checkingIn ? '…' : '签到' }}</text>
          <text class="ci__circle-lb">{{ i.checkin.done ? '当地日期今日已签到' : (checkingIn ? '定位中' : '点击签到') }}</text>
        </view>
        <text class="ci__note t-xs t-tertiary">{{ lastResultNote || i.checkin.note || '仅在点击时采集一次定位；异常只进入人工核验，不自动认定作弊。' }}</text>

        <view class="section-head">
          <text class="section-head__title">完整签到日历</text>
          <picker mode="date" fields="month" :value="calendarMonth + '-01'" @change="changeMonth">
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
          <view class="ci__week-head"><text v-for="w in weekLabels" :key="w">{{ w }}</text></view>
          <view class="ci__days">
            <view v-for="blank in calendarLeadBlanks" :key="'b'+blank" class="ci__day is-blank" />
            <view v-for="d in calendarDays" :key="d.date" class="ci__day" :class="'is-' + String(d.status || '').toLowerCase()">
              <text class="ci__day-num">{{ d.day }}</text>
              <text class="ci__day-status">{{ calendarStatusLabel(d.status) }}</text>
              <button v-if="d.canApplyMakeup" class="ci__day-action" @click.stop="openMakeup(d)">补卡</button>
              <button v-if="d.photoFileId" class="ci__day-action" @click.stop="openPhoto(d, true)">原图</button>
              <button v-if="d.watermarkedFileId" class="ci__day-action" @click.stop="openPhoto(d, false)">水印</button>
            </view>
          </view>
        </view>

        <ReportFilePreview ref="checkinPreview" />
        <view class="section-head"><text class="section-head__title">免签申请</text></view>
        <view class="card ci__exempt">
          <button class="btn btn-ghost ci__exempt-toggle" @click="exemptionOpen = !exemptionOpen">
            {{ exemptionOpen ? '收起申请表' : '申请免签' }}
          </button>
          <view v-if="exemptionOpen" class="stack-sm ci__exempt-form">
            <view class="ci__pair">
              <picker mode="date" :value="exemptionForm.startDate" @change="exemptionForm.startDate = $event.detail.value">
                <view class="ci__picker">{{ exemptionForm.startDate || '开始日期' }}</view>
              </picker>
              <picker mode="date" :value="exemptionForm.endDate" @change="exemptionForm.endDate = $event.detail.value">
                <view class="ci__picker">{{ exemptionForm.endDate || '结束日期' }}</view>
              </picker>
            </view>
            <textarea v-model="exemptionForm.reason" class="ci__textarea" maxlength="500" placeholder="请填写免签理由（至少5字）" />
            <view class="row-between">
              <text class="ci__help">{{ exemptionEvidenceName || '可上传免签佐证附件' }}</text>
              <button class="btn btn-ghost" :disabled="exemptionUploading" @click="pickExemptionEvidence">{{ exemptionUploading ? '上传中…' : '上传佐证' }}</button>
            </view>
            <button class="btn btn-primary" :disabled="exemptionSubmitting" @click="submitExemption">{{ exemptionSubmitting ? '提交中…' : '提交指导老师审核' }}</button>
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
                <button v-if="item.status === 'PENDING'" class="ci__withdraw" :disabled="exemptionSubmitting" @click="withdrawExemption(item)">撤回</button>
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
import { chooseSingleFile, uploadBusinessFile } from '@/services/fileApi'
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
      i: null, state: 'loading', error: '', requestedBatch: '', hidden: false,
      generation: currentSessionGeneration(), loadSequence: 0, checkinSequence: 0,
      checkingIn: false, checkinKey: '', checkinNote: '', lastResultNote: '', preflightRule: null,
      photoFileId: '', photoFileName: '', photoUploading: false, photoSequence: 0, disposed: false,
      overseas: false, countryRegion: '',
      timezoneName: this.detectTimezone(),
      calendarMonth: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
      calendarData: null, calendarDays: [], weekLabels: ['一', '二', '三', '四', '五', '六', '日'],
      exemptions: [], exemptionOpen: false, exemptionSubmitting: false, exemptionUploading: false,
      exemptionEvidenceName: '',
      exemptionForm: { startDate: '', endDate: '', reason: '', evidenceFileId: '' }
    }
  },
  computed: {
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
    pause() { this.hidden = true; this.loadSequence++; this.checkinSequence++; this.checkingIn = false; this.$refs?.checkinPreview?.reset() },
    resetAccount() {
      this.photoSequence++
      this.loadSequence++; this.checkinSequence++; this.generation = currentSessionGeneration()
      this.i = null; this.calendarData = null; this.calendarDays = []; this.exemptions = []
      this.requestedBatch = ''; this.checkinKey = ''; this.checkinNote = ''; this.lastResultNote = ''; this.preflightRule = null
      this.photoFileId = ''; this.photoFileName = ''; this.photoUploading = false; this.checkingIn = false
      this.overseas = false; this.countryRegion = ''; this.exemptionEvidenceName = ''; this.exemptionOpen = false
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
      this.error = ''; this.i = null; this.calendarData = null; this.calendarDays = []; this.exemptions = []
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
      this.calendarMonth = String(e.detail.value || '').slice(0, 7)
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
      if (this.exemptionUploading) return
      this.exemptionUploading = true
      try {
        const file = await chooseSingleFile()
        if (!file) return
        const uploaded = await uploadBusinessFile(file, { bizType: 'INTERNSHIP_CHECKIN_EXEMPTION' })
        this.exemptionForm.evidenceFileId = uploaded.fileId
        this.exemptionEvidenceName = uploaded.fileName || file.name || '免签佐证'
      } catch (e) { toast(normalizeError(e).text) }
      finally { this.exemptionUploading = false }
    },
    async submitExemption() {
      if (this.exemptionSubmitting) return
      const f = this.exemptionForm
      if (!f.startDate || !f.endDate) return toast('请选择免签起止日期')
      if (f.startDate > f.endDate) return toast('免签结束日期不能早于开始日期')
      if (String(f.reason || '').trim().length < 5) return toast('免签理由不少于5个字')
      this.exemptionSubmitting = true
      try {
        await studentApi.applyCheckinExemption({
          batchId: this.i.batchId, internshipId: this.i.recordId,
          startDate: f.startDate, endDate: f.endDate,
          reason: String(f.reason || '').trim(), evidenceFileId: f.evidenceFileId || ''
        })
        toast('免签申请已提交')
        this.exemptionForm = { startDate: '', endDate: '', reason: '', evidenceFileId: '' }
        this.exemptionEvidenceName = ''
        this.exemptionOpen = false
        await this.load()
      } catch (e) { toast(normalizeError(e).text) }
      finally { this.exemptionSubmitting = false }
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
</style>
