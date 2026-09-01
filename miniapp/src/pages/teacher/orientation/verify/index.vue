<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="现场报到核验" show-back />
    <view class="page-pad">
      <view class="ov__point card">
        <text class="t-sm text-secondary">当前报到点</text>
        <picker :range="pointLabels" :value="pointIndex" @change="pickPoint">
          <view class="ov__picker">{{ selectedPoint ? selectedPoint.name : '请选择已授权报到点' }} <text>⌄</text></view>
        </picker>
        <text v-if="selectedPoint?.location" class="ov__point-location">{{ selectedPoint.location }}</text>
      </view>

      <view class="ov__scan card" @click="scan">
        <view class="ov__scan-btn" :class="{ 'is-busy': verifying }">
          <text class="ov__scan-icon">{{ verifying ? '…' : '▣' }}</text>
        </view>
        <text class="ov__scan-tx">{{ verifying ? '预检中…' : '扫描一次性报到凭证' }}</text>
        <text class="ov__scan-alt" @click.stop="manualVisible = !manualVisible">粘贴签名凭证 ›</text>
      </view>

      <view v-if="manualVisible" class="card ov__manual">
        <text class="t-md t-bold">粘贴签名凭证</text>
        <textarea v-model.trim="manualToken" class="ov__token-input" placeholder="仅接受学生端签发的 oci1 签名凭证；录取编号无效" />
        <button class="btn-primary" :disabled="verifying || !manualToken" @click="preflight(manualToken)">先预检，不直接报到</button>
      </view>

      <view v-if="preflightResult" class="card ov__preflight">
        <view class="row-between">
          <view>
            <text class="t-lg t-bold">{{ preflightResult.student.name }}</text>
            <text class="ov__result-sub">{{ preflightResult.student.collegeName }} · {{ preflightResult.student.className || '待分班' }}</text>
          </view>
          <text class="ov__qualified">资格通过</text>
        </view>
        <view class="ov__facts">
          <view><text>录取编号</text><strong>{{ preflightResult.student.admissionNo }}</strong></view>
          <view><text>宿舍</text><strong>{{ preflightResult.dorm.label }}</strong></view>
          <view><text>凭证有效至</text><strong>{{ (preflightResult.expiresAt || '').replace('T', ' ').slice(0, 19) }}</strong></view>
        </view>
        <button class="btn-primary" :disabled="verifying || !selectedPoint" @click="confirmVisible = true">确认现场报到</button>
      </view>

      <view v-if="lastResult" class="card ov__result" :class="{ 'is-fail': !lastResult.ok }">
        <text class="ov__result-icon">{{ lastResult.ok ? '✓' : '✕' }}</text>
        <view class="flex-1">
          <text class="t-md t-bold">{{ lastResult.ok ? lastResult.name + ' 已完成现场报到' : '核验失败' }}</text>
          <text class="ov__result-sub">{{ lastResult.detail }}</text>
        </view>
      </view>

      <view class="section-head">
        <text class="section-head__title">今日已核验</text>
        <text class="section-head__more">{{ list.length }} 人</text>
      </view>
      <MobileGlobalState v-if="!list.length" :state="listState" title="今日暂无核验记录" description="签名凭证确认成功的新生会显示在这里。" @retry="loadList" />
      <view v-else class="card stack-sm">
        <view v-for="s in list" :key="s.id" class="ov__row">
          <view class="ov__row-avatar">{{ s.name.slice(0,1) }}</view>
          <view class="flex-1">
            <text class="t-md">{{ s.name }}</text>
            <text class="ov__row-sub">{{ s.className || '待分班' }} · {{ s.checkinPointName || '现场报到点' }}</text>
          </view>
          <text class="ov__row-time">{{ (s.checkinTime || '').slice(11, 16) }}</text>
        </view>
      </view>
    </view>

    <view v-if="confirmVisible && preflightResult" class="ov__dialog-mask" @click.self="confirmVisible = false">
      <view class="ov__dialog card">
        <text class="t-lg t-bold">确认现场报到</text>
        <text class="ov__dialog-copy">{{ preflightResult.student.name }} · {{ selectedPoint?.name }}</text>
        <text class="ov__dialog-note">确认后一次性凭证立即失效，并形成不可重复的 CheckinRecord。</text>
        <view class="ov__dialog-actions">
          <button class="btn-ghost" @click="confirmVisible = false">取消</button>
          <button class="btn-primary" :disabled="verifying" @click="confirmCheckin">确认现场报到</button>
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
  data() {
    return {
      verifying: false, lastResult: null, list: [], listState: 'loading',
      points: [], pointIndex: 0, manualVisible: false, manualToken: '',
      scannedToken: '', preflightResult: null, confirmVisible: false
    }
  },
  computed: {
    pointLabels() { return this.points.map((item) => item.location ? `${item.name} · ${item.location}` : item.name) },
    selectedPoint() { return this.points[this.pointIndex] || null }
  },
  onLoad() { this.loadAll() },
  onShow() { this.loadList() },
  methods: {
    async loadAll() {
      try {
        const data = await teacherApi.getOrientationCheckinPoints()
        this.points = data.items || []
        this.pointIndex = 0
      } catch (e) { toast(e?.message || '报到点加载失败') }
      await this.loadList()
    },
    pickPoint(e) { this.pointIndex = Number(e.detail.value || 0) },
    loadList() {
      this.listState = 'loading'
      return teacherApi.getOrientationTodayCheckins().then((d) => {
        this.list = (d && d.list) || []
        this.listState = this.list.length ? 'ready' : 'empty'
      }).catch(() => { this.listState = 'error' })
    },
    scan() {
      if (this.verifying) return
      uni.scanCode({
        onlyFromCamera: false,
        success: (res) => this.preflight(res.result),
        fail: () => toast('未能启动扫码，可使用页面内“粘贴签名凭证”')
      })
    },
    async preflight(token) {
      const value = String(token || '').trim()
      if (!value || this.verifying) return
      this.verifying = true
      this.lastResult = null
      this.preflightResult = null
      try {
        this.preflightResult = await teacherApi.orientationCheckinPreflight(value)
        this.scannedToken = value
        this.manualVisible = false
        this.manualToken = ''
      } catch (e) {
        this.lastResult = { ok: false, name: '', detail: e?.biz ? normalizeError(e).text : (e?.message || '凭证预检失败') }
      } finally { this.verifying = false }
    },
    async confirmCheckin() {
      if (!this.scannedToken || !this.selectedPoint || this.verifying) return
      this.verifying = true
      try {
        const d = await teacherApi.orientationCheckinConfirm(this.scannedToken, this.selectedPoint.id)
        this.lastResult = { ok: true, name: d.name, detail: `${d.checkinPointName} · ${(d.checkinTime || '').replace('T', ' ').slice(0, 16)}` }
        this.confirmVisible = false
        this.preflightResult = null
        this.scannedToken = ''
        await this.loadList()
      } catch (e) {
        this.confirmVisible = false
        this.lastResult = { ok: false, name: '', detail: e?.biz ? normalizeError(e).text : (e?.message || '现场报到确认失败') }
      } finally { this.verifying = false }
    }
  }
}
</script>

