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

        <view class="dm__notice" v-if="notice">
          <text class="dm__notice-icon">ℹ️</text>
          <text class="dm__notice-t">{{ notice }}</text>
        </view>

        <view v-if="canChoose" class="dm__select">
          <view class="dm__step-t">{{ cfg.hasBed ? '申请调宿：选择目标床位' : '首次入住：选择床位' }}</view>

          <text class="dm__label">① 选楼栋</text>
          <view class="dm__chips">
            <view v-for="b in buildings" :key="b.buildingId" class="dm__chip"
              :class="{ 'is-on': sel.building === b.buildingId }" @click="pickBuilding(b)">
              {{ b.buildingName }}（空 {{ b.vacantBeds }}）
            </view>
          </view>

          <template v-if="sel.building">
            <text class="dm__label">② 选房间</text>
            <view class="dm__chips">
              <view v-for="r in rooms" :key="r.roomId" class="dm__chip"
                :class="{ 'is-on': sel.room === r.roomId, 'is-full': r.vacantBeds === 0 }"
                @click="r.vacantBeds > 0 && pickRoom(r)">
                {{ r.floorNo }}层 {{ r.roomNo }}（空 {{ r.vacantBeds }}）
              </view>
            </view>
          </template>

          <template v-if="sel.room">
            <text class="dm__label">③ 选床位</text>
            <view class="dm__chips">
              <view v-for="bd in beds" :key="bd.bedId" class="dm__chip"
                :class="{ 'is-on': sel.bed === bd.bedId, 'is-full': bd.status !== 'VACANT' || bd.isCurrent }"
                @click="bd.status === 'VACANT' && !bd.isCurrent && (sel.bed = bd.bedId)">
                {{ bd.bedNo }}{{ bd.isCurrent ? '（当前）' : (bd.status === 'VACANT' ? '' : '（已住）') }}
              </view>
            </view>
          </template>

          <view class="dm__field" v-if="cfg.hasBed && sel.bed">
            <text class="dm__label">调宿原因 <text class="dm__req">*</text></text>
            <textarea v-model="transferReason" class="dm__textarea" maxlength="300" placeholder="说明调宿原因（不少于5字）" />
          </view>

          <view class="dm__confirm" v-if="sel.bed">
            <button class="dm__btn" :disabled="submitting" @click="confirm">
              {{ submitting ? '提交中…' : (cfg.hasBed ? '提交调宿申请' : '确认入住该床位') }}
            </button>
          </view>
        </view>

        <view v-if="transfers.length" class="dm__history">
          <text class="dm__step-t">我的调宿申请</text>
          <view v-for="x in transfers" :key="x.transferId" class="dm__history-row">
            <text>{{ x.status || x.currentNode || '处理中' }}</text>
            <text class="dm__history-reason">{{ x.reason }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { safeToast, toastError, createSubmitLock, normalizeError } from '@/services/request'

export default {
  data() {
    return {
      cfg: null, state: 'loading', buildings: [], rooms: [], beds: [], transfers: [],
      sel: { building: '', room: '', bed: '' }, submitting: false,
      transferReason: '', _lock: createSubmitLock()
    }
  },
  computed: {
    subtitle() {
      if (!this.cfg) return ''
      if (this.cfg.hasBed) return '正式调宿须审批'
      return this.cfg.selfSelectEnabled ? '已开放首次自选' : '辅导员分配'
    },
    canChoose() {
      return !!(this.cfg && (this.cfg.hasBed || this.cfg.canSelfSelect))
    },
    notice() {
      if (!this.cfg) return ''
      if (this.cfg.hasBed) return this.cfg.studentNotice || '如需调整床位，请提交调宿申请，审批完成前原床不变。'
      return this.cfg.selfSelectEnabled ? '首次自选成功后立即入住；已有床位后不能直接换床。' : this.cfg.studentNotice
    }
  },
  onLoad() { this.load() },
  methods: {
    showError(e, fallback) {
      const n = normalizeError(e)
      safeToast(n.text || (e && e.message) || fallback)
      if (n.kind === 'conflict') this.load()
    },
    load() {
      this.state = 'loading'
      this.sel = { building: '', room: '', bed: '' }
      this.rooms = []
      this.beds = []
      Promise.all([
        studentApi.getMyDorm(),
        affairsContractApi.getMyDormTransfers().catch(() => ({ items: [] }))
      ]).then(([dorm, transferData]) => {
        this.cfg = dorm
        this.transfers = (transferData && transferData.items) || []
        this.state = 'ready'
        if (dorm.hasBed) this.loadTransferOptions()
        else if (dorm.canSelfSelect || dorm.selfSelectEnabled) this.loadSelfSelectOptions()
      }).catch((e) => {
        this.state = 'error'
        this.showError(e, '宿舍信息加载失败')
      })
    },
    loadSelfSelectOptions() {
      studentApi.getDormOptions().then((d) => { this.buildings = d.buildings || [] })
        .catch((e) => this.showError(e, '可选楼栋加载失败'))
    },
    loadTransferOptions() {
      affairsContractApi.getDormTransferOptions().then((d) => { this.buildings = d.items || [] })
        .catch((e) => this.showError(e, '调宿可选楼栋加载失败'))
    },
    pickBuilding(b) {
      this.sel = { building: b.buildingId, room: '', bed: '' }
      this.rooms = []
      this.beds = []
      const task = this.cfg.hasBed
        ? affairsContractApi.getDormTransferRooms(b.buildingId)
        : studentApi.getDormRooms(b.buildingId)
      task.then((d) => { this.rooms = d.items || [] }).catch(toastError)
    },
    pickRoom(r) {
      this.sel.room = r.roomId
      this.sel.bed = ''
      this.beds = []
      const task = this.cfg.hasBed
        ? affairsContractApi.getDormTransferBeds(r.roomId)
        : studentApi.getDormBeds(r.roomId)
      task.then((d) => { this.beds = d.items || [] }).catch(toastError)
    },
    confirm() {
      if (this.submitting || !this.sel.bed) return
      if (this.cfg.hasBed && this.transferReason.trim().length < 5) {
        return safeToast('调宿原因至少填写5个字')
      }
      this.submitting = true
      this._lock.run(() => this.cfg.hasBed
        ? affairsContractApi.submitDormTransfer(this.sel.bed, this.transferReason.trim())
        : studentApi.selfSelectBed(this.sel.bed))
        .then(() => {
          safeToast(this.cfg.hasBed ? '调宿申请已提交' : '入住成功', 'success')
          this.transferReason = ''
          this.load()
        })
        .catch((e) => { if (e && e.code === 'LOCKED') return; this.showError(e, '提交失败') })
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.dm__bed { background: var(--brand-primary); color: #fff; border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4); }
.dm__bed-t { display: block; font-size: var(--font-size-sm); opacity: 0.85; }
.dm__bed-v { display: block; font-size: 18px; font-weight: 700; margin-top: 4px; }
.dm__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-4); }
.dm__notice { display: flex; gap: var(--space-2); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); margin-bottom: var(--space-4); }
.dm__notice-t { color: var(--text-secondary); font-size: var(--font-size-base); line-height: 1.6; }
.dm__step-t { display: block; font-weight: 600; margin-bottom: var(--space-3); }
.dm__label { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.dm__chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.dm__chip { padding: 8px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); border: 1px solid var(--border-base); color: var(--text-secondary); }
.dm__chip.is-on { background: var(--brand-primary); color: #fff; border-color: var(--brand-primary); }
.dm__chip.is-full { opacity: 0.4; }
.dm__field { margin-top: var(--space-4); }
.dm__textarea { width: 100%; min-height: 80px; box-sizing: border-box; border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px; background: #fff; }
.dm__req { color: #dc2626; }
.dm__confirm { margin-top: var(--space-5); }
.dm__btn { background: var(--brand-primary); color: #fff; border-radius: var(--radius-full); padding: 12px; font-size: var(--font-size-base); }
.dm__history { margin-top: var(--space-5); }
.dm__history-row { display: flex; justify-content: space-between; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--border-base); font-size: 13px; }
.dm__history-reason { color: var(--text-tertiary); text-align: right; }
</style>
