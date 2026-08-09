<template>
  <view class="page-wrap">
    <view class="ap__hero hero-band is-teacher">
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="ap__navbar"><text class="ap__navbar-title">审批中心</text></view>
      <view class="ap__search">
        <text class="ap__search-icon">🔍</text>
        <input
          v-model="keyword"
          class="ap__search-input"
          confirm-type="search"
          placeholder="搜姓名、学号、任务号、业务单号"
          @confirm="search"
          @input="onKeywordInput"
        />
        <text v-if="keyword" class="ap__search-clear" @click="clearSearch">清除</text>
      </view>
    </view>

    <view class="ap__subtabs">
      <view class="ap__subtab" :class="{ 'is-on': sub === 'pending' }" @click="switchTab('pending')">
        待审批<text v-if="sub === 'pending' && total" class="ap__subtab-badge">{{ total }}</text><text v-if="sub === 'pending'" class="ap__subtab-u" />
      </view>
      <view class="ap__subtab" :class="{ 'is-on': sub === 'done' }" @click="switchTab('done')">已审批<text v-if="sub === 'done'" class="ap__subtab-u" /></view>
      <view class="ap__subtab" :class="{ 'is-on': sub === 'mine' }" @click="switchTab('mine')">我发起的<text v-if="sub === 'mine'" class="ap__subtab-u" /></view>
    </view>

    <MobileGlobalState :state="state" @retry="load(true)">
      <view class="page-pad">
        <MobileGlobalState
          v-if="!list.length"
          state="empty"
          :title="emptyTitle"
          :description="keyword ? '当前关键词没有匹配到真实服务端记录，可换姓名、学号或单号重试。' : emptyDescription"
        />
        <template v-else>
          <view class="ap__chips">
            <view class="ap__chip" :class="{ 'is-on': typeFilter === 'all' }" @click="setType('all')">全部</view>
            <view v-for="t in typeOptions" :key="t" class="ap__chip" :class="{ 'is-on': typeFilter === t }" @click="setType(t)">{{ t }}</view>
          </view>

          <view class="ap__queue-meta">
            <text>{{ queueLabel }} · 共 {{ total }} 条</text>
            <text v-if="keyword">搜索「{{ keyword }}」</text>
          </view>

          <view class="stack">
            <view v-for="a in filteredList" :key="sub + '-' + a.taskId" class="ap card">
              <view class="row-between">
                <view class="flex-1">
                  <view class="row ap__title-row"><text class="t-md t-bold">{{ a.title }}</text><text v-if="a.level === 'high'" class="ap__urgent">临期</text></view>
                  <text class="ap__type">{{ a.type }} · #{{ a.taskId }}</text>
                </view>
                <MobileStatusTag :status="a.status" />
              </view>

              <view class="ap__student">
                <text class="ap__student-avatar">{{ (a.student || '申').slice(0,1) }}</text>
                <view class="ap__student-main">
                  <text class="t-sm">{{ a.student }}<template v-if="a.className"> · {{ a.className }}</template></text>
                  <text v-if="a.studentNo" class="ap__student-no">学号 {{ a.studentNo }}</text>
                </view>
                <text class="ap__time">{{ timeText(a) }}</text>
              </view>

              <view v-if="a.fields && a.fields.length" class="ap__fields">
                <view v-for="(f, i) in a.fields" :key="i" class="ap__field"><text class="ap__field-k">{{ f.label }}</text><text class="ap__field-v flex-1">{{ f.value }}</text></view>
              </view>

              <view v-if="sub === 'pending'" class="ap__semantics">
                <text class="ap__semantics-line">退回修改：流程继续，申请人可修改后重提。</text>
                <text class="ap__semantics-line is-danger">驳回终止：原流程结束，不生成原流程重提入口。</text>
              </view>

              <view v-if="sub === 'pending' && a.status === 'PENDING_REVIEW'" class="ap__actions">
                <button class="btn btn-ghost flex-1" :disabled="acting || !canAct(a, 'RETURN')" @click="act(a, 'RETURN')">退回修改</button>
                <button class="ap__reject flex-1" :disabled="acting || !canAct(a, 'REJECT')" @click="act(a, 'REJECT')">驳回终止</button>
                <button class="ap__approve flex-1" :disabled="acting || !canAct(a, 'APPROVE')" @click="act(a, 'APPROVE')">通过</button>
              </view>
            </view>
          </view>

          <view class="ap__pager">
            <text v-if="hasMore && !loadingMore" class="ap__pager-link" @click="loadMore">加载更多</text>
            <text v-else-if="loadingMore" class="ap__pager-muted">正在加载…</text>
            <text v-else class="ap__pager-muted">已加载全部 {{ total }} 条</text>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { getApprovalQueue, actApproval } from '@/services/approvalApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const PAGE_SIZE = 20

