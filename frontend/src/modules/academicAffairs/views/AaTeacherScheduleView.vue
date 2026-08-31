<template>
  <ModulePageShell
    title="教师课表"
    subtitle="按教师工号查看当前已发布课表；教师本人仅能查看自己，教务处/学院教务可查任意教师"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item aa-filter__item--grow">
          教师
          <AppTeacherPicker v-model="teacherKey" :query="teacherKeyQuery" placeholder="搜索教师姓名/工号" @change="onTeacherChange" />
        </label>
        <AppButton v-if="selfKey" @click="showSelfSchedule">查看本人课表</AppButton>
        <label class="aa-filter__item">
          学期
          <AppTermEntityPicker v-model="termId" placeholder="当前已发布批次" />
        </label>
        <label class="aa-filter__item">
          周次
          <input v-model.number="week" type="number" min="1" max="30" class="aa-input aa-input--sm" placeholder="全部周次" />
        </label>
        <AppButton variant="primary" :disabled="!teacherKey" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!teacherKey" title="请先输入教师工号" description="或点击「查看本人课表」" />
      <template v-else>
        <AppSectionCard v-if="isSelfView" title="今天的授课安排" class="aa-today-card">
          <div class="aa-today-head">
            <div>
              <strong>{{ todayItems.length ? `今天有 ${todayItems.length} 节课` : '今天没有授课安排' }}</strong>
              <p>{{ todayNote }}</p>
            </div>
            <span v-if="todayDate">{{ todayDate }}<template v-if="todayWeek"> · 第{{ todayWeek }}教学周</template></span>
          </div>
          <div v-if="todayItems.length" class="aa-today-list">
            <button v-for="item in todayItems" :key="item.scheduleItemId" type="button" class="aa-today-item" @click="openTodayItem(item)">
              <b>第{{ item.slotNo }}节</b>
              <span><strong>{{ item.courseName }}</strong><small>{{ item.className || '教学班' }} · {{ item.classroom || '教室待定' }}</small></span>
              <em>查看课位与调停课 ›</em>
            </button>
          </div>
          <EmptyState v-else title="今天无课" :description="todayNote" />
        </AppSectionCard>
        <div class="aa-summary">
          <span v-if="weeklyHours" class="aa-summary__item">本学期周学时合计（近似）：<b>{{ weeklyHours }}</b></span>
          <p v-if="note" class="mp-note">{{ note }}</p>
        </div>
        <AppSectionCard :title="`${teacherName || '本人'} · 周课表`">
          <AaScheduleGrid :items="items" :slots="slots" :editable="false" @item-click="onItemClick" />
        </AppSectionCard>
        <AppSectionCard v-if="selectedItem" title="课位详情" class="aa-item-detail">
          <div class="aa-item-detail__head">
            <div>
              <strong>{{ selectedItem.courseName || '课程' }}</strong>
              <p>{{ selectedItem.className || '教学班' }} · {{ selectedItem.teacherName || teacherKey }}</p>
            </div>
            <span>{{ weekdayLabel(selectedItem.weekday) }} 第{{ selectedItem.slotNo }}节</span>
          </div>
          <div class="aa-item-detail__facts">
            <span>周次：{{ selectedItem.startWeek }}–{{ selectedItem.endWeek }}周（{{ parityLabel(selectedItem.weekParity) }}）</span>
            <span>教室：{{ selectedItem.classroom || '待定' }}</span>
          </div>
          <div v-if="isSelfView" class="aa-item-detail__actions">
            <AppButton variant="primary" @click="applyChange('ADJUST')">申请调课</AppButton>
            <AppButton @click="applyChange('STOP')">申请停课</AppButton>
            <AppButton @click="applyChange('MAKEUP')">申请补课</AppButton>
          </div>
          <p v-else class="mp-note">当前为管理查询视图；只有任课教师本人可从课位发起调停课。</p>
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

export default {
  name: 'AaTeacherScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppTeacherPicker, AppTermEntityPicker, AaScheduleGrid },
  props: { ctx: { type: Object, required: true } },
  data() {
    const u = currentUserFromToken() || {}
    return {
      teacherKey: this.$route.params.teacherKey || '', teacherName: '', teacherKeyQuery: { valueField: 'loginName' },
      selfKey: String(u.loginName || u.userId || ''),
      termId: '', week: null,
      slots: [], items: [], weeklyHours: 0, note: '', loading: false, error: '',
      todayItems: [], todayDate: '', todayWeek: null, calendarSource: '', selectedItem: null
    }
  },
  created() {
    this.loadSlots()
    if (this.teacherKey) this.load()
  },
  computed: {
    isSelfView() { return this.isSameTeacherKey(this.teacherKey) },
    todayNote() {
      if (this.calendarSource === 'HOLIDAY') return '学校校历标记今天为节假日，正式课表不执行。'
      if (this.calendarSource === 'SWAP_SOURCE') return '学校校历标记今天为调休停课日，正式课表不执行。'
      if (this.calendarSource === 'OUT_OF_TERM') return '今天不在当前学期教学日期范围内。'
      return this.todayItems.length ? '来自同一份正式课表和校历课次投影。' : '已核对学校校历和本人最新正式课表。'
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
    weekdayLabel(value) { return `周${'一二三四五六日'[Number(value) - 1] || value || ''}` },
    parityLabel(value) { return { ALL: '全周', ODD: '单周', EVEN: '双周' }[value] || '全周' },
    applyChange(changeType) {
      const originItemId = this.selectedItem?.itemId || this.selectedItem?.scheduleItemId
      if (!originItemId) {
        toast.error('该课位缺少正式课表标识，请刷新本人课表后重试')
        return
      }
      this.$router.push({
        path: '/admin/academic-affairs/schedule-change/apply',
        query: { originItemId: String(originItemId), changeType }
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
      const [res, todayRes] = await Promise.all([
        academicAffairsApi.getTeacherSchedule(this.teacherKey, {
          termId: this.termId || undefined, week: this.week || undefined
        }),
        this.isSameTeacherKey(this.teacherKey)
          ? academicAffairsApi.getMyTeacherToday()
          : Promise.resolve(null)
      ])
      this.loading = false
      if (res.code === 0) {
        this.items = res.data.items || []
        if (res.data.teacherName) this.teacherName = res.data.teacherName
        this.selectedItem = null
        this.weeklyHours = res.data.weeklyHours || 0
        this.note = res.data.note || ''
        this.todayItems = todayRes?.code === 0 ? (todayRes.data.todayItems || []) : []
        this.todayDate = todayRes?.code === 0 ? (todayRes.data.todayDate || '') : ''
        this.todayWeek = todayRes?.code === 0 ? (todayRes.data.currentWeek ?? null) : null
        this.calendarSource = todayRes?.code === 0 ? (todayRes.data.calendarSource || '') : ''
        this.$router.replace(`/admin/academic-affairs/schedule/teacher/${this.teacherKey}`).catch(() => {})
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
