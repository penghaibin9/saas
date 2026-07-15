<template>
  <aside class="aibn" role="note" aria-label="账号创建边界说明">
    <div>
      <strong>此处不会创建登录账号</strong>
      <span>这里只导入当前业务数据或名单。老师、学生尚无账号时，请先到系统管理统一批量创建。</span>
    </div>
    <RouterLink class="aibn__link" to="/admin/system/identity-import">前往“导入老师和学生”</RouterLink>
  </aside>
</template>

<script>
export default { name: 'AccountImportBoundaryNotice' }
</script>

<style scoped>
.aibn {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--warning-200, #fde68a);
  border-radius: var(--radius-base);
  background: var(--warning-50, #fffbeb);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-base);
}
.aibn strong {
  display: block;
  margin-bottom: 2px;
  color: var(--text-primary);
}
.aibn span {
  display: block;
}
.aibn__link {
  flex: none;
  color: var(--primary-600);
  font-weight: var(--font-weight-medium);
  text-decoration: none;
  white-space: nowrap;
}
.aibn__link:hover {
  text-decoration: underline;
}
@media (max-width: 640px) {
  .aibn {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
