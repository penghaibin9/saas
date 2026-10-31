<template>
  <view class="internship-surface mobile-page mobile-student page-wrap">
    <MobileNavBar title="轮岗与工资" show-back :fallback-url="'/pages/student-internship/index' + (context.batchId ? '?batchId=' + encodeURIComponent(context.batchId) : '')" />
    <MobileGlobalState :state="state" :description="error || undefined" @retry="load" @back="returnHome">
      <view v-if="context.batchId" class="page-pad stack">
        <view class="section-head"><text class="section-head__title">轮岗安排</text><text class="section-head__more">{{ rotations.length }} 个部门</text></view>
        <view v-if="!rotations.length" class="card pf__empty"><text>暂无轮岗安排</text><text class="pf__sub">导师安排后可查看部门、项目及评价。</text></view>
        <view v-for="item in rotations" :key="item.id" class="card pf">
          <view class="row-between">
            <view class="flex-1">
              <text class="t-md t-bold">第{{ item.rotationSeq }}轮 · {{ item.departmentName }}</text>
              <text class="pf__sub">{{ item.startDate }} ～ {{ item.endDate }} · 带教 {{ item.mentorName }}</text>
            </view>
            <MobileStatusTag :label="rotationLabel(item.status)" :type="item.status === 'COMPLETED' ? 'success' : item.status === 'ACTIVE' ? 'info' : 'default'" />
          </view>

          <view class="pf__projects">
            <view v-for="project in item.projects" :key="project.id" class="pf__project">
              <text class="pf__project-name">{{ project.projectName }}</text>
              <text class="pf__sub">{{ project.projectContent || '暂无项目说明' }}</text>
              <text v-if="project.startDate || project.endDate" class="pf__sub">{{ project.startDate || '—' }} ～ {{ project.endDate || '—' }}</text>
            </view>
            <text v-if="!item.projects.length" class="pf__sub">当前部门还未登记项目。</text>
          </view>

          <view class="pf__score">
            <view><text>{{ scoreText(item.scores?.theory) }}</text><text>理论</text></view>
            <view><text>{{ scoreText(item.scores?.skill) }}</text><text>技能</text></view>
            <view><text>{{ scoreText(item.scores?.mentor) }}</text><text>带教评价</text></view>
            <view class="is-total"><text>{{ scoreText(item.scores?.total) }}</text><text>轮岗总分</text></view>
          </view>

          <view v-if="item.studentSelfEvaluation" class="pf__self-read">
            <text class="pf__label">我的自评 · {{ item.studentSelfRating }}/5</text>
            <text>{{ item.studentSelfEvaluation }}</text>
          </view>
          <view v-else-if="item.status !== 'CANCELLED'" class="pf__self">
            <text class="pf__label">提交本部门自评</text>
            <textarea v-model="selfDrafts[item.id].text" maxlength="2000" class="mobile-textarea pf__textarea" placeholder="写清做了哪些项目、掌握了什么、还需要改进什么（至少20字）" />
            <picker class="mobile-picker" :range="[1,2,3,4,5]" :value="Math.max(0, Number(selfDrafts[item.id].rating || 3)-1)" @change="selfDrafts[item.id].rating = Number($event.detail.value)+1">
              <view class="pf__picker">自评分：{{ selfDrafts[item.id].rating }}/5 ▾</view>
            </picker>
            <button class="mobile-control btn btn-primary" :disabled="busyRotationId === item.id" @click="submitSelf(item)">
              {{ busyRotationId === item.id ? '提交中…' : '提交自评' }}
            </button>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">月度工资单</text><button class="mobile-control pf__add" @click="openPayroll()">新增本月工资单</button></view>
        <view v-if="!payrolls.length" class="card pf__empty"><text>暂无工资单</text><text class="pf__sub">收到工资后，可新增当月记录并上传凭证。</text></view>
        <view v-for="item in payrolls" :key="item.id" class="card pf">
          <view class="row-between">
            <view>
              <text class="t-md t-bold">{{ item.payMonth }}</text>
              <text class="pf__sub">约定报酬：{{ money(item.agreedSalary, item.agreedSalaryCurrency) }}</text>
            </view>
            <MobileStatusTag :label="item.current?.statusLabel || '无当前版本'" :type="payrollTone(item.current?.status)" />
          </view>
          <view v-if="item.current" class="pf__pay-current">
            <view><text>实际发放</text><text>{{ money(item.current.actualAmount, item.current.currency) }}</text></view>
            <view><text>发薪日期</text><text>{{ item.current.paidOn || '未填写' }}</text></view>
            <view><text>当前版本</text><text>第{{ item.current.revisionNo }}版</text></view>
          </view>
          <button v-if="item.current?.evidenceFileId" class="mobile-control pf__file" @click="previewPayroll(item.current)">查看工资凭证</button>
          <text v-if="item.current?.reviewComment && (item.current.status !== 'APPROVED' || !item.history?.length || historyOpen[item.id])" class="pf__review">审核意见：{{ item.current.reviewComment }}</text>
          <button v-if="item.current && item.current.status !== 'SUBMITTED'" class="mobile-control btn btn-ghost" @click="openPayroll(item)">更正工资单</button>
          <view v-if="item.history?.length" class="pf__history">
            <button class="mobile-control btn btn-ghost" :aria-expanded="!!historyOpen[item.id]" @click="historyOpen = { ...historyOpen, [item.id]: !historyOpen[item.id] }">{{ historyOpen[item.id] ? '收起历史版本' : '查看历史版本' }}（{{ item.history.length }}）</button><view v-if="historyOpen[item.id]">
            <view v-for="version in item.history" :key="version.id" class="pf__history-row">
              <text>第{{ version.revisionNo }}版 · {{ version.statusLabel }}</text>
              <text>{{ money(version.actualAmount, version.currency) }}</text>
            </view>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <view v-if="state === 'error' && !context.internshipId" class="page-pad"><button class="mobile-control btn btn-ghost" @click="returnHome">返回实习首页</button></view>

    <view v-if="payrollForm.visible && state === 'ready'" class="pf__mask" @click.self="closePayroll">
      <view class="pf__dialog">
        <view class="row-between"><text class="t-lg t-bold">{{ payrollForm.statementId ? '更正工资单' : '新增工资单' }}</text><button class="mobile-control pf__close" @click="closePayroll">×</button></view>
        <picker class="mobile-picker" mode="date" fields="month" :value="payrollForm.payMonth + '-01'" :disabled="!!payrollForm.statementId" @change="payrollForm.payMonth = String($event.detail.value).slice(0,7)">
          <view class="pf__picker">工资月份：{{ payrollForm.payMonth || '请选择' }} ▾</view>
        </picker>
        <text class="pf__label">实际发放金额</text>
        <input v-model.trim="payrollForm.actualAmount" type="digit" class="mobile-input pf__input" placeholder="实际发放金额，例如 3200.00" />
        <text class="pf__label">币种</text><picker class="mobile-picker" :range="['人民币','美元','其他币种']" :value="payrollForm.currency === 'CNY' ? 0 : payrollForm.currency === 'USD' ? 1 : 2" :disabled="payrollSubmitting" @change="chooseCurrency"><view class="pf__picker">{{ payrollForm.currency === 'CNY' ? '人民币' : payrollForm.currency === 'USD' ? '美元' : '其他币种' }}</view></picker>
        <input v-if="!['CNY','USD'].includes(payrollForm.currency)" v-model.trim="payrollForm.currency" class="mobile-input pf__input" :disabled="payrollSubmitting" maxlength="3" placeholder="其他币种代码，例如 EUR（欧元）" />
        <picker class="mobile-picker" mode="date" :value="payrollForm.paidOn" @change="payrollForm.paidOn = $event.detail.value">
          <view class="pf__picker">发薪日期：{{ payrollForm.paidOn || '未填写' }} ▾</view>
        </picker>
        <textarea v-if="payrollForm.statementId" v-model="payrollForm.correctionReason" class="mobile-textarea pf__textarea" maxlength="500" placeholder="更正原因（至少5字）" />
        <view class="row-between">
          <view class="flex-1"><text class="pf__label">工资凭证照片</text><text class="pf__sub">{{ payrollForm.evidenceName || '须上传工资单或到账凭证图片' }}</text></view>
          <button class="mobile-control btn btn-ghost" :disabled="payrollUploading" @click="pickPayrollPhoto">{{ payrollUploading ? '上传中…' : '选择照片' }}</button>
        </view>
        <text v-if="payrollForm.evidence" class="pf__sub">{{ payrollForm.evidence.statusText }}</text>
        <button v-if="payrollForm.evidence" class="mobile-control btn btn-ghost" :disabled="payrollUploading || payrollSubmitting" @click="refreshPayrollEvidence">刷新凭证安全检查</button>
        <view v-if="payrollForm.conflict" class="pf__review stack">
          <text>工资单已变化，本次填写内容和凭证已保留。请读取最新工资单，核对后再继续。</text>
          <button class="mobile-control btn btn-ghost" :disabled="payrollRefreshing" @click="refreshPayrollConflict">{{ payrollRefreshing ? '读取中…' : '读取最新工资单' }}</button>
          <template v-if="payrollForm.latest">
            <text>最新工资单：{{ payrollForm.latest.current?.revisionNo == null ? '版本待核对' : '第' + payrollForm.latest.current.revisionNo + '版' }} · {{ payrollForm.latest.current?.statusLabel || '状态待核对' }}</text>
            <text>最新实际发放：{{ money(payrollForm.latest.current?.actualAmount, payrollForm.latest.current?.currency) }}；发薪日期：{{ payrollForm.latest.current?.paidOn || '未填写' }}</text>
            <text v-if="payrollForm.latest.current?.status === 'SUBMITTED'">最新版本正在审核，请等待处理结果。本次草稿已保留。</text>
            <button v-else class="mobile-control btn btn-ghost" :disabled="payrollRefreshing" @click="confirmPayrollLatest">已核对最新版本，保留本次填写继续更正</button>
          </template>
        </view>
        <button class="mobile-control btn btn-ghost" :disabled="payrollSubmitting || payrollUploading || payrollRefreshing" @click="discardPayroll">放弃本次填写</button>
        <button class="mobile-control btn btn-primary" :disabled="payrollSubmitting || payrollUploading || !payrollForm.evidence?.readyForBusiness || payrollForm.conflict" @click="submitPayroll">{{ payrollSubmitting ? '提交中…' : '提交审核' }}</button>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import {
  studentInternshipPayroll,
  studentInternshipPayrollSubmit,
  studentInternshipRotations,
  studentInternshipRotationSelfEvaluation
} from '@/services/internshipApi'
import { openBusinessFile, uploadBusinessFile, fileSdk } from '@/services/fileApi'
import { normalizeFileReadiness, refreshFileReadiness } from '@/services/fileReadiness.mjs'
import { go, toast } from '@/utils/nav'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'

