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
        <div><span>当前环节</span><strong>{{ stageText(my.stageLabel || my.stage) }}</strong></div>
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
            <div v-if="step.action || step.actionHint" class="gd-step__actions">
              <button v-if="step.action" class="sp-btn" :disabled="busy" @click="handleAction(step.key)">{{ step.action }}</button>
              <span v-if="step.actionHint" class="sp-muted">{{ step.actionHint }}</span>
            </div>

            <div v-if="step.key === 'archive' && grade.published" class="gd-grade-box">
              <p class="gd-grade-score">综合成绩 <strong>{{ grade.totalScore ?? '—' }}</strong> 分（{{ grade.gradeLevel || '—' }}）</p>
              <p v-if="grade.advisorScore != null || grade.reviewerScore != null || grade.defenseScore != null" class="sp-muted">
                指导 {{ grade.advisorScore ?? '—' }} · 评阅 {{ grade.reviewerScore ?? '—' }} · 答辩 {{ grade.defenseScore ?? '—' }}
              </p>
              <p v-if="grade.latestAppeal?.status === 'PENDING'" class="sp-muted">
                成绩申诉待复核（{{ grade.latestAppeal.statusLabel || '待复核' }}）
              </p>
              <template v-else-if="grade.canAppeal !== false">
                <template v-if="!showAppeal">
                  <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="showAppeal = true">对成绩有异议？发起更正申诉</button>
                </template>
                <template v-else>
                  <label>申诉理由<textarea v-model.trim="appealReason" placeholder="说明异议点与依据（至少 5 字）" maxlength="500" /></label>
                  <button class="sp-btn" :disabled="busy || appealReason.trim().length < 5" @click="submitAppeal">提交成绩申诉</button>
                </template>
              </template>
            </div>

            <div v-if="expanded === step.key" class="gd-form">
              <template v-if="step.key === 'taskbook'">
                <div class="gd-readonly">
                  <div><span>研究目标</span><p>{{ taskbook.objective || '—' }}</p></div>
                  <div><span>研究内容</span><p>{{ taskbook.content || '—' }}</p></div>
                  <div><span>进度安排</span><p>{{ taskbook.progressPlan || '—' }}</p></div>
                  <div><span>成果要求</span><p>{{ taskbook.outcomeRequirement || '—' }}</p></div>
                </div>
                <label class="gd-check">
                  <input v-model="taskbookAck" type="checkbox" />
                  我已阅读并确认任务书第 {{ taskbook.taskbookVersion || '—' }} 版
                </label>
                <button class="sp-btn" :disabled="busy || !taskbookAck || !taskbook.taskbookVersion" @click="signTaskbook">签署确认</button>
              </template>

              <template v-else-if="step.key === 'topic'">
                <template v-if="!hasTopic">
                  <p v-if="!round" class="sp-muted">当前没有开放的选题轮次，请等待管理员发布。</p>
                  <template v-else>
                    <p class="sp-muted">{{ round.roundName }} · 最多提交 {{ round.maxChoices }} 个志愿。点击题目按顺序选择，可再次点击取消。</p>
                    <div v-if="(round.myChoices || []).length" class="gd-change-list">
                      <div v-for="c in round.myChoices" :key="c.id || c.topicId" class="gd-change-item">
                        <span>{{ c.topicTitle || c.title || '志愿课题' }}</span>
                        <em>{{ choiceStatusLabel(c.status) }}</em>
                      </div>
                    </div>
                    <div class="gd-topic-list">
                      <button v-for="topic in topics" :key="topic.id" class="gd-topic" :class="{ 'is-picked': selectedTopicIds.includes(String(topic.id)) }" @click="toggleTopic(topic.id)">
                        <b v-if="selectedTopicIds.includes(String(topic.id))">志愿 {{ selectedTopicIds.indexOf(String(topic.id)) + 1 }}</b>
                        <strong>{{ topic.title }}</strong><span>{{ topic.advisorName || '导师待定' }}</span>
                      </button>
                    </div>
                    <div class="gd-step__actions">
                      <button class="sp-btn" :disabled="busy || !selectedTopicIds.length" @click="submitChoices">提交志愿</button>
                      <button v-if="canWithdrawChoices" class="sp-btn sp-btn--ghost" :disabled="busy" @click="withdrawChoices">退选志愿</button>
                    </div>
                  </template>
                </template>
                <template v-else>
                  <p class="sp-muted">获批课题已锁定，更换须重新审核。请选择目标课题并说明理由（至少 5 字）。</p>
                  <div class="gd-topic-list">
                    <button v-for="topic in topics" :key="topic.id" class="gd-topic" :class="{ 'is-picked': String(changeTopicId) === String(topic.id) }" @click="changeTopicId = topic.id">
                      <b v-if="String(changeTopicId) === String(topic.id)">已选</b>
                      <strong>{{ topic.title }}</strong><span>{{ topic.advisorName || '导师待定' }}</span>
                    </button>
                  </div>
                  <label>变更理由<textarea v-model.trim="changeReason" placeholder="变更理由（至少 5 字）" maxlength="200" /></label>
                  <button class="sp-btn" :disabled="busy || !changeTopicId || changeReason.trim().length < 5" @click="submitTopicChange">提交更换申请</button>
                  <div v-if="changeRequests.length" class="gd-change-list">
                    <p class="sp-muted">我的更换申请</p>
                    <div v-for="r in changeRequests" :key="r.id" class="gd-change-item">
                      <span>{{ r.oldTopicTitle || '原课题' }} → {{ r.newTopicTitle || '新课题' }}</span>
                      <em>{{ r.statusLabel || r.status }}</em>
                    </div>
                  </div>
                </template>
              </template>

              <template v-else-if="step.key === 'proposal'">
                <label>选题背景与研究依据<textarea v-model.trim="proposalForm.background" placeholder="说明研究背景、问题与依据" /></label>
                <label>研究方案与进度计划<textarea v-model.trim="proposalForm.plan" placeholder="说明技术路线、实施计划和阶段安排" /></label>
                <label>预期成果<textarea v-model.trim="proposalForm.outcome" placeholder="可填写预期成果、交付形式等" /></label>
                <label>开题主文档（PDF / Word / ZIP，仅 1 份）<input type="file" accept=".pdf,.doc,.docx,.zip" @change="pickFiles('proposal', $event)" /></label>
                <p class="sp-muted">{{ attachmentText('proposal') }}</p>
                <button class="sp-btn" :disabled="busy || !proposalForm.background || !proposalForm.plan" @click="submitProposal">提交开题报告</button>
              </template>

              <template v-else-if="step.key === 'midterm'">
                <label>整改说明<textarea v-model.trim="rectifyContent" placeholder="逐项说明已采取的整改措施" /></label>
                <button class="sp-btn" :disabled="busy || !rectifyContent" @click="submitRectify">提交整改</button>
              </template>

              <template v-else-if="step.key === 'final'">
                <p class="sp-muted">本次将提交：{{ final.canSubmitFinal ? '定稿' : '初稿' }}。文件上传后由系统生成材料记录，查重结果不能由学生自行填写。</p>
                <label>论文主文档（PDF / Word / ZIP，仅 1 份）<input type="file" accept=".pdf,.doc,.docx,.zip" @change="pickFiles('final', $event)" /></label>
                <p class="sp-muted">{{ attachmentText('final') }}</p>
                <button class="sp-btn" :disabled="busy || !attachments.final.length" @click="submitFinal">提交论文成果</button>
              </template>
            </div>
          </article>
        </li>
      </ol>

      <section v-if="hasPeerWork" class="gd-peer sp-panel">
        <h2>成果互查</h2>
        <p class="sp-muted">任务绑定学校确认的正式定稿。请先下载并阅读材料，再提交互查意见。</p>
        <div v-for="p in (peer.toReview || [])" :key="'r-' + p.id" class="gd-peer__item">
          <header><strong>待互查 · {{ p.studentName || '同学' }}</strong><StatusTag :text="p.statusLabel || '待互查'" tone="warn" /></header>
          <p class="sp-muted">评阅材料：{{ p.finalType || '定稿' }} {{ p.finalVersion || '版本未绑定' }}</p>
          <p v-if="p.taskValid === false" class="gd-step__comment">{{ p.taskError || '任务未绑定有效正式定稿，请联系管理员重新分配。' }}</p>
          <div v-if="p.attachmentsList?.length" class="gd-files">
            <button v-for="file in p.attachmentsList" :key="file.fileId" class="gd-file" :disabled="busy" @click="downloadMaterial(file)">
              下载 {{ file.fileName || '定稿材料' }}
            </button>
          </div>
          <p v-else-if="p.taskValid !== false" class="gd-step__comment">该定稿暂无可下载附件，请联系管理员核对文件状态。</p>
          <label>互查意见<textarea v-model.trim="peerOpinions[p.id]" placeholder="互查意见（至少 5 字）" maxlength="500" /></label>
          <button class="sp-btn" :disabled="busy || p.taskValid === false || !p.attachmentsList?.length || (peerOpinions[p.id] || '').trim().length < 5" @click="submitPeer(p.id)">提交互查意见</button>
        </div>
        <div v-for="p in (peer.myRectify || [])" :key="'x-' + p.id" class="gd-peer__item">
          <header><strong>需整改 · 互查人 {{ p.reviewerName || '—' }}</strong><StatusTag :text="p.statusLabel || '待整改'" tone="danger" /></header>
          <p class="sp-muted">对应材料：{{ p.finalType || '定稿' }} {{ p.finalVersion || '版本未绑定' }}</p>
          <p v-if="p.taskValid === false" class="gd-step__comment">{{ p.taskError || '任务未绑定有效正式定稿，请联系管理员重新分配。' }}</p>
          <div v-if="p.attachmentsList?.length" class="gd-files">
            <button v-for="file in p.attachmentsList" :key="file.fileId" class="gd-file" :disabled="busy" @click="downloadMaterial(file)">
              下载 {{ file.fileName || '定稿材料' }}
            </button>
          </div>
          <p v-if="p.opinion" class="gd-step__comment">互查意见：{{ p.opinion }}</p>
          <label>整改说明<textarea v-model.trim="peerNotes[p.id]" placeholder="整改说明（至少 5 字）" maxlength="500" /></label>
          <button class="sp-btn" :disabled="busy || p.taskValid === false || (peerNotes[p.id] || '').trim().length < 5" @click="submitPeerRectify(p.id)">提交整改说明</button>
        </div>
      </section>
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
const materials = ref({ items: [] })
const defense = ref({})
const grade = ref({})
const archive = ref({})
const peer = ref({ toReview: [], myRectify: [] })
const peerOpinions = reactive({})
const peerNotes = reactive({})
const round = ref(null)
const topics = ref([])
const selectedTopicIds = ref([])
const changeRequests = ref([])
const changeTopicId = ref('')
const changeReason = ref('')
const taskbookAck = ref(false)
const rectifyContent = ref('')
const showAppeal = ref(false)
const appealReason = ref('')
const attachments = reactive({ proposal: [], final: [] })
const proposalForm = reactive({ background: '', plan: '', outcome: '' })

