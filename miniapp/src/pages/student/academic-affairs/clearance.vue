<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="清考结果" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card"><text class="mk__sub">{{ d.note }}</text><text class="mk__sub">{{ clearanceCoverageText }}</text></view>
        <AcademicPageState v-if="!d.items.length" state="empty" title="暂无清考结果" :description="d.note" />
        <view v-for="it in d.items.slice(0, listLimit)" :key="it.recordId" class="list-row">
          <view class="flex-1">
            <text class="t-md">{{ it.courseName }}</text>
            <text class="mk__sub">{{ it.batchName || '清考批次' }} · 原分 {{ it.originScore ?? '—' }} · 清考正式成绩 {{ publishedScore(it) }}</text>
          </view>
          <MobileStatusTag :status="it.status" :label="resultLabel(it)" />
        </view>
        <button v-if="d.items.length > listLimit" class="btn" @click="listLimit += 20">查看更多结果</button>
        <text class="mk__sub">清考是课程补救考核，正式成绩以学校发布结果为准。</text>
        <button class="btn btn-primary" @click="go('/pages/student/academic-affairs/transcript')">查看正式成绩</button>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>
<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { academicReadPage } from './read-page'
import { go } from '@/utils/nav'
export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicReadPage],
  data() { return { d: null, state: 'loading', clearReadDataOnForbidden: true } },
  computed: {
    clearanceCoverageText() {
      const returned = (this.d && this.d.items || []).length
      const total = Number(this.d && this.d.total)
      return Number.isFinite(total) && total > returned
        ? `当前返回 ${returned}/${total} 条清考记录；当前接口未提供翻页。`
        : `当前返回 ${returned} 条清考记录。`
    }
  },
  onLoad() { this.load() },
  methods: {
    go,
    hasPublishedScore(row) {
      return String(row && row.status || '').toUpperCase() === 'FINISHED'
        && (typeof row.score === 'number' || (typeof row.score === 'string' && row.score.trim() !== ''))
        && Number.isFinite(Number(row.score))
    },
    publishedScore(row) { return this.hasPublishedScore(row) ? row.score : '待公布或核对' },
    resultLabel(row) { if (row.status === 'FINISHED') return this.hasPublishedScore(row) ? '已公布成绩' : '已结束，成绩待核对'; return ({ SCORED: '待公布成绩', PENDING_EXAM: '待考试', DEFERRED: '已缓考' })[row.status] || '结果待核对' },
    load() {
      return this.readAcademic(() => studentApi.getMyClearance(), (d) => {
        if (!Array.isArray(d.items)) throw new Error('清考信息无法核对')
        this.d = d
      })
    }
  }
}
</script>
<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.mk__sub { display:block; color: var(--t3); font-size: 12px; margin-top: 4px; }
</style>
