<template>
  <div class="sp-page">
    <StateBlock v-if="loading" type="loading" text="正在加载上岗合规状态…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <section v-if="needSelect" class="sp-card selector-card">
        <div>
          <h2>请选择要办理的实习批次</h2>
          <p class="sp-muted">你有多条进行中的实习记录。系统不会替你猜测；选择后，合规状态、知情确认和安全教育均使用同一批次。</p>
        </div>
        <button v-for="candidate in candidates" :key="candidate.recordId" class="candidate"
          @click="selectBatch(candidate.batchId)">
          <span><strong>{{ candidate.batchName || `批次 ${candidate.batchId}` }}</strong><small>状态 {{ candidate.status }} · 记录 {{ candidate.recordId }}</small></span>
          <span>选择 ›</span>
        </button>
      </section>

      <section v-else-if="!compliance.hasData" class="sp-notice">
        <div>
          <strong>暂无可办理的实习记录</strong>
          <p class="sp-muted">{{ compliance.message || '学校建档后，这里会显示知情确认、安全教育和上岗阻断项。' }}</p>
        </div>
        <button class="sp-btn sp-btn--ghost" @click="load">重新加载</button>
      </section>

      <template v-else>
        <section v-if="candidates.length > 1" class="sp-card batch-switch">
          <span>当前实习批次</span>
          <select v-model="selectedBatchId" @change="changeBatch">
            <option v-for="candidate in candidates" :key="candidate.recordId" :value="String(candidate.batchId)">
              {{ candidate.batchName || `批次 ${candidate.batchId}` }} · {{ candidate.status }}
            </option>
          </select>
        </section>

        <section class="sp-card hero">
          <div>
            <div class="hero__eyebrow">{{ compliance.batchName || '岗位实习' }}</div>
            <h2>上岗合规工作台</h2>
            <p class="sp-muted">规则版本 {{ compliance.ruleVersion }} · 评估时间 {{ fmt(compliance.evaluatedAt) }}</p>
          </div>
          <div class="hero__score">
            <strong>{{ Math.round((compliance.completeness?.ratio || 0) * 100) }}%</strong>
            <span>{{ compliance.completeness?.done || 0 }}/{{ compliance.completeness?.required || 0 }} 项完成</span>
          </div>
          <StatusTag :text="compliance.passed ? '上岗合规通过' : '存在上岗阻断'" :tone="compliance.passed ? 'success' : 'danger'" />
        </section>

        <section v-if="compliance.historyMode" class="sp-notice">
          <div><strong>历史实习记录</strong><p class="sp-muted">当前批次已结束，仅可查看历史合规证据，不可继续确认或学习。</p></div>
        </section>

        <section v-if="compliance.currentTask" class="sp-notice" :class="compliance.passed ? 'is-success' : 'is-warning'">
          <div><strong>{{ compliance.passed ? '当前无阻断项' : `当前待办：${compliance.currentTask.label}` }}</strong><p class="sp-muted">{{ compliance.currentTask.reason || '请按学校要求完成当前事项。' }}</p></div>
          <button v-if="compliance.currentTask.code === 'studentConsent'" class="sp-btn" @click="section='consent'">去办理知情确认</button>
          <button v-else-if="compliance.currentTask.code === 'safetyEducation'" class="sp-btn" @click="section='safety'">去完成安全教育</button>
        </section>

        <nav class="sp-tabs">
          <button v-for="item in sections" :key="item.key" class="sp-tab" :class="{'is-active':section===item.key}" @click="section=item.key">{{ item.label }}</button>
        </nav>

        <div v-if="section === 'overview'" class="compliance-grid">
          <section v-for="item in visibleItems" :key="item.code" class="sp-card compliance-item">
            <div class="compliance-item__head"><div><strong>{{ item.label }}</strong><span v-if="item.required" class="required">必需</span></div><StatusTag :text="item.statusLabel" :tone="tone(item.status)" /></div>
            <p class="sp-muted">{{ item.reason || '该项已满足学校当前规则。' }}</p>
            <button v-if="item.code === 'studentConsent'" class="sp-btn sp-btn--ghost" @click="section='consent'">查看知情确认</button>
            <button v-if="item.code === 'safetyEducation'" class="sp-btn sp-btn--ghost" @click="section='safety'">查看安全教育</button>
          </section>
        </div>

        <div v-else-if="section === 'consent'" class="two">
          <section class="sp-card">
            <div class="sp-panel__head">当前批次知情确认任务</div>
            <StateBlock v-if="!filteredConsents.length" type="empty" text="暂无知情确认任务" />
            <div v-else class="task-list">
              <button v-for="item in filteredConsents" :key="item.id" class="task" :class="{'is-active':selectedConsent?.id===item.id}" @click="selectConsent(item)">
                <span><strong>{{ item.consentType === 'GUARDIAN' ? '监护人知情确认' : '学生知情确认' }}</strong><small>正文版本 {{ item.contentVersion || '—' }}</small></span>
                <StatusTag :text="consentStatus(item.status)" :tone="toneConsent(item.status)" />
              </button>
            </div>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">正文与办理</div>
            <StateBlock v-if="!selectedConsent" type="empty" text="请选择知情确认任务" />
            <template v-else-if="selectedConsent.consentType === 'GUARDIAN'">
              <p class="sp-muted">监护人任务仅展示进度，完整联系方式、确认令牌和身份校验信息不会向学生门户暴露。</p>
              <dl class="kv"><div><dt>关系</dt><dd>{{ selectedConsent.participantRelation || '监护人' }}</dd></div><div><dt>联系方式</dt><dd>{{ selectedConsent.contactMasked || '已脱敏' }}</dd></div><div><dt>状态</dt><dd>{{ consentStatus(selectedConsent.status) }}</dd></div></dl>
            </template>
            <template v-else-if="consentDetail">
              <div class="doc-meta">版本 {{ consentDetail.contentVersion }} · 摘要 {{ shortHash(consentDetail.contentHash) }}</div>
              <article class="doc">{{ consentDetail.contentSnapshot || '正文为空，请联系学校管理员。' }}</article>
              <div v-if="consentDetail.status === 'PENDING' && !compliance.historyMode" class="actions">
                <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="rejectConsent">拒绝并说明原因</button>
                <button class="sp-btn" :disabled="busy || !consentDetail.viewedAt" @click="confirmConsent">本人已阅读并确认</button>
              </div>
              <StatusTag v-else :text="consentStatus(consentDetail.status)" :tone="toneConsent(consentDetail.status)" />
            </template>
          </section>
        </div>

        <div v-else class="two">
          <section class="sp-card">
            <div class="sp-panel__head">当前批次必修课程</div>
            <StateBlock v-if="!safetyCourses.length" type="empty" text="暂无安全教育课程；如学校已启用安全门禁，请联系管理员检查课程配置。" />
            <div v-else class="task-list">
              <button v-for="course in safetyCourses" :key="course.id" class="task" :class="{'is-active':selectedCourse?.id===course.id}" @click="selectCourse(course)">
                <span><strong>{{ course.title }}</strong><small>版本 {{ course.courseVersion }} · {{ course.requiredMinutes }} 分钟</small></span>
                <StatusTag :text="safetyStatus(course.completionStatus)" :tone="toneSafety(course.completionStatus)" />
              </button>
            </div>
          </section>
          <section class="sp-card">
            <div class="sp-panel__head">课程学习与提交</div>
            <StateBlock v-if="!selectedCourse" type="empty" text="请选择一门安全教育课程" />
            <template v-else-if="courseDetail">
              <div class="course-meta"><span>要求 {{ courseDetail.requiredMinutes }} 分钟</span><span>已学习 {{ trustedMinutes }} 分钟</span><span>剩余尝试 {{ courseDetail.remainingAttempts }}</span></div>
              <article class="doc">{{ courseDetail.contentSnapshot || '课程正文为空，请联系学校管理员。' }}</article>
              <div v-if="courseDetail.requireCommitment" class="commitment"><strong>安全承诺</strong><p>本人已阅读当前课程版本正文，承诺遵守岗位安全操作规程，发现风险立即停止作业并报告。</p><button v-if="completion?.status === 'IN_PROGRESS' && !completion.commitmentConfirmed && !compliance.historyMode" class="sp-btn sp-btn--ghost" :disabled="busy" @click="commitSafety">确认安全承诺</button><StatusTag v-else-if="completion?.commitmentConfirmed" text="已确认" tone="success" /><StatusTag v-else text="开始本次学习后确认" tone="warn" /></div>
              <p v-if="completion?.status === 'FAILED'" class="retry-note">本次审核未通过。重新学习会重置本次学习时长和承诺，旧结果仍保留在审计记录中。</p>
              <div class="actions" v-if="!compliance.historyMode"><button v-if="safetyNeedsStart" class="sp-btn" :disabled="busy || safetyNoAttempts" @click="startSafety">{{ completion?.status === 'FAILED' ? (safetyNoAttempts ? '已无剩余尝试次数' : '重新学习') : '开始学习' }}</button><button v-else-if="completion?.status === 'IN_PROGRESS'" class="sp-btn" :disabled="busy || !canSubmitSafety" @click="submitSafety">{{ canSubmitSafety ? '提交学习结果' : '完成学习时长和承诺后提交' }}</button><StatusTag v-else :text="safetyStatus(completion?.status)" :tone="toneSafety(completion?.status)" /></div>
            </template>
          </section>
        </div>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { internshipComplianceApi as api } from '../../services/internshipComplianceApi'
