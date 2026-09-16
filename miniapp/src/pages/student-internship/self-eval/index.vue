<template>
  <view class="page-wrap se">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack" v-if="loaded">
        <view v-if="receipt" class="card se__receipt">
          <view class="row-between"><text class="t-bold">✓ 自评已提交</text><text>v{{ receipt.version }}</text></view>
          <text>鉴定 #{{ receipt.id }} · {{ receipt.statusLabel }}</text><text>{{ receipt.nextStep }}</text>
        </view>
        <view class="card se__head">
          <view class="row-between">
            <text class="card-title">实习自评 / 鉴定</text>
            <MobileStatusTag v-if="evalData" :label="evalData.reviewStatusLabel || evalData.submitStatusLabel" :type="statusTone" />
          </view>
          <text class="se__hint">提交后进入指导意见和学校审核；审核中不可修改，退回后可按版本重交。</text>
          <text v-if="evalData?.version" class="se__version">记录版本 {{ evalData.version }}</text>
        </view>
        <view v-if="dashboard" class="card se__result">
          <view class="row-between">
            <view><text class="se__eyebrow">结项与正式结果</text><text class="card-title">{{ resultTitle }}</text></view>
            <MobileStatusTag :label="resultStatusLabel" :type="dashboard.archive ? 'success' : dashboard.score ? 'info' : 'warning'" />
          </view>
          <template v-if="dashboard.score">
            <view class="se__score-line"><text>{{ dashboard.score.totalScore ?? '—' }}</text><text>分 · {{ dashboard.score.isPass ? '合格' : '不合格' }}</text></view>
            <view class="se__score-grid">
              <text>打卡 {{ dashboard.score.checkinScore ?? '—' }}</text><text>周报 {{ dashboard.score.weeklyScore ?? '—' }}</text>
              <text>月报/总结 {{ dashboard.score.monthlyScore ?? '—' }}</text><text>企业 {{ dashboard.score.enterpriseScore ?? '—' }}</text>
              <text>指导教师 {{ dashboard.score.schoolScore ?? '—' }}</text>
            </view>
            <text class="se__hint">正式成绩发布于 {{ formatTime(dashboard.score.publishedAt) }}</text>
          </template>
          <text v-else class="se__hint">完成自评、企业评价和指导教师评价后，由学校核算、复核并发布正式成绩。</text>
          <view v-if="appealData?.hasAppeal" class="se__appeal-state">
            <text>最近申诉 · {{ appealData.statusLabel || appealData.status }}</text>
            <text>{{ appealNextStep }}</text>
          </view>
          <view v-if="canAppeal" class="se__appeal-form">
            <textarea v-model="appealReason" class="se__textarea" maxlength="500" placeholder="对正式成绩有异议时填写理由（至少5字）" />
            <button class="btn btn-ghost" :disabled="appealSubmitting" @click="submitAppeal">{{ appealSubmitting ? '提交中…' : '提交成绩申诉' }}</button>
          </view>
          <view v-if="dashboard.archive" class="se__archive">
            <text>实习档案已归档 · 完整度 {{ dashboard.archive.completeness }}%</text>
            <text>{{ formatTime(dashboard.archive.archivedAt) }} 完成归档，后续去向进入就业中心继续办理。</text>
          </view>
          <button class="btn btn-primary" @click="openEmployment">查看就业衔接</button>
        </view>
        <MobileInlineAlert v-if="historyMode" type="info" title="历史实习记录" description="历史批次仅可查看鉴定，不可重新提交。" />
        <MobileInlineAlert v-else-if="conflictText" type="warning" title="版本已变化，草稿已保留" :description="conflictText" />
        <MobileInlineAlert v-else-if="evalData?.reviewStatus === 'RETURNED'" type="warning" title="鉴定已退回" :description="evalData.reviewComment || '请按审核意见修改后重新提交。修改正文后旧指导意见将失效。'" />
        <MobileInlineAlert v-else-if="pendingReview" type="info" title="鉴定正在审核" description="当前版本已提交，不能继续覆盖；如需修改，请等待学校退回。" />
        <view class="card se__form">
          <view class="se__field">
            <text class="se__label">实习总结 <text class="se__req">*</text></text>
            <textarea v-model="form.selfSummary" class="se__textarea" :disabled="readonly" maxlength="2000" placeholder="请完整总结实习工作、能力提升和职业认识（至少20字）" />
          </view>
          <view class="se__field">
            <text class="se__label">主要收获</text>
            <textarea v-model="form.selfHarvest" class="se__textarea" :disabled="readonly" maxlength="1000" placeholder="专业技能、企业流程、团队协作等" />
          </view>
          <view class="se__field">
            <text class="se__label">存在问题</text>
            <textarea v-model="form.selfProblem" class="se__textarea" :disabled="readonly" maxlength="1000" placeholder="不足与后续改进计划" />
          </view>
          <view class="se__field">
            <text class="se__label">对企业评分（1-5）</text>
            <picker mode="selector" :disabled="readonly" :range="ratingLabels" @change="onEntRate">
              <view class="se__picker">{{ form.enterpriseRating ? form.enterpriseRating + ' 分' : '请选择' }}</view>
            </picker>
          </view>
          <view class="se__field">
            <text class="se__label">对企业评价</text>
            <textarea v-model="form.enterpriseFeedback" class="se__textarea" :disabled="readonly" maxlength="500" placeholder="对实习企业的真实评价" />
          </view>
          <view class="se__field">
            <text class="se__label">对岗位评分（1-5）</text>
            <picker mode="selector" :disabled="readonly" :range="ratingLabels" @change="onPosRate">
              <view class="se__picker">{{ form.positionRating ? form.positionRating + ' 分' : '请选择' }}</view>
            </picker>
          </view>
          <view class="se__field">
            <text class="se__label">对岗位评价</text>
            <textarea v-model="form.positionFeedback" class="se__textarea" :disabled="readonly" maxlength="500" placeholder="对实习岗位的真实评价" />
          </view>
        </view>
        <view v-if="evalData?.advisorOpinion" class="card">
          <text class="se__label">指导教师意见</text>
          <text class="se__readonly">{{ evalData.advisorOpinion }}</text>
        </view>
        <view v-if="evalData?.reviewedByName" class="card">
          <text class="se__label">学校审核</text>
          <text class="se__readonly">{{ evalData.reviewedByName }} · {{ evalData.reviewStatusLabel }}{{ evalData.reviewComment ? `\n${evalData.reviewComment}` : '' }}</text>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="loaded && !readonly">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : (evalData ? '修改并重新提交' : '提交自评') }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast, go } from '@/utils/nav'

