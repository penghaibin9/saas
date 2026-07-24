<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="学期注册" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card">
          <text class="t-md">{{ d.realName }} · {{ d.studentNo }}</text>
          <text class="mk__sub">学籍状态 {{ d.studentStatus || '—' }}</text>
        </view>
        <MobileGlobalState v-if="!(d.batches || []).length" state="empty" :title="d.note || '暂无开放批次'"
          description="教务处开放注册窗口后，可在此自助完成注册或申请暂缓。" />
        <view v-for="b in d.batches" :key="b.batchId" class="card stack-sm">
          <text class="t-md t-bold">{{ b.batchName }}</text>
          <text class="mk__sub">{{ b.registerTypeLabel }} · {{ (b.windowStart || '').slice(0,10) }} ~ {{ (b.windowEnd || '').slice(0,10) }}</text>
          <text class="mk__sub">注册状态 {{ b.registrationStatus }} · 资格 {{ b.eligibilityStatus }}</text>
          <text v-if="b.blockReason" class="mk__reason">{{ b.blockReason }}</text>
          <text v-if="b.deferral" class="mk__sub">暂缓：{{ b.deferral.status }} {{ b.deferral.reason || '' }}</text>
          <view class="row-gap" style="display:flex;gap:8px;margin-top:8px">
            <button class="btn btn-primary flex-1" :disabled="!b.canRegister || acting" @click="doRegister(b)">完成注册</button>
            <button class="btn btn-ghost flex-1" :disabled="!b.canDefer || acting" @click="doDefer(b)">申请暂缓</button>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'
export default {
  data() { return { d: null, state: 'loading', acting: false } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getMyRegistration().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    doRegister(b) {
      if (!b.canRegister || this.acting) return
      this.acting = true
      studentApi.registerSelf(b.batchId).then(() => { toast('注册成功'); this.load() })
        .catch((e) => toast((e && e.message) || '注册失败'))
        .finally(() => { this.acting = false })
    },
    doDefer(b) {
      if (!b.canDefer || this.acting) return
      uni.showModal({
        title: '申请暂缓注册', editable: true, placeholderText: '请填写暂缓原因',
        success: (r) => {
          if (!r.confirm) return
          const reason = (r.content || '').trim()
          if (reason.length < 2) { toast('原因至少 2 字'); return }
          this.acting = true
          studentApi.deferRegistration(b.batchId, reason).then(() => { toast('暂缓已提交'); this.load() })
            .catch((e) => toast((e && e.message) || '提交失败'))
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>
<style scoped>
.mk__sub { display:block; color: var(--t3); font-size: 12px; margin-top: 4px; }
.mk__reason { display:block; color: var(--warn-fg, #b45309); font-size: 12px; margin-top: 4px; }
</style>
