<template>
  <view class="page-wrap chg">
    <MobileGlobalState :state="pageState" @retry="load">
      <view class="page-pad stack">
        <view class="card">
          <text class="card-title">实习变更申请</text>
          <text class="chg__hint">换岗、换实习单位或自主实习变更，提交后由指导教师审核。</text>
        </view>

        <view class="card stack">
          <view class="chg__field">
            <text class="chg__label">变更类型</text>
            <picker mode="selector" :range="typeLabels" @change="onTypePick">
              <view class="chg__picker">{{ typeLabels[typeIndex] || '请选择' }}</view>
            </picker>
          </view>
          <view class="chg__field">
            <text class="chg__label">目标企业（选填）</text>
            <input v-model="form.targetEnterpriseName" class="chg__input" placeholder="新实习单位名称" />
          </view>
          <view class="chg__field">
            <text class="chg__label">目标岗位（选填）</text>
            <input v-model="form.targetPositionName" class="chg__input" placeholder="新岗位名称" />
          </view>
          <view class="chg__field">
            <text class="chg__label">变更原因 <text class="chg__req">*</text></text>
            <textarea v-model="form.reason" class="chg__textarea" maxlength="500" placeholder="请说明变更原因（不少于 5 字）" />
          </view>
        </view>

        <view v-if="history.length" class="card">
          <text class="card-title">历史申请</text>
          <view v-for="h in history" :key="h.id" class="chg__hist">
            <text>{{ h.changeTypeLabel }} · {{ h.statusLabel }}</text>
            <text class="chg__hist-time">{{ h.createdAt }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar>
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '提交变更申请' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast, back } from '@/utils/nav'

const TYPES = [
  { value: 'CHANGE_POSITION', label: '换岗' },
  { value: 'CHANGE_ENTERPRISE', label: '换实习单位' },
  { value: 'SELF_ARRANGED', label: '自主实习变更' }
]

export default {
  data() {
    return {
      pageState: 'loading', submitting: false,
      typeIndex: 0, typeLabels: TYPES.map((t) => t.label),
      form: { targetEnterpriseName: '', targetPositionName: '', reason: '' },
      history: []
    }
  },
  onLoad() { this.load() },
  methods: {
    onTypePick(e) { this.typeIndex = Number(e.detail.value) || 0 },
    load() {
      this.pageState = 'loading'
      studentApi.getInternshipChangeRequests().then((list) => {
        this.history = list || []
        this.pageState = 'ready'
      }).catch(() => { this.pageState = 'error' })
    },
    submit() {
      if (this.submitting) return
      if ((this.form.reason || '').trim().length < 5) return toast('变更原因不少于 5 字')
      this.submitting = true
      const body = {
        changeType: TYPES[this.typeIndex].value,
        reason: this.form.reason,
        targetEnterpriseName: this.form.targetEnterpriseName,
        targetPositionName: this.form.targetPositionName
      }
      studentApi.applyInternshipChange(body).then(() => {
        toast('变更申请已提交')
        setTimeout(() => back(), 600)
      }).catch((e) => {
        toast((e && e.message) || '提交失败')
      }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.chg__hint { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: var(--space-2); }
.chg__field { display: flex; flex-direction: column; gap: 6px; margin-bottom: var(--space-3); }
.chg__label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.chg__req { color: var(--danger-500); }
.chg__input, .chg__picker { border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px 12px; font-size: var(--font-size-sm); }
.chg__textarea { border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 10px 12px; min-height: 100px; width: 100%; box-sizing: border-box; font-size: var(--font-size-sm); }
.chg__hist { display: flex; justify-content: space-between; padding: var(--space-2) 0; border-bottom: 1px solid var(--border-light); font-size: var(--font-size-sm); }
.chg__hist-time { color: var(--text-tertiary); font-size: var(--font-size-xs); }
</style>
