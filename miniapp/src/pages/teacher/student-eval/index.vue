<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="学生实习鉴定" subtitle="指导意见与学校审核职责分离" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack">
        <view v-if="batches.length" class="card se__batch">
          <text class="se__label">实习批次</text>
          <picker class="flex-1" mode="selector" :range="batchLabels" :value="batchIndex" @change="onBatch">
            <view class="se__pick">{{ batchLabels[batchIndex] || '请选择批次' }} <text>▾</text></view>
          </picker>
        </view>
        <MobileInlineAlert type="info" :description="roleHint" />
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可查看批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="暂无学生鉴定" description="当前批次学生提交实习自评后会出现在这里。" />
        <view v-for="item in list" :key="item.id" class="card se">
          <view class="row-between" @click="toggle(item)">
            <view class="flex-1">
              <text class="t-md t-bold">{{ item.studentName || '—' }}</text>
              <text class="se__sub">{{ item.studentNo || '' }} · {{ item.advisorName || '导师待分配' }}</text>
            </view>
            <view class="row" style="gap:6px;">
              <MobileStatusTag :label="item.submitStatusLabel" :type="item.submitStatus === 'SUBMITTED' ? 'success' : 'default'" />
              <MobileStatusTag :label="item.reviewStatusLabel" :type="reviewTone(item.reviewStatus)" />
            </view>
          </view>
          <text class="se__version">记录版本 {{ item.version }}</text>

          <template v-if="expanded === item.id">
            <view v-if="!details[item.id]" class="se__loading"><text class="t-sm t-tertiary">加载中…</text></view>
            <template v-else>
              <view class="se__block">
                <text class="se__block-title">学生自评</text>
                <text class="se__block-text">{{ details[item.id].selfSummary || '（未填写）' }}</text>
                <text v-if="details[item.id].selfHarvest" class="se__block-text">收获：{{ details[item.id].selfHarvest }}</text>
                <text v-if="details[item.id].selfProblem" class="se__block-text">问题：{{ details[item.id].selfProblem }}</text>
              </view>

              <template v-if="canAdvisor && item.reviewStatus === 'PENDING'">
                <view class="se__row se__row--top">
                  <text class="se__label">指导教师意见 *</text>
                  <textarea class="se__textarea" v-model="drafts[item.id].advisorOpinion" maxlength="1000" placeholder="至少5个字" />
                </view>
                <view class="se__row se__row--top">
                  <text class="se__label">企业导师反馈</text>
                  <textarea class="se__textarea se__textarea--sm" v-model="drafts[item.id].mentorOpinion" maxlength="1000" placeholder="根据企业原始反馈如实填写（可选）" />
                </view>
                <button class="btn btn-ghost" :disabled="acting" @click="saveOpinion(item)">按当前版本保存指导意见</button>
              </template>
              <view v-else-if="details[item.id].advisorOpinion" class="se__block">
                <text class="se__block-title">指导教师意见</text>
                <text class="se__block-text">{{ details[item.id].advisorOpinion }}</text>
              </view>

              <view v-if="canReview && item.submitStatus === 'SUBMITTED' && item.reviewStatus === 'PENDING'" class="se__actions">
                <button class="se__reject flex-1" :disabled="acting" @click="review(item, 'RETURN')">学校退回</button>
                <button class="se__approve flex-1" :disabled="acting || !details[item.id].advisorOpinion" @click="review(item, 'APPROVE')">学校审核通过</button>
              </view>
              <MobileInlineAlert v-if="canReview && !details[item.id].advisorOpinion && item.reviewStatus === 'PENDING'" type="warning" description="指导教师尚未填写意见，学校不能审核通过。" />
              <MobileInlineAlert v-if="details[item.id].reviewComment" :type="item.reviewStatus === 'RETURNED' ? 'warning' : 'info'" :description="`学校审核意见：${details[item.id].reviewComment}`" />
            </template>
          </template>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { useInternshipContextStore } from '@/stores/internshipContext'
