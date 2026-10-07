<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { useEnterpriseContextStore } from '../stores/enterpriseContext'
import ChinaRegionPicker from '../components/ChinaRegionPicker.vue'
import { positionListQuery } from '../services/positionNavigation.js'
const route=useRoute(),router=useRouter(),context=useEnterpriseContextStore(),savedDraftId=ref(''),id=computed(()=>route.params.id||savedDraftId.value),loading=ref(true),saving=ref(false),withdrawing=ref(false),error=ref(''),positionStatus=ref(''),positionVersion=ref(null)
const form=reactive({title:'',category:'',headcount:null,workLocation:'',workAddress:'',majorRequirement:'',gradeRequirement:'',mentorContactId:null,workContent:'',remark:'',dailyHours:null,weeklyHours:null,shiftType:'DAY',nightShift:false,overtimeAllowed:false,restDaysPerWeek:null,remunerationType:'MONTHLY',remunerationAmount:null,remunerationCycle:'MONTHLY',salaryRange:'',subsidy:'',accommodationProvided:false,mealProvided:false,hazardousFlag:false,specialEquipment:'',prohibitedReason:''})
const editableKeys=Object.keys(form)
const emptyForm = { ...form }
const baseline = ref(''), notice = ref(''), needsReload = ref(false), createUncertain = ref(false), leaveDialog = ref(null), schoolReturn = ref(null)
const busy = computed(() => saving.value || withdrawing.value)
const dirty = computed(() => !loading.value && baseline.value !== JSON.stringify(form))
const scope = computed(() => String(context.campaign?.id || ''))
const scopeMatches = computed(() => !route.query.campaignId || String(route.query.campaignId) === scope.value)
const returnLocation = computed(() => ({ path: '/positions', query: positionListQuery(route.query) }))
const sections = [{id:'basic',label:'基本信息'},{id:'duties',label:'岗位职责'},{id:'hours',label:'工作安排'},{id:'pay',label:'薪酬福利'},{id:'safety',label:'安全权益'}]
let alive = true, requestSeq = 0, resolveLeave = null, allowSavedNavigation = false
const current = seq => alive && seq === requestSeq
const statusLabels={DRAFT:'草稿',PENDING:'待学校审核',PUBLISHED:'已发布',OFFLINE:'已下线',SUSPENDED:'已暂停',FULL:'已招满',RISK:'风险',ARCHIVED:'已归档'}
const statusText=computed(()=>statusLabels[positionStatus.value]||positionStatus.value||'加载中')
function hasVersion(value){return value!==null&&value!==undefined&&value!==''&&Number.isInteger(Number(value))&&Number(value)>=0}
const canEdit=computed(()=>!loading.value && scopeMatches.value && !needsReload.value && !createUncertain.value && context.recruitmentWritable && positionStatus.value==='DRAFT' && hasVersion(positionVersion.value))
const canWithdraw=computed(()=>!loading.value && scopeMatches.value && !needsReload.value && context.recruitmentWritable && Boolean(id.value) && positionStatus.value==='PENDING'&&hasVersion(positionVersion.value))
const checks=computed(()=>[
  {ok:Boolean(form.title?.trim()),text:'岗位名称已填写',section:'basic'},
  {ok:Number(form.headcount)>0,text:'招聘人数已填写',section:'basic'},
  {ok:Boolean(form.workLocation?.trim()) && Boolean(form.workAddress?.trim()),text:'工作地区与详细地址已填写',section:'basic'},
  {ok:Boolean(form.workContent?.trim()),text:'工作内容已填写',section:'duties'},
  {ok:Number(form.weeklyHours)>0,text:'每周工时已填写',section:'hours'},
  {ok:Boolean(form.salaryRange?.trim()) || (form.remunerationAmount !== null && form.remunerationAmount !== '' && Number(form.remunerationAmount)>=0),text:'报酬条件已填写',section:'pay'},
])
async function scrollSection() {
  if (!sections.some(section => section.id === route.query.section)) return
  await nextTick()
  document.getElementById(`position-${route.query.section}`)?.scrollIntoView({block:'start'})
}
async function goSection(section) {
  await router.replace({ query: { ...route.query, section } })
  await scrollSection()
}
function applySaved(data) {
  if (!hasVersion(data?.version)) { needsReload.value = true; throw new Error('响应缺少岗位版本，请重新读取后核对') }
  positionVersion.value = Number(data.version)
  positionStatus.value = data.status || positionStatus.value
  if (data.schoolReturn !== undefined) schoolReturn.value = data.schoolReturn
  baseline.value = JSON.stringify(form)
}
async function load() {
  if (createUncertain.value && !id.value) return
  const seq = ++requestSeq, pid = route.params.id || savedDraftId.value
  loading.value = true; saving.value = false; withdrawing.value = false; error.value = ''; notice.value = ''; needsReload.value = false
  positionVersion.value = null; positionStatus.value = ''; savedDraftId.value = pid ? String(pid) : ''
  schoolReturn.value = null
  Object.assign(form, emptyForm)
  try {
    if (!scopeMatches.value || !context.recruitmentContextReady) throw new Error('此岗位链接的招聘季与当前工作区不一致，请重新选择招聘季')
    if (pid) {
      const data = await enterpriseInternshipApi.position(pid)
      if (!current(seq)) return
      if (String(data?.id) !== String(pid)) throw new Error('岗位返回范围不一致，请重新读取')
      for (const key of editableKeys) if (data[key] !== undefined) form[key] = data[key]
      applySaved(data)
      if (!route.params.id) await router.replace({path:`/positions/${pid}/edit`,query:{...positionListQuery(route.query),campaignId:scope.value}})
    } else { positionStatus.value = 'DRAFT'; positionVersion.value = 0 }
    baseline.value = JSON.stringify(form)
  } catch (e) { if (current(seq)) { needsReload.value = true; error.value = e.message || '岗位加载失败' } }
  finally { if (current(seq)) { loading.value = false; baseline.value = JSON.stringify(form); await scrollSection() } }
}
async function save(submit=false) {
  if (busy.value || !canEdit.value) return
  if (!form.title?.trim()) { error.value = '请填写岗位名称'; await goSection('basic'); return }
  if (!Number.isInteger(Number(form.headcount)) || Number(form.headcount) < 1 || Number(form.headcount) > 100000) { error.value = '招聘人数须为 1 至 100000 的整数'; await goSection('basic'); return }
  if (submit && checks.value.some(check => !check.ok)) { error.value = '请完善右侧列出的提交资料后再试'; await goSection(checks.value.find(check => !check.ok).section); return }
  const seq = requestSeq
  let phase = id.value ? 'update' : 'create'
  saving.value = true; error.value = ''; notice.value = ''
  try {
    let pid = id.value, version = positionVersion.value
    if (pid) {
      const saved = await enterpriseInternshipApi.updatePosition(pid,{...form,expectedVersion:version})
      if (!current(seq)) return
      applySaved(saved)
    } else {
      const created = await enterpriseInternshipApi.createPosition({...form})
      if (!current(seq)) return
      if (!created?.id) { createUncertain.value = true; throw new Error('创建结果缺少岗位编号，请返回列表核对，避免重复建单') }
      pid = String(created.id); savedDraftId.value = pid
      // Save the server identity before any submission or navigation can fail.
      applySaved(created)
      await router.replace({path:`/positions/${pid}/edit`,query:{...positionListQuery(route.query),campaignId:scope.value,...(route.query.section?{section:route.query.section}:{})}})
      if (!current(seq)) return
    }
    version = positionVersion.value
    notice.value = '草稿已保存，可继续修改或提交学校审核。'
    if (submit) {
      phase = 'submit'
      const submitted = await enterpriseInternshipApi.submitPosition(pid,version)
      if (!current(seq)) return
      applySaved(submitted)
      notice.value = '岗位已提交学校审核。'
    }
    phase = 'navigation'
    allowSavedNavigation = true
    try { await router.push(returnLocation.value) } finally { allowSavedNavigation = false }
  } catch (e) {
    if (!current(seq)) return
    const uncertain = !e.status || Number(e.status) >= 500 || e.network
    if (phase === 'create' && !id.value && uncertain) createUncertain.value = true
    if (phase !== 'navigation' && id.value && (uncertain || Number(e.status) === 409)) needsReload.value = true
    error.value = e.message || '岗位保存失败'
    if (phase === 'submit') notice.value = '草稿已保存，提交尚未确认。请核对提示后继续办理同一岗位。'
  } finally { if (current(seq)) saving.value = false }
}
async function withdraw() {
  if (busy.value || !canWithdraw.value) return
  const seq = requestSeq, pid = id.value
  withdrawing.value = true; error.value = ''
  try {
    const data = await enterpriseInternshipApi.withdrawPosition(pid,positionVersion.value)
    if (!current(seq)) return
    applySaved(data); notice.value = '已撤回到草稿，可修改后重新提交。'
  } catch (e) { if (current(seq)) { needsReload.value = true; error.value = e.message || '撤回岗位失败，请重新读取确认状态' } }
  finally { if (current(seq)) withdrawing.value = false }
}
function finishLeave(allow) { leaveDialog.value?.close(); const resolve = resolveLeave; resolveLeave = null; resolve?.(allow) }
function confirmLeave() {
  if (busy.value) return false
  if (!dirty.value) return true
  if (resolveLeave) return false
  return new Promise(resolve => { resolveLeave = resolve; leaveDialog.value?.showModal() })
}
async function reload() { if (await confirmLeave()) await load() }
function beforeUnload(event) { if (dirty.value || busy.value) { event.preventDefault(); event.returnValue = '' } }
onBeforeRouteLeave(() => allowSavedNavigation || confirmLeave())
onBeforeRouteUpdate((to,from) => {
  if (String(to.query?.campaignId || scope.value) !== String(from.query?.campaignId || scope.value)) return confirmLeave()
  return String(to.params.id || '') === String(from.params.id || '') || String(to.params.id || '') === savedDraftId.value ? true : confirmLeave()
})
watch(() => [String(route.params.id || ''), scope.value, context.recruitmentContextReady, String(route.query.campaignId || '')], (next,previous) => {
  if (next.every((value,index) => value === previous[index])) return
  if (scopeMatches.value && next[1] === previous[1] && next[2] === previous[2] && next[0] && next[0] === savedDraftId.value) return
  savedDraftId.value = next[0]; createUncertain.value = false; load()
}, {flush:'sync'})
watch(() => route.query.section, scrollSection)
onMounted(() => { load(); window.addEventListener('beforeunload',beforeUnload) })
onBeforeUnmount(() => { alive = false; requestSeq++; finishLeave(false); window.removeEventListener('beforeunload',beforeUnload) })
</script>
<template><section class="ep-page position-workspace"><RouterLink class="back-link" :to="returnLocation">← 返回岗位列表</RouterLink><div class="ep-page-head"><div><h1 class="ep-title">{{ id?'岗位详情':'创建实习岗位' }}</h1><p class="ep-subtitle">草稿可编辑；待学校审核的岗位需先撤回后再修改；发布结果由学校统一审核。</p></div><span v-if="id" class="ep-tag" :class="{warn:positionStatus==='PENDING',ok:positionStatus==='PUBLISHED'}">{{ statusText }}</span></div><div v-if="!context.recruitmentWritable" class="history-note">当前招聘季不可编辑：页面保留岗位信息查看，企业提交和修改操作已关闭。</div><div v-else-if="positionStatus==='PENDING'" class="history-note">岗位正在学校审核中。为避免审核期间信息变化，当前仅可查看；需要修改请先撤回到草稿。</div><div v-else-if="id && positionStatus!=='DRAFT'" class="history-note">当前岗位状态为“{{ statusText }}”，本页仅可查看。企业不能直接修改为已发布状态。</div><section v-if="schoolReturn" class="school-return" aria-labelledby="school-return-title"><h2 id="school-return-title">学校上次退回意见</h2><p>{{ schoolReturn.reason }}</p><small>请按意见修改原岗位，再提交学校审核。已重新提交或发布的记录保留该意见供查阅。</small></section><div v-if="error" class="ep-error" role="alert">{{ error }}<button v-if="!createUncertain && scopeMatches" class="ep-btn" type="button" :disabled="busy" @click="reload">重新读取并核对</button><RouterLink v-if="!scopeMatches" to="/campaign-select" class="back-link">选择招聘季</RouterLink></div><div v-if="createUncertain" class="history-note" role="alert">创建结果尚未确认。请先返回岗位列表核对，避免重复创建。</div><div v-if="notice" class="save-notice" role="status">{{ notice }}</div><nav class="section-nav" aria-label="岗位资料分区"><button v-for="section in sections" :key="section.id" type="button" :class="{active:route.query.section===section.id}" @click="goSection(section.id)">{{ section.label }}</button></nav><div v-if="loading" class="ep-card ep-empty">正在加载岗位…</div><div v-else class="form-layout"><div class="sections"><section id="position-basic" class="ep-card panel"><h2>1. 基本信息</h2><div class="fields"><label>岗位名称 *<input v-model="form.title" class="ep-input" :disabled="!canEdit || busy"></label><label>岗位类别<input v-model="form.category" class="ep-input" :disabled="!canEdit || busy"></label><label>招聘人数 *<input v-model.number="form.headcount" type="number" min="1" class="ep-input" :disabled="!canEdit || busy"></label><div class="fieldbox"><span class="fieldbox__label">工作城市 / 地区 *</span><ChinaRegionPicker v-model="form.workLocation" :disabled="!canEdit || busy" placeholder="选择省 / 市 / 区县" /></div><label class="wide">详细工作地址 *<input v-model="form.workAddress" class="ep-input" :disabled="!canEdit || busy"></label><label>专业要求<input v-model="form.majorRequirement" class="ep-input" :disabled="!canEdit || busy"></label><label>年级要求<input v-model="form.gradeRequirement" class="ep-input" :disabled="!canEdit || busy"></label></div></section><section id="position-duties" class="ep-card panel"><h2>2. 岗位职责 / 要求</h2><label>工作内容 *<textarea v-model="form.workContent" class="ep-textarea" rows="6" :disabled="!canEdit || busy" /></label><label>补充说明<textarea v-model="form.remark" class="ep-textarea" rows="3" :disabled="!canEdit || busy" /></label></section><section id="position-hours" class="ep-card panel"><h2>3. 工作安排</h2><div class="fields"><label>每日工时 *<input v-model.number="form.dailyHours" type="number" min="0" max="24" class="ep-input" :disabled="!canEdit || busy"></label><label>每周工时 *<input v-model.number="form.weeklyHours" type="number" min="0" class="ep-input" :disabled="!canEdit || busy"></label><label>班次<select v-model="form.shiftType" class="ep-select" :disabled="!canEdit || busy"><option value="DAY">白班</option><option value="ROTATING">轮班</option></select></label><label>每周休息天数 *<input v-model.number="form.restDaysPerWeek" type="number" min="0" max="7" class="ep-input" :disabled="!canEdit || busy"></label><label class="check"><input v-model="form.nightShift" type="checkbox" :disabled="!canEdit || busy">存在夜班</label><label class="check"><input v-model="form.overtimeAllowed" type="checkbox" :disabled="!canEdit || busy">允许加班</label></div></section><section id="position-pay" class="ep-card panel"><h2>4. 薪酬福利</h2><div class="fields"><label>报酬类型<select v-model="form.remunerationType" class="ep-select" :disabled="!canEdit || busy"><option value="MONTHLY">月薪</option><option value="DAILY">日薪</option><option value="HOURLY">时薪</option></select></label><label>报酬金额<input v-model.number="form.remunerationAmount" type="number" min="0" class="ep-input" :disabled="!canEdit || busy"></label><label>发放周期<select v-model="form.remunerationCycle" class="ep-select" :disabled="!canEdit || busy"><option value="MONTHLY">每月</option><option value="WEEKLY">每周</option><option value="ONCE">一次性</option></select></label><label>薪资展示<input v-model="form.salaryRange" class="ep-input" placeholder="如 3500-4500/月" :disabled="!canEdit || busy"></label><label>补贴<input v-model="form.subsidy" class="ep-input" :disabled="!canEdit || busy"></label><label class="check"><input v-model="form.accommodationProvided" type="checkbox" :disabled="!canEdit || busy">提供住宿</label><label class="check"><input v-model="form.mealProvided" type="checkbox" :disabled="!canEdit || busy">提供餐食</label></div></section><section id="position-safety" class="ep-card panel"><h2>5. 安全权益</h2><label class="check"><input v-model="form.hazardousFlag" type="checkbox" :disabled="!canEdit || busy">危险 / 特殊岗位</label><label>特殊设备<input v-model="form.specialEquipment" class="ep-input" :disabled="!canEdit || busy"></label><label>禁止安排说明<textarea v-model="form.prohibitedReason" class="ep-textarea" rows="3" :disabled="!canEdit || busy" /></label></section></div><aside class="ep-card preview"><h2 class="ep-section-title">提交学校审核前检查</h2><button v-for="check in checks" :key="check.text" type="button" class="check-row" :class="check.ok?'ok':'warn'" @click="goSection(check.section)">{{ check.ok?'✓':'!' }} {{ check.text }}</button><p v-if="form.nightShift" class="ep-muted">包含夜班安排，请提交学校进一步核验。</p><p class="ep-muted">这里只做提交前检查；岗位最终是否发布，以学校审核结果为准。</p></aside></div><div class="actions"><span class="save-state">{{ busy ? '正在办理，请稍候…' : dirty ? '有未保存的修改' : id ? '当前记录已保存' : '填写后可先保存草稿' }}</span><RouterLink :to="returnLocation" class="ep-btn">返回列表</RouterLink><button v-if="canWithdraw" class="ep-btn" :disabled="busy" @click="withdraw">{{ withdrawing?'撤回中…':'撤回到草稿修改' }}</button><template v-if="canEdit"><button class="ep-btn" :disabled="busy" @click="save(false)">保存草稿</button><button class="ep-btn ep-btn-primary" :disabled="busy" @click="save(true)">提交学校审核</button></template></div><dialog ref="leaveDialog" class="leave-dialog" aria-labelledby="leave-title" @cancel.prevent="finishLeave(false)"><h2 id="leave-title">有尚未保存的修改</h2><p>离开后，本次未保存的填写内容将丢失。</p><div><button class="ep-btn" type="button" autofocus @click="finishLeave(false)">继续填写</button><button class="ep-btn ep-btn-primary" type="button" @click="finishLeave(true)">放弃修改并离开</button></div></dialog></section></template>
<style scoped>.history-note{padding:12px 14px;margin-bottom:14px;background:var(--warn-bg);color:var(--warn-fg);border-radius:8px;font-size:13px}.form-layout{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:16px;align-items:start}.sections{display:grid;gap:14px}.panel,.preview{padding:20px}.panel h2{font-size:16px;margin:0 0 16px}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}label{display:flex;flex-direction:column;gap:7px;font-size:13px;color:var(--t2);margin-bottom:13px}.fields label{margin-bottom:0}.fieldbox{display:flex;flex-direction:column;gap:7px;font-size:13px;color:var(--t2)}.fieldbox__label{font-size:13px;color:var(--t2)}.wide{grid-column:1/-1}.check{flex-direction:row;align-items:center;min-height:40px}.ep-input,.ep-select,.ep-textarea{width:100%}.preview{position:sticky;top:78px}.check-row{padding:9px 0;border-bottom:1px solid var(--line);font-size:13px}.check-row.ok{color:var(--ok-fg)}.check-row.warn{color:var(--warn-fg)}.actions{display:flex;justify-content:flex-end;gap:10px;position:sticky;bottom:0;background:linear-gradient(transparent,var(--page) 30%);padding:24px 0 6px}@media(max-width:1000px){.form-layout{grid-template-columns:1fr}.preview{position:static}}@media(max-width:700px){.fields{grid-template-columns:1fr}.wide{grid-column:auto}}</style>

