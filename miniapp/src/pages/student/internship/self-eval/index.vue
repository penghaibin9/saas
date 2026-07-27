<template>
  <view class="page-wrap se">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack" v-if="loaded">
        <view class="card se__head">
          <view class="row-between">
            <text class="card-title">实习自评 / 鉴定</text>
            <MobileStatusTag v-if="evalData" :label="evalData.reviewStatusLabel || evalData.submitStatusLabel" :type="statusTone" />
          </view>
          <text class="se__hint">提交后进入指导意见和学校审核；审核中不可修改，退回后可按版本重交。</text>
          <text v-if="evalData?.version" class="se__version">记录版本 {{ evalData.version }}</text>
        </view>
        <MobileInlineAlert v-if="historyMode" type="info" title="历史实习记录" description="历史批次仅可查看鉴定，不可重新提交。" />
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
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      pageState: 'loading', loaded: false, submitting: false,
      evalData: null, historyMode: false,
      form: { selfSummary: '', selfHarvest: '', selfProblem: '', enterpriseRating: null, enterpriseFeedback: '', positionRating: null, positionFeedback: '' },
      ratingLabels: ['1 分', '2 分', '3 分', '4 分', '5 分']
    }
  },
  computed: {
    pendingReview() { return this.evalData?.submitStatus === 'SUBMITTED' && this.evalData?.reviewStatus === 'PENDING' },
    readonly() { return this.historyMode || this.evalData?.reviewStatus === 'APPROVED' || this.pendingReview },
    statusTone() {
      if (this.evalData?.reviewStatus === 'APPROVED') return 'success'
      if (this.evalData?.reviewStatus === 'RETURNED') return 'danger'
      return 'warning'
    }
  },
  onLoad() { this.load() },
  methods: {
    onEntRate(e) { if (!this.readonly) this.form.enterpriseRating = Number(e.detail.value) + 1 },
    onPosRate(e) { if (!this.readonly) this.form.positionRating = Number(e.detail.value) + 1 },
    async load() {
      this.pageState = 'loading'
      try {
        const [data, dashboard] = await Promise.all([
          studentApi.getInternshipSelfEval(), studentApi.getInternship()
        ])
        this.evalData = data
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
        await studentApi.submitInternshipSelfEval({
          ...this.form,
          ...(this.evalData?.id ? { expectedVersion: this.evalData.version } : {})
        })
        toast('自评已提交，等待指导意见和学校审核')
        await this.load()
      } catch (e) {
        if (String(e?.code || '').includes('409') || e?.code === 'DATA_CONFLICT') {
          toast('鉴定状态已变化，正在刷新')
          await this.load()
        } else toast(e?.message || '提交失败，请稍后重试')
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
.se__hint,.se__version { display:block;margin-top:6px;font-size:var(--font-size-sm);color:var(--text-secondary); }
.se__version { font-size:var(--font-size-xs);color:var(--text-tertiary); }
.se__field { margin-bottom:14px; }
.se__label { display:block;font-size:var(--font-size-sm);font-weight:var(--font-weight-medium);margin-bottom:6px; }
.se__req { color:var(--danger-600); }
.se__textarea { width:100%;min-height:90px;padding:10px;box-sizing:border-box;border:1px solid var(--border-base);border-radius:var(--radius-md);font-size:var(--font-size-sm); }
.se__picker { border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;color:var(--text-secondary); }
.se__readonly { display:block;margin-top:8px;font-size:var(--font-size-sm);line-height:1.6;white-space:pre-wrap; }
</style>
