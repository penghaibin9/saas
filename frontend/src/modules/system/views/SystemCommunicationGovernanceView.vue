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
              <span class="cg-stat__label">积压待办</span>
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
              <StatusTag :type="c.enabledTemplateCount > 0 ? 'info' : 'warning'" :label="`${channelLabel(c.channel)}：${c.enabledTemplateCount > 0 ? '已启用模板，投递能力未验证' : '未启用模板'}`" dot />
            </span>
          </div>
          <div v-if="(overview.exceptionQueue?.unownedTodoTypes || []).length" class="mp-card__body">
            <p class="cg-warn">{{ overview.exceptionQueue.unownedTodoTypes.length }} 类待办尚未登记所属模块，需要实施人员核对来源。</p>
            <details><summary>实施人员使用：待办类型标识</summary>{{ overview.exceptionQueue.unownedTodoTypes.join('、') }}</details>
          </div>
          <div v-if="(overview.exceptionQueue?.unregisteredEventCodesInCode || []).length" class="mp-card__body">
            <p class="cg-warn">{{ overview.exceptionQueue.unregisteredEventCodesInCode.length }} 类系统事件尚未登记治理目录；这不等于消息投递失败。</p>
            <details><summary>实施人员使用：事件标识</summary>{{ overview.exceptionQueue.unregisteredEventCodesInCode.join('、') }}</details>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">积压待办</span>
            <span class="mp-note">仅修复来源业务已完成或已撤销的失效提醒</span>
          </header>
          <div class="mp-card__body">
            <EmptyState v-if="!todos.length" title="暂无积压待办" description="" />
            <DataTable v-else :columns="todoColumns" :rows="todos" row-key="id">
              <template #cell-scope="{ row }">
                <div class="mp-cell-main">{{ row.title }}</div>
                <div class="mp-cell-sub">{{ moduleLabel(row.sourceModule) }} · 业务记录 {{ row.sourceBizId }} · 版本 {{ row.version }}</div>
                <details><summary>实施人员使用：来源标识</summary>{{ row.sourceModule }} · {{ row.sourceBizType }} · {{ row.todoType }}</details>
              </template>
              <template #cell-due="{ row }">
                <span :class="{ 'cg-warn': isOverdue(row.dueAt) }">{{ row.dueAt || '无期限' }}</span>
              </template>
              <template #cell-ops="{ row }">
                <button class="mp-link" :disabled="submitting || !canManage" @click="askClose(row)">核验并关闭提醒</button>
              </template>
            </DataTable>
            <div class="cg-pages"><span>共 {{ todoTotal }} 项 · 第 {{ todoPage }} 页</span><button class="mp-btn" :disabled="loading || todoPage <= 1" @click="changePage('todo', -1)">上一页待办</button><button class="mp-btn" :disabled="loading || todoPage * 20 >= todoTotal" @click="changePage('todo', 1)">下一页待办</button></div>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">死信事件</span>
            <span class="mp-note">重试只重新排队，不会重复触发业务操作</span>
          </header>
          <div class="mp-card__body">
            <EmptyState v-if="!deadOutbox.length" title="暂无死信事件" description="" />
            <DataTable v-else :columns="outboxColumns" :rows="deadOutbox" row-key="outboxId">
              <template #cell-scope="{ row }">
                <div class="mp-cell-main">{{ eventLabel(row.eventCode) }}</div>
                <div class="mp-cell-sub">{{ moduleLabel(row.sourceModule) }} · 已尝试 {{ row.attemptCount }} 次 · 投递失败</div>
                <details><summary>实施人员使用：投递诊断</summary>事件：{{ row.eventCode }}；错误标识：{{ row.lastError || '未记录' }}</details>
              </template>
              <template #cell-ops="{ row }">
                <button class="mp-link" :disabled="!!retryingId || !canManage" @click="retry(row)">{{ retryingId === row.outboxId ? '正在重新排队' : '重试投递' }}</button>
              </template>
            </DataTable>
            <div class="cg-pages"><span>共 {{ outboxTotal }} 项 · 第 {{ outboxPage }} 页</span><button class="mp-btn" :disabled="loading || outboxPage <= 1" @click="changePage('outbox', -1)">上一页投递</button><button class="mp-btn" :disabled="loading || outboxPage * 20 >= outboxTotal" @click="changePage('outbox', 1)">下一页投递</button></div>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">登记表（事件 / 待办类型 / 渠道）</span></header>
          <div class="mp-card__body">
            <p class="mp-note">事件是否合法以系统为准；本登记表只登记谁负责与治理信息。</p>
            <ul class="cg-reg-list">
              <li v-for="e in registry.events || []" :key="e.eventCode">{{ e.description || '事件名称待登记' }} · {{ moduleLabel(e.ownerModule) }}<details><summary>实施人员使用：事件标识</summary>{{ e.eventCode }}</details></li>
            </ul>
          </div>
        </section>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="closeDialogOpen"
      type="warning"
      title="关闭待办"
      :message="`核验待办「${pendingTodo?.title}」第${pendingTodo?.version}版：系统将重新检查来源业务是否完成或撤销。文字说明不能代替业务结果，不会修改原业务。`"
      confirm-text="关闭"
      require-reason
      reason-label="完成证据"
      :submitting="submitting"
      @confirm="submitClose"
    ><p v-if="closeError" role="alert" class="cg-warn">{{ closeError }}</p></AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { matchPermission } from '@/config/navPlan'
