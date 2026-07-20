<template>
  <AppStepGuide v-model="open" :steps="steps" @finish="markSeen" @skip="markSeen" />
</template>

<script>
/**
 * AppPageGuide —— 页面级新手引导（AppStepGuide + 后端持久化 + 顶栏「重看」联动）。
 *
 * 业务页只需一行：<AppPageGuide guide-key="graduation.gd-batches" />
 * 步骤文案统一登记在 config/help/guides.js，不散落在业务页。
 *
 * 「已看过」存后端 t_user_preference（键 guide.<guideKey>，值 = 引导版本号），不用 localStorage：
 * 老师换一台电脑或清缓存后不该被重复弹引导。引导文案改版时把 guides.js 里的 version 调高，
 * 老师会自动重看一次，无需清库。
 *
 * 失败策略：偏好读取失败时「不弹」。后端不通时页面本来也没数据，
 * 此时每次进页面都弹引导只会骚扰老师；首次引导可由顶栏「?」→「重看本页引导」手动触发。
 */
import { request } from '@/services/http/client'
import { onGuideReplay } from '@/utils/guideBus'
import { getGuide, guidePrefKey } from '@/config/help/guides'
import AppStepGuide from './AppStepGuide.vue'

export default {
  name: 'AppPageGuide',
  components: { AppStepGuide },
  props: {
    /** 引导键，对应 config/help/guides.js 的注册键，如 graduation.gd-batches */
    guideKey: { type: String, required: true }
  },
  data() {
    return { open: false, unsubscribe: null }
  },
  computed: {
    guide() { return getGuide(this.guideKey) },
    steps() { return this.guide ? this.guide.steps : [] }
  },
  mounted() {
    this.unsubscribe = onGuideReplay(this.replay)
    this.autoOpenIfUnseen()
  },
  unmounted() {
    if (this.unsubscribe) this.unsubscribe()
  },
  methods: {
    /** 首次进入且未看过当前版本时自动弹。 */
    async autoOpenIfUnseen() {
      if (!this.steps.length) return
      const key = guidePrefKey(this.guideKey)
      try {
        const d = await request('/me/preferences', { params: { keys: key } })
        const seenVersion = (d.items || {})[key]
        if (seenVersion !== String(this.guide.version)) this.open = true
      } catch {
        // 读不到偏好就不弹，避免后端异常时反复骚扰；用户仍可从顶栏「?」手动重看。
      }
    },
    /** 顶栏「重看本页引导」触发：无论看没看过都弹。 */
    replay() {
      if (this.steps.length) this.open = true
    },
    /** 看完或跳过都算「已看过」——跳过是老师的明确选择，不该下次再弹。 */
    async markSeen() {
      const key = guidePrefKey(this.guideKey)
      try {
        await request('/me/preferences', {
          method: 'POST',
          body: { key, value: String(this.guide.version) }
        })
      } catch {
        // 存不上只影响「下次还会弹」，不打断当前操作，不给老师报错。
      }
    }
  }
}
</script>