const CHOICE_STATUS = { PENDING: '待处理', MATCHED: '已匹配', UNMATCHED: '未录取', CONFIRMED: '已确认', REJECTED: '已驳回' }

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
const hasTopic = computed(() => Boolean(my.value.topicId || my.value.hasTopic))
const hasGuidance = computed(() => (my.value.guideLogs || []).length > 0)
const hasPeerWork = computed(() => ((peer.value.toReview || []).length + (peer.value.myRectify || []).length) > 0)
const canWithdrawChoices = computed(() => {
  const choices = round.value?.myChoices || []
  return !hasTopic.value && choices.some((c) => c.status === 'PENDING')
    && !choices.some((c) => c.status === 'CONFIRMED' || c.status === 'MATCHED')
})

const proposalFiles = computed(() => proposal.value.latest?.attachmentsList || [])
const finalFiles = computed(() => [
  ...proposalFiles.value,
  ...(final.value.items || []).flatMap((item) => item.attachmentsList || [])
])

const defenseDetail = computed(() => {
  if (!defense.value.published) return defense.value.message || '完成资格审核后由学校统一安排。'
  const parts = [
    `${defense.value.date || '待定'} · ${defense.value.location || '待定'} · ${defense.value.groupName || ''}`.trim(),
  ]
  if (defense.value.chair) parts.push(`组长：${defense.value.chair}`)
  if ((defense.value.members || []).length) parts.push(`评委：${(defense.value.members || []).join('、')}`)
  if (defense.value.secretary) parts.push(`秘书：${defense.value.secretary}`)
  return parts.filter(Boolean).join(' · ')
})

