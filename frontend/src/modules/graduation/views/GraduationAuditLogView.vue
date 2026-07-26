<template>
  <ModulePageShell
    title="毕设操作日志"
    subtitle="毕业设计域审计留痕（只读，按时间倒序）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="mp-toolbar-row">
        <input v-model.trim="keyword" class="mp-inp" placeholder="关键词（动作 / 详情）" @keyup.enter="search" />
        <input v-model.trim="bizType" class="mp-inp" placeholder="业务类型（可选）" @keyup.enter="search" />
        <button type="button" class="mp-btn mp-btn--primary" @click="search">查询</button>
        <button type="button" class="mp-btn" @click="reset">重置</button>
      </div>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <DataTable :columns="columns" :rows="rows" row-key="id" />
        <p v-if="!rows.length" class="mp-note">暂无审计记录</p>
        <div class="mp-pager">
          <button type="button" class="mp-link" :disabled="page <= 1" @click="goPage(page - 1)">上一页</button>
          <span>第 {{ page }} 页 · 共 {{ total }} 条</span>
          <button type="button" class="mp-link" :disabled="page * pageSize >= total" @click="goPage(page + 1)">下一页</button>
        </div>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 毕设域操作日志：对接 GET /graduation/audit-logs。 */
import { ModulePageShell, LoadingState, ErrorState, DataTable } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'

export default {
  name: 'GraduationAuditLogView',
  components: { ModulePageShell, LoadingState, ErrorState, DataTable },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], total: 0, page: 1, pageSize: 20,
      keyword: '', bizType: '',
      columns: [
        { key: 'time', title: '时间', width: '160px' },
        { key: 'operator', title: '操作人', width: '100px' },
        { key: 'operatorAccount', title: '操作账号', width: '100px' },
        { key: 'roleName', title: '角色', width: '100px' },
        { key: 'permissionCode', title: '权限码', width: '220px' },
        { key: 'batchId', title: '批次', width: '80px' },
        { key: 'traceId', title: 'TraceId', width: '150px' },
        { key: 'dataScope', title: '数据范围', width: '180px' },
        { key: 'bizType', title: '业务类型', width: '120px' },
        { key: 'action', title: '动作', width: '160px' },
        { key: 'before', title: '变更前', width: '120px' },
        { key: 'after', title: '变更后', width: '120px' },
        { key: 'detail', title: '详情' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getAuditLogs({
        page: this.page, pageSize: this.pageSize,
        keyword: this.keyword || undefined,
        bizType: this.bizType || undefined
      })
      if (res.code === 0) {
        this.rows = res.data.list || []
        this.total = res.data.total || 0
      } else {
        this.error = res.message || '审计日志加载失败'
        this.rows = []
        this.total = 0
      }
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.keyword = ''; this.bizType = ''; this.page = 1; this.load() },
    goPage(p) { this.page = p; this.load() }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-toolbar-row { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; }
.mp-inp { min-width: 180px; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; }
.mp-btn { padding: 7px 14px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-pager { display: flex; align-items: center; gap: var(--space-3); margin-top: var(--space-3); font-size: 13px; color: var(--t2, #475569); }
</style>
