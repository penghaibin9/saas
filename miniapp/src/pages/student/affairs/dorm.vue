<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的宿舍" :subtitle="subtitle" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="cfg">
        <view class="dm__bed" v-if="cfg.hasBed">
          <text class="dm__bed-t">我的床位</text>
          <text class="dm__bed-v">{{ cfg.myBed.building }} · {{ cfg.myBed.room }}室 · {{ cfg.myBed.bedNo }}床</text>
        </view>
        <view class="dm__bed dm__bed--reserved" v-else-if="cfg.hasAllocation">
          <text class="dm__bed-t">{{ cfg.allocation && cfg.allocation.hiddenUntilCheckin ? '宿舍已安排' : '床位已确认' }}</text>
          <text v-if="cfg.allocation && !cfg.allocation.hiddenUntilCheckin" class="dm__bed-v">{{ cfg.allocation.building }} · {{ cfg.allocation.room }}室 · {{ cfg.allocation.bedNo }}床</text>
          <text v-else class="dm__bed-v">完成现场报到后可查看位置</text>
        </view>
        <view class="dm__empty" v-else><text>暂无住宿安排</text></view>

        <view class="dm__notice" v-if="notice"><text class="dm__notice-icon">ℹ️</text><text class="dm__notice-t">{{ notice }}</text></view>
        <view class="dm__presence">
          <view class="row-between"><text class="dm__step-t">归寝状态</text><MobileStatusTag :label="presenceLabel" :type="presenceTone" /></view>
          <text class="dm__history-reason">{{ cfg.presence?.summary || '暂无可靠归寝数据' }}</text>
          <text class="dm__history-route">最近可靠事件：{{ fmtTime(cfg.presence?.lastEventAt) }}</text>
          <text v-if="cfg.presence?.status === 'UNKNOWN'" class="dm__unknown">“未知”表示 Provider 未配置或无可靠数据，不等同于“未归”。</text>
        </view>
        <MobileInlineAlert v-if="pendingTransfer" type="warning" title="已有调宿申请处理中" :description="`当前状态：${statusLabel(pendingTransfer.status || pendingTransfer.currentNode)}。审批完成或驳回前不能重复提交。`" />
        <MobileInlineAlert v-if="transferError" type="warning" title="调宿记录暂不可用" :description="transferError" />
        <MobileInlineAlert v-if="optionError" type="warning" title="可选床位加载失败" :description="optionError" />

        <view class="dm__history">
          <text class="dm__step-t">检查整改</text>
          <view v-for="x in rectifications" :key="x.rectificationId" class="dm__rect">
            <view class="row-between"><text class="dm__history-status">{{ rectStatusLabel(x.status) }} · {{ severityLabel(x.severity) }}</text><text class="dm__deadline" :class="{ overdue: x.overdue }">{{ fmtTime(x.deadlineAt) }}</text></view>
            <text class="dm__history-route">{{ x.buildingName }} · {{ x.roomNo }}室</text>
            <text class="dm__history-reason">{{ x.requirement }}</text>
            <button v-if="x.allowedActions && x.allowedActions.includes('START')" class="dm__secondary" :disabled="submitting" @click="startRect(x)">开始整改</button>
            <view v-if="x.allowedActions && x.allowedActions.includes('SUBMIT')" class="dm__rect-form">
              <textarea v-model="rectNotes[x.rectificationId]" class="dm__textarea" maxlength="1000" placeholder="整改说明（5-1000字）" />
              <button class="dm__secondary" :disabled="submitting" @click="uploadRectPhoto(x)">{{ rectFiles[x.rectificationId] ? '重新上传照片' : '上传整改照片' }}</button>
              <text v-if="rectFiles[x.rectificationId]" class="dm__uploaded">已上传：{{ rectFiles[x.rectificationId].fileName }}</text>
              <button class="dm__btn" :disabled="submitting || (rectNotes[x.rectificationId] || '').trim().length < 5 || !rectFiles[x.rectificationId]" @click="submitRect(x)">提交复检</button>
            </view>
            <text v-if="x.status === 'WAITING_RECHECK'" class="dm__uploaded">整改证据已提交，等待宿管复检。</text>
          </view>
          <text v-if="!rectifications.length" class="dm__empty-text">暂无整改任务</text>
        </view>

        <view v-if="canChoose" class="dm__select">
          <view class="dm__step-t">{{ cfg.hasBed ? '申请调宿：选择目标床位' : '首次选床：选择床位' }}</view>

          <text class="dm__label">① 选楼栋</text>
          <view class="dm__chips">
            <view v-for="b in buildings" :key="b.buildingId" class="dm__chip" :class="{ 'is-on': sel.building === b.buildingId }" @click="pickBuilding(b)">{{ b.buildingName }}（空 {{ b.vacantBeds }}）</view>
          </view>
          <text v-if="optionsLoading" class="dm__loading">正在加载可选房源…</text>

          <template v-if="sel.building">
            <text class="dm__label">② 选房间</text>
            <view class="dm__chips">
              <view v-for="r in rooms" :key="r.roomId" class="dm__chip" :class="{ 'is-on': sel.room === r.roomId, 'is-full': r.vacantBeds === 0 }" @click="r.vacantBeds > 0 && pickRoom(r)">{{ r.floorNo }}层 {{ r.roomNo }}（空 {{ r.vacantBeds }}）</view>
            </view>
          </template>

          <template v-if="sel.room">
            <text class="dm__label">③ 选床位</text>
            <view class="dm__chips">
              <view v-for="bd in beds" :key="bd.bedId" class="dm__chip" :class="{ 'is-on': sel.bed === bd.bedId, 'is-full': bd.status !== 'VACANT' || bd.isCurrent }" @click="bd.status === 'VACANT' && !bd.isCurrent && (sel.bed = bd.bedId)">{{ bd.bedNo }}{{ bd.isCurrent ? '（当前）' : (bd.status === 'VACANT' ? '' : '（已住）') }}</view>
            </view>
          </template>

          <view v-if="sel.bed" class="dm__target"><text class="dm__target-k">已选目标</text><text class="dm__target-v">{{ selectedBedLabel }}</text></view>

          <view class="dm__field" v-if="cfg.hasBed && sel.bed">
            <text class="dm__label">调宿原因 <text class="dm__req">*</text></text>
            <textarea v-model="transferReason" class="dm__textarea" maxlength="300" placeholder="说明调宿原因（5-300字）" />
            <text class="dm__counter">{{ transferReason.trim().length }}/300</text>
          </view>

          <view class="dm__confirm" v-if="sel.bed">
            <button class="dm__btn" :disabled="submitting || (cfg.hasBed && transferReason.trim().length < 5)" @click="confirm">{{ submitting ? '提交中…' : (cfg.hasBed ? '核对并提交调宿' : '核对并确认床位') }}</button>
          </view>
        </view>

        <view v-if="transfers.length" class="dm__history">
          <text class="dm__step-t">我的调宿申请</text>
          <view v-for="x in transfers" :key="x.transferId" class="dm__history-row">
            <view class="flex-1"><text class="dm__history-status">{{ statusLabel(x.status || x.currentNode) }}</text><text class="dm__history-route">{{ x.fromBedLabel || ('原床 #' + (x.fromBedId || '—')) }} → {{ x.toBedLabel || ('目标床 #' + (x.toBedId || '—')) }}</text><text class="dm__history-reason">{{ x.reason || '未填写原因' }}</text></view>
          </view>
        </view>
        <view v-else-if="!transferError" class="dm__history"><text class="dm__step-t">我的调宿申请</text><text class="dm__empty-text">暂无调宿申请</text></view>
        <view class="dm__history">
          <text class="dm__step-t">住宿历史</text>
          <view v-for="x in stays" :key="x.stayId" class="dm__history-row"><text class="dm__history-status">{{ stayStatusLabel(x.status) }}</text><text class="dm__history-route">{{ x.bedLabel || ('床位 #' + x.bedId) }}</text><text class="dm__history-reason">{{ (x.checkinAt || '未记录') + ' → ' + (x.checkoutAt || '当前') }}</text></view>
          <text v-if="!stays.length" class="dm__empty-text">暂无住宿历史</text>
        </view>
      </view>
    </MobileGlobalState>
    <view v-if="confirmDlg.visible" class="dm__mask" @click.self="confirmDlg.visible = false">
      <view class="dm__dialog">
        <text class="dm__dialog-title">{{ cfg.hasBed ? '确认提交调宿' : '确认床位' }}</text>
        <text class="dm__dialog-line" v-if="cfg.hasBed">当前：{{ confirmDlg.current }}</text>
        <text class="dm__dialog-line">目标：{{ selectedBedLabel }}</text>
        <text class="dm__dialog-note">{{ cfg.hasBed ? '审批完成前原床不变。' : '确认后床位将为你预留，变更须走正式调宿。' }}</text>
        <view class="dm__dialog-actions"><button class="dm__dialog-cancel" @click="confirmDlg.visible = false">取消</button><button class="dm__dialog-ok" @click="confirmSubmit">{{ cfg.hasBed ? '提交申请' : '确认床位' }}</button></view>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { safeToast, createSubmitLock, normalizeError } from '@/services/request'