const finalDetail = computed(() => {
  const item = final.value.items?.[0]
  if (!item) return '提交前请确认开题、中期等前置环节已按学校要求完成。'
  const rate = item.plagiarismRate != null && item.plagiarismRate !== '' ? ` · 查重 ${item.plagiarismRate}` : ''
  return `${item.type} ${item.version} · ${item.statusLabel}${rate}`
})

const STAGE_TEXT = { TOPIC: '组织与选题', TASKBOOK: '任务书确认', PROPOSAL: '开题论证', MIDTERM: '中期检查', FINAL: '论文成果', PEER: '成果互查', DEFENSE: '答辩安排', ARCHIVE: '成绩与归档', COMPLETED: '已完成' }
function stageText(value) {
  const raw = String(value || '').trim()
  if (!raw) return '待开始'
  const key = raw.toUpperCase()
  if (STAGE_TEXT[key]) return STAGE_TEXT[key]
  return /^[A-Z0-9_]+$/.test(raw) ? '环节待确认' : raw
}

const steps = computed(() => [
  {
    key: 'topic', order: '01', title: '组织与选题', description: '在学校开放的轮次中提交志愿，等待导师或管理员确认。',
    status: hasTopic.value ? '课题已确认' : (round.value ? '待提交志愿' : '等待开放'), tone: hasTopic.value ? 'success' : 'warn',
    detail: hasTopic.value ? `${my.value.topicTitle}${my.value.advisorName ? ` · 指导教师：${my.value.advisorName}` : ''}` : (round.value?.remark || '学校尚未开放选题轮次。'),
    action: hasTopic.value ? '申请更换课题' : (round.value ? '选择并提交志愿' : '')
  },
  {
    key: 'taskbook', order: '02', title: '任务书确认', description: '阅读导师下达的任务目标、研究内容、进度计划和成果要求。',
    status: taskbook.value.status === 'CONFIRMED' ? '已确认' : taskbook.value.statusLabel || '等待下达', tone: taskbook.value.status === 'CONFIRMED' ? 'success' : 'warn',
    detail: taskbook.value.hasData ? `任务书第 ${taskbook.value.taskbookVersion || 1} 版 · ${taskbook.value.objective || '请阅读任务书详情'}` : (taskbook.value.message || '导师尚未下达任务书。'),
    action: ['PENDING_CONFIRM', 'CHANGE_PENDING'].includes(taskbook.value.status) ? '确认任务书' : ''
  },
  {
    key: 'proposal', order: '03', title: '开题论证', description: '提交研究依据、技术路线、进度计划与预期成果，等待审核。',
    status: proposal.value.latest?.statusLabel || (proposal.value.canSubmit ? '待提交' : '等待前置环节'), tone: proposal.value.latest?.status === 'APPROVED' ? 'success' : proposal.value.latest?.status === 'REJECTED' ? 'danger' : 'warn',
    detail: proposal.value.latest ? `当前版本 ${proposal.value.latest.version || '—'}` : (proposal.value.reason || '请在课题确认后提交开题报告。'),
    reviewComment: proposal.value.latest?.reviewComment,
    files: proposalFiles.value,
    action: proposal.value.canSubmit ? (proposal.value.latest ? '修改后重交开题报告' : '填写开题报告') : '',
    actionHint: proposal.value.reason || ''
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
    detail: finalDetail.value, reviewComment: final.value.items?.[0]?.reviewComment,
    files: finalFiles.value,
    action: final.value.canSubmitDraft || final.value.canSubmitFinal ? '上传并提交论文' : ''
  },
  {
    key: 'defense', order: '07', title: '答辩与评分', description: '答辩安排发布后可查看时间、地点和答辩组信息。',
    status: defense.value.published ? '安排已发布' : defense.value.assigned ? '安排编制中' : '等待分组', tone: defense.value.published ? 'success' : 'warn',
    detail: defenseDetail.value
  },
  {
    key: 'archive', order: '08', title: '成绩归档与总结', description: '学校发布后可查看最终成绩并发起申诉；材料齐套后由学校归档。',
    status: archive.value.statusLabel || (grade.value.published ? '成绩已发布' : '等待发布'),
    tone: archive.value.status === 'FILED' ? 'success' : archive.value.status === 'REJECTED' ? 'danger' : (grade.value.published ? 'success' : 'warn'),
    detail: archive.value.status === 'FILED'
      ? `已由 ${archive.value.verifiedBy || '学校'} 核验归档${archive.value.filedAt ? ` · ${archive.value.filedAt}` : ''}`
      : (archive.value.rejectReason || (grade.value.published ? '成绩已发布，可核对分数并在有异议时发起申诉；学校同步核验归档材料。' : '成绩发布前不展示分数明细。')),
    checklist: archive.value.checklist || []
  }
])

