<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="现场报到核验" show-back />
    <view class="page-pad">
      <view class="ov__scan card" @click="scan">
        <view class="ov__scan-btn" :class="{ 'is-busy': verifying }">
          <text class="ov__scan-icon">{{ verifying ? '…' : '▣' }}</text>
        </view>
        <text class="ov__scan-tx">{{ verifying ? '核验中…' : '扫描新生报到码' }}</text>
        <text class="ov__scan-alt" @click.stop="manualInput">手动输入报到码 ›</text>
      </view>

      <view v-if="lastResult" class="card ov__result" :class="{ 'is-fail': !lastResult.ok }">
        <text class="ov__result-icon">{{ lastResult.ok ? '✓' : '✕' }}</text>
        <view class="flex-1">
          <text class="t-md t-bold">{{ lastResult.ok ? lastResult.name + ' 核验通过' : '核验失败' }}</text>
          <text class="ov__result-sub">{{ lastResult.detail }}</text>
        </view>
      </view>

      <view class="section-head">
        <text class="section-head__title">今日已核验</text>
        <text class="section-head__more">{{ list.length }} 人</text>
      </view>
      <MobileGlobalState v-if="!list.length" :state="listState" title="今日暂无核验记录" description="核验通过的新生会显示在这里。" @retry="loadList" />
      <view v-else class="card stack-sm">
        <view v-for="s in list" :key="s.id" class="ov__row">
          <view class="ov__row-avatar">{{ s.name.slice(0,1) }}</view>
          <view class="flex-1">
            <text class="t-md">{{ s.name }}</text>
            <text class="ov__row-sub">{{ s.className || '待分班' }}</text>
          </view>
          <text class="ov__row-time">{{ (s.checkinTime || '').slice(11, 16) }}</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() { return { verifying: false, lastResult: null, list: [], listState: 'loading' } },
  onLoad() { this.loadList() },
  onShow() { this.loadList() },
  methods: {
    loadList() {
      this.listState = 'loading'
      teacherApi.getOrientationTodayCheckins().then((d) => {
        this.list = (d && d.list) || []
        this.listState = this.list.length ? 'ready' : 'empty'
      }).catch(() => { this.listState = 'error' })
    },
    scan() {
      if (this.verifying) return
      uni.scanCode({
        onlyFromCamera: false,
        success: (res) => this.verify(res.result),
        fail: () => toast('未能启动扫码，可改用「手动输入报到码」')
      })
    },
    manualInput() {
      if (this.verifying) return
      uni.showModal({
        title: '手动输入报到码', editable: true, placeholderText: '录取编号 / 报到码',
        success: (r) => { if (r.confirm && r.content) this.verify(r.content.trim()) }
      })
    },
    verify(code) {
      if (!code || this.verifying) return
      this.verifying = true
      teacherApi.orientationCheckin(code).then((d) => {
        this.lastResult = { ok: true, name: d.name, detail: (d.className || '待分班') + ' · ' + (d.checkinTime || '').replace('T', ' ').slice(0, 16) }
        this.loadList()
      }).catch((e) => {
        this.lastResult = { ok: false, name: '', detail: (e && e.biz) ? normalizeError(e).text : '核验失败，请重试' }
      }).finally(() => { this.verifying = false })
    }
  }
}
</script>

<style scoped>
.ov__scan { display: flex; flex-direction: column; align-items: center; padding: var(--space-6) var(--space-4); }
.ov__scan-btn {
  width: 88px; height: 88px; border-radius: var(--radius-full); background: var(--brand-gradient-teacher);
  display: flex; align-items: center; justify-content: center; box-shadow: var(--shadow-float);
}
.ov__scan-btn.is-busy { opacity: 0.7; }
.ov__scan-icon { font-size: 36px; color: #fff; }
.ov__scan-tx { margin-top: var(--space-3); font-size: var(--font-size-md); color: var(--text-primary); font-weight: var(--font-weight-medium); }
.ov__scan-alt { margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--teacher-700); }
.ov__result { display: flex; align-items: center; gap: var(--space-3); margin-top: var(--card-gap-mobile); }
.ov__result-icon { width: 36px; height: 36px; border-radius: var(--radius-full); background: var(--success-500); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }
.ov__result.is-fail .ov__result-icon { background: var(--danger-500); }
.ov__result-sub { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.ov__row { display: flex; align-items: center; gap: var(--space-3); }
.ov__row-avatar { width: 36px; height: 36px; border-radius: var(--radius-full); background: var(--teacher-50); color: var(--teacher-700); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.ov__row-sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ov__row-time { font-size: var(--font-size-sm); color: var(--text-tertiary); }
</style>
