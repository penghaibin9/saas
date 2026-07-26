<template>
  <view v-if="visible" class="gdbc">
    <view class="gdbc__head">
      <view class="gdbc__main">
        <text class="gdbc__label">当前毕设批次</text>
        <picker v-if="batches.length" mode="selector" :range="batchLabels" :value="selectedIndex" @change="changeBatch">
          <view class="gdbc__picker">
            <view class="gdbc__text">
              <text class="gdbc__name">{{ selectedBatch ? selectedBatch.batchName : '请选择批次' }}</text>
              <text v-if="selectedBatch" class="gdbc__meta">{{ selectedBatch.gradeYear || selectedBatch.academicYear || selectedBatch.batchNo }} · {{ statusLabel(selectedBatch.status) }}</text>
            </view>
            <text class="gdbc__arrow">切换 ›</text>
          </view>
        </picker>
        <view v-else-if="loading" class="gdbc__picker"><text class="gdbc__meta">正在读取本人可处理批次…</text></view>
        <view v-else class="gdbc__picker"><text class="gdbc__error">{{ error || '当前没有可处理的毕业设计批次' }}</text></view>
      </view>
      <button v-if="error" class="gdbc__retry" @click="load">重试</button>
    </view>

    <view class="gdbc__guide">
      <view class="gdbc__guide-main">
        <text class="gdbc__guide-k">本页用途</text>
        <text class="gdbc__guide-v">{{ pageMeta.purpose }}</text>
      </view>
      <view class="gdbc__guide-main">
        <text class="gdbc__guide-k">下一步</text>
        <text class="gdbc__guide-v">{{ pageMeta.next }}</text>
      </view>
    </view>
  </view>
</template>

<script>
import { realRequest, getTeacherGraduationBatch, setTeacherGraduationBatch, normalizeError } from '@/services/request'

const ROUTES = new Set([
  'pages/teacher/graduation-guide/index',
  'pages/teacher/graduation-topics/index',
  'pages/teacher/graduation-taskbook/index',
  'pages/teacher/defense-score/index'
])

const PAGE_META = {
  'pages/teacher/graduation-guide/index': {
    purpose: '集中查看指导学生、材料待审、中期、评阅、答辩和成绩待办。',
    next: '优先处理带数量徽标的队列，完成后自动进入下一条。'
  },
  'pages/teacher/graduation-topics/index': {
    purpose: '确认学生志愿，并审核与本人指导题目相关的变更申请。',
    next: '先核对题目、志愿顺序和变更理由，再确认或驳回。'
  },
  'pages/teacher/graduation-taskbook/index': {
    purpose: '查看本人学生任务书状态，处理下达、变更和确认进度。',
    next: '优先处理未下达、待确认或需要变更的任务书。'
  },
  'pages/teacher/defense-score/index': {
    purpose: '为本人担任评委的学生录入答辩评分、评语或缺席情况。',
    next: '按答辩顺序逐人评分，保存后继续处理下一名学生。'
  }
}

function pageStack() {
  return typeof getCurrentPages === 'function' ? getCurrentPages() : []
}

