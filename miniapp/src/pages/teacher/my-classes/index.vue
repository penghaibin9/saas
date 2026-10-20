<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="我的班级" subtitle="本人担任辅导员/班主任的行政班" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <view class="mc__search">
          <input v-model="keywordInput" class="mc__search-input" maxlength="100" confirm-type="search" placeholder="按班级名称或年级搜索" @confirm="applySearch" />
          <button class="btn mc__search-button" size="mini" @click="applySearch">搜索</button>
        </view>
        <text class="mc__meta">共 {{ d.total }} 个本人可见班级<text v-if="keyword">，已筛选“{{ keyword }}”</text></text>
        <MobileGlobalState v-if="!d.items.length" state="empty" :title="d.note || '暂无负责班级'" description="如信息有误请联系系统管理员核实班级归属。" />
        <view class="list-group" v-else>
          <view v-for="c in d.items" :key="c.classId" class="list-row" @click="openClass(c)">
            <view class="flex-1">
              <text class="t-md">{{ c.className }}</text>
              <text class="mc__sub">{{ c.grade || '—' }}级 · 在校 {{ c.studentCount }} 人</text>
            </view>
            <MobileStatusTag :label="statusLabel(c.status)" :type="c.status === 'ACTIVE' ? 'success' : 'default'" />
          </view>
        </view>
        <view v-if="d.total > 0 || page > 1" class="mc__pager">
          <button class="btn mc__pager-button" :disabled="page <= 1 || isPaging" @click="previousPage">上一页</button>
          <text>第 {{ page }} / {{ pageCount }} 页</text>
          <button class="btn mc__pager-button" :disabled="!d.hasMore || isPaging" @click="nextPage">下一页</button>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { normalizeError } from '@/services/request'
import { teacherApi } from '@/services/teacherApi'
import { go } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

const CLASS_PAGE_SIZE = 20

function normalizeClassPage(result, requestedPage) {
  const items = result?.items
  const page = result?.page
  const pageSize = result?.pageSize
  const total = result?.total
  const hasMore = result?.hasMore
  if (!Array.isArray(items) || !Number.isSafeInteger(page) || page !== requestedPage || page < 1
    || pageSize !== CLASS_PAGE_SIZE || !Number.isSafeInteger(total) || total < 0
    || typeof hasMore !== 'boolean' || items.length > pageSize
    || (items.length > 0 && total < ((page - 1) * pageSize) + items.length)
    || hasMore !== page * pageSize < total) {
    throw new Error('班级分页信息无法核对')
  }
  return { ...result, items, page, pageSize, total, hasMore }
}

export default {
  data() { return { d: null, state: 'loading', page: 1, keyword: '', keywordInput: '', _loadEpoch: 0, _pageActive: true, identity: currentSessionGeneration() } },
  onLoad() { this._pageActive = true; this.load() },
  onShow() {
    if (this.identity !== currentSessionGeneration()) {
      this.identity = currentSessionGeneration(); this.page = 1; this.keyword = ''; this.keywordInput = ''; this.load(1)
    }
  },
  onUnload() { this._pageActive = false; this._loadEpoch += 1 },
  computed: {
    pageCount() { return this.d?.total ? Math.ceil(this.d.total / this.d.pageSize) : 1 },
    isPaging() { return this.state === 'loading' }
  },
  methods: {
    statusLabel(status) { return ({ ACTIVE: '在读', INACTIVE: '已停用', ARCHIVED: '已归档' })[String(status || '').toUpperCase()] || '状态待学校核对' },
    previousPage() { return this.page > 1 ? this.load(this.page - 1) : Promise.resolve(null) },
    nextPage() { return this.d?.hasMore ? this.load(this.page + 1) : Promise.resolve(null) },
    applySearch() {
      const keyword = String(this.keywordInput || '').trim()
      if (keyword === this.keyword && this.state === 'ready') return
      this.keyword = keyword
      this.load(1)
    },
    load(requested = this.page) {
      const requestedPage = Number(requested)
      if (!Number.isSafeInteger(requestedPage) || requestedPage < 1) return Promise.resolve(null)
      const identity = currentSessionGeneration()
      const epoch = this._loadEpoch + 1
      this._loadEpoch = epoch
      this.state = 'loading'
      return teacherApi.getMyClasses({ page: requestedPage, pageSize: CLASS_PAGE_SIZE, keyword: this.keyword || undefined }).then((result) => {
        if (!this._pageActive || this._loadEpoch !== epoch || identity !== currentSessionGeneration()) return
        const data = normalizeClassPage(result, requestedPage)
        this.d = data; this.page = data.page; this.identity = identity; this.state = 'ready'
      }).catch((error) => {
        if (!this._pageActive || this._loadEpoch !== epoch || identity !== currentSessionGeneration()) return
        this.state = normalizeError(error).pageState || 'error'
      })
    },
    openClass(c) { go(`/pages/teacher/my-students/index?classId=${c.classId}&className=${encodeURIComponent(c.className)}`) }
  }
}
</script>

<style scoped>
.mc__search { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.mc__search-input { flex: 1; min-width: 0; height: 38px; padding: 0 12px; border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-card); font-size: var(--font-size-sm); }
.mc__search-button { flex-shrink: 0; margin: 0; }
.mc__meta { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); margin-bottom: 12px; }
.mc__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.mc__pager { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 16px 0; color: var(--text-secondary); font-size: var(--font-size-sm); }
.mc__pager-button { flex: 1; margin: 0; }
</style>