function attachmentText(kind) {
  const list = attachments[kind]
  return list.length ? `已上传 ${list.length} 个附件：${list.map((item) => item.fileName || item.name).join('、')}` : '尚未上传附件'
}

function materialVersion(code) {
  const row = (materials.value.items || []).find((item) => item.materialCode === code)
  return Number(row?.version || 0)
}

function choiceStatusLabel(status) {
  return CHOICE_STATUS[status] || status || '—'
}

function topicBatchId() {
  return my.value.batchId || round.value?.batchId || ''
}

const sections = {
  my: async () => { my.value = await portalApi.domainMy('graduation') },
  taskbook: async () => { taskbook.value = await portalApi.graduationTaskbook() },
  proposal: async () => { proposal.value = await portalApi.graduationProposal() },
  midterm: async () => { midterm.value = await portalApi.graduationMidterm() },
  final: async () => { final.value = await portalApi.graduationFinal() },
  materials: async () => { materials.value = await portalApi.graduationMaterialLibrary() || { items: [] } },
  defense: async () => { defense.value = await portalApi.graduationDefense() },
  grade: async () => { grade.value = await portalApi.graduationGrade() },
  archive: async () => { archive.value = await portalApi.graduationArchive() },
  peer: async () => { peer.value = await portalApi.graduationPeerTasks() || { toReview: [], myRectify: [] } },
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
  expanded.value = expanded.value === key ? '' : key
  if (key === 'taskbook' && expanded.value === 'taskbook') {
    taskbookAck.value = false
  }
  if (key === 'proposal' && expanded.value === 'proposal') {
    const latest = proposal.value.latest
    if (latest) {
      proposalForm.background = latest.background || ''
      proposalForm.plan = latest.plan || ''
      proposalForm.outcome = latest.outcome || ''
    }
  }
  if (key === 'topic' && expanded.value === 'topic') {
    const batchId = topicBatchId()
    if (batchId) {
      try { topics.value = await portalApi.graduationTopics(batchId) } catch (e) { ui.notify(e?.message || '题目库加载失败') }
    } else if (!hasTopic.value && !round.value) {
      topics.value = []
    }
    if (hasTopic.value) {
      changeTopicId.value = ''
      changeReason.value = ''
      try { changeRequests.value = await portalApi.graduationChangeRequests() || [] } catch (e) { ui.notify(e?.message || '更换申请列表加载失败') }
    }
  }
}

