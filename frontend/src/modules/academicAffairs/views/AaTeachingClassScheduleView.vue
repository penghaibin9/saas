<template>
  <ModulePageShell
    title="教学班课表"
    subtitle="按教学班（派生自教学任务，含合班后的教学单元）查看当前已发布课表"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aa-reg-search">
        <AppTeachingClassPicker v-model="teachingClassCode" class="aa-input--grow" placeholder="按教学班名称/课程名搜索" @change="onTeachingClassChange" />
      </div>

      <template v-if="teachingClassCode">
        <div class="aa-filter">
          <button class="mp-link" @click="teachingClassCode = ''">‹ 重新选择教学班</button>
          <label class="aa-filter__item">
            学期
            <AppTermEntityPicker v-model="termId" placeholder="当前已发布批次" @change="load" />
          </label>
          <label class="aa-filter__item">
            周次
            <input v-model.number="week" type="number" min="1" max="30" class="aa-input aa-input--sm" placeholder="全部周次" @keyup.enter="load" />
          </label>
          <AppButton variant="primary" @click="load">查询</AppButton>
        </div>

        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <template v-else>
          <p v-if="note" class="mp-note">{{ note }}</p>
          <AppSectionCard :title="teachingClassName ? `${teachingClassName} · 课表` : '教学班课表'">
            <AaScheduleGrid :items="items" :slots="slots" :editable="false" @item-click="onItemClick" />
          </AppSectionCard>
        </template>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 教学班课表（/admin/academic-affairs/schedule/teaching-class/:code?）：13B 课表管理续工第三轮新增。
 * 教学班无独立表，派生自教学任务（GET /orgs/teaching-classes 只读汇总，本页复用其作为选择器数据源，
 * 一次性拉取当页列表在客户端做关键字筛选——后端该端点暂无 keyword 参数，未新增，见施工记录）。
 * GET /academic-affairs/schedule/teaching-class/{code}?termId=&week=；数据范围校验同班级课表口径，
 * 越范围 → 403002；未知教学班代码 → 404。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppTeachingClassPicker, AppTermEntityPicker } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTeachingClassScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, AppButton, AppSectionCard, AppTeachingClassPicker, AppTermEntityPicker, AaScheduleGrid },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      teachingClassCode: this.$route.params.code || '', teachingClassName: '',
      termId: '', week: null,
      slots: [], items: [], note: '', loading: false, error: ''
    }
  },
  created() {
    this.loadSlots()
    if (this.teachingClassCode) this.load()
  },
  methods: {
    onTeachingClassChange(value, items) {
      const item = items?.[0]
      const row = item?.raw || item || {}
      this.teachingClassName = row.teachingClassName || row.className || item?.label || ''
      if (!value) return
      this.$router.replace(`/admin/academic-affairs/schedule/teaching-class/${encodeURIComponent(this.teachingClassCode)}`).catch(() => {})
      this.load()
    },
    onItemClick(it) {
      toast.success(`${it.courseName || ''} · ${it.teacherName || ''} · ${it.classroom || ''} · ${it.startWeek}-${it.endWeek}周`)
    },
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async load() {
      if (!this.teachingClassCode) return
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTeachingClassSchedule(this.teachingClassCode, {
        termId: this.termId || undefined, week: this.week || undefined
      })
      this.loading = false
      if (res.code === 0) {
        this.items = res.data.items || []
        this.note = res.data.note || ''
        if (res.data.teachingClassName) this.teachingClassName = res.data.teachingClassName
      } else {
        this.error = res.message
        this.items = []
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-reg-search { display: flex; gap: 12px; align-items: center; margin-bottom: 4px; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input--grow { flex: 1; }
.aa-input--sm { width: 120px; }
.aa-cand-list { list-style: none; margin: 0; padding: 0; border: 1px solid var(--border-100, #f0f1f2); border-radius: 6px; max-height: 360px; overflow-y: auto; }
.aa-cand-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 13px; }
.aa-cand-item:last-child { border-bottom: none; }
.aa-filter { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-filter__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); min-width: 160px; }
.aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
</style>
