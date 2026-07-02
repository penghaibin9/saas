<template>
  <AppDrawer :visible="visible" :title="title" @update:visible="$emit('update:visible', $event)">
    <template v-if="payload">
      <div class="handle-drawer__row">
        <span class="handle-drawer__label">学生姓名</span>
        <span class="handle-drawer__value">{{ payload.studentName || '—' }}</span>
      </div>
      <div class="handle-drawer__row">
        <span class="handle-drawer__label">风险类型</span>
        <span class="handle-drawer__value">{{ payload.riskType || '—' }}</span>
      </div>
      <div class="handle-drawer__row handle-drawer__row--block">
        <span class="handle-drawer__label">风险原因</span>
        <p class="handle-drawer__reason">{{ payload.riskReason || '—' }}</p>
      </div>
      <div class="handle-drawer__row">
        <span class="handle-drawer__label">责任老师</span>
        <span class="handle-drawer__value">{{ payload.responsibleTeacher || '—' }}</span>
      </div>
      <div class="handle-drawer__row">
        <span class="handle-drawer__label">处理时限</span>
        <span class="handle-drawer__value">{{ payload.deadline || '—' }}</span>
      </div>
      <div class="handle-drawer__row">
        <span class="handle-drawer__label">当前状态</span>
        <AppStatusTag :status="displayStatus" />
      </div>
      <div v-if="payload.suggestions?.length" class="handle-drawer__suggestions">
        <div class="handle-drawer__suggestions-title">处理建议</div>
        <ul>
          <li v-for="(s, i) in payload.suggestions" :key="i">{{ s }}</li>
        </ul>
      </div>
    </template>
    <template #footer>
      <AppButton variant="secondary" @click="$emit('contact')">联系学生</AppButton>
      <AppButton variant="secondary" @click="$emit('remind')">发起提醒</AppButton>
      <AppButton variant="secondary" @click="$emit('follow')">填写跟进</AppButton>
      <AppButton variant="primary" @click="$emit('resolve')">标记已处理</AppButton>
    </template>
  </AppDrawer>
</template>

<script>
import AppStatusTag from '../common/AppStatusTag.vue'
import { AppDrawer, AppButton } from '../ui'
import { handleDetailStatusCode } from './presentation.js'

export default {
  name: 'AppHandleDrawer',
  components: { AppStatusTag, AppDrawer, AppButton },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, default: '风险处理' },
    payload: { type: Object, default: null }
  },
  emits: ['update:visible', 'contact', 'remind', 'follow', 'resolve'],
  computed: {
    displayStatus() {
      return handleDetailStatusCode(this.payload?.status)
    }
  }
}
</script>

<style scoped>
.handle-drawer__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  font-size: var(--font-size-sm);
  margin-bottom: var(--space-3);
}
.handle-drawer__row--block {
  flex-direction: column;
  align-items: flex-start;
}
.handle-drawer__label {
  color: var(--text-secondary);
  flex-shrink: 0;
}
.handle-drawer__value {
  color: var(--text-primary);
  font-weight: var(--font-weight-medium);
  text-align: right;
}
.handle-drawer__reason {
  margin: var(--space-1) 0 0;
  padding: var(--space-3);
  width: 100%;
  border-radius: var(--radius-md);
  background: var(--danger-50);
  border: 1px solid var(--danger-100);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  line-height: 1.5;
}
.handle-drawer__suggestions {
  margin-top: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
}
.handle-drawer__suggestions-title {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  color: var(--warning-700);
  margin-bottom: var(--space-1);
}
.handle-drawer__suggestions ul {
  margin: 0;
  padding-left: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  line-height: 1.7;
}
</style>