function toggleTopic(id) {
  const value = String(id)
  const index = selectedTopicIds.value.indexOf(value)
  if (index >= 0) { selectedTopicIds.value.splice(index, 1); return }
  if (selectedTopicIds.value.length >= Number(round.value?.maxChoices || 3)) { ui.notify(`最多可选 ${round.value?.maxChoices || 3} 个志愿`); return }
  selectedTopicIds.value.push(value)
}

async function signTaskbook() {
  if (!taskbookAck.value || !taskbook.value.taskbookVersion) return
  busy.value = true
  try {
    await portalApi.signGraduationTaskbook(taskbook.value.taskbookVersion)
    ui.notify('任务书已签署确认')
    expanded.value = ''
    taskbookAck.value = false
    await afterAction(['taskbook', 'my', 'proposal'])
  } catch (e) { ui.notify(e?.message || '签署失败') } finally { busy.value = false }
}

async function submitChoices() {
  busy.value = true
  try {
    await portalApi.submitGraduationChoices(round.value.id, selectedTopicIds.value.map((topicId, index) => ({ topicId, choiceOrder: index + 1 })))
    ui.notify('选题志愿已提交，等待学校处理'); expanded.value = ''; await afterAction(['round', 'my'])
  } catch (e) { ui.notify(e?.message || '提交志愿失败') } finally { busy.value = false }
}

async function withdrawChoices() {
  if (!round.value?.id) return
  busy.value = true
  try {
    await portalApi.withdrawGraduationChoices(round.value.id)
    ui.notify('志愿已退选，可重新填写')
    await afterAction(['round', 'my'])
  } catch (e) { ui.notify(e?.message || '退选失败') } finally { busy.value = false }
}

