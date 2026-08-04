<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="实习打卡" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="i">
        <view class="card ci__map">
          <view class="ci__map-bg">
            <view class="ci__map-pin" />
          </view>
          <text class="ci__map-loc">{{ i.checkin.place || '公司位置未设置' }} · {{ i.checkin.range || '围栏以岗位配置为准' }}</text>
        </view>

        <view class="ci__circle" :class="i.checkin.done ? 'is-done' : 'is-todo'" @click="checkin">
          <text v-if="i.checkin.done" class="ci__circle-num">✓</text>
          <text v-else class="ci__circle-num">{{ checkingIn ? '…' : '打卡' }}</text>
          <text class="ci__circle-lb">{{ i.checkin.done ? '今日已打卡' : (checkingIn ? '定位中' : '点击打卡') }}</text>
        </view>
        <text class="ci__note t-xs t-tertiary">{{ lastResultNote || i.checkin.note || '仅采集一次定位留痕；超范围记异常待核验，不自动认定作弊。生产包禁用演示数据。' }}</text>

        <view class="section-head"><text class="section-head__title">本周打卡记录</text></view>
        <view class="card stack-sm" v-if="days.length">
          <view v-for="d in days" :key="d.date" class="ci__row">
            <text class="ci__row-day">{{ dayLabel(d.date) }}</text>
            <text class="ci__row-date t-xs t-tertiary">{{ d.date.slice(5) }}</text>
            <text class="ci__row-time flex-1">{{ d.time ? d.time.slice(11, 16) : '—' }}</text>
            <MobileStatusTag :label="statusLabel(d.status)" :type="statusType(d.status)" />
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'

const STATUS_LABEL = { NORMAL: '正常', RECORDED: '正常', OUT_OF_RANGE: '超范围', NO_LOCATION: '无定位',
  PENDING: '待打卡', ABSENT: '缺卡' }
const STATUS_TYPE = { NORMAL: 'success', RECORDED: 'success', OUT_OF_RANGE: 'warning', NO_LOCATION: 'warning',
  PENDING: 'default', ABSENT: 'danger' }

export default {
  data() { return { i: null, state: 'loading', checkingIn: false, checkinKey: '', days: [], lastResultNote: '' } },
  onLoad() { this.load() },
  methods: {
    dayLabel(dateStr) {
      const d = new Date(dateStr + 'T00:00:00')
      return ['周日', '周一', '周二', '周三', '周四', '周五', '周六'][d.getDay()]
    },
    statusLabel(s) { return STATUS_LABEL[s] || s },
    statusType(s) { return STATUS_TYPE[s] || 'default' },
    load() {
      this.state = 'loading'
      Promise.all([studentApi.getInternship(), studentApi.getCheckinWeek()]).then(([i, week]) => {
        this.i = i
        this.days = (week && week.days) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    checkin() {
      if (this.i.checkin.done) return toast('今日已打卡')
      if (this.checkingIn) return
      uni.showModal({
        title: '实习打卡',
        content: '仅在此刻采集一次定位用于打卡留痕，不后台持续定位。确认打卡？',
        success: (r) => {
          if (!r.confirm || this.checkingIn) return
          this.checkingIn = true
          this.checkinKey = this.checkinKey || `mp-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
          const submit = (loc) => {
            studentApi.submitCheckin({ ...(loc || {}), idempotencyKey: this.checkinKey,
              deviceRiskFlag: 'normal' }).then((res) => {
              this.checkinKey = ''
              const dist = res && res.distanceM != null ? `（距围栏中心约 ${Math.round(res.distanceM)} 米）` : ''
              const fence = res && res.geofenceConfigured ? '已启用围栏核验' : '岗位未配置围栏，仅留痕'
              this.lastResultNote = `${res.message || '打卡已提交'}${dist} · ${fence}`
              toast(res.message || '打卡成功')
              this.load()
            }).catch((e) => {
              if (e && String(e.code).startsWith('409')) {
                toast('今日已打卡')
                this.load()
              } else if (e && e.biz) {
                toast((e && e.message) || '打卡失败，请稍后重试')
              } else {
                toast('网络异常，打卡未成功，请稍后重试')
              }
            }).finally(() => { this.checkingIn = false })
          }
          // 定位失败不阻断打卡：无定位则只记录时间（后端 result=NO_LOCATION，生成
          // MISSING 异常交教师人工复核，不作作弊认定）。但"用户拒绝授权"是可恢复的，
          // 不应静默产生一条需要老师额外处理的异常记录——先引导去设置里重新授权，
          // 学生仍可选择坚持无定位打卡（2026-08-04 复审补全授权闭环）。
          const tryLocate = () => uni.getLocation({
            type: 'gcj02',
            success: (p) => submit({ lat: p.latitude, lng: p.longitude, gpsAccuracy: p.accuracy }),
            fail: (err) => {
              const denied = /auth|permission|privacy/i.test(String((err && err.errMsg) || ''))
              if (!denied) {
                // 确实取不到定位（无信号/设备未开启定位服务）：按既有契约无定位打卡
                submit({})
                return
              }
              uni.showModal({
                title: '未获得定位权限',
                content: '打卡需要一次定位来核验是否在实习单位范围内。你可以去设置里开启定位权限；也可以坚持无定位打卡，但该记录会标记为异常，需要指导老师人工核实。',
                confirmText: '去设置',
                cancelText: '无定位打卡',
                success: (choice) => {
                  if (!choice.confirm) { submit({}); return }
                  uni.openSetting({
                    success: (res) => {
                      if (res && res.authSetting && res.authSetting['scope.userLocation']) {
                        tryLocate()
                      } else {
                        submit({})
                      }
                    },
                    fail: () => submit({})
                  })
                }
              })
            }
          })
          tryLocate()
        }
      })
    }
  }
}
</script>

<style scoped>
.ci__map { padding: 0; overflow: hidden; }
.ci__map-bg {
  height: 120px; background: linear-gradient(135deg, var(--primary-50), var(--primary-100));
  position: relative; display: flex; align-items: center; justify-content: center;
}
.ci__map-pin { width: 32px; height: 32px; border-radius: var(--radius-full); background: var(--brand-primary); box-shadow: 0 0 0 8px rgba(37,99,235,.14); }
.ci__map-loc { display: block; padding: var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary); text-align: center; }
.ci__circle {
  width: 132px; height: 132px; border-radius: var(--radius-full); margin: var(--space-6) auto var(--space-2);
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.ci__circle.is-todo { background: var(--brand-gradient); box-shadow: 0 14px 30px -12px rgba(37,99,235,.6); }
.ci__circle.is-todo .ci__circle-num { color: #fff; font-size: 17px; font-weight: var(--font-weight-semibold); }
.ci__circle.is-todo .ci__circle-lb { color: rgba(255,255,255,.85); font-size: var(--font-size-xs); margin-top: 4px; }
.ci__circle.is-done { background: var(--success-50); border: 3px solid var(--success-500); }
.ci__circle.is-done .ci__circle-num { color: var(--success-600); font-size: 28px; font-weight: var(--font-weight-semibold); }
.ci__circle.is-done .ci__circle-lb { color: var(--success-600); font-size: var(--font-size-xs); margin-top: 4px; }
.ci__note { display: block; text-align: center; margin-bottom: var(--space-2); }
.ci__row { display: flex; align-items: center; gap: var(--space-3); }
.ci__row-day { width: 40px; font-size: var(--font-size-sm); color: var(--text-primary); font-weight: var(--font-weight-medium); }
</style>