import { contextFingerprint } from '@/modules/system/utils/workspaceContract'
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
      todoPage: 1, todoTotal: 0, outboxPage: 1, outboxTotal: 0,
      closeDialogOpen: false,
      submitting: false,
      retryingId: '', loadSequence: 0,
      pendingTodo: null,
      closeError: '',
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
  computed: {
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'systemAdmin.communication.manage') },
    contextKey() { return contextFingerprint(this.ctx) }
  },
  created() { this.load() },
  watch: { contextKey() { this.loadSequence++; this.todoPage = 1; this.outboxPage = 1; this.todos = []; this.deadOutbox = []; this.closeDialogOpen = false; this.pendingTodo = null; this.load() } },
  beforeUnmount() { this.loadSequence++ },
  methods: {
    moduleLabel(code) { return { 'student-affairs': '学工', studentAffairs: '学工', student: '学工', academic: '教务', 'academic-affairs': '教务', graduation: '毕业设计', internship: '岗位实习', system: '系统管理' }[code] || '来源模块待核对' },
    changePage(kind, step) { if (this.loading || !['todo', 'outbox'].includes(kind)) return; const page = this[`${kind}Page`] + step; if (page < 1 || (page - 1) * 20 >= this[`${kind}Total`]) return; this[`${kind}Page`] = page; this.load() },
    eventLabel(code) { return (this.registry.events || []).find(item => item.eventCode === code)?.description || '事件名称待登记' },
    channelLabel(code) { return { SMS: '短信', WECHAT: '微信', EMAIL: '电子邮件', IN_APP: '站内消息' }[code] || '其他通知渠道' },
    isOverdue(dueAt) {
      return !!dueAt && new Date(dueAt) < new Date()
    },
    askClose(row) {
      if (!this.canManage || this.submitting || !Number.isInteger(row.version)) return
      this.pendingTodo = row
      this.closeError = ''
      this.closeDialogOpen = true
    },
    async submitClose({ reason }) {
      if (!this.canManage || this.submitting || !this.pendingTodo) return
      if (!reason || reason.trim().length < 2) return toast.error('请填写完成证据')
      this.submitting = true
      this.closeError = ''
      const context = this.contextKey
      const res = await systemApi.closeTodoWithEvidence(this.pendingTodo.id, { evidence: reason, expectedVersion: this.pendingTodo.version })
      this.submitting = false
      if (context !== this.contextKey) return
      if (res.code === 0) {
        toast.success('待办已关闭')
        this.closeDialogOpen = false
        this.pendingTodo = null
        await this.load()
      } else {
        this.closeError = res.message
        toast.error(res.message)
      }
    },
    async retry(row) {
      if (!this.canManage || this.retryingId) return
      const context = this.contextKey
      this.retryingId = row.outboxId
      const res = await systemApi.retryDeadOutbox(row.outboxId)
      this.retryingId = ''
      if (context !== this.contextKey) return
      if (res.code === 0) {
        toast.success('已重新入队')
        await this.load()
      } else {
        toast.error(res.message)
      }
    },
    async load() {
      const sequence = ++this.loadSequence
      this.loading = true
      this.error = ''
      const [overview, registry, todos, deadOutbox] = await Promise.all([
        systemApi.getCommunicationGovernanceOverview(),
        systemApi.getCommunicationRegistry(),
        systemApi.listTodoBacklog({ page: this.todoPage, pageSize: 20 }),
        systemApi.listDeadOutbox({ page: this.outboxPage, pageSize: 20 })
      ])
      if (sequence !== this.loadSequence) return
      this.todoTotal = todos.data?.total || 0
      this.outboxTotal = deadOutbox.data?.total || 0
      const failed = [overview, registry, todos, deadOutbox].find(result => result.code !== 0)
      if (failed || !Array.isArray(todos.data?.items) || !Array.isArray(deadOutbox.data?.items)) {
        this.error = failed?.message || '治理数据返回不完整'
        this.todos = []; this.deadOutbox = []; this.overview = {}; this.registry = {}; this.loading = false
        return
      }
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
.cg-pages { display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-top:16px; }
.cg-warn { color: var(--color-danger); margin: 2px 0; }
.cg-reg-list { margin: 0; padding-left: 1.2em; color: var(--text-secondary); font-size: var(--font-size-sm); }
</style>
