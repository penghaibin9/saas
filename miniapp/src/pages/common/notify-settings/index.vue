<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="消息通知设置" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="loaded">
        <text class="t-sm t-tertiary">关闭后，对应分类的消息将不再出现在你的消息中心。</text>
        <view class="list-group" style="margin-top: var(--space-3);">
          <view v-for="it in items" :key="it.key" class="list-row">
            <text class="flex-1 t-md">{{ it.label }}</text>
            <switch :checked="it.enabled" color="var(--brand-primary)" @change="toggle(it, $event)" />
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { studentApi } from '@/services/studentApi'
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

export default {
  data() { return { state: 'loading', loaded: false, items: [], isStudent: true } },
  onLoad() {
    this.isStudent = useSessionStore().side === 'student'
    this.load()
  },
  methods: {
    api() { return this.isStudent ? studentApi : teacherApi },
    load() {
      this.state = 'loading'
      this.api().getNotifyPreferences().then((d) => {
        this.items = (d && d.items) || []
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
    }
  }
}
</script>
