<template>
  <view class="page-wrap se">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack" v-if="loaded">
        <view class="card se__head">
          <view class="row-between">
            <text class="card-title">实习自评 / 鉴定</text>
            <MobileStatusTag v-if="evalData" :status="evalData.submitStatus || 'DRAFT'" />
          </view>
          <text class="se__hint">总结实习收获与问题，提交后由指导教师填写鉴定意见。</text>
        </view>
        <view class="card se__form">
          <view class="se__field">
            <text class="se__label">实习总结 <text class="se__req">*</text></text>
            <textarea v-model="form.selfSummary" class="se__textarea" maxlength="2000" placeholder="如：本次实习期间，我在企业从事了相关专业工作，认真完成各项任务，将专业理论知识与实践相结合…" />
          </view>
          <view class="se__field">
            <text class="se__label">主要收获</text>
            <textarea v-model="form.selfHarvest" class="se__textarea" maxlength="1000" placeholder="如：学会了相关工具的使用，了解了企业实际工作流程与规范，增强了团队协作能力…" />
          </view>
          <view class="se__field">
            <text class="se__label">存在问题</text>
            <textarea v-model="form.selfProblem" class="se__textarea" maxlength="1000" placeholder="如：在某方面经验不足，今后计划通过系统学习加以弥补（可选）" />
          </view>
          <view class="se__field">
            <text class="se__label">对企业评分（1-5）</text>
            <picker mode="selector" :range="ratingLabels" @change="onEntRate">
              <view class="se__picker">{{ form.enterpriseRating ? form.enterpriseRating + ' 分' : '请选择' }}</view>
            </picker>
          </view>
          <view class="se__field">
            <text class="se__label">对企业评价</text>
            <textarea v-model="form.enterpriseFeedback" class="se__textarea" maxlength="500" placeholder="对实习企业的评价（可选）" />
          </view>
          <view class="se__field">
            <text class="se__label">对岗位评分（1-5）</text>
            <picker mode="selector" :range="ratingLabels" @change="onPosRate">
              <view class="se__picker">{{ form.positionRating ? form.positionRating + ' 分' : '请选择' }}</view>
            </picker>
          </view>
          <view class="se__field">
            <text class="se__label">对岗位评价</text>
            <textarea v-model="form.positionFeedback" class="se__textarea" maxlength="500" placeholder="对实习岗位的评价（可选）" />
          </view>
        </view>
        <view v-if="evalData && evalData.advisorOpinion" class="card">
          <text class="se__label">指导教师意见</text>
          <text class="se__readonly">{{ evalData.advisorOpinion }}</text>
        </view>
        <MobileInlineAlert v-if="locked" type="warning" description="鉴定已通过学校审核，不可再修改。" />
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="loaded && !locked">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : (evalData ? '重新提交' : '提交自评') }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast, back } from '@/utils/nav'

export default {
  data() {
    return {
      pageState: 'loading', loaded: false, submitting: false, evalData: null, locked: false,
      form: { selfSummary: '', selfHarvest: '', selfProblem: '',
        enterpriseRating: null, enterpriseFeedback: '', positionRating: null, positionFeedback: '' },
      ratingLabels: ['1 分', '2 分', '3 分', '4 分', '5 分']
    }
  },
  onLoad() { this.load() },
  methods: {
    onEntRate(e) { this.form.enterpriseRating = (Number(e.detail.value) || 0) + 1 },
    onPosRate(e) { this.form.positionRating = (Number(e.detail.value) || 0) + 1 },
    load() {
      this.pageState = 'loading'
      studentApi.getInternshipSelfEval().then((d) => {
        this.evalData = d
        this.locked = d && d.schoolReviewStatus === 'APPROVED'
        if (d) {
          this.form.selfSummary = d.selfSummary || ''
          this.form.selfHarvest = d.selfHarvest || ''
          this.form.selfProblem = d.selfProblem || ''
          this.form.enterpriseRating = d.enterpriseRating || null
          this.form.enterpriseFeedback = d.enterpriseFeedback || ''
          this.form.positionRating = d.positionRating || null
          this.form.positionFeedback = d.positionFeedback || ''
        }
        this.loaded = true
        this.pageState = 'ready'
      }).catch(() => { this.pageState = 'error' })
    },
    submit() {
      if (this.submitting || this.locked) return
      if (!this.form.selfSummary.trim()) return toast('请填写实习总结')
      this.submitting = true
      studentApi.submitInternshipSelfEval(this.form).then(() => {
        toast('自评已提交')
        setTimeout(() => back(), 600)
      }).catch((e) => {
        toast((e && e.message) || '提交失败，请稍后重试')
      }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.se__hint { display: block; margin-top: 6px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.se__field { margin-bottom: 14px; }
.se__label { display: block; font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); margin-bottom: 6px; }
.se__req { color: var(--danger-600); }
.se__textarea { width: 100%; min-height: 90px; padding: 10px; box-sizing: border-box; border: 1px solid var(--border-base); border-radius: var(--radius-md); font-size: var(--font-size-sm); }
.se__readonly { display: block; margin-top: 8px; font-size: var(--font-size-sm); line-height: 1.6; white-space: pre-wrap; }
</style>
