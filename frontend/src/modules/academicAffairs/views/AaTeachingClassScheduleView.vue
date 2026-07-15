<template>
  <ModulePageShell
    title="教学班课表"
    subtitle="按教学班（派生自教学任务，含合班后的教学单元）查看当前已发布课表"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/schedule')">课表批次</button>
    </template>

    <div class="mp-stack">
      <div class="aa-reg-search">
        <input v-model.trim="kw" class="aa-input aa-input--grow" placeholder="按教学班名称/课程名筛选（本页已加载列表内筛选）" />
        <button class="mp-btn" :disabled="listLoading" @click="loadTeachingClasses">刷新列表</button>
      </div>
      <ErrorState v-if="listError" :description="listError" @retry="loadTeachingClasses" />
      <LoadingState v-else-if="listLoading" />
      <ul v-else-if="!teachingClassCode && filteredClasses.length" class="aa-cand-list">
        <li v-for="c in filteredClasses" :key="c.teachingClassCode" class="aa-cand-item">
          <span>{{ c.teachingClassName || c.teachingClassCode }}
            <span class="mp-note">· {{ c.courseCount }} 门课程<template v-if="c.isMerged"> · 合班</template></span>
          </span>
          <button class="mp-link" @click="pick(c)">查看课表</button>
        </li>
      </ul>
      <EmptyState v-else-if="!teachingClassCode && !filteredClasses.length" title="暂无匹配的教学班"
                 description="教学班派生自「教学任务」，请先在教学任务模块生成任务" />

      <template v-if="teachingClassCode">
        <div class="aa-filter">
          <button class="mp-link" @click="teachingClassCode = ''">‹ 重新选择教学班</button>
          <label class="aa-filter__item">
            学期
            <select v-model="termId" class="aa-select" @change="load">
              <option value="">当前已发布批次</option>
              <option v-for="t in terms" :key="t.termId" :value="t.termId">{{ t.yearCode }} 第 {{ t.termNo }} 学期</option>
            </select>
          </label>
          <label class="aa-filter__item">
            周次
            <input v-model.number="week" type="number" min="1" max="30" class="aa-input aa-input--sm" placeholder="全部周次" @keyup.enter="load" />
          </label>
          <button class="mp-btn mp-btn--primary" @click="load">查询</button>
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
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi, academicAffairsOrgApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTeachingClassScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard, AaScheduleGrid },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      kw: '', teachingClasses: [], listLoading: false, listError: '',
      teachingClassCode: this.$route.params.code || '', teachingClassName: '',
      termId: '', week: null,
      terms: [], slots: [], items: [], note: '', loading: false, error: ''
    }
  },
  computed: {
    filteredClasses() {
      const kw = this.kw.trim().toLowerCase()
      if (!kw) return this.teachingClasses
      return this.teachingClasses.filter((c) =>
        (c.teachingClassName || '').toLowerCase().includes(kw) ||
        (c.teachingClassCode || '').toLowerCase().includes(kw) ||
        (c.courses || []).some((n) => (n || '').toLowerCase().includes(kw)))
    }
  },
  created() {
    this.loadTerms()
    this.loadSlots()
    this.loadTeachingClasses()
    if (this.teachingClassCode) this.load()
  },
  methods: {
    async loadTeachingClasses() {
      this.listLoading = true
      this.listError = ''
      const res = await academicAffairsOrgApi.listTeachingClasses({ page: 1, pageSize: 200 })
      this.listLoading = false
      if (res.code === 0) this.teachingClasses = res.data.list || []
      else this.listError = res.message
    },
    pick(c) {
      this.teachingClassCode = c.teachingClassCode
      this.teachingClassName = c.teachingClassName
      this.$router.replace(`/admin/academic-affairs/schedule/teaching-class/${encodeURIComponent(this.teachingClassCode)}`).catch(() => {})
      this.load()
    },
    onItemClick(it) {
      toast.success(`${it.courseName || ''} · ${it.teacherName || ''} · ${it.classroom || ''} · ${it.startWeek}-${it.endWeek}周`)
    },
    async loadTerms() {
      const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
      if (res.code === 0) this.terms = res.data.list
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