import {
  teacherInternshipStudentEvals,
  teacherInternshipStudentEvalDetail,
  teacherInternshipStudentEvalAdvisorComment,
  teacherInternshipStudentEvalReview
} from '@/services/internshipApi'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      list: [], state: 'loading', expanded: '', details: {}, drafts: {}, acting: false,
      batches: [], batchId: '', batchIndex: 0
    }
  },
  computed: {
    context() { return useInternshipContextStore() },
    canAdvisor() { return this.context.can('internship.eval.advisor.manage') },
    canReview() { return this.context.can('internship.eval.self.review') },
    batchLabels() { return this.batches.map((x) => `${x.name} · ${x.status} · ${x.studentCount}人`) },
    roleHint() {
      if (this.canAdvisor && this.canReview) return '当前角色同时拥有指导意见和学校审核权限，但同一节点仍按版本分开操作；学校审核必须在指导意见完成后进行。'
      if (this.canReview) return '当前为学校/学院审核角色：可查看自评和指导意见，不能代替指导教师填写意见。'
      if (this.canAdvisor) return '当前为指导教师角色：只能填写本人学生的指导意见，不能完成学校终审。'
      return '当前仅可查看本人数据范围内的学生鉴定。'
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    reviewTone(status) { return status === 'APPROVED' ? 'success' : status === 'RETURNED' ? 'danger' : 'warning' },
    async load(done) {
      this.state = 'loading'
      try {
        this.context.restore()
        await this.context.load(true)
        this.batches = this.context.batches || []
        this.batchId = this.context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((x) => String(x.id) === String(this.batchId)))
        if (!this.batchId) this.list = []
        else {
          const data = await teacherInternshipStudentEvals(this.batchId)
          this.list = data?.list || []
        }
        this.expanded = ''
        this.details = {}
        this.drafts = {}
        this.state = 'ready'
      } catch (e) { this.state = 'error' }
      finally { if (done) done() }
    },
    async onBatch(e) {
      this.batchIndex = Number(e.detail.value)
      this.context.selectBatch(this.batches[this.batchIndex]?.id)
      await this.load()
    },
    async toggle(item) {
      if (this.expanded === item.id) { this.expanded = ''; return }
      this.expanded = item.id
      if (this.details[item.id]) return
      try {
        const detail = await teacherInternshipStudentEvalDetail(item.id)
        this.details = { ...this.details, [item.id]: detail }
        this.drafts = { ...this.drafts, [item.id]: {
          advisorOpinion: detail.advisorOpinion || '', mentorOpinion: detail.mentorOpinion || ''
        } }
      } catch (e) { toast(e?.message || '加载详情失败'); this.expanded = '' }
    },
    async refreshItem(item) {
      const detail = await teacherInternshipStudentEvalDetail(item.id)
      this.details = { ...this.details, [item.id]: detail }
      const index = this.list.findIndex((x) => x.id === item.id)
      if (index >= 0) this.list.splice(index, 1, { ...this.list[index], ...detail })
      return detail
    },
    async saveOpinion(item) {
      if (this.acting || !this.canAdvisor) return
      const draft = this.drafts[item.id] || {}
      if (String(draft.advisorOpinion || '').trim().length < 5) return toast('指导教师意见至少5个字')
      this.acting = true
      try {
        const detail = this.details[item.id]
        await teacherInternshipStudentEvalAdvisorComment(item.id, {
          advisorOpinion: String(draft.advisorOpinion).trim(),
          mentorOpinion: String(draft.mentorOpinion || '').trim(),
          expectedVersion: detail.version
        })
        toast('指导意见已保存')
        await this.refreshItem(item)
      } catch (e) {
        if (String(e?.code || '').includes('409') || e?.code === 'DATA_CONFLICT') {
          toast('鉴定版本已变化，正在刷新')
          await this.refreshItem(item)
        } else toast(e?.message || '保存失败')
      } finally { this.acting = false }
    },
    review(item, action) {
      if (this.acting || !this.canReview) return
      const returned = action === 'RETURN'
      uni.showModal({
        title: returned ? '学校退回鉴定' : '学校审核通过',
        editable: true,
        placeholderText: returned ? '请填写退回原因（至少5字）' : '可填写审核意见',
        content: '',
        success: async (result) => {
          if (!result.confirm) return
          const comment = String(result.content || '').trim()
          if (returned && comment.length < 5) return toast('退回原因至少5个字')
          this.acting = true
          try {
            const detail = this.details[item.id]
            await teacherInternshipStudentEvalReview(item.id, {
              action, comment, expectedVersion: detail.version
            })
            toast(returned ? '已退回学生修改' : '学校审核已通过')
            await this.load()
          } catch (e) {
            if (String(e?.code || '').includes('409') || e?.code === 'DATA_CONFLICT') {
              toast('鉴定已被处理，正在刷新')
              await this.load()
            } else toast(e?.message || '审核失败')
          } finally { this.acting = false }
        }
      })
    }
  }
}
</script>

<style scoped>
.se { display:flex;flex-direction:column;gap:var(--space-2); }
.se__batch { display:flex;align-items:center;gap:var(--space-3);min-height:48px; }
.se__pick { text-align:right;font-size:var(--font-size-base);color:var(--text-primary); }
.se__sub,.se__version { display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:2px; }
.se__loading { padding:var(--space-3) 0;text-align:center; }
.se__block { background:var(--gray-50);border-radius:var(--radius-md);padding:var(--space-2) var(--space-3);display:flex;flex-direction:column;gap:4px; }
.se__block-title { font-size:var(--font-size-xs);color:var(--text-tertiary); }
.se__block-text { font-size:var(--font-size-sm);color:var(--text-primary);line-height:1.5; }
.se__row { display:flex;flex-direction:column;gap:4px; }
.se__row--top { align-items:stretch; }
.se__label { font-size:var(--font-size-sm);color:var(--text-tertiary);width:90px;flex-shrink:0; }
.se__textarea { min-height:72px;font-size:var(--font-size-base);color:var(--text-primary);line-height:1.6;background:var(--gray-50);border-radius:var(--radius-md);padding:var(--space-2); }
.se__textarea--sm { min-height:56px; }
.se__actions { display:flex;gap:var(--space-2);margin-top:var(--space-2); }
.se__reject,.se__approve { min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md); }
.se__reject { border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600); }
.se__approve { border:none;background:var(--teacher-600);color:#fff; }
.se__reject::after,.se__approve::after { border:none; }
</style>
