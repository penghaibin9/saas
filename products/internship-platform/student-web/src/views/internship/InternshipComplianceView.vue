<template>
  <div class="sp-page">
    <section class="sp-card batch-switch"><h1>上岗准备与安全教育</h1><button type="button" class="sp-btn sp-btn--ghost" @click="returnHome">返回本批次实习</button></section>
    <StateBlock v-if="loading" type="loading" text="正在读取当前批次上岗条件…" />
    <section v-else-if="error" class="sp-card"><StateBlock type="error" :text="error" /><button type="button" class="sp-btn" @click="load">重新读取</button></section>
    <section v-else-if="needSelect" class="sp-card selector-card"><h2>请选择要办理的实习批次</h2><button v-for="candidate in candidates" :key="candidate.recordId" type="button" class="candidate" @click="selectBatch(candidate.batchId)">{{ candidate.batchName || '实习批次' }} · 选择</button></section>
    <StateBlock v-else-if="!compliance.hasData" type="empty" :text="compliance.message || '当前暂无可办理的实习记录'" />
    <template v-else>
      <section class="sp-card hero"><div><h2>{{ compliance.batchName || '本批次上岗准备' }}</h2><p>{{ compliance.currentTask?.reason || (compliance.passed ? '当前上岗条件已满足，仍以学校正式上岗办理为准。' : '请逐项核对学校要求。') }}</p></div><StatusTag :text="compliance.passed ? '上岗合规通过' : '仍有待办条件'" :tone="compliance.passed ? 'success' : 'warn'" /><button type="button" class="sp-btn sp-btn--ghost" :disabled="busy" @click="load">刷新条件与课程</button></section>
      <p v-if="compliance.historyMode" class="sp-notice">当前为历史实习，只能查看已保存的课程及办理结果。</p>
      <div class="compliance-grid"><section v-for="item in visibleItems" :key="item.code" class="sp-card compliance-item"><strong>{{ item.label }}</strong><StatusTag :text="item.statusLabel || itemStatus(item.status)" /><p>{{ item.reason || '该项已满足当前要求' }}</p><button v-if="businessView(item.code)" type="button" class="sp-btn sp-btn--ghost" @click="openBusiness(item.code)">查看{{ item.label }}</button></section></div>
      <section v-if="candidates.length>1" class="sp-card batch-switch"><label>当前批次<select :value="selectedBatchId" :disabled="busy" @change="selectBatch($event.target.value)"><option v-for="candidate in candidates" :key="candidate.recordId" :value="String(candidate.batchId)">{{ candidate.batchName || '实习批次' }}</option></select></label></section>
      <p v-if="actionError" role="alert" class="sp-notice">{{ actionError }} <button type="button" class="sp-btn sp-btn--ghost" :disabled="busy" @click="reloadCourse">重新读取课程结果</button></p><p v-if="receipt" role="status" class="sp-notice is-success">{{ receipt }}</p>
      <div class="two">
        <section class="sp-card"><div class="sp-panel__head">当前批次安全课程</div><StateBlock v-if="!safetyCourses.length" type="empty" text="当前没有安全课程。学校启用安全教育要求时，请联系指导教师核对课程安排。" /><div class="task-list"><button v-for="course in safetyCourses" :key="course.id" type="button" class="task" :class="{'is-active':String(selectedCourse?.id)===String(course.id)}" :disabled="busy" @click="selectCourse(course)"><strong>{{ course.title }}</strong><small>要求 {{ course.requiredMinutes }} 分钟</small><StatusTag :text="safetyStatus(course.completionStatus)" /></button></div></section>
        <section class="sp-card"><div class="sp-panel__head">学习正文与办理</div><StateBlock v-if="courseLoading" type="loading" text="正在读取课程原文…" /><StateBlock v-else-if="courseError" type="error" :text="courseError" /><StateBlock v-else-if="!courseDetail" type="empty" text="请选择一门安全课程" />
          <template v-else><h3>{{ courseDetail.title }}</h3><div class="course-meta"><span>要求 {{ courseDetail.requiredMinutes }} 分钟</span><span>已学习 {{ trustedMinutes }} 分钟</span><span>剩余尝试 {{ courseDetail.remainingAttempts ?? '待核对' }}</span></div><article class="doc">{{ courseDetail.contentSnapshot || '课程正文未配置，请联系学校核对。' }}</article>
            <div v-if="courseDetail.requireCommitment" class="commitment"><strong>安全承诺</strong><p>本人已阅读当前课程版本正文，承诺遵守岗位安全操作规程，发现风险立即停止作业并报告。</p><button v-if="completion?.status==='IN_PROGRESS' && !completion.commitmentConfirmed && !compliance.historyMode" type="button" class="sp-btn" :disabled="busy || actionBlocked" @click="commitSafety">确认安全承诺</button><StatusTag v-else :text="completion?.commitmentConfirmed ? '已确认安全承诺' : '开始学习后确认'" /></div>
            <div class="actions" v-if="!compliance.historyMode"><button v-if="safetyNeedsStart" type="button" class="sp-btn" :disabled="busy || actionBlocked || safetyNoAttempts || !courseDetail.contentSnapshot" @click="startSafety">{{ safetyNoAttempts ? '已无剩余尝试次数' : completion?.status==='FAILED' ? '重新学习' : '开始学习' }}</button><button v-else-if="completion?.status==='IN_PROGRESS'" type="button" class="sp-btn" :disabled="busy || actionBlocked || !canSubmitSafety" @click="submitSafety">{{ canSubmitSafety ? '提交学习结果' : '完成学习时长和承诺后提交' }}</button><StatusTag v-else :text="safetyStatus(completion?.status)" /></div>
            <p v-if="completion?.status==='PENDING_REVIEW'">学习结果已提交，下一步由学校审核；请稍后重新读取结果。</p><p v-if="completion?.status==='FAILED'">学校审核未通过，请核对意见。重新学习将重新计算本次时长和承诺，历史记录保留。</p><p v-if="completion?.reviewComment">审核意见：{{ completion.reviewComment }}</p>
          </template>
        </section>
      </div>
    </template>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { internshipComplianceApi as api } from '../../services/internshipComplianceApi'
