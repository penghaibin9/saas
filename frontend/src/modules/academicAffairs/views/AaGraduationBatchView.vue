<template>
  <ModulePageShell
    title="审核批次"
    subtitle="建批次 → 圈定应届生 → 十项供数三态预审 → 学院初审 → 教务终审 → 归档"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppSectionCard v-if="!batch" title="新建审核批次">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item aa-cal-form__item--grow">批次名称<input v-model.trim="draft.batchName" class="aa-input" placeholder="如 2026届毕业资格审核" maxlength="60" /></label>
          <label class="aa-cal-form__item">年级<input v-model.trim="draft.gradeYear" class="aa-input aa-input--sm" placeholder="如 2023" /></label>
          <label class="aa-cal-form__item">专业ID<input v-model.trim="draft.majorId" class="aa-input aa-input--sm" placeholder="选填" /></label>
          <AppButton variant="primary" :loading="creating" :disabled="!draft.batchName" @click="createBatch">创建</AppButton>
        </div>
      </AppSectionCard>

      <template v-else>
        <AppSectionCard :title="`批次：${batch.batchName}`">
          <div class="aa-batch-actions">
            <AppStatusTag type="primary">{{ batch.status }}</AppStatusTag>
            <AppButton :loading="busy" @click="generate">圈定应届生</AppButton>
            <AppButton :loading="busy" @click="precheck">执行十项预审</AppButton>
            <AppButton variant="primary" @click="$router.push(`/admin/academic-affairs/graduation/${batch.batchId}/results`)">查看结果 / 复核</AppButton>
            <AppButton @click="resetBatch">另建批次</AppButton>
          </div>
          <AppInlineAlert v-if="genInfo" type="success" :message="genInfo" />
          <AppInlineAlert v-if="preInfo" type="success" :message="preInfo" />
          <p class="mp-note">圈定与预审均幂等（结果覆盖非追加）；十项含学籍/学分/必修/选修/实践/实习/毕设/处分/就业/归档，UNKNOWN 不阻断进人工复核。</p>
        </AppSectionCard>
      </template>

      <AppSectionCard title="历史批次">
        <LoadingState v-if="loadingList" />
        <EmptyState v-else-if="!batches.length" title="暂无历史批次" description="新建的审核批次会持久保存在此，刷新页面不丢失" />
        <DataTable v-else :columns="listColumns" :rows="batches" row-key="batchId">
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'ARCHIVED' ? 'default' : 'primary'" dot>{{ row.status }}</AppStatusTag></template>
          <template #cell-ops="{ row }">
            <router-link class="mp-link" :to="`/admin/academic-affairs/graduation/audit-console?batchId=${row.batchId}&tab=results`">进入审核工作台</router-link>
          </template>
        </DataTable>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/** 审核批次（/admin/academic-affairs/graduation）：建批次 + 圈定 + 预审 + 历史批次列表（进审核工作台）。 */
import { ModulePageShell, DataTable, LoadingState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppInlineAlert } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaGraduationBatchView',
  components: { ModulePageShell, DataTable, LoadingState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppInlineAlert },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      draft: { batchName: '', gradeYear: '', majorId: '' },
      creating: false, batch: null, busy: false, genInfo: '', preInfo: '',
      batches: [], loadingList: true,
      listColumns: [
        { key: 'batchName', title: '批次名称' }, { key: 'gradeYear', title: '年级' },
        { key: 'total', title: '应审' }, { key: 'passed', title: '系统通过' }, { key: 'abnormal', title: '系统异常' },
        { key: 'concluded', title: '已终审' }, { key: 'archived', title: '已归档' },
        { key: 'status', title: '状态' }, { key: 'ops', title: '操作', width: '120px' }
      ]
    }
  },
  created() { this.loadBatches() },
  methods: {
    async loadBatches() {
      this.loadingList = true
      const res = await academicAffairsApi.listGradBatches({ pageSize: 100 })
      this.batches = res.code === 0 ? res.data.list : []
      this.loadingList = false
    },
    async createBatch() {
      if (this.creating || !this.draft.batchName) return
      this.creating = true
      const res = await academicAffairsApi.createGradBatch({
        batchName: this.draft.batchName,
        gradeYear: this.draft.gradeYear || undefined,
        majorId: this.draft.majorId || undefined
      })
      this.creating = false
      if (res.code === 0) { this.batch = res.data; toast.success('批次已创建'); this.loadBatches() }
      else toast.error(res.message || '创建失败')
    },
    resetBatch() { this.batch = null; this.genInfo = ''; this.preInfo = ''; this.draft = { batchName: '', gradeYear: '', majorId: '' } },
    async generate() {
      if (this.busy) return
      this.busy = true
      const res = await academicAffairsApi.generateGradStudents(this.batch.batchId, null)
      this.busy = false
      if (res.code === 0) { this.genInfo = `已圈定应届生 ${res.data.generated} 人`; toast.success('已圈定'); this.loadBatches() }
      else toast.error(res.message || '圈定失败')
    },
    async precheck() {
      if (this.busy) return
      this.busy = true
      const res = await academicAffairsApi.precheckGrad(this.batch.batchId)
      this.busy = false
      if (res.code === 0) { this.preInfo = `预审完成：通过 ${res.data.passed} · 异常 ${res.data.abnormal}`; toast.success('预审完成'); this.loadBatches() }
      else toast.error(res.message || '预审失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-cal-form__item--grow { flex: 1; min-width: 240px; }
.aa-input { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 120px; }
.aa-batch-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
</style>
