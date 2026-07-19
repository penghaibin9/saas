<template>
  <view class="page-wrap">
    <view class="gc__hero hero-band is-teacher">
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="gc__navbar"><text class="gc__navbar-title">绿色通道审核</text></view>
      <text class="gc__navbar-sub">学生提交的缓缴/减免申请，通过后自动解除缴费卡点</text>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <MobileGlobalState v-if="!list || !list.length" state="empty" title="暂无待审申请"
          description="学生在小程序提交的绿色通道申请会出现在这里。" />
        <view v-else class="stack">
          <view v-for="a in list" :key="a.id" class="gc card">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ a.name || '（未命名）' }}</text>
                <text class="gc__class">{{ a.className }}</text>
              </view>
              <MobileStatusTag :status="a.status" />
            </view>

            <view class="gc__fields">
              <view class="gc__field"><text class="gc__field-k">申请类型</text><text class="gc__field-v flex-1">{{ a.applyType || '—' }}</text></view>
              <view class="gc__field"><text class="gc__field-k">申请金额</text><text class="gc__field-v flex-1">{{ a.applyAmount || '—' }}</text></view>
              <view v-if="a.remark" class="gc__field"><text class="gc__field-k">申请说明</text><text class="gc__field-v flex-1">{{ a.remark }}</text></view>
              <view class="gc__field"><text class="gc__field-k">提交时间</text><text class="gc__field-v flex-1">{{ (a.submitTime || '').slice(0, 16) }}</text></view>
            </view>

            <view v-if="a.status === 'SUBMITTED' || a.status === 'REVIEWING'" class="gc__actions">
              <button class="btn btn-ghost flex-1" @click="act(a, 'RETURN')">退回</button>
              <button class="gc__reject flex-1" @click="act(a, 'REJECT')">驳回</button>
              <button class="gc__approve flex-1" @click="act(a, 'APPROVE')">通过</button>
            </view>
            <view v-else class="gc__done">
              <text class="gc__done-text">已{{ a.statusLabel || a.status }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { realRequest } from '@/services/request'
import { toast } from '@/utils/nav'
export default {
  data() { return { list: null, state: 'loading', acting: false, statusBarHeight: 20 } },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load()
  },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    load(done) {
      this.state = 'loading'
      realRequest('/mobile/teacher/orientation/green-channels')
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    act(a, type) {
      if (this.acting) return
      const label = { APPROVE: '通过', REJECT: '驳回', RETURN: '退回' }[type]
      const need = type !== 'APPROVE'
      uni.showModal({
        title: label + '绿色通道',
        editable: need,
        placeholderText: need ? ('请填写' + label + '意见（不少于5字）') : '',
        content: need ? '' : ('确认通过「' + (a.name || '该学生') + '」的绿色通道申请？'),
        success: (r) => {
          if (!r.confirm || this.acting) return
          const comment = (r.content || '').trim()
          if (need && comment.length < 5) { toast(label + '意见不少于5字'); return }
          this.acting = true
          realRequest('/mobile/teacher/orientation/green-channels/' + a.id + '/review',
            { method: 'POST', data: { action: type, comment } })
            .then(() => { toast('已' + label); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code && code.startsWith('409')) { toast('该申请已终审，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) { toast((e && e.message) || '没有权限处理该申请') }
              else { toast((e && e.message) || (label + '失败，请重试')) }
            })
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.gc__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.gc__navbar { height: 40px; display: flex; align-items: center; justify-content: center; }
.gc__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.gc__navbar-sub { display: block; font-size: var(--font-size-xs); color: rgba(255,255,255,.85); text-align: center; margin-top: 2px; }
.gc__class { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; }
.gc__fields { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); margin-top: var(--space-3); }
.gc__field { display: flex; gap: var(--space-3); padding: 5px 0; }
.gc__field-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 76px; flex-shrink: 0; }
.gc__field-v { font-size: var(--font-size-sm); color: var(--text-primary); }
.gc__actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.gc__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.gc__reject::after { border: none; }
.gc__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.gc__approve::after { border: none; }
.gc__done { text-align: center; padding: var(--space-2); margin-top: var(--space-2); }
.gc__done-text { font-size: var(--font-size-sm); color: var(--text-tertiary); }
</style>