import fileSdk from '@/services/fileSdk'
import { createClientRequestId } from '@/utils/clientRequestId'

const PENDING = ['SUBMITTED', 'COUNSELOR_REVIEW', 'DORM_MANAGER_REVIEW', 'DORM_REVIEW', 'PENDING']

export default {
  data() {
    return {
      cfg: null, state: 'loading', buildings: [], rooms: [], beds: [], transfers: [], stays: [], rectifications: [],
      transferError: '', optionError: '', optionsLoading: false,
      sel: { building: '', room: '', bed: '' }, submitting: false,
      transferReason: '', rectNotes: {}, rectFiles: {}, rectRequestIds: {}, confirmDlg: { visible: false, current: '', reason: '' }, _lock: createSubmitLock()
    }
  },
  computed: {
    subtitle() {
      if (!this.cfg) return ''
      if (this.cfg.hasBed) return this.pendingTransfer ? '调宿审批处理中' : '正式调宿须审批'
      if (this.cfg.hasAllocation) return '住宿分配已确认'
      return this.cfg.selfSelectEnabled ? '已开放首次选床' : '等待学校分配'
    },
    pendingTransfer() { return this.transfers.find((x) => PENDING.includes(x.status || x.currentNode)) || null },
    presenceLabel() { return this.cfg?.presence?.statusLabel || '未知' },
    presenceTone() { return ({ IN_DORM: 'success', ON_LEAVE: 'primary', LATE_RETURN: 'warning', NOT_RETURNED: 'danger' })[this.cfg?.presence?.status] || 'default' },
    canChoose() { return !!(this.cfg && (this.cfg.hasBed ? !this.pendingTransfer : this.cfg.canSelfSelect)) },
    notice() {
      if (!this.cfg) return ''
      if (this.cfg.hasBed) return this.pendingTransfer ? '请等待当前调宿申请处理完成，审批期间原床位保持不变。' : (this.cfg.studentNotice || '如需调整床位，请提交调宿申请，审批完成前原床不变。')
      return this.cfg.studentNotice
    },
    selectedBuilding() { return this.buildings.find((x) => String(x.buildingId) === String(this.sel.building)) || {} },
    selectedRoom() { return this.rooms.find((x) => String(x.roomId) === String(this.sel.room)) || {} },
    selectedBed() { return this.beds.find((x) => String(x.bedId) === String(this.sel.bed)) || {} },
    selectedBedLabel() {
      return [this.selectedBuilding.buildingName, this.selectedRoom.roomNo && `${this.selectedRoom.roomNo}室`, this.selectedBed.bedNo && `${this.selectedBed.bedNo}床`].filter(Boolean).join(' / ') || `床位 #${this.sel.bed}`
    }
  },
  onLoad() { this.load() },
  methods: {
    statusLabel(s) { return ({ SUBMITTED: '已提交', COUNSELOR_REVIEW: '辅导员审核', DORM_MANAGER_REVIEW: '宿管审核', DORM_REVIEW: '宿管审核', EXECUTED: '已执行', REJECTED: '已驳回', CANCELLED: '已取消' })[s] || s || '处理中' },
    stayStatusLabel(s) { return ({ RESERVED: '待入住', ACTIVE: '当前在住', ENDED: '已退宿', CANCELLED: '已取消' })[String(s || '').toUpperCase()] || '状态待确认' },
    rectStatusLabel(s) { return ({ OPEN: '待整改', RECTIFYING: '整改中', WAITING_RECHECK: '待复检', CLOSED: '已关闭', ESCALATED: '已升级' })[s] || s },
    severityLabel(s) { return ({ LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险', CRITICAL: '重大风险' })[s] || s },
    fmtTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '—' },
    showError(e, fallback) { const n = normalizeError(e); safeToast(n.text || (e && e.message) || fallback); if (n.kind === 'conflict') this.load(); return n },
    async load() {
      this.state = 'loading'; this.sel = { building: '', room: '', bed: '' }; this.rooms = []; this.beds = []; this.transferError = ''; this.optionError = ''
      const [dormResult, transferResult, stayResult, rectResult] = await Promise.allSettled([studentApi.getMyDorm(), affairsContractApi.getMyDormTransfers(), affairsContractApi.getMyDormStays(), affairsContractApi.getMyDormRectifications()])
      if (dormResult.status === 'rejected') { this.state = 'error'; this.showError(dormResult.reason, '宿舍信息加载失败'); return }
      this.cfg = dormResult.value
      if (transferResult.status === 'fulfilled') this.transfers = (transferResult.value && transferResult.value.items) || []
      else { this.transfers = []; this.transferError = normalizeError(transferResult.reason).text || '调宿记录加载失败，请稍后重试' }
      this.stays = stayResult.status === 'fulfilled' ? ((stayResult.value && stayResult.value.items) || []) : []
      this.rectifications = rectResult.status === 'fulfilled' ? ((rectResult.value && rectResult.value.items) || []) : []
      this.state = 'ready'
      if (this.cfg.hasBed && !this.pendingTransfer) this.loadTransferOptions()
      else if (!this.cfg.hasBed && (this.cfg.canSelfSelect || this.cfg.selfSelectEnabled)) this.loadSelfSelectOptions()
    },
    async loadSelfSelectOptions() {
      this.optionsLoading = true; this.optionError = ''
      try { const d = await studentApi.getDormOptions(); this.buildings = d.buildings || [] }
      catch (e) { this.buildings = []; this.optionError = normalizeError(e).text || '可选楼栋加载失败' }
      finally { this.optionsLoading = false }
    },
    async loadTransferOptions() {
      this.optionsLoading = true; this.optionError = ''
      try { const d = await affairsContractApi.getDormTransferOptions(); this.buildings = d.items || [] }
      catch (e) { this.buildings = []; this.optionError = normalizeError(e).text || '调宿可选楼栋加载失败' }
      finally { this.optionsLoading = false }
    },
    async pickBuilding(b) {
      if (this.optionsLoading) return
      this.sel = { building: b.buildingId, room: '', bed: '' }; this.rooms = []; this.beds = []; this.optionError = ''; this.optionsLoading = true
      try {
        const d = await (this.cfg.hasBed ? affairsContractApi.getDormTransferRooms(b.buildingId) : studentApi.getDormRooms(b.buildingId))
        this.rooms = d.items || []
      } catch (e) { this.optionError = normalizeError(e).text || '房间加载失败' }
      finally { this.optionsLoading = false }
    },
    async pickRoom(r) {
      if (this.optionsLoading) return
      this.sel.room = r.roomId; this.sel.bed = ''; this.beds = []; this.optionError = ''; this.optionsLoading = true
      try {
        const d = await (this.cfg.hasBed ? affairsContractApi.getDormTransferBeds(r.roomId) : studentApi.getDormBeds(r.roomId))
        this.beds = d.items || []
      } catch (e) { this.optionError = normalizeError(e).text || '床位加载失败' }
      finally { this.optionsLoading = false }
    },
    async startRect(x) {
      if (this.submitting) return
      this.submitting = true
      try { await affairsContractApi.startDormRectification(x.rectificationId, x.version); safeToast('已开始整改', 'success'); await this.load() }
      catch (e) { this.showError(e, '开始整改失败') }
      finally { this.submitting = false }
    },
    async uploadRectPhoto(x) {
      if (this.submitting) return
      try {
        const selected = await fileSdk.choose(); if (!selected) return
        this.submitting = true
        const uploaded = await fileSdk.upload(selected, { bizType: 'TEMP_PRIVATE' })
        this.rectFiles[x.rectificationId] = { fileId: String(uploaded.fileId || uploaded.id), fileName: uploaded.fileName || selected.name || '整改照片' }
        this.rectRequestIds[x.rectificationId] = createClientRequestId('dorm-rectify')
      } catch (e) { this.showError(e, '照片上传失败') }
      finally { this.submitting = false }
    },
    async submitRect(x) {
      const note = String(this.rectNotes[x.rectificationId] || '').trim(); const file = this.rectFiles[x.rectificationId]
      if (note.length < 5 || !file) return safeToast('请填写至少5字整改说明并上传照片')
      this.submitting = true
      try {
        if (!this.rectRequestIds[x.rectificationId]) this.rectRequestIds[x.rectificationId] = createClientRequestId('dorm-rectify')
        await affairsContractApi.submitDormRectification(x.rectificationId, { expectedVersion: x.version, note, fileIds: [file.fileId], clientRequestId: this.rectRequestIds[x.rectificationId] })
        delete this.rectRequestIds[x.rectificationId]
        safeToast('整改已提交复检', 'success'); await this.load()
      } catch (e) { this.showError(e, '整改提交失败') }
      finally { this.submitting = false }
    },
    confirm() {
      if (this.submitting || !this.sel.bed || this.pendingTransfer) return
      const reason = this.transferReason.trim()
      if (this.cfg.hasBed && (reason.length < 5 || reason.length > 300)) return safeToast('调宿原因需5-300字')
      const current = this.cfg.hasBed && this.cfg.myBed ? `${this.cfg.myBed.building} / ${this.cfg.myBed.room}室 / ${this.cfg.myBed.bedNo}床` : '尚未入住'
      this.confirmDlg = { visible: true, current, reason }
    },
    confirmSubmit() {
      if (this.submitting) return
      const reason = this.confirmDlg.reason
      this.confirmDlg.visible = false
      this.doSubmit(reason)
    },
    doSubmit(reason) {
      this.submitting = true
      this._lock.run(() => this.cfg.hasBed ? affairsContractApi.submitDormTransfer(this.sel.bed, reason) : studentApi.selfSelectBed(this.sel.bed))
        .then(() => { safeToast(this.cfg.hasBed ? '调宿申请已提交' : '选床成功', 'success'); this.transferReason = ''; this.load() })
        .catch((e) => { if (e && e.code === 'LOCKED') return; this.showError(e, '提交失败') })
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.dm__bed--reserved { background: #1d4ed8 !important; }
.dm__bed { background: var(--brand-primary); color: #fff; border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4); }.dm__bed-t { display: block; font-size: var(--font-size-sm); opacity: 0.85; }.dm__bed-v { display: block; font-size: 18px; font-weight: 700; margin-top: 4px; }.dm__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-4); }.dm__notice { display: flex; gap: var(--space-2); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); margin-bottom: var(--space-4); }.dm__notice-t { color: var(--text-secondary); font-size: var(--font-size-base); line-height: 1.6; }.dm__step-t { display: block; font-weight: 600; margin-bottom: var(--space-3); }.dm__label { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }.dm__chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }.dm__chip { padding: 8px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); border: 1px solid var(--border-base); color: var(--text-secondary); }.dm__chip.is-on { background: var(--brand-primary); color: #fff; border-color: var(--brand-primary); }.dm__chip.is-full { opacity: 0.4; }.dm__field { margin-top: var(--space-4); }.dm__textarea { width: 100%; min-height: 80px; box-sizing: border-box; border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px; background: #fff; }.dm__req { color: #dc2626; }.dm__confirm { margin-top: var(--space-5); }.dm__btn { background: var(--brand-primary); color: #fff; border-radius: var(--radius-full); padding: 12px; font-size: var(--font-size-base); }.dm__target { margin-top: 12px; padding: 10px; border-radius: 8px; background: #eff6ff; }.dm__target-k, .dm__target-v { display: block; }.dm__target-k { color: #64748b; font-size: 12px; }.dm__target-v { margin-top: 3px; color: #1d4ed8; font-weight: 600; }.dm__loading, .dm__counter, .dm__empty-text { display: block; margin-top: 6px; color: #94a3b8; font-size: 12px; }.dm__counter { text-align: right; }.dm__history { margin-top: var(--space-5); }.dm__history-row { padding: 10px 0; border-bottom: 1px solid var(--border-base); font-size: 13px; }.dm__history-status, .dm__history-route, .dm__history-reason { display: block; }.dm__history-status { font-weight: 600; color: #334155; }.dm__history-route { margin-top: 4px; color: #1d4ed8; }.dm__history-reason { margin-top: 3px; color: var(--text-tertiary); }
.dm__rect { padding:12px;margin-bottom:10px;border:1px solid var(--border-base);border-radius:10px;background:#fff }.row-between { display:flex;justify-content:space-between;gap:8px }.dm__deadline { color:#64748b;font-size:11px }.dm__deadline.overdue { color:#dc2626 }.dm__rect-form { display:grid;gap:8px;margin-top:10px }.dm__secondary { margin-top:9px;border:1px solid #bfdbfe;background:#eff6ff;color:#1d4ed8;border-radius:9px;font-size:13px }.dm__uploaded { display:block;margin-top:6px;color:#166534;font-size:12px }
.dm__presence { margin:12px 0;padding:12px;border:1px solid #dbeafe;border-radius:10px;background:#f8fafc }.dm__unknown { display:block;margin-top:7px;color:#475569;font-size:12px;line-height:1.55 }
.dm__mask { position:fixed;inset:0;z-index:2000;background:rgba(15,23,42,.45);display:flex;align-items:center;justify-content:center;padding:24px }.dm__dialog { width:100%;max-width:360px;box-sizing:border-box;padding:20px;border-radius:16px;background:#fff;box-shadow:0 20px 60px rgba(15,23,42,.25) }.dm__dialog-title,.dm__dialog-line,.dm__dialog-note { display:block }.dm__dialog-title { font-size:18px;font-weight:700;color:#0f172a;margin-bottom:14px }.dm__dialog-line { color:#334155;line-height:1.7 }.dm__dialog-note { margin-top:10px;color:#64748b;font-size:13px }.dm__dialog-actions { display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:18px }.dm__dialog-cancel,.dm__dialog-ok { border-radius:10px;font-size:14px }.dm__dialog-cancel { background:#f1f5f9;color:#334155 }.dm__dialog-ok { background:#2563eb;color:#fff }
</style>
