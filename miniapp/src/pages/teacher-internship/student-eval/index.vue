<template>
  <view class="internship-surface mobile-page mobile-teacher page-wrap">
    <MobileNavBar variant="teacher" title="学生实习鉴定" show-back />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack">
        <view v-if="batches.length > 1" class="card se__batch">
          <view class="se__batch-copy">
            <text class="se__eyebrow">当前鉴定批次</text>
            <text class="se__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          </view>
          <picker class="mobile-picker se__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="acting" @change="onBatch">
            <view class="se__pick">切换批次 <text>▾</text></view>
          </picker>
        </view>

        <button v-if="list.length" class="mobile-control btn btn-ghost" :aria-expanded="queueSummaryOpen" @click="queueSummaryOpen=!queueSummaryOpen">{{ queueSummaryOpen ? '收起学生鉴定统计' : '查看学生鉴定统计' }}</button>
        <view v-if="list.length && queueSummaryOpen" class="card se__summary">
          <view class="se__summary-main">
            <text class="se__summary-label">本批次鉴定记录</text>
            <view class="se__summary-value"><text>{{ list.length }}</text><text>份</text></view>
            <text class="se__summary-note">{{ summaryConclusion }}</text>
          </view>
          <view class="se__summary-metrics">
            <view class="se__metric"><text>{{ pendingAdvisorCount }}</text><text>待指导意见</text></view>
            <view class="se__metric"><text>{{ pendingReviewCount }}</text><text>待学校审核</text></view>
            <view class="se__metric is-warning"><text>{{ returnedCount }}</text><text>已退回</text></view>
          </view>
        </view>

        <MobileInlineAlert v-if="list.some(item => item.reviewStatus !== 'APPROVED')" type="info" :description="roleHint" />
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次" description="当前身份的数据范围内没有可查看批次。" />
        <MobileGlobalState v-else-if="!list.length" state="empty" title="当前批次没有学生鉴定" description="学生提交实习自评后会出现在这里。" />

        <view v-for="item in list" :key="item.id" class="card se" :class="{ 'is-expanded': expanded === item.id }">
          <view class="row-between se__head" @click="toggle(item)">
            <view class="flex-1 se__identity">
              <text class="t-md t-bold">{{ item.studentName || '—' }}</text>
              <text class="se__sub">{{ item.studentNo || '' }} · {{ item.advisorName || '导师待分配' }}</text>
            </view>
            <view class="se__head-right">
              <view class="se__tags">
                <MobileStatusTag :label="item.reviewStatusLabel" :type="reviewTone(item.reviewStatus)" />
              </view>
              <text class="se__chevron">{{ expanded === item.id ? '收起 ▲' : '查看详情 ▼' }}</text>
            </view>
          </view>

          <view class="se__brief">
            <view><text>自评提交</text><text>{{ item.submitStatusLabel || '—' }}</text></view>
            <view><text>指导意见</text><text>{{ item.hasAdvisorOpinion ? '已填写' : '未填写' }}</text></view>
            <view><text>学校审核</text><text>{{ item.reviewStatusLabel || '—' }}</text></view>
          </view>

          <view v-if="item.reviewStatus !== 'APPROVED'" class="se__next" :class="{ 'is-warning': item.reviewStatus === 'RETURNED' }">
            <text class="se__next-label">下一步</text>
            <text class="se__next-text">{{ nextStepText(item) }}</text>
          </view>

          <template v-if="expanded === item.id">
            <view v-if="!details[item.id]" class="se__loading"><text class="t-sm t-tertiary">正在加载鉴定详情…</text></view>
            <template v-else>
              <view class="se__block se__block--student">
                <text class="se__block-title">学生自评</text>
                <text class="se__block-label">实习总结</text>
                <text class="se__block-text">{{ details[item.id].selfSummary || '（未填写）' }}</text>
                <template v-if="details[item.id].selfHarvest">
                  <text class="se__block-label">主要收获</text>
                  <text class="se__block-text">{{ details[item.id].selfHarvest }}</text>
                </template>
                <template v-if="details[item.id].selfProblem">
                  <text class="se__block-label">存在问题</text>
                  <text class="se__block-text">{{ details[item.id].selfProblem }}</text>
                </template>
              </view>
              <view v-if="conflicts[item.id]" class="se__block">
                <MobileInlineAlert type="warning" title="鉴定已变化，原意见及版本已保留" :description="conflicts[item.id].error" />
                <button class="mobile-control btn btn-ghost" :disabled="acting" @click="rereadEvaluation(item)">读取最新鉴定</button>
                <template v-if="conflicts[item.id].latest">
                  <text>最新第{{ conflicts[item.id].latest.version }}版：{{ conflicts[item.id].latest.selfSummary }}</text>
                  <text>{{ conflicts[item.id].latest.advisorOpinion }} {{ conflicts[item.id].latest.reviewComment }}</text>
                  <button class="mobile-control btn btn-ghost" :disabled="acting" @click="adoptEvaluation(item)">已核对最新鉴定，保留意见继续</button>
                </template>
              </view>

              <template v-if="canAdvisor && item.reviewStatus === 'PENDING'">
                <view class="se__editor">
                  <view class="se__editor-head">
                    <view>
                      <text class="se__editor-title">填写指导教师意见</text>
                      <text class="se__editor-hint">请结合学生自评、过程表现和企业反馈填写，至少5个字。</text>
                    </view>
                  </view>
                  <view class="se__field">
                    <text class="se__field-label">指导教师意见 <text class="se__required">*</text></text>
                    <textarea class="mobile-textarea se__textarea" v-model="drafts[item.id].advisorOpinion" maxlength="1000" placeholder="说明学生表现、问题和改进建议" />
                    <text class="se__counter">{{ (drafts[item.id].advisorOpinion || '').length }}/1000</text>
                  </view>
                  <view class="se__field">
                    <text class="se__field-label">企业导师反馈</text>
                    <textarea class="mobile-textarea se__textarea se__textarea--sm" v-model="drafts[item.id].mentorOpinion" maxlength="1000" placeholder="根据企业原始反馈如实填写（可选）" />
                  </view>
                  <button class="mobile-control btn btn-ghost se__save" :disabled="acting" @click="saveOpinion(item)">保存指导意见</button>
                </view>
              </template>
              <view v-else-if="details[item.id].advisorOpinion" class="se__block se__block--advisor">
                <text class="se__block-title">指导教师意见</text>
                <text class="se__block-text">{{ details[item.id].advisorOpinion }}</text>
                <template v-if="details[item.id].mentorOpinion">
                  <text class="se__block-label">企业导师反馈</text>
                  <text class="se__block-text">{{ details[item.id].mentorOpinion }}</text>
                </template>
              </view>

              <view v-if="canReview && item.submitStatus === 'SUBMITTED' && item.reviewStatus === 'PENDING'" class="se__review-panel">
                <text class="se__review-title">学校审核</text>
                <text class="se__review-hint">确认学生自评与指导意见完整后再通过；退回应写明具体修改内容。</text>
                <view class="se__actions">
                  <button class="mobile-control se__reject flex-1" :disabled="acting" @click="review(item, 'RETURN')">学校退回</button>
                  <button class="mobile-control se__approve flex-1" :disabled="acting || !details[item.id].advisorOpinion" @click="review(item, 'APPROVE')">学校审核通过</button>
                </view>
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
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

