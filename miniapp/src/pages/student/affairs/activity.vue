<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="活动与第二课堂" back />
    <view class="ac__tabs">
      <text class="ac__tab" :class="{ 'is-active': tab === 'available' }" @click="tab = 'available'">可报名</text>
      <text class="ac__tab" :class="{ 'is-active': tab === 'mine' }" @click="tab = 'mine'">我的报名</text>
      <text class="ac__tab" :class="{ 'is-active': tab === 'report' }" @click="openReport">成绩单</text>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <template v-if="tab === 'available'">
          <MobileGlobalState v-if="!d.available.length" state="empty" title="暂无可报名活动" description="学工处发布活动后会显示在这里。" />
          <view class="list-group" v-else>
            <view v-for="a in d.available" :key="a.activityId" class="list-row ac__row">
              <view class="flex-1">
                <text class="t-md">{{ a.activityName }}</text>
                <text class="ac__sub">{{ a.activityTypeLabel }} · {{ fmt(a.startAt) }} · {{ a.location || '—' }}</text>
                <text class="ac__sub" v-if="a.creditValue">确认参加后计入 {{ a.creditValue }}</text>
              </view>
              <button v-if="canEnroll(a)" class="btn btn-primary ac__btn" :disabled="acting === a.activityId" @click="enroll(a)">{{ acting === a.activityId ? '…' : '报名' }}</button>
              <button v-else-if="canCancel(a)" class="btn btn-ghost ac__btn" :disabled="acting === a.activityId" @click="cancelEnroll(a)">{{ acting === a.activityId ? '…' : '取消报名' }}</button>
              <MobileStatusTag v-else :label="signupLabel(a.mySignupStatus)" :type="signupTag(a.mySignupStatus)" />
            </view>
          </view>
        </template>

        <template v-else-if="tab === 'mine'">
          <MobileGlobalState v-if="!d.mine.length" state="empty" title="暂无报名记录" description="在「可报名」中报名后会显示在这里。" />
          <view class="list-group" v-else>
            <view v-for="a in d.mine" :key="a.activityId" class="list-row ac__row">
              <view class="flex-1">
                <text class="t-md">{{ a.activityName }}</text>
                <text class="ac__sub">{{ a.activityTypeLabel }} · {{ fmt(a.startAt) }}</text>
              </view>
              <MobileStatusTag :label="signupLabel(a.mySignupStatus)" :type="signupTag(a.mySignupStatus)" />
              <button v-if="a.status === 'ONGOING' && a.mySignupStatus === 'ENROLLED'" class="btn btn-primary ac__btn" :disabled="acting === a.activityId" @click="openCheckin(a)">输入签到码</button>
            </view>
          </view>
        </template>

        <template v-else>
          <MobileGlobalState v-if="reportState === 'loading'" state="loading" title="正在加载成绩单" />
          <MobileGlobalState v-else-if="reportState === 'error'" state="error" title="成绩单加载失败" description="请重试" @retry="loadReport" />
          <template v-else-if="report">
            <view class="ac__score card">
              <view><text class="ac__score-label">原始合计</text><text class="ac__score-value">{{ report.rawTotal || 0 }}</text></view>
              <view><text class="ac__score-label">加权合计</text><text class="ac__score-value">{{ report.weightedTotal || 0 }}</text></view>
            </view>
            <button class="btn btn-ghost ac__missing-btn" @click="openAppeal(null)">有活动缺记？提交缺记申诉</button>

            <view class="section-head"><text class="section-head__title">按类型</text></view>
            <view class="card ac__summary">
              <view v-for="x in report.byType" :key="x.key" class="ac__summary-row"><text>{{ creditTypeLabel(x.key) }}</text><text>{{ x.value }}</text></view>
              <text v-if="!report.byType.length" class="ac__muted">暂无已确认记录</text>
            </view>

            <view class="section-head"><text class="section-head__title">入账明细</text></view>
            <MobileGlobalState v-if="!report.items.length" state="empty" title="暂无入账明细" description="活动结束并由老师确认后才会计入成绩单。" />
            <view v-else class="list-group">
              <view v-for="(x, i) in report.items" :key="x.activityId + '-' + i" class="list-row ac__credit-row">
                <view class="flex-1"><text class="t-md">{{ x.remark || '第二课堂记录' }}</text><text class="ac__sub">{{ creditTypeLabel(x.creditType) }} · {{ (x.grantedAt || '').slice(0, 10) }}</text></view>
                <text class="ac__credit">+{{ x.creditValue }}</text>
                <button class="btn btn-ghost ac__appeal-btn" @click="openAppeal(x)">申诉</button>
              </view>
            </view>

            <view class="section-head"><text class="section-head__title">我的积分申诉</text></view>
            <MobileInlineAlert v-if="appealError" type="warning" title="申诉记录暂不可用" :description="appealError" />
            <template v-else>
              <MobileGlobalState v-if="!appeals.length" state="empty" title="暂无积分申诉" description="缺记或记错时可提交申诉。" />
              <view v-else class="list-group">
                <view v-for="x in appeals" :key="x.appealId" class="list-row">
                  <view class="flex-1"><text class="t-md">{{ x.appealType === 'MISSING' ? '缺记申诉' : '记错申诉' }}</text><text class="ac__sub">主张：{{ creditTypeLabel(x.claimCreditType) }} {{ x.claimValue }}</text><text class="ac__sub">{{ x.reason }}</text><text class="ac__sub" v-if="x.reviewOpinion">复核意见：{{ x.reviewOpinion }}</text></view>
                  <MobileStatusTag :label="x.statusLabel || x.status" :type="appealTag(x.status)" />
                </view>
              </view>
            </template>
          </template>
        </template>
      </view>
    </MobileGlobalState>

    <view v-if="checkinTarget" class="ac__mask" @click.self="closeCheckin">
      <view class="card ac__sheet">
        <text class="card-title">{{ checkinTarget.activityName }}</text>
        <text class="ac__tip">请输入老师现场展示的6位动态签到码。签到码最多5分钟有效，前导0也必须完整输入。</text>
        <input :value="checkinCode" type="text" inputmode="numeric" maxlength="6" class="ac__code-input" placeholder="6位签到码" @input="onCheckinInput" />
        <view class="ac__sheet-actions"><button class="btn btn-ghost flex-1" :disabled="acting" @click="closeCheckin">取消</button><button class="btn btn-primary flex-1" :disabled="acting || !/^\d{6}$/.test(checkinCode)" @click="checkin">确认签到</button></view>
      </view>
    </view>

    <view v-if="appealVisible" class="ac__mask" @click.self="closeAppeal">
      <view class="card ac__sheet">
        <text class="card-title">{{ appealForm.appealType === 'MISSING' ? '第二课堂缺记申诉' : '第二课堂记错申诉' }}</text>
        <text class="ac__tip" v-if="appealForm.activityName">涉及活动：{{ appealForm.activityName }}</text>
        <picker mode="selector" :range="creditOptions" range-key="label" @change="onCreditType">
          <view class="ac__picker">主张类型：{{ creditTypeLabel(appealForm.claimCreditType) }}</view>
        </picker>
        <input v-model="appealForm.claimValue" type="digit" class="ac__picker" placeholder="主张数值（必填，0.01-9999.99）" />
        <text class="ac__field-error" v-if="appealForm.claimValue !== '' && claimError">{{ claimError }}</text>
        <textarea v-model="appealForm.reason" class="ac__textarea" maxlength="1000" placeholder="说明缺记或记错情况（5-1000字）" />
        <text class="ac__counter">{{ appealForm.reason.trim().length }}/1000</text>
        <view class="ac__sheet-actions"><button class="btn btn-ghost flex-1" :disabled="appealSubmitting" @click="closeAppeal">取消</button><button class="btn btn-primary flex-1" :disabled="appealSubmitting || !appealValid" @click="submitAppeal">{{ appealSubmitting ? '提交中…' : '提交申诉' }}</button></view>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { affairsAppealApi } from '@/services/affairsAppealApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const SIGNUP_LABEL = { ENROLLED: '已报名', WAITLIST: '候补中', CHECKED_IN: '已签到', CONFIRMED: '已确认', CANCELLED: '已取消' }
