<template>
  <BasePortalLayout title="组件开发预览" subtitle="基础能力验证" :menus="[]" active-key="">
    <section class="dev-section">
      <h1>基础能力验证</h1>
      <p>状态语义、数据安全、全局反馈与关键操作组件（非商业首页内容）</p>

      <div class="verification-block">
        <h3>状态与风险语义</h3>
        <div class="tag-row">
          <AppStatusTag v-for="s in statuses" :key="s" :status="s" :dot="s === 'REVIEWING'" />
          <AppRiskTag v-for="r in riskLevels" :key="r" :level="r" />
        </div>
      </div>

      <div class="verification-grid">
        <div class="verification-block">
          <h3>敏感信息保护</h3>
          <div class="data-list">
            <div>
              <span>手机号码</span><AppSensitiveText type="phone" value="13512346867" revealable />
            </div>
            <div>
              <span>身份证号</span
              ><AppSensitiveText type="idcard" value="430102200601011234" revealable />
            </div>
            <div>
              <span>学生姓名</span
              ><AppSensitiveText type="name" value="示例姓名" code="S2026-000001" />
            </div>
          </div>
        </div>
        <div class="verification-block">
          <h3>关键操作确认</h3>
          <AppInlineAlert
            type="warning"
            title="材料需要补充"
            description="材料页码不完整，请补充后重新提交。"
          >
            <template #actions
              ><button class="dev-btn dev-btn--primary" @click="showReturn = true">
                发起退回
              </button></template
            >
          </AppInlineAlert>
        </div>
      </div>

      <div class="verification-block">
        <h3>全局状态</h3>
        <div class="tag-row">
          <button
            v-for="s in globalStates"
            :key="s"
            class="dev-chip"
            :class="{ 'is-active': currentState === s }"
            @click="currentState = s"
          >
            {{ s }}
          </button>
        </div>
        <AppGlobalState :state="currentState" error-code="DEMO_500" @retry="currentState = 'ready'">
          <div class="ready-state">业务内容已就绪，默认插槽渲染正常。</div>
        </AppGlobalState>
      </div>

      <p class="dev-back"><router-link to="/">← 返回产品概览首页</router-link></p>
    </section>

    <AppConfirmDialog
      v-model:visible="showReturn"
      type="warning"
      title="确认退回"
      message="退回后将生成学生待办和消息，学生修改后可重新提交。"
      confirm-text="确认退回"
      require-reason
      reason-label="退回原因"
      show-notify
      @confirm="showReturn = false"
    />
  </BasePortalLayout>
</template>

<script>
import {
  AppStatusTag,
  AppRiskTag,
  AppGlobalState,
  AppSensitiveText,
  AppConfirmDialog,
  AppInlineAlert
} from '@/components/common'
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'

export default {
  name: 'ComponentDevPreview',
  components: {
    BasePortalLayout,
    AppStatusTag,
    AppRiskTag,
    AppGlobalState,
    AppSensitiveText,
    AppConfirmDialog,
    AppInlineAlert
  },
  data() {
    return {
      showReturn: false,
      currentState: 'ready',
      statuses: [
        'DRAFT',
        'PENDING_REVIEW',
        'REVIEWING',
        'APPROVED',
        'RETURNED',
        'REJECTED',
        'OVERDUE',
        'ARCHIVED',
        'READONLY'
      ],
      riskLevels: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
      globalStates: [
        'ready',
        'loading',
        'empty',
        'error',
        'forbidden',
        'offline',
        'readonly',
        'noLicense'
      ]
    }
  }
}
</script>

<style scoped>
.dev-section {
  max-width: 960px;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.dev-section h1 {
  margin: 0;
  font-size: var(--font-size-xl);
}
.dev-section > p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.verification-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}
.verification-block {
  padding: var(--space-5);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-card-sm);
  background: var(--bg-card);
  box-shadow: var(--shadow-card);
}
.verification-block h3 {
  margin: 0 0 var(--space-4);
  font-size: var(--font-size-base);
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.data-list {
  display: grid;
  gap: var(--space-3);
}
.data-list div {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.ready-state {
  padding: var(--space-6);
  border: 1px dashed var(--border-base);
  border-radius: var(--radius-md);
  text-align: center;
  color: var(--text-secondary);
}
.dev-btn {
  height: 36px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-base);
  cursor: pointer;
}
.dev-btn--primary {
  background: var(--primary-600);
  color: #fff;
  border-color: var(--primary-600);
}
.dev-chip {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  cursor: pointer;
  font-size: var(--font-size-xs);
}
.dev-chip.is-active {
  border-color: var(--primary-100);
  background: var(--primary-50);
  color: var(--primary-700);
}
.dev-back {
  margin-top: var(--space-4);
  font-size: var(--font-size-sm);
}
.dev-back a {
  color: var(--primary-600);
  text-decoration: none;
}
@media (max-width: 760px) {
  .verification-grid {
    grid-template-columns: 1fr;
  }
}
</style>
