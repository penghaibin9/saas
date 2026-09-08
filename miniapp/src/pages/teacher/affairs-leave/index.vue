<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="请假与返校" show-back />
    <view class="al__tabs"><button class="al__tab" :class="{ 'is-on': tab === 'pending' }" @click="switchTab('pending')">待审批</button><button class="al__tab" :class="{ 'is-on': tab === 'followup' }" @click="switchTab('followup')">续假与返校</button></view>
    <view class="al__search"><input v-model="keyword" placeholder="搜索学生姓名或学号" confirm-type="search" @confirm="search" /><button @click="search">搜索</button></view>
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <view class="al__queue-bar"><text class="al__queue-note">共 {{ total }} 条 · 第 {{ page }} 页</text><button v-if="tab === 'pending' && visibleItems.length" class="al__queue-toggle" @click="startSequential">连续办理</button></view>
        <MobileGlobalState v-if="!visibleItems.length" state="empty" title="暂无符合条件的申请" description="可以调整关键词，或稍后刷新。" />
        <view v-for="x in visibleItems" :key="x.id" class="card al">
          <view class="row-between"><view class="flex-1"><text class="t-md t-bold">{{ x.studentName || '学生' }}</text><text class="al__sub">{{ x.className }} · {{ x.studentNo }}</text></view><MobileStatusTag :label="x.statusLabel" :type="x.tone" /></view>
          <view class="al__row"><text class="al__row-k">假期</text><text class="flex-1 t-sm">{{ x.startDate }} 至 {{ x.endDate }} · {{ x.days }} 天</text></view>
          <text class="al__reason">{{ x.leaveTypeLabel }} · {{ x.reason || '查看申请信息' }}</text>
          <button class="btn btn-ghost" :disabled="acting" @click="openDetail(x.id)">查看详情并办理</button>
        </view>
        <view v-if="total > pageSize" class="al__pagination"><button class="btn btn-ghost" :disabled="page === 1" @click="changePage(-1)">上一页</button><text>{{ page }} / {{ Math.ceil(total / pageSize) }}</text><button class="btn btn-ghost" :disabled="page * pageSize >= total" @click="changePage(1)">下一页</button></view>
      </view>
    </MobileGlobalState>
    <MobileLeaveDetail v-if="detailVisible" :detail="detail" :loading="detailLoading" :error="detailError" teacher @close="closeDetail" @retry="openDetail(detailId)">
      <template #materials><view v-if="detail && detail.canManageMaterials" class="card al__materials"><text class="t-md t-bold">证明与补交材料</text><text class="al__sub">在材料中心核对学生提交的证明，或发起补交要求。</text><button class="btn btn-ghost" @click="openMaterials">打开材料中心</button></view></template>
      <template #default="{ item: x }">
        <view class="al__actions" v-if="can(x, 'APPROVE')"><button class="al__reject flex-1" :disabled="acting" @click="doReturn(x)">退回修改</button><button class="al__reject flex-1" :disabled="acting" @click="doReject(x)">驳回</button><button class="al__approve flex-1" :disabled="acting" @click="doApprove(x)">通过</button></view>
        <view class="al__actions" v-else-if="can(x, 'CONFIRM_CANCEL')"><button class="al__reject flex-1" :disabled="acting" @click="doCancelReturn(x)">退回补充</button><button class="al__approve flex-1" :disabled="acting" @click="doCancelConfirm(x)">确认已返校</button></view>
        <view class="al__actions" v-else-if="can(x, 'APPROVE_EXTENSION')"><button class="al__reject flex-1" :disabled="acting" @click="doExtension(x, 'REJECT')">驳回续假</button><button class="al__approve flex-1" :disabled="acting" @click="doExtension(x, 'APPROVE')">通过续假</button></view>
        <view class="al__actions" v-else-if="can(x, 'HANDLE_OVERDUE')"><button class="al__approve flex-1" :disabled="acting" @click="doOverdue(x)">登记跟进</button></view>
        <view class="al__actions" v-else-if="can(x, 'PROXY_CANCEL')"><button class="btn btn-primary flex-1" :disabled="acting" @click="doProxyCancel(x)">代登记返校</button></view>
        <text v-else class="al__sub">当前记录可查看，暂无需要你办理的操作。</text>
      </template>
    </MobileLeaveDetail>
    <view v-if="proxyVisible" class="al__proxy-mask"><view class="card al__proxy"><text class="t-md t-bold">代登记返校</text><text class="al__sub">请填写已核实的实际返校时间。</text><picker mode="date" :value="proxyDate" :end="todayDate" @change="proxyDate = $event.detail.value"><view class="al__picker">{{ proxyDate || '选择返校日期' }}</view></picker><picker mode="time" :value="proxyTime" @change="proxyTime = $event.detail.value"><view class="al__picker">{{ proxyTime || '选择返校时间' }}</view></picker><view class="al__actions"><button class="btn btn-ghost flex-1" :disabled="acting" @click="proxyVisible = false">取消</button><button class="btn btn-primary flex-1" :disabled="acting || !proxyDate || !proxyTime" @click="submitProxy">确认登记</button></view></view></view>
  </view>
