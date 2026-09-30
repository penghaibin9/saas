<template>
  <div class="leave-context">
    <div><span>当前进度</span><strong>{{ detail.currentNodeLabel || detail.affairsStatusLabel }}</strong><small v-if="detail.handler">{{ detail.handler }} 正在处理</small></div>
    <router-link v-if="detail.canManageMaterials" :to="{ path: '/admin/student-affairs/material-operations', query: { bizType: 'LEAVE', bizId: detail.id } }">查看材料 / 要求补交</router-link>
  </div>
</template>
<script>
export default { props: { detail: { type: Object, required: true } } }
</script>
<style scoped>
.leave-context{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 14px;margin:16px 0;background:var(--bg-subtle);border:1px solid var(--border-base);border-radius:8px;font-size:12px}.leave-context>div{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.leave-context span,.leave-context small{color:var(--text-secondary)}.leave-context strong{font-weight:500;color:var(--text-primary)}.leave-context a{color:var(--primary-600);white-space:nowrap}
</style>
