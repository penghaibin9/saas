<template>
  <AppRiskStudentCard
    :name="student.name"
    :student-no="student.studentNo"
    :college="student.college"
    :major="student.major"
    :class-name="student.className"
    :stage="student.currentStage || student.stage"
    :risk-level="student.riskLevel"
    :risk-reason="student.lastActivity"
    @contact="$emit('contact')"
    @remind="$emit('remind')"
    @follow="$emit('follow')"
    @resolve="$emit('resolve')"
  />
</template>

<script>
import AppRiskStudentCard from './AppRiskStudentCard.vue'

export default {
  name: 'StudentRiskCard',
  components: { AppRiskStudentCard },
  props: {
    student: { type: Object, required: true }
  },
  emits: ['contact', 'remind', 'follow', 'resolve']
}
</script>
