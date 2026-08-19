<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="消息通知设置" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="loaded">
        <!-- 分区一：站内消息分类 -->
        <view class="card">
          <text class="card-title">站内消息分类</text>
          <text class="ns__hint">关闭后，对应分类的消息将不再出现在你的消息中心。</text>
          <view class="list-group" style="margin-top: var(--space-3);">
            <view v-for="it in items" :key="it.key" class="list-row">
              <text class="flex-1 t-md">{{ it.label }}</text>
              <switch :checked="it.enabled" color="var(--brand-primary)" @change="toggle(it, $event)" />
            </view>
          </view>
        </view>

        <!-- 分区二：微信重要提醒（独立渠道，状态来自服务端，不用一个开关表示两件事） -->
        <view class="card" v-if="isStudent">
          <text class="card-title">微信重要提醒</text>
          <text class="ns__hint">站内分类只影响消息中心；能否在微信里收到提醒，取决于下面的授权状态。</text>

          <MobileInlineAlert v-if="!wechat.configured" type="info" title="学校尚未开通微信提醒"
            description="该能力需要学校在微信公众平台完成配置后才可使用。" />
          <template v-else>
            <view class="list-row">
              <view class="flex-1">
                <text class="t-md">微信订阅授权</text>
                <text class="ns__sub">{{ wechat.effective ? '已授权，可接收重要提醒' : '尚未授权，暂不会收到微信提醒' }}</text>
              </view>
              <MobileStatusTag :label="wechat.effective ? '已授权' : '未授权'"
                :type="wechat.effective ? 'success' : 'default'" />
            </view>
            <view class="list-group" style="margin-top: var(--space-2);">
              <view v-for="scene in wechat.scenes" :key="scene.key" class="list-row">
                <text class="flex-1 t-md">{{ scene.label }}</text>
                <text class="ns__scene" :class="{ 'is-off': !scene.ready }">
                  {{ scene.ready ? '可提醒' : '学校未开通' }}
                </text>
              </view>
            </view>
            <button class="btn btn-secondary ns__auth" :disabled="requesting" @click="requestSubscribe">
              {{ requesting ? '处理中…' : (wechat.effective ? '重新授权微信提醒' : '开启微信重要提醒') }}
            </button>
          </template>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import {
  notifyPreferences, notifySetPreference,
  teacherNotifyPreferences, teacherNotifySetPreference,
  wechatSubscribeStatus
} from '@/services/realApi'
import { toast } from '@/utils/nav'

// V3 §9.3：站内消息分类与微信订阅授权是两条独立渠道，必须分区展示。
// 微信侧的"开没开"只以服务端返回的 configured/authorized 为准；
// provider 未配置或用户未授权时如实显示未开启，绝不因为点过按钮就宣称成功。
export default {
  data() {
    return {
      state: 'loading', loaded: false, items: [], isStudent: true, requesting: false,
      wechat: { configured: false, authorized: false, effective: false, scenes: [] }
    }
  },
  onLoad() {
    this.isStudent = useSessionStore().side === 'student'
    this.load()
  },
  methods: {
    api() {
      return this.isStudent
        ? { getNotifyPreferences: notifyPreferences, setNotifyPreference: notifySetPreference }
        : { getNotifyPreferences: teacherNotifyPreferences, setNotifyPreference: teacherNotifySetPreference }
    },
    load() {
      this.state = 'loading'
      const tasks = [this.api().getNotifyPreferences()]
      tasks.push(this.isStudent ? wechatSubscribeStatus().catch(() => null) : Promise.resolve(null))
      Promise.all(tasks).then(([prefs, wechat]) => {
        this.items = (prefs && prefs.items) || []
        if (wechat) this.wechat = wechat
        this.loaded = true
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    toggle(it, e) {
      const enabled = !!e.detail.value
      const prev = it.enabled
      it.enabled = enabled
      this.api().setNotifyPreference(it.key, enabled).catch(() => {
        it.enabled = prev
        toast('保存失败，请稍后重试')
      })
    },
    requestSubscribe() {
      // requestSubscribeMessage 只能由用户点击触发，且只在服务端已配置模板时才请求。
      const ready = (this.wechat.scenes || []).filter((scene) => scene.ready).map((scene) => scene.key)
      if (!this.wechat.configured || !ready.length) {
        toast('学校尚未开通微信提醒')
        return
      }
      if (typeof uni.requestSubscribeMessage !== 'function') {
        toast('当前环境不支持微信订阅消息')
        return
      }
      this.requesting = true
      uni.requestSubscribeMessage({
        tmplIds: ready,
        complete: () => {
          this.requesting = false
          // 授权结果以服务端复核为准：微信返回 accept 不代表 openid 已经落库。
          this.load()
        }
      })
    }
  }
}
</script>

<style scoped>
.ns__hint { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 4px; }
.ns__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ns__scene { font-size: var(--font-size-xs); color: var(--success-600, #16a34a); }
.ns__scene.is-off { color: var(--text-tertiary); }
.ns__auth { margin-top: var(--space-3); }
</style>