export default {
  name: 'MobileGraduationBatchContext',
  data() {
    return {
      visible: false,
      ownsPageSlot: false,
      pageRoute: '',
      loading: false,
      error: '',
      batches: [],
      selectedId: ''
    }
  },
  computed: {
    batchLabels() { return this.batches.map((b) => `${b.batchName}${b.gradeYear ? ` · ${b.gradeYear}` : ''}`) },
    selectedIndex() {
      const i = this.batches.findIndex((b) => String(b.id) === String(this.selectedId))
      return i < 0 ? 0 : i
    },
    selectedBatch() { return this.batches[this.selectedIndex] || null },
    pageMeta() {
      return PAGE_META[this.pageRoute] || {
        purpose: '查看当前批次中与本人角色相关的毕业设计任务。',
        next: '先确认批次，再处理当前页面的待办。'
      }
    }
  },
  mounted() {
    const pages = pageStack()
    const page = pages[pages.length - 1]
    const route = (page && (page.route || page.__route__)) || ''
    this.pageRoute = route
    if (!ROUTES.has(route)) return

    // 同一页面可能嵌套多个 MobileGlobalState；批次与任务说明只展示一次。
    if (page && !page.__graduationBatchContextOwner) {
      page.__graduationBatchContextOwner = this._uid || true
      this.ownsPageSlot = true
      this.visible = true
      this.load()
    }
  },
  beforeUnmount() {
    if (!this.ownsPageSlot) return
    const pages = pageStack()
    const page = pages[pages.length - 1]
    if (page) delete page.__graduationBatchContextOwner
  },
  methods: {
    statusLabel(status) { return ({ DRAFT: '筹备中', RUNNING: '进行中', CLOSED: '已结束' })[status] || status || '—' },
    load() {
      if (this.loading) return
      this.loading = true
      this.error = ''
      realRequest('/mobile/teacher/graduation/batches').then((data) => {
        this.batches = (data && data.items) || []
        const cached = getTeacherGraduationBatch()
        const preferred = this.batches.find((b) => cached && String(b.id) === String(cached.id))
          || this.batches.find((b) => String(b.id) === String(data && data.selectedBatchId))
          || this.batches[0]
        const oldId = cached && cached.id ? String(cached.id) : ''
        if (preferred) {
          this.selectedId = String(preferred.id)
          setTeacherGraduationBatch({ id: preferred.id, name: preferred.batchName, status: preferred.status })
          if (!oldId) this.reloadCurrentPage()
        } else {
          this.selectedId = ''
          setTeacherGraduationBatch(null)
        }
      }).catch((e) => { this.error = normalizeError(e).text || '批次加载失败' })
        .finally(() => { this.loading = false })
    },
    changeBatch(e) {
      const index = Number(e && e.detail && e.detail.value)
      const next = this.batches[index]
      if (!next || String(next.id) === String(this.selectedId)) return
      this.selectedId = String(next.id)
      setTeacherGraduationBatch({ id: next.id, name: next.batchName, status: next.status })
      this.reloadCurrentPage()
    },
    reloadCurrentPage() {
      this.$nextTick(() => {
        const pages = pageStack()
        const page = pages[pages.length - 1]
        const vm = page && page.$vm
        if (vm && typeof vm.load === 'function') { vm.load(); return }
        if (vm && typeof vm.reloadTab === 'function') { vm.reloadTab(); return }
        try { uni.startPullDownRefresh() } catch (e) { /* 页面无下拉能力时保持当前状态 */ }
      })
    }
  }
}
</script>

<style scoped>
.gdbc {
  margin: 0 var(--page-padding-mobile) var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
}
.gdbc__head { display: flex; align-items: center; gap: var(--space-2); }
.gdbc__main { min-width: 0; flex: 1; }
.gdbc__label { display: block; margin-bottom: 4px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.gdbc__picker {
  min-height: 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: 0 var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--gray-50);
}
.gdbc__text { min-width: 0; }
.gdbc__name { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--font-size-base); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.gdbc__meta { display: block; margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-secondary); }
.gdbc__arrow { flex: none; font-size: var(--font-size-sm); color: var(--primary-600); }
.gdbc__error { font-size: var(--font-size-sm); color: var(--danger-600); overflow-wrap: anywhere; }
.gdbc__retry { flex: none; margin: 0; min-height: 38px; line-height: 38px; padding: 0 var(--space-3); font-size: var(--font-size-sm); color: var(--primary-600); background: var(--bg-card); border: 1px solid var(--primary-200); border-radius: var(--radius-md); }
.gdbc__guide {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-light);
}
.gdbc__guide-main { min-width: 0; }
.gdbc__guide-k { display: block; margin-bottom: 3px; font-size: 10px; color: var(--text-tertiary); }
.gdbc__guide-v { display: block; font-size: var(--font-size-xs); color: var(--text-secondary); line-height: 1.55; overflow-wrap: anywhere; }
@media (max-width: 360px) {
  .gdbc__guide { grid-template-columns: 1fr; gap: var(--space-2); }
}
</style>