const SIGNUP_TAG = { ENROLLED: 'processing', WAITLIST: 'warning', CHECKED_IN: 'success', CONFIRMED: 'success', CANCELLED: 'default' }
const CREDIT_TYPE = { SECOND_CLASS: '第二课堂', MORAL: '德育积分', VOLUNTEER_HOUR: '志愿时长' }

export default {
  data() {
    return {
      d: null, state: 'loading', tab: 'available', acting: null, checkinTarget: null, checkinCode: '',
      report: null, reportState: 'idle', appeals: [], appealError: '', appealVisible: false, appealSubmitting: false,
      appealForm: { appealType: 'MISSING', activityId: '', activityName: '', claimCreditType: 'SECOND_CLASS', claimValue: '', reason: '' },
      creditOptions: Object.entries(CREDIT_TYPE).map(([value, label]) => ({ value, label }))
    }
  },
  computed: {
    claimError() {
      const value = Number(this.appealForm.claimValue)
      if (!Number.isFinite(value) || value <= 0) return '主张数值必须大于0'
      if (value > 9999.99) return '主张数值不得超过9999.99'
      if (Math.round(value * 100) !== value * 100) return '主张数值最多保留2位小数'
      return ''
    },
    appealValid() {
      const reason = this.appealForm.reason.trim()
      return !this.claimError && this.appealForm.claimValue !== '' && reason.length >= 5 && reason.length <= 1000
    }
  },
  onLoad() { this.load() },
  methods: {
    fmt(v) { return (v || '').slice(0, 16).replace('T', ' ') }, signupLabel(s) { return SIGNUP_LABEL[s] || s || '未报名' }, signupTag(s) { return SIGNUP_TAG[s] || 'default' },
    creditTypeLabel(s) { return CREDIT_TYPE[s] || s || '积分' }, appealTag(s) { return s === 'APPROVED' ? 'success' : s === 'REJECTED' ? 'danger' : 'warning' },
    canEnroll(a) { return !a.mySignupStatus || a.mySignupStatus === 'CANCELLED' }, canCancel(a) { return ['ENROLLED', 'WAITLIST'].includes(a.mySignupStatus) },
    showError(e, fallback) { toast(normalizeError(e).text || (e && e.message) || fallback) },
    load() { this.state = 'loading'; studentApi.getMyActivities().then((d) => { this.d = d || { available: [], mine: [] }; this.state = 'ready' }).catch((e) => { this.state = 'error'; this.showError(e, '活动加载失败') }) },
    enroll(a) { if (this.acting) return; this.acting = a.activityId; studentApi.enrollActivity(a.activityId, 'ENROLL').then(() => { toast('报名成功'); this.load() }).catch((e) => this.showError(e, '报名失败')).finally(() => { this.acting = null }) },
    cancelEnroll(a) {
      if (this.acting) return
      uni.showModal({ title: '确认取消报名', content: `确定取消“${a.activityName || '该活动'}”的报名吗？`, confirmText: '确认取消', success: (r) => {
        if (!r.confirm) return
        this.acting = a.activityId
        studentApi.enrollActivity(a.activityId, 'CANCEL').then(() => { toast('已取消报名'); this.load() }).catch((e) => this.showError(e, '取消失败')).finally(() => { this.acting = null })
      } })
    },
    openCheckin(a) { this.checkinTarget = a; this.checkinCode = '' }, closeCheckin() { if (!this.acting) { this.checkinTarget = null; this.checkinCode = '' } },
    onCheckinInput(e) { this.checkinCode = String((e && e.detail && e.detail.value) || '').replace(/\D/g, '').slice(0, 6) },
    checkin() { if (this.acting || !this.checkinTarget || !/^\d{6}$/.test(this.checkinCode)) return; const id = this.checkinTarget.activityId; this.acting = id; affairsContractApi.secureActivityCheckin(id, this.checkinCode).then(() => { toast('签到成功'); this.checkinTarget = null; this.checkinCode = ''; this.load() }).catch((e) => this.showError(e, '签到失败')).finally(() => { this.acting = null }) },
    openReport() { this.tab = 'report'; if (!this.report) this.loadReport() },
    async loadReport() {
      this.reportState = 'loading'; this.appealError = ''
      const [reportResult, appealResult] = await Promise.allSettled([affairsContractApi.getSecondClassReport(), affairsAppealApi.getMyCreditAppeals()])
      if (reportResult.status === 'rejected') {
        this.reportState = 'error'; this.showError(reportResult.reason, '成绩单加载失败'); return
      }
      this.report = { byType: [], items: [], ...(reportResult.value || {}) }
      if (appealResult.status === 'fulfilled') this.appeals = (appealResult.value && appealResult.value.items) || []
      else { this.appeals = []; this.appealError = normalizeError(appealResult.reason).text || '申诉记录加载失败，请稍后重试' }
      this.reportState = 'ready'
    },
    openAppeal(item) {
      this.appealForm = { appealType: item ? 'WRONG' : 'MISSING', activityId: item ? item.activityId : '', activityName: item ? item.remark : '', claimCreditType: item ? item.creditType : 'SECOND_CLASS', claimValue: item && item.creditValue != null ? String(item.creditValue) : '', reason: '' }
      this.appealVisible = true
    },
    closeAppeal() { if (!this.appealSubmitting) this.appealVisible = false },
    onCreditType(e) { this.appealForm.claimCreditType = this.creditOptions[Number(e.detail.value)].value },
    submitAppeal() {
      if (this.appealSubmitting || !this.appealValid) return
      this.appealSubmitting = true
      affairsAppealApi.submitCreditAppeal({
        appealType: this.appealForm.appealType, activityId: this.appealForm.activityId || undefined,
        claimCreditType: this.appealForm.claimCreditType,
        claimValue: Number(this.appealForm.claimValue),
        reason: this.appealForm.reason.trim()
      }).then(() => { toast('积分申诉已提交'); this.appealVisible = false; this.loadReport() })
        .catch((e) => this.showError(e, '申诉提交失败')).finally(() => { this.appealSubmitting = false })
    }
  }
}
</script>

