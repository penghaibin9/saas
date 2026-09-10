<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="毕业进度" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="gr__hero" :class="overallPassed ? 'is-ok' : 'is-warn'">
          <view class="gr__hero-main">
            <text class="gr__eyebrow">教务学业 · 毕业资格自查</text>
            <text class="gr__hero-title">{{ overallPassed ? '当前毕业条件已通过实时核验' : items.length ? '毕业条件还有待处理事项' : '实时自查结果待核对' }}</text>
            <text class="gr__hero-desc">{{ overallPassed ? '当前自查条件已满足，最终毕业结论以学校正式审核为准。' : '逐项核对待处理条件，查看办理建议。' }}</text>
            <view class="gr__hero-chips">
              <text>{{ formalText }}</text><text v-if="items.length">{{ passedCount }}项已通过</text><text v-if="pendingCount">{{ pendingCount }}项待处理</text>
            </view>
          </view>
        </view>

        <view class="gr__formal card">
          <text class="gr__item-name">学校正式毕业审核</text>
          <text class="gr__ev">{{ formalText }}</text>
          <text class="gr__ev">{{ formalStatusText }}</text>
        </view>

        <MobileAcademicDecisionCard
          v-if="safeDecisionText"
          class="gr__decision"
          :trace="safeDecisionTrace"
          :content="safeDecisionText"
          audience="student"
        />



        <view class="gr__section-head">
          <view><text class="gr__section-kicker">毕业条件清单</text><text class="gr__section-title">逐项核对真实业务事实</text></view>
          <text class="gr__section-count">{{ items.length }}项</text>
        </view>

        <view v-if="items.length" class="gr__list">
          <view v-for="it in items" :key="it.item" class="gr__item" :class="badge(it.result)">
            <view class="gr__item-icon"><text>{{ it.result === 'PASS' ? '✓' : '!' }}</text></view>
            <view class="gr__item-main">
              <view class="gr__item-head">
                <text class="gr__item-name">{{ ITEM[it.item] || '毕业条件' }}</text>
                <text class="gr__badge" :class="badge(it.result)">{{ res(it.result) }}</text>
              </view>
              <button class="gr__detail" @click="expandedItem = expandedItem === it.item ? '' : it.item">{{ expandedItem === it.item ? '收起核验依据' : '查看核验依据' }}</button>
              <text v-if="expandedItem === it.item" class="gr__ev">{{ studentEvidence(it) }}</text>
              <button v-if="expandedItem === it.item && remedy(it.item)" class="gr__detail" @click="goRemedy(it.item)">{{ remedy(it.item).label }}</button>
            </view>
          </view>
        </view>
        <view v-else class="gr__empty">
          <view class="gr__empty-icon"><text>—</text></view>
          <text class="gr__empty-title">暂时没有可展示的毕业核验项</text>
          <text class="gr__empty-desc">{{ safeNote }}</text>
        </view>

        <view class="gr__trust">
          <view class="gr__trust-icon"><text>i</text></view>
          <view class="flex-1">
            <text class="gr__trust-title">{{ data.hasAudit ? '实时自查与正式毕业结论分开保存' : '当前结果是实时自查，不等同正式毕业结论' }}</text>
            <text class="gr__trust-text">{{ safeNote }}</text>
          </view>
        </view>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import MobileAcademicDecisionCard from '@/components/MobileAcademicDecisionCard.vue'
import { studentApi } from '@/services/studentApi'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { go } from '@/utils/nav'
const ITEM = {
  STATUS: '学籍状态', CREDIT: '总学分', COURSE_REQUIRED: '必修课程', COURSE_ELECTIVE: '选修学分', PRACTICE: '实践环节',
  INTERNSHIP: '岗位实习', GRADUATION_DESIGN: '毕业设计', DISCIPLINE: '处分情况', EMPLOYMENT: '就业填报', ARCHIVE: '档案归档', FEE: '费用提醒'
}
const GRADUATION_ITEMS = new Set(Object.keys(ITEM))
const GRADUATION_RESULTS = new Set(['PASS', 'FAIL', 'UNKNOWN'])
const CONC = { GRADUATED: '毕业', COMPLETED: '结业', DELAYED: '延期毕业' }
const TECHNICAL_TEXT = /\b(select|insert|update|delete|from|where)\b|tenant[_\s]*id|permission|provider|stack\s*trace|traceback|exception|sql|主键|堆栈|权限内部|模型编号|\b(student_status|status|program(?:id|version|bindingid)?)\s*=/i

