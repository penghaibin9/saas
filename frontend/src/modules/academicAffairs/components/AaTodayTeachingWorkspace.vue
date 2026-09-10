<template>
  <AaOverviewPageFrame title="今日教学运行" subtitle="今日课次只读正式课表，不手工造课次">
    <template #actions><AppButton @click="openOverview">返回运行总览</AppButton><AppButton variant="primary" :loading="loading" @click="load">刷新正式课表</AppButton></template>
    <section class="m02-object">
      <div><strong>{{ className || '请选择班级' }} · 正式课表</strong><p>{{ term.termName || term.termCode || '当前学期待核对' }} · 第 {{ week }} 周<span v-if="schedule.batchIds?.length"> · 发布批次 {{ schedule.batchIds.join('、') }}</span></p><small>来源：当前班级已发布课表；此入口只读查看。<span class="m02-tag">{{ loading ? '正在核对' : schedule.batchId || schedule.batchIds?.length ? '已发布' : '待核对来源' }}</span></small></div>
      <dl><div><dt>当前责任</dt><dd>{{ ctx.currentRole?.roleName || '当前岗位' }}</dd></div><div><dt>下一责任</dt><dd>课程任课教师 · 调整须走调停课审批</dd></div></dl>
    </section>
    <section class="m02-card">
      <header><h2>指定对象 · 正式课表视图</h2></header>
      <div class="m02-toolbar m02-schedule-filters">
        <div class="m02-class-picker"><AppClassPicker v-model="classId" placeholder="选择班级" @change="changeClass" /></div>
        <select v-model.number="week" aria-label="选择教学周" @change="changeWeek"><option v-for="n in weekCount" :value="n" :key="n">第 {{ n }} 周{{ weekRange(n) }}</option></select>
        <small>选择班级与教学周，查看正式课位</small>
      </div>
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!classId" title="请选择班级查看正式课表" description="从有权限的班级中选择，页面会保留班级和教学周。" />
      <template v-else>
        <p v-if="schedule.note" class="m02-schedule-note">{{ schedule.note }}</p>
        <div class="m02-scroll" role="region" aria-label="正式周课表，可横向滚动" tabindex="0"><table class="m02-schedule-table"><thead><tr><th>节次</th><th v-for="day in weekdays" :key="day">{{ dayLabel(day) }}</th></tr></thead><tbody>
          <tr v-for="slot in slots" :key="slot.slotNo"><th><span :title="slot.slotName">第 {{ slot.slotNo }} 节</span><small>{{ slot.startTime || '时间待配置' }}</small></th><td v-for="day in weekdays" :key="day">
            <button v-for="item in itemsAt(day, slot.slotNo)" :key="item.itemId" class="m02-course" :class="{ 'is-alternate': alternateCourses.includes(item.courseName) }" @click="openItem(item)"><strong>{{ item.courseName }}</strong><span>{{ item.className || className }} · {{ item.teacherName || '任课教师待核对' }}</span><small>{{ item.classroom || '教室待核对' }} · 第{{ item.startWeek }}–{{ item.endWeek }}周{{ item.weekParity === 'ODD' ? '（单周）' : item.weekParity === 'EVEN' ? '（双周）' : '' }}</small></button>
            <span v-if="!itemsAt(day, slot.slotNo).length" class="m02-vacant">空课位</span>
          </td></tr>
          <tr v-if="!slots.length"><td :colspan="weekdays.length + 1" class="m02-schedule-note">尚未配置正式作息节次</td></tr>
        </tbody></table></div>
      </template>
    </section>
    <section class="m02-related"><span>关联办理 / 四级下钻</span><AppButton v-if="canOpen('/admin/academic-affairs/schedule')" @click="go('/admin/academic-affairs/schedule')">课表批次</AppButton><AppButton v-if="canOpen('/admin/academic-affairs?panel=scheduleChangeReminders')" @click="go('/admin/academic-affairs?panel=scheduleChangeReminders')">调停课提醒</AppButton><AppButton @click="go('/admin/academic-affairs?panel=todayCourses')">今日课程明细</AppButton></section>
    <AppDrawer :visible="!!selectedItem" title="正式课位 · 对象详情" mode="modal" size="large" @update:visible="closeItem">
      <template v-if="selectedItem"><h2>{{ selectedItem.courseName }}</h2><dl class="m02-item-detail"><div v-for="field in selectedFields" :key="field.label"><dt>{{ field.label }}</dt><dd>{{ field.value || '未提供' }}</dd></div></dl><p class="m02-note">调整时间、教室或任课教师须通过原调停课流程，当前视图不会改写正式课表。</p><AppButton @click="closeItem">返回原课表位置</AppButton></template>
    </AppDrawer>
  </AaOverviewPageFrame>
