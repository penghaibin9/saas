<template>
  <div class="gd-workbench">
    <section class="gd-hero">
      <div>
        <p class="gd-eyebrow">毕业论文（设计）工作台</p>
        <h1>按步骤完成我的毕业设计</h1>
        <p>每一步均对应真实材料、审核或整改记录；批次期限和具体要求以学校发布为准。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" :disabled="loading" @click="load">刷新进度</button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在加载你的毕业设计流程…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <section v-if="!my.hasData" class="gd-empty-notice">
        <strong>毕业设计流程尚未启用</strong>
        <p>{{ my.note || my.message || '管理员尚未将你加入毕业设计批次。建档后各步骤会显示真实状态和待办。' }}</p>
      </section>
      <template v-else>
      <section class="gd-summary sp-panel">
        <div><span>我的课题</span><strong>{{ my.topicTitle || '待选题' }}</strong></div>
        <div><span>指导教师</span><strong>{{ my.advisorName || '待分配' }}</strong></div>
        <div><span>当前环节</span><strong>{{ my.stageLabel || my.stage || '待开始' }}</strong></div>
        <div><span>所属批次</span><strong>{{ my.batchName || '—' }}</strong></div>
      </section>

      <section class="gd-tip">
        <strong>办理规则：</strong>上一环节未通过时，后续关键动作会提示等待原因；导师审核、答辩安排和成绩发布由学校端完成。
      </section>

      <ol class="gd-steps">
        <li v-for="step in steps" :key="step.key" class="gd-step" :class="'is-' + step.tone">
          <div class="gd-step__rail"><span>{{ step.order }}</span></div>
          <article>
            <header class="gd-step__head">
              <div><h2>{{ step.title }}</h2><p>{{ step.description }}</p></div>
              <StatusTag :text="step.status" :tone="step.tone" />
            </header>
            <p v-if="step.detail" class="gd-step__detail">{{ step.detail }}</p>
            <p v-if="step.reviewComment" class="gd-step__comment">审核/整改意见：{{ step.reviewComment }}</p>
            <div v-if="step.files?.length" class="gd-files">
              <span>论文材料：</span>
              <button v-for="file in step.files" :key="file.fileId" class="gd-file" :disabled="busy" @click="downloadMaterial(file)">
                下载 {{ file.fileName || '论文材料' }}（可打开打印）
              </button>
            </div>
            <ul v-if="step.checklist?.length" class="gd-checklist">
              <li v-for="item in step.checklist" :key="item.item" :class="{ 'is-missing': !item.present }">
                {{ item.present ? '✓' : '○' }} {{ item.label || item.item }}
              </li>
            </ul>
            <div v-if="step.action" class="gd-step__actions">
              <button class="sp-btn" :disabled="busy" @click="handleAction(step.key)">{{ step.action }}</button>
              <span v-if="step.actionHint" class="sp-muted">{{ step.actionHint }}</span>
            </div>

            <div v-if="expanded === step.key" class="gd-form">
              <template v-if="step.key === 'topic'">
                <p v-if="!round" class="sp-muted">当前没有开放的选题轮次，请等待管理员发布。</p>
                <template v-else>
                  <p class="sp-muted">{{ round.roundName }} · 最多提交 {{ round.maxChoices }} 个志愿。点击题目按顺序选择，可再次点击取消。</p>
                  <div class="gd-topic-list">
                    <button v-for="topic in topics" :key="topic.id" class="gd-topic" :class="{ 'is-picked': selectedTopicIds.includes(String(topic.id)) }" @click="toggleTopic(topic.id)">
                      <b v-if="selectedTopicIds.includes(String(topic.id))">志愿 {{ selectedTopicIds.indexOf(String(topic.id)) + 1 }}</b>
                      <strong>{{ topic.title }}</strong><span>{{ topic.advisorName || '导师待定' }}</span>
                    </button>
                  </div>
                  <button class="sp-btn" :disabled="busy || !selectedTopicIds.length" @click="submitChoices">提交志愿</button>
                </template>
              </template>

              <template v-else-if="step.key === 'proposal'">
                <label>选题背景与研究依据<textarea v-model.trim="proposalForm.background" placeholder="说明研究背景、问题与依据" /></label>
                <label>研究方案与进度计划<textarea v-model.trim="proposalForm.plan" placeholder="说明技术路线、实施计划和阶段安排" /></label>
                <label>预期成果<textarea v-model.trim="proposalForm.outcome" placeholder="可填写预期成果、交付形式等" /></label>
                <label>附件（PDF / Word / ZIP，最多 10 个）<input type="file" accept=".pdf,.doc,.docx,.zip" multiple @change="pickFiles('proposal', $event)" /></label>
                <p class="sp-muted">{{ attachmentText('proposal') }}</p>
                <button class="sp-btn" :disabled="busy" @click="submitProposal">提交开题报告</button>
              </template>

              <template v-else-if="step.key === 'midterm'">
                <label>整改说明<textarea v-model.trim="rectifyContent" placeholder="逐项说明已采取的整改措施" /></label>
                <button class="sp-btn" :disabled="busy || !rectifyContent" @click="submitRectify">提交整改</button>
              </template>

              <template v-else-if="step.key === 'final'">
                <p class="sp-muted">本次将提交：{{ final.canSubmitFinal ? '定稿' : '初稿' }}。文件上传后由系统生成材料记录，查重结果不能由学生自行填写。</p>
                <label>论文附件（PDF / Word / ZIP）<input type="file" accept=".pdf,.doc,.docx,.zip" multiple @change="pickFiles('final', $event)" /></label>
                <p class="sp-muted">{{ attachmentText('final') }}</p>
                <button class="sp-btn" :disabled="busy || !attachments.final.length" @click="submitFinal">提交论文成果</button>
              </template>
            </div>
          </article>
        </li>
      </ol>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const expanded = ref('')
