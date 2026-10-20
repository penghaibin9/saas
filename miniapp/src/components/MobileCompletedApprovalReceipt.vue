<template>
  <view class="completed-receipts">
    <view v-for="task in tasks" :key="task.taskId" class="completed-receipt">
      <text class="completed-receipt__title">{{ task.title || task.type || '本人审批记录' }}</text>
      <text class="completed-receipt__meta">业务单号 {{ task.sourceBizId }} · {{ task.actedTime || '处理时间未提供' }}</text>
      <text class="completed-receipt__result">{{ result(task.status) }}</text>
      <text class="completed-receipt__meta">这是本人审批节点的处理回执，整张申请的最新结果以业务记录为准。</text>
    </view>
  </view>
</template>
<script>
export default {
  props: { tasks: { type: Array, default: () => [] } },
  methods: { result(status) { return { APPROVED: '本人已通过', REJECTED: '本人已驳回', RETURNED: '本人已退回', TRANSFERRED: '本人已转交' }[status] || '本人已处理' } }
}
</script>
<style scoped>
.completed-receipts { display: flex; flex-direction: column; gap: 12px; }
.completed-receipt { display: flex; flex-direction: column; gap: 10px; padding: 16px; border-radius: 12px; background: #fff; }
.completed-receipt__title { color: #142440; font-size: 16px; font-weight: 600; line-height: 1.5; }
.completed-receipt__meta { color: #64748b; font-size: 13px; line-height: 1.6; }
.completed-receipt__result { color: #142440; font-size: 15px; line-height: 1.5; }
</style>