import { useUiStore } from '../../stores/ui'

const STORAGE_KEY = 'student_portal_internship_batch_v1'
const ui = useUiStore()
const loading = ref(true), error = ref(''), busy = ref(false), section = ref('overview')
const sections = [{ key: 'overview', label: '合规总览' }, { key: 'consent', label: '知情确认' }, { key: 'safety', label: '安全教育' }]
const selectedBatchId = ref(''), candidates = ref([]), compliance = ref({ items: [], blockers: [], warnings: [] })
const consents = ref([]), selectedConsent = ref(null), consentDetail = ref(null)
const safetyCourses = ref([]), safetyCompletions = ref([]), selectedCourse = ref(null), courseDetail = ref(null)
const now = ref(Date.now())
let timer

const needSelect = computed(() => !!compliance.value.needSelect && !selectedBatchId.value)
const visibleItems = computed(() => (compliance.value.items || []).filter(x => x.required || x.status !== 'NOT_APPLICABLE'))
const filteredConsents = computed(() => (consents.value || []).filter(x => !compliance.value.recordId || String(x.internshipId) === String(compliance.value.recordId)))
const completion = computed(() => courseDetail.value?.completion || null)
const safetyNeedsStart = computed(() => !completion.value || ['NOT_STARTED', 'FAILED'].includes(completion.value.status))
const safetyNoAttempts = computed(() => completion.value?.status === 'FAILED' && Number(courseDetail.value?.remainingAttempts || 0) <= 0)
const trustedMinutes = computed(() => {
  const stored = Number(completion.value?.studiedMinutes || courseDetail.value?.studiedMinutes || 0)
  if (completion.value?.status !== 'IN_PROGRESS' || !completion.value?.startedAt) return stored
  const start = new Date(completion.value.startedAt).getTime()
  return Number.isFinite(start) ? Math.max(stored, Math.floor((now.value - start) / 60000)) : stored
})
const canSubmitSafety = computed(() => !!completion.value && completion.value.status === 'IN_PROGRESS' && (!courseDetail.value.requireCommitment || completion.value.commitmentConfirmed) && trustedMinutes.value >= Number(courseDetail.value.requiredMinutes || 0))

