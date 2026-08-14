<template>
  <view class="page-wrap selection-page">
    <MobileNavBar variant="brand" title="实习选岗" show-back />

    <view class="page-pad">
      <view v-if="context" class="context-card">
        <view class="context-head">
          <view>
            <text class="context-eyebrow">当前招聘季</text>
            <text class="context-title">{{ context.campaignName }}</text>
          </view>
          <MobileStatusTag :status="context.canSelect ? 'OPEN' : 'CLOSED'" :label="context.phaseLabel" />
        </view>
        <text class="context-deadline">学生选岗截止：{{ deadlineText }}</text>
        <view class="context-metrics">
          <view><text>{{ context.publishedPositions }}</text><text>已发布岗位</text></view>
          <view><text>{{ context.partnerCompanies }}</text><text>合作企业</text></view>
          <view><text>{{ context.matchedPositions }}</text><text>匹配岗位</text></view>
          <view><text>{{ context.selectedVolunteers }}/3</text><text>已选志愿</text></view>
        </view>
      </view>

      <MobileInlineAlert
        v-if="context && !context.canSelect"
        type="warning"
        title="当前阶段暂不可调整志愿"
        :description="context.blockReason || '请关注学校公布的招聘季阶段与截止时间。'"
      />

      <view class="search-card">
        <view class="search-box">
          <text class="search-icon">⌕</text>
          <input
            class="search-input"
            :value="query.keyword"
            type="text"
            confirm-type="search"
            placeholder="搜索岗位、企业、地点"
            @input="onKeywordInput"
            @confirm="flushSearch"
          />
          <text v-if="query.keyword" class="clear" @click="clearKeyword">×</text>
        </view>
        <view class="quick-row">
          <input class="quick-input" :value="query.city" placeholder="城市" @input="onCityInput" @confirm="flushSearch" />
          <picker :range="sortLabels" :value="sortIndex" @change="onSortChange">
            <view class="sort-picker">{{ sortLabels[sortIndex] }}⌄</view>
          </picker>
        </view>
        <view class="filter-row">
          <view class="filter-chip" :class="{ 'is-on': query.majorMatched === true }" @click="toggleFilter('majorMatched')">专业匹配</view>
          <view class="filter-chip" :class="{ 'is-on': query.accommodation === true }" @click="toggleFilter('accommodation')">住宿</view>
          <view class="filter-chip" :class="{ 'is-on': query.meal === true }" @click="toggleFilter('meal')">餐食</view>
        </view>
      </view>

      <MobileGlobalState :state="listState" @retry="loadPositions">
        <view class="list-summary">
          <text>学校认可岗位</text>
          <text>共 {{ total }} 个 · 每页 20 条</text>
        </view>

        <MobileGlobalState v-if="!positions.length" state="empty" title="暂无匹配岗位" description="调整搜索或筛选条件后再试。" />
        <view v-else class="position-stack">
          <view v-for="p in positions" :key="p.id" class="position-card" @click="rememberPosition(p)">
            <view class="position-top">
              <text class="position-title">{{ p.title }}</text>
              <text class="position-salary">{{ p.remuneration }}</text>
            </view>
            <text class="position-company">{{ p.companyName }}</text>
            <view class="position-meta">
              <text>{{ p.workLocation }}</text>
              <text>剩余 {{ p.remaining }} 个</text>
            </view>
            <view class="tag-row">
              <text v-for="tag in p.tags" :key="tag" class="job-tag">{{ tag }}</text>
            </view>
          </view>
        </view>

        <view v-if="totalPages > 1" class="pager">
          <button class="pager-btn" size="mini" :disabled="query.page <= 1 || listState === 'loading'" @click="changePage(query.page - 1)">上一页</button>
          <text>第 {{ query.page }}/{{ totalPages }} 页</text>
          <button class="pager-btn" size="mini" :disabled="query.page >= totalPages || listState === 'loading'" @click="changePage(query.page + 1)">下一页</button>
        </view>
      </MobileGlobalState>
    </view>

    <MobileSafeAreaBar />
  </view>
</template>

<script>
import { internshipSelectionApi, normalizeMobileCatalogQuery } from '@/services/internshipSelectionApi'
import {
  formatMobileDeadline,
  normalizeMobilePage,
  normalizeMobileSelectionContext
} from '@/modules/internshipSelectionModel'

const SORTS = ['RECOMMENDED', 'LATEST', 'REMUNERATION', 'REMAINING']
const SORT_LABELS = ['推荐', '最新', '薪资', '剩余名额']