const emptyPayroll = () => ({
  visible: false, statementId: '', payMonth: '', actualAmount: '', currency: 'CNY',
  paidOn: '', evidenceFileId: '', evidenceName: '', correctionReason: '', expectedVersion: null, evidence: null, conflict: false, latest: null
})

export default {
  data() {
    return { historyOpen:{},
      state: 'loading',
      error: '', requestedBatchId: '', requestedRecordId: '', loadSeq: 0, hidden: false,
      generation: currentSessionGeneration(), draftScope: '',
      context: { batchId: '', internshipId: '' },
      rotations: [], payrolls: [], selfDrafts: {}, busyRotationId: '',
      payrollForm: emptyPayroll(), payrollUploading: false, payrollSubmitting: false, payrollRefreshing: false
    }
  },
  onLoad(options = {}) { this.requestedBatchId = String(options.batchId || ''); this.requestedRecordId = String(options.internshipId || ''); this.load() },
  onHide() { this.historyOpen = {}; this.hidden = true; this.loadSeq += 1 },
  onUnload() { this.hidden = true; this.loadSeq += 1 },
  onShow() {
    const changed = this.generation !== currentSessionGeneration()
    const returning = this.hidden
    this.hidden = false
    if (returning) { this.payrollUploading=false;this.payrollSubmitting=false;this.payrollRefreshing=false;this.busyRotationId='' }
    if (changed) { this.generation = currentSessionGeneration(); this.context = { batchId: '', internshipId: '' }; this.draftScope = ''; this.selfDrafts = {}; this.payrollForm = emptyPayroll(); this.rotations = []; this.payrolls = []; this.busyRotationId = ''; this.payrollUploading = false; this.payrollSubmitting = false; this.payrollRefreshing = false }
    if (changed || returning || this.state === 'loading') this.load()
  },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    chooseCurrency(e){if(this.payrollSubmitting)return;const choice=Number(e.detail.value);if(choice===0)this.payrollForm.currency='CNY';else if(choice===1)this.payrollForm.currency='USD';else if(choice===2 && ['CNY','USD'].includes(this.payrollForm.currency))this.payrollForm.currency=''},
    returnHome() { go('/pages/student-internship/index' + (this.requestedBatchId ? '?batchId=' + encodeURIComponent(this.requestedBatchId) : '')) },
    canAct() { return !this.hidden && this.generation === currentSessionGeneration() && this.state === 'ready' && !!this.context.batchId && !!this.context.internshipId },
    rotationLabel(status) { return ({ PLANNED: '待开始', ACTIVE: '轮岗中', COMPLETED: '已完成', CANCELLED: '已取消' })[status] || '状态待核对' },
    scoreText(value) { return value == null ? '—' : Number(value).toFixed(1) },
    money(value, currency = 'CNY') { return value == null ? '未填写' : `${({CNY:'人民币',USD:'美元',JPY:'日元',EUR:'欧元',HKD:'港币'})[currency] || '币种待核对'} ${Number(value).toFixed(2)}` },
    payrollTone(status) { return status === 'APPROVED' ? 'success' : status === 'RETURNED' ? 'danger' : status === 'SUBMITTED' ? 'warning' : 'default' },
    ensureSelfDrafts() {
      const next = { ...this.selfDrafts }
      for (const row of this.rotations) if (!next[row.id]) next[row.id] = { text: '', rating: 3 }
      this.selfDrafts = next
    },
    async load(done) {
      const seq = ++this.loadSeq, generation = currentSessionGeneration(), batchId = this.requestedBatchId
      const current = () => !this.hidden && seq === this.loadSeq && generation === currentSessionGeneration() && batchId === this.requestedBatchId
      this.state = 'loading'
      this.error = ''
      try {
        const dashboard = await studentApi.getInternship(batchId)
        if (!current()) return
        if (!dashboard || typeof dashboard.hasBatch !== 'boolean') throw new Error('invalid dashboard')
        if (!dashboard.hasBatch || !dashboard.batchId || !dashboard.recordId) {
          this.context = { batchId: '', internshipId: '' }; this.rotations = []; this.payrolls = []
          this.state = dashboard.hasBatch ? 'error' : 'empty'
          this.error = dashboard.hasBatch ? '实习记录信息不完整，请返回实习首页重新选择。' : (dashboard.message || (dashboard.needSelect ? '请返回实习首页选择批次。' : '当前暂无实习安排，请返回实习首页查看。'))
          return
        }
        const context = { batchId: String(dashboard.batchId), internshipId: String(dashboard.recordId) }
        if ((batchId && context.batchId !== batchId) || (this.requestedRecordId && context.internshipId !== this.requestedRecordId)) throw new Error('context changed')
        const [rotations, payrolls] = await Promise.all([
          studentInternshipRotations(context.batchId, context.internshipId),
          studentInternshipPayroll(context.batchId, context.internshipId)
        ])
        if (!current()) return
        if (!Array.isArray(rotations) || !Array.isArray(payrolls)) throw new Error('invalid process facts')
        const scope = `${generation}:${context.batchId}:${context.internshipId}`
        if (this.draftScope && this.draftScope !== scope) { this.selfDrafts = {}; this.payrollForm = emptyPayroll() }
        this.draftScope = scope
        this.context = context
        this.rotations = rotations
        this.payrolls = payrolls
        this.ensureSelfDrafts()
        this.state = 'ready'
      } catch (e) {
        if (!current()) return
        const error = normalizeError(e); this.state = error.pageState || 'error'; this.error = error.text
      } finally { if (typeof done === 'function') done() }
    },
    async submitSelf(item) {
      if (!this.canAct() || this.busyRotationId) return
      const draft = this.selfDrafts[item.id] || {}
      if (String(draft.text || '').trim().length < 20) return toast('轮岗自评至少20个字')
      const generation = currentSessionGeneration(), scope = this.draftScope
      const current = () => !this.hidden && generation === currentSessionGeneration() && scope === this.draftScope
      this.busyRotationId = item.id
      try {
        await studentInternshipRotationSelfEvaluation(item.id, {
          ...this.context,
          selfEvaluation: String(draft.text || '').trim(),
          selfRating: Number(draft.rating || 3),
          expectedVersion: item.version
        })
        if (!current()) return
        toast('轮岗自评已提交')
        await this.load()
      } catch (e) { if (current()) toast(e?.message || '轮岗自评提交失败') }
      finally { if (generation === currentSessionGeneration() && scope === this.draftScope) this.busyRotationId = '' }
    },
    openPayroll(statement = null) {
      if (!this.canAct() || this.payrollSubmitting || this.payrollUploading || this.payrollRefreshing) return
      if (this.payrollForm.payMonth && String(this.payrollForm.statementId) === String(statement?.id || '')) { this.payrollForm.visible = true; return }
      const current = statement?.current
      const now = new Date()
      this.payrollForm = {
        ...emptyPayroll(),
        visible: true,
        statementId: statement?.id || '',
        expectedVersion: statement?.version ?? null,
        payMonth: statement?.payMonth || `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`,
        actualAmount: current?.actualAmount == null ? '' : String(current.actualAmount),
        currency: current?.currency || 'CNY',
        paidOn: current?.paidOn || '',
        correctionReason: ''
      }
    },
    closePayroll() { if (!this.payrollSubmitting && !this.payrollUploading && !this.payrollRefreshing) this.payrollForm.visible = false },
    discardPayroll() {
      if (!this.canAct() || this.payrollSubmitting || this.payrollUploading || this.payrollRefreshing) return
      const form = this.payrollForm, generation = currentSessionGeneration(), scope = this.draftScope
      uni.showModal({ title: '放弃本次工资填写', content: '本次填写的金额、说明和凭证选择将清除，原工资单不受影响。', success: result => {
        if (result.confirm && this.canAct() && !this.payrollSubmitting && !this.payrollUploading && !this.payrollRefreshing && generation === currentSessionGeneration() && scope === this.draftScope && form === this.payrollForm) this.payrollForm = emptyPayroll()
      } })
    },
    async refreshPayrollConflict() {
      const form = this.payrollForm
      if (!this.canAct() || !form.conflict || this.payrollRefreshing) return
      const seq = this.loadSeq, generation = currentSessionGeneration(), scope = this.draftScope
      const current = () => this.canAct() && seq === this.loadSeq && generation === currentSessionGeneration() && scope === this.draftScope && form === this.payrollForm
      this.payrollRefreshing = true; form.latest = null
      try {
        const rows = await studentInternshipPayroll(this.context.batchId, this.context.internshipId)
        if (!current()) return
        if (!Array.isArray(rows)) throw new Error('工资单读取未完整返回，请重试')
        const latest = rows.find(row => form.statementId ? String(row.id) === String(form.statementId) : row.payMonth === form.payMonth)
        if (!latest || !/^[1-9]\d*$/.test(String(latest.id)) || latest.payMonth !== form.payMonth || !Number.isInteger(latest.version) || latest.version < 0) throw new Error('原工资单当前无法核对，请返回列表确认。本次填写已保留')
        form.latest = latest; this.payrolls = rows
      } catch (e) { if (current()) toast(e?.message || '最新工资单读取失败，本次填写已保留') }
      finally { if (current()) this.payrollRefreshing = false }
    },
    confirmPayrollLatest() {
      const form = this.payrollForm
      if (!this.canAct() || this.payrollRefreshing || !form.conflict || !form.latest || form.latest.payMonth !== form.payMonth || (form.statementId && String(form.latest.id) !== String(form.statementId)) || form.latest.current?.status === 'SUBMITTED') return
      form.statementId = String(form.latest.id); form.expectedVersion = form.latest.version; form.conflict = false; form.latest = null
    },
    pickPayrollPhoto() {
      if (!this.canAct() || this.payrollUploading) return
      const form = this.payrollForm, generation = currentSessionGeneration(), scope = this.draftScope, seq=this.loadSeq
      const current = () => !this.hidden && seq===this.loadSeq && form === this.payrollForm && generation === currentSessionGeneration() && scope === this.draftScope
      this.payrollUploading = true
      uni.chooseImage({
        count: 1, sourceType: ['camera', 'album'], sizeType: ['original'],
        success: async (res) => {
          try {
            const path = (res.tempFilePaths || [])[0]
            const source = (res.tempFiles || [])[0] || {}
            if (!path || !current()) return
            const uploaded = await uploadBusinessFile({
              path, name: source.name || `payroll-${Date.now()}.jpg`, size: source.size || 0
            }, { bizType: 'TEMP_PRIVATE' })
            if (!current()) return
            this.payrollForm.evidenceFileId = uploaded.fileId
            this.payrollForm.evidenceName = uploaded.fileName || '工资凭证照片'
            this.payrollForm.evidence = normalizeFileReadiness(uploaded)
            if (!this.payrollForm.evidence.readyForBusiness) toast('凭证已上传，请等待扫描后刷新安全检查')
          } catch (e) { if (current()) toast(e?.message || '工资凭证上传失败') }
          finally { if (current()) this.payrollUploading = false }
        },
        fail: () => { if (current()) this.payrollUploading = false }
      })
    },
    async refreshPayrollEvidence() {
      if (!this.canAct() || this.payrollUploading || this.payrollSubmitting || !this.payrollForm.evidence) return
      const form=this.payrollForm,generation=currentSessionGeneration(),scope=this.draftScope,seq=this.loadSeq
      const current=()=>!this.hidden&&seq===this.loadSeq&&form===this.payrollForm&&generation===currentSessionGeneration()&&scope===this.draftScope
      this.payrollUploading=true
      form.evidence={...form.evidence,readyForBusiness:false,statusText:'正在读取安全检查结果'}
      try { const rows=await refreshFileReadiness([form.evidence],id=>fileSdk.metadata(id),current);if(rows)form.evidence=rows[0] }
      catch(e){if(current())toast(e?.message||'安全检查读取失败，填写内容和凭证已保留')}
      finally{if(current())this.payrollUploading=false}
    },
    async submitPayroll() {
      if (!this.canAct() || this.payrollSubmitting || this.payrollUploading || this.payrollForm.conflict) return
      const f = this.payrollForm
      const generation = currentSessionGeneration(), scope = this.draftScope
      const current = () => !this.hidden && f === this.payrollForm && generation === currentSessionGeneration() && scope === this.draftScope
      if (!/^20\d{2}-(0[1-9]|1[0-2])$/.test(f.payMonth)) return toast('请选择工资月份')
      if (!/^\d+(\.\d{1,2})?$/.test(String(f.actualAmount || ''))) return toast('请输入正确的实际发放金额')
      if (!/^[A-Za-z]{3}$/.test(f.currency)) return toast('请选择人民币、美元，或填写有效的三位币种代码')
      if (!f.evidenceFileId || f.evidence?.readyForBusiness !== true) return toast('请上传凭证并等待安全检查通过')
      if (f.statementId && String(f.correctionReason || '').trim().length < 5) return toast('更正原因至少5个字')
      this.payrollSubmitting = true
      try {
        await studentInternshipPayrollSubmit({
          ...this.context,
          expectedVersion: f.expectedVersion,
          payMonth: f.payMonth,
          actualAmount: f.actualAmount,
          currency: String(f.currency).toUpperCase(),
          paidOn: f.paidOn || '',
          evidenceFileId: f.evidenceFileId,
          correctionReason: String(f.correctionReason || '').trim(),
          submitNote: f.statementId ? '学生提交工资单更正版本' : '学生首次提交月度工资单'
        })
        if (!current()) return
        toast(f.statementId ? '工资单更正版本已提交' : '工资单已提交')
        this.payrollForm = emptyPayroll()
        await this.load()
      } catch (e) { if (current()) { if(e?.httpStatus===409 || e?.bizCode==='DATA_CONFLICT')f.conflict=true;toast(e?.message || '工资单提交失败') } }
      finally { if (generation === currentSessionGeneration() && scope === this.draftScope) this.payrollSubmitting = false }
    },
    async previewPayroll(version) {
      if (!version?.evidenceFileId) return
      try { await openBusinessFile(version.evidenceFileId) }
      catch (e) { toast(e?.message || '工资凭证无法打开') }
    }
  }
}
</script>

