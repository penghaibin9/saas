<template>
  <ModulePageShell
:title="isAcademicTeacher ? '个人课表' : '教师课表'"
    :subtitle="isAcademicTeacher ? '点击课程可申请调课、停课或补课。' : '选择教师查看已发布的课程安排。'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="!isAcademicTeacher" @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <AaScheduleObjectBar
        :name="teacherName || (teacherKey ? '教师姓名待核对' : '课表查询范围')"
        :identity="termId ? '按所选学期查询' : '使用默认学期'"
        :source="isAcademicTeacher ? '仅可查看本人的授课安排。' : '仅显示已发布的课程安排。'"
        :status="teacherKey ? '仅供查看' : '未选择教师'"
        :owner="ctx.currentRole.roleName || '教务排课岗'"
        next-owner="任课教师申请调停课"
      />
      <div class="aa-filter">
        <label v-if="!isAcademicTeacher" class="aa-filter__item aa-filter__item--grow">
          教师
          <AppTeacherPicker v-model="teacherKey" :query="teacherKeyQuery" placeholder="搜索教师姓名/工号" @change="onTeacherChange" />
        </label>
        <AppButton v-if="!isAcademicTeacher && selfKey" @click="showSelfSchedule">查看本人课表</AppButton>
        <label class="aa-filter__item">
          学期
          <AppTermEntityPicker v-model="termId" placeholder="默认学期" />
        </label>
        <label class="aa-filter__item">
          周次
          <input v-model.number="week" type="number" min="1" max="30" class="aa-input aa-input--sm" placeholder="全部周次" />
        </label>
        <AppButton variant="primary" :disabled="!teacherKey" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!teacherKey" title="请先选择教师" description="可按姓名或工号搜索" />
      <template v-else>
        <AppSectionCard v-if="isSelfView" title="今天的授课安排" class="aa-today-card">
          <ErrorState v-if="todayError" :description="todayError" @retry="load" />
          <div v-else class="aa-today-head">
            <div v-if="todayItems.length">
              <strong>共 {{ todayItems.length }} 节课</strong>
              <p v-if="todayNote">{{ todayNote }}</p>
            </div>
            <span v-if="todayDate">{{ todayDate }}<template v-if="todayWeek"> · 第{{ todayWeek }}教学周</template></span>
          </div>
          <div v-if="!todayError && todayItems.length" class="aa-today-list">
            <button v-for="item in todayItems" :key="item.scheduleItemId" type="button" class="aa-today-item" @click="openTodayItem(item)">
              <b>第{{ item.slotNo }}节</b>
              <span><strong>{{ item.courseName }}</strong><small>{{ item.className || '教学班' }} · {{ item.classroom || '教室待定' }}</small></span>
              <em>查看课程与调停课 ›</em>
            </button>
          </div>
          <EmptyState v-else-if="!todayError" title="今天无课" :description="todayNote" />
        </AppSectionCard>
        <div class="aa-summary">
          <span v-if="weeklyHours" class="aa-summary__item">本学期周学时合计（近似）：<b>{{ weeklyHours }}</b></span>
          <p v-if="note" class="mp-note">{{ note }}</p>
        </div>
        <AppSectionCard title="课程安排">
          <AaScheduleGrid :items="items" :slots="slots" :editable="false" @item-click="onItemClick" />
        </AppSectionCard>
        <AppSectionCard v-if="selectedItem" title="课程详情" class="aa-item-detail">
          <div class="aa-item-detail__head">
            <div>
              <strong>{{ selectedItem.courseName || '课程' }}</strong>
              <p>{{ selectedItem.className || '教学班' }} · {{ selectedItem.teacherName || teacherName || '教师待确认' }}</p>
            </div>
            <span>{{ weekdayLabel(selectedItem.weekday) }} 第{{ selectedItem.slotNo }}节</span>
          </div>
          <div class="aa-item-detail__facts">
            <span>周次：{{ selectedItem.startWeek }}–{{ selectedItem.endWeek }}周（{{ parityLabel(selectedItem.weekParity) }}）</span>
            <span>教室：{{ selectedItem.classroom || '待定' }}</span>
          </div>
          <div v-if="isSelfView" class="aa-item-detail__actions">
            <AppButton variant="primary" @click="applyChange('ADJUST')">申请调课</AppButton>
            <AppButton :disabled="!selectedOccurrenceWeek" @click="applyChange('STOP')">申请停课</AppButton>
            <AppButton :disabled="!selectedOccurrenceWeek" @click="applyChange('MAKEUP')">申请补课</AppButton>
          </div>
          <p v-if="isSelfView && !selectedOccurrenceWeek" class="mp-note">停课或补课须先选周次，调课可在下一步选择单次或周期调整。</p>
          <p v-else-if="isSelfView" class="mp-note">第{{ selectedOccurrenceWeek }}教学周的申请先交学院审核，教务处终审通过后更新课表。</p>
          <p v-else class="mp-note">仅任课教师本人可申请调课、停课或补课。</p>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 教师课表（/admin/academic-affairs/schedule/teacher/:teacherKey?）：13B 课表管理 Tier1 R2。
 * GET /academic-affairs/schedule/teacher/{teacherKey}?termId=&week=；教师本人仅能查看自己（403002）。
 * 教师目录暂无统一主数据表（教务域历史沿用 teacher_key 自由文本标识），沿用既有「三视图」页同款
 * 工号输入约定，不新造教师选择器接口。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppTeacherPicker, AppTermEntityPicker } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'
