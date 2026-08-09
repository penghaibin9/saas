<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="毕业进度" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="gr__hero" :class="overallPassed ? 'is-ok' : 'is-warn'">
          <view class="gr__hero-main">
            <text class="gr__eyebrow">教务学业 · 毕业资格自查</text>
            <text class="gr__hero-title">{{ overallPassed ? '当前毕业条件已通过实时核验' : '毕业条件还有待处理事项' }}</text>
            <text class="gr__hero-desc">{{ overallPassed ? '当前共享毕业核验器未发现阻断项，最终结论仍以学校正式审核为准。' : '先看规则解释，再逐项处理未通过或待核验条件。' }}</text>
            <view class="gr__hero-chips">
              <text>{{ formalText }}</text><text>{{ passedCount }}项已通过</text><text v-if="pendingCount">{{ pendingCount }}项待处理</text>
            </view>
          </view>
          <view class="gr__hero-score">
            <text>条件通过</text><text class="gr__hero-number">{{ conditionPct }}</text><text>%</text>
          </view>
        </view>

        <MobileAcademicDecisionCard
          v-if="data.decisionTrace || data.decisionText"
          class="gr__decision"
          :trace="data.decisionTrace"
          :content="data.decisionText"
          audience="student"
        />

        <view class="gr__metrics">
          <view class="gr__metric"><text>已通过</text><text class="gr__metric-value is-ok">{{ passedCount }}</text><text>项条件</text></view>
          <view class="gr__metric"><text>待处理</text><text class="gr__metric-value" :class="pendingCount ? 'is-warn' : 'is-ok'">{{ pendingCount }}</text><text>项条件</text></view>
          <view class="gr__metric"><text>正式预审</text><text class="gr__metric-status">{{ data.hasAudit ? '已纳入' : '未纳入' }}</text><text>{{ data.hasAudit ? '与实时自查分开保存' : '当前仅实时自查' }}</text></view>
        </view>

        <view class="gr__section-head">
          <view><text class="gr__section-kicker">毕业条件清单</text><text class="gr__section-title">逐项核对真实业务事实</text></view>
          <text class="gr__section-count">{{ items.length }}项</text>
        </view>

        <view v-if="items.length" class="gr__list">
          <view v-for="it in items" :key="it.item" class="gr__item" :class="badge(it.result)">
            <view class="gr__item-icon"><text>{{ it.result === 'PASS' ? '✓' : '!' }}</text></view>
            <view class="gr__item-main">
              <view class="gr__item-head">
                <text class="gr__item-name">{{ ITEM[it.item] || it.item || '毕业条件' }}</text>
                <text class="gr__badge" :class="badge(it.result)">{{ res(it.result) }}</text>
              </view>
              <text class="gr__ev">{{ it.evidence || evidenceFallback(it) }}</text>
            </view>
          </view>
        </view>
        <view v-else class="gr__empty">
          <view class="gr__empty-icon"><text>—</text></view>
          <text class="gr__empty-title">暂时没有可展示的毕业核验项</text>
          <text class="gr__empty-desc">{{ data.note || '请稍后重新加载，或联系教务老师确认毕业预审配置。' }}</text>
        </view>

        <view class="gr__trust">
          <view class="gr__trust-icon"><text>i</text></view>
          <view class="flex-1">
            <text class="gr__trust-title">{{ data.hasAudit ? '实时自查与正式毕业结论分开保存' : '当前结果是实时自查，不等同正式毕业结论' }}</text>
            <text class="gr__trust-text">{{ data.note || '刷新页面不会创建新的正式毕业预审记录；最终毕业结论以学校正式审核形成的事实为准。' }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import MobileAcademicDecisionCard from '@/components/MobileAcademicDecisionCard.vue'
import { studentApi } from '@/services/studentApi'
const ITEM = {
  STATUS: '学籍状态', CREDIT: '总学分', COURSE_REQUIRED: '必修课程', COURSE_ELECTIVE: '选修学分', PRACTICE: '实践环节',
  INTERNSHIP: '岗位实习', GRADUATION_DESIGN: '毕业设计', DISCIPLINE: '处分情况', EMPLOYMENT: '就业填报', ARCHIVE: '档案归档'
}
const CONC = { GRADUATED: '毕业', COMPLETED: '结业', DELAYED: '延期毕业' }
export default {
  components: { MobileAcademicDecisionCard },
  data() { return { data: null, state: 'loading', ITEM } },
  computed: {
    items() { return (this.data && Array.isArray(this.data.items)) ? this.data.items : [] },
    passedCount() { return this.items.filter((item) => String(item.result || '').toUpperCase() === 'PASS').length },
    pendingCount() { return this.items.length - this.passedCount },
    overallPassed() { return String((this.data && this.data.overall) || '').toUpperCase() === 'SYSTEM_PASSED' },
    conditionPct() { return this.items.length ? Math.round(this.passedCount / this.items.length * 100) : 0 },
    formalText() {
      if (!this.data || !this.data.hasAudit) return '尚未纳入正式预审'
      if (this.data.conclusion) return `正式结论：${this.concText(this.data.conclusion)}`
      return '已纳入正式预审'
    }
  },
  onLoad() { this.load() },
  methods: {
    res(r) { return r === 'PASS' ? '已通过' : r === 'FAIL' ? '未达标' : '待核验' },
    concText(c) { return CONC[c] || c },
    badge(r) { return r === 'PASS' ? 'is-ok' : r === 'FAIL' ? 'is-bad' : 'is-wait' },
    evidenceFallback(it) {
      return it.result === 'PASS' ? '学校业务系统已记录满足该项条件的有效事实。' : '当前正式数据还不足以确认该项通过，请按上方建议处理后重新核验。'
    },
    load() {
      this.state = 'loading'
      studentApi.getMyGraduation().then((d) => { this.data = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.gr__hero { display: flex; align-items: stretch; justify-content: space-between; gap: var(--space-3); padding: var(--space-4); border: 1px solid rgba(217,119,6,.20); border-radius: 18px; background: linear-gradient(135deg, rgba(255,255,255,.98), rgba(255,247,237,.94)); box-shadow: var(--shadow-card); }
.gr__hero.is-ok { border-color: rgba(22,163,74,.18); background: linear-gradient(135deg, rgba(255,255,255,.98), rgba(240,253,244,.94)); }
.gr__hero-main { flex: 1; min-width: 0; }
.gr__eyebrow { display: block; font-size: 10px; font-weight: 700; letter-spacing: 1px; color: #b45309; }
.gr__hero.is-ok .gr__eyebrow { color: #15803d; }
.gr__hero-title { display: block; margin-top: 5px; font-size: 18px; font-weight: 700; line-height: 1.4; color: var(--text-primary); }
.gr__hero-desc { display: block; margin-top: 5px; font-size: var(--font-size-xs); line-height: 1.65; color: var(--text-secondary); }
.gr__hero-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: var(--space-3); }
.gr__hero-chips text { font-size: 10px; line-height: 22px; padding: 0 8px; border-radius: var(--radius-full); background: rgba(255,255,255,.84); color: var(--text-secondary); }
.gr__hero-score { flex-shrink: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 78px; border-left: 1px solid rgba(217,119,6,.12); color: var(--text-tertiary); font-size: 10px; }
.gr__hero.is-ok .gr__hero-score { border-left-color: rgba(22,163,74,.12); }
.gr__hero-number { margin: 4px 0 2px; font-size: 28px; line-height: 1; font-weight: 800; color: #b45309; }
.gr__hero.is-ok .gr__hero-number { color: #15803d; }
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
