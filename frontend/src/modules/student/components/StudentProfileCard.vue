<template>
  <AppCard class="stu-profile-card" hoverable @click="$emit('view', student)">
    <div class="stu-profile-card__avatar">{{ (student.name || '生').slice(0, 1) }}</div>
    <div class="stu-profile-card__body">
      <div class="stu-profile-card__row">
        <span class="stu-profile-card__name">{{ student.name }}</span>
        <span class="stu-profile-card__no">{{ student.studentNo }}</span>
        <StudentStatusTag :status="student.studentStatus" />
      </div>
      <div class="stu-profile-card__org">{{ org }}</div>
      <StudentRiskFlag :flags="student.riskFlags" />
    </div>
    <div class="stu-profile-card__actions" @click.stop>
      <slot name="actions" />
    </div>
  </AppCard>
</template>

<script>
/** StudentProfileCard — 学生卡片（头像/姓名/学号/状态/归属/风险） */
import { AppCard } from '@/components/ui'
import StudentStatusTag from './StudentStatusTag.vue'
import StudentRiskFlag from './StudentRiskFlag.vue'
import { formatOrg } from '../helpers/student-format.helper'

export default {
  name: 'StudentProfileCard',
  components: { AppCard, StudentStatusTag, StudentRiskFlag },
  props: { student: { type: Object, required: true } },
  emits: ['view'],
  computed: {
    org() {
      return formatOrg(this.student)
    }
  }
}
</script>

<style scoped>
.stu-profile-card { display: flex; align-items: flex-start; gap: var(--space-3); padding: var(--space-4); cursor: pointer; }
.stu-profile-card__avatar {
  width: 40px; height: 40px; flex-shrink: 0;
  border-radius: var(--radius-full);
  background: var(--primary-50);
  color: var(--primary-600);
  display: flex; align-items: center; justify-content: center;
  font-weight: var(--font-weight-semibold);
}
.stu-profile-card__body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: var(--space-1); }
.stu-profile-card__row { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.stu-profile-card__name { font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.stu-profile-card__no { font-size: var(--font-size-sm); color: var(--text-tertiary); font-variant-numeric: var(--font-numeric); }
.stu-profile-card__org { font-size: var(--font-size-sm); color: var(--text-secondary); }
.stu-profile-card__actions { flex-shrink: 0; display: flex; gap: var(--space-2); }
</style>