export default {
  data() {
    return {
      pageState: 'loading', loaded: false, submitting: false,
      evalData: null, dashboard: null, appealData: null, historyMode: false,
      appealReason: '', appealSubmitting: false,
      receipt: null, conflictText: '',
      form: { selfSummary: '', selfHarvest: '', selfProblem: '', enterpriseRating: null, enterpriseFeedback: '', positionRating: null, positionFeedback: '' },
      ratingLabels: ['1 分', '2 分', '3 分', '4 分', '5 分']
    }
  },
  computed: {
    pendingReview() { return this.evalData?.submitStatus === 'SUBMITTED' && this.evalData?.reviewStatus === 'PENDING' },
    readonly() { return this.historyMode || this.evalData?.reviewStatus === 'APPROVED' || this.pendingReview },
    canAppeal() {
      return !!this.dashboard?.score && !this.dashboard?.archive &&
        !['PENDING', 'APPROVED_RECALCULATING'].includes(this.appealData?.status)
    },
    resultTitle() {
      if (this.dashboard?.archive) return '实习已归档'
      if (this.dashboard?.score) return '正式成绩已发布'
      return '结项材料办理中'
    },
    resultStatusLabel() {
      if (this.dashboard?.archive) return '已归档'
      if (this.dashboard?.score) return '成绩已发布'
      return '待结项'
    },
    appealNextStep() {
      const status = this.appealData?.status
      if (status === 'PENDING') return '学校正在核对本次申诉。'
      if (status === 'APPROVED_RECALCULATING') return '原成绩已撤回，等待重新核算、复核和发布。'
      if (status === 'CLOSED') return '新的正式成绩已发布，请核对结果。'
      if (status === 'REJECTED') return this.appealData?.handleComment || '本次申诉已办结，请查看处理意见。'
      return ''
    },
    statusTone() {
      if (this.evalData?.reviewStatus === 'APPROVED') return 'success'
      if (this.evalData?.reviewStatus === 'RETURNED') return 'danger'
      return 'warning'
    }
  },
  onLoad(options = {}) { this.requestedBatchId = String(options.batchId || ''); this.load() },
  methods: {
    onEntRate(e) { if (!this.readonly) this.form.enterpriseRating = Number(e.detail.value) + 1 },
    onPosRate(e) { if (!this.readonly) this.form.positionRating = Number(e.detail.value) + 1 },
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' },
    openEmployment() { go('/pages/student/employment/index') },
    async load() {
      this.pageState = 'loading'
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        const [data, appeal] = await Promise.all([
          studentApi.getInternshipSelfEval(dashboard?.batchId, dashboard?.recordId),
          studentApi.getInternshipScoreAppeal(dashboard?.batchId, dashboard?.recordId)
        ])
        this.dashboard = dashboard
        this.evalData = data
        this.appealData = appeal
        this.historyMode = !!dashboard?.historyMode
        if (data) {
          this.form = {
            selfSummary: data.selfSummary || '', selfHarvest: data.selfHarvest || '',
            selfProblem: data.selfProblem || '', enterpriseRating: data.enterpriseRating || null,
            enterpriseFeedback: data.enterpriseFeedback || '', positionRating: data.positionRating || null,
            positionFeedback: data.positionFeedback || ''
          }
        }
        this.loaded = true
        this.pageState = 'ready'
      } catch (e) { this.pageState = 'error' }
    },
    async submit() {
      if (this.submitting || this.readonly) return
      if (String(this.form.selfSummary || '').trim().length < 20) return toast('实习总结至少20个字')
      this.submitting = true
      try {
        const result = await studentApi.submitInternshipSelfEval({
          ...this.form,
          batchId: this.dashboard?.batchId,
          internshipId: this.dashboard?.recordId,
          ...(this.evalData?.id ? { expectedVersion: this.evalData.version } : {})
        })
        this.receipt = { id: result?.id || '', version: result?.version,
          statusLabel: result?.reviewStatusLabel || result?.reviewStatus || '待审核',
          nextStep: '等待导师填写评价并由学校审核' }
        this.conflictText = ''
        toast('自评已提交，等待指导意见和学校审核')
        await this.load()
      } catch (e) {
        if (String(e?.code || '').includes('409') || e?.code === 'DATA_CONFLICT') {
          this.conflictText = '服务端鉴定版本已更新。当前输入没有丢失；请核对后手动返回并刷新，再决定是否重新提交。系统不会自动重放。'
          toast('版本已变化，当前草稿已保留')
        } else toast(e?.message || '提交失败，请稍后重试')
      } finally { this.submitting = false }
    },
    async submitAppeal() {
      if (this.appealSubmitting || !this.canAppeal) return
      const reason = String(this.appealReason || '').trim()
      if (reason.length < 5) return toast('申诉理由至少5个字')
      this.appealSubmitting = true
      try {
        await studentApi.submitInternshipScoreAppeal({
          batchId: this.dashboard.batchId,
          internshipId: this.dashboard.recordId,
          reason
        })
        this.appealReason = ''
        this.appealData = await studentApi.getInternshipScoreAppeal(
          this.dashboard.batchId, this.dashboard.recordId)
        toast('成绩申诉已提交，等待学校处理')
      } catch (e) {
        toast(e?.message || '申诉提交失败，请稍后重试')
      } finally { this.appealSubmitting = false }
    }
  }
}
</script>

