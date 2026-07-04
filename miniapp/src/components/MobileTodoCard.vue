<template>
  <view class="mobile-todo-card" :class="{ 'is-overdue': overdue }" @click="$emit('view')">
    <view class="mtc-head">
      <text class="mtc-title">{{ title }}</text>
      <MobileStatusTag v-if="status" :status="status" />
    </view>
    <view class="mtc-meta">
      <text v-if="sourceModule" class="mtc-module">{{ sourceModule }}</text>
      <text v-if="studentName" class="mtc-meta-item">{{ studentName }}</text>
      <text v-if="deadline" class="mtc-meta-item" :class="{ 'is-overdue-text': overdue }">
        截止 {{ deadline }}
      </text>
    </view>
    <view v-if="returnReason" class="mtc-return">
      <text class="mtc-return__badge">已退回</text>
      <text class="mtc-return__reason">{{ returnReason }}</text>
    </view>
    <view class="mtc-actions" @click.stop>
      <slot name="actions">
        <button class="mtc-btn" @click="$emit('handle')">{{ actionText }}</button>
      </slot>
    </view>
  </view>
</template>

<script>
import MobileStatusTag from './MobileStatusTag.vue'

/**
 * MobileTodoCard 移动端待办卡片
 * 依据 V2.1 §11.4：被退回待办必须显示警告气泡 + 退回原因摘要 + 去修改按钮。
 * Props: title、sourceModule、studentName、deadline、status（状态码）、
 *        overdue、returnReason（退回原因摘要，有值时显示退回气泡）、actionText
 * Emits: view（点卡片）、handle（点操作按钮）
 * Slots: actions
 */
export default {
  name: 'MobileTodoCard',
  components: { MobileStatusTag },
  props: {
    title: { type: String, required: true },
    sourceModule: { type: String, default: '' },
    studentName: { type: String, default: '' },
    deadline: { type: String, default: '' },
    status: { type: String, default: '' },
    overdue: { type: Boolean, default: false },
    returnReason: { type: String, default: '' },
    actionText: { type: String, default: '去处理' }
  },
  emits: ['view', 'handle']
}
</script>

<style scoped>
.mobile-todo-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--card-padding-mobile);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.mobile-todo-card.is-overdue { border: 1px solid var(--danger-100); }
.mtc-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.mtc-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mtc-meta { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.mtc-module { font-size: var(--font-size-sm); color: var(--primary-600); }
.mtc-meta-item { font-size: var(--font-size-sm); color: var(--text-secondary); }
.mtc-meta-item.is-overdue-text { color: var(--danger-600); }
.mtc-return {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  background: var(--danger-50);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
}
.mtc-return__badge {
  font-size: var(--font-size-xs);
  color: var(--text-inverse);
  background: var(--danger-500);
  border-radius: var(--radius-sm);
  padding: 1px var(--space-1);
  flex-shrink: 0;
}
.mtc-return__reason { font-size: var(--font-size-sm); color: var(--danger-700); }
.mtc-actions { display: flex; justify-content: flex-end; gap: var(--space-2); }
.mtc-btn {
  min-height: 36px;
  line-height: 36px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid var(--primary-600);
  background: var(--bg-card);
  color: var(--primary-600);
  font-size: var(--font-size-base);
}
</style>
