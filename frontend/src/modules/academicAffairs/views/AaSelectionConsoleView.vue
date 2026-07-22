<template>
  <ModulePageShell
    title="选课管理 · 教务处控制台"
    :subtitle="'批次生命周期：草稿→发布→开选→截止→锁定→归档 · 共 ' + pagination.total + ' 个批次'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="ghost" @click="runTimeTick">按时间批量开选/截止</AppButton>
      <AppButton variant="primary" @click="openCreate">新建批次</AppButton>
    </template>

    <div class="aasel-layout">
      <!-- 左：批次列表 -->
      <div class="aasel-list">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无选课批次" description="点击右上角「新建批次」创建" />
        <ul v-else class="aasel-batches">
          <li
            v-for="b in rows" :key="b.batchId"
            :class="['aasel-batch', { 'is-active': current && current.batchId === b.batchId }]"
            @click="select(b)"
          >
            <div class="aasel-batch-name">{{ b.batchName }}</div>
            <StatusTag :type="statusType(b.status)" :label="statusLabel(b.status)" dot />
          </li>
        </ul>
      </div>

      <!-- 右：选中批次详情 -->
      <div class="aasel-detail">
        <EmptyState v-if="!current" title="选择一个批次" description="从左侧列表选择批次以管理可选课程与名单" />
        <template v-else>
          <div class="aasel-detail-head">
            <div>
              <div class="aasel-detail-title">{{ current.batchName }}</div>
              <StatusTag :type="statusType(current.status)" :label="statusLabel(current.status)" dot />
            </div>
            <div class="aasel-actions">
              <AppButton v-if="current.status === 'DRAFT'" variant="primary" size="small" @click="lifecycle('publishBatch', '发布')">发布</AppButton>
              <AppButton v-if="current.status === 'PUBLISHED'" variant="primary" size="small" @click="lifecycle('openBatch', '开选')">开选</AppButton>
              <AppButton v-if="current.status === 'OPEN'" variant="warning" size="small" @click="lifecycle('closeBatch', '截止')">截止</AppButton>
              <AppButton v-if="current.status === 'CLOSED'" variant="primary" size="small" @click="lifecycle('lockBatch', '锁定名单')">锁定名单</AppButton>
              <AppButton v-if="current.status === 'LOCKED'" variant="ghost" size="small" @click="lifecycle('archiveBatch', '归档')">归档</AppButton>
            </div>
          </div>

          <!-- 统计条 -->
          <div v-if="stats" class="aasel-stats">
            <span>课程 {{ stats.courseCount }}</span>
            <span>容量 {{ stats.totalCapacity }}</span>
            <span>已选 {{ stats.totalSelected }}</span>
            <span>填充率 {{ (stats.fillRate * 100).toFixed(0) }}%</span>
            <span :class="{ 'is-warn': stats.lowEnrollCount }">低人数 {{ stats.lowEnrollCount }}</span>
          </div>

          <div class="aasel-courses-head">
            <span>选课轮次（不建轮次 = 全程先到先得）</span>
            <AppButton v-if="!['LOCKED','ARCHIVED'].includes(current.status)" size="small" variant="ghost" @click="openAddRound">+ 添加轮次</AppButton>
          </div>
          <DataTable v-if="rounds.length" :columns="roundColumns" :rows="rounds" row-key="roundId">
            <template #cell-round="{ row }">第{{ row.roundNo }}轮 · {{ row.roundName }}</template>
            <template #cell-mode="{ row }">
              <StatusTag :type="row.mode === 'LOTTERY' ? 'warning' : 'primary'" :label="row.mode === 'LOTTERY' ? '抽签' : '先到先得'" dot />
            </template>
            <template #cell-ctrl="{ row }">{{ row.allowEnroll ? '可选' : '禁选' }} / {{ row.allowDrop ? '可退' : '禁退' }}</template>
            <template #cell-status="{ row }">
              <StatusTag :type="roundStatusType(row.status)" :label="roundStatusLabel(row.status)" dot />
            </template>
            <template #cell-ops="{ row }">
              <button v-if="['DRAFT','CLOSED'].includes(row.status)" class="mp-link" @click="roundAction(row, 'openRound', '开启轮次')">开启</button>
              <button v-if="row.status === 'OPEN'" class="mp-link" @click="roundAction(row, 'closeRound', '关闭轮次')">关闭</button>
              <button v-if="row.status === 'CLOSED' && row.mode === 'LOTTERY'" class="mp-link is-danger" @click="roundAction(row, 'drawRound', '抽签摇号（一次性，不可重摇）')">摇号</button>
            </template>
          </DataTable>
          <AppInlineAlert v-if="drawResult" type="success"
                          :description="'摇号完成：中签 ' + drawResult.totalWinners + ' 人，未中签 ' + drawResult.totalLosers + ' 人（' + drawResult.courses.map(c => `${c.courseName} ${c.winners}/${c.applicants}`).join('；') + '）'" />

          <div class="aasel-courses-head">
            <span>可选课程供给</span>
            <AppButton v-if="['DRAFT','PUBLISHED'].includes(current.status)" size="small" variant="ghost" @click="openAddCourse">+ 添加课程</AppButton>
          </div>
          <EmptyState v-if="!courses.length" title="未配置课程" description="添加至少一门课程后方可发布" />
          <DataTable v-else :columns="courseColumns" :rows="courses" row-key="selectionCourseId">
            <template #cell-course="{ row }">
              <div class="mp-cell-main">{{ row.courseName }}</div>
              <div class="mp-cell-sub">{{ row.teacherName || '未派课' }} · {{ row.credit }} 学分</div>
            </template>
            <template #cell-fill="{ row }">{{ row.selectedCount }} / {{ row.capacity }}（余 {{ row.remain }}）</template>
            <template #cell-status="{ row }">
              <StatusTag :type="row.status === 'OPEN' ? 'success' : 'default'" :label="row.status === 'OPEN' ? '开放' : '已取消'" dot />
            </template>
            <template #cell-ops="{ row }">
              <button class="mp-link" @click="openRoster(row)">名单</button>
              <button v-if="current.status === 'CLOSED' && row.status === 'OPEN'" class="mp-link is-danger" @click="cancelCourse(row)">取消开课</button>
            </template>
          </DataTable>
        </template>
      </div>
    </div>

    <!-- 建批次 -->
    <AppDrawer :visible="createVisible" title="新建选课批次" @close="createVisible = false">
      <div class="aasel-form">
        <AppFormItem label="批次名称" required>
          <AppTextInput v-model="form.batchName" placeholder="如 2024秋公共选修课选课" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="选课学分上限">
          <AppNumberInput v-model="form.maxCredits" :min="0" :max="50" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="备注">
          <AppTextarea v-model="form.remark" placeholder="选填" :disabled="saving" />
        </AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <!-- 加课程 -->
    <AppDrawer :visible="courseVisible" title="添加可选课程" @close="courseVisible = false">
      <div class="aasel-form">
        <AppFormItem label="课程" required>
          <AppCoursePicker v-model="courseForm.courseId" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="教学任务">
          <AppTeachingTaskPicker v-model="courseForm.teachingTaskId" :query="{ courseId: courseForm.courseId || undefined }" placeholder="选填（关联任课教师/教学班）" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="容量上限" required>
          <AppNumberInput v-model="courseForm.capacity" :min="1" :max="1000" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="开课人数下限">
          <AppNumberInput v-model="courseForm.minCapacity" :min="0" :max="1000" :disabled="saving" />
        </AppFormItem>
        <AppInlineAlert v-if="courseError" type="danger" :description="courseError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="courseVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCourse">添加</AppButton>
      </template>
    </AppDrawer>

    <!-- 建轮次 -->
    <AppDrawer :visible="roundVisible" title="添加选课轮次" @close="roundVisible = false">
      <div class="aasel-form">
        <AppFormItem label="轮次名称" required>
          <AppTextInput v-model="roundForm.roundName" placeholder="如 第一轮预选 / 正选 / 补退选" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="模式" required>
          <AppSelect v-model="roundForm.mode" :options="[{ label: '先到先得（实时占容量）', value: 'FCFS' }, { label: '抽签（志愿登记，关轮后摇号）', value: 'LOTTERY' }]" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="选课控制">
          <AppSelect v-model="roundForm.ctrl" :options="[{ label: '可选可退', value: 'BOTH' }, { label: '只可选（禁退）', value: 'ENROLL_ONLY' }, { label: '只可退（补退选禁新增）', value: 'DROP_ONLY' }]" :disabled="saving" />
        </AppFormItem>
        <AppInlineAlert v-if="roundError" type="danger" :description="roundError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="roundVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitRound">创建</AppButton>
      </template>
    </AppDrawer>

    <!-- 名单抽屉 -->
    <AppDrawer :visible="rosterVisible" :title="'选课名单 · ' + (rosterCourse ? rosterCourse.courseName : '')" @close="rosterVisible = false">
      <EmptyState v-if="!rosterRows.length" title="暂无学生" description="该课程尚无有效选课记录" />
      <DataTable v-else :columns="rosterColumns" :rows="rosterRows" row-key="recordId">
        <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）</template>
      </DataTable>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 选课管理 · 教务处控制台（/admin/academic-affairs/selection）：批次生命周期 + 课程供给 + 名单 + 统计。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppCoursePicker, AppTeachingTaskPicker } from '@/components/common'
