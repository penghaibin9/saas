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
            <span class="mp-card__title">关系登记表</span>
            <span class="mp-note">{{ summary }}</span>
          </header>
          <div class="mp-card__body">
            <DataTable :columns="typeColumns" :rows="types" row-key="relationType">
              <template #cell-relation="{ row }">
                <div class="mp-cell-main">{{ row.label }}</div>
                <details><summary>实施人员使用</summary>{{ row.relationType }}</details>
              </template>
              <template #cell-ownerModule="{ row }">{{ moduleLabel(row.ownerModule) }}</template>
              <template #cell-source="{ row }">
                <div class="mp-cell-sub">{{ sourceLabel(row.relationType) }}</div>
                <details><summary>实施人员使用</summary>{{ row.sourceModel }}.{{ row.subjectField }}<p>范围 {{ row.scopeType || '未登记' }}</p></details>
              </template>
              <template #cell-health="{ row }">
                <StatusTag :type="row.healthy ? 'success' : 'danger'"
                           :label="row.healthy ? '登记正常' : '登记异常'" dot />
                <div v-for="c in row.checks" :key="c.code" class="mp-cell-sub">
                  {{ checkLabel(c.code) }}<details><summary>实施人员使用</summary>{{ c.code }}：{{ c.message }}</details>
                </div>
              </template>
              <template #cell-gap="{ row }">
                <template v-if="issueOf(row.relationType)">
                  <div v-if="issueOf(row.relationType).error" class="mp-cell-sub">
                    本次读取失败，请重新校验。<details><summary>实施人员使用</summary>{{ issueOf(row.relationType).error }}</details>
                  </div>
                  <div v-else-if="!gapList(row.relationType).length" class="mp-cell-sub">{{ emptyResult(row.relationType) }}</div>
                  <div class="mp-cell-sub">已检查 {{ issueOf(row.relationType).scanned ?? '未取得' }} / {{ issueOf(row.relationType).total ?? '未取得' }} 条</div>
                  <div v-for="i in gapList(row.relationType)" :key="i.code" class="mp-cell-sub">
                    {{ i.count }} 条 · {{ i.message }}
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
            <p class="mp-note">负责模块：{{ moduleLabel(detail.registry.ownerModule) }}</p>
            <details><summary>实施人员使用</summary>
            <p class="mp-note">模块：{{ detail.registry.ownerModule }} ·
              解析方式：{{ detail.registry.resolver || '未登记' }} ·
              测试：{{ detail.registry.test }}</p>
            <p v-if="detail.registry.notes" class="mp-note">{{ detail.registry.notes }}</p>
            </details>
            <p v-if="detail.data.error" class="mp-note">本次读取失败，请重试；不能据此判断没有缺口。</p>
            <template v-else>
              <p class="mp-note">
                扫描 {{ detail.data.scanned }} / {{ detail.data.total }} 条
                <span v-if="detail.data.truncated">（超出扫描上限，统计为样本）</span>
              </p>
              <ul class="br-list">
                <li v-for="i in (detail.data.issues || [])" :key="i.code">
                  {{ i.count }} 条 · {{ i.message }}
                  <div v-for="sample in i.samples || []" :key="sample.id">
                    <button v-if="sample.object?.route" class="mp-link" @click="openObject(sample.object)">查看样例：{{ sample.object.label }} · {{ sample.object.batchName }}</button>
                    <span v-else-if="sample.object" class="mp-note">{{ sample.object.label }}，定位信息待核对</span>
                  </div>
                  <details><summary>实施人员使用</summary>问题编码 {{ i.code }}；样例编号 {{ (i.samples || []).map((s) => s.id).join('、') }}</details>
                </li>
              </ul>
              <p v-if="!(detail.data.issues || []).length" class="mp-note">{{ detail.data.total === 0 ? '尚无可校验的业务对象。' : detail.data.truncated ? '本次抽查未发现缺口，未覆盖全部对象。' : '本次检查未发现缺口。' }}</p>
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
import { contextFingerprint } from '../utils/workspaceContract'
import { relationshipObjectDestination } from '@/utils/systemRelationshipNavigation'

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
      readSequence: 0,
      detailSequence: 0,
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
    contextKey() { return contextFingerprint(this.ctx) },
    summary() {
      const bad = this.types.filter((t) => !t.healthy).length
      return `共 ${this.types.length} 种关系，登记异常 ${bad} 种`
    }
  },
  created() { this.load() },
  watch: { contextKey() { this.types = []; this.issues = []; this.load() } },
  beforeUnmount() { this.readSequence++; this.detailSequence++ },
  methods: {
    openObject(item) { const route = relationshipObjectDestination(item, this.$route.fullPath); if (route) this.$router.push(route); else toast.error('对象入口或批次信息待核对') },
    moduleLabel(value) { return {studentAffairs:'学工中心',academicAffairs:'教务中心',graduationDesign:'毕业设计',internship:'岗位实习'}[value] || '归属待核对' },
    sourceLabel(value) { return {COUNSELOR_CLASS:'班级当前辅导员',HEAD_TEACHER_CLASS:'班级当前班主任',GD_MENTOR_STUDENT:'毕设批次内导师与学生关系',INTERNSHIP_ADVISOR_STUDENT:'实习批次内校内指导关系',TEACHING_CLASS_TEACHER:'教学班任课关系',DORM_MANAGER_BUILDING:'宿舍楼栋负责人'}[value] || '来源待核对' },
    checkLabel(code) { return {UNSTABLE_KEY:'依赖姓名或文本匹配，改名后可能失联',MODEL_MISSING:'数据来源不可读取',FIELD_MISSING:'数据来源字段缺失',RESOLVER_MISSING:'范围解析能力缺失',RESOLVER_FIELD_MISSING:'范围解析与业务字段不一致',TEST_MISSING:'缺少对应验证记录'}[code] || '登记信息需要核对' },
    emptyResult(type) { const row=this.issueOf(type); return row?.total === 0 ? '尚无可校验对象' : row?.truncated ? '抽查未发现缺口，未覆盖全部' : '本次检查未发现缺口' },
    issueOf(relationType) {
      return this.issues.find((i) => i.relationType === relationType) || null
    },
    gapList(relationType) {
      const row = this.issueOf(relationType)
      return (row && row.issues) || []
    },
    async validateOne(row) {
      const sequence = ++this.detailSequence
      const res = await systemApi.validateBusinessRelation(row.relationType)
      if (sequence !== this.detailSequence) return
      if (res.code === 0) this.detail = res.data
      else toast.error(res.message)
    },
    async load() {
      const sequence = ++this.readSequence
      this.detailSequence++
      this.loading = true
      this.error = ''
      this.detail = null
      const [types, issues] = await Promise.all([
        systemApi.listBusinessRelationTypes(),
        systemApi.listBusinessRelationIssues()
      ])
      if (sequence !== this.readSequence) return
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
