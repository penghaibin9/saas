<template>
  <ModulePageShell
    title="合规与监管证据"
    subtitle="规则版本 · 准入/知情/安全/备案 · 统一上岗检查 · 一键证据包"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="mp-tabs" aria-label="合规工作区">
        <button
          v-for="t in tabs"
          :key="t.key"
          class="mp-tab"
          :class="{ 'is-active': tab === t.key }"
          @click="tab = t.key"
        >{{ t.label }}</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <template v-else>
        <div v-if="tab === 'evaluate'" class="mp-card">
          <p class="mp-note">输入实习记录 ID，执行统一上岗/归档合规检查（同一规则版本）。</p>
          <div class="bar">
            <input v-model="internshipId" class="mp-input" placeholder="internshipId" />
            <AppButton variant="secondary" size="sm" @click="runEvaluate">检查</AppButton>
            <AppButton variant="ghost" size="sm" :disabled="!batchStore.selectedBatchId" @click="runBatchStats">批次统计</AppButton>
            <AppButton variant="primary" size="sm" :disabled="!internshipId" @click="genPackage('STUDENT', internshipId)">生成学生证据包</AppButton>
            <AppButton variant="primary" size="sm" :disabled="!batchStore.selectedBatchId" @click="genPackage('BATCH', batchStore.selectedBatchId)">生成批次证据包</AppButton>
          </div>
          <pre v-if="evalResult" class="mp-pre">{{ evalResult }}</pre>
        </div>

        <div v-else-if="tab === 'templates'" class="mp-card">
          <div class="bar">
            <AppButton variant="secondary" size="sm" @click="createTpl">新建草稿模板</AppButton>
            <AppButton variant="ghost" size="sm" @click="loadTemplates">刷新</AppButton>
          </div>
          <EmptyState v-if="!templates.length" title="暂无合规模板" description="可新建草稿并激活（激活后不可原地覆盖）" />
          <ul v-else class="mp-list">
            <li v-for="t in templates" :key="t.id" class="mp-list__item">
              <strong>{{ t.templateName || t.name || t.id }}</strong>
              <span class="mp-note">{{ t.status }} · v{{ t.templateVersion || t.version }}</span>
              <button v-if="t.status === 'DRAFT'" class="mp-link" @click="activateTpl(t.id)">激活</button>
            </li>
          </ul>
        </div>

        <div v-else class="mp-card">
          <p class="mp-note">企业考察、知情确认、安全教育、特殊备案、事故处置请通过对应业务台账与本页「合规检查」联用；本页不重复堆砌多套表单。</p>
          <p class="mp-note">当前批次：{{ batchStore.selectedBatchId || '未选择' }}</p>
        </div>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppButton from '@/components/ui/AppButton.vue'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { complianceApi } from '@/modules/internship/api/compliance.api'
import { toast } from '@/utils/toast'

export default {
  name: 'InternshipComplianceView',
  components: { ModulePageShell, ErrorState, LoadingState, EmptyState, AppButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'evaluate',
      tabs: [
        { key: 'evaluate', label: '合规检查与证据包' },
        { key: 'templates', label: '规则模板' },
        { key: 'guide', label: '能力说明' }
      ],
      loading: false,
      error: '',
      internshipId: '',
      evalResult: '',
      templates: []
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() }
  },
  mounted() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = false
      this.error = ''
      if (this.tab === 'templates') await this.loadTemplates()
    },
    async loadTemplates() {
      const res = await complianceApi.listTemplates()
      if (res.code !== 0) { toast.error(res.message || '加载失败'); return }
      this.templates = Array.isArray(res.data) ? res.data : (res.data?.list || [])
    },
    async createTpl() {
      const res = await complianceApi.createTemplate({
        templateCode: 'DEFAULT',
        templateName: '岗位实习合规模板',
        config: {
          studentConsent: { required: true, severity: 'BLOCK' },
          safetyEducation: { required: true, severity: 'BLOCK' },
          enterpriseAccess: { required: true, severity: 'BLOCK' }
        }
      })
      if (res.code !== 0) return toast.error(res.message || '创建失败')
      toast.success('草稿已创建')
      this.loadTemplates()
    },
    async activateTpl(id) {
      const res = await complianceApi.activateTemplate(id, { changeReason: '启用合规模板' })
      if (res.code !== 0) return toast.error(res.message || '激活失败')
      toast.success('模板已激活')
      this.loadTemplates()
    },
    async runEvaluate() {
      if (!this.internshipId) return toast.error('请填写实习记录 ID')
      const res = await complianceApi.evaluate(this.internshipId, 'ONBOARD')
      if (res.code !== 0) return toast.error(res.message || '检查失败')
      this.evalResult = JSON.stringify(res.data, null, 2)
    },
    async runBatchStats() {
      const bid = this.batchStore.selectedBatchId
      if (!bid) return toast.error('请先选择批次')
      const res = await complianceApi.batchStats(bid)
      if (res.code !== 0) return toast.error(res.message || '统计失败')
      this.evalResult = JSON.stringify(res.data, null, 2)
    },
    async genPackage(type, id) {
      const res = await complianceApi.generateEvidencePackage(type, id)
      if (res.code !== 0) return toast.error(res.message || '生成失败')
      toast.success(`证据包已生成 v${res.data.version}，缺失项 ${ (res.data.missingItems || []).length }`)
      this.evalResult = JSON.stringify(res.data, null, 2)
    }
  },
  watch: {
    tab() { this.load() }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.bar { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-3); align-items: center; }
.mp-input { min-width: 220px; padding: 6px 10px; border: 1px solid var(--border-color, #d0d5dd); border-radius: 6px; }
.mp-pre { white-space: pre-wrap; font-size: 12px; background: var(--color-bg-subtle, #f6f7f9); padding: var(--space-3); border-radius: 8px; max-height: 480px; overflow: auto; }
.mp-list { list-style: none; padding: 0; margin: 0; }
.mp-list__item { display: flex; gap: 12px; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--border-color, #eee); }
</style>
