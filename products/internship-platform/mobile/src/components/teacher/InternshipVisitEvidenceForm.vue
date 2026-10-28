<template>
  <view class="visit-evidence card">
    <view class="ve__head">
      <view class="flex-1">
        <text class="t-md t-bold">记录巡访执行证据 · {{ target.name }}</text>
        <text class="ve__sub">{{ target.enterpriseName || '实习单位' }} · 默认不采集教师位置</text>
      </view>
      <text class="ve__close" @click="$emit('cancel')">关闭</text>
    </view>

    <MobileInlineAlert type="info" description="默认不采集位置。你可主动获取本次位置，随保存提交；位置加密保存，仅供有权限的人员按用途留痕查看。" />
    <view v-if="contextState !== 'ready' || conflict" class="ve__field">
      <text>{{ contextMessage || '正在核对当前计划和学生…' }}</text>
      <button :disabled="!active || submitting || reading" @click="loadContext">{{ reading ? '核对中…' : '重读计划与学生' }}</button>
      <template v-if="latestContext && conflict">
        <text>当前计划第 {{ latestContext.expectedPlanVersion }} 版，实习记录第 {{ latestContext.expectedVersion }} 版；原输入和照片已保留。</text>
        <button :disabled="!active || submitting || reading" @click="adoptContext">已核对，采用当前版本继续</button>
      </template>
    </view>
    <text v-if="originalContext" class="ve__hint">{{ originalContext.planDate || '日期待定' }} · 计划第 {{ originalContext.expectedPlanVersion }} 版 · 实习记录第 {{ originalContext.expectedVersion }} 版</text>
    <view class="ve__field"><text class="ve__label">巡访标题 *</text><input v-model="form.title" class="ve__input" maxlength="200" placeholder="简要说明本次巡访主题，至少2字" /></view>
    <view class="ve__field">
      <text class="ve__label">巡访方式 *</text>
      <picker :range="methodLabels" :value="methodIndex" @change="changeMethod">
        <view class="ve__picker">{{ methodLabels[methodIndex] }} ›</view>
      </picker>
    </view>
    <view class="ve__field"><text class="ve__label">企业联系人 *</text><input v-model="form.contactPerson" class="ve__input" maxlength="100" placeholder="如：企业导师王老师" /></view>
    <view class="ve__field"><text class="ve__label">学生当前工作状态 *</text><textarea v-model="form.workStatus" class="ve__textarea is-short" maxlength="300" placeholder="岗位任务、出勤、适应情况等" /></view>
    <view class="ve__field"><text class="ve__label">企业反馈 *</text><textarea v-model="form.enterpriseFeedback" class="ve__textarea" maxlength="1000" placeholder="企业对学生表现、技能、纪律等真实反馈" /></view>
    <view class="ve__field"><text class="ve__label">事实记录 *</text><textarea v-model="form.facts" class="ve__textarea" maxlength="1600" placeholder="至少 10 字，只记录本次实际沟通/巡访事实" /></view>
    <view class="ve__field"><text class="ve__label">发现问题</text><textarea v-model="form.issues" class="ve__textarea is-short" maxlength="500" placeholder="没有可留空；只写本次发现的问题事实" /></view>
    <view class="ve__field"><text class="ve__label">处理建议</text><textarea v-model="form.advice" class="ve__textarea is-short" maxlength="500" placeholder="给学生/企业的明确建议" /><text class="ve__hint">发现问题或填写处理建议后，会形成整改跟进待办。</text></view>

    <view class="ve__toggle"><view><text class="ve__label">需要后续跟进</text><text class="ve__hint">形成巡访整改待办</text></view><switch :checked="form.needFollow" @change="form.needFollow = !!$event.detail.value" /></view>
    <view class="ve__toggle"><view><text class="ve__label">转为实习风险</text><text class="ve__hint">在同一事务形成正式风险单</text></view><switch :checked="form.needRisk" @change="form.needRisk = !!$event.detail.value" /></view>
    <template v-if="form.needRisk">
      <view class="ve__field">
        <text class="ve__label">风险等级 *</text>
        <picker :range="riskLabels" :value="riskIndex" @change="riskIndex = Number($event.detail.value || 0)">
          <view class="ve__picker">{{ riskLabels[riskIndex] }} ›</view>
        </picker>
      </view>
      <view class="ve__field"><text class="ve__label">转风险原因 *</text><textarea v-model="form.riskReason" class="ve__textarea is-short" maxlength="500" placeholder="至少 5 字，写明需跟进的风险事实" /></view>
    </template>

    <view class="ve__field">
      <text class="ve__label">本次巡访位置（可选）</text>
      <text class="ve__hint">点击后由设备申请一次定位。拒绝或失败可继续填写；保存前可移除。</text>
      <button :disabled="!active || submitting || locating" @click="captureLocation">{{ locating ? '正在获取位置…' : location ? '重新获取本次位置' : '主动获取本次位置' }}</button>
      <template v-if="location">
        <text>已取得本次位置，精度约 {{ Math.round(location.accuracyM) }} 米；保存后登记。</text>
        <button :disabled="submitting" @click="removeLocation">移除本次位置</button>
      </template>
      <text v-if="locationError" role="alert">{{ locationError }}</text>
    </view>
    <view class="ve__field">
      <text class="ve__label">巡访照片</text>
      <button :disabled="!active || submitting || uploading" @click="choosePhoto">{{ uploading ? '照片处理中…' : pendingEvidence ? '更换照片' : '拍照或选择照片' }}</button>
      <template v-if="pendingEvidence">
        <text>{{ pendingEvidence.fileName || '巡访照片' }} · {{ pendingEvidence.statusText }}</text>
        <button v-if="!pendingEvidence.readyForBusiness" :disabled="!active || submitting || uploading" @click="refreshEvidence">读取安全检查结果</button>
        <button v-else :disabled="!active || submitting" @click="openEvidence">查看照片</button>
      </template>
      <text v-if="photoError" role="alert">{{ photoError }}</text>
      <text class="ve__hint">支持一张照片，单张不超过20MB。安全可用后随本次巡访保存，学校按权限查看。</text>
    </view>

    <view class="ve__actions">
      <button class="btn btn-ghost flex-1" :disabled="submitting" @click="$emit('cancel')">取消</button>
      <button class="ve__submit flex-1" :class="{ 'is-disabled': submitDisabled }" :disabled="submitDisabled" plain @click="submit">{{ submitting ? '保存中…' : '保存执行证据' }}</button>
    </view>
  </view>
