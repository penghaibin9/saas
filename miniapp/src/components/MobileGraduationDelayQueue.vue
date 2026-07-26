<template>
  <view v-if="visible" class="gddq">
    <view class="gddq__head"><view><text class="gddq__title">延期答辩待审核</text><text class="gddq__hint">仅显示当前批次、本人指导学生的待导师审核申请。</text></view><text class="gddq__refresh" @click="load">刷新</text></view>
    <text v-if="error" class="gddq__error">{{ error }}</text>
    <text v-else-if="!rows.length" class="gddq__empty">当前没有待导师审核的延期答辩申请</text>
    <view v-for="row in rows" :key="row.id" class="gddq__card">
      <view class="row-between"><text class="t-md t-bold">{{ row.studentName }}</text><text class="gddq__status">{{ row.statusLabel }}</text></view>
      <text class="gddq__text">{{ row.studentNo }} · {{ row.className }}</text>
      <text class="gddq__text">课题：{{ row.topicTitle || '—' }}</text>
      <text class="gddq__reason">申请理由：{{ row.reason }}</text>
      <view class="gddq__actions">
        <button class="btn btn-primary" :disabled="busyId === row.id" @click="review(row, 'APPROVE')">审核通过</button>
        <button class="btn btn-ghost" :disabled="busyId === row.id" @click="review(row, 'REJECT')">驳回</button>
      </view>
    </view>
  </view>
</template>

<script>
import { realRequest, normalizeError, getTeacherGraduationBatch } from '@/services/request'
function pageStack() { return typeof getCurrentPages === 'function' ? getCurrentPages() : [] }
let owner = null
export default {
  name: 'MobileGraduationDelayQueue',
  data() { return { visible: false, rows: [], error: '', busyId: '', lastBatchId: '', timer: null, owns: false } },
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
      if (id && id !== this.lastBatchId) { this.lastBatchId = id; this.load() }
    },
    load() {
      if (!getTeacherGraduationBatch()) return
      this.error = ''
      realRequest('/mobile/teacher/graduation/defense-delays/pending?page=1&pageSize=100').then((d) => {
        this.rows = (d && (d.items || d.list)) || []
      }).catch((e) => { this.rows = []; this.error = normalizeError(e).text || '延期答辩待办加载失败' })
    },
    review(row, action) {
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回延期答辩' : '同意延期答辩',
        editable: true,
        placeholderText: reject ? '填写驳回理由（至少5字）' : '填写导师意见（选填）',
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
.gddq { margin:0 var(--page-padding-mobile) var(--space-3); padding:var(--space-3); border:1px solid var(--warning-100); border-radius:var(--radius-lg); background:var(--warning-50); }.gddq__head { display:flex; justify-content:space-between; gap:var(--space-2); }.gddq__title { display:block; font-size:var(--font-size-base); font-weight:var(--font-weight-medium); color:var(--text-primary); }.gddq__hint,.gddq__text,.gddq__empty { display:block; margin-top:4px; color:var(--text-secondary); font-size:var(--font-size-xs); line-height:1.5; }.gddq__refresh,.gddq__status { color:var(--warning-700); font-size:var(--font-size-xs); }.gddq__card { margin-top:var(--space-3); padding:var(--space-3); border:1px solid var(--warning-200); border-radius:var(--radius-md); background:var(--bg-card); }.gddq__reason { display:block; margin-top:var(--space-2); color:var(--text-primary); font-size:var(--font-size-sm); line-height:1.6; }.gddq__actions { display:flex; gap:var(--space-2); margin-top:var(--space-3); }.gddq__actions button { flex:1; }.gddq__error { display:block; margin-top:var(--space-2); color:var(--danger-600); font-size:var(--font-size-sm); }
</style>
