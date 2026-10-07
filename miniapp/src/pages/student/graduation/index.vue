<template>
  <view class="page-wrap">
    <MobilePrivacyGate />
    <MobileGraduationSectionErrors />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="journey && !journey.hasData">
        <MobileGlobalState state="empty" title="当前暂无毕业设计任务" :description="journey.message || '进入毕业设计阶段后，这里会按步骤显示你要办理的事项。'" />
      </view>
      <view class="page-pad stack" v-else-if="journey">
        <!-- 概览：课题 / 导师 / 进度 -->
        <view class="gd__hero card">
          <view class="gd__hero-top">
            <text class="gd__hero-batch">{{ journey.batchName || '毕业设计' }}</text>
            <text class="gd__hero-stage">已完成 {{ journey.doneCount }}/{{ journey.total }}</text>
          </view>
          <text class="gd__hero-topic">{{ journey.topicTitle || '尚未确定课题' }}</text>
          <text class="gd__hero-mentor">指导教师 · {{ journey.advisorName || '待分配' }}</text>
          <view class="gd__progress"><view class="gd__progress-bar" :style="{ width: progressPercent + '%' }" /></view>
        </view>

        <!-- 当前要做：后端统一派生，与学生 PC 同源 -->
        <MobileActionCard
          v-if="current"
          :title="currentTitle"
          :description="currentDescription"
          icon="→"
          :action-text="current.actionLabel || '查看'"
          @action="openStep(current.key)"
          @click="openStep(current.key)"
        />
        <MobileInlineAlert v-if="current && current.comment" type="danger" title="老师意见" :description="current.comment" />

        <!-- 办理步骤：一次只展开一步，展开时才加载该环节数据 -->
        <view class="section-head"><text class="section-head__title">办理步骤</text></view>
        <view class="card gd__steps">
          <view v-for="step in journey.steps" :key="step.key" :id="'gd-' + step.key" class="gd__step">
            <view class="gd__step-row" @click="toggleStep(step.key)">
              <text class="gd__step-no" :class="'is-' + step.tone">{{ step.state === 'done' ? '✓' : step.order }}</text>
              <view class="flex-1">
                <text class="gd__step-title">{{ step.title }}</text>
                <text class="gd__step-status">{{ step.statusText }}</text>
              </view>
              <MobileStatusTag :label="stepTagLabel(step)" :type="stepTagType(step)" />
              <text class="gd__arrow">{{ expanded === step.key ? '⌄' : '›' }}</text>
            </view>

            <view v-if="expanded === step.key" class="gd__panel stack-sm">
              <text v-if="step.detail" class="gd__hint">{{ step.detail }}</text>
              <text v-if="sectionLoading" class="gd__hint">正在加载…</text>

              <!-- 1 选题 / 2 任务书 / 7 答辩：独立页面办理 -->
              <button v-if="step.key === 'topic'" class="btn btn-primary" @click="go('/pages/student/graduation/topics/index')">
                {{ step.state === 'done' ? '查看课题 / 申请更换' : '进入选题' }}
              </button>
              <button v-if="step.key === 'taskbook'" class="btn btn-primary" @click="go('/pages/student/graduation/taskbook/index')">
                {{ step.state === 'todo' ? '阅读并确认任务书' : '查看任务书' }}
              </button>
              <button v-if="step.key === 'defense' && step.state !== 'locked'" class="btn btn-ghost" @click="go('/pages/student/graduation/defense/index')">查看答辩安排</button>

              <!-- 3 开题报告 -->
              <template v-if="step.key === 'proposal' && proposal">
                <view v-if="proposal.latest" class="gd__choice-row">
                  <text class="gd__choice-title">{{ proposal.latest.version }} · {{ proposal.latest.statusLabel }}</text>
                  <MobileStatusTag :label="proposal.latest.statusLabel"
                                   :type="proposal.latest.status === 'APPROVED' ? 'success' : proposal.latest.status === 'REJECTED' ? 'danger' : 'warning'" />
                </view>
                <MobileInlineAlert v-if="proposal.latest && proposal.latest.status === 'REJECTED' && proposal.latest.reviewComment"
                                   type="danger" title="需要重交" :description="proposal.latest.reviewComment" />
                <view v-if="proposal.latest && proposal.latest.attachmentsList && proposal.latest.attachmentsList.length" class="gd__atts">
                  <text v-for="a in proposal.latest.attachmentsList" :key="a.fileId" class="gd__att" @click="downloadAtt(a)">📎 {{ a.fileName }}</text>
                </view>
                <text v-if="!proposal.canSubmit && proposal.reason" class="gd__hint">{{ proposal.reason }}</text>
                <button v-if="proposal.canSubmit && !showProposalForm" class="btn btn-primary" @click="startProposal">
                  {{ proposal.latest && proposal.latest.status === 'REJECTED' ? '修改后重交开题报告' : '填写开题报告' }}
                </button>
                <template v-if="proposal.canSubmit && showProposalForm">
                  <textarea class="gd__reason" v-model="propForm.background" :maxlength="2000" placeholder="选题背景（必填）" placeholder-class="wr__ph" />
                  <textarea class="gd__reason" v-model="propForm.plan" :maxlength="2000" placeholder="研究方案与进度（必填）" placeholder-class="wr__ph" />
                  <textarea class="gd__reason" v-model="propForm.outcome" :maxlength="2000" placeholder="预期成果（选填）" placeholder-class="wr__ph" />
                  <view class="gd__atts">
                    <text v-for="(a, i) in propAtts" :key="a.fileId" class="gd__att gd__att--pending">📎 {{ a.fileName }}<text class="gd__att-x" @click.stop="removeAtt('prop', i)"> ×</text></text>
                    <button class="btn btn-ghost gd__att-add" :disabled="uploading" @click="pickUpload('prop')">{{ uploading ? '上传中…' : (propAtts.length ? '更换开题主文档' : '+ 上传开题主文档') }}</button>
                  </view>
                  <text class="gd__hint">可直接从微信聊天记录选择 PDF 或 Word 文件（20MB 以内）。</text>
                  <button class="btn btn-primary" :disabled="!propForm.background.trim() || !propForm.plan.trim() || proposalSubmitting" @click="submitProposal">
                    {{ proposalSubmitting ? '提交中…' : '提交开题报告' }}
                  </button>
                </template>
              </template>

              <!-- 4 过程指导 -->
              <template v-if="step.key === 'guidance' && g">
                <template v-if="g.guideLogs && g.guideLogs.length">
                  <view v-for="l in g.guideLogs" :key="l.id" class="gd__log">
                    <view class="gd__log-head">
                      <text class="gd__log-from">{{ l.from }}</text>
                      <text class="gd__log-date">{{ l.date }}</text>
                    </view>
                    <text class="gd__log-text">{{ l.text }}</text>
                    <text v-if="l.issues" class="gd__log-issue">待改进 · {{ l.issues }}</text>
                  </view>
                </template>
                <text v-else class="gd__hint">导师尚未填写指导记录</text>
              </template>

              <!-- 5 中期检查 -->
              <template v-if="step.key === 'midterm' && midterm">
                <view class="gd__choice-row"><text class="gd__choice-title">{{ midterm.conclusionLabel || midterm.statusLabel }}</text><MobileStatusTag :label="midterm.statusLabel" :type="midtermTagType" /></view>
                <text v-if="midterm.checkComment" class="gd__hint">检查意见：{{ midterm.checkComment }}</text>
                <template v-if="midterm.status === 'RECTIFYING'">
                  <text v-if="midterm.rectifyDeadline" class="gd__hint">整改截止：{{ midterm.rectifyDeadline }}</text>
                  <textarea class="gd__reason" v-model="rectifyContent" :maxlength="500" placeholder="逐项说明你已完成的整改" placeholder-class="wr__ph" />
                  <button class="btn btn-primary" :disabled="!rectifyContent.trim() || rectifySubmitting" @click="submitRectify">
                    {{ rectifySubmitting ? '提交中…' : '提交整改' }}
                  </button>
                </template>
                <text v-if="midterm.rectifyContent && midterm.status !== 'RECTIFYING'" class="gd__hint">我的整改说明：{{ midterm.rectifyContent }}</text>
              </template>

              <!-- 6 论文提交：手机可直接提交初稿/定稿 -->
              <template v-if="step.key === 'final' && final">
                <view v-for="it in final.items" :key="it.id" class="gd__final-item">
                  <view class="gd__choice-row">
                    <text class="gd__choice-title">{{ it.type }} {{ it.version }} · 查重 {{ it.plagiarismRate }}</text>
                    <MobileStatusTag :label="it.statusLabel"
                                     :type="it.status === 'APPROVED' ? 'success' : it.status === 'REJECTED' ? 'danger' : 'warning'" />
                  </view>
                  <view v-if="it.attachmentsList && it.attachmentsList.length" class="gd__atts">
                    <text v-for="a in it.attachmentsList" :key="a.fileId" class="gd__att" @click="downloadAtt(a)">📎 {{ a.fileName }}</text>
                  </view>
                </view>
                <MobileInlineAlert v-if="finalRejected" type="danger" title="需要重交" :description="finalRejected" />
                <text class="gd__hint">{{ final.hint }}</text>
                <template v-if="final.canSubmitDraft || final.canSubmitFinal">
                  <view class="gd__atts">
                    <text v-for="(a, i) in finalAtts" :key="a.fileId" class="gd__att gd__att--pending">📎 {{ a.fileName }}<text class="gd__att-x" @click.stop="removeAtt('final', i)"> ×</text></text>
                    <button class="btn btn-ghost gd__att-add" :disabled="uploading" @click="pickUpload('final')">{{ uploading ? '上传中…' : (finalAtts.length ? '更换论文文件' : '+ 选择论文文件') }}</button>
                  </view>
                  <text class="gd__hint">可直接从微信聊天记录选择 PDF 或 Word 文件（20MB 以内）；设计作品包、源代码请到电脑端上传。</text>
                  <button class="btn btn-primary" :disabled="finalSubmitting || !finalAtts.length" @click="submitFinal(final.canSubmitFinal ? '定稿' : '初稿')">
                    {{ finalSubmitting ? '提交中…' : (final.canSubmitFinal ? '提交论文定稿' : '提交论文初稿') }}
                  </button>
                </template>
              </template>

              <!-- 8 成绩与归档 -->
              <template v-if="step.key === 'grade'">
                <template v-if="grade && grade.published">
                  <view class="gd__choice-row"><text class="gd__choice-title">综合成绩 {{ grade.totalScore }} 分（{{ grade.gradeLevel }}）</text></view>
                  <text class="gd__hint">指导 {{ grade.advisorScore != null ? grade.advisorScore : '—' }} · 评阅 {{ grade.reviewerScore != null ? grade.reviewerScore : '—' }} · 答辩 {{ grade.defenseScore != null ? grade.defenseScore : '—' }}</text>
                  <MobileInlineAlert v-if="grade.latestAppeal && grade.latestAppeal.status === 'PENDING'"
                                     type="warning" title="成绩申诉待复核"
                                     :description="grade.latestAppeal.reason || '已提交申诉，请等待复核结果'" />
                  <template v-else-if="grade.canAppeal !== false">
                    <button v-if="!showAppeal" class="btn btn-ghost" @click="showAppeal = true">对成绩有异议？发起更正申诉</button>
                    <template v-else>
                      <textarea class="gd__reason" v-model="appealReason" :maxlength="500" placeholder="申诉理由（至少5字）" placeholder-class="wr__ph" />
                      <button class="btn btn-primary" :disabled="appealReason.trim().length < 5 || appealSubmitting" @click="submitAppeal">
                        {{ appealSubmitting ? '提交中…' : '提交申诉' }}
                      </button>
                    </template>
                  </template>
                </template>
                <view v-if="archive && archive.hasData && archive.checklist && archive.checklist.length" class="stack-sm">
                  <text class="gd__choice-title">归档材料（{{ archive.statusLabel || '待归档' }}）</text>
                  <text v-for="(c, i) in archive.checklist" :key="c.item || i" class="gd__hint">{{ c.present ? '✓' : '○' }} {{ c.label || c.item }}</text>
                </view>
                <button v-if="step.state === 'done'" class="btn btn-ghost" @click="go('/pages/student/graduation/evidence-package')">我的毕业归档包</button>
              </template>
            </view>
          </view>
        </view>

        <!-- 互查任务：有任务时才出现 -->
        <view v-if="hasPeerWork" class="section-head"><text class="section-head__title">成果互查</text></view>
        <view v-if="hasPeerWork" class="card stack-sm">
          <view v-for="p in (peer.toReview || [])" :key="'r-' + p.id" class="gd__final-item">
            <view class="gd__choice-row">
              <text class="gd__choice-title">待互查 · {{ p.studentName || '同学' }}</text>
              <MobileStatusTag :label="p.statusLabel || '待互查'" type="warning" />
            </view>
            <text class="gd__hint">评阅材料：{{ p.finalType || '定稿' }} {{ p.finalVersion || '版本未绑定' }}</text>
            <MobileInlineAlert v-if="p.taskValid === false" type="danger" title="互查任务不可处理" :description="p.taskError || '任务未绑定有效正式定稿，请联系管理员'" />
            <view v-if="p.attachmentsList && p.attachmentsList.length" class="gd__atts">
              <text v-for="a in p.attachmentsList" :key="a.fileId" class="gd__att" @click="downloadAtt(a)">📎 {{ a.fileName }}</text>
            </view>
            <text v-else-if="p.taskValid !== false" class="gd__hint">该定稿暂无可下载附件，请联系管理员核对文件状态。</text>
            <textarea class="gd__reason" v-model="peerOpinions[p.id]" :maxlength="500" placeholder="互查意见（至少5字）" placeholder-class="wr__ph" />
            <button class="btn btn-primary" :disabled="peerBusyId === p.id || p.taskValid === false || !(p.attachmentsList || []).length || (peerOpinions[p.id] || '').trim().length < 5" @click="submitPeer(p.id)">
              {{ peerBusyId === p.id ? '提交中…' : '提交互查意见' }}
            </button>
          </view>
          <view v-for="p in (peer.myRectify || [])" :key="'x-' + p.id" class="gd__final-item">
            <view class="gd__choice-row">
              <text class="gd__choice-title">需整改 · 互查人 {{ p.reviewerName || '—' }}</text>
              <MobileStatusTag :label="p.statusLabel || '待整改'" type="danger" />
            </view>
            <text class="gd__hint">对应材料：{{ p.finalType || '定稿' }} {{ p.finalVersion || '版本未绑定' }}</text>
            <MobileInlineAlert v-if="p.taskValid === false" type="danger" title="整改任务不可处理" :description="p.taskError || '任务未绑定有效正式定稿，请联系管理员'" />
            <view v-if="p.attachmentsList && p.attachmentsList.length" class="gd__atts">
              <text v-for="a in p.attachmentsList" :key="a.fileId" class="gd__att" @click="downloadAtt(a)">📎 {{ a.fileName }}</text>
            </view>
            <text v-if="p.opinion" class="gd__hint">互查意见：{{ p.opinion }}</text>
            <textarea class="gd__reason" v-model="peerNotes[p.id]" :maxlength="500" placeholder="整改说明（至少5字）" placeholder-class="wr__ph" />
            <button class="btn btn-primary" :disabled="peerBusyId === p.id || p.taskValid === false || (peerNotes[p.id] || '').trim().length < 5" @click="submitPeerRectify(p.id)">
              {{ peerBusyId === p.id ? '提交中…' : '提交整改说明' }}
            </button>
          </view>
        </view>

        <!-- 材料库：折叠，展开时才加载 -->
        <view class="card gd__linkrow" @click="toggleMaterials">
          <view class="flex-1">
            <text class="t-md t-bold">我的材料库</text>
            <text class="gd__hint" style="margin:2px 0 0;">{{ materials ? ((materials.items || []).length + ' 类材料 · 缺 ' + materialCount('MISSING') + ' · 退回 ' + materialCount('RETURNED')) : '查看各类材料的版本、审核与退回原因' }}</text>
          </view>
          <text class="gd__arrow">{{ showMaterials ? '⌄' : '›' }}</text>
        </view>
        <view v-if="showMaterials && materials" class="card stack-sm">
          <view v-for="m in materials.items || []" :key="m.materialId" class="gd__final-item">
            <view class="gd__choice-row">
              <view class="flex-1"><text class="gd__choice-title">{{ m.materialName }}</text><text class="gd__hint">{{ materialVersionText(m) }} · {{ materialScanLabel(m.currentVersion?.scanStatus) }}</text></view>
              <MobileStatusTag :label="materialStatusLabel(m)" :type="materialStatusType(m)" />
            </view>
            <MobileInlineAlert v-if="m.rejectReason" type="danger" title="需要重交" :description="m.rejectReason" />
            <view class="gg__actions">
              <button v-if="m.currentVersion?.fileId && (m.currentVersion.allowedActions || []).includes('preview')" class="btn btn-ghost" @click="openMaterial(m)">安全预览</button>
              <button v-if="canMiniSubmit(m)" class="btn btn-primary" :disabled="materialUploadingCode === m.materialCode" @click="submitSmallMaterial(m)">{{ materialUploadingCode === m.materialCode ? '上传中…' : '上传材料' }}</button>
              <text v-else-if="isPcOnly(m.materialCode) && ['MISSING','RETURNED'].includes(m.businessStatus)" class="gd__hint">设计作品包、源代码等大型文件请到电脑端上传</text>
              <text v-else-if="isThesisCode(m.materialCode) && ['MISSING','RETURNED'].includes(m.businessStatus)" class="gd__hint">论文请在上方「论文提交」步骤中提交</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileGraduationExtensionPanel />
    <MobileGraduationTempFileJanitor />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { isStaleReadError } from '@/services/latestRead'