</template>

<script>
import { teacherInternshipEvidenceV3Api } from '@/services/teacherInternshipEvidenceV3Api'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { uploadBusinessFile, fileSdk } from '@/services/fileApi'
import { normalizeFileReadiness, refreshFileReadiness } from '@/services/fileReadiness.mjs'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { checkinLocationPolicy } from '@/services/checkinPresentation.mjs'

const METHODS = ['ONSITE', 'ONLINE', 'PHONE', 'VIDEO', 'OTHER']
const RISK_LEVELS = ['LOW', 'MEDIUM', 'HIGH']

export default {
  props: {
    target: { type: Object, required: true },
    submitting: { type: Boolean, default: false },
    active: { type: Boolean, default: true },
    conflicted: { type: Boolean, default: false }
  },
  emits: ['submit', 'cancel', 'adopt'],
  data() {
    return {
      contextState: 'loading', contextMessage: '', originalContext: null, latestContext: null,
      localConflict: false, reading: false, readEpoch: 0, photoEpoch: 0, disposed: false,
      generation: currentSessionGeneration(),
      methodLabels: ['现场巡访', '线上沟通', '电话沟通', '视频沟通', '其他'], methodIndex: 0,
      riskLabels: ['低风险', '中风险', '高风险'], riskIndex: 1,
      pendingEvidence: null, uploading: false, photoError: '',
      location: null, locating: false, locationError: '', locationEpoch: 0,
      form: {
        title: '', contactPerson: '', workStatus: '', enterpriseFeedback: '', facts: '', issues: '', advice: '',
        needFollow: false, needRisk: false, riskReason: ''
      }
    }
  },
  computed: {
    conflict() { return this.localConflict || this.conflicted },
    submitDisabled() {
      return !this.active || this.submitting || this.reading || this.uploading || this.locating || this.conflict ||
        this.contextState !== 'ready' || !this.originalContext ||
        (this.pendingEvidence && this.pendingEvidence.readyForBusiness !== true)
    }
  },
  created() { this.originalContext = { ...this.target }; this.loadContext() },
  beforeUnmount() { this.disposed = true; this.readEpoch++; this.photoEpoch++; this.locationEpoch++; this.location = null; this.locating = false; this.reading = false; this.uploading = false },
  watch: {
    active(value) {
      this.readEpoch++; this.reading = false; this.latestContext = null
      this.locationEpoch++; this.locating = false
      if (value) this.loadContext()
      else { this.contextState = 'paused'; this.contextMessage = '返回后重新核对计划，填写内容已保留' }
    },
    conflicted(value) {
      if (value) { this.latestContext = null; this.contextState = 'conflict'; this.contextMessage = '计划或实习状态已变化，请先重读核对；填写内容已保留' }
    }
  },
  methods: {
    capture() {
      return { target: this.target, generation: this.generation, batchId: String(this.target.batchId || ''),
        planId: String(this.target.planId || ''), internshipId: String(this.target.internshipId || '') }
    },
    owns(t) {
      return !this.disposed && t.target === this.target && t.generation === currentSessionGeneration() &&
        t.batchId === String(this.target.batchId || '') && t.planId === String(this.target.planId || '') &&
        t.internshipId === String(this.target.internshipId || '')
    },
    async loadContext() {
      if (!this.active || this.submitting || this.disposed) return
      const t = this.capture(), epoch = ++this.readEpoch
      const current = () => this.active && this.owns(t) && epoch === this.readEpoch
      if (!this.owns(t)) { this.contextState = 'error'; this.contextMessage = '账号已变化，请关闭原草稿重新进入'; return }
      this.reading = true; this.latestContext = null; this.contextMessage = ''
      this.contextState = 'loading'
      try {
        const data = await teacherInternshipEvidenceV3Api.visitTargets(t.batchId, { planId: t.planId, internshipId: t.internshipId })
        if (!current()) return
        const plan = data?.plans?.find(p => String(p.id) === t.planId)
        const student = plan?.students?.find(s => String(s.internshipId) === t.internshipId)
        if (String(data?.batchId) !== t.batchId || String(plan?.batchId) !== t.batchId ||
          !student?.resolvable || String(student.batchId) !== t.batchId || String(student.planId) !== t.planId ||
          !Number.isInteger(student.expectedVersion) || student.expectedVersion < 0 ||
          !Number.isInteger(student.expectedPlanVersion) || student.expectedPlanVersion < 0) {
          this.contextState = 'error'; this.contextMessage = '当前计划中已无可办理的原学生，请关闭后刷新'; return
        }
        if (student.visited) { this.contextState = 'error'; this.contextMessage = '本计划已留巡访记录，请关闭草稿后查看登记结果'; return }
        const fresh = { ...t, expectedVersion: student.expectedVersion, expectedPlanVersion: student.expectedPlanVersion, planDate: plan.planDate }
        const original = this.originalContext
        this.localConflict ||= fresh.expectedVersion !== original?.expectedVersion || fresh.expectedPlanVersion !== original?.expectedPlanVersion
        this.contextState = 'ready'; this.latestContext = fresh
        if (this.conflict) this.contextMessage = '版本已变化，原输入和照片已保留，请核对后明确采用'
      } catch (e) {
        if (!current()) return
        this.contextState = 'error'
        this.contextMessage = normalizeError(e).text
      } finally { if (current()) this.reading = false }
    },
    adoptContext() {
      if (!this.active || this.submitting || this.reading || !this.conflict || !this.latestContext || !this.owns(this.latestContext)) return
      this.originalContext = { ...this.latestContext }; this.localConflict = false
      this.contextMessage = ''; this.$emit('adopt', this.originalContext)
    },
    changeMethod(e) { this.methodIndex = Math.max(0, Math.min(METHODS.length - 1, Number(e.detail.value || 0))) },
    captureLocation() {
      if (!this.active || this.submitting || this.locating || !this.owns(this.capture())) return
      const t = this.capture(), op = ++this.locationEpoch, policy = checkinLocationPolicy(false)
      const current = () => this.active && this.owns(t) && op === this.locationEpoch
      this.location = null; this.locationError = ''; this.locating = true
      uni.getLocation({ type: policy.type,
        success: p => {
          if (!current()) return
          const valid = Number.isFinite(p.latitude) && Math.abs(p.latitude) <= 90 &&
            Number.isFinite(p.longitude) && Math.abs(p.longitude) <= 180 && Number.isFinite(p.accuracy) && p.accuracy >= 0
          if (valid) this.location = { consent: true, latitude: p.latitude, longitude: p.longitude,
            accuracyM: p.accuracy, coordinateSystem: policy.coordinateSystem, capturedAt: new Date().toISOString() }
          else this.locationError = '设备未返回完整有效的位置与精度，请重新获取；正文和照片已保留。'
          this.locating = false
        },
        fail: () => { if (current()) { this.locating = false; this.locationError = '位置未取得，请核对定位权限和设备设置；正文和照片已保留，也可不登记位置。' } }
      })
    },
    removeLocation() { if (!this.submitting) { this.locationEpoch++; this.locating = false; this.location = null; this.locationError = '' } },
    choosePhoto() {
      if (!this.active || this.submitting || this.uploading) return
      const t = this.capture(), op = ++this.photoEpoch
      const current = () => this.owns(t) && op === this.photoEpoch
      if (!current()) return
      this.uploading = true; this.photoError = ''
      uni.chooseImage({ count: 1, sourceType: ['camera', 'album'], sizeType: ['original'],
        success: async res => {
          if (!current()) return
          try {
            const path = res.tempFilePaths?.[0], source = res.tempFiles?.[0] || {}
            if (!path) return
            if (Number(source.size || 0) > 20 * 1024 * 1024) throw new Error('单张照片不能超过20MB')
            const file = normalizeFileReadiness(await uploadBusinessFile({ path, name: source.name || '巡访照片.jpg', size: source.size || 0 }, { bizType: 'INTERNSHIP_VISIT' }))
            if (!current()) return
            if (!file.fileId) throw new Error('照片接收结果缺少编号，请重试')
            this.pendingEvidence = file
          } catch (e) { if (current()) this.photoError = normalizeError(e).text }
          finally { if (current()) this.uploading = false }
        },
        fail: () => { if (current()) this.uploading = false }
      })
    },
    async refreshEvidence() {
      if (!this.active || this.submitting || this.uploading || !this.pendingEvidence) return
      const t = this.capture(), op = ++this.photoEpoch, original = this.pendingEvidence
      const current = () => this.active && this.owns(t) && op === this.photoEpoch && original === this.pendingEvidence
      this.uploading = true; this.photoError = ''
      try {
        const files = await refreshFileReadiness([original], id => fileSdk.metadata(id), current)
        if (current() && files) this.pendingEvidence = files[0]
      } catch (e) { if (current()) this.photoError = '照片安全检查结果读取失败，请重试' }
      finally { if (this.owns(t) && op === this.photoEpoch) this.uploading = false }
    },
    async openEvidence() {
      const t = this.capture()
      if (!this.active || !this.owns(t) || !this.pendingEvidence?.readyForBusiness) return
      try { await fileSdk.open(String(this.pendingEvidence.fileId)) }
      catch (e) { if (this.active && this.owns(t)) this.photoError = '照片打开未完成，请重试' }
    },
    submit() {
      if (this.submitDisabled) return
      const p = this.originalContext
      if (!this.owns(this.capture())) return
      const f = this.form
      if (f.title.trim().length < 2) return toast('巡访标题至少2字')
      if (f.contactPerson.trim().length < 2) return toast('企业联系人至少 2 字')
      if (f.workStatus.trim().length < 2) return toast('请填写学生当前工作状态')
      if (f.enterpriseFeedback.trim().length < 2) return toast('请填写企业反馈')
      if (f.facts.trim().length < 10) return toast('事实记录至少 10 字')
      if (f.needRisk && f.riskReason.trim().length < 5) return toast('转风险原因至少 5 字')
      this.$emit('submit', {
        batchId: String(p.batchId), planId: String(p.planId), expectedPlanVersion: p.expectedPlanVersion,
        visitType: METHODS[this.methodIndex],
        title: f.title.trim(),
        contactPerson: f.contactPerson.trim(),
        workStatus: f.workStatus.trim(),
        enterpriseFeedback: f.enterpriseFeedback.trim(),
        facts: f.facts.trim(),
        issues: f.issues.trim() || null,
        advice: f.advice.trim() || null,
        needFollow: !!f.needFollow,
        needRisk: !!f.needRisk,
        riskLevel: f.needRisk ? RISK_LEVELS[this.riskIndex] : null,
        riskReason: f.needRisk ? f.riskReason.trim() : null,
        fileIds: this.pendingEvidence?.readyForBusiness ? [String(this.pendingEvidence.fileId)] : [],
        location: this.location ? { ...this.location } : null,
        expectedVersion: p.expectedVersion
      })
    }
  }
}
</script>

