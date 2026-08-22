<template>
  <div class="gd-student-closure">
    <GraduationFeedbackResubmitView />
    <GraduationWorkbenchView />
  </div>
</template>

<script setup>
import GraduationFeedbackResubmitView from './GraduationFeedbackResubmitView.vue'
import GraduationWorkbenchView from './GraduationWorkbenchView.vue'
</script>

<style scoped>
.gd-student-closure{display:grid;gap:0}
</style>
