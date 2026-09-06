<template>
  <!-- #ifdef MP-WEIXIN -->
  <view v-if="visible" class="pg__mask">
    <view class="pg__sheet">
      <text class="pg__title">用户隐私保护提示</text>
      <text class="pg__body">
        为了向你提供实习打卡等服务，我们需要在你主动操作时收集必要的信息。
        请阅读并同意<text class="pg__link" @click="openDoc">《{{ contractName || '隐私政策' }}》</text>后继续。
      </text>
      <view class="pg__acts">
        <button class="pg__btn pg__btn--ghost" plain @click="onDisagree">拒绝</button>
        <button
          id="pg-agree-btn"
          class="pg__btn pg__btn--primary"
          plain
          open-type="agreePrivacyAuthorization"
          @agreeprivacyauthorization="onAgree"
        >同意并继续</button>
      </view>
    </view>
  </view>
  <!-- #endif -->
</template>

<script>
/**
 * 微信隐私授权弹窗。
 *
 * 微信自 2023-10-17 起对已在小程序后台声明的隐私接口做前置校验：用户未同意隐私协议时，
 * wx.getLocation 等接口直接失败（errno 112 "api scope is not declared in the privacy
 * agreement"）。这种失败**不能**用 openSetting 修复——openSetting 管的是系统授权，
 * 而这里缺的是"同意隐私协议"这一步，只能由带 open-type="agreePrivacyAuthorization"
 * 的 button 完成。
 *
 * 多个业务组件可以声明 <MobilePrivacyGate />，但整个运行时只注册一个
 * wx.onNeedPrivacyAuthorization 监听器；当前页面最后挂载的 gate 作为唯一 UI owner。
 * 这样列表/循环中的多个附件选择器不会叠加多个遮罩，也不会重复注册隐私回调。
 */
const privacyGateInstances = []
let privacyListenerInstalled = false

function activePrivacyGate() {
  return privacyGateInstances[privacyGateInstances.length - 1] || null
}

function installPrivacyListener() {
  if (privacyListenerInstalled) return
  if (typeof wx === 'undefined' || typeof wx.onNeedPrivacyAuthorization !== 'function') return

  wx.onNeedPrivacyAuthorization((resolve, eventInfo) => {
    const gate = activePrivacyGate()
    if (!gate) {
      // 没有可承载授权 UI 的当前页面时 fail closed，避免隐私 API 请求悬空。
      resolve({ event: 'disagree' })
      return
    }
    gate.acceptPrivacyRequest(resolve, eventInfo)
  })
  privacyListenerInstalled = true
}

export default {
  name: 'MobilePrivacyGate',
  data() {
    return { visible: false, contractName: '', _resolve: null }
  },
  mounted() {
    privacyGateInstances.push(this)
    installPrivacyListener()
  },
  beforeUnmount() {
    const index = privacyGateInstances.indexOf(this)
    if (index >= 0) privacyGateInstances.splice(index, 1)
    if (this._resolve) {
      this._resolve({ event: 'disagree' })
      this._resolve = null
    }
    this.visible = false
  },
  methods: {
    acceptPrivacyRequest(resolve, eventInfo) {
      this._resolve = resolve
      this.contractName = (eventInfo && eventInfo.privacyContractName) || ''
      this.visible = true
    },
    openDoc() {
      uni.navigateTo({ url: '/pages/common/legal-doc/index?kind=privacy' })
    },
    onAgree() {
      this.visible = false
      if (this._resolve) {
        this._resolve({ buttonId: 'pg-agree-btn', event: 'agree' })
        this._resolve = null
      }
      this.$emit('agree')
    },
    onDisagree() {
      this.visible = false
      if (this._resolve) {
        this._resolve({ event: 'disagree' })
        this._resolve = null
      }
      this.$emit('disagree')
    }
  }
}
</script>

<style scoped>
.pg__mask { position: fixed; inset: 0; z-index: 2000; display: flex; align-items: center; justify-content: center; background: rgba(15, 23, 42, .55); }
.pg__sheet { width: 82%; max-width: 340px; padding: 22px 20px 16px; border-radius: 14px; background: #fff; }
.pg__title { display: block; font-size: 17px; font-weight: 600; text-align: center; color: var(--text-primary); }
.pg__body { display: block; margin-top: 14px; font-size: 13px; line-height: 1.75; color: var(--text-secondary); }
.pg__link { color: var(--brand-primary); }
.pg__acts { display: flex; gap: 10px; margin-top: 20px; }
.pg__btn { flex: 1; height: 42px; line-height: 42px; border-radius: 8px; font-size: 14px; border: none; }
.pg__btn--ghost { background: var(--bg-page, #f3f4f6); color: var(--text-secondary); }
.pg__btn--primary { background: var(--brand-primary); color: #fff; }
</style>
