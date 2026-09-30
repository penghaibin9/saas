<template>
  <ModulePageShell
    title="材料规则"
    subtitle="设置本批次学生要交哪些材料、格式和大小、是否需要老师审核。改动先存成草稿，确认影响后再启用"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" text="正在读取材料规则…" />
    <EmptyState v-else-if="!batchId" title="请先选择批次" description="在页面顶部选择毕业设计批次后，这里显示该批次的材料规则。" />
    <div v-else class="mr-page">
      <section class="mr-card">
        <header class="mr-head">
          <div>
            <strong>当前生效的规则</strong>
            <span v-if="active">版本 {{ active.ruleVersion }} · {{ active.items.filter((i) => i.enabled).length }} 项材料</span>
            <span v-else class="mr-bad">本批次还没有生效的材料规则，学生暂时无法提交材料</span>
          </div>
        </header>
        <table v-if="active" class="mr-table">
          <thead><tr><th>材料</th><th>环节</th><th>必交</th><th>老师审核</th><th>格式</th><th>大小上限</th></tr></thead>
          <tbody>
            <tr v-for="item in active.items.filter((i) => i.enabled)" :key="item.materialCode">
              <td>{{ item.materialName }}</td>
              <td>{{ stageLabel(item.stage) }}</td>
              <td>{{ item.required ? '必交' : '选交' }}</td>
              <td>{{ item.reviewRequired ? '需要' : '不需要' }}</td>
              <td>{{ (item.allowedExtensions || []).join('、') }}</td>
              <td>{{ mb(item.maxSizeBytes) }} MB</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="mr-note">下面可以用系统标准模板创建第一版规则，确认后启用。</p>
      </section>

      <section v-if="drafts.length" class="mr-card">
        <header class="mr-head"><div><strong>待启用的草稿</strong><span>草稿不影响学生；启用后才会生效</span></div></header>
        <div v-for="draft in drafts" :key="draft.id" class="mr-draft">
          <div class="mr-draft__main">
            <b>{{ draft.ruleName }}（版本 {{ draft.ruleVersion }}）</b>
            <small>{{ draft.items.filter((i) => i.enabled).length }} 项材料</small>
          </div>
          <div class="mr-actions">
            <AppButton :disabled="busy" @click="showImpact(draft)">查看启用影响</AppButton>
          </div>
          <div v-if="impact && impact.ruleId === draft.id" class="mr-impact">
            <p>启用后会影响本批次 <b>{{ impact.data.affectedStudents }}</b> 名学生，现有材料记录 <b>{{ impact.data.existingMaterialRows }}</b> 条。</p>
            <p v-if="impact.data.addedCodes.length">新增材料：{{ names(impact.data.addedCodes) }}</p>
            <p v-if="impact.data.removedCodes.length">去掉材料：{{ names(impact.data.removedCodes) }}（已有学生上传文件的材料不能去掉，系统会拒绝）</p>
            <p v-if="impact.data.changedCodes.length">调整了要求：{{ names(impact.data.changedCodes) }}</p>
            <p v-if="!impact.data.addedCodes.length && !impact.data.removedCodes.length && !impact.data.changedCodes.length">和当前生效规则没有差别。</p>
            <label v-if="impact.data.requiresCatalogRepair" class="mr-confirm">
              <input v-model="confirmRepair" type="checkbox" />
              我已了解：启用时会同步更新学生已有的材料清单（已归档的学生不受影响）
            </label>
            <div class="mr-actions">
              <AppButton
                variant="primary"
                :disabled="busy || (impact.data.requiresCatalogRepair && !confirmRepair)"
                @click="activate(draft)"
              >{{ busy ? '正在启用，请不要关闭页面…' : '确认启用' }}</AppButton>
            </div>
          </div>
        </div>
      </section>

      <section class="mr-card">
        <header class="mr-head">
          <div>
            <strong>{{ active ? '修改规则（保存为新草稿）' : '创建第一版规则' }}</strong>
            <span>灰色的是毕设主流程必需的材料，不能关闭</span>
          </div>
          <AppButton :disabled="busy" @click="resetEditor">恢复为{{ active ? '当前规则' : '标准模板' }}</AppButton>
        </header>
        <div class="mr-scroll">
          <table class="mr-table mr-edit">
            <thead><tr><th>启用</th><th>材料</th><th>环节</th><th>必交</th><th>老师审核</th><th>允许格式（逗号分隔）</th><th>大小上限 MB</th><th>最多文件数</th></tr></thead>
            <tbody>
              <tr v-for="row in rows" :key="row.materialCode" :class="{ 'is-off': !row.enabled }">
                <td><input v-model="row.enabled" type="checkbox" :disabled="row.locked" :aria-label="`启用${row.materialName}`" /></td>
                <td>{{ row.materialName }}</td>
                <td>{{ stageLabel(row.stage) }}</td>
                <td><input v-model="row.required" type="checkbox" :disabled="!row.enabled" :aria-label="`${row.materialName}必交`" /></td>
                <td>
                  <input
                    v-model="row.reviewRequired" type="checkbox" :disabled="!row.enabled || !row.reviewSupported"
                    :title="row.reviewSupported ? '' : '这项材料系统不支持老师审核'" :aria-label="`${row.materialName}需老师审核`"
                  />
                </td>
                <td><input v-model="row.extText" class="ie-in" :disabled="!row.enabled" /></td>
                <td><input v-model.number="row.maxMb" class="ie-in mr-num" type="number" min="1" max="1024" :disabled="!row.enabled" /></td>
                <td><input v-model.number="row.maxFiles" class="ie-in mr-num" type="number" min="1" max="20" :disabled="!row.enabled" /></td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-if="formError" class="mr-error">{{ formError }}</p>
        <div class="mr-actions">
          <AppButton variant="primary" :disabled="busy" @click="saveDraft">保存为草稿</AppButton>
          <span class="mr-note">保存后会出现在上面的“待启用的草稿”，确认影响后才会生效。</span>
        </div>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { graduationMaterialCenterApi } from '@/modules/graduation/api/graduation-material-center.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

