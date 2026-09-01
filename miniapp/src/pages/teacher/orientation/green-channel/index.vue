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
              <button class="btn btn-ghost flex-1" @click="openReview(a, 'RETURN')">退回</button>
              <button class="gc__reject flex-1" @click="openReview(a, 'REJECT')">驳回</button>
              <button class="gc__approve flex-1" @click="openReview(a, 'APPROVE')">通过</button>
            </view>
            <view v-else class="gc__done">
              <text class="gc__done-text">已{{ a.statusLabel || a.status }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <view v-if="reviewDialog.visible" class="gc__dialog-mask" @click.self="closeReview">
      <view class="gc__dialog">
        <text class="gc__dialog-title">{{ reviewDialog.label }}绿色通道</text>
        <text class="gc__dialog-copy">{{ reviewDialog.studentName }} · {{ reviewDialog.applyType }}</text>
        <textarea
          v-if="reviewDialog.needsComment"
          v-model="reviewDialog.comment"
          class="gc__dialog-input"
          maxlength="1000"
          :placeholder="'请填写' + reviewDialog.label + '意见（不少于5字）'"
        />
        <text v-else class="gc__dialog-description">确认通过该学生的绿色通道申请？通过后将按服务端资格规则重新计算缴费卡点。</text>
        <text v-if="reviewDialog.error" class="gc__dialog-error">{{ reviewDialog.error }}</text>
        <view class="gc__dialog-actions">
          <button class="gc__dialog-cancel" :disabled="acting" @click="closeReview">取消</button>
          <button class="gc__dialog-confirm" :disabled="acting" @click="submitReview">{{ acting ? '提交中…' : '确认' + reviewDialog.label }}</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { realRequest } from '@/services/request'
import { toast } from '@/utils/nav'
export default {
  data() { return { list: null, state: 'loading', acting: false, statusBarHeight: 20,
    reviewDialog: { visible: false, target: null, action: '', label: '', needsComment: false, studentName: '', applyType: '', comment: '', error: '' } } },
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
    openReview(a, type) {
      if (this.acting) return
      const label = { APPROVE: '通过', REJECT: '驳回', RETURN: '退回' }[type]
      this.reviewDialog = {
        visible: true, target: a, action: type, label,
        needsComment: type !== 'APPROVE', studentName: a.name || '该学生',
        applyType: a.applyType || '绿色通道', comment: '', error: ''
      }
    },
    closeReview() {
      if (this.acting) return
      this.reviewDialog.visible = false
      this.reviewDialog.target = null
    },
    submitReview() {
      if (this.acting || !this.reviewDialog.target) return
      const dialog = this.reviewDialog
      const comment = String(dialog.comment || '').trim()
      if (dialog.needsComment && comment.length < 5) {
        dialog.error = dialog.label + '意见不少于5字'
        return
      }
      dialog.error = ''
      this.acting = true
      const target = dialog.target
      realRequest('/mobile/teacher/orientation/green-channels/' + target.id + '/review', {
        method: 'POST',
        data: { action: dialog.action, comment, expectedVersion: target.version }
      }).then(() => {
        toast('已' + dialog.label)
        this.reviewDialog.visible = false
        this.reviewDialog.target = null
        this.load()
      }).catch((e) => {
        const code = e && String(e.code)
        if (code && code.startsWith('409')) {
          toast('该申请已终审，正在刷新')
          this.reviewDialog.visible = false
          this.reviewDialog.target = null
          this.load()
        } else {
          dialog.error = (e && e.message) || (code && code.startsWith('403')
            ? '没有权限处理该申请'
            : dialog.label + '失败，请重试')
        }
      }).finally(() => { this.acting = false })
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
.gc__dialog-mask { position: fixed; inset: 0; z-index: 2000; display: flex; align-items: center; justify-content: center; padding: 24px; background: rgba(15,23,42,.45); }
.gc__dialog { width: 100%; max-width: 360px; box-sizing: border-box; padding: 20px; border-radius: 16px; background: #fff; box-shadow: 0 20px 60px rgba(15,23,42,.25); }
.gc__dialog-title,.gc__dialog-copy,.gc__dialog-description,.gc__dialog-error { display: block; }
.gc__dialog-title { color: #0f172a; font-size: 18px; font-weight: 700; }
.gc__dialog-copy { margin-top: 8px; color: #475569; font-size: 13px; }
.gc__dialog-description { margin-top: 14px; color: #475569; font-size: 13px; line-height: 1.65; }
.gc__dialog-input { width: 100%; min-height: 100px; box-sizing: border-box; margin-top: 14px; padding: 10px; border: 1px solid #cbd5e1; border-radius: 10px; background: #fff; }
.gc__dialog-error { margin-top: 8px; color: #dc2626; font-size: 12px; }
.gc__dialog-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 18px; }
.gc__dialog-cancel,.gc__dialog-confirm { border-radius: 10px; font-size: 14px; }
.gc__dialog-cancel { background: #f1f5f9; color: #334155; }
.gc__dialog-confirm { background: var(--teacher-600); color: #fff; }
</style>
