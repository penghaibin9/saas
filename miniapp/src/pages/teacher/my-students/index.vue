<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="我的学生" :subtitle="className || '本人可见范围学生'" show-back />
    <MobileGlobalState :state="state" @retry="reload">
      <view class="page-pad">
        <view class="ms__search">
          <view class="ms__search-row">
            <input
              v-model="keywordInput"
              class="ms__search-input"
              type="text"
              maxlength="100"
              confirm-type="search"
              placeholder="按姓名或学号搜索"
              @confirm="applySearch"
            />
            <button class="ms__search-btn" size="mini" @click="applySearch">搜索</button>
          </view>
          <view class="ms__search-meta">
            <text>共 {{ total }} 名学生</text>
            <text v-if="keyword" class="ms__clear" @click="clearSearch">清除“{{ keyword }}”</text>
          </view>
        </view>

        <MobileGlobalState
          v-if="!items.length"
          state="empty"
          :title="keyword ? '未找到匹配学生' : '暂无学生'"
          :description="keyword ? '可换姓名或学号再次搜索。' : '如信息有误请联系系统管理员核实教师数据范围。'"
        />
        <view class="list-group" v-else>
          <view v-for="s in items" :key="s.studentId" class="list-row" @click="openStudent(s)">
            <view class="ms__avatar">{{ (s.name || '').slice(0, 1) }}</view>
            <view class="flex-1">
              <text class="t-md">{{ s.name }}</text>
              <text class="ms__sub">{{ s.studentNo }} · {{ s.className || '—' }}</text>
            </view>
            <MobileStatusTag :status="s.status" />
          </view>
        </view>

        <view v-if="items.length" class="ms__pager">
          <text v-if="loadingMore">正在加载更多…</text>
          <text v-else-if="hasMore" class="ms__more" @click="loadMore">继续加载</text>
          <text v-else>已加载全部 {{ items.length }} 名学生</text>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherStudentV3Api, TEACHER_STUDENT_PAGE_SIZE } from '@/services/teacherStudentV3Api'
import { normalizeError, toastError } from '@/services/request'
import { decodeQueryText, go } from '@/utils/nav'

export default {
  data() {
    return {
      items: [],
      total: 0,
      nextCursor: '',
      hasMore: false,
      state: 'loading',
      loadingMore: false,
      classId: '',
      className: '',
      keywordInput: '',
      keyword: '',
      _loadEpoch: 0,
      _pageActive: true
    }
  },
  onLoad(q) {
    this._pageActive = true
    this.classId = (q && q.classId) || ''
    // H5 路由会对已编码的中文 query 再编码一次；兼容微信宿主的一次编码和 H5 的双重编码。
    this.className = decodeQueryText(decodeQueryText(q && q.className))
    this.reload()
  },
  onUnload() {
    this._pageActive = false
    this._loadEpoch += 1
  },
  onReachBottom() {
    this.loadMore()
  },
  methods: {
    async load({ append = false } = {}) {
      if (append) {
        if (!this.hasMore || this.loadingMore) return
        this.loadingMore = true
      } else {
        this.state = 'loading'
        this.items = []
        this.total = 0
        this.nextCursor = ''
        this.hasMore = false
      }
      const epoch = this._loadEpoch + 1
      this._loadEpoch = epoch
      const request = {
        classId: this.classId,
        keyword: this.keyword,
        cursor: append ? this.nextCursor : '',
        pageSize: TEACHER_STUDENT_PAGE_SIZE
      }
      try {
        const data = await teacherStudentV3Api.list(request)
        // Search, refresh and load-more can overlap on a slow network.  A late
        // response belongs to its original filter/cursor and must not overwrite
        // the newer server page or attach an old cursor to the next request.
        if (!this._pageActive || this._loadEpoch !== epoch) return
        const incoming = Array.isArray(data && data.items) ? data.items : []
        if (append) {
          const seen = new Set(this.items.map((item) => String(item.studentId)))
          this.items = this.items.concat(incoming.filter((item) => !seen.has(String(item.studentId))))
        } else {
          this.items = incoming
        }
        this.total = Number((data && data.total) || 0)
        this.nextCursor = (data && data.nextCursor) || ''
        this.hasMore = Boolean(data && data.hasMore && this.nextCursor)
        this.state = 'ready'
      } catch (error) {
        if (!this._pageActive || this._loadEpoch !== epoch) return
        if (append) {
          toastError(error)
        } else {
          this.state = normalizeError(error).pageState || 'error'
        }
      } finally {
        if (this._pageActive && this._loadEpoch === epoch) this.loadingMore = false
      }
    },
    reload() {
      return this.load({ append: false })
    },
    loadMore() {
      return this.load({ append: true })
    },
    applySearch() {
      const next = String(this.keywordInput || '').trim()
      if (next === this.keyword && this.state === 'ready') return
      this.keyword = next
      this.reload()
    },
    clearSearch() {
      this.keywordInput = ''
      this.keyword = ''
      this.reload()
    },
    openStudent(s) {
      go('/pages/teacher/student-detail/index?id=' + encodeURIComponent(s.studentId))
    }
  }
}
</script>

<style scoped>
.ms__search { margin-bottom: 12px; padding: 12px; border-radius: var(--radius-lg); background: var(--bg-card); }
.ms__search-row { display: flex; align-items: center; gap: 8px; }
.ms__search-input { flex: 1; min-width: 0; height: 36px; padding: 0 12px; border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-page); font-size: var(--font-size-sm); }
.ms__search-btn { flex-shrink: 0; margin: 0; }
.ms__search-meta { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 8px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ms__clear { color: var(--teacher-700); }
.ms__avatar { width: 40px; height: 40px; border-radius: var(--radius-full); background: var(--teacher-50); color: var(--teacher-700); display: flex; align-items: center; justify-content: center; font-size: var(--font-size-lg); flex-shrink: 0; }
.ms__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ms__pager { padding: 16px 0 6px; text-align: center; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ms__more { color: var(--teacher-700); }
</style>