</template>

<script>
import AaOverviewPageFrame from './AaOverviewPageFrame.vue'
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppClassPicker } from '@/components/common'
import { LoadingState, ErrorState, EmptyState } from '@/components/business'
import { academicAffairsApi } from '../api/academic-affairs.api'
import { academicAffairsPickerAdapters } from '../pickerAdapters'
import { request, currentUserFromToken } from '@/services/http/client'
import { academicIdentity } from '../academicFlowContext'
import { canEnterRoute } from '@/security/permissionGate'
import { safeBusinessMessage } from '@/utils/presentationSafety'
const scalar = v => typeof v === 'string' ? v : ''
export default {
  name: 'AaTodayTeachingWorkspace', components: { AaOverviewPageFrame, AppButton, AppDrawer, AppClassPicker, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } }, inject: { academicFlow: { default: null } },
  data: () => ({ classId: '', className: '', week: 1, term: {}, schedule: {}, slots: [], loading: false, error: '', generation: 0, initialized: false }),
  computed: {
    identity() { return academicIdentity(currentUserFromToken(), this.ctx) },
    weekCount() { return Math.max(1, Math.min(30, this.term.teachingWeeks || 20)) },
    items() { return this.schedule.items || [] },
    alternateCourses() { return [...new Set(this.items.map(r => r.courseName))].sort().filter((_, i) => i % 2 === 0) },
    weekdays() { return this.items.some(r => Number(r.weekday) > 5) ? [1, 2, 3, 4, 5, 6, 7] : [1, 2, 3, 4, 5] },
    selectedItem() { return this.items.find(r => String(r.itemId) === scalar(this.$route.query.itemId)) || null },
    selectedFields() { const r = this.selectedItem || {}; return [{ label: '课位 ID', value: r.itemId }, { label: '正式批次', value: r.batchId || this.schedule.batchId }, { label: '教学班', value: r.teachingClassName || r.className || this.className }, { label: '任课教师', value: r.teacherName }, { label: '上课地点', value: r.classroom }, { label: '上课时间', value: `${this.dayLabel(Number(r.weekday))} · 第 ${r.slotNo} 节` }, { label: '有效周次', value: `${r.startWeek}–${r.endWeek} 周` }] }
  },
  created() { this.initialize() }, beforeUnmount() { this.generation++ },
  watch: {
    '$route.query.classId'() { if (this.initialized) { this.sync(); this.load() } },
    '$route.query.week'() { if (this.initialized) { this.sync(); this.load() } },
    identity() { this.initialized = false; this.className = ''; this.initialize() }
  },
  methods: {
    sync() { this.classId = scalar(this.$route.query.classId); const n = Number(this.$route.query.week); this.week = Number.isInteger(n) && n >= 1 && n <= 30 ? n : 1 },
    async initialize() {
      const ticket = ++this.generation, identity = this.identity
      this.loading = true; this.error = ''; this.schedule = {}; this.slots = []; this.sync()
      try {
        if (this.$route.query.classId !== undefined && (!this.classId || !/^\d+$/.test(this.classId))) throw new Error('班级参数不完整，请重新选择班级')
        if (this.$route.query.week !== undefined && (!scalar(this.$route.query.week) || !/^\d+$/.test(scalar(this.$route.query.week)) || Number(this.$route.query.week) < 1 || Number(this.$route.query.week) > 30)) throw new Error('教学周参数不完整，请重新选择')
        const [term, slots, classes] = await Promise.all([request('/academic-affairs/terms/current'), academicAffairsApi.getTimeSlots(), this.classId ? Promise.resolve([]) : academicAffairsPickerAdapters.class.search('')])
        if (ticket !== this.generation || identity !== this.identity) return
        if (slots.code !== 0) throw new Error(slots.message)
        this.term = term || {}; this.slots = Array.isArray(slots.data) ? slots.data : slots.data?.items || []
        if (this.week > this.weekCount) throw new Error('教学周超出当前学期范围，请重新选择')
        if (!this.classId && classes.length) { this.classId = String(classes[0].value); this.className = classes[0].label }
        if (!this.$route.query.week && term?.startDate) { const elapsed = Math.floor((Date.now() - new Date(String(term.startDate).slice(0, 10) + 'T00:00:00').getTime()) / 86400000 / 7) + 1; this.week = Math.min(this.weekCount, Math.max(1, elapsed)) }
        await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, classId: this.classId || undefined, week: String(this.week) } })
        this.initialized = true; await this.load()
      } catch (e) { if (ticket === this.generation && identity === this.identity) { this.error = safeBusinessMessage(e?.message, '正式课表初始化失败'); this.loading = false } }
    },
    async load() {
      if (!this.initialized) { return this.initialize() }
      const ticket = ++this.generation, identity = this.identity, classId = this.classId, week = this.week
      this.loading = true; this.error = ''; this.schedule = {}
      try {
        if (this.$route.query.classId !== undefined && (!scalar(this.$route.query.classId) || !/^\d+$/.test(scalar(this.$route.query.classId)))) throw new Error('班级参数不完整，请重新选择班级')
        if (this.$route.query.week !== undefined && (!scalar(this.$route.query.week) || !/^\d+$/.test(scalar(this.$route.query.week)) || Number(this.$route.query.week) < 1 || Number(this.$route.query.week) > this.weekCount)) throw new Error('教学周超出当前学期范围，请重新选择')
        if (!classId) return
        const response = await academicAffairsApi.getClassSchedule(classId, { termId: this.term.termId || undefined, week })
        if (ticket !== this.generation || identity !== this.identity || classId !== this.classId || week !== this.week) return
        if (response.code !== 0 || !Array.isArray(response.data?.items)) throw new Error(response.message || '课表返回不完整')
        this.schedule = response.data; this.className = response.data.className || this.className
      } catch (e) { if (ticket === this.generation && identity === this.identity) this.error = safeBusinessMessage(e?.message, '课表读取失败') }
      finally { if (ticket === this.generation && identity === this.identity) this.loading = false }
    },
    changeClass(_value, options) { this.className = options?.[0]?.label || ''; this.updateRoute() },
    changeWeek() { this.updateRoute() },
    updateRoute() { this.generation++; this.schedule = {}; this.$router.push({ path: this.$route.path, query: { ...this.$route.query, classId: this.classId || undefined, week: String(this.week), itemId: undefined } }) },
    itemsAt(day, slot) { return this.items.filter(r => Number(r.weekday) === day && Number(r.slotNo) === Number(slot)) },
    dayDate(day, week = this.week) { if (!this.term.startDate) return null; const start = new Date(String(this.term.startDate).slice(0, 10) + 'T00:00:00'); if (!Number.isFinite(start.getTime())) return null; start.setDate(start.getDate() - (start.getDay() + 6) % 7 + (week - 1) * 7 + day - 1); return start },
    dayLabel(day) { const date = this.dayDate(day); return `周${['一', '二', '三', '四', '五', '六', '日'][day - 1]}${date ? ' ' + String(date.getDate()).padStart(2, '0') : ''}` },
    weekRange(n) { const start = this.dayDate(1, n), end = this.dayDate(7, n); return start && end ? ` · ${start.getMonth() + 1}月${start.getDate()}日—${end.getMonth() + 1}月${end.getDate()}日` : '' },
    openItem(item) { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, itemId: String(item.itemId) } }) },
    closeItem() { this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, itemId: undefined } }) },
    canOpen(target) { const route = this.$router.resolve(target); return !!route.matched.length && route.matched.every(r => canEnterRoute(r.meta)) },
    go(target) { if (!this.canOpen(target)) return; const route = this.$router.resolve(target), returnToken = this.academicFlow?.captureReturn(); this.$router.push({ path: route.path, query: { ...route.query, ...(returnToken ? { returnToken } : {}) } }) },
    openOverview() { this.$router.push('/admin/academic-affairs') }
  }
}
</script>

