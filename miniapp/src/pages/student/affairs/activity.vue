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
              <button v-if="canEnroll(a)" class="btn btn-primary ac__btn" :disabled="acting === a.activityId" @click="enroll(a)">
                {{ acting === a.activityId ? '…' : '报名' }}
              </button>
              <button v-else-if="canCancel(a)" class="btn btn-ghost ac__btn" :disabled="acting === a.activityId" @click="cancelEnroll(a)">
                {{ acting === a.activityId ? '…' : '取消报名' }}
              </button>
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
              <button v-if="a.status === 'ONGOING' && a.mySignupStatus === 'ENROLLED'"
                class="btn btn-primary ac__btn" :disabled="acting === a.activityId" @click="openCheckin(a)">
                输入签到码
              </button>
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
            <view class="section-head"><text class="section-head__title">按类型</text></view>
            <view class="card ac__summary">
              <view v-for="x in report.byType" :key="x.key" class="ac__summary-row">
                <text>{{ creditTypeLabel(x.key) }}</text><text>{{ x.value }}</text>
              </view>
              <text v-if="!report.byType.length" class="ac__muted">暂无已确认记录</text>
            </view>
            <view class="section-head"><text class="section-head__title">入账明细</text></view>
            <MobileGlobalState v-if="!report.items.length" state="empty" title="暂无入账明细" description="活动结束并由老师确认后才会计入成绩单。" />
            <view v-else class="list-group">
              <view v-for="(x, i) in report.items" :key="x.activityId + '-' + i" class="list-row">
                <view class="flex-1"><text class="t-md">{{ x.remark || '第二课堂记录' }}</text><text class="ac__sub">{{ creditTypeLabel(x.creditType) }} · {{ (x.grantedAt || '').slice(0, 10) }}</text></view>
                <text class="ac__credit">+{{ x.creditValue }}</text>
              </view>
            </view>
          </template>
        </template>
      </view>
    </MobileGlobalState>

    <view v-if="checkinTarget" class="ac__mask" @click.self="closeCheckin">
      <view class="card ac__sheet">
        <text class="card-title">{{ checkinTarget.activityName }}</text>
        <text class="ac__tip">请输入老师现场展示的6位动态签到码。签到码最多5分钟有效。</text>
        <input v-model="checkinCode" type="number" maxlength="6" class="ac__code-input" placeholder="6位签到码" />
        <view class="ac__sheet-actions">
          <button class="btn btn-ghost flex-1" :disabled="acting" @click="closeCheckin">取消</button>
          <button class="btn btn-primary flex-1" :disabled="acting || checkinCode.length !== 6" @click="checkin">确认签到</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const SIGNUP_LABEL = { ENROLLED: '已报名', WAITLIST: '候补中', CHECKED_IN: '已签到', CONFIRMED: '已确认', CANCELLED: '已取消' }
const SIGNUP_TAG = { ENROLLED: 'processing', WAITLIST: 'warning', CHECKED_IN: 'success', CONFIRMED: 'success', CANCELLED: 'default' }
const CREDIT_TYPE = { SECOND_CLASS: '第二课堂', MORAL: '德育积分', VOLUNTEER_HOUR: '志愿时长' }

export default {
  data() {
    return {
      d: null, state: 'loading', tab: 'available', acting: null,
      checkinTarget: null, checkinCode: '', report: null, reportState: 'idle'
    }
  },
  onLoad() { this.load() },
  methods: {
    fmt(v) { return (v || '').slice(0, 16).replace('T', ' ') },
    signupLabel(s) { return SIGNUP_LABEL[s] || s || '未报名' },
    signupTag(s) { return SIGNUP_TAG[s] || 'default' },
    creditTypeLabel(s) { return CREDIT_TYPE[s] || s || '积分' },
    canEnroll(a) { return !a.mySignupStatus || a.mySignupStatus === 'CANCELLED' },
    canCancel(a) { return ['ENROLLED', 'WAITLIST'].includes(a.mySignupStatus) },
    showError(e, fallback) { toast(normalizeError(e).text || (e && e.message) || fallback) },
    load() {
      this.state = 'loading'
      studentApi.getMyActivities().then((d) => { this.d = d || { available: [], mine: [] }; this.state = 'ready' })
        .catch((e) => { this.state = 'error'; this.showError(e, '活动加载失败') })
    },
    enroll(a) {
      if (this.acting) return
      this.acting = a.activityId
      studentApi.enrollActivity(a.activityId, 'ENROLL').then(() => { toast('报名成功'); this.load() })
        .catch((e) => this.showError(e, '报名失败')).finally(() => { this.acting = null })
    },
    cancelEnroll(a) {
      if (this.acting) return
      this.acting = a.activityId
      studentApi.enrollActivity(a.activityId, 'CANCEL').then(() => { toast('已取消报名'); this.load() })
        .catch((e) => this.showError(e, '取消失败')).finally(() => { this.acting = null })
    },
    openCheckin(a) { this.checkinTarget = a; this.checkinCode = '' },
    closeCheckin() { if (!this.acting) { this.checkinTarget = null; this.checkinCode = '' } },
    checkin() {
      if (this.acting || !this.checkinTarget || this.checkinCode.length !== 6) return
      const id = this.checkinTarget.activityId
      this.acting = id
      affairsContractApi.secureActivityCheckin(id, this.checkinCode).then(() => {
        toast('签到成功')
        this.checkinTarget = null
        this.checkinCode = ''
        this.load()
      }).catch((e) => this.showError(e, '签到失败')).finally(() => { this.acting = null })
    },
    openReport() { this.tab = 'report'; if (!this.report) this.loadReport() },
    loadReport() {
      this.reportState = 'loading'
      affairsContractApi.getSecondClassReport().then((d) => {
        this.report = { byType: [], items: [], ...(d || {}) }
        this.reportState = 'ready'
      }).catch((e) => {
        this.reportState = 'error'
        this.showError(e, '成绩单加载失败')
      })
    }
  }
}
</script>

<style scoped>
.ac__tabs { display: flex; background: var(--bg-card); padding: 0 var(--page-padding-mobile); border-bottom: 1px solid var(--border-light); }
.ac__tab { flex: 1; text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-base); color: var(--text-secondary); }
.ac__tab.is-active { color: var(--brand-primary); font-weight: var(--font-weight-semibold); border-bottom: 2px solid var(--brand-primary); }
.ac__row { align-items: center; }
.ac__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ac__btn { flex-shrink: 0; min-height: 32px; padding: 0 var(--space-3); font-size: var(--font-size-sm); margin-left: var(--space-2); }
.ac__score { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; text-align: center; }
.ac__score-label { display: block; font-size: 12px; color: var(--text-tertiary); }
.ac__score-value { display: block; font-size: 26px; font-weight: 800; color: var(--brand-primary); margin-top: 4px; }
.ac__summary-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
.ac__muted { color: var(--text-tertiary); font-size: 13px; }
.ac__credit { font-weight: 700; color: #16a34a; }
.ac__mask { position: fixed; inset: 0; z-index: 1000; background: rgba(15,23,42,.5); display: flex; align-items: flex-end; }
.ac__sheet { width: 100%; border-radius: 18px 18px 0 0; padding: 20px; }
.ac__tip { display: block; margin: 10px 0; font-size: 13px; color: var(--text-secondary); line-height: 1.6; }
.ac__code-input { height: 54px; border: 1px solid var(--border-base); border-radius: 10px; padding: 0 14px; font-size: 26px; letter-spacing: 8px; text-align: center; }
.ac__sheet-actions { display: flex; gap: 12px; margin-top: 16px; }
</style>