import fileSdk from '@/services/fileSdk'
import { go, toast } from '@/utils/nav'

const MATERIAL_STATUS_LABEL = {
  MISSING: '未上传', NOT_SUBMITTED: '未上传', SUBMITTED: '已提交', PENDING: '待审核',
  NOT_REVIEWED: '待审核', APPROVED: '已通过', RETURNED: '需重交', REJECTED: '未通过',
  UNKNOWN: '结果待核对'
}
const MATERIAL_SCAN_LABEL = {
  PENDING: '安全检查中', SCANNING: '安全检查中', CLEAN: '安全检查通过', PASSED: '安全检查通过',
  INFECTED: '安全检查未通过', FAILED: '安全检查未通过', ERROR: '安全检查待核对', UNKNOWN: '安全检查待核对'
}
const STEP_TAG = { done: ['已完成', 'success'], todo: ['待办理', 'processing'], waiting: ['等待中', 'warning'], blocked: ['需处理', 'danger'], locked: ['未开始', 'default'] }

const MOBILE_DOC_MAX_BYTES = 20 * 1024 * 1024
const MOBILE_DOC_EXTENSIONS = ['pdf', 'doc', 'docx']
// 设计作品包、源代码通常为大体积压缩包，仍引导到电脑端；论文初稿/定稿可在手机提交。
const PC_ONLY_MATERIAL_CODES = ['DESIGN_WORK', 'SOURCE_CODE']
const THESIS_MATERIAL_CODES = ['THESIS_DRAFT', 'THESIS_FINAL']

