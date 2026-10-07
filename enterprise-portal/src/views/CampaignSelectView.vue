<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { setSelectedCampaignId } from '../services/request'

// Authority contract: 不允许选择 companyId，企业范围由登录成员关系决定。
const router = useRouter(), loading = ref(true), error = ref(''), items = ref([]), entering = ref('')
let alive = true, sequence = 0
const available = item => item.participationStatus === 'ACCEPTED' && item.recruitmentAvailable === true
const historical = item => ['CLOSED', 'ARCHIVED'].includes(item.status)
const activeItems = computed(() => items.value.filter(item => available(item) && !historical(item)))
const historyItems = computed(() => items.value.filter(item => available(item) && historical(item)))
const collaborationItems = computed(() => items.value.filter(item => !available(item) && item.collaborationAvailable === true))
const waitingItems = computed(() => items.value.filter(item => !available(item) && item.collaborationAvailable !== true))
const statusLabel = status => ({ DRAFT: '筹备中', OPEN: '进行中', FROZEN: '已冻结', CLOSED: '已结束', ARCHIVED: '已归档' }[status] || '状态待核对')
function unavailableLabel(item) {
  if (item.participationStatus !== 'ACCEPTED') return ({ INVITED: '待接受邀请', SUSPENDED: '参与已暂停', REVOKED: '参与已撤销', DECLINED: '已谢绝邀请' }[item.participationStatus] || '参与状态待核对')
  return ({ MISSING: '本人尚无访问权限', EXPIRED: '访问有效期已结束', NOT_STARTED: '访问尚未生效', REVOKED: '访问已撤销' }[item.recruitmentAccessStatus] || '访问状态待核对')
}
async function load() {
  if (entering.value) return
  const current = ++sequence
  loading.value = true; error.value = ''
  try {
    const data = await enterpriseInternshipApi.campaigns()
    if (alive && current === sequence) items.value = Array.isArray(data) ? data : (Array.isArray(data?.items) ? data.items : [])
  } catch (e) {
    if (alive && current === sequence) { items.value = []; error.value = e.message || '招聘季列表加载失败' }
  } finally { if (alive && current === sequence) loading.value = false }
}
async function enter(item, mode = 'RECRUITMENT') {
  if (entering.value || loading.value || !alive) return
  if (mode === 'RECRUITMENT' ? !available(item) : mode !== 'COLLABORATION' || item.collaborationAvailable !== true) return
  const id = item.id || item.campaignId
  if (!id) return
  const current = ++sequence
  entering.value = String(id); error.value = ''
  try {
    // Recheck immediately before saving a selection; list data can expire while the page is open.
    const context = mode === 'RECRUITMENT'
      ? await enterpriseInternshipApi.context(id)
      : await enterpriseInternshipApi.collaborationContext(item.batchId)
    if (!alive || current !== sequence) return
    if (mode === 'RECRUITMENT' ? String(context?.campaignId) !== String(id) : String(context?.batchId) !== String(item.batchId)) throw new Error('办理范围已变化，请重新读取后选择')
    setSelectedCampaignId(id)
    await router.push('/home')
  } catch (e) {
    if (alive && current === sequence) error.value = e.message || '当前无法进入，请重新读取后再试'
  } finally { if (alive && current === sequence) entering.value = '' }
}
onMounted(load)
onBeforeUnmount(() => { alive = false; sequence++ })
</script>

