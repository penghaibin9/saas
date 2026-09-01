<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="o">
        <!-- 报到总览 -->
        <view class="or__hero card">
          <text class="or__hero-batch">{{ o.batch }}</text>
          <view class="or__hero-status">
            <text class="or__hero-icon" :class="{ 'is-pending': !reportDone }">{{ reportDone ? '✓' : '…' }}</text>
            <view class="flex-1">
              <text class="t-lg t-bold">{{ o.overallText }}</text>
              <text class="or__hero-sub">{{ heroSub }}</text>
            </view>
          </view>
          <view class="or__code" :class="{ 'is-invalid': !o.reportCode.canIssue }" @click="go('/pages/student/orientation/code/index')">
            <view class="flex-1">
              <text class="or__code-label">一次性现场报到凭证</text>
              <text class="or__code-value">{{ reportCodeText }}</text>
            </view>
            <text class="or__code-note">{{ o.reportCode.note }}</text>
          </view>
        </view>

        <view v-if="!reportDone" class="or__next card stack-sm">
          <view class="row-between">
            <text class="t-md t-bold">下一步</text>
            <text class="or__next-tag">{{ nextAction.owner }}</text>
          </view>
          <text class="or__next-title">{{ nextAction.title }}</text>
          <text class="or__next-desc">{{ nextAction.description }}</text>
          <button v-if="nextAction.path" class="btn btn-primary" @click="go(nextAction.path)">{{ nextAction.button }}</button>
        </view>

        <view class="section-head"><text class="section-head__title">报到资格与缴费</text></view>
        <view class="card stack-sm">
          <view class="row-between">
            <text class="t-md t-bold">{{ qualificationText }}</text>
            <text class="or__qualification" :class="{ 'is-ok': o.qualification && o.qualification.verdict === 'QUALIFIED' }">{{ qualificationBadge }}</text>
          </view>
          <text class="or__payment">缴费状态：{{ paymentText }} · 应缴 ¥{{ o.payment && o.payment.payableAmount || '0.00' }} · 已缴 ¥{{ o.payment && o.payment.paidAmount || '0.00' }}</text>
          <view v-if="studentBlockers.length" class="or__status-group">
            <text class="or__status-label">你还需要完成</text>
            <text v-for="item in studentBlockers" :key="item.code + item.step" class="or__blocker">{{ item.message }}</text>
          </view>
          <view v-if="schoolBlockers.length" class="or__status-group is-school">
            <text class="or__status-label">学校正在处理</text>
            <text v-for="item in schoolBlockers" :key="item.code + item.step" class="or__school-item">{{ friendlySchoolMessage(item) }}</text>
          </view>
        </view>

        <!-- 快捷操作 -->
        <view v-if="!reportDone" class="or__actions">
          <view class="or__action" @click="go('/pages/student/orientation/collect/index')">
            <text class="or__action-ic">📝</text><text>预报到信息采集</text>
          </view>
          <view class="or__action" @click="go('/pages/student/orientation/arrival/index')">
            <text class="or__action-ic">🚆</text><text>到校计划</text>
          </view>
          <view class="or__action" @click="go('/pages/student/orientation/materials/index')">
            <text class="or__action-ic">📎</text><text>迎新材料</text>
          </view>
          <view v-if="o.greenChannelStatus === 'NOT_APPLIED'" class="or__action" @click="go('/pages/student/orientation/green-channel/index')">
            <text class="or__action-ic">🤝</text><text>绿色通道申请</text>
          </view>
        </view>

        <!-- 报到流程时间线 -->
        <view class="section-head"><text class="section-head__title">报到流程</text></view>
        <view class="card">
          <MobileTimeline :nodes="o.steps" />
        </view>

        <!-- 联系人 -->
        <view class="section-head"><text class="section-head__title">联系人</text></view>
        <view class="card stack-sm">
          <view v-for="c in o.contacts" :key="c.role" class="or__contact">
            <view class="or__contact-avatar">{{ c.name.slice(0,1) }}</view>
            <view class="flex-1">
              <text class="t-md">{{ c.name }}</text>
              <text class="or__contact-role">{{ c.role }}</text>
            </view>
            <view class="or__contact-call" @click="call(c)">☎ 联系</view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { go, toast } from '@/utils/nav'