function studentSafeText(value, fallback) {
  const text = typeof value === 'string' ? value.trim() : ''
  if (!text || TECHNICAL_TEXT.test(text)) return fallback
  return text
}
function safeGraduationItem(item) {
  const code = String(item && item.item || '').toUpperCase()
  if (!GRADUATION_ITEMS.has(code)) return null
  const result = String(item && item.result || 'UNKNOWN').toUpperCase()
  return { item: code, result: GRADUATION_RESULTS.has(result) ? result : 'UNKNOWN', evidence: studentSafeText(item && item.evidence, '') }
}
function projectGraduation(data) {
  const items = Array.isArray(data && data.items) ? data.items.map(safeGraduationItem).filter(Boolean) : []
  const conclusion = String(data && data.conclusion || '').toUpperCase()
  const status = String(data && data.status || '').toUpperCase()
  const decisionText = data && typeof data.decisionText === 'object' && !Array.isArray(data.decisionText) ? data.decisionText : null
  return {
    hasAudit: data && data.hasAudit === true,
    overall: ['SYSTEM_PASSED', 'SYSTEM_ABNORMAL'].includes(String(data && data.overall || '').toUpperCase()) ? String(data.overall).toUpperCase() : '',
    conclusion: Object.prototype.hasOwnProperty.call(CONC, conclusion) ? conclusion : '',
    status: ['WAIT_PRECHECK', 'SYSTEM_PASSED', 'SYSTEM_ABNORMAL', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW', 'GRADUATED', 'COMPLETED', 'DELAYED'].includes(status) ? status : '',
    items,
    decisionText: decisionText ? {
      title: studentSafeText(decisionText.title, ''),
      reason: studentSafeText(decisionText.reason, ''),
      nextStep: studentSafeText(decisionText.nextStep, '')
    } : null,
    note: studentSafeText(data && data.note, '')
  }
}
export default {
  components: { AcademicPageNav, AcademicPageState, MobileAcademicDecisionCard },
  data() { return { data: null, state: 'loading', ITEM, requestEpoch: 0, hidden: false, identity: currentSessionGeneration(), expandedItem: '' } },
  computed: {
    items() { return (this.data && Array.isArray(this.data.items)) ? this.data.items : [] },
    passedCount() { return this.items.filter((item) => String(item.result || '').toUpperCase() === 'PASS').length },
    pendingCount() { return this.items.length - this.passedCount },
    overallPassed() { return String((this.data && this.data.overall) || '').toUpperCase() === 'SYSTEM_PASSED' },
    formalText() {
      if (!this.data || !this.data.hasAudit) return '尚未纳入正式预审'
      if (this.data.conclusion) return `正式结论：${this.concText(this.data.conclusion)}`
      return '已纳入正式预审'
    },
    formalStatusText() {
      if (!this.data || !this.data.hasAudit) return '当前仅有实时自查结果，尚无学校正式毕业审核状态。'
      return { WAIT_PRECHECK: '等待学校预审', SYSTEM_PASSED: '正式预审条件通过，仍需学校审核', SYSTEM_ABNORMAL: '正式预审存在待处理条件', COLLEGE_REVIEW: '学院审核中', ACADEMIC_REVIEW: '教务终审中', GRADUATED: '学校已形成毕业审核结果', COMPLETED: '学校已形成结业审核结果', DELAYED: '学校已形成延期毕业审核结果' }[this.data.status] || '审核进度请以学校通知为准。'
    },
    safeDecisionText() {
      const content = this.data && this.data.decisionText
      if (!content && !(this.data && this.data.decisionTrace)) return null
      return {
        title: studentSafeText(content && content.title, this.overallPassed ? '当前实时自查通过' : '毕业条件待核对'),
        reason: studentSafeText(content && content.reason, '本页自查结果不代表学校已批准毕业。'),
        nextStep: studentSafeText(content && content.nextStep, this.overallPassed ? '关注学校正式毕业审核通知。' : '查看各项核验依据，联系教务老师核对待处理事项。')
      }
    },
    safeDecisionTrace() { return { domain: 'GRADUATION', decision: this.overallPassed ? 'ALLOWED' : 'BLOCKED' } },
    safeNote() { return studentSafeText(this.data && this.data.note, '刷新页面不会创建新的正式毕业预审记录；最终毕业结论以学校正式审核形成的事实为准。') }
  },
  onLoad() { this.load() },
  onShow() { if (this.hidden || this.identity !== currentSessionGeneration()) { this.hidden = false; this.load() } },
  onHide() { this.hidden = true; this.requestEpoch += 1 },
  onUnload() { this.hidden = true; this.requestEpoch += 1 },
  methods: {
    remedy(item) { return { STATUS: { route: 'status', label: '核对学籍与异动' }, CREDIT: { route: 'credits', label: '查看学分修读' }, COURSE_REQUIRED: { route: 'makeup', label: '查看课程补救' }, COURSE_ELECTIVE: { route: 'credits', label: '查看选修学分' } }[item] || null },
    goRemedy(item) { const target = this.remedy(item); if (target) go('/pages/student/academic-affairs/' + target.route) },
    res(r) { return r === 'PASS' ? '已通过' : r === 'FAIL' ? '未达标' : '待核验' },
    concText(c) { return CONC[c] || '请查看学校审核通知' },
    badge(r) { return r === 'PASS' ? 'is-ok' : r === 'FAIL' ? 'is-bad' : 'is-wait' },
    evidenceFallback(it) {
      return it.result === 'PASS' ? '学校业务系统已记录满足该项条件的有效事实。' : '当前正式数据还不足以确认该项通过，请按上方建议处理后重新核验。'
    },
    studentEvidence(it) { return studentSafeText(it && it.evidence, this.evidenceFallback(it || {})) },
    clearGraduationData() { this.data = null; this.expandedItem = '' },
    load() {
      const identity = currentSessionGeneration()
      if (identity !== this.identity) { this.clearGraduationData(); this.identity = identity }
      const epoch = ++this.requestEpoch
      this.state = 'loading'
      return studentApi.getMyGraduation().then((d) => {
        if (epoch !== this.requestEpoch || this.hidden || identity !== currentSessionGeneration()) return
        if (!d || typeof d !== 'object' || Array.isArray(d) || (d.hasAudit !== false && !Array.isArray(d.items))) throw new Error('毕业信息暂时无法核对')
        this.data = projectGraduation(d); this.state = 'ready'
      }).catch((error) => {
        if (epoch !== this.requestEpoch || this.hidden || identity !== currentSessionGeneration()) return
        const forbidden = Number(error?.httpStatus) === 403 || /^403/.test(String(error?.code || ''))
        if (forbidden) this.clearGraduationData()
        this.state = forbidden ? 'forbidden' : 'error'
      })
    }
  }
}
</script>

<style scoped>
.gr__formal { margin-top: 14px; }
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.gr__detail { margin: 6px 0 0; padding: 0; min-height: 40px; background: transparent; color: var(--brand-primary); font-size: 12px; text-align: left; }
.gr__detail::after { border: 0; }
.gr__hero { display: flex; align-items: stretch; justify-content: space-between; gap: var(--space-3); padding: var(--space-4); border: 1px solid rgba(217,119,6,.20); border-radius: 18px; background: linear-gradient(135deg, rgba(255,255,255,.98), rgba(255,247,237,.94)); box-shadow: var(--shadow-card); }
.gr__hero.is-ok { border-color: rgba(22,163,74,.18); background: linear-gradient(135deg, rgba(255,255,255,.98), rgba(240,253,244,.94)); }
.gr__hero-main { flex: 1; min-width: 0; }
.gr__eyebrow { display: block; font-size: 10px; font-weight: 700; letter-spacing: 1px; color: #b45309; }
.gr__hero.is-ok .gr__eyebrow { color: #15803d; }
.gr__hero-title { display: block; margin-top: 5px; font-size: 18px; font-weight: 700; line-height: 1.4; color: var(--text-primary); }
.gr__hero-desc { display: block; margin-top: 5px; font-size: var(--font-size-xs); line-height: 1.65; color: var(--text-secondary); }
.gr__hero-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: var(--space-3); }
.gr__hero-chips text { font-size: 10px; line-height: 22px; padding: 0 8px; border-radius: var(--radius-full); background: rgba(255,255,255,.84); color: var(--text-secondary); }
.gr__decision { margin-top: var(--space-3); }
.gr__metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); margin-top: var(--space-3); }
.gr__metric { min-width: 0; padding: var(--space-3); border: 1px solid var(--border-light); border-radius: 14px; background: var(--bg-card); box-shadow: var(--shadow-card); }
.gr__metric > text:first-child { display: block; font-size: 10px; color: var(--text-tertiary); }
.gr__metric > text:last-child { display: block; margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 9px; color: var(--text-tertiary); }
.gr__metric-value { display: block; margin-top: 4px; font-size: 20px; font-weight: 800; color: var(--text-primary); }
.gr__metric-value.is-ok { color: #15803d; }
.gr__metric-value.is-warn { color: #b45309; }
.gr__metric-status { display: block; margin-top: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; font-weight: 700; color: var(--text-primary); }
.gr__section-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin: var(--space-5) 2px var(--space-3); }
.gr__section-kicker { display: block; font-size: 9px; font-weight: 700; letter-spacing: 1px; color: var(--brand-primary); }
.gr__section-title { display: block; margin-top: 3px; font-size: var(--font-size-base); font-weight: 700; color: var(--text-primary); }
.gr__section-count { flex-shrink: 0; font-size: 10px; line-height: 22px; padding: 0 8px; border-radius: var(--radius-full); background: rgba(59,130,246,.08); color: var(--brand-primary); }
.gr__list { display: flex; flex-direction: column; gap: var(--space-2); }
.gr__item { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-3) var(--space-4); border: 1px solid var(--border-light); border-radius: 14px; background: var(--bg-card); box-shadow: var(--shadow-card); }
.gr__item.is-bad, .gr__item.is-wait { border-color: rgba(217,119,6,.16); }
.gr__item-icon { flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: 11px; background: rgba(217,119,6,.10); color: #b45309; font-size: 13px; font-weight: 800; }
.gr__item.is-ok .gr__item-icon { background: rgba(22,163,74,.10); color: #15803d; }
.gr__item-main { flex: 1; min-width: 0; }
.gr__item-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.gr__item-name { font-size: var(--font-size-base); font-weight: 600; color: var(--text-primary); }
.gr__badge { flex-shrink: 0; font-size: 9px; line-height: 20px; padding: 0 7px; border-radius: var(--radius-full); }
.gr__badge.is-ok { background: rgba(34,197,94,0.12); color: #15803d; }
.gr__badge.is-bad { background: rgba(239,68,68,0.11); color: #dc2626; }
.gr__badge.is-wait { background: rgba(234,179,8,0.13); color: #b45309; }
.gr__ev { display: block; margin-top: 5px; font-size: var(--font-size-xs); line-height: 1.65; color: var(--text-tertiary); word-break: break-word; }
.gr__empty { display: flex; flex-direction: column; align-items: center; padding: var(--space-6) var(--space-4); border: 1px solid var(--border-light); border-radius: 16px; background: var(--bg-card); text-align: center; }
.gr__empty-icon { display: flex; align-items: center; justify-content: center; width: 42px; height: 42px; border-radius: 13px; background: rgba(15,23,42,.05); color: var(--text-tertiary); }
.gr__empty-title { display: block; margin-top: var(--space-3); font-size: var(--font-size-base); font-weight: 600; color: var(--text-primary); }
.gr__empty-desc { display: block; margin-top: 4px; font-size: var(--font-size-xs); line-height: 1.65; color: var(--text-tertiary); }
.gr__trust { display: flex; align-items: flex-start; gap: var(--space-3); margin-top: var(--space-4); padding: var(--space-3) var(--space-4); border: 1px solid rgba(59,130,246,.10); border-radius: 14px; background: rgba(255,255,255,.75); }
.gr__trust-icon { flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 30px; height: 30px; border-radius: 9px; background: rgba(59,130,246,.08); color: var(--brand-primary); font-family: serif; font-weight: 700; }
.gr__trust-title { display: block; font-size: var(--font-size-sm); font-weight: 600; color: var(--text-primary); }
.gr__trust-text { display: block; margin-top: 3px; font-size: 10px; line-height: 1.65; color: var(--text-tertiary); }
</style>