</template>
<script>
import MobileLeaveDetail from '@/components/MobileLeaveDetail.vue'
import { leaveDate, leaveError } from '@/services/leavePresentation'
import { teacherApi } from '@/services/teacherApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const OVERDUE_TYPES = [
  { key: 'CONTACT', label: '联系学生' }, { key: 'TO_HOME_SCHOOL', label: '转家校联系' },
  { key: 'CLOSE', label: '处置完毕关闭' }
]

export default {
  components: { MobileLeaveDetail },
  data() {
    return {
      keyword: '', page: 1, pageSize: 20, total: 0, detail: null, detailId: '', detailVisible: false, detailLoading: false, detailError: '', detailEpoch: 0, loadEpoch: 0, proxyVisible: false, proxyDate: '', proxyTime: '',
      tab: 'pending', pending: null, followup: null, state: 'loading', acting: false,
      sequentialMode: false, sequentialIndex: 0, sequentialConflict: false
    }
  },
  computed: {
    todayDate() { return leaveDate(new Date().toISOString()) },
    visibleItems() { return (this.tab === 'pending' ? this.pending : this.followup) || [] },
    sequentialItems() {
      return (this.pending || []).filter((x) => ['APPROVE', 'REJECT', 'RETURN'].some((action) => this.can(x, action)))
    },
    sequentialCurrent() { return this.sequentialItems[this.sequentialIndex] || null }
  },
  onLoad(query) { this.load().catch(() => {}); if (query && query.recordId) this.openDetail(String(query.recordId)) },
  onShow() { if (this.state === 'ready' && !this.acting) { this.load().catch(() => {}); if (this.detailVisible) this.openDetail(this.detailId) } },
  onUnload() { this.loadEpoch++; this.detailEpoch++ },
  onPullDownRefresh() { if (this.state === 'loading') { uni.stopPullDownRefresh(); return }; this.load(() => uni.stopPullDownRefresh()).catch(() => {}) },
  methods: {
    fmt(v) { return leaveDate(v, true) },
    hasVersion(x) { return x && x.version !== undefined && x.version !== null && x.version !== '' },
    can(x, action) { return this.hasVersion(x) && Array.isArray(x && x.allowedActions) && x.allowedActions.includes(action) },
    followupTone(s) { return s === 'OVERDUE' ? 'danger' : s === 'WAIT_CANCEL_LEAVE' ? 'warning' : 'default' },
    switchTab(t) {
      if (this.tab === t) return
      this.stopSequential()
      this.tab = t
      this.page = 1; this.load().catch(() => {})
    },
    startSequential() {
      if (!this.sequentialItems.length) return
      this.sequentialMode = true
      this.sequentialIndex = 0
      this.sequentialConflict = false
      this.openDetail(this.sequentialItems[0].id)
    },
    stopSequential() {
      this.sequentialMode = false
      this.sequentialIndex = 0
      this.sequentialConflict = false
    },
    restartSequential() {
      this.sequentialConflict = false
      this.sequentialIndex = Math.max(0, Math.min(this.sequentialIndex, this.sequentialItems.length - 1))
    },
    openSequentialItem(x) { if (x) this.openDetail(x.id) },
    search() { this.page = 1; this.stopSequential(); this.load().catch(() => {}) },
    changePage(delta) { this.page += delta; this.stopSequential(); this.load().catch(() => {}) },
    closeDetail() { if (this.acting) return; this.detailVisible = false; this.detailEpoch++; this.stopSequential() },
    async openDetail(id) {
      const ticket = ++this.detailEpoch
      this.detailId = String(id); this.detailVisible = true; this.detailLoading = true; this.detailError = ''; this.detail = null
      try { const data = await teacherApi.getAffairsLeaveDetail(id); if (ticket === this.detailEpoch) this.detail = data }
      catch (e) { if (ticket === this.detailEpoch) this.detailError = leaveError(e, '暂时无法读取申请详情，请重试。') }
      finally { if (ticket === this.detailEpoch) this.detailLoading = false }
    },
    openMaterials() { uni.navigateTo({ url: '/pages/teacher/affairs/index?bizType=LEAVE&bizId=' + encodeURIComponent(this.detailId) }) },
    nextSequential() {
      if (this.sequentialConflict || this.acting) return
      if (this.sequentialIndex < this.sequentialItems.length - 1) this.sequentialIndex += 1
    },
    load(done) {
      this.state = 'loading'
      const currentId = this.sequentialCurrent && String(this.sequentialCurrent.id)
      const epoch = ++this.loadEpoch
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword.trim() }
      const fetchPage = this.tab === 'pending' ? teacherApi.getAffairsLeavePending : teacherApi.getAffairsLeaveFollowup
      const request = fetchPage(params).then((data) => {
        if (epoch !== this.loadEpoch) return
        this.total = Number(data.total || 0)
        if (!(data.list || []).length && this.page > 1 && this.total > 0) {
          this.page = Math.max(1, Math.ceil(this.total / this.pageSize))
          return this.load()
        }
        if (this.tab === 'pending') this.pending = data.list || []
        else this.followup = data.list || []
        if (this.sequentialMode && currentId) {
          const found = this.sequentialItems.findIndex((x) => String(x.id) === currentId)
          if (found >= 0) this.sequentialIndex = found
          else this.sequentialIndex = Math.max(0, Math.min(this.sequentialIndex, this.sequentialItems.length - 1))
          if (!this.sequentialItems.length) this.stopSequential()
        }
        this.state = 'ready'
        return { pending: this.pending, followup: this.followup }
      }).catch((e) => {
        if (epoch !== this.loadEpoch) return
        this.state = 'error'
        this._err(e, '加载')
        throw e
      }).finally(() => { if (typeof done === 'function') done() })
      return request
    },
    _err(e, label) {
      const n = normalizeError(e)
      toast(leaveError(e, label + '失败，请重试'))
      return n
    },
    afterSequentialSuccess(processedId, oldIndex) {
      if (!this.sequentialMode) return
      if (!this.sequentialItems.length) return this.stopSequential()
      const stillThere = this.sequentialItems.findIndex((x) => String(x.id) === String(processedId))
      if (stillThere >= 0) this.sequentialIndex = Math.min(stillThere + 1, this.sequentialItems.length - 1)
      else this.sequentialIndex = Math.max(0, Math.min(oldIndex, this.sequentialItems.length - 1))
    },
    async run(task, successText, label, retry, sequentialId = null) {
      if (this.acting) return
      const queueId = sequentialId || (this.sequentialMode && this.sequentialCurrent ? this.sequentialCurrent.id : null)
      const oldIndex = this.sequentialIndex
      this.acting = true
      try {
        await task()
      } catch (e) {
        const n = this._err(e, label)
        if (n.kind !== 'conflict') {
          if (retry) setTimeout(retry, 0)
          this.acting = false
          return
        }
        this.stopSequential()
        this.sequentialConflict = true
        await this.load().catch(() => {})
        await this.openDetail(this.detailId)
        this.acting = false
        return
      }
      toast(successText)
      // A committed command is never retried merely because its subsequent read failed.
      try {
        await this.load()
        this.afterSequentialSuccess(queueId, oldIndex)
        const nextId = this.sequentialMode && this.sequentialCurrent ? this.sequentialCurrent.id : this.detailId
        await this.openDetail(nextId)
      } catch (e) {
        this.stopSequential()
        this.detail = null
        this.detailError = '操作已成功，但列表刷新失败。请刷新查看最新结果。'
        toast(this.detailError)
      } finally { this.acting = false }
    },
    promptText({ title, placeholder, initial = '', required = false, max = 300, submit }) {
      uni.showModal({ title, editable: true, placeholderText: placeholder, content: initial, success: (r) => {
        if (!r.confirm) return
        const value = (r.content || '').trim()
        if ((required && value.length < 5) || value.length > max) {
          toast(value.length > max ? `处理意见不能超过${max}字` : '处理意见至少5个字')
          setTimeout(() => this.promptText({ title, placeholder, initial: value, required, max, submit }), 0)
          return
        }
        // Finish closing the editable modal before opening its confirmation on H5 / WeChat.
        setTimeout(() => submit(value), 0)
      } })
    },
    parseReturnAt(value) {
      const raw = String(value || '').trim().replace('T', ' ')
      const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})$/)
      if (!m) return { error: '请选择有效的返校日期和时间' }
      const [year, month, day, hour, minute] = m.slice(1).map(Number)
      const dt = new Date(year, month - 1, day, hour, minute, 0, 0)
      if (dt.getFullYear() !== year || dt.getMonth() !== month - 1 || dt.getDate() !== day || dt.getHours() !== hour || dt.getMinutes() !== minute) return { error: '实际返校时间不是有效日期时间' }
      if (dt.getTime() > Date.now() + 60 * 1000) return { error: '实际返校时间不能晚于当前时间' }
      return { value: `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}` }
    },
    doApprove(x, initial = '') {
      this.promptText({ title: '通过请假', placeholder: '可填写审批意见（可选）', initial, submit: (opinion) => {
        uni.showModal({ title: '确认通过请假', content: `${x.studentName || '该学生'}\n${this.fmt(x.startTime)} 至 ${this.fmt(x.endTime)}\n\n确认请假时间、事由和审批节点无误。`, confirmText: '确认通过', success: (r) => { if (r.confirm) this.run(() => affairsContractApi.approveLeave(x.id, opinion, x.version), '已通过', '审批', () => this.doApprove(x, opinion), x.id) } })
      } })
    },
    doReject(x, initial = '') { this.promptText({ title: '驳回请假', placeholder: '请填写驳回原因（≥5字）', initial, required: true, submit: (reason) => this.run(() => affairsContractApi.rejectLeave(x.id, reason, x.version), '已驳回', '驳回', () => this.doReject(x, reason), x.id) }) },
    doReturn(x, initial = '') { this.promptText({ title: '退回申请人修改', placeholder: '请明确填写需要修改的内容（≥5字）', initial, required: true, submit: (reason) => this.run(() => affairsContractApi.returnLeave(x.id, reason, x.version), '已退回申请人修改', '退回', () => this.doReturn(x, reason), x.id) }) },
    doCancelConfirm(x, initial = '') {
      this.promptText({ title: '确认销假', placeholder: '可填写备注（可选）', initial, submit: (note) => {
        uni.showModal({ title: '确认学生已返校', content: `${x.studentName || '该学生'}的销假将被确认并办结，请确认返校事实已核实。`, confirmText: '确认销假', success: (r) => { if (r.confirm) this.run(() => affairsContractApi.confirmCancelLeave(x.id, 'CONFIRM', { note }, x.version), '已确认销假', '销假确认', () => this.doCancelConfirm(x, note)) } })
      } })
    },
    doCancelReturn(x, initial = '') { this.promptText({ title: '销假退回', placeholder: '请填写退回原因（≥5字）', initial, required: true, submit: (reason) => this.run(() => affairsContractApi.confirmCancelLeave(x.id, 'RETURN', { reason }, x.version), '销假申请已退回', '销假退回', () => this.doCancelReturn(x, reason)) }) },
    doProxyCancel(x) {
      this.detail = x; this.proxyDate = this.todayDate
      const now = new Date(); this.proxyTime = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0')
      this.proxyVisible = true
    },
    submitProxy() {
      const parsed = this.parseReturnAt(this.proxyDate + ' ' + this.proxyTime)
      if (parsed.error) return toast(parsed.error)
      const x = this.detail
      this.run(async () => { await affairsContractApi.proxyCancelLeave(x.id, parsed.value, '辅导员核实后代登记销假', x.version); this.proxyVisible = false }, '已登记返校，待核实确认', '代登记返校')
    },
    doExtension(x, action, initial = '') {
      const reject = action === 'REJECT'
      if (!reject) {
        uni.showModal({ title: '续假通过', content: `${x.studentName || '该学生'}\n请确认续假日期与理由已核对。`, confirmText: '确认通过', success: (r) => { if (r.confirm) this.run(() => affairsContractApi.reviewLeaveExtension(x.id, action, '', x.version), '已通过', '续假审批') } })
        return
      }
      this.promptText({ title: '续假驳回', placeholder: '请填写驳回原因（≥5字）', initial, required: true, submit: (reason) => this.run(() => affairsContractApi.reviewLeaveExtension(x.id, action, reason, x.version), '已驳回', '续假审批', () => this.doExtension(x, action, reason)) })
    },
    doOverdue(x, selectedIndex = null, initial = '') {
      const prompt = (type) => this.promptText({ title: type.label, placeholder: '请填写处置说明（≥5字）', initial, required: true, submit: (note) => this.run(() => affairsContractApi.handleLeaveOverdue(x.id, type.key, note, x.version), '已登记', '逾期处置', () => this.doOverdue(x, OVERDUE_TYPES.indexOf(type), note)) })
      if (selectedIndex !== null && OVERDUE_TYPES[selectedIndex]) return prompt(OVERDUE_TYPES[selectedIndex])
      uni.showActionSheet({ itemList: OVERDUE_TYPES.map((t) => t.label), success: (res) => prompt(OVERDUE_TYPES[res.tapIndex]) })
    }
  }
}
</script>