// 毕设主流程必须有的材料：关掉后学生在对应环节无法提交（与「开工检查」口径一致）
const FLOW_CODES = ['TASKBOOK', 'PROPOSAL_REPORT', 'MIDTERM_REPORT', 'THESIS_DRAFT', 'THESIS_FINAL']
const STAGE_LABELS = {
  TOPIC: '选题', TASKBOOK: '任务书', PROPOSAL: '开题', GUIDANCE: '过程指导', MIDTERM: '中期检查',
  FINAL_DRAFT: '论文初稿', FINAL_APPROVED: '论文定稿', PLAGIARISM: '查重', REVIEW: '评阅', DEFENSE: '答辩', GRADE: '成绩评定', TEMPLATE: '模板参考', ARCHIVE: '归档'
}
const MB = 1024 * 1024

export default {
  name: 'GraduationMaterialRuleView',
  components: { AppButton, ModulePageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      loading: false, busy: false, error: '', formError: '',
      rules: [], template: [], reviewCodes: [],
      rows: [], impact: null, confirmRepair: false, loadToken: 0
    }
  },
  computed: {
    batchId() { return String(this.batchStore.selectedBatchId || '') },
    batchRules() { return this.rules.filter((rule) => String(rule.batchId || '') === this.batchId) },
    active() {
      return this.batchRules.filter((rule) => rule.status === 'ENABLED' && rule.enabled)
        .sort((a, b) => b.ruleVersion - a.ruleVersion)[0] || null
    },
    drafts() {
      return this.batchRules.filter((rule) => rule.status === 'DRAFT').sort((a, b) => b.ruleVersion - a.ruleVersion)
    }
  },
  watch: {
    batchId() { this.impact = null; this.load() }
  },
  created() { this.load() },
  beforeUnmount() { ++this.loadToken },
  methods: {
    stageLabel(code) { return STAGE_LABELS[code] ? STAGE_LABELS[code] : '其他环节' },
    mb(bytes) { return Math.round((Number(bytes) || 0) / MB) },
    names(codes) {
      const all = [...this.template, ...(this.active?.items || []), ...this.drafts.flatMap((d) => d.items)]
      return codes.map((code) => all.find((row) => row.materialCode === code)?.materialName || code).join('、')
    },
    async load() {
      const token = ++this.loadToken
      this.error = ''
      if (!this.batchId) { this.rules = []; this.rows = []; return }
      this.loading = true
      try {
        const data = await graduationMaterialCenterApi.listRules(this.batchId)
        if (token !== this.loadToken) return
        this.rules = Array.isArray(data?.items) ? data.items : []
        this.template = Array.isArray(data?.defaultTemplate) ? data.defaultTemplate : []
        this.reviewCodes = Array.isArray(data?.reviewSupportedCodes) ? data.reviewSupportedCodes : []
        this.resetEditor()
      } catch (failure) {
        if (token === this.loadToken) this.error = failure?.message || '材料规则读取失败'
      } finally {
        if (token === this.loadToken) this.loading = false
      }
    },
    resetEditor() {
      this.formError = ''
      const activeByCode = new Map((this.active?.items || []).map((item) => [item.materialCode, item]))
      const seen = new Set()
      const rows = []
      const build = (base, enabled) => ({
        materialCode: base.materialCode, materialName: base.materialName, stage: base.stage,
        ownerRole: base.ownerRole || 'STUDENT', versionPolicy: base.versionPolicy || 'IMMUTABLE_APPEND',
        archiveRequired: base.archiveRequired !== false, sensitivityLevel: base.sensitivityLevel || 'SENSITIVE',
        enabled, locked: FLOW_CODES.includes(base.materialCode),
        required: Boolean(base.required), reviewRequired: Boolean(base.reviewRequired),
        reviewSupported: this.reviewCodes.includes(base.materialCode),
        extText: (base.allowedExtensions || []).join(','),
        maxMb: this.mb(base.maxSizeBytes) || 50, maxFiles: Number(base.maxFileCount) || 1
      })
      // 没有生效规则时，主流程材料默认全开；有生效规则时以它为准
      for (const tpl of this.template) {
        const current = activeByCode.get(tpl.materialCode)
        rows.push(build(current || tpl, this.active ? Boolean(current && current.enabled) || FLOW_CODES.includes(tpl.materialCode) : true))
        seen.add(tpl.materialCode)
      }
      for (const item of this.active?.items || []) {
        if (!seen.has(item.materialCode)) rows.push(build(item, Boolean(item.enabled)))
      }
      this.rows = rows
    },
    validate() {
      const enabled = this.rows.filter((row) => row.enabled)
      if (!enabled.length) return '至少要启用一项材料'
      for (const row of enabled) {
        const exts = String(row.extText || '').split(/[,，、\s]+/).map((s) => s.trim().replace(/^\./, '')).filter(Boolean)
        if (!exts.length) return `「${row.materialName}」需要填写允许的文件格式，例如 pdf,docx`
        if (!(Number(row.maxMb) > 0)) return `「${row.materialName}」的大小上限要大于 0`
        if (!(Number(row.maxFiles) >= 1)) return `「${row.materialName}」最多文件数至少是 1`
      }
      const missing = FLOW_CODES.filter((code) => !enabled.some((row) => row.materialCode === code))
      if (missing.length) return `这些是毕设主流程必需的材料，不能关闭：${this.names(missing)}`
      return ''
    },
    async saveDraft() {
      if (this.busy) return
      this.formError = this.validate()
      if (this.formError) return
      this.busy = true
      try {
        const items = this.rows.filter((row) => row.enabled).map((row) => ({
          materialCode: row.materialCode, materialName: row.materialName, stage: row.stage, ownerRole: row.ownerRole,
          required: Boolean(row.required), reviewRequired: Boolean(row.reviewRequired && row.reviewSupported),
          allowedExtensions: String(row.extText).split(/[,，、\s]+/).map((s) => s.trim().replace(/^\./, '')).filter(Boolean),
          maxSizeBytes: Math.round(Number(row.maxMb) * MB), maxFileCount: Math.round(Number(row.maxFiles)),
          versionPolicy: row.versionPolicy, archiveRequired: row.archiveRequired, sensitivityLevel: row.sensitivityLevel,
          enabled: true
        }))
        await graduationMaterialCenterApi.createRule({
          batchId: this.batchId, ruleName: `${this.batchStore.selectedBatchName || '本批次'}材料规则`, items
        })
        toast.success('草稿已保存，请在上方确认影响后启用')
        this.impact = null
        await this.load()
      } catch (failure) {
        this.formError = failure?.message || '草稿保存失败'
      } finally {
        this.busy = false
      }
    },
    async showImpact(draft) {
      if (this.busy) return
      this.busy = true
      this.confirmRepair = false
      try {
        const data = await graduationMaterialCenterApi.ruleImpact(draft.id)
        this.impact = { ruleId: draft.id, data: {
          affectedStudents: 0, existingMaterialRows: 0, addedCodes: [], removedCodes: [], changedCodes: [],
          requiresCatalogRepair: false, ...(data || {})
        } }
      } catch (failure) {
        toast.error(failure?.message || '影响分析读取失败')
      } finally {
        this.busy = false
      }
    },
    async activate(draft) {
      if (this.busy) return
      this.busy = true
      try {
        await graduationMaterialCenterApi.activateRule(draft.id, {
          confirmCatalogRepair: this.confirmRepair, expectedVersion: draft.version
        })
        toast.success('材料规则已启用')
        this.impact = null
        await this.load()
      } catch (failure) {
        toast.error(failure?.message || '启用失败')
      } finally {
        this.busy = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mr-page{display:grid;gap:14px}.mr-card{border:1px solid var(--border-light,#e2e8f0);border-radius:12px;background:#fff;padding:14px;min-width:0}.mr-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.mr-head>div{display:grid;gap:3px}.mr-head strong{font-size:15px}.mr-head span,.mr-note{font-size:12px;color:var(--text-tertiary,#64748b)}.mr-bad{color:#b91c1c!important}.mr-scroll{overflow:auto}.mr-table{width:100%;border-collapse:collapse;font-size:13px}.mr-table th,.mr-table td{padding:7px 8px;border-bottom:1px solid var(--border-light,#e2e8f0);text-align:left;vertical-align:middle}.mr-table th{font-size:12px;color:var(--text-tertiary,#64748b);font-weight:500;white-space:nowrap}.mr-edit .is-off td{opacity:.55}.mr-num{width:78px}.mr-edit .ie-in{min-width:150px}.mr-edit .mr-num{min-width:0}.mr-draft{display:grid;gap:8px;padding:10px 0;border-bottom:1px dashed var(--border-light,#e2e8f0)}.mr-draft__main{display:flex;gap:10px;align-items:baseline}.mr-draft__main small{color:var(--text-tertiary,#64748b)}.mr-impact{padding:10px;border-radius:8px;background:var(--primary-50,#eff6ff);font-size:13px;line-height:1.7}.mr-impact p{margin:2px 0}.mr-confirm{display:flex;gap:8px;align-items:flex-start;margin:8px 0;font-size:13px}.mr-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px}.mr-error{margin:10px 0 0;padding:9px;border-radius:8px;background:#fef2f2;color:#b91c1c;font-size:12px}.mp-btn{padding:7px 14px;border:1px solid var(--border-light,#d9dee8);border-radius:8px;background:#fff;cursor:pointer}.mp-btn--primary{background:var(--pri,#2563eb);border-color:var(--pri,#2563eb);color:#fff}.mp-btn:disabled{opacity:.55;cursor:not-allowed}
</style>
