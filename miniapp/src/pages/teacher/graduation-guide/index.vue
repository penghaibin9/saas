<template>
  <view class="page-wrap">
    <!-- 列表模式：待办工作台（待批阅队列入口 + 指导学生列表） -->
    <MobileGlobalState v-if="mode === 'list'" :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <!-- 开题待批阅：进入单页批阅队列 -->
        <view v-if="queue.length" class="gg__queue card" @click="enterReview(0)">
          <view class="row-between">
            <text class="t-md t-bold">开题待批阅</text>
            <text class="gg__queue-count">{{ queue.length }} 条</text>
          </view>
          <text class="gg__queue-hint">逐条查看背景 / 方案 / 成果，处理后自动进入下一条</text>
          <button class="gg__review" @click.stop="enterReview(0)">开始批阅</button>
        </view>

        <view class="gg__filters">
          <text class="gg__filter" :class="{ 'is-active': f === 'all' }" @click="f = 'all'">全部 {{ data.list.length }}</text>
          <text class="gg__filter" :class="{ 'is-active': f === 'review' }" @click="f = 'review'">待批阅 {{ queue.length }}</text>
          <text class="gg__filter" :class="{ 'is-active': f === 'overdue' }" @click="f = 'overdue'">已逾期 {{ overdueCount }}</text>
        </view>

        <view v-if="!filtered.length" class="gg__empty">
          <text>{{ f === 'review' ? '暂无待批阅开题' : f === 'overdue' ? '暂无逾期学生' : '暂无指导学生' }}</text>
        </view>
        <view class="stack">
          <view v-for="g in filtered" :key="g.id" class="gg card">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ g.name }}</text>
                <text class="gg__class">{{ g.className }}</text>
              </view>
              <MobileStatusTag :status="g.status" />
            </view>
            <text class="gg__topic">{{ g.topic }}</text>
            <view class="gg__meta">
              <text class="gg__node">当前节点 · {{ g.node }}</text>
              <text class="gg__deadline" :class="{ 'is-overdue': g.status === 'OVERDUE' }">截止 {{ g.deadline || '未设置' }}</text>
            </view>
            <view class="gg__actions">
              <button v-if="queueIndexOf(g) >= 0" class="gg__review" @click.stop="enterReview(queueIndexOf(g))">去批阅开题</button>
              <button class="btn btn-ghost" @click.stop="addGuidance(g)">记录指导</button>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <!-- 批阅模式：单页详情 + 顶部队列进度 + 底部固定操作 + 上一条/下一条 -->
    <view v-else class="rv">
      <view class="rv__head">
        <text class="rv__back" @click="exitReview">‹ 列表</text>
        <text class="rv__progress">第 {{ queueIndex + 1 }} / {{ queue.length }} 条</text>
        <text class="rv__side"></text>
      </view>
      <scroll-view scroll-y class="rv__body">
        <MobileGlobalState :state="detailState" @retry="loadDetail">
          <view v-if="detail" class="rv__content">
            <text class="rv__stu">{{ detail.studentName }}<text v-if="detail.className"> · {{ detail.className }}</text></text>
            <text class="rv__topic">{{ detail.topicTitle || '（未选题）' }}</text>
            <view class="rv__tags">
              <text class="rv__tag">版本 {{ detail.version || '—' }}</text>
              <text v-if="detail.isResubmit" class="rv__tag rv__tag--warn">重交</text>
              <text class="rv__tag">附件 {{ detail.attachments }}</text>
              <text class="rv__tag">提交 {{ detail.submitAt || '—' }}</text>
            </view>
            <view class="rv__block"><text class="rv__label">选题背景</text><text class="rv__text">{{ detail.background || '（未填写）' }}</text></view>
            <view class="rv__block"><text class="rv__label">研究方案与进度</text><text class="rv__text">{{ detail.plan || '（未填写）' }}</text></view>
            <view class="rv__block"><text class="rv__label">预期成果</text><text class="rv__text">{{ detail.outcome || '（未填写）' }}</text></view>
            <view v-if="detail.reviewComment" class="rv__block">
              <text class="rv__label">上次批阅意见</text><text class="rv__text rv__text--warn">{{ detail.reviewComment }}</text>
            </view>
            <view v-if="detail.versions && detail.versions.length > 1" class="rv__block">
              <text class="rv__label">历史版本</text>
              <text v-for="(v, i) in detail.versions" :key="i" class="rv__ver">· {{ v.title }}<text v-if="v.desc"> — {{ v.desc }}</text></text>
            </view>
            <view v-if="detail.attachments > 0" class="rv__note">附件 {{ detail.attachments }} 个：文件预览与下载请在 PC 端毕设中心查看</view>
          </view>
        </MobileGlobalState>
      </scroll-view>
      <view class="rv__foot">
        <button class="rv__nav" :disabled="queueIndex <= 0 || acting" @click="prev">上一条</button>
        <button class="rv__act rv__return" :disabled="acting || !detail || detailState !== 'ready'" @click="act('return')">退回整改</button>
        <button class="rv__act rv__pass" :disabled="acting || !detail || detailState !== 'ready'" @click="act('pass')">批阅通过</button>
        <button class="rv__nav" :disabled="queueIndex >= queue.length - 1 || acting" @click="next">下一条</button>
      </view>
    </view>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
