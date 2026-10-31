<template>
  <view class="internship-surface mobile-page mobile-student page-wrap">
    <MobileNavBar variant="brand" title="实习求助" show-back :fallback-url="'/pages/student-internship/index' + (context.batchId ? '?batchId=' + encodeURIComponent(context.batchId) : '')" />
    <MobileGlobalState :state="state" :description="errorMessage" @retry="load()">
    <view class="page-pad stack">
      <MobileInlineAlert v-if="errorMessage" type="warning" :description="errorMessage" />
      <button class="mobile-control hp__refresh" :disabled="supporting || submitting" @click="load()">刷新进度</button>
      <MobileInlineAlert v-if="historyMode" type="info" description="历史实习仅可查看咨询与求助记录，不能新增或评价。" />
      <MobileInlineAlert v-if="support.feedbackNotice" type="info" :description="support.feedbackNotice" />
      <view v-if="canWrite" class="card stack"><text class="card-title">需要老师直接协助？</text><text class="hp__hint">填写后提交给指导教师。</text><button class="mobile-control btn btn-primary" :disabled="!canWrite || submitting || supporting" @click="manualOpen = !manualOpen">{{ manualOpen ? '收起人工求助表单' : '直接人工求助' }}</button></view>
      <view v-if="canWrite && manualOpen" class="card stack hp__manual">
        <view>
          <text class="card-title">人工求助</text>
          <text class="hp__hint">安全、权益等紧急问题可直接提交。</text>
        </view>
        <view class="hp__field">
          <text class="hp__label">紧急程度</text>
          <picker class="mobile-picker" mode="selector" :range="levelLabels" :disabled="!canWrite || submitting || supporting" @change="onLevel">
            <view class="hp__picker">{{ levelLabels[levelIndex] }}</view>
          </picker>
        </view>
        <view class="hp__field">
          <text class="hp__label">标题</text>
          <input v-model="form.title" :disabled="!canWrite || submitting || supporting" class="mobile-input hp__input" maxlength="40" placeholder="可选，默认「学生实习求助」" />
        </view>
        <view class="hp__field">
          <text class="hp__label">情况说明 <text class="hp__req">*</text></text>
          <textarea v-model="form.content" :disabled="!canWrite || submitting || supporting" class="mobile-textarea hp__textarea" maxlength="500" placeholder="不少于 5 字，请客观描述现状与诉求" />
        </view>
        <button class="mobile-control btn btn-primary" :disabled="!canWrite || submitting || supporting" @click="submitManual">{{ submitting ? '提交中…' : '提交人工求助' }}</button>
      </view>
      <view v-if="receipt" class="card hp__receipt">
        <text class="t-bold">✓ 求助已登记 · {{ helpStatus(receipt.status) }}</text>
        <text>记录 #{{ receipt.id }} · 处理结果可在本页查看。</text>
      </view>
      <view v-if="records.length" class="card stack">
        <text class="card-title">求助处理进度</text>
        <view v-for="item in records" :key="item.id" class="hp__record">
          <view class="row-between"><text class="t-bold">{{ item.title }}</text><MobileStatusTag :label="helpStatus(item.status)" :type="item.status === 'CLOSED' ? 'success' : item.status === 'PROCESSING' ? 'info' : 'warning'" /></view>
          <text class="hp__hint">{{ item.latestFeedback || '已提交，等待指导教师受理。' }}</text>
          <text class="hp__time">更新于 {{ formatTime(item.updatedAt) }}</text>
        </view>
      </view>

      <view v-if="canWrite" class="card">
        <text class="card-title">常见问题</text>
        <view class="hp__quick">
          <text v-for="item in quickQuestions" :key="item" class="hp__chip" @click="askQuick(item)">{{ item }}</text>
        </view>
      </view>

      <MobileInlineAlert v-if="support.status === 'TRANSFERRED'" type="info" title="本次咨询已转人工求助"
        :description="`已关联求助记录 #${support.transferredRiskId || '—'}，处理结果见上方进度。`" />

      <view v-if="support.history.length" class="card stack">
        <button v-if="support.status === 'TRANSFERRED'" class="mobile-control hp__history-toggle" :aria-expanded="supportHistoryExpanded" @click="expandedSupportScope = supportHistoryExpanded ? '' : supportHistoryScope">{{ supportHistoryExpanded ? '收起咨询记录' : '查看咨询记录' }}（{{ support.history.length }}轮）</button>
        <text v-else class="card-title">本次咨询</text>
        <template v-if="support.status !== 'TRANSFERRED' || supportHistoryExpanded">
        <view v-for="(item, index) in support.history" :key="index" class="hp__chat">
          <view class="hp__bubble hp__bubble--me"><text>{{ item.question }}</text></view>
          <view class="hp__bubble hp__bubble--bot"><text>{{ item.answer }}</text></view>
        </view>
        </template>
        <view v-if="canWrite && awaitingFeedback && support.status === 'ACTIVE'" class="hp__feedback">
          <text class="hp__hint">这个回答解决了吗？未解决累计 {{ support.unresolvedCount }}/3。</text>
          <view class="hp__feedback-actions">
            <button class="mobile-control btn btn-ghost flex-1" :disabled="!canWrite || supporting || submitting" @click="markUnresolved">没解决</button>
            <button class="mobile-control btn btn-primary flex-1" :disabled="!canWrite || supporting || submitting" @click="markSolved">已解决</button>
          </view>
        </view>
      </view>

      <view v-if="canWrite && support.status !== 'TRANSFERRED'" class="card">
        <view class="hp__field">
          <text class="hp__label">继续提问</text>
          <textarea v-model="question" :disabled="!canWrite || supporting || submitting" class="mobile-textarea hp__textarea hp__textarea--ask" maxlength="500" placeholder="例如：为什么今天打卡提示定位异常？" />
        </view>
        <button class="mobile-control btn btn-primary hp__ask" :disabled="!canWrite || supporting || submitting || awaitingFeedback" @click="askSupport">
          {{ supporting ? '处理中…' : (awaitingFeedback ? '请先确认上个回答' : '发送问题') }}
        </button>
        <text v-if="support.status === 'ACTIVE'" class="hp__counter">再有 {{ support.remainingBeforeHuman }} 次明确“没解决”将自动转人工。</text>
      </view>

    </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { formatDateTime } from '@/utils/format'

