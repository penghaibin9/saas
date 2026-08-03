<template>
  <ModulePageShell
    title="统一消息、待办与通知治理"
    subtitle="投递失败 · 渠道健康 · 重复模板 · 待办积压/逾期 · 无责任人异常队列"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'refresh', label: '刷新' }]" @action="load" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">首屏结论</span></header>
          <div class="mp-card__body cg-summary">
            <div class="cg-stat">
              <span class="cg-stat__num">{{ overview.deliveryFailures?.deadOutbox || 0 }}</span>
              <span class="cg-stat__label">死信事件</span>
            </div>
            <div class="cg-stat">
              <span class="cg-stat__num">{{ overview.deliveryFailures?.notificationFailLast7d || 0 }}</span>
              <span class="cg-stat__label">近7天通知失败</span>
            </div>
            <div class="cg-stat">
              <span class="cg-stat__num">{{ overview.todoBacklog || 0 }}</span>
              <span class="cg-stat__label">积压待办（PENDING）</span>
            </div>
            <div class="cg-stat" :class="{ 'cg-stat--warn': overview.todoOverdue }">
              <span class="cg-stat__num">{{ overview.todoOverdue || 0 }}</span>
              <span class="cg-stat__label">逾期待办</span>
            </div>
            <div class="cg-stat" :class="{ 'cg-stat--warn': (overview.duplicateTemplates || []).length }">
              <span class="cg-stat__num">{{ (overview.duplicateTemplates || []).length }}</span>
              <span class="cg-stat__label">重复模板</span>
            </div>
          </div>
          <div class="mp-card__body cg-channels">
            <span v-for="c in overview.channelHealth || []" :key="c.channel" class="cg-channel">
              <StatusTag :type="c.healthy ? 'success' : 'danger'" :label="`${c.channel}：${c.healthy ? '健康' : '无启用模板'}`" dot />
            </span>
          </div>
          <div v-if="(overview.exceptionQueue?.unownedTodoTypes || []).length" class="mp-card__body">
            <p class="cg-warn">无责任人待办类型（未在注册表登记 ownerModule）：{{ overview.exceptionQueue.unownedTodoTypes.join('、') }}</p>
          </div>
          <div v-if="(overview.exceptionQueue?.unregisteredEventCodesInCode || []).length" class="mp-card__body">
            <p class="cg-warn">代码已支持但治理注册表未登记的事件码：{{ overview.exceptionQueue.unregisteredEventCodesInCode.join('、') }}</p>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">积压待办</span>
            <span class="mp-note">关闭须填写完成证据，写入审计</span>
          </header>
          <div class="mp-card__body">
            <EmptyState v-if="!todos.length" title="暂无积压待办" description="" />
            <DataTable v-else :columns="todoColumns" :rows="todos" row-key="id">
              <template #cell-scope="{ row }">
                <div class="mp-cell-main">{{ row.title }}</div>
                <div class="mp-cell-sub">{{ row.sourceModule }} · {{ row.todoType }}</div>
              </template>
              <template #cell-due="{ row }">
                <span :class="{ 'cg-warn': isOverdue(row.dueAt) }">{{ row.dueAt || '无期限' }}</span>
              </template>
              <template #cell-ops="{ row }">
                <button class="mp-link" @click="askClose(row)">关闭（须填证据）</button>
              </template>
            </DataTable>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">死信事件</span>
            <span class="mp-note">重试只重新入队，不重复触发业务动作（复用 dedupeKey）</span>
          </header>
          <div class="mp-card__body">
            <EmptyState v-if="!deadOutbox.length" title="暂无死信事件" description="" />
            <DataTable v-else :columns="outboxColumns" :rows="deadOutbox" row-key="outboxId">
              <template #cell-scope="{ row }">
                <div class="mp-cell-main">{{ row.eventCode }}</div>
                <div class="mp-cell-sub">{{ row.sourceModule }} · 尝试 {{ row.attemptCount }} 次 · {{ row.lastError }}</div>
              </template>
              <template #cell-ops="{ row }">
                <button class="mp-link" @click="retry(row)">重试</button>
              </template>
            </DataTable>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">注册表（事件 / 待办类型 / 渠道）</span></header>
          <div class="mp-card__body">
            <p class="mp-note">事件码合法性以代码 _EVENT_TEMPLATES 为准；本注册表只登记谁负责与治理元数据。</p>
            <ul class="cg-reg-list">
              <li v-for="e in registry.events || []" :key="e.eventCode">{{ e.eventCode }} — {{ e.ownerModule }}（{{ e.description }}）</li>
            </ul>
          </div>
        </section>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="closeDialogOpen"
      type="warning"
      title="关闭待办"
      :message="`确认关闭待办「${pendingTodo?.title}」？必须填写完成证据。`"
      confirm-text="关闭"
      require-reason
      reason-label="完成证据"
      :submitting="submitting"
      @confirm="submitClose"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemCommunicationGovernanceView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      overview: {},
      registry: {},
      todos: [],
      deadOutbox: [],
      closeDialogOpen: false,
      submitting: false,
      pendingTodo: null,
      todoColumns: [
        { key: 'scope', title: '待办' },
        { key: 'due', title: '期限' },
        { key: 'ops', title: '操作' }
      ],
      outboxColumns: [
        { key: 'scope', title: '事件' },
        { key: 'ops', title: '操作' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    isOverdue(dueAt) {
      return !!dueAt && new Date(dueAt) < new Date()
    },
    askClose(row) {
      this.pendingTodo = row
      this.closeDialogOpen = true
    },
    async submitClose({ reason }) {
      if (!reason || reason.trim().length < 2) return toast.error('请填写完成证据')
      this.submitting = true
      const res = await systemApi.closeTodoWithEvidence(this.pendingTodo.id, { evidence: reason })
      this.submitting = false
      if (res.code === 0) {
        toast.success('待办已关闭')
        this.closeDialogOpen = false
        this.pendingTodo = null
        await this.load()
      } else {
        toast.error(res.message)
      }
    },
    async retry(row) {
      const res = await systemApi.retryDeadOutbox(row.outboxId)
      if (res.code === 0) {
        toast.success('已重新入队')
        await this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const [overview, registry, todos, deadOutbox] = await Promise.all([
        systemApi.getCommunicationGovernanceOverview(),
        systemApi.getCommunicationRegistry(),
        systemApi.listTodoBacklog({ pageSize: 20 }),
        systemApi.listDeadOutbox({ pageSize: 20 })
      ])
      if (overview.code === 0) this.overview = overview.data || {}
      else this.error = overview.message
      if (registry.code === 0) this.registry = registry.data || {}
      if (todos.code === 0) this.todos = todos.data.items || []
      if (deadOutbox.code === 0) this.deadOutbox = deadOutbox.data.items || []
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.cg-summary { display: flex; flex-wrap: wrap; gap: var(--space-4); }
.cg-stat {
  min-width: 150px;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}
.cg-stat--warn { border-color: var(--color-danger); }
.cg-stat__num { display: block; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.cg-stat__label { display: block; color: var(--text-secondary); font-size: var(--font-size-xs); }
.cg-channels { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.cg-warn { color: var(--color-danger); margin: 2px 0; }
.cg-reg-list { margin: 0; padding-left: 1.2em; color: var(--text-secondary); font-size: var(--font-size-sm); }
</style>
