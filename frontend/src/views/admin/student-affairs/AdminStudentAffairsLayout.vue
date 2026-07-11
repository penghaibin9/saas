<template>
  <div class="sa-layout">
    <nav class="sa-layout__tabs" aria-label="学工中心 B 包主线">
      <RouterLink v-for="item in tabs" :key="item.path" :to="item.path" class="sa-layout__tab">
        {{ item.label }}
      </RouterLink>
    </nav>
    <RouterView />
  </div>
</template>

<script>
export default {
  name: 'AdminStudentAffairsLayout',
  data() {
    return {
      // 班级/请假已由 master 上的正式模块承接（/admin/campus-service/classes、/leave 系列），此处不重复
      tabs: [
        { label: '学工看板', path: '/admin/student-affairs/dashboard' },
        { label: '学生画像', path: '/admin/student-affairs/profile' },
        { label: '宿舍管理', path: '/admin/student-affairs/dormitory' },
        { label: '风险预警', path: '/admin/student-affairs/risk' }
      ]
    }
  }
}
</script>

<style scoped>
.sa-layout {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.sa-layout__tabs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: var(--space-2);
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card-sm);
}
.sa-layout__tab {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-base);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: var(--font-size-sm);
}
.sa-layout__tab.router-link-active {
  color: var(--primary-700);
  background: var(--primary-50);
  font-weight: var(--font-weight-semibold);
}
</style>