<style scoped>
.ov__point { display:grid; gap:8px; }
.ov__picker { display:flex; justify-content:space-between; align-items:center; min-height:42px; padding:0 12px; border:1px solid var(--border-base); border-radius:var(--radius-base); }
.ov__point-location { font-size:var(--font-size-xs); color:var(--text-tertiary); }
.ov__scan { display:flex; flex-direction:column; align-items:center; padding:var(--space-6) var(--space-4); margin-top:var(--card-gap-mobile); }
.ov__scan-btn { width:88px; height:88px; border-radius:var(--radius-full); background:var(--brand-gradient-teacher); display:flex; align-items:center; justify-content:center; box-shadow:var(--shadow-float); }
.ov__scan-btn.is-busy { opacity:.7; }
.ov__scan-icon { font-size:36px; color:#fff; }
.ov__scan-tx { margin-top:var(--space-3); font-size:var(--font-size-md); color:var(--text-primary); font-weight:var(--font-weight-medium); }
.ov__scan-alt { margin-top:var(--space-3); font-size:var(--font-size-sm); color:var(--teacher-700); }
.ov__manual,.ov__preflight { display:grid; gap:var(--space-3); margin-top:var(--card-gap-mobile); }
.ov__token-input { width:100%; min-height:150rpx; box-sizing:border-box; padding:12px; border:1px solid var(--border-base); border-radius:var(--radius-base); font-size:var(--font-size-xs); word-break:break-all; }
.ov__qualified { color:var(--success-600); background:var(--success-50); padding:4px 10px; border-radius:var(--radius-full); font-size:var(--font-size-xs); }
.ov__facts { display:grid; gap:8px; padding:12px; background:var(--gray-50); border-radius:var(--radius-base); }
.ov__facts view { display:flex; justify-content:space-between; gap:14px; }
.ov__facts text { color:var(--text-tertiary); font-size:var(--font-size-sm); }
.ov__facts strong { text-align:right; font-size:var(--font-size-sm); }
.ov__result { display:flex; align-items:center; gap:var(--space-3); margin-top:var(--card-gap-mobile); }
.ov__result-icon { width:36px; height:36px; border-radius:var(--radius-full); background:var(--success-500); color:#fff; display:flex; align-items:center; justify-content:center; font-size:18px; flex-shrink:0; }
.ov__result.is-fail .ov__result-icon { background:var(--danger-500); }
.ov__result-sub { display:block; font-size:var(--font-size-sm); color:var(--text-secondary); margin-top:2px; }
.ov__row { display:flex; align-items:center; gap:var(--space-3); }
.ov__row-avatar { width:36px; height:36px; border-radius:var(--radius-full); background:var(--teacher-50); color:var(--teacher-700); display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.ov__row-sub { display:block; font-size:var(--font-size-xs); color:var(--text-tertiary); margin-top:2px; }
.ov__row-time { font-size:var(--font-size-sm); color:var(--text-tertiary); }
.ov__dialog-mask { position:fixed; inset:0; z-index:999; display:flex; align-items:center; justify-content:center; padding:32rpx; background:rgba(15,23,42,.48); }
.ov__dialog { width:100%; max-width:620rpx; display:grid; gap:var(--space-3); }
.ov__dialog-copy { color:var(--text-primary); }
.ov__dialog-note { color:var(--text-secondary); font-size:var(--font-size-sm); line-height:1.6; }
.ov__dialog-actions { display:grid; grid-template-columns:1fr 1fr; gap:var(--space-3); }
</style>
