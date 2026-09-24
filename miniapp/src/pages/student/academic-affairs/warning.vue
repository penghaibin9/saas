<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="学业预警" show-back />
    <AcademicPageState :state="state" @retry="retry">
      <view class="page-pad" v-if="d">
        <AcademicPageState v-if="!d.items.length" state="empty" :title="page > 1 || d.total > 0 ? '本页暂无预警记录' : '暂无学业预警'" :description="page > 1 ? '记录可能已更新，请返回上一页核对。' : '请以学校正式预警记录为准。'" />
        <view class="list-group" v-else>
          <view v-for="w in d.items" :key="w.warningId" class="list-row wn__row" :class="{ 'is-target': String(w.warningId) === targetId }">
            <view class="wn__level" :class="'is-' + (w.level || 'low').toLowerCase()">{{ levelText(w.level) }}</view>
            <view class="flex-1">
              <text class="t-md t-bold">{{ typeText(w.warnType) }}</text>
              <text class="wn__reason">{{ w.reason || '—' }}</text>
            </view>
            <MobileStatusTag :status="w.status" :label="{ CLOSED: '已关闭', ESCALATED: '已升级跟进', VOID: '已作废' }[w.status] || ''" />
          </view>
        </view>
        <text v-if="targetNotice" class="wn__notice">{{ targetNotice }}</text>
        <view v-if="d.total > 0 || page > 1" class="wn__pager">
          <button class="btn wn__pager-button" :disabled="!hasPrevious || isPaging" @click="previousPage">上一页</button>
          <text class="wn__pager-text">第 {{ page }} / {{ pageCount }} 页</text>
          <button class="btn wn__pager-button" :disabled="!hasNext || isPaging" @click="nextPage">下一页</button>
        </view>
        <text class="wn__coverage">{{ warningCoverageText }}</text>
        <view v-if="d.items.length" class="wn__actions">
          <button class="btn" @click="go('/pages/student/academic-affairs/transcript')">查看原成绩</button>
          <button class="btn btn-primary" @click="go('/pages/student/academic-affairs/makeup')">打开补考重修</button>
        </view>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { academicReadPage } from './read-page'
import { go } from '@/utils/nav'

const WARNING_PAGE_SIZE = 20
const LEVEL_TEXT = { HIGH: '高', MEDIUM: '中', LOW: '低' }
const TYPE_TEXT = { MULTI_FAIL: '多科挂科预警' }

function normalizeWarningPage(result, requestedPage) {
  const items = result?.items
  const page = result?.page
  const pageSize = result?.pageSize
  const total = result?.total
  const hasMore = result?.hasMore
  if (!Array.isArray(items) || !Number.isSafeInteger(page) || page !== requestedPage || page < 1 || pageSize !== WARNING_PAGE_SIZE || !Number.isSafeInteger(total) || total < 0 || typeof hasMore !== 'boolean' || items.length > pageSize || (items.length > 0 && total < ((page - 1) * pageSize) + items.length)) {
    throw new Error('预警分页信息无法核对')
  }
  if (hasMore !== page * pageSize < total) throw new Error('预警分页状态无法核对')
  return { items, page, pageSize, total, hasMore }
}

export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicReadPage],
  data() { return { d: null, state: 'loading', page: 1, targetId: '', targetNotice: '', clearReadDataOnForbidden: true } },
  computed: {
    pageCount() { return this.d?.total ? Math.ceil(this.d.total / this.d.pageSize) : 1 },
    hasPrevious() { return this.page > 1 },
    hasNext() { return this.d?.hasMore === true },
    isPaging() { return this.state === 'loading' },
    warningCoverageText() {
      if (!this.d) return ''
      return this.d.total
        ? `第 ${this.page} / ${this.pageCount} 页，本页 ${this.d.items.length} 条，共 ${this.d.total} 条学业预警。`
        : '当前没有学业预警。'
    }
  },
  onLoad(options = {}) { this.targetId = String(options.id || '').trim(); this.page = 1; this.load(1) },
  methods: {
    go,
    resetAcademicContext() { this.page = 1; this.targetId = ''; this.targetNotice = '' },
    clearForbiddenWarning() { this.d = null; this.page = 1; this.targetId = ''; this.targetNotice = '' },
    levelText(l) { return LEVEL_TEXT[l] || '提示' },
    typeText(t) { return TYPE_TEXT[t] || '学业预警' },
    retry() { return this.load(this.page) },
    previousPage() { return this.hasPrevious ? this.load(this.page - 1) : Promise.resolve(null) },
    nextPage() { return this.hasNext ? this.load(this.page + 1) : Promise.resolve(null) },
    load(requested = this.page) {
      // 切换身份时永远回到第一页；旧身份的页码、深链与请求结果不能带入新身份。
      const requestedPage = this.readIdentity !== currentSessionGeneration() ? 1 : Number(requested)
      if (!Number.isSafeInteger(requestedPage) || requestedPage < 1) return Promise.resolve(null)
      this.targetNotice = ''
      return this.readAcademic(
        () => studentApi.getMyWarnings({ page: requestedPage, pageSize: WARNING_PAGE_SIZE }),
        (result) => {
          const data = normalizeWarningPage(result, requestedPage)
          this.d = data
          this.page = data.page
          if (this.targetId && !data.items.some(row => String(row.warningId) === this.targetId)) {
            this.targetNotice = '未在当前页定位到该预警。请使用上一页或下一页继续查看。'
          }
        }
      ).then((result) => {
        if (!result && this.state === 'forbidden') this.clearForbiddenWarning()
        return result
      })
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.wn__actions { display: flex; gap: 8px; margin-top: 16px; }
.wn__row { align-items: flex-start; }
.wn__row.is-target { border: 1px solid var(--brand-primary); box-shadow: 0 0 0 2px var(--brand-50); }
.wn__level { flex-shrink: 0; width: 44px; height: 44px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xs); font-weight: 700; color: #fff; margin-right: var(--space-3); }
.wn__level.is-low { background: #eab308; }
.wn__level.is-medium { background: #f97316; }
.wn__level.is-high { background: var(--danger-600); }
.wn__reason { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.wn__notice { display: block; margin-top: var(--space-3); color: var(--warning-700, #a16207); font-size: var(--font-size-sm); }
.wn__pager { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); margin-top: var(--space-4); }
.wn__pager-button { flex: 1; margin: 0; }
.wn__pager-text { flex-shrink: 0; color: var(--text-secondary); font-size: var(--font-size-sm); }
.wn__coverage { display: block; margin-top: var(--space-3); color: var(--text-tertiary); font-size: var(--font-size-xs); }
</style>
