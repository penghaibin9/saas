<template>
  <div class="gd-student-closure">
    <router-link class="frozen-package-entry" to="/graduation/evidence-package"><span>冻结证据包</span><strong>查看归档时固定的材料与业务快照 →</strong></router-link>
    <GraduationFeedbackResubmitView />
    <GraduationWorkbenchView />
  </div>
</template>

<script setup>
import GraduationFeedbackResubmitView from './GraduationFeedbackResubmitView.vue'
import GraduationWorkbenchView from './GraduationWorkbenchView.vue'
</script>

<style scoped>
.gd-student-closure{display:grid;gap:0}.frozen-package-entry{display:flex;align-items:center;justify-content:space-between;gap:18px;margin:18px 24px 0;padding:16px 18px;border:1px solid #cfe0f5;border-radius:13px;background:#f3f8ff;color:#1769e0;text-decoration:none}.frozen-package-entry span{font-weight:800}.frozen-package-entry strong{font-size:13px}@media(max-width:700px){.frozen-package-entry{align-items:flex-start;flex-direction:column}}
</style>