const my = ref({})
const taskbook = ref({})
const proposal = ref({})
const midterm = ref({})
const final = ref({})
const defense = ref({})
const grade = ref({})
const archive = ref({})
const round = ref(null)
const topics = ref([])
const selectedTopicIds = ref([])
const rectifyContent = ref('')
const attachments = reactive({ proposal: [], final: [] })
const proposalForm = reactive({ background: '', plan: '', outcome: '' })

const approvedMidterm = computed(() => ['CHECKED_PASS', 'RECTIFIED_PASS'].includes(midterm.value.status))
const midtermTone = computed(() => {
  if (approvedMidterm.value) return 'success'
  if (midterm.value.status === 'CHECKED_FAIL') return 'danger'
  if (midterm.value.status === 'RECTIFYING' || midterm.value.status === 'RECTIFY_SUBMITTED') return 'warn'
  return 'warn'
})
const finalTone = computed(() => {
  if (final.value.finalApproved) return 'success'
  const items = final.value.items || []
  if (items.some((i) => i.status === 'REJECTED')) return 'danger'
  return 'warn'
})
const hasTopic = computed(() => Boolean(my.value.topicTitle && my.value.topicTitle !== '（未选题）'))
const hasGuidance = computed(() => (my.value.guideLogs || []).length > 0)

