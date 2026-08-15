<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import ApplicationMaterialView from '../components/applicant/ApplicationMaterialView.vue'
import ContactRevealButton from '../components/applicant/ContactRevealButton.vue'
import DecisionActions from '../components/applicant/DecisionActions.vue'
const props=defineProps({ applicationId:{type:[String,Number],default:''}, summary:{type:Object,default:null}, campaignWritable:{type:Boolean,default:false} })
const emit=defineEmits(['changed'])
const loading=ref(false),error=ref(''),data=ref(null),material=ref(null)
const id=computed(()=>props.applicationId)
const groupStatus=computed(()=>data.value?.volunteerGroupStatus||'')
const releaseReason=computed(()=>data.value?.releaseReason||'')
const decisionStatus=computed(()=>data.value?.decisionStatus||'')
const schoolVerified=computed(()=>Boolean(material.value?.schoolFacts?.realName)||data.value?.studentVerified===true)
function mergeSummary(materialData){
  const summary=props.summary||{}
  const facts=materialData?.schoolFacts||{}
  return {
    applicationId:id.value,
    ...summary,
    name:facts.realName||summary.name||'学生',
    major:facts.majorName||summary.major||'',
    grade:facts.grade||summary.grade||'',
    positionName:materialData?.positionTitle||summary.positionName||summary.position_name||'',
    applicationStatement:materialData?.applicationStatement||summary.applicationStatement||'',
  }
}
async function load(){
  if(!id.value){data.value=null;material.value=null;return}
  loading.value=true;error.value=''
  try{
    const materialData=await enterpriseInternshipApi.applicationMaterial(id.value)
    material.value=materialData
    data.value=mergeSummary(materialData)
  }catch(e){error.value=e.message||'申请材料加载失败';data.value=null;material.value=null}finally{loading.value=false}
}
onMounted(load);watch(id,load);watch(()=>props.summary,()=>{if(material.value)data.value=mergeSummary(material.value)})
async function changed(){await load();emit('changed')}
</script>
<template><div class="detail"><div v-if="loading" class="ep-empty">正在加载申请材料…</div><div v-else-if="error" class="ep-error">{{ error }}</div><div v-else-if="!data" class="ep-empty">从左侧选择一名报名学生查看申请详情。</div><template v-else><header class="head"><div><div class="name-line"><h2>{{ data.name }}</h2><span class="ep-tag">第{{ data.volunteerNo??'—' }}志愿</span><span v-if="schoolVerified" class="ep-tag ok">学校实名学生</span></div><p>{{ data.major||'专业待补充' }} · {{ data.grade||'年级待补充' }} · {{ data.positionName||'申请岗位' }}</p></div><div v-if="data.matchPercent" class="match">{{ data.matchPercent }}%<small>岗位匹配</small></div></header><div v-if="!campaignWritable" class="history-only">当前招聘季未开放企业处理权限：申请材料仍可查看，新的处理动作暂不可用。</div><div v-if="groupStatus==='LOCKED' && decisionStatus==='ACCEPT_INTENT'" class="locked"><strong>拟接收 · 等待学校最终确认</strong><span>学校审核截止时间：{{ data.teacherConfirmDeadline||'—' }}</span></div><div v-if="groupStatus==='NEEDS_REVISION' && (releaseReason==='TEACHER_CONFIRM_TIMEOUT' || data.acceptIntentReleased)" class="released">学校未在确认期限内完成最终确认，本次拟接收已释放，申请状态可能发生变化。历史处理记录仍会保留。</div><section class="summary"><h3>学校允许查看的学生信息</h3><dl><div><dt>专业 / 年级</dt><dd>{{ data.major||'—' }} / {{ data.grade||'—' }}</dd></div><div><dt>申请岗位</dt><dd>{{ data.positionName||'—' }}</dd></div><div><dt>申请时间</dt><dd>{{ data.appliedAt||'—' }}</dd></div></dl></section><section class="summary"><h3>联系方式授权</h3><ContactRevealButton :application-id="id" :contact-policy="data.contactPolicy||{}" /></section><ApplicationMaterialView :material="{...(material||{}),applicationStatement:data.applicationStatement||material?.applicationStatement||''}" /><section class="history"><h3>企业处理记录</h3><div v-if="!(data.decisionHistory||[]).length" class="ep-muted">当前暂无企业处理记录。</div><div v-for="item in (data.decisionHistory||[])" :key="item.id||`${item.status}-${item.at}`" class="history-row"><span>{{ item.status }}</span><span>{{ item.effectStatus||'—' }}</span><span>{{ item.at||item.createdAt||'—' }}</span></div></section><footer class="sticky"><DecisionActions :application="data" :campaign-writable="campaignWritable" @changed="changed" /></footer></template></div></template>
<style scoped>.detail{padding:22px 24px 90px}.head{display:flex;justify-content:space-between;gap:20px;padding-bottom:18px;border-bottom:1px solid var(--line)}.name-line{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.name-line h2{margin:0;font-size:22px}.head p{margin:8px 0 0;color:var(--t3);font-size:13px}.match{font-size:24px;color:var(--pri);font-weight:800;text-align:right}.match small{display:block;color:var(--t3);font-size:11px;font-weight:400}.history-only,.locked,.released{margin:16px 0;padding:13px 14px;border-radius:8px;display:flex;flex-direction:column;gap:5px}.history-only,.locked{background:var(--warn-bg);color:var(--warn-fg)}.released{background:var(--danger-bg);color:var(--danger-fg);line-height:1.6}.summary,.history{padding:18px 0;border-bottom:1px solid var(--line)}h3{font-size:14px;margin:0 0 12px}dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:0}dl div{background:#fafbfc;border-radius:8px;padding:10px}dt{font-size:11px;color:var(--t3)}dd{margin:5px 0 0;font-size:13px}.history-row{display:grid;grid-template-columns:1fr 1fr 1.5fr;gap:12px;padding:9px 0;border-top:1px solid var(--line);font-size:12px;color:var(--t2)}.sticky{position:absolute;left:0;right:0;bottom:0;padding:14px 24px;background:#fff;border-top:1px solid var(--line)}@media(max-width:700px){.detail{padding:18px 16px 100px}.head{flex-direction:column}.match{text-align:left}dl{grid-template-columns:1fr}.sticky{position:fixed;z-index:10}}</style>
