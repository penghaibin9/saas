<template>
  <view v-if="visible" class="gddq">
    <view class="gddq__head">
      <view class="gddq__head-main">
        <text class="gddq__title">延期答辩待审核</text>
        <text class="gddq__hint">当前批次 · 仅本人稳定绑定的指导学生</text>
      </view>
      <view class="gddq__count"><text>{{ rows.length }}</text><text>待处理</text></view>
    </view>

    <view v-if="loading && !rows.length" class="gddq__state"><text>正在加载延期答辩待办…</text></view>
    <view v-else-if="error" class="gddq__state gddq__state--error">
      <text>{{ error }}。这不是“暂无待办”。</text>
      <button class="gddq__retry" @click="load">重新加载</button>
    </view>
    <view v-else-if="!rows.length" class="gddq__state">
      <text class="gddq__empty">当前没有待导师审核的延期答辩申请</text>
      <text class="gddq__hint">学生提交申请后会进入这里，不需要到其他页面寻找。</text>
    </view>

    <view v-for="row in rows" :key="row.id" class="gddq__card">
      <view class="row-between">
        <view class="gddq__student"><text class="t-md t-bold">{{ row.studentName }}</text><text class="gddq__text">{{ row.studentNo }} · {{ row.className }}</text></view>
        <text class="gddq__status">{{ row.statusLabel }}</text>
      </view>
      <text class="gddq__text">课题：{{ row.topicTitle || '未填写课题' }}</text>
      <view class="gddq__reason"><text class="gddq__label">申请理由</text><text>{{ row.reason }}</text></view>
      <view v-if="row.allowedActions && row.allowedActions.advisorReview" class="gddq__actions">
        <button class="btn btn-primary" :disabled="busyId === row.id" @click="review(row, 'APPROVE')">审核通过</button>
        <button class="btn btn-ghost" :disabled="busyId === row.id" @click="review(row, 'REJECT')">驳回</button>
      </view>
      <text v-else class="gddq__locked">该申请已不属于你的可处理范围，请刷新批次和身份上下文。</text>
    </view>
  </view>
</template>

<script>
import { realRequest, normalizeError, getTeacherGraduationBatch } from '@/services/request'
function pageStack() { return typeof getCurrentPages === 'function' ? getCurrentPages() : [] }
let owner = null
export default {
  name: 'MobileGraduationDelayQueue',
  data() { return { visible: false, rows: [], error: '', busyId: '', lastBatchId: '', timer: null, owns: false, loading: false } },
  mounted() {
    const pages = pageStack(); const page = pages[pages.length - 1]
    const match = ((page && (page.route || page.__route__)) || '') === 'pages/teacher/graduation-guide/index'
    if (match && owner == null) {
      owner = this._uid; this.owns = true; this.visible = true
      this.timer = setInterval(this.syncBatch, 600)
      this.syncBatch()
    }
  },
  beforeUnmount() {
    if (this.timer) clearInterval(this.timer)
    if (this.owns && owner === this._uid) owner = null
  },
  methods: {
    syncBatch() {
      const batch = getTeacherGraduationBatch()
      const id = batch && batch.id ? String(batch.id) : ''
      if (!id) { this.rows = []; this.error = '请先选择毕业设计批次'; this.lastBatchId = ''; return }
      if (id !== this.lastBatchId) { this.lastBatchId = id; this.load() }
    },
    load() {
      if (!getTeacherGraduationBatch() || this.loading) return
      this.loading = true; this.error = ''
      realRequest('/mobile/teacher/graduation/defense-delays/pending?page=1&pageSize=100').then((d) => {
        this.rows = (d && (d.items || d.list)) || []
      }).catch((e) => {
        this.rows = []; this.error = normalizeError(e).text || '延期答辩待办加载失败'
      }).finally(() => { this.loading = false })
    },
    review(row, action) {
      if (!row.allowedActions || !row.allowedActions.advisorReview) {
        uni.showToast({ title: '当前身份不可处理该申请', icon: 'none' }); return
      }
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回延期答辩' : '同意延期答辩',
        editable: true,
        placeholderText: reject ? '填写驳回理由（至少5字）' : '填写导师意见（建议说明后续要求）',
        success: (res) => {
          if (!res.confirm || this.busyId) return
          const comment = (res.content || '').trim()
          if (reject && comment.length < 5) { uni.showToast({ title: '驳回理由至少5字', icon: 'none' }); return }
          this.busyId = row.id
          realRequest(`/mobile/teacher/graduation/defense-delays/${row.id}/review`, { method: 'POST', data: { action, comment } })
            .then(() => { uni.showToast({ title: '审核完成', icon: 'success' }); this.load() })
            .catch((e) => { this.error = normalizeError(e).text || '审核失败' })
            .finally(() => { this.busyId = '' })
        }
      })
    }
  }
}
</script>

<style scoped>
.gddq { margin:0 var(--page-padding-mobile) var(--space-3); padding:var(--space-3); border:1px solid var(--warning-100); border-radius:var(--radius-lg); background:var(--warning-50); overflow:hidden; }.gddq__head { display:flex; justify-content:space-between; align-items:flex-start; gap:var(--space-2); }.gddq__head-main { flex:1; min-width:0; }.gddq__title { display:block; font-size:var(--font-size-base); font-weight:var(--font-weight-medium); color:var(--text-primary); }.gddq__hint,.gddq__text,.gddq__empty { display:block; margin-top:4px; color:var(--text-secondary); font-size:var(--font-size-xs); line-height:1.55; word-break:break-word; }.gddq__count { flex:none; min-width:54px; padding:7px 9px; border-radius:var(--radius-md); background:var(--bg-card); text-align:center; }.gddq__count text { display:block; color:var(--warning-700); font-size:var(--font-size-xs); }.gddq__count text:first-child { font-size:var(--font-size-lg); font-weight:var(--font-weight-medium); }.gddq__state { margin-top:var(--space-3); padding:var(--space-3); border-radius:var(--radius-md); background:var(--bg-card); color:var(--text-secondary); font-size:var(--font-size-sm); }.gddq__state--error { border:1px solid var(--danger-100); background:var(--danger-50); color:var(--danger-600); }.gddq__retry { margin-top:var(--space-2); min-height:36px; line-height:36px; font-size:var(--font-size-sm); }.gddq__card { margin-top:var(--space-3); padding:var(--space-3); border:1px solid var(--warning-200); border-radius:var(--radius-md); background:var(--bg-card); overflow:hidden; }.gddq__student { flex:1; min-width:0; }.gddq__status { flex:none; color:var(--warning-700); font-size:var(--font-size-xs); }.gddq__reason { margin-top:var(--space-2); padding:var(--space-2); border-radius:var(--radius-sm); background:var(--gray-50); }.gddq__reason text { display:block; color:var(--text-primary); font-size:var(--font-size-sm); line-height:1.6; word-break:break-word; }.gddq__reason .gddq__label { margin-bottom:3px; color:var(--text-tertiary); font-size:var(--font-size-xs); }.gddq__actions { display:flex; gap:var(--space-2); margin-top:var(--space-3); }.gddq__actions button { flex:1; min-width:0; }.gddq__locked { display:block; margin-top:var(--space-2); color:var(--danger-600); font-size:var(--font-size-xs); line-height:1.5; }
</style>
