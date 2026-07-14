<template>
  <ModulePageShell
    title="校历管理"
    subtitle="按学期维护教学 / 考试 / 实习 / 假期 / 调课日安排"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <!-- 学期选择 -->
      <div class="aa-filter">
        <label class="aa-filter__item">
          学期
          <select v-model="termId" class="aa-select" @change="loadEvents">
            <option v-for="t in terms" :key="t.termId" :value="t.termId">
              {{ t.yearCode }} 第 {{ t.termNo }} 学期{{ t.isCurrent ? '（当前）' : '' }}
            </option>
          </select>
        </label>
      </div>

      <EmptyState
        v-if="!termsLoading && !terms.length"
        title="还没有学年学期"
        description="校历依附于学期，请先到「学年学期」创建并发布一个学期"
      >
        <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/academic-affairs/terms')">前往学年学期</button>
      </EmptyState>

      <template v-else>
        <!-- 新增事件 -->
        <AppSectionCard title="新增校历事件">
          <div class="aa-cal-form">
            <label class="aa-cal-form__item">
              类型
              <select v-model="draft.eventType" class="aa-select">
                <option v-for="(label, val) in EVENT_TYPES" :key="val" :value="val">{{ label }}</option>
              </select>
            </label>
            <label class="aa-cal-form__item">
              开始日期
              <input v-model="draft.startDate" type="date" class="aa-input aa-input--date" />
            </label>
            <label class="aa-cal-form__item">
              结束日期
              <input v-model="draft.endDate" type="date" class="aa-input aa-input--date" />
            </label>
            <label v-if="draft.eventType === 'SWAP'" class="aa-cal-form__item">
              调至日期
              <input v-model="draft.swapToDate" type="date" class="aa-input aa-input--date" />
            </label>
            <label class="aa-cal-form__item aa-cal-form__item--grow">
              备注
              <input v-model.trim="draft.remark" class="aa-input" placeholder="选填，如 国庆假期 / 期末考试周" maxlength="60" />
            </label>
            <button class="mp-btn mp-btn--primary" :disabled="adding || !draft.startDate" @click="addEvent">
              {{ adding ? '添加中…' : '添加事件' }}
            </button>
          </div>
        </AppSectionCard>

        <!-- 事件列表 -->
        <AppSectionCard title="校历事件">
          <ErrorState v-if="error" :description="error" @retry="loadEvents" />
          <LoadingState v-else-if="eventsLoading" />
          <EmptyState v-else-if="!events.length" title="本学期暂无校历事件" description="用上方表单添加教学/考试/假期等安排" />
          <ul v-else class="aa-cal-list">
            <li v-for="ev in events" :key="ev.eventId" class="aa-cal-item">
              <AppStatusTag :type="typeColor(ev.eventType)">{{ EVENT_TYPES[ev.eventType] || ev.eventType }}</AppStatusTag>
              <span class="aa-cal-item__date">
                {{ ev.startDate || '—' }}<template v-if="ev.endDate && ev.endDate !== ev.startDate"> ~ {{ ev.endDate }}</template>
                <template v-if="ev.swapToDate"> → 调至 {{ ev.swapToDate }}</template>
              </span>
              <span class="aa-cal-item__remark">{{ ev.remark || '' }}</span>
            </li>
          </ul>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 校历管理（/admin/academic-affairs/calendar）：按学期 GET/POST /academic-affairs/terms/{termId}/calendar。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const EVENT_TYPES = { TEACHING: '教学', EXAM: '考试', INTERNSHIP: '实习', HOLIDAY: '假期', SWAP: '调课' }
const TYPE_COLOR = { TEACHING: 'primary', EXAM: 'danger', INTERNSHIP: 'warning', HOLIDAY: 'success', SWAP: 'default' }

export default {
  name: 'AaCalendarView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      EVENT_TYPES,
      termsLoading: true,
      terms: [],
      termId: '',
      eventsLoading: false,
      error: '',
      events: [],
      adding: false,
      draft: { eventType: 'TEACHING', startDate: '', endDate: '', swapToDate: '', remark: '' }
    }
  },
  created() {
    this.loadTerms()
  },
  methods: {
    typeColor(t) {
      return TYPE_COLOR[t] || 'default'
    },
    async loadTerms() {
      this.termsLoading = true
      const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
      if (res.code === 0) {
        this.terms = res.data.list
        const cur = this.terms.find((t) => t.isCurrent) || this.terms[0]
        if (cur) {
          this.termId = cur.termId
          this.loadEvents()
        }
      } else {
        this.error = res.message
      }
      this.termsLoading = false
    },
    async loadEvents() {
      if (!this.termId) return
      this.eventsLoading = true
      this.error = ''
      const res = await academicAffairsApi.getCalendar(this.termId)
      if (res.code === 0) {
        this.events = res.data || []
      } else {
        this.error = res.message
      }
      this.eventsLoading = false
    },
    async addEvent() {
      if (this.adding || !this.termId) return
      if (!this.draft.startDate) {
        toast.error('请先选择开始日期')
        return
      }
      if (this.draft.eventType === 'SWAP' && !this.draft.swapToDate) {
        toast.error('调课事件请填写「调至日期」')
        return
      }
      this.adding = true
      const body = {
        eventType: this.draft.eventType,
        startDate: this.draft.startDate,
        endDate: this.draft.endDate || this.draft.startDate,
        swapToDate: this.draft.eventType === 'SWAP' ? this.draft.swapToDate : undefined,
        remark: this.draft.remark || undefined
      }
      const res = await academicAffairsApi.addCalendarEvent(this.termId, body)
      this.adding = false
      if (res.code === 0) {
        toast.success('校历事件已添加')
        this.draft = { eventType: 'TEACHING', startDate: '', endDate: '', swapToDate: '', remark: '' }
        this.loadEvents()
      } else {
        toast.error(res.message || '添加失败')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; }
.aa-filter__item, .aa-cal-form__item {
  display: inline-flex; flex-direction: column; gap: 6px;
  font-size: 13px; color: var(--text-700, #4e5969);
}
.aa-filter__item { flex-direction: row; align-items: center; gap: 8px; }
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item--grow { flex: 1; min-width: 200px; }
.aa-select, .aa-input {
  height: 34px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px;
  box-sizing: border-box;
}
.aa-input--date { width: 160px; }
.aa-cal-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.aa-cal-item {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 4px; border-bottom: 1px solid var(--border-100, #f0f1f2);
}
.aa-cal-item__date { font-size: 14px; color: var(--text-900, #1f2329); min-width: 220px; }
.aa-cal-item__remark { color: var(--text-500, #646a73); font-size: 13px; }
</style>