const steps = computed(() => [
  {
    key: 'topic', order: '01', title: '组织与选题', description: '在学校开放的轮次中提交志愿，等待导师或管理员确认。',
    status: hasTopic.value ? '课题已确认' : (round.value ? '待提交志愿' : '等待开放'), tone: hasTopic.value ? 'success' : 'warn',
    detail: hasTopic.value ? `${my.value.topicTitle}${my.value.advisorName ? ` · 指导教师：${my.value.advisorName}` : ''}` : (round.value?.remark || '学校尚未开放选题轮次。'),
    action: !hasTopic.value && round.value ? '选择并提交志愿' : ''
  },
  {
    key: 'taskbook', order: '02', title: '任务书确认', description: '阅读导师下达的任务目标、研究内容、进度计划和成果要求。',
    status: taskbook.value.status === 'CONFIRMED' ? '已确认' : taskbook.value.statusLabel || '等待下达', tone: taskbook.value.status === 'CONFIRMED' ? 'success' : 'warn',
    detail: taskbook.value.hasData ? `任务书 v${taskbook.value.taskbookVersion || 1} · ${taskbook.value.objective || '请阅读任务书详情'}` : (taskbook.value.message || '导师尚未下达任务书。'),
    action: ['PENDING_CONFIRM', 'CHANGE_PENDING'].includes(taskbook.value.status) ? '确认任务书' : ''
  },
  {
    key: 'proposal', order: '03', title: '开题论证', description: '提交研究依据、技术路线、进度计划与预期成果，等待审核。',
    status: proposal.value.latest?.statusLabel || (proposal.value.canSubmit ? '待提交' : '等待前置环节'), tone: proposal.value.latest?.status === 'APPROVED' ? 'success' : proposal.value.latest?.status === 'REJECTED' ? 'danger' : 'warn',
    detail: proposal.value.latest ? `当前版本 ${proposal.value.latest.version || '—'}` : (proposal.value.reason || '请在课题确认后提交开题报告。'), reviewComment: proposal.value.latest?.reviewComment,
    action: proposal.value.canSubmit ? (proposal.value.latest ? '修改后重交开题报告' : '填写开题报告') : ''
  },
  {
    key: 'guidance', order: '04', title: '过程指导', description: '导师指导记录会沉淀为可追溯的过程证据。',
    status: hasGuidance.value ? `已有 ${my.value.guideLogs.length} 条记录` : '等待指导', tone: hasGuidance.value ? 'success' : 'warn',
    detail: hasGuidance.value ? (my.value.guideLogs[0]?.text || '已记录最新指导意见。') : '请根据任务书计划主动与指导教师沟通；最低指导次数由本校批次规则决定。'
  },
  {
    key: 'midterm', order: '05', title: '中期检查', description: '查看检查结论；被要求整改时提交整改说明，等待复核。',
    status: midterm.value.statusLabel || '待检查', tone: midtermTone.value,
    detail: midterm.value.checkComment || midterm.value.rectifyDeadline || '学校完成中期检查后会在此展示结论。', reviewComment: midterm.value.reviewComment,
    action: midterm.value.status === 'RECTIFYING' ? '提交整改说明' : ''
  },
  {
    key: 'final', order: '06', title: '成果检查', description: '按初稿、定稿顺序提交论文材料，等待评阅和查重。',
    status: final.value.finalApproved ? '定稿已通过' : final.value.hint || '等待提交', tone: finalTone.value,
    detail: final.value.items?.[0] ? `${final.value.items[0].type} ${final.value.items[0].version} · ${final.value.items[0].statusLabel}` : '提交前请确认开题、中期等前置环节已按学校要求完成。', reviewComment: final.value.items?.[0]?.reviewComment,
    files: (final.value.items || []).filter((item) => item.type === '定稿').flatMap((item) => item.attachmentsList || []),
    action: final.value.canSubmitDraft || final.value.canSubmitFinal ? '上传并提交论文' : ''
  },
  {
    key: 'defense', order: '07', title: '答辩与评分', description: '答辩安排发布后可查看时间、地点和答辩组信息。',
    status: defense.value.published ? '安排已发布' : defense.value.assigned ? '安排编制中' : '等待分组', tone: defense.value.published ? 'success' : 'warn',
    detail: defense.value.published ? `${defense.value.date || '待定'} · ${defense.value.location || '待定'} · ${defense.value.groupName || ''}` : (defense.value.message || '完成资格审核后由学校统一安排。')
  },
  {
    key: 'archive', order: '08', title: '成绩归档与总结', description: '学校发布后可查看最终成绩；材料齐套后由学校归档。',
    status: archive.value.statusLabel || (grade.value.published ? '等待学校归档' : '等待发布'), tone: archive.value.status === 'FILED' ? 'success' : archive.value.status === 'REJECTED' ? 'danger' : 'warn',
    detail: archive.value.status === 'FILED' ? `已由 ${archive.value.verifiedBy || '学校'} 核验归档${archive.value.filedAt ? ` · ${archive.value.filedAt}` : ''}` : (archive.value.rejectReason || (grade.value.published ? '成绩已发布，学校正在核验归档材料。' : '成绩发布前不展示分数明细。')),
    checklist: archive.value.checklist || []
  }
])

function attachmentText(kind) {
  const list = attachments[kind]
  return list.length ? `已上传 ${list.length} 个附件：${list.map((item) => item.fileName || item.name).join('、')}` : '尚未上传附件'
}

// 每个板块一个命名加载器：动作后只刷新受影响板块，也避免长数组位置解构错位。
const sections = {
  my: async () => { my.value = await portalApi.domainMy('graduation') },
  taskbook: async () => { taskbook.value = await portalApi.graduationTaskbook() },
  proposal: async () => { proposal.value = await portalApi.graduationProposal() },
  midterm: async () => { midterm.value = await portalApi.graduationMidterm() },
  final: async () => { final.value = await portalApi.graduationFinal() },
  defense: async () => { defense.value = await portalApi.graduationDefense() },
  grade: async () => { grade.value = await portalApi.graduationGrade() },
  archive: async () => { archive.value = await portalApi.graduationArchive() },
  round: async () => {
    round.value = await portalApi.graduationActiveRound()
    selectedTopicIds.value = (round.value?.myChoices || []).sort((a, b) => a.choiceOrder - b.choiceOrder).map((item) => String(item.topicId))
  }
}

