<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="o" class="page-pad stack">
        <MobileInlineAlert v-if="!available" type="warning" :description="unavailableReason" />
        <view class="card stack-sm">
          <text class="card-title">到校计划</text>
          <view class="oa__field"><text>到校方式</text><picker :range="modeLabels" :value="modeIndex" @change="modeIndex = Number($event.detail.value)"><text class="oa__value">{{ modeLabels[modeIndex] }} ›</text></picker></view>
          <view class="oa__field"><text>到校日期</text><picker mode="date" :value="form.date" @change="form.date = $event.detail.value"><text class="oa__value">{{ form.date || '请选择' }} ›</text></picker></view>
          <view class="oa__field"><text>到校时间</text><picker mode="time" :value="form.time" @change="form.time = $event.detail.value"><text class="oa__value">{{ form.time || '请选择' }} ›</text></picker></view>
          <view class="oa__field"><text>站点/航站楼</text><input v-model="form.stationName" class="oa__input" placeholder="申请接站时必填" /></view>
          <view class="oa__field"><text>车次/航班号</text><input v-model="form.transportNo" class="oa__input" placeholder="选填" /></view>
          <view class="oa__field"><text>随行人数</text><input v-model="form.companionCount" type="number" class="oa__input" placeholder="0-20" /></view>
          <view class="oa__field" @click="form.pickupRequired = !form.pickupRequired"><text>申请学校接站</text><switch :checked="form.pickupRequired" color="#2563eb" /></view>
        </view>
        <MobileInlineAlert type="info" description="计划到校时间须在学校公布的报到窗口内；保存冲突时页面会刷新最新版本。" />
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="o"><button class="btn btn-primary flex-1" :disabled="submitting || !available" @click="submit">{{ submitting ? '保存中…' : '保存到校计划' }}</button></MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'

const modes = ['TRAIN', 'AIR', 'COACH', 'SELF_DRIVE', 'CITY_TRANSIT', 'OTHER']
export default {
  data() { return { o: null, state: 'loading', submitting: false, modeIndex: 0, modeLabels: ['高铁/火车', '飞机', '长途客车', '自驾', '市内公共交通', '其他'], form: { date: '', time: '', stationName: '', transportNo: '', pickupRequired: false, companionCount: 0, expectedVersion: 0 } } },
  computed: {
    available() { return !!this.o?.selfService?.available },
    unavailableReason() { return this.o?.selfService?.reason || '当前预报到未开放，请联系学校。' }
  },
  onLoad() { this.load() },
  methods: {
    async load() {
      this.state = 'loading'
      try {
        this.o = await studentApi.getOrientation()
        const plan = this.o?.selfService?.arrivalPlan
        if (plan) {
          this.modeIndex = Math.max(0, modes.indexOf(plan.arrivalMode))
          const value = String(plan.plannedArrivalAt || '')
          Object.assign(this.form, { ...plan, date: value.slice(0, 10), time: value.slice(11, 16), expectedVersion: plan.version })
        }
        this.state = 'ready'
      } catch (e) { this.state = 'error' }
    },
    async submit() {
      if (!this.form.date || !this.form.time) return toast('请选择计划到校日期和时间')
      const count = Number(this.form.companionCount || 0)
      if (!Number.isInteger(count) || count < 0 || count > 20) return toast('随行人数须为 0 到 20 的整数')
      if (this.form.pickupRequired && !String(this.form.stationName || '').trim()) return toast('申请接站时请填写到达站点')
      this.submitting = true
      try {
        await studentApi.submitOrientationArrival({
          arrivalMode: modes[this.modeIndex], plannedArrivalAt: `${this.form.date}T${this.form.time}:00`,
          stationName: String(this.form.stationName || '').trim(), transportNo: String(this.form.transportNo || '').trim(),
          pickupRequired: !!this.form.pickupRequired, companionCount: count, expectedVersion: Number(this.form.expectedVersion || 0)
        })
        toast('到校计划已保存'); await this.load()
      } catch (e) { toast(e?.message || '保存失败，请刷新后重试'); if (String(e?.code || '').includes('409')) await this.load() }
      finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
.oa__field { display:flex; justify-content:space-between; align-items:center; min-height:48px; border-bottom:1px solid var(--border-light); font-size:var(--font-size-base); color:var(--text-secondary); }
.oa__field:last-child { border-bottom:none; }
.oa__value { color:var(--text-primary); }
.oa__input { width:55%; text-align:right; color:var(--text-primary); }
</style>