import { currentSessionGeneration } from '../../services/request'
import { systemConfirm } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'
const route=useRoute(),router=useRouter(),session=useSessionStore()
const STORAGE_KEY='student_portal_internship_batch_v1'
const loading=ref(true),error=ref(''),busy=ref(false),selectedBatchId=ref(''),candidates=ref([]),compliance=ref({}),safetyCourses=ref([])
const selectedCourse=ref(null),courseDetail=ref(null),courseLoading=ref(false),courseError=ref(''),actionError=ref(''),receipt=ref(''),actionBlocked=ref(false),now=ref(Date.now())
const identity=computed(()=>JSON.stringify([session.user?.tenantId,session.user?.userId,session.user?.roleCode]))
const needSelect=computed(()=>compliance.value.needSelect===true)
const visibleItems=computed(()=>(compliance.value.items||[]).filter(item=>item.required||item.status!=='NOT_APPLICABLE'))
const completion=computed(()=>courseDetail.value?.completion||null)
const safetyNeedsStart=computed(()=>!completion.value||['NOT_STARTED','FAILED'].includes(completion.value.status))
const safetyNoAttempts=computed(()=>completion.value?.status==='FAILED' && Number(courseDetail.value?.remainingAttempts ?? 0)<=0)
const trustedMinutes=computed(()=>{const saved=Number(completion.value?.studiedMinutes ?? courseDetail.value?.studiedMinutes ?? 0);if(completion.value?.status!=='IN_PROGRESS'||!completion.value.startedAt)return saved;const start=Date.parse(completion.value.startedAt);return Number.isFinite(start)?Math.max(saved,Math.floor((now.value-start)/60000)):saved})
const canSubmitSafety=computed(()=>completion.value?.status==='IN_PROGRESS' && (!courseDetail.value?.requireCommitment||completion.value.commitmentConfirmed) && trustedMinutes.value>=Number(courseDetail.value?.requiredMinutes ?? 0))
let alive=true,sequence=0,courseSequence=0,timer
const rows=data=>Array.isArray(data)?data:Array.isArray(data?.items)?data.items:[]
function capture(){return {sequence,generation:currentSessionGeneration(),identity:identity.value,batch:selectedBatchId.value}}
function current(t){return alive&&t.sequence===sequence&&t.generation===currentSessionGeneration()&&t.identity===identity.value&&t.batch===selectedBatchId.value}
function safetyStatus(s){return ({NOT_STARTED:'未开始',IN_PROGRESS:'学习中',PENDING_REVIEW:'待学校审核',PASSED:'已通过',FAILED:'未通过'})[s]||'未开始'}
function itemStatus(s){return ({VALID:'已满足',EXEMPTED:'已按规定豁免',MISSING:'待补齐',PENDING:'待办理',REJECTED:'未通过',CONFIG_ERROR:'待学校核对配置',NOT_APPLICABLE:'无需办理'})[s]||'状态待核对'}
function businessView(code){return ({studentConsent:'consent',guardianConsent:'consent',enterprise:'selection',position:'application',insurance:'insurance',agreement:'agreement'})[code]||''}
function openBusiness(code){const view=businessView(code);if(!view)return;router.push({path:view==='selection'?'/internship/selection':'/internship',query:{batchId:selectedBatchId.value,...(view==='selection'?{}:{view})}})}
function returnHome(){router.push({path:'/internship',query:selectedBatchId.value?{batchId:selectedBatchId.value}: {}})}
function selectBatch(id){if(busy.value||!/^[1-9]\d*$/.test(String(id)))return;router.replace({path:'/internship/compliance',query:{batchId:String(id)}})}
async function load(){
  const previous=String(selectedCourse.value?.id||''),previousBatch=selectedBatchId.value;sequence++;courseSequence++;loading.value=true;error.value='';busy.value=false;actionError.value='';receipt.value='';actionBlocked.value=false;compliance.value={};safetyCourses.value=[];courseDetail.value=null;selectedCourse.value=null;courseError.value='';courseLoading.value=false
  const raw=route.query.batchId;selectedBatchId.value=''
  if(raw!==undefined && (typeof raw!=='string'||!/^[1-9]\d*$/.test(raw))){loading.value=false;error.value='实习批次定位无效，请从本人实习首页重新进入';return}
  if(raw)selectedBatchId.value=raw;else try{selectedBatchId.value=sessionStorage.getItem(STORAGE_KEY)||''}catch{ /* 当前页面仍可选择批次。 */ }
  let t=capture()
  try{
    const result=await api.compliance('ONBOARD',selectedBatchId.value);if(!current(t))return
    if(!result||typeof result.hasData!=='boolean')throw Error('上岗条件读取结果不完整，请重试')
    compliance.value=result;candidates.value=Array.isArray(result.candidates)?result.candidates:[]
    if(result.needSelect||!result.hasData)return
    if(!/^[1-9]\d*$/.test(String(result.batchId||'')))throw Error('上岗条件缺少批次定位，请重试')
    selectedBatchId.value=String(result.batchId);t=capture();try{sessionStorage.setItem(STORAGE_KEY,selectedBatchId.value)}catch{ /* 显式批次继续有效。 */ }
    const [courses,completions]=await Promise.all([api.safetyCourses(t.batch),api.safetyCompletions(t.batch)]);if(!current(t))return
    if(!Array.isArray(courses)&&!Array.isArray(courses?.items))throw Error('课程列表读取结果不完整，请重试')
    const cmap=new Map(rows(completions).map(row=>[String(row.courseId),row]))
    safetyCourses.value=rows(courses).map(course=>({...course,completionStatus:course.completionStatus||cmap.get(String(course.id))?.status||'NOT_STARTED'}))
    const choice=t.batch===previousBatch?safetyCourses.value.find(course=>String(course.id)===previous):null;if(choice)await selectCourse(choice)
  }catch(e){if(current(t)){error.value=e?.message||'上岗条件读取失败';compliance.value={};safetyCourses.value=[];courseDetail.value=null}}
  finally{if(current(t))loading.value=false}
}
async function selectCourse(course){
  if(busy.value||!course?.id)return;const t=capture(),seq=++courseSequence;selectedCourse.value=course;courseDetail.value=null;courseLoading.value=true;courseError.value='';actionError.value='';actionBlocked.value=false
  try{const data=await api.safetyDetail(course.id);if(!current(t)||seq!==courseSequence)return;if(String(data?.id)!==String(course.id))throw Error('课程返回结果与原课程不一致，请重试');courseDetail.value=data;safetyCourses.value=safetyCourses.value.map(item=>String(item.id)===String(course.id)?{...item,completionStatus:data.completion?.status||data.completionStatus||'NOT_STARTED'}:item)}
  catch(e){if(current(t)&&seq===courseSequence)courseError.value=e?.message||'课程原文读取失败'}finally{if(current(t)&&seq===courseSequence)courseLoading.value=false}
}
async function reloadCourse(){if(busy.value||!selectedCourse.value)return;await selectCourse(selectedCourse.value)}
async function runAction(task,message,confirmation){
  if(busy.value||actionBlocked.value||compliance.value.historyMode||!selectedCourse.value||!courseDetail.value)return
  const t=capture(),seq=courseSequence,id=String(selectedCourse.value.id),version=completion.value?.version
  const valid=()=>current(t)&&seq===courseSequence&&id===String(selectedCourse.value?.id)
  busy.value=true;actionError.value='';receipt.value=''
  try{
    if(confirmation && (!await systemConfirm(confirmation)||!valid()))return
    await task(id,version);if(!valid())return;receipt.value=message;busy.value=false
    const choice=selectedCourse.value;await selectCourse(choice)
    if(!current(t))return
    const latest=await api.compliance('ONBOARD',t.batch);if(current(t))compliance.value=latest
  }catch(e){if(valid()){actionError.value=e?.message||'办理结果未确认，请重新读取课程核对';actionBlocked.value=true}}
  finally{if(valid())busy.value=false}
}
function startSafety(){if(!safetyNeedsStart.value||safetyNoAttempts.value)return;return runAction(id=>api.safetyStart(id),'课程学习已开始；请阅读正文并完成学校要求。')}
function commitSafety(){if(completion.value?.status!=='IN_PROGRESS'||completion.value.commitmentConfirmed)return;const hash=courseDetail.value?.contentHash;return runAction((id,version)=>api.safetyCommit(completion.value.id,{expectedVersion:version,contentHash:hash,deviceDigest:'student-pc'}),'安全承诺已确认。',{title:'确认岗位安全承诺',message:'确认本人已阅读当前课程正文并承诺遵守岗位安全规程？',confirmText:'本人确认并承诺'})}
function submitSafety(){if(!canSubmitSafety.value)return;const minutes=trustedMinutes.value;return runAction((id,version)=>api.safetySubmit(id,{expectedVersion:version,studiedMinutes:minutes,answers:{readAndUnderstood:true}}),'学习结果已提交，下一步由学校审核。')}
watch(()=>[route.query.batchId,identity.value],load,{immediate:true,flush:'sync'})
onMounted(()=>{timer=setInterval(()=>{now.value=Date.now()},15000)})
onBeforeUnmount(()=>{alive=false;sequence++;courseSequence++;clearInterval(timer)})
</script>
<style scoped>
.selector-card{display:flex;flex-direction:column;gap:14px}.candidate{display:flex;justify-content:space-between;align-items:center;text-align:left;padding:14px;border:1px solid var(--line);border-radius:10px;background:#fff;cursor:pointer}.candidate small{display:block;margin-top:4px;color:var(--t3)}.batch-switch{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.batch-switch select{padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:#fff}.hero{display:flex;align-items:center;gap:24px;margin-bottom:16px}.hero>div:first-child{flex:1}.hero h2{margin:4px 0 6px;font-size:22px}.hero__eyebrow{color:var(--pri);font-size:13px;font-weight:600}.hero__score{text-align:right}.hero__score strong{display:block;font-size:30px;color:var(--pri)}.hero__score span{color:var(--t3);font-size:12px}.sp-notice{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:16px 18px;border:1px solid var(--line);border-radius:12px;background:#fff;margin-bottom:16px}.sp-notice.is-warning{border-color:#FFD591;background:#FFFBE6}.sp-notice.is-success{border-color:#B7EB8F;background:#F6FFED}.sp-notice p{margin:6px 0 0}.compliance-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.compliance-item{display:flex;flex-direction:column;gap:12px}.compliance-item__head{display:flex;align-items:center;justify-content:space-between;gap:12px}.required{margin-left:8px;padding:2px 6px;border-radius:5px;background:#FFF1F0;color:#CF1322;font-size:11px}.two{display:grid;grid-template-columns:1fr 1.35fr;gap:18px;align-items:start}.task-list{display:flex;flex-direction:column;gap:8px}.task{all:unset;box-sizing:border-box;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px;border:1px solid var(--line);border-radius:10px;cursor:pointer}.task:hover,.task.is-active{border-color:var(--pri);background:var(--pri-50)}.task strong,.task small{display:block}.task small{margin-top:4px;color:var(--t3)}.kv{display:grid;grid-template-columns:1fr 1fr;gap:12px}.kv div{padding:12px;background:#F7F8FA;border-radius:8px}.kv dt{color:var(--t3);font-size:12px}.kv dd{margin:4px 0 0;color:var(--t1)}.doc-meta{color:var(--t3);font-size:12px;margin-bottom:10px}.doc{white-space:pre-wrap;line-height:1.8;color:var(--t2);max-height:420px;overflow:auto;padding:16px;background:#F7F8FA;border-radius:10px}.actions{display:flex;gap:10px;align-items:center;margin-top:14px}.course-meta{display:flex;gap:18px;color:var(--t3);font-size:12px;margin-bottom:12px}.commitment{margin-top:14px;padding:14px;border:1px solid #FFD591;background:#FFFBE6;border-radius:10px}.commitment p{color:#8B5C00;line-height:1.6}.retry-note{margin-top:12px;padding:10px 12px;border-radius:8px;background:#FFF2F0;color:#A8071A;font-size:13px;line-height:1.6}@media(max-width:1100px){.compliance-grid{grid-template-columns:1fr 1fr}.two{grid-template-columns:1fr}}
</style>