import { academicAffairsApi, academicAffairsSelectionApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _LABEL = { DRAFT: '草稿', PUBLISHED: '已发布', OPEN: '选课中', CLOSED: '已截止', LOCKED: '已锁定', ARCHIVED: '已归档' }

export default {
  name: 'AaSelectionConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppCoursePicker, AppTeachingTaskPicker },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [],
      pagination: { page: 1, pageSize: 50, total: 0 },
      current: null, courses: [], stats: null,
      createVisible: false, form: { batchName: '', maxCredits: 0, remark: '' }, formError: '',
      courseVisible: false, courseForm: { courseId: '', teachingTaskId: '', capacity: 30, minCapacity: 1 }, courseError: '',
      rosterVisible: false, rosterCourse: null, rosterRows: [],
      saving: false,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      rounds: [], drawResult: null,
      roundVisible: false, roundForm: { roundName: '', mode: 'FCFS', ctrl: 'BOTH' }, roundError: '',
      roundColumns: [
        { key: 'round', title: '轮次' }, { key: 'mode', title: '模式' },
        { key: 'ctrl', title: '选退控制' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ],
      courseColumns: [
        { key: 'course', title: '课程' }, { key: 'fill', title: '选课情况' },
        { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }
      ],
      rosterColumns: [{ key: 'student', title: '学生' }, { key: 'status', title: '状态' }]
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  methods: {
    async runTimeTick() {
      const res = await api.timeTick()
      if (res.code === 0) {
        const d = res.data || {}
        toast.success(`已按时间处理：开选 ${d.opened != null ? d.opened : 0} / 截止 ${d.closed != null ? d.closed : 0}`)
        await this.load()
        if (this.current) await this.select(this.current)
      } else toast.error(res.message)
    },
    statusLabel(s) { return _LABEL[s] || s },
    statusType(s) {
      if (s === 'OPEN') return 'success'
      if (s === 'CLOSED') return 'warning'
      if (['LOCKED', 'ARCHIVED'].includes(s)) return 'default'
      return 'primary'
    },
    async load() {
      this.loading = true; this.error = ''
      const res = await api.listBatches({ page: 1, pageSize: 50 })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else this.error = res.message
      this.loading = false
    },
    async select(b) {
      this.current = b
      await this.refreshDetail()
    },
    async refreshDetail() {
      if (!this.current) return
      const [cs, st, rd] = await Promise.all([
        api.listCourses(this.current.batchId, { pageSize: 200 }),
        api.batchStats(this.current.batchId),
        api.listRounds(this.current.batchId)
      ])
      this.courses = cs.code === 0 ? cs.data.list : []
      this.stats = st.code === 0 ? st.data : null
      this.rounds = rd.code === 0 ? (rd.data.items || []) : []
    },
    roundStatusLabel(s) { return { DRAFT: '草稿', OPEN: '进行中', CLOSED: '已关闭', DRAWN: '已摇号' }[s] || s },
    roundStatusType(s) {
      if (s === 'OPEN') return 'success'
      if (s === 'DRAWN') return 'default'
      if (s === 'CLOSED') return 'warning'
      return 'primary'
    },
    openAddRound() { this.roundForm = { roundName: '', mode: 'FCFS', ctrl: 'BOTH' }; this.roundError = ''; this.roundVisible = true },
    async submitRound() {
      if (!this.roundForm.roundName) { this.roundError = '轮次名称必填'; return }
      this.saving = true
      const res = await api.createRound(this.current.batchId, {
        roundName: this.roundForm.roundName, mode: this.roundForm.mode,
        allowEnroll: this.roundForm.ctrl !== 'DROP_ONLY',
        allowDrop: this.roundForm.ctrl !== 'ENROLL_ONLY'
      })
      this.saving = false
      if (res.code === 0) { toast.success('轮次已创建'); this.roundVisible = false; await this.refreshDetail() }
      else this.roundError = res.message
    },
    roundAction(row, fn, label) {
      this.confirmTitle = label
      this.confirmMessage = `确认对「第${row.roundNo}轮 ${row.roundName}」执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api[fn](row.roundId)
        if (res.code === 0) {
          toast.success(res.message || label + '成功')
          if (fn === 'drawRound') this.drawResult = res.data
          await this.refreshDetail()
        } else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    openCreate() { this.form = { batchName: '', maxCredits: 0, remark: '' }; this.formError = ''; this.createVisible = true },
    async submitCreate() {
      if (!this.form.batchName) { this.formError = '批次名称必填'; return }
      this.saving = true
      const body = { batchName: this.form.batchName, remark: this.form.remark }
      if (this.form.maxCredits > 0) body.rule = { maxCredits: this.form.maxCredits }
      const res = await api.createBatch(body)
      this.saving = false
      if (res.code === 0) { toast.success('已创建'); this.createVisible = false; await this.load() }
      else this.formError = res.message
    },
    lifecycle(fn, label) {
      this.confirmTitle = label
      this.confirmMessage = `确认对批次「${this.current.batchName}」执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api[fn](this.current.batchId)
        if (res.code === 0) { toast.success(label + '成功'); this.current = res.data; await this.load(); await this.refreshDetail() }
        else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    openAddCourse() { this.courseForm = { courseId: '', teachingTaskId: '', capacity: 30, minCapacity: 1 }; this.courseError = ''; this.courseVisible = true },
    async submitCourse() {
      if (!this.courseForm.courseId) { this.courseError = '请选择课程'; return }
      this.saving = true
      const res = await api.addCourse(this.current.batchId, {
        courseId: this.courseForm.courseId,
        teachingTaskId: this.courseForm.teachingTaskId || undefined,
        capacity: this.courseForm.capacity, minCapacity: this.courseForm.minCapacity
      })
      this.saving = false
      if (res.code === 0) { toast.success('已添加'); this.courseVisible = false; await this.refreshDetail() }
      else this.courseError = res.message
    },
    cancelCourse(row) {
      this.confirmTitle = '取消开课'
      this.confirmMessage = `确认取消「${row.courseName}」开课？已选学生将置为课程取消状态。`
      this.pendingAction = async () => {
        const res = await api.cancelCourse(row.selectionCourseId)
        if (res.code === 0) { toast.success('已取消开课'); await this.refreshDetail() }
        else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    async openRoster(row) {
      this.rosterCourse = row; this.rosterRows = []; this.rosterVisible = true
      const res = await api.courseRoster(row.selectionCourseId, { pageSize: 500 })
      if (res.code === 0) this.rosterRows = res.data.list
      else toast.error(res.message)
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aasel-layout { display: grid; grid-template-columns: 300px 1fr; gap: 16px; }
.aasel-batches { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aasel-batch { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aasel-batch.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aasel-batch-name { font-weight: 500; }
.aasel-detail-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.aasel-detail-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
.aasel-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aasel-stats { display: flex; gap: 16px; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.aasel-stats .is-warn { color: var(--warning-color, #d97706); font-weight: 600; }
.aasel-courses-head { display: flex; justify-content: space-between; align-items: center; margin: 8px 0; font-weight: 500; }
.aasel-form { display: flex; flex-direction: column; gap: 12px; }
</style>