function persistBatch() { try { selectedBatchId.value ? localStorage.setItem(STORAGE_KEY, selectedBatchId.value) : localStorage.removeItem(STORAGE_KEY) } catch { /* storage unavailable */ } }
function selectBatch(id) { selectedBatchId.value = String(id || ''); persistBatch(); selectedConsent.value = null; selectedCourse.value = null; load() }
function changeBatch() { persistBatch(); selectedConsent.value = null; selectedCourse.value = null; load() }
function fmt(v) { return v ? String(v).replace('T', ' ').slice(0, 16) : '—' }
function shortHash(v) { return v ? `${v.slice(0, 10)}…${v.slice(-6)}` : '—' }
function tone(s) { return ['VALID','EXEMPTED','NOT_APPLICABLE'].includes(s) ? 'success' : ['REJECTED','CONFIG_ERROR'].includes(s) ? 'danger' : 'warn' }
function consentStatus(s) { return ({PENDING:'待确认',VALID:'已确认',REJECTED:'已拒绝',REVOKED:'已作废',SUPERSEDED:'已更新',NOT_APPLICABLE:'不适用'})[s] || s }
function toneConsent(s) { return s === 'VALID' ? 'success' : ['REJECTED','REVOKED'].includes(s) ? 'danger' : 'warn' }
function safetyStatus(s) { return ({NOT_STARTED:'未开始',IN_PROGRESS:'学习中',PENDING_REVIEW:'待审核',PASSED:'已通过',FAILED:'未通过'})[s] || s || '未开始' }
function toneSafety(s) { return s === 'PASSED' ? 'success' : s === 'FAILED' ? 'danger' : 'warn' }
function deviceDigest() { try { return [navigator.platform,navigator.userAgent,screen.width,screen.height].filter(Boolean).join('|') || 'student-portal' } catch { return 'student-portal' } }