async function submitTopicChange() {
  const reason = changeReason.value.trim()
  if (!changeTopicId.value || reason.length < 5) return
  busy.value = true
  try {
    await portalApi.requestGraduationTopicChange(changeTopicId.value, reason)
    ui.notify('课题更换申请已提交')
    changeTopicId.value = ''
    changeReason.value = ''
    try { changeRequests.value = await portalApi.graduationChangeRequests() || [] } catch { /* keep previous list */ }
    await afterAction(['my', 'round'])
  } catch (e) { ui.notify(e?.message || '更换申请提交失败') } finally { busy.value = false }
}

async function pickFiles(kind, event) {
  const file = Array.from(event.target.files || [])[0]
  if (!file) return
  busy.value = true
  try {
    const uploaded = await portalApi.uploadGraduationMaterial(file)
    attachments[kind].splice(0, attachments[kind].length, uploaded)
    ui.notify('主文档已上传；重新选择会替换本次待提交文件')
  } catch (e) { ui.notify(e?.message || '主文档上传失败') } finally { busy.value = false; event.target.value = '' }
}

async function submitProposal() {
  if (!proposalForm.background || !proposalForm.plan) return
  busy.value = true
  try {
    await portalApi.submitGraduationProposal({
      ...proposalForm,
      attachments: attachments.proposal.map((item) => item.fileId),
      expectedVersion: materialVersion('PROPOSAL_REPORT')
    })
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
    const isFinal = final.value.canSubmitFinal
    await portalApi.submitGraduationFinal({
      finalType: isFinal ? '定稿' : '初稿',
      attachments: attachments.final.map((item) => item.fileId),
      expectedVersion: materialVersion(isFinal ? 'THESIS_FINAL' : 'THESIS_DRAFT')
    })
    ui.notify('论文成果已提交，等待审阅'); expanded.value = ''; await afterAction(['final', 'my'])
  } catch (e) { ui.notify(e?.message || '论文提交失败') } finally { busy.value = false }
}

async function downloadMaterial(file) {
  busy.value = true
  try { await portalApi.downloadGraduationMaterial(file.fileId, file.fileName); ui.notify('材料已开始下载，可用本机阅读器打开并打印') } catch (e) { ui.notify(e?.message || '材料下载失败') } finally { busy.value = false }
}

async function submitAppeal() {
  const reason = appealReason.value.trim()
  if (reason.length < 5) return
  busy.value = true
  try {
    await portalApi.graduationGradeAppeal(reason)
    ui.notify('成绩申诉已提交，等待学校复核')
    showAppeal.value = false
    appealReason.value = ''
    await afterAction(['grade'])
  } catch (e) { ui.notify(e?.message || '申诉提交失败') } finally { busy.value = false }
}

async function submitPeer(pid) {
  const task = (peer.value.toReview || []).find((item) => String(item.id) === String(pid))
  const opinion = (peerOpinions[pid] || '').trim()
  if (!task || task.taskValid === false || !(task.attachmentsList || []).length || opinion.length < 5) return
  busy.value = true
  try {
    await portalApi.submitGraduationPeer(pid, opinion)
    ui.notify('互查意见已提交')
    peerOpinions[pid] = ''
    await afterAction(['peer'])
  } catch (e) { ui.notify(e?.message || '互查提交失败') } finally { busy.value = false }
}

