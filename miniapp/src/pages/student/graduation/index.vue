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

        <!-- 中期检查 -->
        <view v-if="midterm && midterm.hasData && midterm.status !== 'PENDING'" id="gd-midterm" class="section-head"><text class="section-head__title">中期检查</text></view>
        <view v-if="midterm && midterm.hasData && midterm.status !== 'PENDING'" class="card stack-sm">
          <view class="gd__choice-row"><text class="gd__choice-title">{{ midterm.conclusionLabel || midterm.statusLabel }}</text><MobileStatusTag :label="midterm.statusLabel" :type="midtermTagType" /></view>
          <template v-if="midterm.status === 'RECTIFYING'">
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
          <button v-if="final.canSubmitDraft" class="btn btn-primary" :disabled="finalSubmitting" @click="submitFinal('初稿')">
            {{ finalSubmitting ? '提交中…' : '提交论文初稿' }}
          </button>
          <button v-if="final.canSubmitFinal" class="btn btn-primary" :disabled="finalSubmitting" @click="submitFinal('定稿')">
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
          <button v-if="!showAppeal" class="btn btn-ghost" @click="showAppeal = true">对成绩有异议？发起更正申诉</button>
          <template v-else>
            <textarea class="gd__reason" v-model="appealReason" :maxlength="500" placeholder="申诉理由（至少5字）" placeholder-class="wr__ph" />
            <button class="btn btn-primary" :disabled="appealReason.trim().length < 5 || appealSubmitting" @click="submitAppeal">
              {{ appealSubmitting ? '提交中…' : '提交申诉' }}
            </button>
          </template>
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
import { normalizeError, getToken } from '@/services/request'
import { go, toast } from '@/utils/nav'
import { ENV } from '@/config/env'