/** 手机端论文/开题主文档的前置校验；最终类型、大小与安全扫描仍以后端材料规则为准。 */
function mobileDocumentProblem(file) {
  const name = String((file && (file.name || file.path || file.tempFilePath)) || '').toLowerCase()
  const ext = name.includes('.') ? name.slice(name.lastIndexOf('.') + 1) : ''
  if (!MOBILE_DOC_EXTENSIONS.includes(ext)) return '手机端请提交 PDF 或 Word 文档；作品包、源代码请到电脑端上传'
  if (Number((file && file.size) || 0) > MOBILE_DOC_MAX_BYTES) return '文件超过 20MB，请压缩后重试或到电脑端上传'
  return ''
}

// 每个步骤展开时需要加载的环节数据
const STEP_SECTIONS = {
  proposal: ['proposal', 'materials'],
  guidance: ['g'],
  midterm: ['midterm'],
  final: ['final', 'materials'],
  grade: ['grade', 'archive']
}
const SECTION_LABEL = { proposal: '开题', materials: '材料库', g: '指导记录', midterm: '中期', final: '论文', grade: '成绩', archive: '归档', peer: '互查' }

export default {
  data() {
    return {
      journey: null, state: 'loading', expanded: '', sectionLoading: false,
      g: null,
      proposal: null, showProposalForm: false, proposalSubmitting: false,
      propForm: { background: '', plan: '', outcome: '' },
      propAtts: [], finalAtts: [], uploading: false,
      final: null, finalSubmitting: false,
      midterm: null, rectifyContent: '', rectifySubmitting: false,
      grade: null, archive: null, materials: null, showMaterials: false, materialUploadingCode: '',
      showAppeal: false, appealReason: '', appealSubmitting: false,
      peer: { toReview: [], myRectify: [] }, peerOpinions: {}, peerNotes: {}, peerBusyId: '',
      processErrors: []
    }
  },
  computed: {
    current() { return (this.journey && this.journey.current) || null },
    currentTitle() {
      const c = this.current
      if (!c) return ''
      return c.state === 'todo' || c.state === 'blocked' ? `第 ${c.order} 步 · ${c.title}` : `等待中 · ${c.title}`
    },
    currentDescription() {
      const c = this.current
      return c ? [c.statusText, c.detail].filter(Boolean).join('：') : ''
    },
    progressPercent() {
      const j = this.journey
      return j && j.total ? Math.round((j.doneCount / j.total) * 100) : 0
    },
    hasPeerWork() {
      return ((this.peer && this.peer.toReview) || []).length > 0 || ((this.peer && this.peer.myRectify) || []).length > 0
    },
    finalRejected() {
      const items = (this.final && this.final.items) || []
      const r = items[0] && items[0].status === 'REJECTED' ? items[0] : null
      return r && r.reviewComment ? r.reviewComment : ''
    },
    midtermTagType() {
      const s = (this.midterm && this.midterm.status) || ''
      if (s === 'CHECKED_FAIL') return 'danger'
      if (s === 'RECTIFYING' || s === 'RECTIFY_SUBMITTED' || s === 'PENDING') return 'warning'
      if (s === 'CHECKED_PASS' || s === 'RECTIFIED_PASS') return 'success'
      return 'default'
    }
  },
  onLoad() { this.load() },
  // 返回本页 / 深链再次进入后刷新（首个 onShow 与 onLoad 配对，跳过避免重复请求）
  onShow() { if (this._entered) this.refresh(); this._entered = true },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.refresh(() => uni.stopPullDownRefresh())
  },
  methods: {
    go, toast,
    load(done) {
      if (!this.journey) this.state = 'loading'
      return studentApi.getGraduationJourney().then((j) => {
        const first = !this.journey
        this.journey = j
        this.state = 'ready'
        if (!j || !j.hasData) return
        if (first && !this.expanded && this.current && ['todo', 'blocked'].includes(this.current.state)) {
          this.expanded = this.current.key
        }
        return this.loadSections(['peer', ...(STEP_SECTIONS[this.expanded] || []), ...(this.showMaterials ? ['materials'] : [])])
      }).catch((e) => {
        if (isStaleReadError(e)) return
        if (!this.journey) this.state = 'error'
        else toast('刷新失败，请稍后重试')
      }).finally(() => { if (done) done() })
    },
    refresh(done) { return this.load(done) },
    // 兼容公共“部分环节加载失败”条的重试入口
    loadProcess() { return this.refresh() },
    loadSections(keys) {
      const loaders = {
        g: () => studentApi.getGraduation().then((d) => { this.g = d }),
        proposal: () => studentApi.getGraduationProposal().then((d) => { this.proposal = d }),
        final: () => studentApi.getGraduationFinal().then((d) => { this.final = d }),
        midterm: () => studentApi.getGraduationMidterm().then((d) => { this.midterm = d }),
        grade: () => studentApi.getGraduationGrade().then((d) => { this.grade = d }),
        archive: () => studentApi.getGraduationArchive().then((d) => { this.archive = d }),
        materials: () => studentApi.getGraduationMaterialLibrary().then((d) => { this.materials = d }),
        peer: () => studentApi.getGraduationPeerTasks().then((d) => { this.peer = d || { toReview: [], myRectify: [] } })
      }
      const unique = [...new Set(keys)].filter((k) => loaders[k])
      this.processErrors = this.processErrors.filter((label) => !unique.some((k) => SECTION_LABEL[k] === label))
      this.sectionLoading = unique.length > 0
      return Promise.all(unique.map((k) => loaders[k]().catch((error) => {
        // 账号/角色切换或本页刷新后的旧读取不能覆盖当前私有数据，也不应被误报为业务加载失败。
        if (isStaleReadError(error)) return null
        if (!this.processErrors.includes(SECTION_LABEL[k])) this.processErrors.push(SECTION_LABEL[k])
        return null
      }))).finally(() => { this.sectionLoading = false })
    },
    toggleStep(key) {
      if (this.expanded === key) { this.expanded = ''; return }
      this.openStep(key)
    },
    openStep(key) {
      this.expanded = key
      this.loadSections(STEP_SECTIONS[key] || [])
      this.$nextTick(() => uni.pageScrollTo({ selector: '#gd-' + key, duration: 260, fail: () => {} }))
    },
    toggleMaterials() {
      this.showMaterials = !this.showMaterials
      if (this.showMaterials) this.loadSections(['materials'])
    },
    stepTagLabel(step) { return (STEP_TAG[step.state] || STEP_TAG.locked)[0] },
    stepTagType(step) { return step.returned ? 'danger' : (STEP_TAG[step.state] || STEP_TAG.locked)[1] },
    submitPeer(pid) {
      const opinion = (this.peerOpinions[pid] || '').trim()
      if (opinion.length < 5 || this.peerBusyId) return
      this.peerBusyId = pid
      studentApi.submitGraduationPeer(pid, opinion).then(() => {
        uni.showToast({ title: '互查意见已提交', icon: 'success' })
        this.peerOpinions[pid] = ''
        this.refresh()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.peerBusyId = '' })
    },
    submitPeerRectify(pid) {
      const note = (this.peerNotes[pid] || '').trim()
      if (note.length < 5 || this.peerBusyId) return
      this.peerBusyId = pid
      studentApi.rectifyGraduationPeer(pid, note).then(() => {
        uni.showToast({ title: '整改说明已提交', icon: 'success' })
        this.peerNotes[pid] = ''
        this.refresh()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.peerBusyId = '' })
    },
    startProposal() {
      this.showProposalForm = true
      const l = this.proposal && this.proposal.latest
      // 重交时预填上一版内容，便于修改
      if (l) { this.propForm = { background: l.background || '', plan: l.plan || '', outcome: l.outcome || '' } }
    },
    async ensureMaterials() {
      if (!this.materials) await this.loadSections(['materials'])
    },
    async submitProposal() {
      const f = this.propForm
      if (!f.background.trim() || !f.plan.trim() || this.proposalSubmitting) return
      this.proposalSubmitting = true
      try {
        await this.ensureMaterials()
        await studentApi.submitGraduationProposal({
          background: f.background.trim(), plan: f.plan.trim(), outcome: f.outcome.trim(),
          attachments: this.propAtts.map((a) => a.fileId),
          expectedVersion: this.materialVersion('PROPOSAL_REPORT')
        })
        uni.showToast({ title: '开题报告已提交', icon: 'success' })
        this.showProposalForm = false
        this.propForm = { background: '', plan: '', outcome: '' }
        this.propAtts = []
        this.refresh()
      } catch (e) { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') }
      finally { this.proposalSubmitting = false }
    },
    submitAppeal() {
      const reason = this.appealReason.trim()
      if (reason.length < 5 || this.appealSubmitting) return
      this.appealSubmitting = true
      studentApi.appealGraduationGrade(reason).then(() => {
        uni.showToast({ title: '申诉已提交', icon: 'success' })
        this.showAppeal = false
        this.appealReason = ''
        this.refresh()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.appealSubmitting = false })
    },
    async submitFinal(finalType) {
      if (this.finalSubmitting) return
      if (!this.finalAtts.length) { toast('请先选择论文文件（PDF 或 Word）'); return }
      this.finalSubmitting = true
      try {
        await this.ensureMaterials()
        await studentApi.submitGraduationFinal({
          finalType,
          attachments: this.finalAtts.map((a) => a.fileId),
          expectedVersion: this.materialVersion(finalType === '定稿' ? 'THESIS_FINAL' : 'THESIS_DRAFT')
        })
        uni.showToast({ title: finalType + '已提交', icon: 'success' })
        this.finalAtts = []
        this.refresh()
      } catch (e) { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') }
      finally { this.finalSubmitting = false }
    },
    // 公共 File SDK：统一鉴权刷新、错误处理与上传合同。
    // 开题主文档、论文初稿/定稿可在手机提交（PDF/Word，≤20MB，可直接从微信聊天记录选择）；
    // 设计作品包、源代码等大型压缩包仍引导到学生 PC。
    async pickUpload(target) {
      if (this.uploading) return
      const arr = target === 'prop' ? 'propAtts' : 'finalAtts'
      this.uploading = true
      try {
        const selected = await fileSdk.choose()
        if (!selected) return
        const problem = mobileDocumentProblem(selected)
        if (problem) { toast(problem); return }
        const uploaded = await fileSdk.upload(selected, { bizType: 'GRADUATION_MATERIAL' })
        this[arr].splice(0, this[arr].length, {
          fileId: uploaded.fileId, fileName: uploaded.fileName || selected.name || '主文档'
        })
      } catch (e) { toast(normalizeError(e).text || '上传失败') }
      finally { this.uploading = false }
    },
    removeAtt(target, i) {
      const arr = target === 'prop' ? 'propAtts' : 'finalAtts'
      this[arr].splice(i, 1)
    },
    materialVersion(code) {
      const row = ((this.materials && this.materials.items) || []).find((item) => item.materialCode === code)
      return Number((row && row.version) || 0)
    },
    async downloadAtt(a) {
      const fileId = a && a.fileId
      if (!fileId) { toast('附件无效'); return }
      try {
        await fileSdk.openAuthorized({
          fileId,
          fileName: a.fileName,
          ticketPath: `/mobile/graduation/material-center/files/${encodeURIComponent(fileId)}/ticket`,
          openPath: `/mobile/graduation/material-center/files/${encodeURIComponent(fileId)}/preview`,
          action: 'preview'
        })
      } catch (e) { toast(normalizeError(e).text || '附件暂不可预览') }
    },
    materialCount(status) { return ((this.materials && this.materials.items) || []).filter((m) => m.businessStatus === status || m.reviewStatus === status).length },
    materialVersionText(material) {
      const version = material && material.currentVersion && material.currentVersion.versionNo
      return version ? `当前第 ${version} 版` : '尚未上传版本'
    },
    materialScanLabel(status) { return MATERIAL_SCAN_LABEL[status] || (status ? '安全检查待核对' : '尚未进入安全检查') },
    materialStatusLabel(material) {
      const review = material && material.reviewStatus
      const business = material && material.businessStatus
      const status = review && review !== 'NOT_REVIEWED' ? review : business
      return MATERIAL_STATUS_LABEL[status] || '状态待核对'
    },
    materialStatusType(material) {
      const status = (material && material.reviewStatus && material.reviewStatus !== 'NOT_REVIEWED') ? material.reviewStatus : (material && material.businessStatus)
      if (status === 'APPROVED') return 'success'
      if (['RETURNED', 'REJECTED'].includes(status)) return 'danger'
      return 'warning'
    },
    isPcOnly(code) { return PC_ONLY_MATERIAL_CODES.includes(code) },
    isThesisCode(code) { return THESIS_MATERIAL_CODES.includes(code) },
    // 论文初稿/定稿走「论文提交」步骤（生成成果记录并进入导师批阅），不在材料库重复提供入口。
    canMiniSubmit(material) {
      return !this.isPcOnly(material.materialCode)
        && !this.isThesisCode(material.materialCode)
        && ['MISSING', 'RETURNED'].includes(material.businessStatus)
    },
    async openMaterial(material) { return this.downloadAtt(material.currentVersion || {}) },
    async submitSmallMaterial(material) {
      if (this.materialUploadingCode) return
      this.materialUploadingCode = material.materialCode
      try {
        const selected = await fileSdk.choose()
        if (!selected) return
        if (Number(selected.size || 0) > MOBILE_DOC_MAX_BYTES) { toast('手机端仅支持 20MB 以内材料，请到电脑端上传'); return }
        const uploaded = await fileSdk.upload(selected, { bizType: 'GRADUATION_MATERIAL', bizId: material.materialId })
        await studentApi.submitGraduationMaterial(material.materialCode, {
          fileId: uploaded.fileId, expectedVersion: material.version
        })
        uni.showToast({ title: '材料已提交', icon: 'success' })
        this.materials = await studentApi.getGraduationMaterialLibrary()
      } catch (e) { toast(normalizeError(e).text || '材料提交失败') }
      finally { this.materialUploadingCode = '' }
    },
    submitRectify() {
      const content = this.rectifyContent.trim()
      if (!content || this.rectifySubmitting) return
      this.rectifySubmitting = true
      studentApi.submitGraduationMidtermRectify(content).then(() => {
        uni.showToast({ title: '整改已提交', icon: 'success' })
        this.rectifyContent = ''
        this.refresh()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.rectifySubmitting = false })
    }
  }
}
</script>

<style scoped>
.gd__hero-top { display: flex; align-items: center; justify-content: space-between; }
.gd__hero-batch { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.gd__hero-stage { flex-shrink: 0; font-size: var(--font-size-xs); color: #fff; background: var(--brand-primary); padding: 2px 10px; border-radius: var(--radius-full); }
.gd__hero-topic { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); margin: 6px 0; line-height: 1.4; }
.gd__hero-mentor { font-size: var(--font-size-sm); color: var(--text-secondary); }
.gd__progress { margin-top: var(--space-3); height: 6px; border-radius: var(--radius-full); background: var(--gray-100); overflow: hidden; }
.gd__progress-bar { height: 100%; background: var(--brand-primary); border-radius: var(--radius-full); }
.gd__steps { padding-top: 0; padding-bottom: 0; }
.gd__step { border-bottom: 1px solid var(--border-light); }
.gd__step:last-of-type { border-bottom: none; }
.gd__step-row { display: flex; align-items: center; gap: var(--space-3); min-height: var(--touch-target-min); padding: var(--space-3) 0; }
.gd__step-no { flex-shrink: 0; width: 26px; height: 26px; line-height: 26px; text-align: center; border-radius: var(--radius-full); font-size: var(--font-size-sm); color: var(--text-tertiary); background: var(--gray-100); }
.gd__step-no.is-success { color: #fff; background: var(--success-500); }
.gd__step-no.is-primary { color: #fff; background: var(--brand-primary); }
.gd__step-no.is-warning { color: var(--warning-700); background: var(--warning-50); }
.gd__step-no.is-danger { color: #fff; background: var(--danger-500); }
.gd__step-title { display: block; font-size: var(--font-size-base); color: var(--text-primary); font-weight: var(--font-weight-medium); }
.gd__step-status { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 2px; }
.gd__panel { padding: 0 0 var(--space-3) 38px; }
.gd__linkrow { display: flex; align-items: center; gap: var(--space-3); }
.gd__arrow { color: var(--text-tertiary); font-size: var(--font-size-2xl); }
.gd__log { border-left: 3px solid var(--primary-100); padding-left: var(--space-3); }
.gd__log-head { display: flex; align-items: center; justify-content: space-between; }
.gd__log-from { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--brand-primary); }
.gd__log-date { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.gd__log-text { display: block; font-size: var(--font-size-base); color: var(--text-secondary); margin-top: 4px; line-height: 1.5; }
.gd__log-issue { display: block; font-size: var(--font-size-sm); color: var(--warning-600); margin-top: 4px; line-height: 1.5; }
.gd__hint { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-bottom: var(--space-2); }
.gd__final-item { padding-bottom: var(--space-2); border-bottom: 1px solid var(--border-light); }
.gd__final-item:last-of-type { border-bottom: none; }
.gd__atts { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; margin: var(--space-2) 0; }
.gd__att { font-size: var(--font-size-sm); color: var(--brand-primary); background: var(--primary-50); border: 1px solid var(--primary-100); padding: 5px 10px; border-radius: var(--radius-md); }
.gd__att--pending { color: var(--text-secondary); background: var(--gray-50); border-color: var(--border-base); }
.gd__att-x { color: var(--danger-500); font-weight: var(--font-weight-semibold); }
.gd__att-add { min-height: 34px; padding: 0 var(--space-3); font-size: var(--font-size-sm); }
.gd__choice-row { display: flex; align-items: center; justify-content: space-between; }
.gd__choice-title { font-size: var(--font-size-base); color: var(--text-primary); }
.gd__reason { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; margin: var(--space-2) 0; }
</style>
