<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的办理" back />
    <view class="mw__seg">
      <MobileSegmented :items="tabs" :model-value="tab" @update:modelValue="switchTab" />
    </view>
    <MobileGlobalState :state="state" @retry="refresh">
      <view class="page-pad stack">
        <MobileGlobalState v-if="!items.length" state="empty" title="这里还没有办理记录"
          description="提交请假、资助或校园服务申请后，进度和结果都会显示在这里。" />
        <template v-else>
          <view v-for="row in items" :key="row.caseId" class="card stack-sm mw__card"
            :class="{ 'is-focus': isFocused(row) }" :id="'case-' + row.caseId" @click="openDetail(row)">
            <view class="row-between">
              <text class="mw__title ellipsis flex-1">{{ row.title }}</text>
              <MobileStatusTag :label="row.statusLabel" :type="tagType(row.statusGroup)" />
            </view>
            <view class="mw__meta">
              <text class="mw__meta-item">{{ row.dept }}</text>
              <text class="mw__meta-item">当前：{{ row.handler }}</text>
              <text class="mw__meta-item">{{ shortTime(row.updatedAt) }}</text>
            </view>
            <MobileInlineAlert v-if="row.latestOpinion" type="warning" title="需要你处理"
              :description="row.latestOpinion" />
            <view class="mw__foot" v-if="canRun(row.action)">
              <button class="btn btn-primary mw__btn" @click.stop="runAction(row.action)">
                {{ row.statusGroup === 'returned' ? '修改后重提' : '去查看' }}
              </button>
            </view>
          </view>
          <button v-if="hasMore" class="btn btn-secondary" :disabled="loadingMore" @click="loadMore">
            {{ loadingMore ? '加载中…' : '加载更多' }}
          </button>
        </template>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="home" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { canNavigate, runAction } from '@/services/actionRouter'
import { hasFocusRow, isFocusRow, readFocusId, scrollToFocus } from '@/utils/listFocus.mjs'
import { createNetworkPager } from '@/utils/networkPager'
import { toast } from '@/utils/nav'
import { go } from '@/utils/nav'

const TAG_TYPE = { pending: 'warning', processing: 'processing', returned: 'danger', done: 'success' }

// V3 §7：业务回执中心。列表、状态过滤与分页全部由服务端投影提供；
// 每条记录的可办理动作都回它自己的原业务页，本页不复制任何业务状态机。
export default {
  data() {
    return {
      tabs: [], tab: 'all', items: [], state: 'loading',
      cursor: '', hasMore: false, loadingMore: false,
      focusId: '', focusMissing: false
    }
  },
  onLoad(query) {
    this.tab = (query && query.tab) || 'all'
    this.focusId = readFocusId(query, 'caseId')
    this.refresh()
  },
  onPullDownRefresh() { this.refresh().finally(() => uni.stopPullDownRefresh()) },
  methods: {
    tagType(group) { return TAG_TYPE[group] || 'default' },
    shortTime(iso) { return iso ? String(iso).slice(0, 16).replace('T', ' ') : '' },
    canRun(action) { return canNavigate(action, 'student') },
    runAction(action) { return runAction(action, { side: 'student' }) },
    isFocused(row) { return isFocusRow(row, this.focusId, ['caseId']) },
    applyFocus() {
      if (!this.focusId) return
      this.focusMissing = !hasFocusRow(this.items, this.focusId, ['caseId'])
      if (this.focusMissing) return
      this.$nextTick(() => scrollToFocus('#case-', this.focusId))
    },
    openDetail(row) { go(`/pages/student/my-work/detail?caseId=${encodeURIComponent(row.caseId)}`) },
    switchTab(next) {
      const key = typeof next === 'string' ? next : (next && next.key)
      if (!key || key === this.tab) return
      this.tab = key
      // 换分段等于换查询：作废旧 pager，避免上一段的游标与条目串到新分段。
      if (this._pager) this._pager.reset()
      this._pager = null
      this.items = []
      this.refresh()
    },
    // V3 §11.3：分页、去重、epoch 失效与单页内存上限全部交给共享 networkPager，
    // 页面不再各自手写一套（教师端后续复用同一个工具）。
    pager() {
      if (!this._pager || this._pagerTab !== this.tab) {
        this._pagerTab = this.tab
        const tab = this.tab
        this._pager = createNetworkPager(
          (cursor, pageSize) => studentApi.getCases(tab, cursor, pageSize).then((data) => {
            this.tabs = (data && data.tabs) || this.tabs
            return { items: (data && data.items) || [], nextCursor: (data && data.nextCursor) || '' }
          }),
          { pageSize: 20, idKey: 'caseId' }
        )
      }
      return this._pager
    },
    syncFromPager(state) {
      this.items = state.items
      this.hasMore = state.hasMore
      this.loadingMore = state.loading && !state.refreshing
    },
    refresh() {
      this.state = this.items.length ? this.state : 'loading'
      return this.pager().refresh()
        .then((state) => {
          this.syncFromPager(state)
          this.state = 'ready'
          this.applyFocus()
        })
        .catch(() => { this.state = 'error' })
    },
    loadMore() {
      if (this.loadingMore || !this.hasMore) return
      this.loadingMore = true
      return this.pager().loadMore()
        .then((state) => this.syncFromPager(state))
        .catch((e) => toast((e && e.message) || '加载失败'))
        .finally(() => { this.loadingMore = false })
    }
  }
}
</script>

<style scoped>
.mw__seg { position: sticky; top: 0; z-index: 5; background: var(--bg-page, #f9fafb); padding: var(--space-2) var(--space-4); }
.mw__title { font-size: var(--font-size-base); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.mw__meta { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: 4px; }
.mw__meta-item { font-size: 11px; color: var(--text-tertiary); }
.mw__foot { display: flex; justify-content: flex-end; margin-top: var(--space-2); }
.mw__btn { min-width: 120px; }
.is-focus { outline: 2px solid var(--brand-primary); outline-offset: 2px; border-radius: var(--radius-md); }
</style>