async function load() {
  loading.value = true; error.value = ''
  try {
    const c = await api.compliance('ONBOARD', selectedBatchId.value)
    compliance.value = c || { items: [], blockers: [], warnings: [] }
    candidates.value = c?.candidates || candidates.value
    if (selectedBatchId.value && candidates.value.length && !candidates.value.some(x => String(x.batchId) === selectedBatchId.value)) { selectedBatchId.value = ''; persistBatch(); compliance.value = await api.compliance('ONBOARD', '') }
    if (compliance.value.needSelect && !selectedBatchId.value) return
    const [cs, courses, completions] = await Promise.all([api.consents(), api.safetyCourses(selectedBatchId.value), api.safetyCompletions(selectedBatchId.value)])
    consents.value = Array.isArray(cs) ? cs : (cs?.items || [])
    safetyCompletions.value = Array.isArray(completions) ? completions : (completions?.items || [])
    const cmap = Object.fromEntries(safetyCompletions.value.map(x => [String(x.courseId), x]))
    safetyCourses.value = (Array.isArray(courses) ? courses : (courses?.items || [])).map(x => ({ ...x, completionStatus: x.completionStatus || cmap[String(x.id)]?.status || 'NOT_STARTED' }))
  } catch (e) { error.value = e?.message || '上岗合规状态加载失败' } finally { loading.value = false }
}
async function selectConsent(item) { selectedConsent.value = item; consentDetail.value = null; if (item.consentType !== 'STUDENT') return; try { let d = await api.consentDetail(item.id); if (d.status === 'PENDING' && !compliance.value.historyMode) d = await api.consentView(item.id); consentDetail.value = d } catch (e) { ui.notify(e?.message || '知情书加载失败') } }
async function refreshConsent() { const id = consentDetail.value?.id || selectedConsent.value?.id; await load(); const latest = filteredConsents.value.find(x => String(x.id) === String(id)); if (latest) await selectConsent(latest) }
async function confirmConsent() { if (!consentDetail.value || busy.value || compliance.value.historyMode) return; if (!confirm(`确认已阅读正文版本 ${consentDetail.value.contentVersion} 并同意按学校实习要求执行？`)) return; busy.value = true; try { await api.consentConfirm(consentDetail.value.id,{expectedVersion:consentDetail.value.version,contentVersion:consentDetail.value.contentVersion,contentHash:consentDetail.value.contentHash,deviceDigest:deviceDigest()}); ui.notify('知情确认已完成'); await load(); selectedConsent.value=null; consentDetail.value=null } catch(e){ ui.notify(e?.message||'确认失败，请刷新后重试'); if(String(e?.code||'').includes('CONFLICT')) await refreshConsent() } finally { busy.value=false } }
async function rejectConsent() { if (!consentDetail.value || busy.value || compliance.value.historyMode) return; const reason=(prompt('请说明无法确认的具体原因（至少5字）')||'').trim(); if(reason.length<5) return ui.notify('拒绝原因至少5个字'); busy.value=true; try{ await api.consentReject(consentDetail.value.id,{expectedVersion:consentDetail.value.version,reason}); ui.notify('拒绝原因已提交'); await load(); selectedConsent.value=null; consentDetail.value=null }catch(e){ ui.notify(e?.message||'提交失败，请重试'); if(String(e?.code||'').includes('CONFLICT')) await refreshConsent() }finally{busy.value=false} }
async function selectCourse(course) { selectedCourse.value=course; courseDetail.value=null; try{courseDetail.value=await api.safetyDetail(course.id)}catch(e){ui.notify(e?.message||'课程详情加载失败')} }
async function startSafety(){ if(!selectedCourse.value||busy.value||safetyNoAttempts.value||compliance.value.historyMode)return; const retry=completion.value?.status==='FAILED'; busy.value=true; try{await api.safetyStart(selectedCourse.value.id);ui.notify(retry?'已重新开始学习':'课程学习已开始');await selectCourse(selectedCourse.value)}catch(e){ui.notify(e?.message||'开始失败')}finally{busy.value=false} }
async function commitSafety(){ if(!completion.value||completion.value.status!=='IN_PROGRESS'||busy.value||compliance.value.historyMode)return;if(!confirm('确认本人已阅读当前课程版本正文并承诺遵守岗位安全规程？'))return;busy.value=true;try{await api.safetyCommit(completion.value.id,{expectedVersion:completion.value.version,contentHash:courseDetail.value.contentHash,deviceDigest:deviceDigest()});ui.notify('安全承诺已确认');await selectCourse(selectedCourse.value)}catch(e){ui.notify(e?.message||'确认失败，请刷新后重试');if(String(e?.code||'').includes('CONFLICT'))await selectCourse(selectedCourse.value)}finally{busy.value=false} }
async function submitSafety(){if(!canSubmitSafety.value||busy.value||compliance.value.historyMode)return;busy.value=true;try{await api.safetySubmit(selectedCourse.value.id,{expectedVersion:completion.value.version,studiedMinutes:trustedMinutes.value,answers:{readAndUnderstood:true}});ui.notify('学习结果已提交审核');await selectCourse(selectedCourse.value);await load()}catch(e){ui.notify(e?.message||'提交失败，请重试');if(String(e?.code||'').includes('CONFLICT'))await selectCourse(selectedCourse.value)}finally{busy.value=false}}

