<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="o">
        <view class="card oc__identity">
          <text class="card-title">基础信息</text>
          <view class="oc__row"><text class="oc__k">姓名</text><text class="oc__v">{{ o.identity.name }}</text></view>
          <view class="oc__row"><text class="oc__k">性别</text><text class="oc__v">{{ o.identity.gender || '—' }}</text></view>
          <view class="oc__row"><text class="oc__k">录取编号</text><text class="oc__v">{{ o.reportCode.code }}</text></view>
          <view class="oc__row"><text class="oc__k">学院</text><text class="oc__v">{{ o.identity.collegeName || '—' }}</text></view>
          <view class="oc__row"><text class="oc__k">专业</text><text class="oc__v">{{ o.identity.majorName || '—' }}</text></view>
          <view class="oc__row"><text class="oc__k">班级</text><text class="oc__v">{{ o.identity.className || '待分班' }}</text></view>
        </view>

        <view class="card oc__form">
          <text class="card-title">联系方式与生源地</text>
          <view class="oc__field">
            <text class="oc__label">手机号</text>
            <input class="oc__input" v-model="phone" type="number" maxlength="20"
              :placeholder="o.identity.phoneMasked || '请输入常用手机号'" placeholder-class="oc__ph" />
          </view>
          <view class="oc__field">
            <text class="oc__label">生源地</text>
            <input class="oc__input" v-model="origin" maxlength="100"
              :placeholder="o.identity.origin || '如：广东省广州市'" placeholder-class="oc__ph" />
          </view>
        </view>

        <MobileInlineAlert type="info" description="提交后信息核对环节即完成，可在报到总览中查看后续环节。" />
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="o">
      <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '保存并提交' }}</button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast, back } from '@/utils/nav'

const submitLock = createSubmitLock(1500)

export default {
  data() { return { o: null, state: 'loading', phone: '', origin: '', submitting: false } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getOrientation().then((d) => {
        this.o = d
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    submit() {
      if (this.submitting) return
      const phone = this.phone.trim()
      if (phone && !(/^\d{6,20}$/.test(phone))) { toast('手机号格式不正确'); return }
      this.submitting = true
      submitLock.run(() => studentApi.submitOrientationCollect({ phone, origin: this.origin.trim() }))
        .then(() => {
          uni.showToast({ title: '提交成功', icon: 'success' })
          setTimeout(() => back(), 700)
        })
        .catch((e) => {
          if (e && e.code === 'LOCKED') return
          toast(e && e.biz ? normalizeError(e).text : '网络异常，提交未成功，请稍后重试')
        })
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.oc__identity { margin-bottom: var(--card-gap-mobile); }
.oc__row { display: flex; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
.oc__row:last-child { border-bottom: none; }
.oc__k { width: 76px; flex-shrink: 0; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.oc__v { font-size: var(--font-size-base); color: var(--text-primary); }
.oc__field { display: flex; align-items: center; min-height: 48px; border-bottom: 1px solid var(--border-light); }
.oc__field:last-child { border-bottom: none; }
.oc__label { width: 76px; flex-shrink: 0; font-size: var(--font-size-base); color: var(--text-secondary); }
.oc__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.oc__ph { color: var(--text-tertiary); }
</style>
