<template>
  <ModulePageShell
    title="业务关系中心"
    subtitle="统一发现关系缺口 · 真实数据仍在各业务模块，本页不改业务终态"
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
          <header class="mp-card__head">
            <span class="mp-card__title">关系注册表</span>
            <span class="mp-note">{{ summary }}</span>
          </header>
          <div class="mp-card__body">
            <DataTable :columns="typeColumns" :rows="types" row-key="relationType">
              <template #cell-relation="{ row }">
                <div class="mp-cell-main">{{ row.label }}</div>
                <div class="mp-cell-sub">{{ row.relationType }}</div>
              </template>
              <template #cell-source="{ row }">
                <div class="mp-cell-sub">{{ row.sourceModel }}.{{ row.subjectField }}</div>
                <div class="mp-cell-sub">范围 {{ row.scopeType || '未登记' }}</div>
              </template>
              <template #cell-health="{ row }">
                <StatusTag :type="row.healthy ? 'success' : 'danger'"
                           :label="row.healthy ? '登记正常' : '登记异常'" dot />
                <div v-for="c in row.checks" :key="c.code" class="mp-cell-sub">
                  <span class="br-tag">{{ c.code }}</span> {{ c.message }}
                </div>
              </template>
              <template #cell-gap="{ row }">
                <template v-if="issueOf(row.relationType)">
                  <div v-if="issueOf(row.relationType).error" class="mp-cell-sub">
                    体检失败：{{ issueOf(row.relationType).error }}
                  </div>
                  <div v-else-if="!gapList(row.relationType).length" class="mp-cell-sub">无缺口</div>
                  <div v-for="i in gapList(row.relationType)" :key="i.code" class="mp-cell-sub">
                    <span class="br-tag br-tag--warn">{{ i.code }}</span> {{ i.count }} 条 · {{ i.message }}
                  </div>
                </template>
                <span v-else class="mp-cell-sub">—</span>
              </template>
              <template #cell-ops="{ row }">
                <button class="mp-link" @click="validateOne(row)">重新校验</button>
              </template>
            </DataTable>
          </div>
        </section>

        <section v-if="detail" class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">{{ detail.registry.label }} · 校验结果</span>
          </header>
          <div class="mp-card__body">
            <p class="mp-note">owner：{{ detail.registry.ownerModule }} ·
              resolver：{{ detail.registry.resolver || '未登记' }} ·
              测试：{{ detail.registry.test }}</p>
            <p v-if="detail.registry.notes" class="mp-note">{{ detail.registry.notes }}</p>
            <p v-if="detail.data.error" class="mp-note">体检失败：{{ detail.data.error }}</p>
            <template v-else>
              <p class="mp-note">
                扫描 {{ detail.data.scanned }} / {{ detail.data.total }} 条
                <span v-if="detail.data.truncated">（超出扫描上限，统计为样本）</span>
              </p>
              <ul class="br-list">
                <li v-for="i in (detail.data.issues || [])" :key="i.code">
                  {{ i.code }}：{{ i.count }} 条 · {{ i.message }}
                  <span class="mp-cell-sub">样例 ID {{ (i.samples || []).map((s) => s.id).join('、') }}</span>
                </li>
              </ul>
              <p v-if="!(detail.data.issues || []).length" class="mp-note">本类型当前没有缺口。</p>
            </template>
          </div>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState } from '@/components/business'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemBusinessRelationView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      types: [],
      issues: [],
      detail: null,
      typeColumns: [
        { key: 'relation', title: '业务关系' },
        { key: 'ownerModule', title: '归属模块' },
        { key: 'source', title: '权威数据位置' },
        { key: 'health', title: '登记校验' },
        { key: 'gap', title: '关系缺口' },
        { key: 'ops', title: '操作' }
      ]
    }
  },
  computed: {
    summary() {
      const bad = this.types.filter((t) => !t.healthy).length
      return `共 ${this.types.length} 种关系，登记异常 ${bad} 种`
    }
  },
  created() { this.load() },
  methods: {
    issueOf(relationType) {
      return this.issues.find((i) => i.relationType === relationType) || null
    },
    gapList(relationType) {
      const row = this.issueOf(relationType)
      return (row && row.issues) || []
    },
    async validateOne(row) {
      const res = await systemApi.validateBusinessRelation(row.relationType)
      if (res.code === 0) this.detail = res.data
      else toast.error(res.message)
    },
    async load() {
      this.loading = true
      this.error = ''
      this.detail = null
      const [types, issues] = await Promise.all([
        systemApi.listBusinessRelationTypes(),
        systemApi.listBusinessRelationIssues()
      ])
      if (types.code === 0) this.types = types.data.list || []
      else this.error = types.message
      if (issues.code === 0) this.issues = issues.data.list || []
      else if (!this.error) this.error = issues.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.br-tag {
  display: inline-block;
  padding: 1px 6px;
  border-radius: var(--radius-sm);
  background: var(--bg-hover);
  font-size: var(--font-size-xs);
}
.br-tag--warn { color: var(--warning-700); background: var(--warning-50); }
.br-list { margin: var(--space-2) 0; padding-left: var(--space-4); }
</style>