onMounted(() => { try { selectedBatchId.value = localStorage.getItem(STORAGE_KEY) || '' } catch { /* storage unavailable */ } load(); timer = setInterval(() => { now.value = Date.now() }, 15000) })
onBeforeUnmount(()=>{if(timer)clearInterval(timer)})
</script>

<style scoped>
.selector-card{display:flex;flex-direction:column;gap:14px}.candidate{display:flex;justify-content:space-between;align-items:center;text-align:left;padding:14px;border:1px solid var(--line);border-radius:10px;background:#fff;cursor:pointer}.candidate small{display:block;margin-top:4px;color:var(--t3)}.batch-switch{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}.batch-switch select{padding:8px 12px;border:1px solid var(--line);border-radius:8px;background:#fff}.hero{display:flex;align-items:center;gap:24px;margin-bottom:16px}.hero>div:first-child{flex:1}.hero h2{margin:4px 0 6px;font-size:22px}.hero__eyebrow{color:var(--pri);font-size:13px;font-weight:600}.hero__score{text-align:right}.hero__score strong{display:block;font-size:30px;color:var(--pri)}.hero__score span{color:var(--t3);font-size:12px}.sp-notice{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:16px 18px;border:1px solid var(--line);border-radius:12px;background:#fff;margin-bottom:16px}.sp-notice.is-warning{border-color:#FFD591;background:#FFFBE6}.sp-notice.is-success{border-color:#B7EB8F;background:#F6FFED}.sp-notice p{margin:6px 0 0}.compliance-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.compliance-item{display:flex;flex-direction:column;gap:12px}.compliance-item__head{display:flex;align-items:center;justify-content:space-between;gap:12px}.required{margin-left:8px;padding:2px 6px;border-radius:5px;background:#FFF1F0;color:#CF1322;font-size:11px}.two{display:grid;grid-template-columns:1fr 1.35fr;gap:18px;align-items:start}.task-list{display:flex;flex-direction:column;gap:8px}.task{all:unset;box-sizing:border-box;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px;border:1px solid var(--line);border-radius:10px;cursor:pointer}.task:hover,.task.is-active{border-color:var(--pri);background:var(--pri-50)}.task strong,.task small{display:block}.task small{margin-top:4px;color:var(--t3)}.kv{display:grid;grid-template-columns:1fr 1fr;gap:12px}.kv div{padding:12px;background:#F7F8FA;border-radius:8px}.kv dt{color:var(--t3);font-size:12px}.kv dd{margin:4px 0 0;color:var(--t1)}.doc-meta{color:var(--t3);font-size:12px;margin-bottom:10px}.doc{white-space:pre-wrap;line-height:1.8;color:var(--t2);max-height:420px;overflow:auto;padding:16px;background:#F7F8FA;border-radius:10px}.actions{display:flex;gap:10px;align-items:center;margin-top:14px}.course-meta{display:flex;gap:18px;color:var(--t3);font-size:12px;margin-bottom:12px}.commitment{margin-top:14px;padding:14px;border:1px solid #FFD591;background:#FFFBE6;border-radius:10px}.commitment p{color:#8B5C00;line-height:1.6}.retry-note{margin-top:12px;padding:10px 12px;border-radius:8px;background:#FFF2F0;color:#A8071A;font-size:13px;line-height:1.6}@media(max-width:1100px){.compliance-grid{grid-template-columns:1fr 1fr}.two{grid-template-columns:1fr}}
</style>