<style scoped>
.m02-object { display:flex; align-items:center; justify-content:space-between; gap:24px; padding:14px 16px; background:var(--bg-card); border:1px solid var(--border-base); border-left:3px solid var(--pri); border-radius:11px; }.m02-object strong { font-size:15px; }.m02-object p { font-size:11px; color:var(--text-secondary); margin:6px 0; }.m02-object small { font-size:11px; color:var(--text-secondary); }.m02-object dl { display:flex; gap:24px; margin:0; }.m02-object dt { color:var(--text-secondary); font-size:11px; }.m02-object dd { font-size:12px; margin:4px 0 0; font-weight:600; }.m02-object .m02-tag { margin-left:6px; }
.m02-class-picker { width:180px; }.m02-schedule-filters select { height:40px; padding:0 10px; color:var(--text-primary); border:1px solid var(--border-base); border-radius:6px; background:var(--bg-card); font:inherit; }.m02-schedule-note { margin:0; padding:10px 16px; font-size:12px; color:var(--text-secondary); }
.m02-schedule-table { width:100%; min-width:680px; border-collapse:collapse; table-layout:fixed; font-size:12px; }.m02-schedule-table th,.m02-schedule-table td { border:1px solid var(--border-base); }.m02-schedule-table thead th { padding:12px 6px; background:var(--bg-soft,var(--pri-bg)); font-weight:400; }.m02-schedule-table tr > :first-child { width:65px; border-left:0; }.m02-schedule-table tr > :last-child { border-right:0; }.m02-schedule-table tbody th { background:var(--bg-page); color:var(--text-secondary); font-size:11px; font-weight:400; }.m02-schedule-table th small { display:block; font-size:10px; margin-top:6px; }.m02-schedule-table td { height:90px; padding:6px; vertical-align:middle; text-align:center; }.m02-course { display:flex; flex-direction:column; justify-content:center; gap:5px; width:100%; min-height:76px; padding:9px; text-align:left; border:0; border-left:3px solid var(--pri); border-radius:5px; background:var(--pri-bg); color:var(--text-primary); cursor:pointer; font:inherit; }.m02-course strong { font-size:12px; }.m02-course span,.m02-course small { font-size:10px; color:var(--text-secondary); line-height:1.5; }.m02-course.is-alternate { background:var(--aa-success-bg); border-left-color:var(--success-color,#307653); }.m02-course + .m02-course { margin-top:5px; }.m02-vacant { color:var(--text-secondary); font-size:11px; }
.m02-related { display:flex; align-items:center; gap:8px; flex-wrap:wrap; border:1px solid var(--border-base); background:var(--bg-card); border-radius:10px; padding:16px; }.m02-related > span { color:var(--text-secondary); font-size:12px; }.m02-item-detail { display:grid; gap:15px; padding:12px 0; }.m02-item-detail > div { display:grid; grid-template-columns:110px 1fr; gap:12px; }.m02-item-detail dt { color:var(--text-secondary); }.m02-item-detail dd { margin:0; }
@container academic-body (max-width:760px) { .m02-object { align-items:flex-start; flex-direction:column; gap:12px; } }
.m02-object { padding:12px 16px; }.m02-object p { margin:4px 0; line-height:1.5; }.m02-object small { line-height:1.5; }
</style>