export default {
  data() {
    return { requestedBatchId: '', queueSummaryOpen:false,
      list: [], state: 'loading', error: '', expanded: '', details: {}, drafts: {}, acting: false,
      reviewDrafts: {}, conflicts: {}, loadSeq: 0, generation: currentSessionGeneration(), hidden: false,
      batches: [], batchId: '', batchIndex: 0, page: 1, hasMore: false, loadingMore: false
    }
  },
  computed: {
    context() { return useInternshipContextStore() },
    canAdvisor() { return this.context.can('internship.eval.advisor.manage') },
    canReview() { return this.context.can('internship.eval.self.review') },
    batchLabels() { return this.batches.map((x) => `${x.name} · ${x.studentCount}人`) },
    pendingAdvisorCount() { return this.list.filter((item) => item.submitStatus === 'SUBMITTED' && item.reviewStatus === 'PENDING' && !item.hasAdvisorOpinion).length },
    pendingReviewCount() { return this.list.filter((item) => item.submitStatus === 'SUBMITTED' && item.reviewStatus === 'PENDING' && item.hasAdvisorOpinion).length },
    returnedCount() { return this.list.filter((item) => item.reviewStatus === 'RETURNED').length },
    summaryConclusion() {
      if (!this.list.length) return '当前没有需要办理的学生鉴定。'
      if (this.pendingAdvisorCount) return `优先完成 ${this.pendingAdvisorCount} 份指导教师意见。`
      if (this.pendingReviewCount) return `${this.pendingReviewCount} 份已具备学校审核条件。`
      if (this.returnedCount) return `有 ${this.returnedCount} 份已退回，关注学生重新提交。`
      return '当前记录已处理或正在等待学生提交。'
    },
    roleHint() {
      if (this.canAdvisor && this.canReview) return '先保存指导意见，再办理学校审核。'
      if (this.canReview) return '核对自评和指导意见后审核；指导意见由指导教师填写。'
      if (this.canAdvisor) return '填写指导意见后，交学校审核。'
      return '当前仅可查看鉴定。'
    }
  },
  onLoad(query={}) { this.requestedBatchId=String(query.batchId||'');this.load() },
  onHide() { this.hidden = true; this.loadSeq++; this.acting = false },
  onUnload() { this.hidden = true; this.loadSeq++ },
  onShow() { this.hidden = false; if (this.generation !== currentSessionGeneration()) this.load() },
  onReachBottom() { this.loadMore() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    reviewTone(status) { return status === 'APPROVED' ? 'success' : status === 'RETURNED' ? 'danger' : 'warning' },
    nextStepText(item) {
      if (item.reviewStatus === 'RETURNED') return '等待学生按学校意见修改并重新提交。'
      if (item.submitStatus !== 'SUBMITTED') return '等待学生完成并提交实习自评。'
      if (!item.hasAdvisorOpinion) return this.canAdvisor ? '展开详情并填写指导教师意见。' : '等待指导教师填写意见。'
      if (item.reviewStatus === 'PENDING') return this.canReview ? '展开详情核对材料并完成学校审核。' : '等待学校或学院授权角色审核。'
      return '鉴定已完成审核，可查看最终意见。'
    },
    async load(done) {
      const sequence = ++this.loadSeq, generation = currentSessionGeneration(), previousBatch = this.batchId
      if (this.generation !== generation) { this.drafts = {}; this.reviewDrafts = {}; this.conflicts = {}; this.generation = generation }
      this.state = 'loading'; this.error = ''
      this.page = 1
      this.hasMore = false
      try {
        this.context.restore()
        await this.context.load(true)
        if (this.hidden || sequence !== this.loadSeq || generation !== currentSessionGeneration()) return
        if(this.requestedBatchId){if(!this.context.selectBatch(this.requestedBatchId))throw {httpStatus:403,message:'当前批次不在授权范围'};this.requestedBatchId=''}
        this.batches = this.context.batches || []
        this.batchId = this.context.selectedBatchId || ''
        if (previousBatch !== this.batchId) { this.drafts = {}; this.reviewDrafts = {}; this.conflicts = {} }
        this.batchIndex = Math.max(0, this.batches.findIndex((x) => String(x.id) === String(this.batchId)))
        if (!this.batchId) this.list = []
        else {
          const data = await teacherInternshipStudentEvals(this.batchId, 1, 20)
          if (this.hidden || sequence !== this.loadSeq || generation !== currentSessionGeneration()) return
          this.list = data?.items || data?.list || []
          this.hasMore = !!data?.hasMore
        }
        this.expanded = ''
        this.details = {}
        this.state = 'ready'
      } catch (e) { if (!this.hidden && sequence === this.loadSeq && generation === currentSessionGeneration()) { const error = normalizeError(e); this.state = error.pageState || 'error'; this.error = error.text } }
      finally { if (done) done() }
    },
    async onBatch(e) {
      if (this.acting) return
      this.drafts = {}; this.reviewDrafts = {}; this.conflicts = {}
      this.batchIndex = Number(e.detail.value)
      this.context.selectBatch(this.batches[this.batchIndex]?.id)
      this.list = []
      await this.load()
    },
    async loadMore() {
      if (!this.batchId || !this.hasMore || this.loadingMore || this.state !== 'ready') return
      const selectedBatch = this.batchId
      this.loadingMore = true
      try {
        const nextPage = this.page + 1
        const data = await teacherInternshipStudentEvals(selectedBatch, nextPage, 20)
        if (selectedBatch !== this.batchId) return
        this.list = [...this.list, ...(data?.items || [])]
        this.page = nextPage
        this.hasMore = !!data?.hasMore
      } catch (e) { if (selectedBatch === this.batchId) { const error = normalizeError(e); this.state = error.pageState || 'error'; this.error = error.text } }
      finally { this.loadingMore = false }
    },
    async toggle(item) {
      if (this.expanded === item.id) { this.expanded = ''; return }
      this.expanded = item.id
      if (this.details[item.id]) return
      const generation = currentSessionGeneration(), sequence = this.loadSeq, batchId = this.batchId
      try {
        const detail = await teacherInternshipStudentEvalDetail(item.id)
        if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSeq || batchId !== this.batchId) return
        if (String(detail?.id) !== String(item.id) || String(detail.batchId) !== String(batchId)) throw new Error('鉴定原单不一致')
        this.details = { ...this.details, [item.id]: detail }
        this.drafts = { ...this.drafts, [item.id]: {
          advisorOpinion: detail.advisorOpinion || '', mentorOpinion: detail.mentorOpinion || '', version: detail.version, ...this.drafts[item.id]
        } }
      } catch (e) { toast(e?.message || '加载详情失败'); this.expanded = '' }
    },
    async refreshItem(item) {
      const generation = currentSessionGeneration(), sequence = this.loadSeq, batchId = this.batchId
      const detail = await teacherInternshipStudentEvalDetail(item.id)
      if (this.hidden || generation !== currentSessionGeneration() || sequence !== this.loadSeq || batchId !== this.batchId) return detail
      if (String(detail?.id) !== String(item.id) || String(detail.batchId) !== String(batchId)) throw new Error('鉴定原单不一致')
      this.details = { ...this.details, [item.id]: detail }
      const index = this.list.findIndex((x) => x.id === item.id)
      if (index >= 0) this.list.splice(index, 1, { ...this.list[index], ...detail })
      return detail
    },
    async saveOpinion(item) {
      if (this.acting || !this.canAdvisor || this.state !== 'ready' || this.conflicts[item.id]) return
      const draft = this.drafts[item.id] || {}
      if (String(draft.advisorOpinion || '').trim().length < 5) return toast('指导教师意见至少5个字')
      this.acting = true
      const generation = currentSessionGeneration(), batchId = this.batchId, sequence = this.loadSeq
      const current = () => !this.hidden && sequence === this.loadSeq && generation === currentSessionGeneration() && batchId === this.batchId
      try {
        const detail = this.details[item.id]
        await teacherInternshipStudentEvalAdvisorComment(item.id, this.batchId, {
          advisorOpinion: String(draft.advisorOpinion).trim(),
          mentorOpinion: String(draft.mentorOpinion || '').trim(),
          expectedVersion: draft.version ?? detail.version
        })
        if (!current()) return
        toast('指导意见已保存')
        const saved = await this.refreshItem(item)
        if (current()) draft.version = saved.version
      } catch (e) {
        if (!current()) return
        if (normalizeError(e).kind === 'conflict') {
          this.conflicts[item.id] = { version: draft.version ?? this.details[item.id].version, latest: null, error: '原意见已保留，请核对最新鉴定后明确采用版本。' }
          await this.rereadEvaluation(item)
        } else toast(e?.message || '保存失败')
      } finally { if (current()) this.acting = false }
    },
    review(item, action) {
      if (this.acting || !this.canReview || this.state !== 'ready' || this.conflicts[item.id]) return
      const version = this.details[item.id]?.version, sequence = this.loadSeq, generation = currentSessionGeneration(), batchId = this.batchId
      const current = () => !this.hidden && sequence === this.loadSeq && generation === currentSessionGeneration() && batchId === this.batchId
      if (!Number.isInteger(version)) return toast('请先读取鉴定正文')
      const returned = action === 'RETURN'
      uni.showModal({
        title: returned ? '学校退回鉴定' : '学校审核通过',
        editable: true,
        placeholderText: returned ? '请填写退回原因（至少5字）' : '可填写审核意见',
        content: this.reviewDrafts[item.id]?.action === action ? this.reviewDrafts[item.id].comment : '',
        success: async (result) => {
          if (!result.confirm || this.acting || !current()) return
          const comment = String(result.content || '').trim()
          if (returned && comment.length < 5) return toast('退回原因至少5个字')
          this.reviewDrafts[item.id] = { action, comment, version }
          this.acting = true
          try {
            const detail = this.details[item.id]
            await teacherInternshipStudentEvalReview(item.id, this.batchId, {
              action, comment, expectedVersion: version
            })
            if (!current()) return
            delete this.reviewDrafts[item.id]; delete this.drafts[item.id]
            toast(returned ? '已退回学生修改' : '学校审核已通过')
            this.acting = false
            await this.load()
          } catch (e) {
            if (!current()) return
            if (normalizeError(e).kind === 'conflict') {
              this.conflicts[item.id] = { version, latest: null, error: '学校审核意见已保留，请核对最新鉴定后明确采用版本。' }
              await this.rereadEvaluation(item)
            } else toast(e?.message || '审核失败')
          } finally { if (current()) this.acting = false }
        }
      })
    },
    async rereadEvaluation(item) {
      const c = this.conflicts[item.id], sequence = this.loadSeq, generation = currentSessionGeneration(), batchId = this.batchId
      if (!c || c.reading) return
      const current = () => !this.hidden && sequence === this.loadSeq && generation === currentSessionGeneration() && batchId === this.batchId && c === this.conflicts[item.id]
      c.reading = true; c.latest = null
      try {
        const latest = await teacherInternshipStudentEvalDetail(item.id)
        if (!current()) return
        if (String(latest?.id) !== String(item.id) || String(latest.batchId) !== String(batchId) || !Number.isInteger(latest.version)) throw new Error('鉴定原单不一致，请重新读取')
        c.latest = latest; c.error = '请核对最新正文、指导意见及学校审核状态，明确采用后才可继续。'
      } catch (e) { if (current()) c.error = e?.message || '读取失败，原意见已保留' }
      finally { c.reading = false }
    },
    adoptEvaluation(item) {
      const c = this.conflicts[item.id], latest = c?.latest
      if (!latest || c.reading || this.acting || this.hidden || this.generation !== currentSessionGeneration()) return
      if (latest.submitStatus !== 'SUBMITTED' || latest.reviewStatus !== 'PENDING') { c.error = '原鉴定已处理或等待学生重交，意见保留，不能覆盖'; return }
      this.details[item.id] = latest
      const row = this.list.find(row => String(row.id) === String(item.id)); if (row) Object.assign(row, latest)
      if (this.drafts[item.id]) this.drafts[item.id].version = latest.version
      if (this.reviewDrafts[item.id]) this.reviewDrafts[item.id].version = latest.version
      delete this.conflicts[item.id]
    }
  }
}
</script>

