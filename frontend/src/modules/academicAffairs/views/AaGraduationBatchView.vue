<template>
  <ModulePageShell
    title="毕业资格预审"
    subtitle="建批次 → 圈定应届生 → 七项供数三态预审 → 学院初审 → 教务终审"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppSectionCard v-if="!batch" title="新建预审批次">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item aa-cal-form__item--grow">批次名称<input v-model.trim="draft.batchName" class="aa-input" placeholder="如 2026届毕业资格预审" maxlength="60" /></label>
          <label class="aa-cal-form__item">年级<input v-model.trim="draft.gradeYear" class="aa-input aa-input--sm" placeholder="如 2023" /></label>
          <label class="aa-cal-form__item">专业ID<input v-model.trim="draft.majorId" class="aa-input aa-input--sm" placeholder="选填" /></label>
          <button class="mp-btn mp-btn--primary" :disabled="creating || !draft.batchName" @click="createBatch">{{ creating ? '创建中…' : '创建' }}</button>
        </div>
      </AppSectionCard>

      <template v-else>
        <AppSectionCard :title="`批次：${batch.batchName}`">
          <div class="aa-batch-actions">
            <AppStatusTag type="primary">{{ batch.status }}</AppStatusTag>
            <button class="mp-btn" :disabled="busy" @click="generate">圈定应届生</button>
            <button class="mp-btn" :disabled="busy" @click="precheck">执行七项预审</button>
            <button class="mp-btn mp-btn--primary" @click="$router.push(`/admin/academic-affairs/graduation/${batch.batchId}/results`)">查看结果 / 复核</button>
            <button class="mp-btn" @click="resetBatch">另建批次</button>
          </div>
          <AppInlineAlert v-if="genInfo" type="success" :message="genInfo" />
          <AppInlineAlert v-if="preInfo" type="success" :message="preInfo" />
          <p class="mp-note">圈定与预审均幂等（结果覆盖非追加）；七项含学籍/学分成绩/处分/实习/毕设/就业/归档，UNKNOWN 不阻断进人工复核。</p>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 毕业预审批次（/admin/academic-affairs/graduation）：建批次 + 圈定 + 预审。 */
import { ModulePageShell } from '@/components/business'
import { AppSectionCard, AppStatusTag, AppInlineAlert } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaGraduationBatchView',
  components: { ModulePageShell, AppSectionCard, AppStatusTag, AppInlineAlert },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      draft: { batchName: '', gradeYear: '', majorId: '' },
      creating: false, batch: null, busy: false, genInfo: '', preInfo: ''
    }
  },
  methods: {
    async createBatch() {
      if (this.creating || !this.draft.batchName) return
      this.creating = true
      const res = await academicAffairsApi.createGradBatch({
        batchName: this.draft.batchName,
        gradeYear: this.draft.gradeYear || undefined,
        majorId: this.draft.majorId || undefined
      })
      this.creating = false
      if (res.code === 0) { this.batch = res.data; toast.success('批次已创建') }
      else toast.error(res.message || '创建失败')
    },
    resetBatch() { this.batch = null; this.genInfo = ''; this.preInfo = ''; this.draft = { batchName: '', gradeYear: '', majorId: '' } },
    async generate() {
      if (this.busy) return
      this.busy = true
      const res = await academicAffairsApi.generateGradStudents(this.batch.batchId, null)
      this.busy = false
      if (res.code === 0) { this.genInfo = `已圈定应届生 ${res.data.generated} 人`; toast.success('已圈定') }
      else toast.error(res.message || '圈定失败')
    },
    async precheck() {
      if (this.busy) return
      this.busy = true
      const res = await academicAffairsApi.precheckGrad(this.batch.batchId)
      this.busy = false
      if (res.code === 0) { this.preInfo = `预审完成：通过 ${res.data.passed} · 异常 ${res.data.abnormal}`; toast.success('预审完成') }
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