<style scoped>
.pf{display:flex;flex-direction:column;gap:12px;padding:14px}.pf__sub{display:block;margin-top:4px;font-size:var(--font-size-base);color:var(--text-tertiary);line-height:1.55}.pf__projects{display:flex;flex-direction:column;gap:7px}.pf__project{padding:9px;border-radius:8px;background:var(--gray-50)}.pf__project-name,.pf__label{display:block;font-size:var(--font-size-base);font-weight:600;color:var(--text-primary)}.pf__score{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;padding:9px;border-radius:8px;background:var(--gray-50)}.pf__score view{display:flex;flex-direction:column;align-items:center;gap:3px}.pf__score text:first-child{font-size:17px;font-weight:700}.pf__score text:last-child{font-size:var(--font-size-base);color:var(--text-tertiary)}.pf__score .is-total text:first-child{color:var(--brand-primary)}.pf__self-read,.pf__self{padding:10px;border-radius:8px;background:var(--primary-50)}.pf__self-read>text:last-child{display:block;margin-top:6px;font-size:var(--font-size-base);line-height:1.7;color:var(--text-secondary)}.pf__textarea,.pf__input,.pf__picker{box-sizing:border-box;width:100%;border:1px solid var(--border-base);border-radius:8px;padding:10px 12px;background:#fff;font-size:var(--font-size-base)}.pf__textarea{min-height:90px;margin:8px 0}.pf__picker{margin:8px 0}.pf__add{margin:0;padding:2px 4px;min-height:0;border:0;background:transparent;color:var(--brand-primary);font-size:var(--font-size-base)}.pf__add::after{border:none}.pf__pay-current{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;padding:10px;border-radius:8px;background:var(--gray-50)}.pf__pay-current view{display:flex;flex-direction:column;gap:4px}.pf__pay-current text:first-child{font-size:var(--font-size-base);color:var(--text-tertiary)}.pf__pay-current text:last-child{font-size:var(--font-size-base);font-weight:600}.pf__file{margin:0;padding:5px 0;min-height:0;border:0;background:transparent;color:var(--brand-primary);font-size:var(--font-size-base);text-align:left}.pf__file::after{border:none}.pf__review{display:block;padding:8px;border-radius:6px;background:var(--warning-50);color:var(--warning-700);font-size:var(--font-size-base)}.pf__history{font-size:var(--font-size-base);color:var(--text-secondary)}.pf__history-row{display:flex;justify-content:space-between;padding:7px 0;border-top:1px solid var(--border-light)}.pf__mask{position:fixed;inset:0;z-index:999;display:flex;align-items:flex-end;background:rgba(15,23,42,.48)}.pf__dialog{box-sizing:border-box;width:100%;max-height:88vh;overflow:auto;padding:18px;border-radius:18px 18px 0 0;background:#fff;display:flex;flex-direction:column;gap:10px}.pf__close{margin:0;padding:0 6px;min-height:0;border:0;background:transparent;font-size:24px;color:var(--text-tertiary)}.pf__close::after{border:none}
.pf__empty{padding:20px 16px;font-size:var(--font-size-base);color:var(--text-secondary)}.pf__input{height:44px;min-height:44px;padding:0 12px}.pf__picker{min-height:44px;display:flex;align-items:center}.pf__add,.pf__file,.pf__close{min-height:44px;min-width:44px}.pf__pay-current{grid-template-columns:repeat(2,minmax(0,1fr))}.pf__pay-current view{overflow-wrap:anywhere}.pf__dialog{padding-bottom:calc(18px + env(safe-area-inset-bottom))}.pf__review.stack{display:flex}</style>
