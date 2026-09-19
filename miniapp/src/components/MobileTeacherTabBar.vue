<template><MobileTabBar side="teacher" :active="active" :badges="{ workbench: pending === null ? pendingCount : pending, message: unread === null ? unreadCount : unread }" /></template>
<script>
import { teacherTodoT8Api } from '@/services/teacherTodoT8Api'
import { getTeacherMessageBadges } from '@/services/teacherMessagesV3Api'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
export default {
  props: { active: String, pending: { type: Number, default: null }, unread: { type: Number, default: null } },
  data: () => ({ pendingCount: null, unreadCount: null, epoch: 0 }),
  mounted() { this.refresh() },
  beforeUnmount() { this.epoch++ },
  methods: {
    invalidate() { this.epoch++; this.pendingCount = null; this.unreadCount = null },
    refresh() {
      const epoch = ++this.epoch, generation = currentSessionGeneration()
      const current = () => epoch === this.epoch && generation === currentSessionGeneration()
      if (this.pending === null) teacherTodoT8Api.list({ pageSize: 1 }).then(data => {
        if (current()) this.pendingCount = data.pendingCount ?? null
      }).catch(() => { if (current()) this.pendingCount = null })
      if (this.unread === null) getTeacherMessageBadges().then(data => {
        if (current()) this.unreadCount = data.badges ? Object.values(data.badges).reduce((sum, value) => sum + (Number(value) || 0), 0) : null
      }).catch(() => { if (current()) this.unreadCount = null })
    }
  }
}
</script>
