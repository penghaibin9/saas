<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="我的成绩" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="tr__sum">
          <view class="tr__stat"><text class="tr__num">{{ data.earnedCredits ?? '—' }}</text><text class="tr__lbl">已获学分</text></view>
          <view class="tr__stat"><text class="tr__num">{{ data.items.length }}</text><text class="tr__lbl">课程数</text></view>
          <view class="tr__stat"><text class="tr__num" :class="{ 'is-bad': data.failCount }">{{ data.failCount || 0 }}</text><text class="tr__lbl">挂科</text></view>
        </view>
        <picker :range="termLabels" :value="termIndex" @change="termIndex = Number($event.detail.value); listLimit = 20"><view class="tr__filter">{{ termLabels[termIndex] }}</view></picker>
        <text class="tr__tip">仅展示正式成绩。免修、缓考、缺考不按零分显示。</text>
        <text class="tr__tip">{{ gradeCoverageText }}</text>
        <view class="tr__empty" v-if="!visibleGrades.length"><text>当前学期暂无正式成绩</text></view>
        <view class="stack">
          <view v-for="(g, i) in visibleGrades.slice(0, listLimit)" :key="g.gradeId || i" class="tr__row">
            <view class="tr__main">
              <text class="tr__course">{{ g.courseName }}</text>
              <text class="tr__term">{{ g.term }} · {{ g.credit }}学分</text>
              <button v-if="g.gradeId" class="tr__detail" @click="go('/pages/student/academic-affairs/recheck?id=' + encodeURIComponent(g.gradeId))">查看与复查</button>
            </view>
            <text class="tr__score" :class="['FAIL','FAILED'].includes(g.passStatus) ? 'is-bad' : g.passStatus === 'PASSED' ? 'is-ok' : ''">{{ scoreText(g) }}</text>
          </view>
        </view>
        <button v-if="visibleGrades.length > listLimit" class="btn" @click="listLimit += 20">查看更多成绩</button>
        <button class="tr__print" :disabled="printing" @click="printDoc">{{ printing ? '申请中…' : '复制成绩摘要（登记用途）' }}</button>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { safeToast } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { academicReadPage } from './read-page'
import { go } from '@/utils/nav'
export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicReadPage],
  data() { return { data: null, state: 'loading', printing: false, termIndex: 0, clearReadDataOnForbidden: true } },
  onLoad() { this.load() },
  computed: {
    termLabels() { return ['全部已发布学期', ...new Set(((this.data && this.data.items) || []).map(g => g.term).filter(Boolean))] },
    visibleGrades() { return ((this.data && this.data.items) || []).filter(g => !this.termIndex || g.term === this.termLabels[this.termIndex]) },
    gradeCoverageText() {
      const returned = (this.data && this.data.items || []).length
      const total = Number(this.data && this.data.total)
      if (!Number.isFinite(total) || total < 0) return `当前返回 ${returned} 条已发布成绩；学校暂未提供总条数。`
      return total > returned ? `当前返回 ${returned}/${total} 条已发布成绩；当前接口未提供翻页。` : `当前返回 ${returned} 条已发布成绩。`
    }
  },
  methods: {
    go,
    resetAcademicContext() { this.termIndex = 0; this.printing = false },
    scoreText(g) { return { EXEMPT: '免修', EXEMPTED: '免修', DEFERRED: '缓考', ABSENT: '缺考' }[g.passStatus] || (g.score == null ? '待核对' : g.score) },
    load() {
      return this.readAcademic(() => studentApi.getMyTranscript(), (d) => {
        if (!Array.isArray(d.items)) throw new Error('成绩信息无法核对')
        this.data = d
        if (this.termIndex >= this.termLabels.length) this.termIndex = 0
      })
    },
    printDoc() {
      if (this.printing || !this.data || this.state !== 'ready') return
      const identity = currentSessionGeneration()
      const epoch = this.readEpoch
      const current = () => identity === currentSessionGeneration() && epoch === this.readEpoch && !this.readHidden
      const snapshot = this.data
      this.printing = true
      studentApi.printMyTranscript('个人成绩单').then((res) => {
        if (!current()) return
        if (!res || !res.loggedAt) throw new Error('成绩摘要登记结果待核实')
        const lines = (snapshot.items || []).map((g) => `${g.courseName} ${this.scoreText(g)}`).join('\n')
        const text = `成绩摘要\n水印：${res.watermark || ''}\n用途登记时间：${res.loggedAt}\n已获学分：${snapshot.earnedCredits ?? '—'}\n\n${lines || '暂无成绩'}`
        uni.setClipboardData({
          data: text,
          success: () => { if (current()) safeToast('已复制成绩摘要', 'success') },
          fail: () => { if (current()) safeToast('用途已登记，复制未完成') }
        })
      }).catch(() => { if (current()) safeToast('成绩摘要暂未完成，请稍后核对') }).finally(() => { if (identity === currentSessionGeneration()) this.printing = false })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.tr__filter { background: var(--bg-card); border: 1px solid var(--border-base); border-radius: 10px; padding: 12px; font-size: 14px; }
.tr__tip { display: block; color: var(--text-tertiary); font-size: 12px; margin: 12px 0; }
.tr__detail { margin: 4px 0 0; padding: 0; min-height: 40px; font-size: 12px; color: var(--brand-primary); text-align: left; background: transparent; }
.tr__detail::after { border: 0; }
.tr__sum { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }
.tr__stat { flex: 1; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3) 0; text-align: center; box-shadow: var(--shadow-card); }
.tr__num { display: block; font-size: 22px; font-weight: 700; color: var(--brand-primary); }
.tr__num.is-bad { color: #dc2626; }
.tr__lbl { font-size: var(--font-size-sm); color: var(--text-secondary); }
.tr__print { margin-bottom: var(--space-3); background: var(--brand-primary); color: #fff; border-radius: var(--radius-full); font-size: var(--font-size-sm); }
.tr__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.tr__row { display: flex; justify-content: space-between; align-items: center; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-2); box-shadow: var(--shadow-card); }
.tr__course { display: block; font-weight: 600; }
.tr__term { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 2px; }
.tr__score { font-size: 20px; font-weight: 700; }
.tr__score.is-ok { color: #16a34a; }
.tr__score.is-bad { color: #dc2626; }
</style>
