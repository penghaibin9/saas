<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的宿舍" :subtitle="cfg ? (cfg.selfSelectEnabled ? '已开放自选' : '辅导员分配') : ''" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="cfg">
        <!-- 当前床位 -->
        <view class="dm__bed" v-if="cfg.hasBed">
          <text class="dm__bed-t">我的床位</text>
          <text class="dm__bed-v">{{ cfg.myBed.building }} · {{ cfg.myBed.room }}室 · {{ cfg.myBed.bedNo }}床</text>
        </view>
        <view class="dm__empty" v-else><text>你还没有床位</text></view>

        <!-- 未放开自选：提醒学生 -->
        <view class="dm__notice" v-if="!cfg.selfSelectEnabled">
          <text class="dm__notice-icon">ℹ️</text>
          <text class="dm__notice-t">{{ cfg.studentNotice }}</text>
        </view>

        <!-- 放开自选：选床级联 -->
        <view v-else class="dm__select">
          <view class="dm__step-t">{{ cfg.hasBed ? '如需换床，选择新床位' : '选择床位' }}</view>

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
                :class="{ 'is-on': sel.bed === bd.bedId, 'is-full': bd.status !== 'VACANT' }"
                @click="bd.status === 'VACANT' && (sel.bed = bd.bedId)">
                {{ bd.bedNo }}{{ bd.status === 'VACANT' ? '' : '（已住）' }}
              </view>
            </view>
          </template>

          <view class="dm__confirm" v-if="sel.bed">
            <button class="dm__btn" :disabled="submitting" @click="confirm">确认入住该床位</button>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { safeToast, toastError, createSubmitLock } from '@/services/request'
export default {
  data() {
    return {
      cfg: null, state: 'loading', buildings: [], rooms: [], beds: [],
      sel: { building: '', room: '', bed: '' }, submitting: false, _lock: createSubmitLock()
    }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      this.sel = { building: '', room: '', bed: '' }
      studentApi.getMyDorm().then((d) => {
        this.cfg = d; this.state = 'ready'
        if (d.selfSelectEnabled) this.loadOptions()
      }).catch(() => { this.state = 'error' })
    },
    loadOptions() {
      studentApi.getDormOptions().then((d) => { this.buildings = d.buildings || [] }).catch(() => {})
    },
    pickBuilding(b) {
      this.sel = { building: b.buildingId, room: '', bed: '' }; this.rooms = []; this.beds = []
      studentApi.getDormRooms(b.buildingId).then((d) => { this.rooms = d.items || [] }).catch(toastError)
    },
    pickRoom(r) {
      this.sel.room = r.roomId; this.sel.bed = ''; this.beds = []
      studentApi.getDormBeds(r.roomId).then((d) => { this.beds = d.items || [] }).catch(toastError)
    },
    confirm() {
      this.submitting = true
      this._lock.run(() => studentApi.selfSelectBed(this.sel.bed))
        .then(() => { safeToast('入住成功', 'success'); this.load() })
        .catch((e) => { if (e && e.code === 'LOCKED') return; toastError(e) })
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
.dm__notice { display: flex; gap: var(--space-2); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); }
.dm__notice-t { color: var(--text-secondary); font-size: var(--font-size-base); line-height: 1.6; }
.dm__step-t { font-weight: 600; margin-bottom: var(--space-3); }
.dm__label { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.dm__chips { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.dm__chip { padding: 8px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); border: 1px solid var(--border-base); color: var(--text-secondary); }
.dm__chip.is-on { background: var(--brand-primary); color: #fff; border-color: var(--brand-primary); }
.dm__chip.is-full { opacity: 0.4; }
.dm__confirm { margin-top: var(--space-5); }
.dm__btn { background: var(--brand-primary); color: #fff; border-radius: var(--radius-full); padding: 12px; font-size: var(--font-size-base); }
</style>