async function submitPeerRectify(pid) {
  const task = (peer.value.myRectify || []).find((item) => String(item.id) === String(pid))
  const note = (peerNotes[pid] || '').trim()
  if (!task || task.taskValid === false || note.length < 5) return
  busy.value = true
  try {
    await portalApi.rectifyGraduationPeer(pid, note)
    ui.notify('整改说明已提交')
    peerNotes[pid] = ''
    await afterAction(['peer'])
  } catch (e) { ui.notify(e?.message || '整改提交失败') } finally { busy.value = false }
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
.gd-step article { margin:0 0 14px 18px; padding:16px 18px; background:#fff; border:1px solid #edf0f3; border-radius:10px; }.gd-step__head { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }.gd-step h2 { font-size:16px; margin:0; }.gd-step__head p,.gd-step__detail { margin:6px 0 0; color:#86909c; font-size:13px; line-height:1.6; }.gd-step__comment { margin:10px 0 0; padding:8px 10px; border-radius:6px; background:#fff7e8; color:#8b5c00; font-size:13px; white-space:pre-wrap; }.gd-step__actions { display:flex; align-items:center; gap:10px; margin-top:13px; flex-wrap:wrap; }.gd-form { margin-top:14px; padding:14px; background:#fafbfc; border-radius:8px; }.gd-form label { display:block; margin:10px 0; color:#4e5969; font-size:13px; }.gd-form textarea { display:block; width:100%; min-height:76px; resize:vertical; margin-top:6px; padding:9px 10px; font:inherit; border:1px solid #dcdfe6; border-radius:6px; }.gd-form input[type=file] { display:block; margin-top:7px; font-size:12px; }
.gd-readonly { display:grid; gap:10px; margin-bottom:8px; }.gd-readonly > div { padding:10px 12px; background:#fff; border:1px solid #edf0f3; border-radius:6px; }.gd-readonly span { display:block; color:#86909c; font-size:12px; margin-bottom:6px; }.gd-readonly p { margin:0; color:#1d2129; font-size:13px; line-height:1.65; white-space:pre-wrap; }
.gd-check { display:flex !important; align-items:center; gap:8px; cursor:pointer; }.gd-check input { margin:0; }
.gd-change-list { margin:12px 0; display:grid; gap:8px; }.gd-change-item { display:flex; justify-content:space-between; gap:12px; align-items:center; padding:8px 10px; background:#fff; border:1px solid #edf0f3; border-radius:6px; font-size:13px; color:#4e5969; }.gd-change-item em { font-style:normal; color:var(--sp-primary); flex-shrink:0; }
.gd-files { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-top:12px; color:#4e5969; font-size:13px; }.gd-file { border:0; padding:5px 8px; border-radius:5px; color:var(--sp-primary); background:rgba(22,119,255,.08); cursor:pointer; font-size:12px; }.gd-file:disabled { cursor:not-allowed; opacity:.6; }.gd-checklist { display:flex; flex-wrap:wrap; gap:7px 14px; margin:12px 0 0; padding:0; list-style:none; color:#4e5969; font-size:12px; }.gd-checklist li { color:#00a33a; }.gd-checklist li.is-missing { color:#f53f3f; }
.gd-topic-list { display:grid; grid-template-columns:repeat(auto-fill, minmax(220px, 1fr)); gap:8px; margin:12px 0; }.gd-topic { position:relative; min-height:72px; padding:10px; text-align:left; cursor:pointer; background:#fff; border:1px solid #e5e6eb; border-radius:7px; }.gd-topic.is-picked { border-color:var(--sp-primary); background:rgba(22,119,255,.05); }.gd-topic b { position:absolute; right:8px; top:8px; color:var(--sp-primary); font-size:11px; }.gd-topic strong,.gd-topic span { display:block; padding-right:44px; }.gd-topic strong { font-size:13px; }.gd-topic span { color:#86909c; font-size:12px; margin-top:5px; }
.gd-grade-box { margin-top:12px; padding:12px 14px; border-radius:8px; background:#f7fafc; border:1px solid #edf0f3; }.gd-grade-score { margin:0 0 6px; font-size:14px; color:#1d2129; }.gd-grade-score strong { font-size:20px; color:var(--sp-primary); }.gd-grade-box .sp-btn { margin-top:10px; }.gd-grade-box label { display:block; margin-top:10px; color:#4e5969; font-size:13px; }.gd-grade-box textarea { display:block; width:100%; min-height:72px; margin-top:6px; padding:9px 10px; font:inherit; border:1px solid #dcdfe6; border-radius:6px; resize:vertical; }
.gd-peer { margin-top:16px; padding:16px 18px; }.gd-peer h2 { margin:0 0 6px; font-size:16px; }.gd-peer__item { margin-top:14px; padding-top:14px; border-top:1px solid #edf0f3; }.gd-peer__item header { display:flex; justify-content:space-between; gap:12px; align-items:center; }.gd-peer__item label { display:block; margin:10px 0; color:#4e5969; font-size:13px; }.gd-peer__item textarea { display:block; width:100%; min-height:72px; margin-top:6px; padding:9px 10px; font:inherit; border:1px solid #dcdfe6; border-radius:6px; resize:vertical; }
@media (max-width: 760px) { .gd-hero { display:block; }.gd-hero .sp-btn { margin-top:12px; }.gd-summary { grid-template-columns:repeat(2, 1fr); }.gd-step { grid-template-columns:40px minmax(0, 1fr); }.gd-step article { margin-left:12px; }.gd-step__head { display:block; }.gd-step__head .sp-tag { margin-top:8px; } }
</style>