export default {
  data() {
    return {
      g: null, state: 'loading',
      proposal: null, showProposalForm: false, proposalSubmitting: false,
      propForm: { background: '', plan: '', outcome: '' },
      propAtts: [], finalAtts: [], uploading: false,
      final: null, finalSubmitting: false,
      midterm: null, rectifyContent: '', rectifySubmitting: false,
      defense: null, grade: null,
      showAppeal: false, appealReason: '', appealSubmitting: false
    }
  },
  computed: {
    finalRejected() {
      const items = (this.final && this.final.items) || []
      const r = items.find((i) => i.status === 'REJECTED')
      return r && r.reviewComment ? r.reviewComment : ''
    },
    midtermTagType() {
      const s = (this.midterm && this.midterm.status) || ''
      if (s === 'CHECKED_FAIL') return 'danger'
      if (s === 'RECTIFYING' || s === 'RECTIFY_SUBMITTED') return 'warning'
      if (s === 'CHECKED_PASS' || s === 'RECTIFIED_PASS') return 'success'
      return 'default'
    },
    // 快速导航：仅显示本页已有真实内容的功能区；选题/任务书为独立页固定入口
    quickNav() {
      const nav = [{ label: '节点', anchor: 'nodes' }, { label: '选题', anchor: 'topic' }, { label: '任务书', anchor: 'taskbook' }]
      if (this.proposal && this.proposal.hasData) nav.push({ label: '开题', anchor: 'proposal' })
      if (this.midterm && this.midterm.hasData && this.midterm.status !== 'PENDING') nav.push({ label: '中期', anchor: 'midterm' })
      if (this.final && this.final.hasData) nav.push({ label: '成果', anchor: 'final' })
      if (this.defense && this.defense.assigned) nav.push({ label: '答辩', anchor: 'defense' })
      if (this.grade && this.grade.published) nav.push({ label: '成绩', anchor: 'grade' })
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
      studentApi.getGraduationProposal().then((d) => { this.proposal = d }).catch(() => {})
      studentApi.getGraduationFinal().then((d) => { this.final = d }).catch(() => {})
      studentApi.getGraduationMidterm().then((d) => { this.midterm = d }).catch(() => {})
      studentApi.getGraduationDefense().then((d) => { this.defense = d }).catch(() => {})
      studentApi.getGraduationGrade().then((d) => { this.grade = d }).catch(() => {})
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
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.appealSubmitting = false })
    },
    submitFinal(finalType) {
      if (this.finalSubmitting) return
      this.finalSubmitting = true
      studentApi.submitGraduationFinal({ finalType, attachments: this.finalAtts.map((a) => a.fileId) }).then(() => {
        uni.showToast({ title: finalType + '已提交', icon: 'success' })
        this.finalAtts = []
        this.loadProcess()
      }).catch((e) => { toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试') })
        .finally(() => { this.finalSubmitting = false })
    },
    // 附件：选择 → 校验大小/类型 → 真实上传文件中心 → 记录 file_id（提交时随材料一起提交）
    pickUpload(target) {
      if (this.uploading) return
      const arr = target === 'prop' ? 'propAtts' : 'finalAtts'
      const MAX_IMAGE = 5 * 1024 * 1024
      const MAX_DOC = 10 * 1024 * 1024
      const ALLOWED_EXT = ['jpg', 'jpeg', 'png', 'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx']
      const extOf = (name) => (name || '').split('.').pop().toLowerCase()
      const checkFile = (name, size, isImage) => {
        const ext = extOf(name)
        if (!isImage && ext && ALLOWED_EXT.indexOf(ext) < 0) {
          toast('不支持的文件类型：.' + ext); return false
        }
        const limit = isImage ? MAX_IMAGE : MAX_DOC
        if (typeof size === 'number' && size > limit) {
          toast('文件过大，请控制在 ' + (limit / 1024 / 1024) + 'MB 以内'); return false
        }
        return true
      }
      const doUpload = (path, name, size) => {
        this.uploading = true
        const token = getToken()
        uni.uploadFile({
          url: ENV.apiBaseUrl + ENV.apiPrefix + '/files/upload', filePath: path, name: 'file',
          header: token ? { Authorization: 'Bearer ' + token } : {},
          success: (res) => {
            try {
              const body = JSON.parse(res.data)
              if (body && body.code === 0 && body.data) {
                this[arr].push({ fileId: body.data.fileId, fileName: body.data.fileName || name || '附件' })
              } else { toast((body && body.message) || '上传失败') }
            } catch (e) { toast('上传失败') }
          },
          fail: () => { toast('上传失败，请检查网络') },
          complete: () => { this.uploading = false }
        })
      }
      // #ifdef H5 || APP-PLUS
      uni.chooseFile ? uni.chooseFile({ count: 1, success: (r) => {
        const f = r.tempFiles && r.tempFiles[0]
        if (!f || !checkFile(f.name, f.size, false)) return
        doUpload(r.tempFilePaths[0], f.name, f.size)
      } })
        : uni.chooseImage({ count: 1, sizeType: ['compressed'], success: (r) => {
          const f = r.tempFiles && r.tempFiles[0]
          if (f && !checkFile('image.jpg', f.size, true)) return
          doUpload(r.tempFilePaths[0], 'image.jpg', f && f.size)
        } })
      // #endif
      // #ifdef MP-WEIXIN
      uni.chooseMessageFile({ count: 1, type: 'file', success: (r) => {
        const f = r.tempFiles[0]
        if (!f || !checkFile(f.name, f.size, false)) return
        doUpload(f.path, f.name, f.size)
      } })
      // #endif
    },
    removeAtt(target, i) {
      const arr = target === 'prop' ? 'propAtts' : 'finalAtts'
      this[arr].splice(i, 1)
    },
    downloadAtt(a) {
      const token = getToken()
      uni.showLoading({ title: '下载中' })
      uni.downloadFile({
        url: ENV.apiBaseUrl + ENV.apiPrefix + '/files/download/' + a.fileId,
        header: token ? { Authorization: 'Bearer ' + token } : {},
        success: (res) => {
          uni.hideLoading()
          if (res.statusCode !== 200) { toast('下载失败或无权限'); return }
          // #ifdef H5
          try { const link = document.createElement('a'); link.href = res.tempFilePath; link.download = a.fileName; link.click() } catch (e) { toast('已下载') }
          // #endif
          // #ifndef H5
          uni.openDocument({ filePath: res.tempFilePath, showMenu: true, fail: () => toast('已下载，暂无法预览此类型') })
          // #endif
        },
        fail: () => { uni.hideLoading(); toast('下载失败，请检查网络') }
      })
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
    // 定位到本页真实功能区（不再 toast「去 PC 端」）
    scrollTo(anchor) {
      uni.pageScrollTo({ selector: '#gd-' + anchor, duration: 260, fail: () => {} })
    },
    goPrimary() {
      const a = (this.g && this.g.primaryAction && this.g.primaryAction.anchor) || 'nodes'
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