<style scoped>
.visit-evidence{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3);border:1px solid var(--teacher-200,#bfdbfe)}.ve__head{display:flex;align-items:flex-start;gap:var(--space-2)}.ve__sub{display:block;margin-top:4px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.ve__close{font-size:var(--font-size-sm);color:var(--teacher-700);flex-shrink:0}.ve__field{display:flex;flex-direction:column;gap:6px}.ve__label{display:block;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.ve__hint{display:block;margin-top:2px;font-size:10px;line-height:1.45;color:var(--text-tertiary)}.ve__input,.ve__picker,.ve__textarea{box-sizing:border-box;width:100%;border:1px solid var(--border-base);border-radius:var(--radius-md);background:var(--bg-card);font-size:var(--font-size-base);color:var(--text-primary)}.ve__input,.ve__picker{min-height:var(--touch-target-min);padding:0 12px;display:flex;align-items:center}.ve__textarea{min-height:128px;padding:10px 12px;line-height:1.55}.ve__textarea.is-short{min-height:92px}.ve__toggle{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:10px 0;border-top:1px solid var(--border-light)}.ve__actions{display:flex;gap:var(--space-2);padding-top:var(--space-1)}.ve__submit{min-height:var(--touch-target-min);border:0;border-radius:var(--radius-md);background:var(--teacher-600);color:#fff;font-size:var(--font-size-md)}.ve__submit.is-disabled{opacity:.55}
</style>