export default {
  data() {
    return {
      context: null,
      listState: 'loading',
      positions: [],
      total: 0,
      query: normalizeMobileCatalogQuery({ page: 1, pageSize: 20 }),
      sortLabels: SORT_LABELS,
      searchTimer: null,
      requestSeq: 0
    }
  },
  computed: {
    deadlineText() {
      return formatMobileDeadline(this.context && this.context.selectionDeadline)
    },
    totalPages() {
      return Math.max(1, Math.ceil(this.total / 20))
    },
    sortIndex() {
      const index = SORTS.indexOf(this.query.sort)
      return index >= 0 ? index : 0
    }
  },
  onLoad() {
    this.loadContext()
    this.loadPositions()
  },
  onUnload() {
    clearTimeout(this.searchTimer)
    this.requestSeq += 1
  },
  methods: {
    loadContext() {
      internshipSelectionApi.context().then((data) => {
        this.context = normalizeMobileSelectionContext(data || {})
      }).catch(() => {
        this.context = null
      })
    },
    loadPositions(nextQuery) {
      const query = normalizeMobileCatalogQuery(nextQuery || this.query)
      this.query = query
      const requestId = ++this.requestSeq
      this.listState = 'loading'
      internshipSelectionApi.positions(query).then((data) => {
        if (requestId !== this.requestSeq) return
        const page = normalizeMobilePage(data || {})
        this.positions = page.items
        this.total = page.total
        this.listState = 'ready'
      }).catch(() => {
        if (requestId !== this.requestSeq) return
        this.positions = []
        this.total = 0
        this.listState = 'error'
      })
    },
    scheduleSearch() {
      clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(() => this.loadPositions({ ...this.query, page: 1 }), 350)
    },
    onKeywordInput(e) {
      this.query = { ...this.query, keyword: e.detail.value }
      this.scheduleSearch()
    },
    onCityInput(e) {
      this.query = { ...this.query, city: e.detail.value }
      this.scheduleSearch()
    },
    flushSearch() {
      clearTimeout(this.searchTimer)
      this.loadPositions({ ...this.query, page: 1 })
    },
    clearKeyword() {
      this.query = { ...this.query, keyword: '' }
      this.flushSearch()
    },
    onSortChange(e) {
      const index = Number(e.detail.value || 0)
      this.loadPositions({ ...this.query, page: 1, sort: SORTS[index] || 'RECOMMENDED' })
    },
    toggleFilter(key) {
      const next = this.query[key] === true ? '' : true
      this.loadPositions({ ...this.query, page: 1, [key]: next })
    },
    changePage(page) {
      this.loadPositions({ ...this.query, page })
    },
    rememberPosition(position) {
      try { uni.setStorageSync('gx_internship_selection_position_v1', position) } catch (e) { /* no-op */ }
      // A03-10 接入正式岗位详情页；A03-9 旧 enterprises 路由继续稳定承载列表。
    }
  }
}
</script>

<style scoped>
.selection-page { background: var(--bg-page); min-height: 100vh; }
.context-card { margin-bottom: var(--space-3); padding: var(--card-padding-mobile); border-radius: var(--radius-lg); background: var(--bg-card); box-shadow: var(--shadow-card); }
.context-head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.context-eyebrow { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.context-title { display: block; margin-top: 2px; color: var(--text-primary); font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); }
.context-deadline { display: block; margin-top: var(--space-2); color: var(--text-secondary); font-size: var(--font-size-xs); }
.context-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-top: var(--space-3); }
.context-metrics view { min-width: 0; padding: 8px 4px; border-radius: var(--radius-md); background: var(--gray-50); text-align: center; }
.context-metrics text:first-child { display: block; color: var(--text-primary); font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); }
.context-metrics text:last-child { display: block; margin-top: 2px; color: var(--text-tertiary); font-size: 10px; white-space: nowrap; }
.search-card { margin: var(--space-3) 0; padding: var(--space-3); border-radius: var(--radius-lg); background: var(--bg-card); }
.search-box { display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 12px; border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--gray-50); }
.search-icon { color: var(--text-tertiary); }
.search-input { flex: 1; min-width: 0; font-size: var(--font-size-sm); }
.clear { padding: 4px; color: var(--text-tertiary); font-size: 18px; }
.quick-row { display: grid; grid-template-columns: 1fr 108px; gap: 8px; margin-top: 8px; }
.quick-input,.sort-picker { box-sizing: border-box; height: 36px; padding: 0 10px; border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 36px; }
.filter-row { display: flex; gap: 8px; margin-top: 8px; overflow-x: auto; }
.filter-chip { flex-shrink: 0; padding: 6px 10px; border-radius: 4px; background: #f0f5ff; color: #34527a; font-size: var(--font-size-xs); }
.filter-chip.is-on { background: var(--brand-primary); color: #fff; }
.list-summary { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: var(--space-2); color: var(--text-secondary); font-size: var(--font-size-xs); }
.list-summary text:first-child { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.position-stack { display: flex; flex-direction: column; gap: var(--space-3); }
.position-card { padding: var(--card-padding-mobile); border: 1px solid #eef0f3; border-radius: 10px; background: #fff; }
.position-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.position-title { flex: 1; color: #1a1a1a; font-size: 18px; font-weight: var(--font-weight-semibold); line-height: 1.35; }
.position-salary { flex-shrink: 0; color: #fa541c; font-size: 16px; font-weight: var(--font-weight-semibold); }
.position-company { display: block; margin-top: 6px; color: var(--text-secondary); font-size: var(--font-size-sm); }
.position-meta { display: flex; justify-content: space-between; gap: 8px; margin-top: 5px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.tag-row { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 9px; }
.job-tag { padding: 3px 7px; border-radius: 4px; background: #f0f5ff; color: #34527a; font-size: 12px; }
.pager { display: flex; align-items: center; justify-content: center; gap: 10px; margin-top: var(--space-4); color: var(--text-tertiary); font-size: var(--font-size-xs); }
.pager-btn { min-width: 74px; }
</style>