<style scoped>
.al__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }.al__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }.al__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }.al__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }.al__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }.al { display: flex; flex-direction: column; gap: var(--space-2); }.al__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }.al__row { display: flex; gap: var(--space-3); }.al__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 40px; flex-shrink: 0; }.al__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }.al__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }.al__reject::after { border: none; }.al__approve { min-height:var(--touch-target-min); border-radius:var(--radius-md); font-size:var(--font-size-md); border:0; background:var(--teacher-600); color:#fff; }.al__approve::after { border:none; }.al__queue-bar{display:flex;align-items:center;justify-content:space-between;gap:var(--space-2);margin-bottom:var(--space-3)}.al__queue-note{font-size:var(--font-size-sm);color:var(--text-secondary)}.al__queue-toggle{flex-shrink:0;font-size:var(--font-size-sm);color:var(--teacher-700)}.al__queue-item{padding:0}
.al__search{display:flex;margin:14px 16px;gap:8px;background:var(--bg-card);border:1px solid var(--border-color,#e3e8eb);border-radius:10px;padding:4px 10px}.al__search input{flex:1;min-width:0;font-size:14px;height:40px}.al__search button{margin:0;background:transparent;font-size:13px;color:var(--teacher-600);padding:0 10px}.al__search button::after,.al__tab::after,.al__queue-toggle::after{border:0}.al__tab{margin:0;background:transparent;line-height:42px;padding:0 8px;font-size:15px}.al__reason{font-size:12px;color:var(--text-secondary);line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.al__pagination{display:flex;align-items:center;justify-content:space-between;margin:20px 0;font-size:13px}.al__pagination button{margin:0}.al__materials{margin-top:12px}.al__materials button{margin-top:12px}.al__proxy-mask{position:fixed;inset:0;z-index:100;background:#14233066;display:flex;align-items:center;padding:22px}.al__proxy{width:100%;padding:20px}.al__picker{padding:14px;background:var(--bg-page,#f4f6f8);border-radius:8px;margin:12px 0;font-size:15px}.al__queue-toggle{margin:0;border:0;background:transparent;padding:4px 10px;line-height:28px}
</style>