const LEVELS = [{v:'LOW',l:'一般'},{v:'MEDIUM',l:'较急'},{v:'HIGH',l:'紧急'}]
const blankSupport=()=>({sessionId:'',status:'NEW',unresolvedCount:0,remainingBeforeHuman:3,history:[],transferredRiskId:'',awaitingFeedback:false,answerVersion:null,feedbackNotice:''})
export default {
  data() { return {
    manualOpen:false,levelIndex:1,levelLabels:LEVELS.map(x=>x.l),quickQuestions:['打卡定位异常','周报怎么提交','请假要什么材料','三方协议进度','免实习怎么申请','成绩有异议'],
    form:{title:'',content:''},submitting:false,supporting:false,question:'',context:{},records:[],receipt:null,support:blankSupport(),expandedSupportScope:'',
    state:'loading',errorMessage:'',requestedBatchId:'',historyMode:false,hidden:false,sequence:0,generation:currentSessionGeneration()
  } },
  computed:{
    supportHistoryScope(){return [this.generation,this.context.batchId,this.context.internshipId,this.support.sessionId,this.support.answerVersion].join(':')},
    supportHistoryExpanded(){return this.expandedSupportScope===this.supportHistoryScope},
    awaitingFeedback(){return this.support.awaitingFeedback===true},
    canWrite(){return this.state==='ready' && !this.hidden && !this.historyMode && !!this.context.batchId && !!this.context.internshipId && this.generation===currentSessionGeneration()}
  },
  onLoad(options={}){this.requestedBatchId=String(options.batchId||'');this.load()},
  onShow(){if(this.hidden || this.generation!==currentSessionGeneration()){this.hidden=false;this.load()}},
  onHide(){this.hidden=true;this.sequence++},
  onUnload(){this.hidden=true;this.sequence++;this.form={title:'',content:''};this.question='';this.context={};this.support=blankSupport();this.records=[];this.receipt=null},
  onPullDownRefresh(){this.load().finally(()=>uni.stopPullDownRefresh())},
  methods:{
    formatTime:formatDateTime,
    helpStatus(status){return ({PENDING_HANDLE:'待处理',PROCESSING:'处理中',RESOLVED:'已化解',CLOSED:'已关闭'})[status]||'状态待确认'},
    command(){return {sequence:this.sequence,generation:currentSessionGeneration(),batchId:this.context.batchId,internshipId:this.context.internshipId}},
    current(command){return !this.hidden && command.sequence===this.sequence && command.generation===currentSessionGeneration() && command.batchId===this.context.batchId && command.internshipId===this.context.internshipId},
    applySupport(result){
      if(!result || !Array.isArray(result.history) || typeof result.awaitingFeedback!=='boolean' || !['NEW','ACTIVE','SOLVED','TRANSFERRED'].includes(result.status) ||
        (result.awaitingFeedback && (!Number.isSafeInteger(result.answerVersion)||result.answerVersion<1)))throw Error('invalid support response')
      this.support={...blankSupport(),...result}
    },
    showError(error){this.errorMessage=normalizeError(error).text;toast(this.errorMessage)},
    async load(){
      const generation=currentSessionGeneration(),sequence=++this.sequence
      const current=()=>!this.hidden && sequence===this.sequence && generation===currentSessionGeneration()
      if(this.generation!==generation){this.form={title:'',content:''};this.question='';this.context={}}
      this.generation=generation;this.state='loading';this.errorMessage='';this.records=[];this.support=blankSupport();this.receipt=null;this.submitting=false;this.supporting=false
      try{
        const dashboard=await studentApi.getInternship(this.requestedBatchId)
        if(!current())return
        const context={batchId:String(dashboard?.batchId||''),internshipId:String(dashboard?.recordId||'')}
        if(this.context.batchId && (this.context.batchId!==context.batchId || this.context.internshipId!==context.internshipId)){this.form={title:'',content:''};this.question=''}
        this.context=context;this.historyMode=dashboard?.historyMode===true
        if(!context.batchId || !context.internshipId){this.errorMessage='当前没有可用实习记录，请先核对实习批次。';this.state='empty';return}
        const [help,support]=await Promise.all([studentApi.getInternshipHelp(context.batchId,context.internshipId),studentApi.getInternshipSupport(context.batchId,context.internshipId)])
        if(!current())return
        if(!Array.isArray(help?.items))throw Error('invalid help response')
        this.applySupport(support);this.records=help.items;this.state='ready'
      }catch(error){if(current()){this.state='error';this.showError(error)}}
    },
    askQuick(text){if(!this.canWrite || this.supporting || this.submitting || this.awaitingFeedback || this.support.status==='TRANSFERRED')return;this.question=text;this.askSupport()},
    async askSupport(){
      if(!this.canWrite || this.supporting || this.submitting || this.awaitingFeedback || this.support.status==='TRANSFERRED')return
      const message=this.question.trim();if(message.length<2)return toast('请至少输入2个字的问题')
      const command=this.command();this.supporting=true;this.errorMessage=''
      try{const result=await studentApi.askInternshipSupport({batchId:command.batchId,internshipId:command.internshipId,message});if(!this.current(command))return;this.applySupport(result);this.question=''}
      catch(error){if(this.current(command))this.showError(error)}
      finally{if(this.current(command))this.supporting=false}
    },
    markSolved(){return this.sendFeedback('SOLVED')},
    markUnresolved(){return this.sendFeedback('UNRESOLVED')},
    async sendFeedback(action){
      if(!this.canWrite || this.supporting || this.submitting || !this.awaitingFeedback || !this.support.sessionId)return
      const command=this.command(),id=this.support.sessionId,answerVersion=this.support.answerVersion
      this.supporting=true;this.errorMessage=''
      try{
        const send=action==='SOLVED'?studentApi.solveInternshipSupport:studentApi.unresolvedInternshipSupport
        const result=await send(id,{batchId:command.batchId,internshipId:command.internshipId,answerVersion})
        if(!this.current(command))return
        if(String(result?.sessionId)!==String(id))throw Error('invalid support session')
        this.applySupport(result)
        toast(result.status==='TRANSFERRED'?'最近对话已登记到人工求助记录':action==='SOLVED'?'已记录为解决':`已记录未解决（${result.unresolvedCount}/3），可继续补充问题`)
        if(result.status==='TRANSFERRED')await this.refreshHelp(command)
      }catch(error){if(this.current(command))this.showError(error)}
      finally{if(this.current(command))this.supporting=false}
    },
    async refreshHelp(command){
      try{const result=await studentApi.getInternshipHelp(command.batchId,command.internshipId);if(!this.current(command))return;if(!Array.isArray(result?.items))throw Error('invalid help response');this.records=result.items}
      catch(error){if(this.current(command))this.errorMessage='人工求助已登记，进度读取未完成，请重新读取；无需重复提交。'}
    },
    onLevel(e){if(this.canWrite && !this.submitting && !this.supporting)this.levelIndex=Number(e.detail.value)||0},
    async submitManual(){
      if(!this.canWrite || this.submitting || this.supporting)return
      if(this.form.content.trim().length<5)return toast('情况说明不少于5个字')
      const command=this.command();this.submitting=true;this.errorMessage=''
      try{
        const result=await studentApi.reportInternshipHelp({batchId:command.batchId,internshipId:command.internshipId,title:this.form.title,content:this.form.content,riskLevel:LEVELS[this.levelIndex]?.v||'MEDIUM'})
        if(!this.current(command))return
        if(!result?.id)throw Error('invalid help receipt')
        this.receipt=result;toast('人工求助已登记');this.form={title:'',content:''};await this.refreshHelp(command)
      }catch(error){if(this.current(command))this.showError(error)}
      finally{if(this.current(command))this.submitting=false}
    }
  }
}
</script>

