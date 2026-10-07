<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="清考结果" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card"><text class="mk__sub">{{ d.note }}</text><text class="mk__sub">{{ clearanceCoverageText }}</text></view>
        <AcademicPageState v-if="!d.items.length" state="empty" title="暂无清考结果" :description="d.note" />
        <view v-for="it in d.items" :key="it.recordId" class="list-row">
          <view class="flex-1">
            <text class="t-md">{{ it.courseName }}</text>
            <text class="mk__sub">{{ it.batchName || '清考批次' }} · 原分 {{ it.originScore ?? '—' }} · 清考正式成绩 {{ publishedScore(it) }}</text>
          </view>
          <MobileStatusTag :status="it.status" :label="resultLabel(it)" />
        </view>
        <view v-if="d.total > 0 || page > 1" class="cl__pager">
          <button class="btn cl__pager-button" :disabled="page <= 1 || isPaging" @click="previousPage">上一页</button>
          <text>第 {{ page }} / {{ pageCount }} 页，共 {{ d.total }} 条</text>
          <button class="btn cl__pager-button" :disabled="!d.hasMore || isPaging" @click="nextPage">下一页</button>
        </view>
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
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

const CLEARANCE_PAGE_SIZE = 20

function normalizeClearancePage(result, requestedPage) {
  const items = result?.items
  const page = result?.page
  const pageSize = result?.pageSize
  const total = result?.total
  const hasMore = result?.hasMore
  if (!Array.isArray(items) || !Number.isSafeInteger(page) || page !== requestedPage || page < 1
    || pageSize !== CLEARANCE_PAGE_SIZE || !Number.isSafeInteger(total) || total < 0
    || typeof hasMore !== 'boolean' || items.length > pageSize
    || (items.length > 0 && total < ((page - 1) * pageSize) + items.length)
    || hasMore !== page * pageSize < total) {
    throw new Error('清考结果分页信息无法核对')
  }
  return { ...result, items, page, pageSize, total, hasMore }
}

export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicReadPage],
  data() { return { d: null, state: 'loading', page: 1, clearReadDataOnForbidden: true } },
  computed: {
    clearanceCoverageText() {
      const returned = (this.d && this.d.items || []).length
      const total = Number(this.d && this.d.total)
      const pageCount = this.pageCount
      return Number.isFinite(total) && total >= 0
        ? `第 ${this.page}/${pageCount} 页，本页 ${returned} 条，共 ${total} 条清考记录。`
        : `本页返回 ${returned} 条清考记录。`
    },
    pageCount() { return this.d?.total ? Math.ceil(this.d.total / this.d.pageSize) : 1 },
    isPaging() { return this.state === 'loading' }
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
    resetAcademicContext() { this.page = 1 },
    previousPage() { return this.page > 1 ? this.load(this.page - 1) : Promise.resolve(null) },
    nextPage() { return this.d?.hasMore ? this.load(this.page + 1) : Promise.resolve(null) },
    load(requested = this.page) {
      const requestedPage = this.readIdentity !== currentSessionGeneration() ? 1 : Number(requested)
      if (!Number.isSafeInteger(requestedPage) || requestedPage < 1) return Promise.resolve(null)
      return this.readAcademic(() => studentApi.getMyClearance({ page: requestedPage, pageSize: CLEARANCE_PAGE_SIZE }), (result) => {
        const data = normalizeClearancePage(result, requestedPage)
        this.d = data
        this.page = data.page
      })
    }
  }
}
</script>
<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.mk__sub { display:block; color: var(--t3); font-size: 12px; margin-top: 4px; }
.cl__pager { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); margin: var(--space-4) 0; color: var(--text-secondary); font-size: var(--font-size-sm); }
.cl__pager-button { flex: 1; margin: 0; }
</style>