export default {
  data() {
    return {
      data: null, state: 'loading', f: 'all', acting: false,
      queue: [], mode: 'list', queueIndex: 0, detail: null, detailState: 'loading'
    }
  },
  onLoad() { this.load() },
  // 返回本页后刷新（首个 onShow 与 onLoad 配对，跳过避免重复请求）
  onShow() { if (this._entered) { if (this.mode === 'list') this.load() } this._entered = true },
  onPullDownRefresh() {
    if (this.state === 'loading' || this.mode !== 'list') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    filtered() {
      if (!this.data) return []
      if (this.f === 'review') {
        const ids = new Set(this.queue.map((q) => q.gdStudentId))
        return this.data.list.filter((g) => ids.has(g.id))
      }
      if (this.f === 'overdue') return this.data.list.filter((g) => g.status === 'OVERDUE')
      return this.data.list
    },
    overdueCount() { return this.data ? this.data.list.filter((g) => g.status === 'OVERDUE').length : 0 },
    current() { return this.queue[this.queueIndex] || null }
  },
  methods: {
    toast,
    load(done) {
      if (!this.data) this.state = 'loading'
      teacherApi.getGdStudents().then((d) => {
        this.data = d
        this.queue = (d && d.reviewQueue) || []
        this.state = 'ready'
      }).catch(() => { if (!this.data) this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    queueIndexOf(g) { return this.queue.findIndex((q) => q.gdStudentId === g.id) },
    enterReview(index) {
      if (!this.queue.length) { toast('暂无待批阅开题'); return }
      this.queueIndex = Math.max(0, Math.min(index, this.queue.length - 1))
      this.mode = 'review'
      this.loadDetail()
    },
    exitReview() {
      this.mode = 'list'
      this.detail = null
      this.detailState = 'loading'
      this.load() // 服务器为准刷新，筛选 f 保留在组件状态中不变
    },
    loadDetail() {
      const item = this.current
      if (!item) { this.detailState = 'empty'; return }
      this.detailState = 'loading'
      this.detail = null
      teacherApi.getGraduationProposalDetail(item.proposalId).then((d) => {
        this.detail = { ...d, submitAt: d.submitAt || item.submitAt || '—' }
        this.detailState = 'ready'
      }).catch((e) => {
        this.detailState = 'error'
        toast(normalizeError(e).text)
      })
    },
    prev() { if (this.queueIndex > 0) { this.queueIndex--; this.loadDetail() } },
    next() { if (this.queueIndex < this.queue.length - 1) { this.queueIndex++; this.loadDetail() } },
    act(type) {
      if (this.acting || !this.current) return
      const item = this.current
      const label = type === 'pass' ? '通过' : '退回整改'
      uni.showModal({
        title: label, editable: true,
        placeholderText: type === 'pass' ? '可填写通过意见（选填）' : '请填写退回意见（至少 5 字）',
        success: (r) => {
          if (!r.confirm || this.acting) return
          const comment = (r.content || '').trim()
          if (type !== 'pass' && comment.length < 5) { toast('退回需填写至少 5 字意见'); return }
          this.acting = true
          teacherApi.reviewProposal(item.proposalId, type === 'pass' ? 'APPROVE' : 'REJECT', comment)
            .then(() => { toast('已' + label); this.afterReviewed() })
            .catch((e) => {
              if (String(e && e.code).startsWith('409')) {
                toast('该开题已被批阅，正在刷新队列'); this.afterReviewed()
              } else { toast(normalizeError(e).text) }
            })
            .finally(() => { this.acting = false })
        }
      })
    },
    // 处理后：从队列移除本条并自动进入下一条；队列空则回列表
    afterReviewed() {
      this.queue.splice(this.queueIndex, 1)
      if (!this.queue.length) { this.exitReview(); return }
      if (this.queueIndex > this.queue.length - 1) this.queueIndex = this.queue.length - 1
      this.loadDetail()
    },
    addGuidance(g) {
      if (this.acting) return
      if (!/^\d+$/.test(String(g.id))) { toast('当前为离线数据，无法记录指导'); return }
      uni.showModal({ title: '记录指导', editable: true, placeholderText: '填写本次指导内容', success: (r) => {
        if (!r.confirm || this.acting) return
        if (!r.content || r.content.trim().length < 2) { toast('指导内容至少 2 字'); return }
        this.acting = true
        teacherApi.createGuidance(g.id, { content: r.content.trim(), method: 'ONLINE' })
          .then(() => { toast('已记录') })
          .catch((e) => { toast(normalizeError(e).text) })
          .finally(() => { this.acting = false })
      } })
    }
  }
}
</script>

<style scoped>
.gg__queue { background: var(--teacher-50, var(--primary-50)); border: 1px solid var(--teacher-200, var(--primary-100)); }
.gg__queue-count { font-size: var(--font-size-sm); color: var(--teacher-700); font-weight: var(--font-weight-semibold); }
.gg__queue-hint { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin: var(--space-2) 0 var(--space-3); }
.gg__filters { display: flex; gap: var(--space-2); margin: var(--space-4) 0; }
.gg__filter { padding: 5px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); }
.gg__filter.is-active { background: var(--teacher-600); color: #fff; border-color: var(--teacher-600); }
.gg__empty { padding: var(--space-6) 0; text-align: center; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.gg__class { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.gg__topic { display: block; font-size: var(--font-size-base); color: var(--text-primary); margin: var(--space-2) 0; line-height: 1.4; }
.gg__meta { display: flex; justify-content: space-between; }
.gg__node { font-size: var(--font-size-sm); color: var(--teacher-700); }
.gg__deadline { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.gg__deadline.is-overdue { color: var(--danger-600); }
.gg__actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.gg__review { min-height: 40px; border-radius: var(--radius-md); border: none; background: var(--teacher-600); color: #fff; font-size: var(--font-size-md); padding: 0 var(--space-4); }
.gg__review::after { border: none; }

/* 批阅单页 */
.rv { position: fixed; inset: 0; background: var(--bg-page, var(--gray-50)); display: flex; flex-direction: column; z-index: var(--z-modal, 100); }
.rv__head { flex-shrink: 0; display: flex; align-items: center; justify-content: space-between; padding: calc(var(--space-3) + env(safe-area-inset-top)) var(--page-padding-mobile) var(--space-3); background: var(--bg-card); border-bottom: 1px solid var(--border-light); }
.rv__back { font-size: var(--font-size-base); color: var(--teacher-700); min-width: 60px; }
.rv__progress { font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.rv__side { min-width: 60px; }
.rv__body { flex: 1; overflow-y: auto; }
.rv__content { padding: var(--page-padding-mobile); }
.rv__stu { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.rv__topic { display: block; font-size: var(--font-size-base); color: var(--text-secondary); margin: 6px 0 var(--space-3); line-height: 1.4; }
.rv__tags { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-4); }
.rv__tag { font-size: var(--font-size-xs); color: var(--text-secondary); background: var(--gray-100, var(--gray-50)); padding: 3px 10px; border-radius: var(--radius-full); }
.rv__tag--warn { color: var(--warning-700); background: var(--warning-50); }
.rv__block { background: var(--bg-card); border-radius: var(--radius-md); padding: var(--space-3); margin-bottom: var(--space-3); }
.rv__label { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: 4px; }
.rv__text { display: block; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; white-space: pre-wrap; }
.rv__text--warn { color: var(--danger-600); }
.rv__ver { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; line-height: 1.5; }
.rv__note { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: var(--space-2); line-height: 1.5; }
.rv__foot { flex-shrink: 0; display: flex; gap: var(--space-2); align-items: center; padding: var(--space-3) var(--page-padding-mobile) calc(var(--space-3) + env(safe-area-inset-bottom)); background: var(--bg-card); border-top: 1px solid var(--border-light); }
.rv__nav { flex-shrink: 0; min-height: 42px; padding: 0 var(--space-3); border-radius: var(--radius-md); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-sm); }
.rv__nav::after { border: none; }
.rv__nav[disabled] { opacity: 0.4; }
.rv__act { flex: 1; min-height: 42px; border-radius: var(--radius-md); border: none; font-size: var(--font-size-md); }
.rv__act::after { border: none; }
.rv__return { background: var(--bg-card); color: var(--danger-600); border: 1px solid var(--danger-500); }
.rv__pass { background: var(--teacher-600); color: #fff; }
.rv__act[disabled] { opacity: 0.5; }
</style>
