<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的宿舍" :subtitle="subtitle" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="cfg">
        <view class="dm__bed" v-if="cfg.hasBed">
          <text class="dm__bed-t">我的床位</text>
          <text class="dm__bed-v">{{ cfg.myBed.building }} · {{ cfg.myBed.room }}室 · {{ cfg.myBed.bedNo }}床</text>
        </view>
        <view class="dm__empty" v-else><text>你还没有床位</text></view>

        <view class="dm__notice" v-if="notice"><text class="dm__notice-icon">ℹ️</text><text class="dm__notice-t">{{ notice }}</text></view>
        <MobileInlineAlert v-if="pendingTransfer" type="warning" title="已有调宿申请处理中" :description="`当前状态：${statusLabel(pendingTransfer.status || pendingTransfer.currentNode)}。审批完成或驳回前不能重复提交。`" />
        <MobileInlineAlert v-if="transferError" type="warning" title="调宿记录暂不可用" :description="transferError" />
        <MobileInlineAlert v-if="optionError" type="warning" title="可选床位加载失败" :description="optionError" />

        <view v-if="canChoose" class="dm__select">
          <view class="dm__step-t">{{ cfg.hasBed ? '申请调宿：选择目标床位' : '首次入住：选择床位' }}</view>

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
            <button class="dm__btn" :disabled="submitting || (cfg.hasBed && transferReason.trim().length < 5)" @click="confirm">{{ submitting ? '提交中…' : (cfg.hasBed ? '核对并提交调宿' : '核对并确认入住') }}</button>
          </view>
        </view>

        <view v-if="transfers.length" class="dm__history">
          <text class="dm__step-t">我的调宿申请</text>
          <view v-for="x in transfers" :key="x.transferId" class="dm__history-row">
            <view class="flex-1"><text class="dm__history-status">{{ statusLabel(x.status || x.currentNode) }}</text><text class="dm__history-route">{{ x.fromBedLabel || ('原床 #' + (x.fromBedId || '—')) }} → {{ x.toBedLabel || ('目标床 #' + (x.toBedId || '—')) }}</text><text class="dm__history-reason">{{ x.reason || '未填写原因' }}</text></view>
          </view>
        </view>
        <view v-else-if="!transferError" class="dm__history"><text class="dm__step-t">我的调宿申请</text><text class="dm__empty-text">暂无调宿申请</text></view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { safeToast, createSubmitLock, normalizeError } from '@/services/request'

const PENDING = ['SUBMITTED', 'COUNSELOR_REVIEW', 'DORM_MANAGER_REVIEW', 'DORM_REVIEW', 'PENDING']

