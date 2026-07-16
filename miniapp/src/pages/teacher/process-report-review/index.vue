<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="过程报告批阅" subtitle="日报 · 月报 · 实习总结" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待批阅报告"
          description="本人指导学生提交日报/月报/实习总结后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="r in list" :key="r.id" class="card pr">
            <view class="row-between" @click="toggle(r)">
              <view class="flex-1">
                <text class="t-md t-bold">{{ r.studentName || '—' }}</text>
                <text class="pr__sub">{{ r.studentNo || '' }} · {{ r.reportTypeLabel }} · {{ r.periodKey }} · {{ r.wordCount }}字</text>
              </view>
              <MobileStatusTag :label="r.statusLabel" type="warning" />
            </view>

            <template v-if="expanded === r.id">
              <view v-if="!detail[r.id]" class="pr__loading"><text class="t-sm t-tertiary">加载中…</text></view>
              <template v-else>
                <view class="pr__content"><text class="pr__content-text">{{ detail[r.id].content || '（无正文）' }}</text></view>
                <view class="pr__actions">
                  <button class="pr__reject flex-1" :disabled="acting" @click="review(r, 'RETURN')">退回</button>
                  <button class="pr__approve flex-1" :disabled="acting" @click="review(r, 'APPROVE')">通过</button>
                </view>
              </template>
            </template>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

export default {
  data() { return { list: null, state: 'loading', expanded: null, detail: {}, acting: false } },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    load(done) {
      this.state = 'loading'
      teacherApi.getProcessReportPending()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    toggle(r) {
      if (this.expanded === r.id) { this.expanded = null; return }
      this.expanded = r.id
      if (this.detail[r.id]) return
      teacherApi.getProcessReportDetail(r.id).then((d) => {
        this.$set ? this.$set(this.detail, r.id, d) : (this.detail[r.id] = d)
      }).catch((err) => {
        toast((err && err.message) || '加载详情失败')
        this.expanded = null
      })
    },
    review(r, action) {
      if (this.acting) return
      const reject = action === 'RETURN'
      uni.showModal({
        title: reject ? '退回报告' : '通过报告',
        editable: true, placeholderText: reject ? '请填写退回原因（≥5 字）' : '可填写批阅意见（可选）',
        content: '',
        success: (m) => {
          if (!m.confirm) return
          const comment = (m.content || '').trim()
          if (reject && comment.length < 5) { toast('退回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.reviewProcessReport(r.id, action, comment)
            .then(() => { toast(reject ? '已退回' : '已通过'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code === 'DATA_CONFLICT') { toast((e && e.message) || '当前状态不可批阅，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) toast((e && e.message) || '不在你的数据范围内')
              else toast((e && e.message) || (reject ? '退回' : '通过') + '失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.pr { display: flex; flex-direction: column; gap: var(--space-2); }
.pr__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.pr__loading { padding: var(--space-3) 0; text-align: center; }
.pr__content { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-3); }
.pr__content-text { font-size: var(--font-size-sm); color: var(--text-primary); line-height: 1.6; white-space: pre-wrap; }
.pr__actions { display: flex; gap: var(--space-2); }
.pr__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.pr__reject::after { border: none; }
.pr__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.pr__approve::after { border: none; }
</style>
