<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="g && !g.hasBatch">
        <MobileGlobalState state="empty" title="当前暂无毕业设计任务" description="进入毕业设计阶段后，这里会显示课题、任务书、开题、中期、答辩等节点。" />
      </view>
      <view class="page-pad stack" v-else-if="g">
        <!-- 课题卡 -->
        <view class="gd__hero card">
          <view class="gd__hero-top">
            <text class="gd__hero-batch">{{ g.batch }}</text>
            <text v-if="g.stageLabel" class="gd__hero-stage">{{ g.stageLabel }}</text>
          </view>
          <text class="gd__hero-topic">{{ g.topic }}</text>
          <text class="gd__hero-mentor">指导教师 · {{ g.mentor }}</text>
        </view>

        <!-- 当前主任务：按钮定位到本页对应真实功能区（不再跳 PC 端） -->
        <MobileActionCard
          :title="g.primaryAction.title"
          :description="g.primaryAction.desc"
          icon="→"
          :action-text="g.primaryAction.actionText"
          @action="goPrimary"
          @click="goPrimary"
        />

        <!-- 快速导航：滚动到本页真实功能区（仅显示有内容的入口，取代旧假入口） -->
        <view v-if="quickNav.length" class="gd__quicknav card">
          <text v-for="n in quickNav" :key="n.anchor" class="gd__quick" @click="scrollTo(n.anchor)">{{ n.label }}</text>
        </view>

        <!-- 节点进度 -->
        <view id="gd-nodes" class="section-head"><text class="section-head__title">毕设节点</text></view>
        <view class="card"><MobileTimeline :nodes="g.nodes" /></view>

        <!-- 选题管理：轻量入口，详情/操作在独立的「毕设选题」页 -->
        <view id="gd-topic" class="section-head"><text class="section-head__title">选题管理</text></view>
        <view class="card gd__linkrow" @click="go('/pages/student/graduation/topics/index')">
          <view class="flex-1">
            <text class="t-md t-bold">{{ g.hasTopic ? '课题已确定' : '选题/志愿管理' }}</text>
            <text class="gd__hint" style="margin:2px 0 0;">{{ g.hasTopic ? '点击查看课题与申请更换' : '点击查看题目库、提交或调整志愿' }}</text>
          </view>
          <text class="gd__arrow">›</text>
        </view>

        <!-- 开题报告 -->
        <view v-if="proposal && proposal.hasData" id="gd-proposal" class="section-head"><text class="section-head__title">开题报告</text></view>
        <view v-if="proposal && proposal.hasData" class="card stack-sm">
          <view v-if="proposal.latest" class="gd__choice-row">
            <text class="gd__choice-title">{{ proposal.latest.version }} · {{ proposal.latest.statusLabel }}</text>
            <MobileStatusTag :label="proposal.latest.statusLabel"
                             :type="proposal.latest.status === 'APPROVED' ? 'success' : proposal.latest.status === 'REJECTED' ? 'danger' : 'warning'" />
          </view>
          <MobileInlineAlert v-if="proposal.latest && proposal.latest.status === 'REJECTED' && proposal.latest.reviewComment"
                             type="danger" title="开题被驳回" :description="proposal.latest.reviewComment" />
          <view v-if="proposal.latest && proposal.latest.attachmentsList && proposal.latest.attachmentsList.length" class="gd__atts">
            <text v-for="a in proposal.latest.attachmentsList" :key="a.fileId" class="gd__att" @click="downloadAtt(a)">📎 {{ a.fileName }}</text>
          </view>
          <text v-if="!proposal.canSubmit && proposal.reason" class="gd__hint">{{ proposal.reason }}</text>
          <button v-if="proposal.canSubmit && !showProposalForm" class="btn btn-primary" @click="startProposal">
            {{ proposal.latest && proposal.latest.status === 'REJECTED' ? '修改后重交开题报告' : '提交开题报告' }}
          </button>
          <template v-if="proposal.canSubmit && showProposalForm">
            <textarea class="gd__reason" v-model="propForm.background" :maxlength="2000" placeholder="选题背景（必填）" placeholder-class="wr__ph" />
            <textarea class="gd__reason" v-model="propForm.plan" :maxlength="2000" placeholder="研究方案与进度（必填）" placeholder-class="wr__ph" />
            <textarea class="gd__reason" v-model="propForm.outcome" :maxlength="2000" placeholder="预期成果（选填）" placeholder-class="wr__ph" />
            <view class="gd__atts">
              <text v-for="(a, i) in propAtts" :key="a.fileId" class="gd__att gd__att--pending">📎 {{ a.fileName }}<text class="gd__att-x" @click.stop="removeAtt('prop', i)"> ×</text></text>
              <button class="btn btn-ghost gd__att-add" :disabled="uploading" @click="pickUpload('prop')">{{ uploading ? '上传中…' : '+ 添加附件' }}</button>
            </view>
            <button class="btn btn-primary" :disabled="!propForm.background.trim() || !propForm.plan.trim() || proposalSubmitting" @click="submitProposal">
              {{ proposalSubmitting ? '提交中…' : '提交开题报告' }}
            </button>
          </template>
        </view>

        <!-- 任务书：轻量入口，详情/确认在独立的「毕设任务书」页 -->
        <view id="gd-taskbook" class="section-head"><text class="section-head__title">任务书</text></view>
        <view class="card gd__linkrow" @click="go('/pages/student/graduation/taskbook/index')">
          <view class="flex-1">
            <text class="t-md t-bold">查看任务书</text>
            <text class="gd__hint" style="margin:2px 0 0;">研究内容、进度安排与确认</text>
          </view>
          <text class="gd__arrow">›</text>
        </view>

        <!-- 中期检查（含 PENDING「待导师检查」） -->
        <view v-if="midterm && midterm.hasData" id="gd-midterm" class="section-head"><text class="section-head__title">中期检查</text></view>
        <view v-if="midterm && midterm.hasData" class="card stack-sm">
          <view class="gd__choice-row"><text class="gd__choice-title">{{ midterm.conclusionLabel || midterm.statusLabel }}</text><MobileStatusTag :label="midterm.statusLabel" :type="midtermTagType" /></view>
          <template v-if="midterm.status === 'RECTIFYING'">
            <text v-if="midterm.checkComment" class="gd__hint">检查意见：{{ midterm.checkComment }}</text>
            <text v-if="midterm.rectifyDeadline" class="gd__hint">整改截止：{{ midterm.rectifyDeadline }}</text>
            <textarea class="gd__reason" v-model="rectifyContent" :maxlength="500" placeholder="填写整改内容后提交" placeholder-class="wr__ph" />
            <button class="btn btn-primary" :disabled="!rectifyContent.trim() || rectifySubmitting" @click="submitRectify">
              {{ rectifySubmitting ? '提交中…' : '提交整改' }}
            </button>
          </template>
        </view>

        <!-- 成果提交（论文初稿/定稿） -->
        <view v-if="final && final.hasData" id="gd-final" class="section-head"><text class="section-head__title">成果提交</text></view>
        <view v-if="final && final.hasData" class="card stack-sm">
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
          <MobileInlineAlert v-if="finalRejected" type="danger" title="成果被退回" :description="finalRejected" />
          <text class="gd__hint">{{ final.hint }}</text>
          <view v-if="final.canSubmitDraft || final.canSubmitFinal" class="gd__atts">
            <text v-for="(a, i) in finalAtts" :key="a.fileId" class="gd__att gd__att--pending">📎 {{ a.fileName }}<text class="gd__att-x" @click.stop="removeAtt('final', i)"> ×</text></text>
            <button class="btn btn-ghost gd__att-add" :disabled="uploading" @click="pickUpload('final')">{{ uploading ? '上传中…' : '+ 添加论文附件' }}</button>
          </view>
          <button v-if="final.canSubmitDraft" class="btn btn-primary" :disabled="finalSubmitting || !finalAtts.length" @click="submitFinal('初稿')">
            {{ finalSubmitting ? '提交中…' : '提交论文初稿' }}
          </button>
          <button v-if="final.canSubmitFinal" class="btn btn-primary" :disabled="finalSubmitting || !finalAtts.length" @click="submitFinal('定稿')">
            {{ finalSubmitting ? '提交中…' : '提交论文定稿' }}
          </button>
        </view>

        <!-- 答辩安排：轻量入口，详情在独立的「答辩安排」页 -->
        <view v-if="defense && defense.assigned" id="gd-defense" class="section-head"><text class="section-head__title">答辩安排</text></view>
        <view v-if="defense && defense.assigned" class="card gd__linkrow" @click="go('/pages/student/graduation/defense/index')">
          <view class="flex-1">
            <text class="t-md t-bold">{{ defense.groupName }}</text>
            <text class="gd__hint" style="margin:2px 0 0;">{{ defense.published ? ('时间：' + defense.date + ' · 地点：' + defense.location) : defense.message }}</text>
          </view>
          <MobileStatusTag :label="defense.published ? '已发布' : '编制中'" :type="defense.published ? 'success' : 'warning'" />
        </view>

        <!-- 成绩 -->
        <view v-if="grade && grade.published" id="gd-grade" class="section-head"><text class="section-head__title">毕设成绩</text></view>
        <view v-if="grade && grade.published" class="card stack-sm">
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
        </view>

        <!-- 统一材料库：状态、版本、退回原因和小型材料补交 -->
        <view v-if="materials" id="gd-materials" class="section-head"><text class="section-head__title">材料库</text></view>
        <view v-if="materials" class="card stack-sm">
          <view class="gd__choice-row"><text class="gd__choice-title">18 类材料 · 缺 {{ materialCount('MISSING') }} · 退回 {{ materialCount('RETURNED') }}</text></view>
          <view v-for="m in materials.items || []" :key="m.materialId" class="gd__final-item">
            <view class="gd__choice-row">
              <view class="flex-1"><text class="gd__choice-title">{{ m.materialName }}</text><text class="gd__hint">{{ m.materialCode }} · 当前版本 {{ m.currentVersion?.versionNo || '—' }} · {{ m.currentVersion?.scanStatus || '未上传' }}</text></view>
              <MobileStatusTag :label="m.reviewStatus || m.businessStatus" :type="m.reviewStatus === 'APPROVED' ? 'success' : m.reviewStatus === 'RETURNED' ? 'danger' : 'warning'" />
            </view>
            <MobileInlineAlert v-if="m.rejectReason" type="danger" title="需要重交" :description="m.rejectReason" />
            <view class="gg__actions">
              <button v-if="m.currentVersion?.fileId && (m.currentVersion.allowedActions || []).includes('preview')" class="btn btn-ghost" @click="openMaterial(m)">安全预览</button>
              <button v-if="canMiniSubmit(m)" class="btn btn-primary" :disabled="materialUploadingCode === m.materialCode" @click="submitSmallMaterial(m)">{{ materialUploadingCode === m.materialCode ? '上传中…' : '补交小型材料' }}</button>
              <text v-else-if="isPcOnly(m.materialCode) && ['MISSING','RETURNED'].includes(m.businessStatus)" class="gd__hint">大型论文、作品或源代码请到学生 PC 上传</text>
            </view>
          </view>
        </view>

        <!-- 归档 -->
        <view v-if="archive && archive.hasData" id="gd-archive" class="section-head"><text class="section-head__title">材料归档</text></view>
        <view v-if="archive && archive.hasData" class="card stack-sm">
          <view class="gd__choice-row">
            <text class="gd__choice-title">归档状态</text>
            <MobileStatusTag :label="archive.statusLabel || archive.status || '—'" type="default" />
          </view>
          <view v-if="archive.checklist && archive.checklist.length" class="stack-sm">
            <text v-for="(c, i) in archive.checklist" :key="c.item || i" class="gd__hint">
              {{ c.present ? '✓' : '○' }} {{ c.label || c.item }}
            </text>
          </view>
        </view>

        <!-- 互查任务：待我互查 / 我需整改 -->
        <view v-if="hasPeerWork" id="gd-peer" class="section-head"><text class="section-head__title">成果互查</text></view>
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

        <!-- 指导记录（真实，最新在前；无记录空态） -->
        <view id="gd-guidance" class="section-head"><text class="section-head__title">指导记录</text></view>
        <view class="card stack-sm">
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
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import fileSdk from '@/services/fileSdk'
import { go, toast } from '@/utils/nav'

