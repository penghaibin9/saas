<template>
  <ModulePageShell
    title="作息时间 · 节次"
    subtitle="配置每天的上课节次与起止时间，供排课与课表使用（全校统一）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppSectionCard title="新增节次">
        <div class="aa-slot-form">
          <label class="aa-slot-form__item">
            第几节
            <input v-model.number="draft.slotNo" type="number" min="1" max="20" class="aa-input aa-input--num" placeholder="如 1" />
          </label>
          <label class="aa-slot-form__item">
            名称
            <input v-model.trim="draft.slotName" class="aa-input" placeholder="选填，如 第一大节" maxlength="30" />
          </label>
          <label class="aa-slot-form__item">
            开始时间
            <input v-model.trim="draft.startTime" class="aa-input aa-input--time" placeholder="08:00" maxlength="5" />
          </label>
          <label class="aa-slot-form__item">
            结束时间
            <input v-model.trim="draft.endTime" class="aa-input aa-input--time" placeholder="08:45" maxlength="5" />
          </label>
          <button class="mp-btn mp-btn--primary" :disabled="adding" @click="addSlot">
            {{ adding ? '添加中…' : '添加节次' }}
          </button>
        </div>
        <div v-if="formError" class="aa-form__err">{{ formError }}</div>
      </AppSectionCard>

      <AppSectionCard title="节次列表">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="尚未配置节次" description="用上方表单添加第 1 节、第 2 节…及其上课时间" />
        <table v-else class="aa-slot-table">
          <thead>
            <tr>
              <th>节次</th>
              <th>名称</th>
              <th>开始</th>
              <th>结束</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in rows" :key="s.slotId">
              <td>第 {{ s.slotNo }} 节</td>
              <td>{{ s.slotName || '—' }}</td>
              <td>{{ s.startTime || '—' }}</td>
              <td>{{ s.endTime || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </AppSectionCard>

      <p class="mp-note">节次为全校统一配置，供后续「排课 / 课表」波次的周历网格使用。编辑 / 停用节次为后续波次交付。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 作息节次（/admin/academic-affairs/time-slots）：GET/POST /academic-affairs/time-slots。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const HHMM_RE = /^([01]\d|2[0-3]):[0-5]\d$/

export default {
  name: 'AaTimeSlotView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      adding: false,
      formError: '',
      draft: { slotNo: null, slotName: '', startTime: '', endTime: '' }
    }
  },
  created() {
    this.load()
  },
  methods: {
    validate() {
      if (!this.draft.slotNo || this.draft.slotNo < 1) return '请填写有效的节次序号（≥1）'
      if (this.draft.startTime && !HHMM_RE.test(this.draft.startTime)) return '开始时间格式应为 HH:MM，如 08:00'
      if (this.draft.endTime && !HHMM_RE.test(this.draft.endTime)) return '结束时间格式应为 HH:MM，如 08:45'
      if (this.draft.startTime && this.draft.endTime && this.draft.startTime >= this.draft.endTime) {
        return '结束时间应晚于开始时间'
      }
      return ''
    },
    async addSlot() {
      if (this.adding) return
      const err = this.validate()
      this.formError = err
      if (err) return
      this.adding = true
      const body = {
        slotNo: Number(this.draft.slotNo),
        slotName: this.draft.slotName || undefined,
        startTime: this.draft.startTime || undefined,
        endTime: this.draft.endTime || undefined
      }
      const res = await academicAffairsApi.createTimeSlot(body)
      this.adding = false
      if (res.code === 0) {
        toast.success(`已添加第 ${body.slotNo} 节`)
        this.draft = { slotNo: null, slotName: '', startTime: '', endTime: '' }
        this.load()
      } else {
        toast.error(res.message || '添加失败')
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) {
        this.rows = res.data || []
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-slot-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-slot-form__item {
  display: inline-flex; flex-direction: column; gap: 6px;
  font-size: 13px; color: var(--text-700, #4e5969);
}
.aa-input {
  height: 34px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px;
  box-sizing: border-box;
}
.aa-input--num { width: 120px; }
.aa-input--time { width: 120px; }
.aa-form__err { margin-top: 8px; font-size: 12px; color: var(--danger-600, #f53f3f); }
.aa-slot-table { width: 100%; border-collapse: collapse; }
.aa-slot-table th, .aa-slot-table td {
  text-align: left; padding: 10px 12px;
  border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px;
}
.aa-slot-table th { color: var(--text-500, #646a73); font-weight: 500; font-size: 13px; }
</style>