<style scoped>
.ac__tabs { display: flex; background: var(--bg-card); padding: 0 var(--page-padding-mobile); border-bottom: 1px solid var(--border-light); }
.ac__tab { flex: 1; text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-base); color: var(--text-secondary); }
.ac__tab.is-active { color: var(--brand-primary); font-weight: var(--font-weight-semibold); border-bottom: 2px solid var(--brand-primary); }
.ac__row { align-items: center; }.ac__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }.ac__btn { flex-shrink: 0; min-height: 32px; padding: 0 var(--space-3); font-size: var(--font-size-sm); margin-left: var(--space-2); }
.ac__score { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; text-align: center; }.ac__score-label { display: block; font-size: 12px; color: var(--text-tertiary); }.ac__score-value { display: block; font-size: 26px; font-weight: 800; color: var(--brand-primary); margin-top: 4px; }
.ac__missing-btn { width: 100%; margin-top: 10px; }.ac__summary-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-light); }.ac__muted { color: var(--text-tertiary); font-size: 13px; }.ac__credit { font-weight: 700; color: #16a34a; }.ac__credit-row { flex-wrap: wrap; }.ac__appeal-btn { font-size: 12px; padding: 0 8px; }
.ac__mask { position: fixed; inset: 0; z-index: 1000; background: rgba(15,23,42,.5); display: flex; align-items: flex-end; }.ac__sheet { width: 100%; border-radius: 18px 18px 0 0; padding: 20px; }.ac__tip { display: block; margin: 10px 0; font-size: 13px; color: var(--text-secondary); line-height: 1.6; }.ac__code-input { height: 54px; border: 1px solid var(--border-base); border-radius: 10px; padding: 0 14px; font-size: 26px; letter-spacing: 8px; text-align: center; }.ac__sheet-actions { display: flex; gap: 12px; margin-top: 16px; }.ac__picker { height: 42px; line-height: 42px; border: 1px solid var(--border-base); border-radius: 8px; padding: 0 10px; margin-top: 10px; }.ac__textarea { width: 100%; min-height: 90px; box-sizing: border-box; border: 1px solid var(--border-base); border-radius: 8px; padding: 10px; margin-top: 10px; }.ac__field-error { display: block; margin-top: 5px; color: #dc2626; font-size: 12px; }.ac__counter { display: block; margin-top: 3px; text-align: right; color: #94a3b8; font-size: 11px; }
</style>