<style scoped>
.se__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.se__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.se__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.se__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.se__picker{flex-shrink:0}.se__pick{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.se__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.se__summary-main{flex:1;min-width:0}.se__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.se__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.se__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.se__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.se__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.se__summary-metrics{width:50%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.se__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 3px;border-left:1px solid var(--border-light);text-align:center}.se__metric:first-child{border-left:0}.se__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.se__metric.is-warning text:first-child{color:var(--warning-700)}.se__metric text:last-child{font-size:10px;line-height:1.25;color:var(--text-tertiary)}.se{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.se.is-expanded{border-color:var(--teacher-200,#bfdbfe)}.se__head{align-items:flex-start}.se__identity{min-width:0}.se__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px;word-break:break-word}.se__head-right{flex-shrink:0;display:flex;flex-direction:column;align-items:flex-end;gap:6px}.se__tags{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:5px}.se__chevron{font-size:10px;color:var(--teacher-700)}.se__brief{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;padding:var(--space-2);background:var(--gray-50);border-radius:var(--radius-md)}.se__brief>view{min-width:0;display:flex;flex-direction:column;gap:3px}.se__brief text:first-child{font-size:10px;color:var(--text-tertiary)}.se__brief text:last-child{font-size:var(--font-size-xs);font-weight:600;color:var(--text-primary);word-break:break-word}.se__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.se__next.is-warning{background:var(--warning-50,#fff7ed)}.se__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.se__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.se__loading{padding:var(--space-4) 0;text-align:center}.se__block{border-radius:var(--radius-md);padding:var(--space-3);display:flex;flex-direction:column;gap:6px}.se__block--student{background:var(--gray-50)}.se__block--advisor{background:var(--success-50)}.se__block-title{font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.se__block-label{margin-top:4px;font-size:10px;color:var(--text-tertiary)}.se__block-text{font-size:var(--font-size-sm);color:var(--text-primary);line-height:1.65;white-space:pre-wrap;word-break:break-word}.se__editor{padding:var(--space-3);border:1px solid var(--teacher-200,#bfdbfe);border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff);display:flex;flex-direction:column;gap:var(--space-3)}.se__editor-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.se__editor-hint{display:block;margin-top:3px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.se__field{display:flex;flex-direction:column;gap:6px}.se__field-label{font-size:var(--font-size-sm);color:var(--text-secondary)}.se__required{color:var(--danger-600)}.se__textarea{width:100%;min-height:86px;box-sizing:border-box;font-size:var(--font-size-base);color:var(--text-primary);line-height:1.6;background:var(--bg-card);border:1px solid var(--border-light);border-radius:var(--radius-md);padding:var(--space-2)}.se__textarea--sm{min-height:64px}.se__counter{align-self:flex-end;font-size:10px;color:var(--text-tertiary)}.se__save{align-self:flex-end}.se__review-panel{padding:var(--space-3);border:1px solid var(--border-light);border-radius:var(--radius-md)}.se__review-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.se__review-hint{display:block;margin-top:3px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.se__actions{display:flex;gap:var(--space-2);margin-top:var(--space-3)}.se__reject,.se__approve{min-height:var(--touch-target-min);border-radius:var(--radius-md);font-size:var(--font-size-md)}.se__reject{border:1px solid var(--danger-500);background:var(--bg-card);color:var(--danger-600)}.se__approve{border:none;background:var(--teacher-600);color:#fff}.se__reject::after,.se__approve::after{border:none}.se__reject[disabled],.se__approve[disabled]{opacity:.5}@media(max-width:360px){.se__summary{flex-direction:column}.se__summary-metrics{width:100%}.se__brief{grid-template-columns:1fr}.se__batch{align-items:flex-start}}
.se__eyebrow,.se__summary-label,.se__summary-note,.se__metric text:last-child,.se__sub,.se__chevron,.se__brief text:first-child,.se__brief text:last-child,.se__next-label,.se__next-text,.se__block-label,.se__block-text,.se__editor-hint,.se__field-label,.se__counter,.se__review-hint{font-size:var(--font-size-base)}.se__pick{display:flex;align-items:center;min-height:44px;font-size:var(--font-size-base)}.se__save{min-height:44px;font-size:var(--font-size-md)}
@media(max-width:430px){.se__summary{flex-direction:column}.se__summary-metrics{width:100%}}
</style>