export default {
  data() { return { o: null, state: 'loading' } },
  onShow() { this.load() },
  computed: {
    // 只有真实报到状态为「已现场报到 / 学院已确认」（mock 兼容 REGISTERED）才算完成，
    // 未报到/预报到不再显示"全部报到环节已完成"的假完成态
    reportDone() {
      const s = this.o && this.o.overallStatus
      return s === 'CHECKED_IN' || s === 'COLLEGE_CONFIRMED' || s === 'REGISTERED'
    },
    heroSub() {
      if (!this.o) return ''
      if (this.reportDone) return '全部报到环节已完成，欢迎加入！'
      if (this.o.blocked && this.o.blocked.reason) return '报到卡点：' + this.o.blocked.reason
      return '报到进行中，请尽快完成剩余报到环节'
    },
    qualificationText() {
      const verdict = this.o?.qualification?.verdict
      return ({ QUALIFIED: '已具备报到资格', MANUAL_REVIEW: '学校处理中', NOT_QUALIFIED: '还有事项未完成' })[verdict] || '资格待确认'
    },
    qualificationBadge() {
      return this.o?.qualification?.verdict === 'QUALIFIED' ? '已通过' : '持续更新'
    },
    qualificationBlockers() { return (this.o && this.o.qualification && this.o.qualification.blockers) || [] },
    requiredMaterialFacts() { return this.o?.qualification?.facts?.materials?.required || [] },
    materialsWaitingReview() {
      return this.requiredMaterialFacts.length > 0 && this.requiredMaterialFacts.every((item) => item.status === 'UPLOADED')
    },
    studentBlockers() {
      return this.qualificationBlockers.filter((item) => item.step === 'INFO' || (item.step === 'MATERIAL' && !this.materialsWaitingReview))
    },
    schoolBlockers() {
      const seen = new Set()
      return this.qualificationBlockers.filter((item) => {
        if (item.step === 'INFO' || (item.step === 'MATERIAL' && !this.materialsWaitingReview)) return false
        const key = this.materialsWaitingReview && item.step === 'MATERIAL' ? 'MATERIAL_REVIEW' : `${item.code}:${item.step}`
        if (seen.has(key)) return false
        seen.add(key)
        return true
      })
    },
    stepMap() {
      return Object.fromEntries((this.o?.steps || []).map((item) => [item.key, item.status]))
    },
    nextAction() {
      const done = (key) => ['DONE', 'WAIVED', 'NOT_REQUIRED'].includes(this.stepMap[key])
      if (!done('INFO')) return { owner: '需要你完成', title: '先核对个人信息', description: '确认联系方式、生源地和紧急联系人，提交后自动进入下一环节。', button: '去核对信息', path: '/pages/student/orientation/collect/index' }
      if (!this.o?.selfService?.arrivalPlan) return { owner: '需要你完成', title: '填写到校计划', description: '选择预计到校时间和交通方式，需要接站时一并登记。', button: '填写到校计划', path: '/pages/student/orientation/arrival/index' }
      if (!done('MATERIAL') && this.materialsWaitingReview) return { owner: '学校处理中', title: '材料已提交，等待审核', description: '身份证明和录取通知书已交齐，无需重复上传。审核结果会在这里自动更新。', button: '', path: '' }
      if (!done('MATERIAL')) return { owner: '需要你完成', title: '上传必交材料', description: '请提交身份证明和录取通知书；学校审核结果会在这里更新。', button: '上传迎新材料', path: '/pages/student/orientation/materials/index' }
      if (this.o?.qualification?.verdict !== 'QUALIFIED') return { owner: '学校处理中', title: '你的线上事项已提交', description: '缴费同步、宿舍安排和异常复核由学校继续处理。无需重复填写，请留意本页状态和学校通知。', button: '', path: '' }
      return { owner: '需要你完成', title: '领取现场报到凭证', description: '资格已通过，签发一次性凭证后到校出示即可。', button: '领取报到凭证', path: '/pages/student/orientation/code/index' }
    },
    reportCodeText() {
      const status = this.o?.reportCode?.status
      return ({ ELIGIBLE: '点击签发', ISSUED: '点击刷新', CHECKED_IN: '已完成报到', FINALIZED: '学院已确认' })[status] || '暂不可签发'
    },
    paymentText() { return ({ PAID: '已缴清', PARTIAL: '部分缴费', UNPAID: '未缴费', WAIVED: '已减免', DEFERRED: '已批准缓缴', GREEN_CHANNEL: '绿色通道' })[this.o && this.o.payStatus] || '待同步' }
  },
  methods: {
    go,
    friendlySchoolMessage(item) {
      const mapped = ({
        MATERIAL_EVIDENCE_NOT_READY: '材料已交齐，正在等待学校审核。',
        PAYMENT_FACT_MISSING: '缴费结果待系统同步；如已缴费，无需重复操作。',
        DORM_NOT_CONFIRMED: '宿舍正在安排，结果确定后会自动显示。',
        OPEN_EXCEPTION_PAYMENT: '学校正在复核迎新异常事项。'
      })[item.code]
      if (mapped) return mapped
      if (String(item.code || '').startsWith('OPEN_EXCEPTION')) return '学校正在复核迎新异常事项。'
      return item.message
    },
    load() {
      this.state = 'loading'
      studentApi.getOrientation().then((d) => { this.o = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    call(c) { uni.makePhoneCall({ phoneNumber: c.phone, fail: () => toast('拨号未成功，可手动拨打：' + (c.phone || '')) }) }
  }
}
</script>

<style scoped>
.or__hero-batch { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.or__hero-status { display: flex; align-items: center; gap: var(--space-3); margin: var(--space-3) 0; }
.or__hero-icon { width: 40px; height: 40px; border-radius: var(--radius-full); background: var(--success-500); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 22px; }
.or__hero-icon.is-pending { background: var(--warning-500); }
.or__hero-sub { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.or__code { display: flex; align-items: center; gap: var(--space-3); background: var(--primary-50); border-radius: var(--radius-md); padding: var(--space-3); }
.or__code.is-invalid { background: var(--gray-100); }
.or__code-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.or__code-value { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); letter-spacing: 1px; }
.or__code-note { font-size: var(--font-size-xs); color: var(--text-tertiary); max-width: 44%; text-align: right; }
.or__contact { display: flex; align-items: center; gap: var(--space-3); }
.or__contact-avatar { width: 38px; height: 38px; border-radius: var(--radius-full); background: var(--primary-50); color: var(--brand-primary); display: flex; align-items: center; justify-content: center; }
.or__contact-role { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.or__contact-call { font-size: var(--font-size-sm); color: var(--brand-primary); border: 1px solid var(--brand-primary); border-radius: var(--radius-full); padding: 5px 12px; }
.or__actions { display: flex; gap: var(--space-3); }
.or__action { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4) var(--space-2); box-shadow: var(--shadow-card); font-size: var(--font-size-sm); color: var(--text-secondary); }
.or__action-ic { font-size: 22px; }
.or__qualification { font-size: var(--font-size-xs); color: var(--warning-600); }
.or__qualification.is-ok { color: var(--success-600); }
.or__payment { font-size: var(--font-size-sm); color: var(--text-secondary); }
.or__blocker { font-size: var(--font-size-sm); color: var(--danger-600); line-height: 1.5; }
.or__next { border: 1px solid var(--primary-100); background: linear-gradient(135deg, var(--primary-50), var(--bg-card)); }
.or__next-tag { font-size: var(--font-size-xs); color: var(--brand-primary); background: var(--primary-50); border-radius: var(--radius-full); padding: 4px 9px; }
.or__next-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.or__next-desc { font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.6; }
.or__status-group { display: flex; flex-direction: column; gap: 5px; padding-top: 8px; border-top: 1px solid var(--border-light); }
.or__status-group.is-school { background: var(--gray-50); border-radius: var(--radius-md); border-top: 0; padding: 10px; }
.or__status-label { font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); color: var(--text-tertiary); }
.or__school-item { font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.5; }
</style>