<style scoped>
.se__receipt{display:flex;flex-direction:column;gap:5px;padding:var(--space-3);border-color:var(--success-300,#86efac);background:var(--success-50,#f0fdf4);font-size:var(--font-size-xs);color:var(--text-secondary)}
.se__hint,.se__version { display:block;margin-top:6px;font-size:var(--font-size-sm);color:var(--text-secondary); }
.se__version { font-size:var(--font-size-xs);color:var(--text-tertiary); }
.se__field { margin-bottom:14px; }
.se__label { display:block;font-size:var(--font-size-sm);font-weight:var(--font-weight-medium);margin-bottom:6px; }
.se__req { color:var(--danger-600); }
.se__textarea { width:100%;min-height:90px;padding:10px;box-sizing:border-box;border:1px solid var(--border-base);border-radius:var(--radius-md);font-size:var(--font-size-sm); }
.se__picker { border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;color:var(--text-secondary); }
.se__readonly { display:block;margin-top:8px;font-size:var(--font-size-sm);line-height:1.6;white-space:pre-wrap; }
.se__result{display:flex;flex-direction:column;gap:12px;border-top:3px solid var(--brand-primary)}
.se__eyebrow{display:block;margin-bottom:4px;font-size:10px;color:var(--text-tertiary)}
.se__score-line{display:flex;align-items:baseline;gap:8px}.se__score-line text:first-child{font-size:36px;font-weight:700;color:var(--brand-primary)}.se__score-line text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}
.se__score-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.se__score-grid text{padding:8px 10px;border-radius:var(--radius-md);background:var(--gray-50);font-size:var(--font-size-xs);color:var(--text-secondary)}
.se__appeal-state,.se__archive{display:flex;flex-direction:column;gap:4px;padding:10px 12px;border-radius:var(--radius-md);background:var(--warning-50,#fffbeb);font-size:var(--font-size-xs);line-height:1.5;color:var(--warning-800,#92400e)}
.se__archive{background:var(--success-50,#f0fdf4);color:var(--success-800,#166534)}.se__appeal-form{display:flex;flex-direction:column;gap:8px}.se__appeal-form .se__textarea{min-height:72px}
</style>
