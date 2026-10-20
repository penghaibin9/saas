<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { schoolVolunteerApi } from '../api/school-volunteer.api'
import { AppFilePreview, AppConfirmDialog } from '@/components/common'
import { canCode } from '../composables/permission'
import { downloadAttachment } from '../api/guidance-visit.api'

const route = useRoute(), router = useRouter()
const props = defineProps({ ctx: { type: Object, default: () => ({}) } })
const BASE = '/admin/internship/volunteer-review'
const statuses = [
  { value: 'PENDING', label: '待学校处理' }, { value: 'NEEDS_REVISION', label: '已退回' },
  { value: 'APPROVED', label: '已确认' }, { value: 'ALL', label: '全部记录' }
]
const labels = { DRAFT: '学生草稿', SUBMITTED: '已投递', LOCKED: '企业拟接收', NEEDS_REVISION: '待学生补正', APPROVED: '岗位已确认', CLOSED: '已关闭' }
const decisions = { PENDING: '待企业处理', INTERESTED: '企业感兴趣', INTERVIEW: '邀请面试', ACCEPT_INTENT: '拟接收', REJECTED: '不合适' }
const effects = computed(() => ({ ACTIVE: detail.value?.status === 'NEEDS_REVISION' ? '退回前的企业意见' : '当前有效', EXPIRED: '已过期', SUPERSEDED: '已失效', CONSUMED: '学校已确认' }))
const batchId = computed(() => String(route.query.batchId || ''))
const campaignId = computed(() => String(route.query.campaignId || ''))
const groupId = computed(() => String(route.params.groupId || ''))
const page = computed(() => Math.max(1, Number(route.query.page) || 1))
const status = computed(() => statuses.some(s => s.value === route.query.status) ? route.query.status : 'PENDING')
const campaigns = ref([]), rows = ref([]), total = ref(0), detail = ref(null)
const loading = ref(false), contextLoading = ref(false), error = ref(''), contextError = ref(''), keyword = ref('')
const selectedSection = computed(() => ['choices', 'materials', 'history'].includes(route.query.section) ? route.query.section : 'choices')
const downloadError = ref('')
const currentCampaign = computed(() => campaigns.value.find(c => c.id === campaignId.value))
const profile = computed(() => detail.value?.material?.profileSnapshot?.profile || {})
const materialItems = computed(() => detail.value?.material?.profileSnapshot?.items || [])
const schoolFacts = computed(() => detail.value?.material?.schoolFactSnapshot || {})
const files = computed(() => (detail.value?.material?.attachmentFileIds || []).map((id, i) => ({ id: String(id), name: `投递附件 ${i + 1}`, sensitive: true })))
let alive = true, contextRequest = 0, dataRequest = 0
const title = computed(() => detail.value ? `${detail.value.studentName}的岗位志愿` : '岗位确认')
const studentRecordLocation = computed(() => {
  const id = detail.value?.recordId
  if (!id || !batchId.value || !Array.isArray(props.ctx?.permissionPatterns) || !canCode(props.ctx, 'internship.student.view')) return null
  return { path: `/admin/internship/students/${encodeURIComponent(String(id))}`, query: { batchId: batchId.value, section: 'placement', returnTo: route.fullPath } }
})
const queryKey = computed(() => JSON.stringify([batchId.value, campaignId.value, groupId.value, route.query.status, route.query.keyword, route.query.page]))
const selectedApplication = ref(''), action = ref(null), actionBusy = ref(false), actionError = ref(''), actionStale = ref(false)
const canReview = computed(() => Array.isArray(props.ctx?.permissionPatterns) &&
  (canCode(props.ctx, 'internship.application.review') || canCode(props.ctx, 'internship.recruitment.manage')))
const canHandle = computed(() => canReview.value && detail.value && ['SUBMITTED', 'LOCKED'].includes(detail.value.status) &&
  ['PREPARING', 'READY'].includes(detail.value.recordStatus) && !detail.value.positionId)
