<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import ApplicationMaterialView from '../components/applicant/ApplicationMaterialView.vue'
import ContactRevealButton from '../components/applicant/ContactRevealButton.vue'
import DecisionActions from '../components/applicant/DecisionActions.vue'
const props=defineProps({ applicationId:{type:[String,Number],default:''}, summary:{type:Object,default:null}, campaignWritable:{type:Boolean,default:false} })
const emit=defineEmits(['changed'])
const loading=ref(false),error=ref(''),data=ref(null),material=ref(null)
let loadSeq=0
const id=computed(()=>props.applicationId)
const decisionStatus=computed(()=>data.value?.decisionStatus||'PENDING')
const decisionEffectStatus=computed(()=>data.value?.decisionEffectStatus||'')
const schoolConfirmed=computed(()=>data.value?.applicationStatus==='APPROVED'||data.value?.groupStatus==='APPROVED')
const activeAcceptIntent=computed(()=>decisionStatus.value==='ACCEPT_INTENT'&&decisionEffectStatus.value==='ACTIVE')
const inactiveAcceptIntent=computed(()=>decisionStatus.value==='ACCEPT_INTENT'&&decisionEffectStatus.value&&decisionEffectStatus.value!=='ACTIVE')
const schoolVerified=computed(()=>Boolean(material.value?.schoolFacts?.realName)||data.value?.studentVerified===true)
function displayDateTime(value){if(!value)return '—';const date=new Date(value);return Number.isNaN(date.getTime())?'时间待确认':date.toLocaleString('zh-CN',{hour12:false})}
function mergeSummary(materialData){
  const summary=String(props.summary?.applicationId)===String(id.value)?props.summary:{}
  const facts=materialData?.schoolFacts||{}
  return {
    applicationId:id.value,
    ...summary,
    ...materialData,
    name:facts.realName||summary.name||'学生',
    major:facts.majorName||summary.major||'',
    grade:facts.grade||summary.grade||'',
    positionName:materialData?.positionTitle||summary.positionName||'',
    applicationStatement:materialData?.applicationStatement||summary.applicationStatement||'',
    contactPolicy:materialData?.contactSharingPolicy||summary.contactPolicy||{},
  }
}
async function load(historyPage=1){
  const seq=++loadSeq,target=id.value
  if(!id.value){data.value=null;material.value=null;loading.value=false;error.value='';return}
  loading.value=true;error.value='';data.value=null;material.value=null
  try{
    const materialData=await enterpriseInternshipApi.applicationMaterial(target,historyPage)
    if(seq!==loadSeq||String(target)!==String(id.value))return
    if(String(materialData.applicationId)!==String(target))throw new Error('读取的申请与当前对象不一致，请重新打开')
    material.value=materialData
    data.value=mergeSummary(materialData)
  }catch(e){if(seq===loadSeq){error.value=e.message||'申请材料加载失败';data.value=null;material.value=null}}finally{if(seq===loadSeq)loading.value=false}
}
onMounted(()=>load());watch(id,()=>load());watch(()=>props.summary,()=>{if(material.value)data.value=mergeSummary(material.value)})
async function changed(){await load();emit('changed')}
</script>
<template><div class="detail"><div v-if="loading" class="ep-empty">正在加载申请材料…</div><div v-else-if="error" class="ep-error">{{ error }}</div><div v-else-if="!data" class="ep-empty">从左侧选择一名报名学生查看申请详情。</div><template v-else><header class="head"><div><div class="name-line"><h2>{{ data.name }}</h2><span class="ep-tag">第{{ data.volunteerNo??'—' }}志愿</span><span v-if="schoolVerified" class="ep-tag ok">学校实名学生</span></div><p>{{ data.major||'专业待补充' }} · {{ data.grade||'年级待补充' }} · {{ data.positionName||'申请岗位' }}</p></div></header><div v-if="!campaignWritable" class="history-only">当前招聘季限制新的企业处理；本申请可办理事项及材料、联系方式仍由学校系统分别校验。</div><div v-if="schoolConfirmed" class="locked"><strong>学校已确认岗位</strong><span>企业拟接收已用于本次岗位确认，保留材料及处理历史供核对。</span></div><div v-if="activeAcceptIntent" class="locked"><strong>拟接收 · 等待学校最终确认</strong><span>这仍是企业拟接收意向，不等于正式落岗。</span></div><div v-if="inactiveAcceptIntent && !schoolConfirmed" class="released">本次拟接收已失效或进入后续处理，不能继续作为当前有效企业意向。历史处理事实仍保留。</div><section class="summary"><h3>学校允许查看的学生信息</h3><dl><div><dt>专业 / 年级</dt><dd>{{ data.major||'—' }} / {{ data.grade||'—' }}</dd></div><div><dt>申请岗位</dt><dd>{{ data.positionName||'—' }}</dd></div><div><dt>申请时间</dt><dd>{{ displayDateTime(data.appliedAt) }}</dd></div></dl></section><section class="summary"><h3>联系方式授权</h3><ContactRevealButton :application-id="id" :contact-policy="data.contactPolicy||{}" /></section><ApplicationMaterialView :application-id="id" :material="{...(material||{}),applicationStatement:data.applicationStatement||material?.applicationStatement||''}" /><section class="history"><h3>企业处理记录</h3><div v-if="!(data.decisionHistory||[]).length" class="ep-muted">当前暂无企业处理记录。</div><div v-for="item in (data.decisionHistory||[])" :key="item.id||`${item.status}-${item.at}`" class="history-row"><span>第{{ item.submissionVersion }}次投递 · {{ item.statusLabel }}</span><span>{{ item.effectLabel }}</span><span>{{ displayDateTime(item.decidedAt) }}</span></div><div v-if="data.decisionHistoryTotal > data.decisionHistoryPageSize"><button type="button" class="ep-btn" :disabled="loading || data.decisionHistoryPage<=1" @click="load(data.decisionHistoryPage-1)">上一页记录</button><span>第{{ data.decisionHistoryPage }}页 · 共{{ data.decisionHistoryTotal }}条记录</span><button type="button" class="ep-btn" :disabled="loading || data.decisionHistoryPage*data.decisionHistoryPageSize>=data.decisionHistoryTotal" @click="load(data.decisionHistoryPage+1)">下一页记录</button></div></section><footer class="sticky"><DecisionActions :application="data" :campaign-writable="campaignWritable" @changed="changed" /></footer></template></div></template>
<style scoped>.detail{height:100%;overflow:auto;box-sizing:border-box;padding:22px 24px 90px}.head{display:flex;justify-content:space-between;gap:20px;padding-bottom:18px;border-bottom:1px solid var(--line)}.name-line{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.name-line h2{margin:0;font-size:22px}.head p{margin:8px 0 0;color:var(--t3);font-size:13px}.history-only,.locked,.released{margin:16px 0;padding:13px 14px;border-radius:8px;display:flex;flex-direction:column;gap:5px}.history-only,.locked{background:var(--warn-bg);color:var(--warn-fg)}.released{background:var(--danger-bg);color:var(--danger-fg);line-height:1.6}.summary,.history{padding:18px 0;border-bottom:1px solid var(--line)}h3{font-size:14px;margin:0 0 12px}dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0}dl div{background:#fafbfc;border-radius:8px;padding:10px}dt{font-size:11px;color:var(--t3)}dd{margin:5px 0 0;font-size:13px}.history-row{display:grid;grid-template-columns:1fr 1fr 1.5fr;gap:12px;padding:9px 0;border-top:1px solid var(--line);font-size:12px;color:var(--t2)}.sticky{position:absolute;z-index:6;left:0;right:0;bottom:0;max-height:min(60vh,430px);overflow:auto;box-sizing:border-box;padding:14px 24px;background:#fff;border-top:1px solid var(--line);box-shadow:0 -8px 24px rgba(22,39,67,.08)}@media(max-width:700px){.detail{height:auto;padding:18px 16px 100px}.head{flex-direction:column}dl{grid-template-columns:1fr}.sticky{position:fixed;z-index:10;max-height:min(60vh,430px);padding:12px 16px}}</style>
