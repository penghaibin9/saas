<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="学生实习鉴定" subtitle="填写指导意见 · 审核学生自评" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无学生鉴定"
          description="本人指导学生提交实习自评后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="e in list" :key="e.id" class="card se">
            <view class="row-between" @click="toggle(e)">
              <view class="flex-1">
                <text class="t-md t-bold">{{ e.studentName || '—' }}</text>
                <text class="se__sub">{{ e.studentNo || '' }}</text>
              </view>
              <view class="row" style="gap:6px;">
                <MobileStatusTag :label="e.submitStatusLabel" :type="e.submitStatus === 'SUBMITTED' ? 'success' : 'default'" />
                <MobileStatusTag :label="e.reviewStatusLabel" :type="reviewTone(e.reviewStatus)" />
              </view>
            </view>

            <template v-if="expanded === e.id">
              <view v-if="!detail[e.id]" class="se__loading"><text class="t-sm t-tertiary">加载中…</text></view>
              <template v-else>
                <view class="se__block">
                  <text class="se__block-title">学生自评</text>
                  <text class="se__block-text">{{ detail[e.id].selfSummary || '（未填写）' }}</text>
                  <text class="se__block-text" v-if="detail[e.id].selfHarvest">收获：{{ detail[e.id].selfHarvest }}</text>
                  <text class="se__block-text" v-if="detail[e.id].selfProblem">问题：{{ detail[e.id].selfProblem }}</text>
                </view>

                <view class="se__row se__row--top">
                  <text class="se__label">指导教师意见</text>
                  <textarea class="se__textarea" v-model="drafts[e.id].advisorOpinion" :maxlength="1000"
                    placeholder="请填写指导教师意见（必填）" placeholder-class="se__ph" />
                </view>
                <view class="se__row se__row--top">
                  <text class="se__label">企业导师意见</text>
                  <textarea class="se__textarea se__textarea--sm" v-model="drafts[e.id].mentorOpinion" :maxlength="1000"
                    placeholder="可代填企业导师反馈（可选）" placeholder-class="se__ph" />
                </view>
                <button class="btn btn-ghost" :disabled="acting" @click="saveOpinion(e)">保存意见</button>

                <view class="se__divider" v-if="e.submitStatus === 'SUBMITTED' && e.reviewStatus === 'PENDING'" />
                <view class="se__actions" v-if="e.submitStatus === 'SUBMITTED' && e.reviewStatus === 'PENDING'">
                  <button class="se__reject flex-1" :disabled="acting" @click="review(e, 'RETURN')">退回</button>
                  <button class="se__approve flex-1" :disabled="acting" @click="review(e, 'APPROVE')">通过</button>
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
  data() { return { list: null, state: 'loading', expanded: null, detail: {}, drafts: {}, acting: false } },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    reviewTone(s) { return s === 'APPROVED' ? 'success' : s === 'RETURNED' ? 'danger' : 'warning' },
    load(done) {
      this.state = 'loading'
      teacherApi.getStudentEvalPending()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    toggle(e) {
      if (this.expanded === e.id) { this.expanded = null; return }
      this.expanded = e.id
      if (this.detail[e.id]) return
      teacherApi.getStudentEvalDetail(e.id).then((d) => {
        this.$set ? this.$set(this.detail, e.id, d) : (this.detail[e.id] = d)
        const draft = { advisorOpinion: d.advisorOpinion || '', mentorOpinion: d.mentorOpinion || '' }
        this.$set ? this.$set(this.drafts, e.id, draft) : (this.drafts[e.id] = draft)
      }).catch((err) => {
        toast((err && err.message) || '加载详情失败')
        this.expanded = null
      })
    },
    saveOpinion(e) {
      if (this.acting) return
      const draft = this.drafts[e.id] || {}
      if (!(draft.advisorOpinion || '').trim()) { toast('指导教师意见必填'); return }
      this.acting = true
      teacherApi.submitStudentEvalAdvisorComment(e.id, {
        advisorOpinion: draft.advisorOpinion.trim(), mentorOpinion: (draft.mentorOpinion || '').trim()
      }).then(() => {
        toast('意见已保存')
        e.hasAdvisorOpinion = true
        return teacherApi.getStudentEvalDetail(e.id)
      }).then((d) => {
        if (!d) return
        this.$set ? this.$set(this.detail, e.id, d) : (this.detail[e.id] = d)
      }).catch((err) => {
        toast((err && err.message) || '保存失败，请重试')
      }).finally(() => { this.acting = false })
    },
    review(e, action) {
      if (this.acting) return
      const reject = action === 'RETURN'
      uni.showModal({
        title: reject ? '退回鉴定' : '通过鉴定',
        editable: true, placeholderText: reject ? '请填写退回原因（≥5 字）' : '可填写审核意见（可选）',
        content: '',
        success: (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('退回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.reviewStudentEval(e.id, action, comment)
            .then(() => { toast(reject ? '已退回' : '已通过'); this.load() })
            .catch((err) => {
              const code = err && String(err.code)
              if (code && code === 'DATA_CONFLICT') { toast('该鉴定已被处理，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) toast((err && err.message) || '不在你的数据范围内')
              else toast((err && err.message) || (reject ? '退回' : '通过') + '失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.se { display: flex; flex-direction: column; gap: var(--space-2); }
.se__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.se__loading { padding: var(--space-3) 0; text-align: center; }
.se__block { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); display: flex; flex-direction: column; gap: 4px; }
.se__block-title { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.se__block-text { font-size: var(--font-size-sm); color: var(--text-primary); line-height: 1.5; }
.se__row { display: flex; flex-direction: column; gap: 4px; }
.se__row--top { align-items: stretch; }
.se__label { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.se__textarea { min-height: 72px; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2); }
.se__textarea--sm { min-height: 56px; }
.se__ph { color: var(--text-tertiary); }
.se__divider { height: 1px; background: var(--border-light); margin: var(--space-1) 0; }
.se__actions { display: flex; gap: var(--space-2); }
.se__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.se__reject::after { border: none; }
.se__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.se__approve::after { border: none; }
</style>