<style scoped>
.back-link{display:inline-flex;color:var(--pri);font-size:13px;text-decoration:none;margin-bottom:14px;min-height:32px;align-items:center}.position-workspace .ep-page-head{margin-bottom:16px}.section-nav{display:flex;gap:6px;padding:8px;margin:14px 0;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:auto}.section-nav button{border:0;background:transparent;color:var(--t2);min-height:36px;white-space:nowrap;padding:0 16px;border-radius:6px}.section-nav button:hover,.section-nav button.active{background:var(--pri-50);color:var(--pri)}.panel{scroll-margin-top:90px}.check-row{display:block;width:100%;background:transparent;border:0;text-align:left;cursor:pointer;line-height:1.7}.save-notice{padding:12px 16px;color:var(--ok-fg);background:var(--ok-bg);border-radius:8px;font-size:13px}.ep-error .ep-btn{margin-left:14px}.save-state{margin-right:auto;color:var(--t3);font-size:12px;align-self:center}.actions{align-items:center;background:var(--card);border-top:1px solid var(--line);padding:12px 16px;box-shadow:0 -6px 22px rgba(20,40,70,.04);border-radius:10px}.leave-dialog{border:1px solid var(--line);border-radius:14px;padding:24px;max-width:min(440px,calc(100vw - 40px));color:var(--t1)}.leave-dialog::backdrop{background:rgba(18,32,54,.36)}.leave-dialog h2{font-size:18px;margin-top:0}.leave-dialog p{color:var(--t2);line-height:1.7}.leave-dialog>div{display:flex;justify-content:flex-end;gap:10px;margin-top:22px}button:focus-visible,a:focus-visible{outline:2px solid var(--pri);outline-offset:3px}@media(max-width:700px){.save-state{flex-basis:100%}.actions{flex-wrap:wrap;padding-bottom:max(12px,env(safe-area-inset-bottom))}.section-nav button{padding:0 12px}.ep-error .ep-btn{display:block;margin:10px 0 0}.leave-dialog>div{flex-wrap:wrap}}
</style>

<style scoped>.school-return{margin:16px 0;padding:18px 20px;background:var(--warn-bg);border:1px solid #f0d8ad;border-radius:10px}.school-return h2{font-size:15px;margin:0 0 10px;color:var(--warn-fg)}.school-return p{margin:0 0 10px;line-height:1.8;font-size:14px;color:var(--t1);white-space:pre-wrap;overflow-wrap:anywhere}.school-return small{line-height:1.6;color:var(--t2)}</style>
