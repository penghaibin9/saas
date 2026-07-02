<template>
  <AppCard class="stu-panel">
    <AppSectionHeader title="联系方式" compact />
    <dl class="stu-kv">
      <dt>手机号</dt><dd>{{ masked.phone || '未登记' }}</dd>
      <dt>邮箱</dt><dd>{{ masked.email || '—' }}</dd>
      <dt>在校住址</dt><dd>{{ student.currentAddress || '—' }}</dd>
    </dl>
  </AppCard>
</template>

<script>
/** StudentContactPanel — 联系方式（手机号/邮箱脱敏） */
import { AppCard, AppSectionHeader } from '@/components/ui'
import { maskStudentForDisplay } from '../helpers/student-security.helper'

export default {
  name: 'StudentContactPanel',
  components: { AppCard, AppSectionHeader },
  props: { student: { type: Object, required: true } },
  computed: {
    masked() {
      return maskStudentForDisplay(this.student)
    }
  }
}
</script>

<style scoped>
@import './student-panel.css';
</style>