import AaScheduleObjectBar from '../components/AaScheduleObjectBar.vue'

export default {
  name: 'AaTeacherScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppTeacherPicker, AppTermEntityPicker, AaScheduleGrid, AaScheduleObjectBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    const u = currentUserFromToken() || {}
    return {
      teacherKey: this.$route.params.teacherKey || '', teacherName: '', teacherKeyQuery: { valueField: 'loginName' },
      selfKey: String(u.loginName || u.userId || ''),
      termId: '', week: null,
      slots: [], items: [], weeklyHours: 0, note: '', loading: false, error: '',
      todayItems: [], todayDate: '', todayWeek: null, calendarSource: '', todayError: '', selectedItem: null
    }
  },
  created() {
    this.loadSlots()
    if (this.isAcademicTeacher && this.selfKey) {
      this.teacherKey = this.selfKey
      this.teacherName = '本人'
      this.load()
    } else if (this.teacherKey) this.load()
  },
  computed: {
    isAcademicTeacher() {
      return String(this.ctx?.currentRole?.roleCode || this.ctx?.currentRole?.roleType || '').toUpperCase() === 'ACADEMIC_TEACHER'
    },
    isSelfView() { return this.isSameTeacherKey(this.teacherKey) },
    selectedOccurrenceWeek() {
      const week = Number(this.week || this.selectedItem?.weekNo || 0)
      return Number.isInteger(week) && week > 0 ? week : null
    },
    todayNote() {
      if (this.calendarSource === 'HOLIDAY') return '今天为校历节假日，不安排上课。'
      if (this.calendarSource === 'SWAP_SOURCE') return '今天为校历调休停课日，不安排上课。'
      if (this.calendarSource === 'OUT_OF_TERM') return '今天不在当前学期教学日期范围内。'
      return this.todayItems.length ? '点击课程查看详情或申请调停课。' : '可在下方查看其他周次的课程安排。'
    }
  },
  methods: {
    onTeacherChange(value, items) {
      const item = items?.[0]
      const teacher = item?.raw || item || {}
      this.teacherName = teacher.realName || teacher.teacherName || item?.label || ''
      if (value) this.load()
    },
    showSelfSchedule() {
      this.teacherKey = this.selfKey
      this.teacherName = '本人'
      this.load()
    },
    isSameTeacherKey(value) {
      return String(value || '').trim() === String(this.selfKey || '').trim()
    },
    openTodayItem(item) {
      this.selectedItem = { ...item, itemId: item.itemId || item.scheduleItemId }
      this.$nextTick(() => document.querySelector('.aa-item-detail')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }))
    },
    onItemClick(it) {
      this.selectedItem = it
    },
    weekdayLabel(value) { return `周${'一二三四五六日'[Number(value) - 1] || (value ? '待确认' : '')}` },
    parityLabel(value) { return { ALL: '全周', ODD: '单周', EVEN: '双周' }[value] || '全周' },
    applyChange(changeType) {
      const originItemId = this.selectedItem?.itemId || this.selectedItem?.scheduleItemId
      if (!originItemId) {
        toast.error('无法确认原课程安排，请刷新课表后重试')
        return
      }
      if (['STOP', 'MAKEUP'].includes(changeType) && !this.selectedOccurrenceWeek) {
        toast.error('请先选择具体教学周，再申请停课或补课')
        return
      }
      this.$router.push({
        path: '/admin/academic-affairs/schedule-change/apply',
        query: {
          originItemId: String(originItemId),
          changeType,
          occurrenceWeek: String(this.selectedOccurrenceWeek || '')
        }
      })
    },
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async load() {
      if (!this.teacherKey) return
      this.loading = true
      this.error = ''
      this.todayError = ''
      const [res, todayRes] = await Promise.all([
        academicAffairsApi.getTeacherSchedule(this.teacherKey, {
          termId: this.termId || undefined, week: this.week || undefined
        }),
        this.isSameTeacherKey(this.teacherKey)
          ? academicAffairsApi.getMyTeacherToday().catch((error) => {
              this.todayError = error?.message || '今日课表暂不可用'
              return null
            })
          : Promise.resolve(null)
      ])
      this.loading = false
      if (res.code === 0) {
        this.items = res.data.items || []
        if (res.data.teacherName) this.teacherName = res.data.teacherName
        this.selectedItem = null
        this.weeklyHours = res.data.weeklyHours || 0
        this.note = res.data.note || ''
        if (this.isSelfView && todayRes?.code !== 0 && !this.todayError) this.todayError = todayRes?.message || '今日课表读取失败，请重试；下方周课表仍可查看。'
        this.todayItems = todayRes?.code === 0 ? (todayRes.data.todayItems || []) : []
        this.todayDate = todayRes?.code === 0 ? (todayRes.data.todayDate || '') : ''
        this.todayWeek = todayRes?.code === 0 ? (todayRes.data.currentWeek ?? null) : null
        this.calendarSource = todayRes?.code === 0 ? (todayRes.data.calendarSource || '') : ''
        this.$router.replace({
          path: `/admin/academic-affairs/schedule/teacher/${this.teacherKey}`,
          query: { ...(this.$route?.query || {}) }
        }).catch(() => {})
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
.aa-filter { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-filter__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); min-width: 160px; }
.aa-input, .aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 120px; }
.aa-summary { margin-bottom: 4px; }
.aa-summary__item { font-size: 13px; color: var(--text-700, #4e5969); }
.aa-today-card { margin-bottom: 14px; }
.aa-today-head { display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; }
.aa-today-head strong { color: var(--text-900, #1f2329); font-size: 16px; }
.aa-today-head p { margin: 4px 0 0; color: var(--text-500, #86909c); font-size: 12px; }
.aa-today-head > span { color: var(--success-600, #16a34a); font-size: 12px; }
.aa-today-list { display: grid; gap: 8px; margin-top: 14px; }
.aa-today-item { display: grid; grid-template-columns: 90px minmax(0, 1fr) auto; gap: 14px; align-items: center; width: 100%; padding: 12px 14px; border: 1px solid var(--border-200, #e5e6eb); border-left: 4px solid var(--success-500, #22c55e); border-radius: 10px; background: #fff; color: inherit; text-align: left; cursor: pointer; }
.aa-today-item > b { color: var(--success-600, #16a34a); }
.aa-today-item span strong, .aa-today-item span small { display: block; }
.aa-today-item span small { margin-top: 3px; color: var(--text-500, #86909c); }
.aa-today-item em { color: var(--primary-600, #2563eb); font-style: normal; font-size: 12px; }
.aa-item-detail { margin-top: 14px; }
.aa-item-detail__head { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.aa-item-detail__head strong { color: var(--text-900, #1f2329); font-size: 17px; }
.aa-item-detail__head p { margin: 4px 0 0; color: var(--text-500, #86909c); font-size: 13px; }
.aa-item-detail__head > span { color: var(--primary-600, #2563eb); font-weight: 600; }
.aa-item-detail__facts { display: flex; flex-wrap: wrap; gap: 12px 28px; margin-top: 14px; color: var(--text-700, #4e5969); font-size: 13px; }
.aa-item-detail__actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
</style>