const selectableChoices = computed(() => (detail.value?.volunteers || []).filter(choice =>
  choice.currentSubmission && choice.positionAvailable && choice.status === 'PENDING_REVIEW' &&
  (detail.value.status !== 'LOCKED' || choice.id === detail.value.lockedApplicationId)))
const chosen = computed(() => selectableChoices.value.find(choice => choice.id === selectedApplication.value))
const confirmBlock = computed(() => {
  if (!detail.value?.advisorUserId) return '请先分配校内指导教师，再确认岗位。'
  if (detail.value.eligibilityStatus !== 'QUALIFIED') return '学生当前实习资格未通过，暂不能确认岗位。'
  if (detail.value.lockExpired) return '企业拟接收已超时，请退回学生修订。'
  if (detail.value.enterpriseConfirmRequired && detail.value.status !== 'LOCKED') return '等待企业拟接收后，再由学校确认岗位。'
  if (!currentCampaign.value?.schoolConfirmStartAt || !currentCampaign.value?.schoolConfirmEndAt) return '学校确认时间尚未配置。'
  if (currentCampaign.value.status !== 'OPEN') return '招聘季当前未开放学校确认。'
  if (!selectableChoices.value.length) return '本次没有可确认的有效岗位，请核对岗位状态或退回修订。'
  if (!chosen.value) return '请选择本次需要确认的志愿。'
  return ''
})

function askAction(kind) {
  if (!canHandle.value || actionBusy.value || (kind === 'confirm' && confirmBlock.value)) return
  const row = detail.value, choice = chosen.value
  actionError.value = ''; actionStale.value = false
  action.value = { kind, key: queryKey.value, sequence: dataRequest, campaignId: campaignId.value, groupId: groupId.value,
    studentName: row.studentName, positionName: choice?.positionName, companyName: choice?.companyName,
    payload: { expectedGroupVersion: row.version, expectedRecordVersion: row.recordVersion,
      ...(kind === 'confirm' ? { applicationId: choice.id, expectedApplicationVersion: choice.version } : {}) } }
}
async function submitAction({ reason = '' } = {}) {
  const target = action.value
  if (!target || actionBusy.value || actionStale.value || target.key !== queryKey.value || target.sequence !== dataRequest || !canReview.value) return
  if (target.kind === 'return' && (reason.trim().length < 2 || reason.trim().length > 500)) {
    actionError.value = '请填写 2～500 字的退回原因。'; return
  }
  actionBusy.value = true; actionError.value = ''
  try {
    const payload = { ...target.payload, ...(target.kind === 'return' ? { reason: reason.trim() } : {}) }
    const result = await schoolVolunteerApi[target.kind](target.campaignId, target.groupId, payload)
    if (!alive || target.key !== queryKey.value || target.sequence !== dataRequest) return
    detail.value = result; action.value = null; selectedApplication.value = ''
  } catch (e) {
    if (!alive || target.key !== queryKey.value || target.sequence !== dataRequest) return
    actionError.value = e.message || '办理未成功，请重试。'
    actionStale.value = e.status === 409 || e.httpStatus === 409 || e.code === 409001 || e.bizCode === 'DATA_CONFLICT'
  } finally { actionBusy.value = false }
}