export default {
  data() {
    return {
      list: [], total: 0, page: 1, pageSize: PAGE_SIZE,
      state: 'loading', loadingMore: false, acting: false,
      sub: 'pending', typeFilter: 'all', keyword: '', searchTimer: null,
      statusBarHeight: 20
    }
  },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load(true)
  },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(true, () => uni.stopPullDownRefresh())
  },
  onReachBottom() {
    this.loadMore()
  },
  computed: {
    typeOptions() { return [...new Set(this.list.map((a) => a.type).filter(Boolean))] },
    filteredList() { return this.typeFilter === 'all' ? this.list : this.list.filter((a) => a.type === this.typeFilter) },
    hasMore() { return this.list.length < this.total },
    queueLabel() { return { pending: '待我审批', done: '我已审批', mine: '我发起的' }[this.sub] || '审批队列' },
    emptyTitle() { return { pending: '暂无待审批', done: '暂无已审批记录', mine: '暂无我发起的审批' }[this.sub] },
    emptyDescription() {
      return this.sub === 'pending'
        ? '这里只展示服务端当前分配给你的真实待办。'
        : this.sub === 'done'
          ? '办理完成后会进入这里，支持服务端真分页查询。'
          : '你作为申请人发起的真实审批实例会进入这里。'
    }
  },
  beforeUnmount() {
    if (this.searchTimer) clearTimeout(this.searchTimer)
  },
  methods: {
    canAct(task, action) { return Array.isArray(task.allowedActions) && task.allowedActions.includes(action) },
    timeText(a) {
      if (this.sub === 'done' && a.actedTime) return '办理 ' + a.actedTime.slice(5, 16)
      return a.submitTime ? '提交 ' + a.submitTime.slice(5, 16) : ''
    },
    switchTab(next) {
      if (this.sub === next) return
      this.sub = next
      this.typeFilter = 'all'
      this.load(true)
    },
    setType(type) {
      this.typeFilter = type
    },
    search() {
      if (this.searchTimer) clearTimeout(this.searchTimer)
      this.load(true)
    },
    onKeywordInput() {
      if (this.searchTimer) clearTimeout(this.searchTimer)
      this.searchTimer = setTimeout(() => this.load(true), 350)
    },
    clearSearch() {
      this.keyword = ''
      this.load(true)
    },
    async load(reset = true, done) {
      if (reset) {
        this.state = 'loading'
        this.page = 1
      }
      try {
        const d = await getApprovalQueue(this.sub, this.page, this.pageSize, this.keyword)
        this.list = d.items || []
        this.total = Number(d.total || 0)
        this.page = Number(d.page || 1)
        this.state = 'ready'
        if (this.typeFilter !== 'all' && !this.typeOptions.includes(this.typeFilter)) this.typeFilter = 'all'
      } catch (e) {
        this.state = 'error'
        const err = normalizeError(e)
        toast(err.text || '审批队列加载失败')
      } finally {
        if (done) done()
      }
    },
    async loadMore() {
      if (!this.hasMore || this.loadingMore || this.state !== 'ready') return
      this.loadingMore = true
      const nextPage = this.page + 1
      try {
        const d = await getApprovalQueue(this.sub, nextPage, this.pageSize, this.keyword)
        const seen = new Set(this.list.map((x) => String(x.taskId)))
        const next = (d.items || []).filter((x) => !seen.has(String(x.taskId)))
        this.list = [...this.list, ...next]
        this.total = Number(d.total || this.total)
        this.page = Number(d.page || nextPage)
      } catch (e) {
        const err = normalizeError(e)
        toast(err.text || '加载更多失败，请重试')
      } finally {
        this.loadingMore = false
      }
    },
    act(task, action) {
      if (this.acting || !this.canAct(task, action)) return
      const labels = { APPROVE: '通过', RETURN: '退回修改', REJECT: '驳回终止' }
      const label = labels[action]
      const needReason = action !== 'APPROVE'
      uni.showModal({
        title: label,
        editable: needReason,
        placeholderText: action === 'RETURN' ? '请填写退回原因与修改要求' : action === 'REJECT' ? '请填写终止原流程的原因' : '',
        content: needReason ? '' : `确认通过「${task.title}」？`,
        success: async (r) => {
          if (!r.confirm || this.acting) return
          const reason = String(r.content || '').trim()
          if (needReason && !reason) { toast(action === 'RETURN' ? '请填写退回修改原因' : '请填写驳回终止原因'); return }
          this.acting = true
          try {
            const result = await actApproval(task, action, reason)
            const expectedStatus = { APPROVE: 'APPROVED', RETURN: 'RETURNED', REJECT: 'REJECTED' }[action]
            if (!result || String(result.status || '').toUpperCase() !== expectedStatus) {
              throw { code: 'BAD_RESPONSE', message: '服务端审批结果与请求动作不一致' }
            }
            toast(action === 'RETURN' ? '已退回修改，申请人可修改后重提' : action === 'REJECT' ? '已驳回终止原流程' : '审批已通过')
            // 连续工作队列：动作成功后重新读取真实第一页，下一条自然顶上来；不在本地伪造终态。
            await this.load()
          } catch (e) {
            const err = normalizeError(e)
            if (err.kind === 'conflict') {
              toast('该审批事实已变化，正在刷新')
              await this.load(true)
            } else {
              toast(err.text || `${label}失败，请重试`)
            }
          } finally {
            this.acting = false
          }
        }
      })
    }
  }
}
</script>