<style scoped>
.hp__hint{display:block;margin-top:8px;font-size:var(--font-size-base);color:var(--text-secondary);line-height:1.55}.hp__quick{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.hp__chip{padding:7px 10px;border-radius:999px;background:var(--brand-50);color:var(--brand-primary);font-size:var(--font-size-base)}
.hp__chat{display:flex;flex-direction:column;gap:8px}.hp__bubble{max-width:88%;padding:10px 12px;border-radius:12px;font-size:var(--font-size-base);line-height:1.6;white-space:pre-wrap;word-break:break-word}.hp__bubble--me{align-self:flex-end;background:var(--brand-primary);color:#fff}.hp__bubble--bot{align-self:flex-start;background:var(--gray-100);color:var(--text-primary)}
.hp__feedback{padding-top:4px}.hp__feedback-actions{display:flex;gap:10px;margin-top:10px}.hp__counter{display:block;margin-top:8px;font-size:var(--font-size-base);color:var(--text-tertiary)}
.hp__field{margin-bottom:12px}.hp__label{display:block;font-size:var(--font-size-base);color:var(--text-secondary);margin-bottom:6px}.hp__req{color:var(--danger-500)}.hp__input,.hp__picker,.hp__textarea{width:100%;border:1px solid var(--border-base);border-radius:var(--radius-sm);padding:10px 12px;font-size:var(--font-size-base);box-sizing:border-box}.hp__textarea{min-height:120px}.hp__textarea--ask{min-height:78px}.hp__ask{width:100%;margin:0}
.hp__receipt{display:flex;flex-direction:column;gap:5px;border-color:var(--success-300,#86efac);background:var(--success-50,#f0fdf4);font-size:var(--font-size-base);color:var(--success-800,#166534)}.hp__record{padding:10px 0;border-bottom:1px solid var(--border-light)}.hp__record:last-child{border-bottom:0}.hp__time{display:block;margin-top:5px;font-size:var(--font-size-base);color:var(--text-tertiary)}
.hp__input{height:44px;min-height:44px;padding:0 12px}
.hp__refresh{align-self:flex-end;min-height:44px;margin:0;padding:0 8px;background:transparent;border:0;color:var(--text-link);font-size:var(--font-size-base);line-height:44px}.hp__refresh::after{border:0}.hp__history-toggle{display:flex;align-items:center;width:100%;min-height:44px;margin:0;padding:0;background:transparent;border:0;color:var(--text-link);font-size:var(--font-size-base)}.hp__history-toggle::after{border:0}.hp__picker{min-height:44px;display:flex;align-items:center;box-sizing:border-box}.hp__quick{gap:8px}.hp__chip{min-height:44px;box-sizing:border-box;display:flex;align-items:center;padding:8px 10px}</style>
