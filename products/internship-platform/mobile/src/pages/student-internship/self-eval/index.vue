<template>
  <view class="mobile-page mobile-student page-wrap se internship-flow">
    <MobileNavBar title="实习鉴定" show-back :fallback-url="'/pages/student-internship/index' + (dashboard?.batchId ? '?batchId=' + encodeURIComponent(dashboard.batchId) : '')" />
    <MobileGlobalState :state="pageState" :description="loadError || undefined" @retry="load">
      <view class="page-pad stack" v-if="loaded">
        <view v-if="receipt" class="card se__receipt">
          <view class="row-between"><text class="t-bold">✓ 自评已提交</text><text>第{{ receipt.version }}版</text></view>
          <text>鉴定 #{{ receipt.id }} · {{ receipt.statusLabel }}</text><text>{{ receipt.nextStep }}</text>
        </view>
        <view class="card se__head">
          <view class="row-between">
            <text class="card-title">我的自评</text>
            <MobileStatusTag v-if="evalData" :label="evalData.reviewStatusLabel || evalData.submitStatusLabel" :type="statusTone" />
            <MobileStatusTag v-else label="尚未提交" type="info" />
          </view>
          <text v-if="!readonly" class="se__hint">提交后由指导教师填写意见，再交学校审核。</text>
          <text v-if="evalData?.version" class="se__version">记录版本 {{ evalData.version }}</text>
          <view v-if="dashboard && !dashboard.score && !dashboard.archive" class="se__pending-result"><text>结项进度：{{ resultStatusLabel }}</text><text class="se__hint">自评与企业、导师评价齐备后，由学校发布正式成绩。</text></view>
        </view>
        <view v-if="dashboard && (dashboard.score || dashboard.archive || appealData?.hasAppeal)" class="card se__result">
          <view class="row-between">
            <view><text class="se__eyebrow">结项与正式结果</text><text class="card-title">{{ dashboard.archive ? '实习结果' : resultTitle }}</text></view>
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
          <text v-else class="se__hint">正式成绩尚未发布，请查看当前办理结果。</text>
          <view v-if="appealData?.hasAppeal" class="se__appeal-state">
            <text>最近申诉 · {{ appealData.statusLabel || '状态待核对' }}</text>
            <text>{{ appealNextStep }}</text>
          </view>
          <view v-if="canAppeal" class="se__appeal-form">
            <textarea v-model="appealReason" class="mobile-textarea se__textarea" maxlength="500" placeholder="对正式成绩有异议时填写理由（至少5字）" />
            <button class="mobile-control btn btn-ghost" :disabled="appealSubmitting" @click="submitAppeal">{{ appealSubmitting ? '提交中…' : '提交成绩申诉' }}</button>
          </view>
          <view v-if="dashboard.archive" class="se__archive">
            <text>档案完整度 {{ dashboard.archive.completeness }}%</text>
            <text>归档时间：{{ formatTime(dashboard.archive.archivedAt) }}</text>
          </view>
        </view>
        <MobileInlineAlert v-if="historyMode && !dashboard?.archive" type="info" description="历史实习鉴定仅供查阅。" />
        <MobileInlineAlert v-else-if="conflictText" type="warning" title="版本已变化，草稿已保留" :description="conflictText" />
        <MobileInlineAlert v-else-if="evalData?.reviewStatus === 'RETURNED'" type="warning" title="鉴定已退回" :description="evalData.reviewComment || '请按审核意见修改后重新提交。修改正文后旧指导意见将失效。'" />
        <MobileInlineAlert v-else-if="pendingReview" type="info" title="鉴定正在审核" description="当前版本已提交，不能继续覆盖；如需修改，请等待学校退回。" />
        <view class="card se__form">
          <button v-if="readonly" class="mobile-control flow-disclosure" :aria-expanded="reviewExpanded" @click="reviewExpanded = !reviewExpanded"><text class="se__section-title">实习回顾</text><text class="flow-link">{{ reviewExpanded ? '收起' : '查看' }}</text></button>
          <text v-else class="se__section-title">实习回顾</text>
          <view v-show="!readonly || reviewExpanded">
          <view class="se__field">
            <text class="se__label">实习总结 <text class="se__req">*</text></text>
            <textarea v-if="!readonly" v-model="form.selfSummary" class="mobile-textarea se__textarea se__textarea--summary" :disabled="readonly" maxlength="2000" placeholder="请完整总结实习工作、能力提升和职业认识（至少20字）" />
            <text v-else class="se__readonly">{{ form.selfSummary || '未填写' }}</text>
          </view>
          <view v-if="!readonly || form.selfHarvest" class="se__field">
            <text class="se__label">主要收获</text>
            <textarea v-if="!readonly" v-model="form.selfHarvest" class="mobile-textarea se__textarea" :disabled="readonly" maxlength="1000" placeholder="专业技能、企业流程、团队协作等" />
            <text v-else class="se__readonly">{{ form.selfHarvest || '未填写' }}</text>
          </view>
          <view v-if="!readonly || form.selfProblem" class="se__field">
            <text class="se__label">存在问题</text>
            <textarea v-if="!readonly" v-model="form.selfProblem" class="mobile-textarea se__textarea" :disabled="readonly" maxlength="1000" placeholder="不足与后续改进计划" />
            <text v-else class="se__readonly">{{ form.selfProblem || '未填写' }}</text>
          </view>
          <text v-if="!readonly || form.enterpriseRating || form.enterpriseFeedback || form.positionRating || form.positionFeedback" class="se__section-title se__section-title--next">企业与岗位评价</text>
          <view v-if="!readonly || form.enterpriseRating" class="se__field">
            <text class="se__label">对企业评分（1-5）</text>
            <picker class="mobile-picker" mode="selector" :disabled="readonly" :range="ratingLabels" @change="onEntRate">
              <view class="se__picker">{{ form.enterpriseRating ? form.enterpriseRating + ' 分' : '请选择' }}</view>
            </picker>
          </view>
          <view v-if="!readonly || form.enterpriseFeedback" class="se__field">
            <text class="se__label">对企业评价</text>
            <textarea v-if="!readonly" v-model="form.enterpriseFeedback" class="mobile-textarea se__textarea" :disabled="readonly" maxlength="500" placeholder="对实习企业的真实评价" />
            <text v-else class="se__readonly">{{ form.enterpriseFeedback || '未填写' }}</text>
          </view>
          <view v-if="!readonly || form.positionRating" class="se__field">
            <text class="se__label">对岗位评分（1-5）</text>
            <picker class="mobile-picker" mode="selector" :disabled="readonly" :range="ratingLabels" @change="onPosRate">
              <view class="se__picker">{{ form.positionRating ? form.positionRating + ' 分' : '请选择' }}</view>
            </picker>
          </view>
          <view v-if="!readonly || form.positionFeedback" class="se__field">
            <text class="se__label">对岗位评价</text>
            <textarea v-if="!readonly" v-model="form.positionFeedback" class="mobile-textarea se__textarea" :disabled="readonly" maxlength="500" placeholder="对实习岗位的真实评价" />
            <text v-else class="se__readonly">{{ form.positionFeedback || '未填写' }}</text>
          </view>
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
      <button class="mobile-control btn btn-primary flex-1" :disabled="submitting || !!conflictText" @click="submit">{{ submitting ? '提交中…' : (evalData ? '修改并重新提交' : '提交自评') }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'

const blankSelfEval = () => ({ selfSummary: '', selfHarvest: '', selfProblem: '', enterpriseRating: null, enterpriseFeedback: '', positionRating: null, positionFeedback: '' })

export default {
  data() {
    return {
      pageState: 'loading', loaded: false, submitting: false, reviewExpanded: false,
      evalData: null, dashboard: null, appealData: null, historyMode: false,
      appealReason: '', appealSubmitting: false,
      receipt: null, conflictText: '',
      loadError:'',requestedBatchId:'',hidden:false,sequence:0,generation:currentSessionGeneration(),draftScope:'',formBaseline:JSON.stringify(blankSelfEval()),
      form: blankSelfEval(),
      ratingLabels: ['1 分', '2 分', '3 分', '4 分', '5 分']
    }
  },
  computed: {
    pendingReview() { return this.evalData?.submitStatus === 'SUBMITTED' && this.evalData?.reviewStatus === 'PENDING' },
    readonly() { return !this.loaded || this.pageState!=='ready' || this.historyMode || this.evalData?.reviewStatus === 'APPROVED' || this.pendingReview },
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
  onHide(){this.hidden=true;this.sequence++},
  onUnload(){this.hidden=true;this.sequence++},
  onShow(){const changed=this.generation!==currentSessionGeneration(),returning=this.hidden;this.hidden=false;if(changed){this.generation=currentSessionGeneration();this.sequence++;this.loaded=false;this.dashboard=null;this.evalData=null;this.appealData=null;this.receipt=null;this.conflictText='';this.form=blankSelfEval();this.formBaseline=JSON.stringify(this.form);this.draftScope='';this.appealReason=''}if(changed||returning){this.submitting=false;this.appealSubmitting=false;this.load()}},
  methods: {
    fence(){const sequence=this.sequence,generation=currentSessionGeneration(),batch=this.requestedBatchId;return ()=>!this.hidden&&sequence===this.sequence&&generation===currentSessionGeneration()&&batch===this.requestedBatchId},
    canAct(){return !this.hidden&&this.generation===currentSessionGeneration()&&this.loaded&&this.pageState==='ready'&&!!this.dashboard?.batchId&&!!this.dashboard?.recordId},
    onEntRate(e) { if (!this.readonly) this.form.enterpriseRating = Number(e.detail.value) + 1 },
    onPosRate(e) { if (!this.readonly) this.form.positionRating = Number(e.detail.value) + 1 },
    formatTime(value) { return formatDateTime(value) },
    async load() {
      const preserve=!!this.draftScope&&JSON.stringify(this.form)!==this.formBaseline,oldScope=this.draftScope
      this.sequence++;const current=this.fence()
      this.loaded=false;this.loadError=''
      this.pageState = 'loading'
      try {
        const dashboard = await studentApi.getInternship(this.requestedBatchId)
        if(!current())return
        if(!dashboard?.batchId||!dashboard?.recordId||(this.requestedBatchId&&String(dashboard.batchId)!==this.requestedBatchId))throw new Error('当前批次没有可办理的实习记录，请返回实习首页核对。')
        const [data, appeal] = await Promise.all([
          studentApi.getInternshipSelfEval(dashboard?.batchId, dashboard?.recordId),
          studentApi.getInternshipScoreAppeal(dashboard?.batchId, dashboard?.recordId)
        ])
        if(!current())return
        const scope=`${this.generation}:${dashboard.batchId}:${dashboard.recordId}`
        this.dashboard = dashboard
        this.appealData = appeal
        this.historyMode = !!dashboard?.historyMode
        if(preserve&&scope===oldScope){
          if(String(data?.id||'')!==String(this.evalData?.id||'')||data?.version!==this.evalData?.version)this.conflictText='服务端鉴定版本已变化，当前正文与原版本已保留。请返回并核对最新记录后再填写，系统不会自动采用新版本覆盖。'
        }else{
          this.evalData = data?.id ? data : null
          this.form=blankSelfEval()
        if (data?.id) {
          this.form = {
            selfSummary: data.selfSummary || '', selfHarvest: data.selfHarvest || '',
            selfProblem: data.selfProblem || '', enterpriseRating: data.enterpriseRating || null,
            enterpriseFeedback: data.enterpriseFeedback || '', positionRating: data.positionRating || null,
            positionFeedback: data.positionFeedback || ''
          }
        }
        this.conflictText = ''
          this.formBaseline=JSON.stringify(this.form)
        }
        this.draftScope=scope
        this.loaded = true
        this.pageState = 'ready'
      } catch (e) { if(current()){const error=normalizeError(e);this.pageState=error.pageState||'error';this.loadError=error.text||e?.message||'鉴定读取失败，未提交内容已保留，请重试。'} }
    },
    async submit() {
      if (!this.canAct() || this.submitting || this.readonly || this.conflictText) return
      const current=this.fence()
      if (String(this.form.selfSummary || '').trim().length < 20) return toast('实习总结至少20个字')
      this.submitting = true
      try {
        const result = await studentApi.submitInternshipSelfEval({
          ...this.form,
          batchId: this.dashboard?.batchId,
          internshipId: this.dashboard?.recordId,
          ...(this.evalData?.id ? { expectedVersion: this.evalData.version } : {})
        })
        if(!current())return
        this.receipt = { id: result?.id || '', version: result?.version,
          statusLabel: result?.reviewStatusLabel || result?.reviewStatus || '待审核',
          nextStep: '等待导师填写评价并由学校审核' }
        this.conflictText = ''
        this.formBaseline=JSON.stringify(this.form)
        toast('自评已提交，等待指导意见和学校审核')
        this.submitting=false
        await this.load()
      } catch (e) {
        if(!current())return
        if (normalizeError(e).kind === 'conflict') {
          this.conflictText = '服务端鉴定版本已更新。当前输入没有丢失；请核对后手动返回并刷新，再决定是否重新提交。系统不会自动重放。'
          toast('版本已变化，当前草稿已保留')
        } else toast(e?.message || '提交失败，请稍后重试')
      } finally { if(current())this.submitting = false }
    },
    async submitAppeal() {
      if (!this.canAct() || this.appealSubmitting || !this.canAppeal) return
      const current=this.fence(),context={batchId:this.dashboard.batchId,internshipId:this.dashboard.recordId}
      const reason = String(this.appealReason || '').trim()
      if (reason.length < 5) return toast('申诉理由至少5个字')
      this.appealSubmitting = true
      try {
        await studentApi.submitInternshipScoreAppeal({
          ...context,
          reason
        })
        if(!current())return
        this.appealReason = ''
        const appeal=await studentApi.getInternshipScoreAppeal(context.batchId,context.internshipId)
        if(!current())return
        this.appealData = appeal
        toast('成绩申诉已提交，等待学校处理')
      } catch (e) {
        if(current())toast(e?.message || '申诉提交失败，请稍后重试')
      } finally { if(current())this.appealSubmitting = false }
    }
  }
}
</script>

<style scoped>
.se__receipt{display:flex;flex-direction:column;gap:5px;padding:var(--space-3);border-color:var(--success-300,#86efac);background:var(--success-50,#f0fdf4);font-size:var(--font-size-base);color:var(--text-secondary)}
.se__hint,.se__version { display:block;margin-top:6px;font-size:var(--font-size-base);color:var(--text-secondary); }
.se__version { font-size:var(--font-size-base);color:var(--text-tertiary); }
.se__field { margin-bottom:14px; }
.se__label { display:block;font-size:var(--font-size-base);font-weight:var(--font-weight-medium);margin-bottom:6px; }
.se__req { color:var(--danger-600); }
.se__textarea { width:100%;min-height:90px;padding:10px;box-sizing:border-box;border:1px solid var(--border-base);border-radius:var(--radius-md);font-size:var(--font-size-base); }
.se__picker { border:1px solid var(--border-base);border-radius:var(--radius-md);padding:10px 12px;color:var(--text-secondary); }
.se__readonly { display:block;margin-top:8px;font-size:var(--font-size-base);line-height:1.6;white-space:pre-wrap; }
.se__result{display:flex;flex-direction:column;gap:12px;border-top:3px solid var(--brand-primary)}
.se__eyebrow{display:block;margin-bottom:4px;font-size:var(--font-size-base);color:var(--text-tertiary)}
.se__score-line{display:flex;align-items:baseline;gap:8px}.se__score-line text:first-child{font-size:36px;font-weight:700;color:var(--brand-primary)}.se__score-line text:last-child{font-size:var(--font-size-base);color:var(--text-secondary)}
.se__score-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.se__score-grid text{padding:8px 10px;border-radius:var(--radius-md);background:var(--gray-50);font-size:var(--font-size-base);color:var(--text-secondary)}
.se__appeal-state,.se__archive{display:flex;flex-direction:column;gap:4px;padding:10px 12px;border-radius:var(--radius-md);background:var(--warning-50,#fffbeb);font-size:var(--font-size-base);line-height:1.5;color:var(--warning-800,#92400e)}
.se__archive{background:var(--success-50,#f0fdf4);color:var(--success-800,#166534)}.se__appeal-form{display:flex;flex-direction:column;gap:8px}.se__appeal-form .se__textarea{min-height:72px}
.se__head>.row-between{gap:12px;flex-wrap:wrap}.se__hint{line-height:1.65}.se__pending-result{margin-top:12px;padding-top:12px;border-top:1px solid var(--border-light);font-size:var(--font-size-base);color:var(--text-secondary)}.se__section-title{display:block;margin-bottom:16px;font-size:var(--font-size-lg);font-weight:600;color:var(--text-primary)}.se__section-title--next{padding-top:16px;border-top:1px solid var(--border-light)}.se__textarea{height:110px;min-height:110px;line-height:1.6}.se__textarea--summary{height:150px;min-height:150px}.se__picker{display:flex;align-items:center;height:44px;min-height:44px;box-sizing:border-box;padding:0 12px;font-size:var(--font-size-base)}.se__field:last-child{margin-bottom:0}</style>