async function refresh(keys) {
  const results = await Promise.allSettled(keys.map((key) => sections[key]()))
  return results.filter((r) => r.status === 'rejected')
}

async function load() {
  loading.value = true
  error.value = ''
  const keys = Object.keys(sections)
  const failed = await refresh(keys)
  // 单个接口故障只降级对应板块；全部失败才整页报错。
  if (failed.length === keys.length) {
    error.value = failed[0].reason?.message || '毕业设计数据加载失败'
  } else if (failed.length) {
    ui.notify(`有 ${failed.length} 个板块加载失败，可点「刷新进度」重试`)
  }
  loading.value = false
}

async function afterAction(keys) {
  if (await refresh(keys).then((f) => f.length)) ui.notify('状态刷新失败，可点「刷新进度」重试')
}

async function handleAction(key) {
  if (key === 'taskbook') return confirmTaskbook()
  expanded.value = expanded.value === key ? '' : key
  // 题目库最多数百条且选定课题后用不到，展开选题面板时才拉取。
  if (key === 'topic' && expanded.value === 'topic' && round.value && !topics.value.length) {
    try { topics.value = await portalApi.graduationTopics(round.value.batchId) } catch (e) { ui.notify(e?.message || '题目库加载失败') }
  }
}

function toggleTopic(id) {
  const value = String(id)
  const index = selectedTopicIds.value.indexOf(value)
  if (index >= 0) { selectedTopicIds.value.splice(index, 1); return }
  if (selectedTopicIds.value.length >= Number(round.value?.maxChoices || 3)) { ui.notify(`最多可选 ${round.value?.maxChoices || 3} 个志愿`); return }
  selectedTopicIds.value.push(value)
}

async function confirmTaskbook() {
  busy.value = true
  try { await portalApi.confirmGraduationTaskbook(); ui.notify('任务书已确认'); await afterAction(['taskbook', 'my']) } catch (e) { ui.notify(e?.message || '确认失败') } finally { busy.value = false }
}

async function submitChoices() {
  busy.value = true
  try {
    await portalApi.submitGraduationChoices(round.value.id, selectedTopicIds.value.map((topicId, index) => ({ topicId, choiceOrder: index + 1 })))
    ui.notify('选题志愿已提交，等待学校处理'); expanded.value = ''; await afterAction(['round', 'my'])
  } catch (e) { ui.notify(e?.message || '提交志愿失败') } finally { busy.value = false }
}

async function pickFiles(kind, event) {
  const files = Array.from(event.target.files || [])
  if (!files.length) return
  busy.value = true
  try {
    const uploaded = await Promise.all(files.map((file) => portalApi.uploadGraduationMaterial(file)))
    attachments[kind].push(...uploaded)
    ui.notify(`已上传 ${uploaded.length} 个附件`)
  } catch (e) { ui.notify(e?.message || '附件上传失败') } finally { busy.value = false; event.target.value = '' }
}

async function submitProposal() {
  busy.value = true
  try {
    await portalApi.submitGraduationProposal({ ...proposalForm, attachments: attachments.proposal.map((item) => item.fileId) })
    ui.notify('开题报告已提交，等待指导教师审阅'); expanded.value = ''; await afterAction(['proposal', 'my'])
  } catch (e) { ui.notify(e?.message || '开题报告提交失败') } finally { busy.value = false }
}

async function submitRectify() {
  busy.value = true
  try { await portalApi.rectifyGraduationMidterm(rectifyContent.value); ui.notify('整改说明已提交，等待复核'); expanded.value = ''; await afterAction(['midterm', 'my']) } catch (e) { ui.notify(e?.message || '整改提交失败') } finally { busy.value = false }
}

async function submitFinal() {
  busy.value = true
  try {
    await portalApi.submitGraduationFinal({ finalType: final.value.canSubmitFinal ? '定稿' : '初稿', attachments: attachments.final.map((item) => item.fileId) })
    ui.notify('论文成果已提交，等待审阅'); expanded.value = ''; await afterAction(['final', 'my'])
  } catch (e) { ui.notify(e?.message || '论文提交失败') } finally { busy.value = false }
}

async function downloadMaterial(file) {
  busy.value = true
  try { await portalApi.downloadGraduationMaterial(file.fileId, file.fileName); ui.notify('材料已开始下载，可用本机阅读器打开并打印') } catch (e) { ui.notify(e?.message || '材料下载失败') } finally { busy.value = false }
}

onMounted(load)
</script>