<template>
  <main class="select-page"><section class="panel">
    <header class="page-head"><div><div class="brand">跃科 · 企业协同中心</div><h1>选择招聘季</h1><p>按学校安排进入本轮招聘，或继续已有的实习协同。</p></div><button class="ep-btn" type="button" :disabled="loading || !!entering" @click="load">重新读取</button></header>
    <div v-if="error" class="ep-error" role="alert">{{ error }}</div>
    <div v-if="loading" class="ep-card ep-empty" role="status">正在读取当前账号可办理的招聘季…</div>
    <template v-else>
      <section aria-labelledby="current-heading"><div class="section-head"><h2 id="current-heading">当前招聘季</h2><span>{{ activeItems.length }} 个</span></div>
        <div v-if="!activeItems.length" class="ep-card ep-empty">当前没有可进入的招聘季，请查看下方参与状态。</div>
        <div v-else class="campaigns"><button v-for="item in activeItems" :key="item.id || item.campaignId" class="campaign ep-card" type="button" :disabled="!!entering" @click="enter(item)"><div><strong>{{ item.campaignName || item.name }}</strong><span>{{ statusLabel(item.status) }}</span></div><p>{{ item.phaseLabel || '进入后查看岗位报送与学校安排。' }}</p><small>{{ entering === String(item.id || item.campaignId) ? '正在核验访问权限…' : '进入招聘工作台 →' }}</small></button></div>
      </section>
      <section v-if="collaborationItems.length" aria-labelledby="collab-heading"><div class="section-head"><h2 id="collab-heading">实习协同</h2><span>{{ collaborationItems.length }} 个</span></div><div class="campaigns"><button v-for="item in collaborationItems" :key="item.id || item.campaignId" class="campaign ep-card" type="button" :disabled="!!entering" @click="enter(item, 'COLLABORATION')"><div><strong>{{ item.campaignName || item.name }}</strong><span>协同可用</span></div><p>本轮招聘：{{ unavailableLabel(item) }}。可继续已授权的学生指导与评价。</p><small>仅进入实习协同 →</small></button></div></section>
      <section aria-labelledby="history-heading"><div class="section-head"><h2 id="history-heading">历史招聘季</h2><span>{{ historyItems.length }} 个</span></div><div v-if="!historyItems.length" class="ep-card ep-empty">暂无可查阅的历史招聘季</div><div v-else class="campaigns"><button v-for="item in historyItems" :key="item.id || item.campaignId" class="campaign history ep-card" type="button" :disabled="!!entering" @click="enter(item)"><div><strong>{{ item.campaignName || item.name }}</strong><span>{{ statusLabel(item.status) }}</span></div><p>在访问有效期内查阅岗位、申请及企业处理记录。</p><small>进入历史只读视图 →</small></button></div></section>
      <section v-if="waitingItems.length" aria-labelledby="waiting-heading"><div class="section-head"><h2 id="waiting-heading">当前不可进入</h2><span>{{ waitingItems.length }} 个</span></div><article v-for="item in waitingItems" :key="item.id || item.campaignId" class="ep-card waiting-campaign"><div><strong>{{ item.campaignName || item.name }}</strong><span>{{ unavailableLabel(item) }}</span></div><p>{{ item.participationStatus === 'INVITED' ? '请打开学校提供的邀请链接，由受邀联系人确认本轮参与。' : item.recruitmentAccessStatus === 'NOT_STARTED' ? '请在学校设置的访问时间内进入，可稍后重新读取。' : '如需查阅或继续办理，请联系学校核对本人的访问权限。' }}</p></article></section>
    </template>
    <button class="back" type="button" :disabled="!!entering" @click="router.push('/login')">返回登录</button>
  </section></main>
</template>

<style scoped>
.select-page{min-height:100vh;background:var(--page);padding:40px 24px}.panel{max-width:1080px;margin:0 auto;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 24px}.panel>section{min-width:0}.page-head,.panel>.ep-error,.panel>.ep-empty,.back{grid-column:1/-1}.page-head{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:28px}.brand{color:var(--pri);font-weight:800;font-size:13px}.page-head h1{margin:12px 0 8px;font-size:28px}.page-head p{margin:0;color:var(--t3);line-height:1.7}.section-head{display:flex;align-items:center;justify-content:space-between;margin:26px 0 12px}.section-head h2{margin:0;font-size:16px}.section-head span{font-size:12px;color:var(--t3)}.campaigns{display:grid;grid-template-columns:1fr;gap:12px}.campaign{text-align:left;padding:22px;border-color:var(--line);min-width:0}.campaign:not(:disabled):hover{border-color:var(--pri);box-shadow:0 6px 20px rgba(47,107,255,.07)}.campaign:focus-visible,.back:focus-visible{outline:2px solid var(--pri);outline-offset:3px}.campaign:disabled{cursor:wait;opacity:.65}.campaign>div,.waiting-campaign>div{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.campaign strong{font-size:16px;line-height:1.6;overflow-wrap:anywhere}.campaign span{flex-shrink:0;font-size:12px;color:var(--pri);background:var(--pri-50);padding:4px 8px;border-radius:5px}.campaign p,.waiting-campaign p{color:var(--t3);font-size:13px;line-height:1.7}.campaign small{color:var(--pri);font-weight:600}.campaign.history span{color:var(--t3);background:var(--page)}.waiting-campaign{padding:18px 22px;margin-bottom:10px}.waiting-campaign span{font-size:12px;color:var(--warn-fg);text-align:right}.waiting-campaign p{margin-bottom:0}.back{margin-top:24px;min-height:40px;border:0;background:transparent;color:var(--t3)}@media(max-width:700px){.panel{grid-template-columns:1fr}.select-page{padding:24px 16px}.page-head{align-items:flex-start}.page-head h1{font-size:24px}.page-head .ep-btn{flex-shrink:0}.campaign,.waiting-campaign{padding:18px}.waiting-campaign>div{flex-direction:column;gap:6px}}
</style>
