<template>
  <div v-if="state && state.active" class="cfn" role="alert">
    <div class="cfn__head">
      <span class="cfn__icon">!</span>
      <span class="cfn__title">{{ state.message }}</span>
    </div>
    <p v-if="state.detail" class="cfn__detail">服务端说明：{{ state.detail }}</p>
    <ul v-if="state.latest && state.latest.length" class="cfn__latest">
      <li v-for="item in state.latest" :key="item.label">
        <span class="cfn__label">{{ item.label }}</span>
        <span class="cfn__value">{{ item.value === '' || item.value == null ? '—' : item.value }}</span>
      </li>
    </ul>
    <p v-if="state.stale" class="cfn__stale">最新状态没拉回来，请关闭后手动刷新页面再确认，别照着当前这份旧数据提交。</p>
    <template v-if="state.kept">
      <p class="cfn__foot">这条已经被别人办完，按钮不会再出现。下面是你刚才写的内容，需要的话先复制走：</p>
      <textarea class="cfn__kept" readonly rows="4" :value="state.kept" @focus="$event.target.select()"></textarea>
    </template>
    <p v-else class="cfn__foot">你填的内容已保留。确认要按最新状态继续，就再点一次下面的按钮；不想继续就取消。</p>
  </div>
</template>

<script>
/**
 * ConflictNotice — 写冲突提示条（岗位实习模块内部组件）。
 *
 * 放在 AppConfirmDialog 默认插槽或抽屉表单顶部，配合
 * `@/modules/internship/composables/conflictGuard` 使用：
 *   <AppConfirmDialog ... @confirm="onConfirm">
 *     <ConflictNotice :state="conflict" />
 *   </AppConfirmDialog>
 *
 * 它只负责「把最新真值摆出来」，不带任何自动重试按钮——重新提交必须是老师
 * 自己再点一次确认，页面不能替他决定。
 */
export default {
  name: 'ConflictNotice',
  props: {
    /** conflictGuard.captureConflict() 的返回值；emptyConflict() 时不渲染 */
    state: { type: Object, default: null }
  }
}
</script>

<style scoped>
.cfn {
  margin-bottom: var(--space-3, 12px);
  padding: var(--space-3, 12px);
  border: 1px solid var(--warning-300, #fcd34d);
  border-radius: var(--radius-base, 6px);
  background: var(--warning-50, #fffbeb);
}
.cfn__head {
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
}
.cfn__icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  border-radius: var(--radius-full, 999px);
  background: var(--warning-600, #d97706);
  color: var(--text-inverse, #fff);
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cfn__title {
  font-size: var(--font-size-base, 14px);
  font-weight: var(--font-weight-semibold, 600);
  color: var(--warning-700, #b45309);
  line-height: 1.4;
}
.cfn__detail,
.cfn__stale,
.cfn__foot {
  margin: var(--space-2, 8px) 0 0;
  font-size: var(--font-size-sm, 13px);
  line-height: 1.5;
  color: var(--text-secondary, #4b5563);
}
.cfn__stale {
  color: var(--danger-600, #dc2626);
}
.cfn__latest {
  margin: var(--space-2, 8px) 0 0;
  padding: 0;
  list-style: none;
}
.cfn__latest li {
  display: flex;
  gap: var(--space-2, 8px);
  padding: 2px 0;
  font-size: var(--font-size-sm, 13px);
}
.cfn__label {
  flex-shrink: 0;
  min-width: 5.5em;
  color: var(--text-tertiary, #6b7280);
}
.cfn__kept {
  width: 100%;
  box-sizing: border-box;
  margin-top: var(--space-1, 4px);
  padding: var(--space-2, 8px);
  border: 1px solid var(--warning-300, #fcd34d);
  border-radius: var(--radius-base, 6px);
  background: var(--bg-card, #fff);
  color: var(--text-primary, #111827);
  font: inherit;
  font-size: var(--font-size-sm, 13px);
  line-height: 1.6;
  resize: vertical;
}
.cfn__value {
  color: var(--text-primary, #111827);
  font-weight: var(--font-weight-medium, 500);
  word-break: break-all;
}
</style>