export default {
  data() {
    return {
      cfg: null, state: 'loading', buildings: [], rooms: [], beds: [], transfers: [],
      transferError: '', optionError: '', optionsLoading: false,
      sel: { building: '', room: '', bed: '' }, submitting: false,
      transferReason: '', _lock: createSubmitLock()
    }
  },
  computed: {
    subtitle() {
      if (!this.cfg) return ''
      if (this.cfg.hasBed) return this.pendingTransfer ? '调宿审批处理中' : '正式调宿须审批'
      return this.cfg.selfSelectEnabled ? '已开放首次自选' : '辅导员分配'
    },
    pendingTransfer() { return this.transfers.find((x) => PENDING.includes(x.status || x.currentNode)) || null },
    canChoose() { return !!(this.cfg && (this.cfg.hasBed ? !this.pendingTransfer : this.cfg.canSelfSelect)) },
    notice() {
      if (!this.cfg) return ''
      if (this.cfg.hasBed) return this.pendingTransfer ? '请等待当前调宿申请处理完成，审批期间原床位保持不变。' : (this.cfg.studentNotice || '如需调整床位，请提交调宿申请，审批完成前原床不变。')
      return this.cfg.selfSelectEnabled ? '首次自选成功后立即入住；已有床位后不能直接换床。' : this.cfg.studentNotice
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
    showError(e, fallback) { const n = normalizeError(e); safeToast(n.text || (e && e.message) || fallback); if (n.kind === 'conflict') this.load(); return n },
    async load() {
      this.state = 'loading'; this.sel = { building: '', room: '', bed: '' }; this.rooms = []; this.beds = []; this.transferError = ''; this.optionError = ''
      const [dormResult, transferResult] = await Promise.allSettled([studentApi.getMyDorm(), affairsContractApi.getMyDormTransfers()])
      if (dormResult.status === 'rejected') { this.state = 'error'; this.showError(dormResult.reason, '宿舍信息加载失败'); return }
      this.cfg = dormResult.value
      if (transferResult.status === 'fulfilled') this.transfers = (transferResult.value && transferResult.value.items) || []
      else { this.transfers = []; this.transferError = normalizeError(transferResult.reason).text || '调宿记录加载失败，请稍后重试' }
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
    confirm() {
      if (this.submitting || !this.sel.bed || this.pendingTransfer) return
      const reason = this.transferReason.trim()
      if (this.cfg.hasBed && (reason.length < 5 || reason.length > 300)) return safeToast('调宿原因需5-300字')
      const current = this.cfg.hasBed && this.cfg.myBed ? `${this.cfg.myBed.building} / ${this.cfg.myBed.room}室 / ${this.cfg.myBed.bedNo}床` : '尚未入住'
      uni.showModal({
        title: this.cfg.hasBed ? '确认提交调宿' : '确认首次入住',
        content: this.cfg.hasBed ? `当前：${current}\n目标：${this.selectedBedLabel}\n\n审批完成前原床不变。` : `目标：${this.selectedBedLabel}\n\n确认后将立即入住该床位。`,
        confirmText: this.cfg.hasBed ? '提交申请' : '确认入住',
        success: (r) => { if (r.confirm) this.doSubmit(reason) }
      })
    },
    doSubmit(reason) {
      this.submitting = true
      this._lock.run(() => this.cfg.hasBed ? affairsContractApi.submitDormTransfer(this.sel.bed, reason) : studentApi.selfSelectBed(this.sel.bed))
        .then(() => { safeToast(this.cfg.hasBed ? '调宿申请已提交' : '入住成功', 'success'); this.transferReason = ''; this.load() })
        .catch((e) => { if (e && e.code === 'LOCKED') return; this.showError(e, '提交失败') })
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.dm__bed { background: var(--brand-primary); color: #fff; border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4); }.dm__bed-t { display: block; font-size: var(--font-size-sm); opacity: 0.85; }.dm__bed-v { display: block; font-size: 18px; font-weight: 700; margin-top: 4px; }.dm__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-4); }.dm__notice { display: flex; gap: var(--space-2); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); margin-bottom: var(--space-4); }.dm__notice-t { color: var(--text-secondary); font-size: var(--font-size-base); line-height: 1.6; }.dm__step-t { display: block; font-weight: 600; margin-bottom: var(--space-3); }.dm__label { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }.dm__chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }.dm__chip { padding: 8px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); border: 1px solid var(--border-base); color: var(--text-secondary); }.dm__chip.is-on { background: var(--brand-primary); color: #fff; border-color: var(--brand-primary); }.dm__chip.is-full { opacity: 0.4; }.dm__field { margin-top: var(--space-4); }.dm__textarea { width: 100%; min-height: 80px; box-sizing: border-box; border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px; background: #fff; }.dm__req { color: #dc2626; }.dm__confirm { margin-top: var(--space-5); }.dm__btn { background: var(--brand-primary); color: #fff; border-radius: var(--radius-full); padding: 12px; font-size: var(--font-size-base); }.dm__target { margin-top: 12px; padding: 10px; border-radius: 8px; background: #eff6ff; }.dm__target-k, .dm__target-v { display: block; }.dm__target-k { color: #64748b; font-size: 12px; }.dm__target-v { margin-top: 3px; color: #1d4ed8; font-weight: 600; }.dm__loading, .dm__counter, .dm__empty-text { display: block; margin-top: 6px; color: #94a3b8; font-size: 12px; }.dm__counter { text-align: right; }.dm__history { margin-top: var(--space-5); }.dm__history-row { padding: 10px 0; border-bottom: 1px solid var(--border-base); font-size: 13px; }.dm__history-status, .dm__history-route, .dm__history-reason { display: block; }.dm__history-status { font-weight: 600; color: #334155; }.dm__history-route { margin-top: 4px; color: #1d4ed8; }.dm__history-reason { margin-top: 3px; color: var(--text-tertiary); }
</style>