<style scoped>
.gd-workbench { max-width: 1120px; margin: 0 auto; }
.gd-hero { display:flex; justify-content:space-between; gap:24px; align-items:flex-start; margin:4px 0 18px; }
.gd-eyebrow { margin:0 0 6px; color:var(--sp-primary); font-size:13px; font-weight:600; }.gd-hero h1 { margin:0; font-size:25px; }.gd-hero p:not(.gd-eyebrow) { color:#86909c; margin:8px 0 0; font-size:14px; }
.gd-summary { display:grid; grid-template-columns:repeat(4, 1fr); gap:14px; }.gd-summary div { min-width:0; }.gd-summary span { display:block; color:#86909c; font-size:12px; margin-bottom:6px; }.gd-summary strong { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:14px; }
.gd-tip { margin:16px 0; padding:11px 14px; border-radius:8px; background:#f2f7ff; color:#4e5969; font-size:13px; line-height:1.6; }
.gd-empty-notice { margin-bottom:16px; padding:14px 16px; border:1px solid #ffd591; border-radius:10px; background:#fffbe6; color:#613400; }.gd-empty-notice strong { font-size:14px; }.gd-empty-notice p { margin:6px 0 0; color:#8b5c00; font-size:13px; line-height:1.6; }
.gd-steps { margin:0; padding:0; list-style:none; }.gd-step { display:grid; grid-template-columns:58px minmax(0, 1fr); }.gd-step__rail { border-right:1px solid #e5e6eb; position:relative; display:flex; justify-content:center; }.gd-step__rail span { width:30px; height:30px; line-height:30px; border-radius:50%; text-align:center; color:#86909c; background:#f2f3f5; font-size:12px; font-weight:600; z-index:1; }.gd-step.is-success .gd-step__rail span { background:rgba(0,180,42,.12); color:#00a33a; }.gd-step.is-danger .gd-step__rail span { background:#ffece8; color:#f53f3f; }
.gd-step article { margin:0 0 14px 18px; padding:16px 18px; background:#fff; border:1px solid #edf0f3; border-radius:10px; }.gd-step__head { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }.gd-step h2 { font-size:16px; margin:0; }.gd-step__head p,.gd-step__detail { margin:6px 0 0; color:#86909c; font-size:13px; line-height:1.6; }.gd-step__comment { margin:10px 0 0; padding:8px 10px; border-radius:6px; background:#fff7e8; color:#8b5c00; font-size:13px; white-space:pre-wrap; }.gd-step__actions { display:flex; align-items:center; gap:10px; margin-top:13px; }.gd-form { margin-top:14px; padding:14px; background:#fafbfc; border-radius:8px; }.gd-form label { display:block; margin:10px 0; color:#4e5969; font-size:13px; }.gd-form textarea { display:block; width:100%; min-height:76px; resize:vertical; margin-top:6px; padding:9px 10px; font:inherit; border:1px solid #dcdfe6; border-radius:6px; }.gd-form input[type=file] { display:block; margin-top:7px; font-size:12px; }
.gd-files { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-top:12px; color:#4e5969; font-size:13px; }.gd-file { border:0; padding:5px 8px; border-radius:5px; color:var(--sp-primary); background:rgba(22,119,255,.08); cursor:pointer; font-size:12px; }.gd-file:disabled { cursor:not-allowed; opacity:.6; }.gd-checklist { display:flex; flex-wrap:wrap; gap:7px 14px; margin:12px 0 0; padding:0; list-style:none; color:#4e5969; font-size:12px; }.gd-checklist li { color:#00a33a; }.gd-checklist li.is-missing { color:#f53f3f; }
.gd-topic-list { display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:8px; margin:12px 0; }.gd-topic { position:relative; min-height:72px; padding:10px; text-align:left; cursor:pointer; background:#fff; border:1px solid #e5e6eb; border-radius:7px; }.gd-topic.is-picked { border-color:var(--sp-primary); background:rgba(22,119,255,.05); }.gd-topic b { position:absolute; right:8px; top:8px; color:var(--sp-primary); font-size:11px; }.gd-topic strong,.gd-topic span { display:block; padding-right:44px; }.gd-topic strong { font-size:13px; }.gd-topic span { color:#86909c; font-size:12px; margin-top:5px; }
@media (max-width: 760px) { .gd-hero { display:block; }.gd-hero .sp-btn { margin-top:12px; }.gd-summary { grid-template-columns:repeat(2, 1fr); }.gd-step { grid-template-columns:40px minmax(0, 1fr); }.gd-step article { margin-left:12px; }.gd-step__head { display:block; }.gd-step__head .sp-tag { margin-top:8px; } }
</style>