export default {
  data() {
    return {
      g: null, state: 'loading',
      proposal: null, showProposalForm: false, proposalSubmitting: false,
      propForm: { background: '', plan: '', outcome: '' },
      propAtts: [], finalAtts: [], uploading: false,
      final: null, finalSubmitting: false,
      midterm: null, rectifyContent: '', rectifySubmitting: false,
      defense: null, grade: null, archive: null,
      showAppeal: false, appealReason: '', appealSubmitting: false,
      peer: { toReview: [], myRectify: [] }, peerOpinions: {}, peerNotes: {}, peerBusyId: '',
      processErrors: []
    }
  },
  computed: {
    hasPeerWork() {
      return ((this.peer && this.peer.toReview) || []).length > 0 || ((this.peer && this.peer.myRectify) || []).length > 0
    },
    finalRejected() {
      const items = (this.final && this.final.items) || []
      const r = items.find((i) => i.status === 'REJECTED')
      return r && r.reviewComment ? r.reviewComment : ''
    },
    midtermTagType() {
      const s = (this.midterm && this.midterm.status) || ''
      if (s === 'CHECKED_FAIL') return 'danger'
      if (s === 'RECTIFYING' || s === 'RECTIFY_SUBMITTED' || s === 'PENDING') return 'warning'
      if (s === 'CHECKED_PASS' || s === 'RECTIFIED_PASS') return 'success'
      return 'default'
    },
    // 快速导航：仅显示本页已有真实内容的功能区；选题/任务书为独立页固定入口
    quickNav() {
      const nav = [{ label: '节点', anchor: 'nodes' }, { label: '选题', anchor: 'topic' }, { label: '任务书', anchor: 'taskbook' }]
      if (this.proposal && this.proposal.hasData) nav.push({ label: '开题', anchor: 'proposal' })
      if (this.midterm && this.midterm.hasData) nav.push({ label: '中期', anchor: 'midterm' })
      if (this.final && this.final.hasData) nav.push({ label: '成果', anchor: 'final' })
      if (this.defense && this.defense.assigned) nav.push({ label: '答辩', anchor: 'defense' })
      if (this.grade && this.grade.published) nav.push({ label: '成绩', anchor: 'grade' })
      if (this.materials) nav.push({ label: '材料', anchor: 'materials' })
      if (this.archive && this.archive.hasData) nav.push({ label: '归档', anchor: 'archive' })
      if (this.hasPeerWork) nav.push({ label: '互查', anchor: 'peer' })
      nav.push({ label: '指导记录', anchor: 'guidance' })
      return nav
    }
  },
  onLoad() { this.load() },
  // 返回本页 / 深链再次进入后刷新（首个 onShow 与 onLoad 配对，跳过避免重复请求）
  onShow() { if (this._entered) this.load(); this._entered = true },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    go, toast,
    load(done) {
      // 保留已加载内容时不闪 loading（下拉刷新/返回刷新场景）
      if (!this.g) this.state = 'loading'
      studentApi.getGraduation().then((d) => {
        this.g = d
        this.state = 'ready'
        if (d && d._real && d.hasBatch) {
          this.loadProcess()
        }
      }).catch(() => { if (!this.g) this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    loadProcess() {
      this.processErrors = []
      const track = (label, p) => p.catch(() => {
        this.processErrors.push(label)
        return null
      })
      Promise.all([
        track('开题', studentApi.getGraduationProposal().then((d) => { this.proposal = d })),
        track('成果', studentApi.getGraduationFinal().then((d) => { this.final = d })),
        track('中期', studentApi.getGraduationMidterm().then((d) => { this.midterm = d })),
        track('答辩', studentApi.getGraduationDefense().then((d) => { this.defense = d })),
        track('成绩', studentApi.getGraduationGrade().then((d) => { this.grade = d })),
        track('互查', studentApi.getGraduationPeerTasks().then((d) => { this.peer = d || { toReview: [], myRectify: [] } })),
        track('归档', studentApi.getGraduationArchive().then((d) => { this.archive = d })),
        track('材料库', studentApi.getGraduationMaterialLibrary().then((d) => { this.materials = d }))
      ]).then(() => {
        if (this.processErrors.length) toast('部分环节加载失败')
      })
    },
    submitPeer(pid) {
      const opinion = (this.peerOpinions[pid] || '').trim()
      if (opinion.length < 5 || this.peerBusyId) return
      this.peerBusyId = pid
      studentApi.submitGraduationPeer(pid, opinion).then(() => {
        uni.showToast({ title: '互查意见已提交', icon: 'success' })
        this.peerOpinions[pid] = ''
        this.loadProcess()
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
        this.loadProcess()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.peerBusyId = '' })
    },
    startProposal() {
      this.showProposalForm = true
      const l = this.proposal && this.proposal.latest
      // 重交时预填上一版内容，便于修改
      if (l) { this.propForm = { background: l.background || '', plan: l.plan || '', outcome: l.outcome || '' } }
    },
    submitProposal() {
      const f = this.propForm
      if (!f.background.trim() || !f.plan.trim() || this.proposalSubmitting) return
      this.proposalSubmitting = true
      studentApi.submitGraduationProposal({
        background: f.background.trim(), plan: f.plan.trim(), outcome: f.outcome.trim(),
        attachments: this.propAtts.map((a) => a.fileId)
      }).then(() => {
        uni.showToast({ title: '开题报告已提交', icon: 'success' })
        this.showProposalForm = false
        this.propForm = { background: '', plan: '', outcome: '' }
        this.propAtts = []
        this.loadProcess()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.proposalSubmitting = false })
    },
    submitAppeal() {
      const reason = this.appealReason.trim()
      if (reason.length < 5 || this.appealSubmitting) return
      this.appealSubmitting = true
      studentApi.appealGraduationGrade(reason).then(() => {
        uni.showToast({ title: '申诉已提交', icon: 'success' })
        this.showAppeal = false
        this.appealReason = ''
        this.loadProcess()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.appealSubmitting = false })
    },
    submitFinal(finalType) {
      if (this.finalSubmitting) return
      if (!this.finalAtts.length) { toast('请先上传论文附件（PDF/Word/ZIP）'); return }
      this.finalSubmitting = true
      studentApi.submitGraduationFinal({ finalType, attachments: this.finalAtts.map((a) => a.fileId) }).then(() => {
        uni.showToast({ title: finalType + '已提交', icon: 'success' })
        this.finalAtts = []
        this.loadProcess()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.finalSubmitting = false })
    },
    // 公共 File SDK：统一鉴权刷新、错误处理与上传合同；小程序不承担大型论文/ZIP上传。
    async pickUpload(target) {
      if (this.uploading) return
      // #ifdef MP-WEIXIN
      if (target === 'final') { toast('论文定稿、作品和源代码请使用学生 PC 上传'); return }
      // #endif
      const arr = target === 'prop' ? 'propAtts' : 'finalAtts'
      this.uploading = true
      try {
        const selected = await fileSdk.choose()
        if (!selected) return
        const uploaded = await fileSdk.upload(selected, { bizType: 'GRADUATION_MATERIAL' })
        this[arr].push({ fileId: uploaded.fileId, fileName: uploaded.fileName || selected.name || '附件' })
      } catch (e) { toast(normalizeError(e).text || '上传失败') }
      finally { this.uploading = false }
    },
    removeAtt(target, i) {
      const arr = target === 'prop' ? 'propAtts' : 'finalAtts'
      this[arr].splice(i, 1)
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
    isPcOnly(code) { return ['THESIS_DRAFT', 'THESIS_FINAL', 'DESIGN_WORK', 'SOURCE_CODE', 'WORK_DESCRIPTION'].includes(code) },
    canMiniSubmit(material) { return !this.isPcOnly(material.materialCode) && ['MISSING', 'RETURNED'].includes(material.businessStatus) },
    async openMaterial(material) { return this.downloadAtt(material.currentVersion || {}) },
    async submitSmallMaterial(material) {
      if (this.materialUploadingCode) return
      this.materialUploadingCode = material.materialCode
      try {
        const selected = await fileSdk.choose()
        if (!selected) return
        if (Number(selected.size || 0) > 8 * 1024 * 1024) { toast('小程序仅支持 8MB 以内材料，请到学生 PC 上传'); return }
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
        this.loadProcess()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.rectifySubmitting = false })
    },
    // 定位到本页真实功能区；目标未渲染时回退到节点区并提示
    scrollTo(anchor) {
      const id = '#gd-' + anchor
      uni.createSelectorQuery().in(this).select(id).boundingClientRect((rect) => {
        if (!rect) {
          toast('当前环节暂无可展示内容')
          uni.pageScrollTo({ selector: '#gd-nodes', duration: 260, fail: () => {} })
          return
        }
        uni.pageScrollTo({ selector: id, duration: 260, fail: () => toast('定位失败') })
      }).exec()
    },
    goPrimary() {
      const a = (this.g && this.g.primaryAction && this.g.primaryAction.anchor) || 'nodes'
      // 中期无数据 / 成绩未发布时，主按钮勿滚到隐藏区
      if (a === 'midterm' && !(this.midterm && this.midterm.hasData)) {
        toast('中期检查尚未开始')
        this.scrollTo('nodes')
        return
      }
      if (a === 'grade' && !(this.grade && this.grade.published)) {
        toast('成绩尚未发布')
        this.scrollTo('nodes')
        return
      }
      this.scrollTo(a)
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
.gd__quicknav { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.gd__quick { font-size: var(--font-size-sm); color: var(--brand-primary); background: var(--primary-50); border: 1px solid var(--primary-100); padding: 6px 14px; border-radius: var(--radius-full); }
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
.gd__topic-row { display: flex; align-items: center; justify-content: space-between; padding: var(--space-3) 0; border-bottom: 1px solid var(--border-light); }
.gd__topic-row:last-of-type { border-bottom: none; }
.gd__topic-main { display: flex; flex-direction: column; gap: 2px; }
.gd__topic-title { font-size: var(--font-size-base); color: var(--text-primary); font-weight: var(--font-weight-medium); }
.gd__topic-sub { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.gd__topic-badge { flex-shrink: 0; font-size: var(--font-size-xs); color: #fff; background: var(--brand-primary); padding: 3px 10px; border-radius: var(--radius-full); }
.gd__reason { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; margin: var(--space-2) 0; }
</style>