<style scoped>
.ap__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.ap__navbar { height: 40px; display: flex; align-items: center; justify-content: center; }
.ap__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.ap__search { display: flex; align-items: center; gap: var(--space-2); background: rgba(255,255,255,.94); border-radius: var(--radius-md); padding: 8px var(--space-4); margin-top: var(--space-1); color: var(--text-tertiary); font-size: var(--font-size-sm); }
.ap__search-input { flex: 1; height: 30px; font-size: var(--font-size-sm); color: var(--text-primary); }
.ap__search-clear { color: var(--teacher-700); font-size: var(--font-size-xs); }
.ap__subtabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.ap__subtab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.ap__subtab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.ap__subtab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.ap__subtab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.ap__chips { display: flex; gap: var(--space-2); overflow-x: auto; margin-bottom: var(--space-3); }
.ap__chip { flex-shrink: 0; font-size: var(--font-size-sm); padding: 6px 13px; border-radius: var(--radius-full); background: var(--bg-card); color: var(--text-secondary); box-shadow: var(--shadow-card); }
.ap__chip.is-on { background: var(--teacher-600); color: #fff; }
.ap__queue-meta { display: flex; justify-content: space-between; gap: var(--space-2); margin-bottom: var(--space-2); color: var(--text-tertiary); font-size: var(--font-size-xs); }
.ap__title-row { gap: 6px; }
.ap__urgent { font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 6px; border-radius: var(--radius-sm); }
.ap__type { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; }
.ap__student { display: flex; align-items: center; gap: var(--space-2); margin: var(--space-3) 0; }
.ap__student-main { display: flex; flex-direction: column; min-width: 0; }
.ap__student-no { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ap__student-avatar { width: 26px; height: 26px; border-radius: var(--radius-full); background: var(--teacher-50); color: var(--teacher-700); display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xs); }
.ap__time { margin-left: auto; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ap__fields { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.ap__field { display: flex; gap: var(--space-3); padding: 5px 0; }
.ap__field-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 76px; flex-shrink: 0; }
.ap__field-v { font-size: var(--font-size-sm); color: var(--text-primary); }
.ap__semantics { margin: var(--space-3) 0; padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); background: var(--gray-50); display: flex; flex-direction: column; gap: 4px; }
.ap__semantics-line { font-size: var(--font-size-xs); color: var(--text-secondary); }
.ap__semantics-line.is-danger { color: var(--danger-600); }
.ap__actions { display: flex; gap: var(--space-2); }
.ap__reject, .ap__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); }
.ap__reject { border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ap__approve { border: none; background: var(--teacher-600); color: #fff; }
.ap__reject::after, .ap__approve::after { border: none; }
.ap__pager { display: flex; justify-content: center; padding: var(--space-5) 0 var(--space-3); font-size: var(--font-size-sm); }
.ap__pager-link { color: var(--teacher-700); }
.ap__pager-muted { color: var(--text-tertiary); }
button[disabled] { opacity: .45; }
</style>