function date(value) {
  if (!value) return '未设置'
  const parsed = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`)
  return Number.isNaN(parsed.getTime()) ? '时间不可用' : parsed.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
}
function stateLabel(row) {
  if (row.lockExpired) return '确认已超时'
  if (row.status === 'LOCKED' && row.unlockRequestedAt) return '学生申请改志愿'
  return labels[row.status] || row.status
}
function navigate(changes = {}, id = '') {
  return router.push({ path: id ? `${BASE}/${encodeURIComponent(id)}` : BASE, query: { ...route.query, ...changes, section: undefined } })
}
function changeSection(section) { router.replace({ path: route.path, query: { ...route.query, section } }) }
function filter(nextStatus) { navigate({ status: nextStatus, page: undefined }) }
function search() { navigate({ keyword: keyword.value.trim() || undefined, page: undefined }) }
function changeCampaign(event) { navigate({ campaignId: event.target.value || undefined, page: undefined }) }

async function loadContext() {
  const seq = ++contextRequest
  ++dataRequest
  campaigns.value = []; rows.value = []; detail.value = null; total.value = 0
  action.value = null; selectedApplication.value = ''
  contextError.value = ''; error.value = ''; loading.value = false
  if (!batchId.value) { contextLoading.value = false; return }
  contextLoading.value = true
  try {
    const result = await schoolVolunteerApi.context(batchId.value)
    if (!alive || seq !== contextRequest) return
    campaigns.value = result.items || []
    if (!campaignId.value && campaigns.value.length === 1 && !groupId.value) {
      await router.replace({ path: BASE, query: { ...route.query, campaignId: campaigns.value[0].id } })
    } else await loadData()
  } catch (e) {
    if (alive && seq === contextRequest) contextError.value = e.message || '招聘季加载失败'
  } finally { if (alive && seq === contextRequest) contextLoading.value = false }
}
async function loadData() {
  const seq = ++dataRequest
  keyword.value = String(route.query.keyword || '')
  rows.value = []; detail.value = null; total.value = 0; error.value = ''; downloadError.value = ''
  action.value = null; selectedApplication.value = ''
  if (!campaignId.value || !currentCampaign.value) { loading.value = false; return }
  loading.value = true
  try {
    if (groupId.value) {
      const result = await schoolVolunteerApi.detail(campaignId.value, groupId.value)
      if (!alive || seq !== dataRequest) return
      detail.value = result
      selectedApplication.value = result.lockedApplicationId || ''
    } else {
      const result = await schoolVolunteerApi.list(campaignId.value, { status: status.value, keyword: keyword.value || undefined, page: page.value, pageSize: 20 })
      if (!alive || seq !== dataRequest) return
      rows.value = result.items || []; total.value = result.total || 0
    }
  } catch (e) {
    if (alive && seq === dataRequest) error.value = e.message || '志愿记录加载失败，请重试'
  } finally { if (alive && seq === dataRequest) loading.value = false }
}
async function download(file) {
  downloadError.value = ''
  try { await downloadAttachment(file.id, file.name) }
  catch (e) { downloadError.value = e.message || '附件读取失败，请重试' }
}
watch(batchId, loadContext, { immediate: true })
watch(queryKey, (next, previous) => {
  if (previous && JSON.parse(next)[0] !== JSON.parse(previous)[0]) return
  loadData()
})
onBeforeUnmount(() => { alive = false; contextRequest++; dataRequest++ })
</script>

<template>
  <section class="volunteer-workspace" :aria-busy="loading || contextLoading">
    <header class="vw-header">
      <div>
        <button v-if="groupId" class="vw-back" type="button" @click="navigate()">返回岗位确认</button>
        <h1>{{ title }}</h1>
        <p>{{ groupId ? '核对本次投递材料、企业处理和学校落实结果。' : '按学生整组查看志愿，跟进企业拟接收与学校确认。' }}</p>
      </div>
      <label v-if="!groupId && campaigns.length" class="vw-campaign">招聘季
        <select :value="campaignId" aria-label="选择招聘季" @change="changeCampaign">
          <option value="">请选择招聘季</option>
          <option v-for="campaign in campaigns" :key="campaign.id" :value="campaign.id">{{ campaign.name }}</option>
        </select>
      </label>
    </header>
    <div v-if="contextError" class="vw-state vw-error" role="alert">{{ contextError }} <button @click="loadContext">重新加载</button></div>
    <div v-else-if="contextLoading" class="vw-state" role="status">正在读取当前批次的招聘季…</div>
    <div v-else-if="!batchId" class="vw-state">请先在上方选择实习批次。</div>
    <div v-else-if="!campaigns.length" class="vw-state">当前负责的批次暂无招聘季。自主实习与校内岗位申请可从“申请审核”办理。</div>
    <div v-else-if="!currentCampaign" class="vw-state">{{ campaignId ? '链接中的招聘季不属于当前负责批次，请返回列表重新选择。' : '请选择需要查看的招聘季。' }} <button v-if="groupId" @click="navigate({ campaignId: undefined })">返回列表</button></div>
    <template v-else>
      <div class="vw-context">
        <span>{{ currentCampaign.name }}</span>
        <span v-if="currentCampaign.schoolConfirmStartAt && currentCampaign.schoolConfirmEndAt">学校确认：{{ date(currentCampaign.schoolConfirmStartAt) }} — {{ date(currentCampaign.schoolConfirmEndAt) }}</span><span v-else>学校确认时间尚未配置</span>
        <span v-if="currentCampaign.enterpriseConfirmRequired">须先取得企业拟接收</span>
      </div>
      <template v-if="!groupId">
        <div class="vw-toolbar">
          <nav aria-label="志愿处理状态" class="vw-tabs">
            <button v-for="item in statuses" :key="item.value" :aria-pressed="status === item.value" :class="{ active: status === item.value }" @click="filter(item.value)">{{ item.label }}</button>
          </nav>
          <form class="vw-search" @submit.prevent="search"><input v-model="keyword" type="search" aria-label="学生姓名或学号" placeholder="搜索学生姓名、学号"><button type="submit">搜索</button></form>
        </div>
        <div v-if="error" class="vw-state vw-error" role="alert">{{ error }} <button @click="loadData">重试</button></div>
        <div v-else-if="loading" class="vw-state" role="status">正在读取志愿队列…</div>
        <template v-else>
          <div class="vw-queue">
            <div class="vw-queue-heading"><h2>{{ statuses.find(s => s.value === status)?.label }}</h2><span>{{ total }} 名学生</span><span v-if="status === 'PENDING'" class="vw-queue-note">优先显示改志愿申请与企业拟接收</span></div>
            <div v-if="!rows.length" class="vw-empty"><strong>{{ total ? '这一页暂无记录' : '当前没有符合条件的志愿' }}</strong><p>可调整状态或学生关键词。这里仅展示当前招聘季的正式志愿。</p></div>
            <div v-else class="vw-table-wrap"><table><thead><tr><th>学生 / 投递</th><th>当前进展</th><th>校内指导教师</th><th>学校确认截止</th><th><span class="vw-visually-hidden">操作</span></th></tr></thead>
              <tbody><tr v-for="row in rows" :key="row.id"><td><strong>{{ row.studentName }}</strong><small>{{ row.studentNo }} · 第 {{ row.submissionVersion }} 次投递</small></td><td><span class="vw-status" :data-state="row.lockExpired ? 'NEEDS_REVISION' : row.status">{{ stateLabel(row) }}</span><small>提交于 {{ date(row.submittedAt) }}</small></td><td>{{ row.advisorName || '待分配' }}</td><td :class="{ 'vw-danger': row.lockExpired }">{{ row.teacherConfirmDeadline ? date(row.teacherConfirmDeadline) : '—' }}</td><td><button class="vw-link" :aria-label="`查看${row.studentName}的岗位志愿`" @click="navigate({}, row.id)">查看志愿</button></td></tr></tbody>
            </table></div>
            <footer class="vw-pagination"><span>第 {{ page }} 页</span><button :disabled="page <= 1" @click="navigate({ page: String(page - 1) })">上一页</button><button :disabled="page * 20 >= total" @click="navigate({ page: String(page + 1) })">下一页</button></footer>
          </div>
        </template>
      </template>
      <template v-else>
        <div v-if="error" class="vw-state vw-error" role="alert">{{ error }} <button @click="loadData">重新加载</button></div>
        <div v-else-if="loading" class="vw-state" role="status">正在读取本次投递材料…</div>
        <template v-else-if="detail">
          <section class="vw-identity"><div><span class="vw-status" :data-state="detail.status">{{ stateLabel(detail) }}</span><p>{{ detail.studentNo }} · 第 {{ detail.submissionVersion }} 次投递 · {{ date(detail.submittedAt) }}</p></div><dl><div><dt>校内指导教师</dt><dd>{{ detail.advisorName || '待分配' }}</dd></div><div><dt>学校确认截止</dt><dd>{{ detail.teacherConfirmDeadline ? date(detail.teacherConfirmDeadline) : '—' }}</dd></div></dl></section>
          <div v-if="detail.unlockRequestReason && detail.status === 'LOCKED'" class="vw-notice"><strong>学生申请修改志愿</strong><p>{{ detail.unlockRequestReason }}</p></div>
          <div v-if="detail.revisionReason && detail.status === 'NEEDS_REVISION'" class="vw-notice"><strong>学校退回意见</strong><p>{{ detail.revisionReason }}</p></div>
          <div v-if="detail.status === 'APPROVED'" class="vw-result"><div><strong>已确定：{{ detail.enterpriseName }} · {{ detail.positionName }}</strong><p>岗位确认于 {{ date(detail.approvedAt) }}。协议、保险及上岗核验另行办理。</p></div><RouterLink v-if="studentRecordLocation" class="vw-next" :to="studentRecordLocation">继续实习安排</RouterLink></div>
          <nav class="vw-detail-nav" aria-label="志愿详情内容"><button v-for="section in [{id:'choices',label:'志愿与企业处理'},{id:'materials',label:'本次投递材料'},{id:'history',label:'企业决定历史'}]" :key="section.id" :class="{ active: selectedSection === section.id }" :aria-pressed="selectedSection === section.id" @click="changeSection(section.id)">{{ section.label }}</button></nav>
          <section v-if="selectedSection === 'choices'" class="vw-choices" aria-label="本次志愿">
            <article v-for="choice in detail.volunteers" :key="choice.id" class="vw-choice"><div class="vw-rank">{{ choice.volunteerNo }}<small>志愿</small></div><div class="vw-choice-body"><div class="vw-choice-heading"><div><h2>{{ choice.positionName }}</h2><p>{{ choice.companyName || '企业信息未提供' }}</p></div><span class="vw-status">{{ decisions[choice.enterpriseDecision?.status] || '待企业处理' }}</span></div><p class="vw-statement">{{ choice.applicationStatement || '未填写岗位申请说明' }}</p><div class="vw-choice-meta"><span>{{ choice.currentSubmission ? '对应本次投递材料' : '不属于当前投递材料版本' }}</span><span v-if="choice.enterpriseDecision">{{ effects[choice.enterpriseDecision.effectStatus] || choice.enterpriseDecision.effectStatus }}</span></div><div v-if="choice.enterpriseDecision?.reason" class="vw-decision-note">企业意见：{{ choice.enterpriseDecision.reason }}</div></div></article>
            <div v-if="!detail.volunteers.length" class="vw-state">没有可读取的志愿记录。</div>
          </section>
          <section v-else-if="selectedSection === 'materials'" class="vw-material">
            <template v-if="detail.material"><header><h2>第 {{ detail.material.submissionVersion }} 次投递材料</h2><p>材料在投递时保存，学生后续修改个人档案不会覆盖此版本。</p></header><dl class="vw-facts"><div><dt>专业</dt><dd>{{ schoolFacts.majorName || '未提供' }}</dd></div><div><dt>班级</dt><dd>{{ schoolFacts.className || '未提供' }}</dd></div><div><dt>投递时间</dt><dd>{{ date(detail.submittedAt) }}</dd></div></dl><h3>个人介绍</h3><p class="vw-statement">{{ profile.selfIntro || profile.summary || '本次材料未填写个人介绍' }}</p><article v-for="(item, index) in materialItems" :key="item.id || index" class="vw-material-item"><h3>{{ item.title || item.name || '经历与成果' }}</h3><p class="vw-statement">{{ item.description || item.content || '未填写说明' }}</p></article><h3>投递附件</h3><AppFilePreview v-if="files.length" :files="files" @download="download" /><p v-else>本次投递没有附件。</p><p v-if="downloadError" class="vw-error" role="alert">{{ downloadError }}</p></template>
            <div v-else class="vw-state">未找到当前投递版本的材料，请核对记录后再处理。</div>
          </section>
          <section v-else class="vw-history"><h2>企业决定历史</h2><p>不同投递版本的企业决定分别保留，请以当前投递材料为准。</p><ol v-if="detail.decisionHistory.length"><li v-for="item in detail.decisionHistory" :key="item.id"><div><strong>{{ decisions[item.status] || item.status }}</strong><span>{{ effects[item.effectStatus] || item.effectStatus }}</span></div><small>第 {{ item.submissionVersion }} 次投递 · {{ date(item.decidedAt) }}</small><p v-if="item.reason">{{ item.reason }}</p></li></ol><div v-else class="vw-empty">暂无企业处理记录。</div></section>
          <section v-if="canHandle" class="vw-handling" aria-label="学校办理">
            <div><h2>学校办理</h2><p>确认前核对岗位、当前投递材料与企业意见。岗位确定后，继续办理协议及上岗核验。</p></div>
            <label class="vw-target">确认岗位
              <select v-model="selectedApplication" aria-label="选择确认志愿" :disabled="actionBusy || detail.status === 'LOCKED'">
                <option value="">请选择一个志愿</option>
                <option v-for="choice in selectableChoices" :key="choice.id" :value="choice.id">第 {{ choice.volunteerNo }} 志愿 · {{ choice.companyName }} · {{ choice.positionName }}</option>
              </select>
            </label>
            <p v-if="confirmBlock" class="vw-handle-hint">{{ confirmBlock }}</p>
            <div class="vw-handle-actions">
              <button type="button" class="vw-return" :disabled="actionBusy" @click="askAction('return')">退回学生修订</button>
              <button type="button" class="vw-confirm" :disabled="actionBusy || !!confirmBlock" @click="askAction('confirm')">确认岗位</button>
            </div>
          </section>
        </template>
      </template>
    </template>
    <AppConfirmDialog :visible="!!action" @update:visible="value => { if (!value) action = null }"
      :title="action?.kind === 'return' ? '退回学生修订' : '确认学生岗位'"
      :content="action?.kind === 'return' ? `退回${action.studentName}的本次志愿。如有企业拟接收，将一并解除；请写明学生需要补正的内容。` : `将${action?.studentName}的实习岗位确定为${action?.companyName} · ${action?.positionName}。本组其他待处理志愿将关闭。`"
      :require-reason="action?.kind === 'return'" :reason-min-length="2" reason-label="退回原因"
      :confirm-text="action?.kind === 'return' ? '退回修订' : '确认岗位'" :danger="action?.kind === 'return'"
      :submitting="actionBusy" :confirm-disabled="actionStale" @confirm="submitAction">
      <p v-if="actionError" class="vw-error" role="alert">{{ actionError }}</p>
      <button v-if="actionStale" class="vw-link" type="button" @click="loadData">重新读取当前投递</button>
    </AppConfirmDialog>
  </section>
</template>

<style scoped>
.vw-handling{margin-top:24px;padding:22px;border:1px solid var(--line);border-radius:10px;background:var(--card,#fff)}
.vw-handling h2{font-size:15px;margin:0 0 7px}.vw-handling p{font-size:13px;line-height:1.7;color:var(--t3);margin:0 0 16px}
.vw-target{display:flex;gap:12px;align-items:center;font-size:13px}.vw-target select{flex:1;min-width:0;padding:10px;border:1px solid var(--line);border-radius:6px;background:var(--card,#fff);color:var(--t1)}
.vw-handling .vw-handle-hint{margin:10px 0;color:var(--t2)}.vw-handle-actions{display:flex;justify-content:flex-end;gap:12px;margin-top:18px}.vw-handle-actions button{padding:10px 16px;border:1px solid var(--line);border-radius:6px;background:var(--card,#fff);color:var(--t2)}.vw-handle-actions .vw-confirm{background:var(--primary,#346bba);border-color:var(--primary,#346bba);color:white}
.volunteer-workspace{padding:22px 26px 32px;color:var(--t1,#20334c);font-size:14px;min-width:0}.vw-header{display:flex;align-items:center;justify-content:space-between;gap:24px;margin-bottom:18px}.vw-header h1{font-size:22px;line-height:1.4;letter-spacing:-.4px;margin:0 0 6px}.vw-header p,.vw-material header p,.vw-history>p{color:var(--t3,#65748b);font-size:13px;margin:0;line-height:1.7}.vw-campaign{display:flex;align-items:center;gap:10px;color:var(--t2,#536780);white-space:nowrap}.volunteer-workspace button,.volunteer-workspace input,.volunteer-workspace select{font:inherit}.volunteer-workspace button{cursor:pointer}.volunteer-workspace button:disabled{opacity:.45;cursor:default}.volunteer-workspace :is(button,a,input,select):focus-visible{outline:2px solid var(--primary,#346bba);outline-offset:3px}.vw-campaign select,.vw-search input{height:36px;max-width:340px;padding:0 11px;background:var(--card,#fff);color:var(--t1);border:1px solid var(--line,#dce4ed);border-radius:6px}.vw-context{display:flex;flex-wrap:wrap;gap:8px 22px;color:var(--t3,#65748b);font-size:12px;padding:0 0 18px;border-bottom:1px solid var(--line,#dce4ed)}.vw-context>span:first-child{color:var(--t2);font-weight:600}.vw-toolbar{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:18px 0}.vw-tabs,.vw-detail-nav{display:flex;flex-wrap:wrap;gap:4px}.vw-tabs button,.vw-detail-nav button{border:0;border-radius:6px;padding:9px 13px;background:transparent;color:var(--t2,#536780);white-space:nowrap}.vw-tabs button.active,.vw-detail-nav button.active{color:var(--primary,#346bba);background:var(--primary-soft,#eaf1fc);font-weight:650}.vw-search{display:flex;gap:6px}.vw-search input{width:220px}.vw-search button,.vw-pagination button,.vw-state button{background:var(--card,#fff);border:1px solid var(--line,#dce4ed);color:var(--t2,#536780);padding:7px 12px;border-radius:6px}.vw-queue,.vw-material,.vw-history{border:1px solid var(--line,#dce4ed);background:var(--card,#fff);border-radius:10px;overflow:hidden}.vw-queue-heading{display:flex;align-items:center;gap:12px;padding:18px 20px}.vw-queue-heading h2,.vw-choice h2,.vw-material h2,.vw-history h2{font-size:15px;margin:0;font-weight:650}.vw-queue-heading>span{color:var(--t3);font-size:12px}.vw-queue-note{margin-left:auto}.vw-table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;text-align:left}th{background:var(--bg,#f7f9fc);color:var(--t3);font-weight:500;font-size:12px;padding:11px 20px}td{padding:18px 20px;border-bottom:1px solid var(--line,#e8edf3);white-space:nowrap}td strong{font-weight:650}td small{display:block;margin-top:7px;color:var(--t3);font-size:12px}tbody tr:last-child td{border-bottom:0}.vw-link,.vw-back{border:0;background:transparent;color:var(--primary,#346bba);padding:4px 0}.vw-back{margin-bottom:12px;font-size:12px!important}.vw-status{display:inline-flex;align-items:center;border-radius:4px;background:var(--bg,#f2f5f9);padding:4px 8px;font-size:12px;color:var(--t2,#536780);font-weight:550;white-space:nowrap}.vw-status[data-state=LOCKED]{color:#855914;background:#fff5df}.vw-status[data-state=APPROVED]{color:#267359;background:#eaf6f0}.vw-status[data-state=NEEDS_REVISION]{color:#995144;background:#fff0eb}.vw-pagination{display:flex;align-items:center;justify-content:flex-end;gap:10px;padding:12px 20px;border-top:1px solid var(--line,#e8edf3)}.vw-pagination span{margin-right:5px;color:var(--t3);font-size:12px}.vw-empty,.vw-state{padding:42px 24px;text-align:center;color:var(--t3);line-height:1.8}.vw-empty strong{font-size:15px;color:var(--t2);font-weight:600}.vw-empty p{margin:8px 0 0;font-size:13px}.vw-state button{margin-left:8px}.vw-error,.vw-danger{color:var(--danger,#b34b3f)}.vw-identity{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:22px 0}.vw-identity p{color:var(--t3);font-size:12px;margin:8px 0 0}.vw-identity dl{display:flex;gap:38px;margin:0}dt{font-size:12px;color:var(--t3);margin-bottom:6px}dd{margin:0;font-size:13px}.vw-notice,.vw-result{padding:14px 18px;border-radius:7px;background:#fff5e5;color:#855914;margin-bottom:16px;font-size:13px}.vw-result{background:#eaf6f0;color:#267359}.vw-notice p,.vw-result p{margin:6px 0 0;line-height:1.7;white-space:pre-wrap}.vw-detail-nav{border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:18px}.vw-choices{display:grid;gap:12px}.vw-choice{display:flex;align-items:stretch;gap:18px;border:1px solid var(--line,#dce4ed);background:var(--card,#fff);border-radius:10px;padding:22px}.vw-rank{font-size:23px;color:var(--primary);font-weight:650;border-right:1px solid var(--line);padding-right:18px;min-width:40px;text-align:center}.vw-rank small{display:block;font-size:11px;color:var(--t3);font-weight:400;margin-top:4px}.vw-choice-body{min-width:0;flex:1}.vw-choice-heading{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.vw-choice-heading p{margin:5px 0 0;font-size:13px;color:var(--t2)}.vw-statement{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.8;color:var(--t2);margin:16px 0;font-size:13px}.vw-choice-meta{display:flex;flex-wrap:wrap;gap:14px;color:var(--t3);font-size:12px}.vw-decision-note{margin-top:14px;padding:12px;background:var(--bg,#f7f9fc);font-size:13px;line-height:1.7}.vw-material,.vw-history{padding:24px}.vw-material header p{margin-top:7px}.vw-facts{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:24px 0;padding-bottom:20px;border-bottom:1px solid var(--line)}.vw-material h3{font-size:14px;margin:20px 0 8px}.vw-material-item{border-top:1px solid var(--line)}.vw-history>p{margin-top:8px}.vw-history ol{list-style:none;margin:22px 0 0;padding:0}.vw-history li{padding:16px 0;border-top:1px solid var(--line)}.vw-history li>div{display:flex;justify-content:space-between;gap:16px}.vw-history li span,.vw-history li small{font-size:12px;color:var(--t3)}.vw-history li small{display:block;margin-top:7px}.vw-history li p{font-size:13px;line-height:1.7}.vw-visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}@media(max-width:1100px){.vw-header{align-items:flex-start;flex-direction:column;gap:14px}.vw-toolbar{align-items:flex-start;flex-direction:column}.vw-queue-note{display:none}}@media(max-width:650px){.volunteer-workspace{padding:18px 14px}.vw-header h1{font-size:20px}.vw-campaign{width:100%;white-space:normal}.vw-campaign select{min-width:0;flex:1}.vw-search,.vw-search input{width:100%}.vw-search input{min-width:0}.vw-identity{align-items:flex-start;flex-direction:column;gap:18px}.vw-identity dl{gap:25px}.vw-choice{padding:16px;gap:12px}.vw-choice-heading{flex-direction:column;gap:10px}.vw-rank{padding-right:12px;min-width:28px}.vw-material,.vw-history{padding:18px}.vw-facts{grid-template-columns:1fr}.vw-detail-nav button{padding:10px;font-size:12px}}
.vw-result{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.vw-result>div{flex:1;min-width:220px}
.vw-next{display:inline-flex;align-items:center;justify-content:center;padding:9px 14px;border:1px solid currentColor;border-radius:6px;color:inherit;text-decoration:none;white-space:nowrap;font-weight:600;font-size:13px}
.vw-next:hover{background:rgba(255,255,255,.7)}
</style>
