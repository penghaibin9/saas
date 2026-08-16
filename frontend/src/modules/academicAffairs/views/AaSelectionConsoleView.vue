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
      <aside class="aasel-list-card">
        <div class="aasel-list-head">
          <div>
            <span class="aasel-eyebrow">批次导航</span>
            <h2>选课批次</h2>
          </div>
          <span class="aasel-list-count">{{ pagination.total }}</span>
        </div>

        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无选课批次" description="点击右上角「新建批次」创建" />
        <ul v-else class="aasel-batches">
          <li
            v-for="b in rows"
            :key="b.batchId"
            :class="['aasel-batch', { 'is-active': current && current.batchId === b.batchId }]"
            tabindex="0"
            @click="select(b)"
            @keyup.enter="select(b)"
          >
            <div class="aasel-batch-top">
              <strong>{{ b.batchName }}</strong>
              <StatusTag :type="statusType(b.status)" :label="statusLabel(b.status)" dot />
            </div>
            <p>{{ batchWindowText(b, true) }}</p>
            <div class="aasel-batch-next">
              <span>下一动作</span>
              <b>{{ nextActionFor(b.status) }}</b>
            </div>
          </li>
        </ul>
      </aside>

      <main class="aasel-detail">
        <section v-if="!current" class="aasel-placeholder">
          <div class="aasel-placeholder-icon" aria-hidden="true">选</div>
          <strong>选择一个选课批次</strong>
          <span>从左侧进入批次后，可查看当前阶段、真实时间窗、容量、轮次、低人数风险与名单。</span>
        </section>

        <template v-else>
          <section class="aasel-hero" :class="`is-${String(current.status || '').toLowerCase()}`">
            <div class="aasel-hero-main">
              <div class="aasel-hero-topline">
                <span class="aasel-eyebrow">当前批次运行态</span>
                <StatusTag :type="statusType(current.status)" :label="statusLabel(current.status)" dot />
              </div>
              <h2>{{ current.batchName }}</h2>
              <p>{{ phaseDescription }}</p>
              <div class="aasel-hero-meta">
                <span><b>选课窗口</b>{{ batchWindowText(current) }}</span>
                <span><b>轮次策略</b>{{ roundSummary }}</span>
                <span v-if="current.remark"><b>备注</b>{{ current.remark }}</span>
              </div>
            </div>

            <aside class="aasel-next-card" :class="healthTone">
              <span>当前结论</span>
              <strong>{{ healthLabel }}</strong>
              <p>{{ healthDescription }}</p>
              <div class="aasel-next-action">
                <small>建议下一动作</small>
                <b>{{ nextActionFor(current.status) }}</b>
              </div>
            </aside>

            <div class="aasel-actions">
              <AppButton v-if="current.status === 'DRAFT'" variant="primary" size="small" @click="lifecycle('publishBatch', '发布')">发布</AppButton>
              <AppButton v-if="current.status === 'PUBLISHED'" variant="primary" size="small" @click="lifecycle('openBatch', '开选')">开选</AppButton>
              <AppButton v-if="current.status === 'OPEN'" variant="warning" size="small" @click="lifecycle('closeBatch', '截止')">截止</AppButton>
              <AppButton v-if="current.status === 'CLOSED'" variant="primary" size="small" @click="lifecycle('lockBatch', '锁定名单')">锁定名单</AppButton>
              <AppButton v-if="current.status === 'LOCKED'" variant="ghost" size="small" @click="lifecycle('archiveBatch', '归档')">归档</AppButton>
            </div>
          </section>

          <AppInlineAlert
            v-if="preflight && !preflight.allowed"
            class="aasel-preflight-alert"
            type="danger"
            :description="preflightMessage(preflight)"
          />

          <section class="aasel-metrics" aria-label="批次关键指标">
            <article>
              <span>课程供给</span>
              <strong>{{ metricValue('courseCount') }}</strong>
              <small>当前批次可选课程</small>
            </article>
            <article>
              <span>总容量</span>
              <strong>{{ metricValue('totalCapacity') }}</strong>
              <small>全部课程容量合计</small>
            </article>
            <article>
              <span>已选人次</span>
              <strong>{{ metricValue('totalSelected') }}</strong>
              <small>当前有效选课占用</small>
            </article>
            <article>
              <span>整体填充率</span>
              <strong>{{ stats ? `${Math.round(Number(stats.fillRate || 0) * 100)}%` : '—' }}</strong>
              <small>已选 / 总容量</small>
            </article>
            <article :class="{ 'is-risk': Number(stats && stats.lowEnrollCount || 0) > 0 }">
              <span>低人数课程</span>
              <strong>{{ metricValue('lowEnrollCount') }}</strong>
              <small>{{ Number(stats && stats.lowEnrollCount || 0) > 0 ? '达到截止后处置关注条件' : '当前无显式低人数项' }}</small>
            </article>
          </section>

          <section class="aasel-section">
            <header class="aasel-section-head">
              <div>
                <span class="aasel-eyebrow">轮次控制</span>
                <h3>选课轮次</h3>
                <p>{{ rounds.length ? '轮次决定学生当前可选、可退以及是否需要抽签。' : '当前未建立轮次，继续使用批次级先到先得模式。' }}</p>
              </div>
              <AppButton v-if="!['LOCKED','ARCHIVED'].includes(current.status)" size="small" variant="ghost" @click="openAddRound">+ 添加轮次</AppButton>
            </header>

            <div v-if="rounds.length" class="aasel-table-wrap">
              <DataTable :columns="roundColumns" :rows="rounds" row-key="roundId">
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
            </div>
            <div v-else class="aasel-inline-empty">
              <span aria-hidden="true">轮</span>
              <div><strong>未配置独立轮次</strong><p>学生按批次 OPEN/CLOSED 状态执行先到先得；如需预选、正选或补退选，再建立轮次。</p></div>
            </div>

            <AppInlineAlert
              v-if="drawResult"
              type="success"
              :description="'摇号完成：中签 ' + drawResult.totalWinners + ' 人，未中签 ' + drawResult.totalLosers + ' 人（' + drawResult.courses.map(c => `${c.courseName} ${c.winners}/${c.applicants}`).join('；') + '）'"
            />
          </section>

          <section class="aasel-section">
            <header class="aasel-section-head">
              <div>
                <span class="aasel-eyebrow">课程供给</span>
                <h3>可选课程与实时容量</h3>
                <p>容量、已选与余量均来自当前批次真实课程供给；名单入口保留在每门课程。</p>
              </div>
              <AppButton v-if="['DRAFT','PUBLISHED'].includes(current.status)" size="small" variant="ghost" @click="openAddCourse">+ 添加课程</AppButton>
            </header>

            <EmptyState v-if="!courses.length" title="未配置课程" description="添加至少一门课程后方可发布" />
            <div v-else class="aasel-table-wrap">
              <DataTable :columns="courseColumns" :rows="courses" row-key="selectionCourseId">
                <template #cell-course="{ row }">
                  <div class="mp-cell-main">{{ row.courseName }}</div>
                  <div class="mp-cell-sub">{{ row.teacherName || '未派课' }} · {{ row.credit }} 学分</div>
                </template>
                <template #cell-fill="{ row }">
                  <div class="aasel-capacity">
                    <div><strong>{{ row.selectedCount }}</strong><span>/ {{ row.capacity }} · 余 {{ row.remain }}</span></div>
                    <div class="aasel-capacity-bar" aria-hidden="true"><i :style="{ width: `${courseFillPct(row)}%` }"></i></div>
                  </div>
                </template>
                <template #cell-status="{ row }">
                  <StatusTag :type="row.status === 'OPEN' ? 'success' : 'default'" :label="row.status === 'OPEN' ? '开放' : '已取消'" dot />
                </template>
                <template #cell-ops="{ row }">
                  <button class="mp-link" @click="openRoster(row)">名单</button>
                  <button v-if="current.status === 'CLOSED' && row.status === 'OPEN'" class="mp-link is-danger" @click="cancelCourse(row)">取消开课</button>
                </template>
              </DataTable>
            </div>
          </section>
        </template>
      </main>
    </div>

    <AppDrawer :visible="createVisible" title="新建选课批次" mode="modal" size="medium" @close="createVisible = false">
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

    <AppDrawer :visible="courseVisible" title="添加可选课程" mode="modal" size="large" @close="courseVisible = false">
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

    <AppDrawer :visible="roundVisible" title="添加选课轮次" mode="modal" size="medium" @close="roundVisible = false">
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

    <AppDrawer :visible="rosterVisible" :title="'选课名单 · ' + (rosterCourse ? rosterCourse.courseName : '')" mode="modal" size="xlarge" @close="rosterVisible = false">
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
const _NEXT = {
  DRAFT: '配置课程并发布',
  PUBLISHED: '核对时间窗并开选',
  OPEN: '关注容量并按时截止',
  CLOSED: '处置低人数并锁定名单',
  LOCKED: '复核名单并归档',
  ARCHIVED: '查阅归档事实'
}

export default {
  name: 'AaSelectionConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppCoursePicker, AppTeachingTaskPicker
  },
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
      preflight: null, preflightLoading: false, preflightRequestSeq: 0,
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
  computed: {
    roundSummary() {
      if (!this.rounds.length) return '无独立轮次 · 先到先得'
      const active = this.rounds.filter((row) => row.status === 'OPEN').length
      return `${this.rounds.length} 个轮次 · ${active} 个进行中`
    },
    healthLabel() {
      const status = this.current?.status
      if (status === 'ARCHIVED') return '已归档'
      if (status === 'LOCKED') return '名单已锁定'
      if (this.stats && Number(this.stats.courseCount || 0) === 0) return '待配置课程'
      if (this.stats && ['OPEN', 'CLOSED'].includes(status) && Number(this.stats.lowEnrollCount || 0) > 0) return '存在低人数关注项'
      if (status === 'OPEN') return '正在选课'
      if (status === 'CLOSED') return '已截止 · 待锁定'
      if (status === 'PUBLISHED') return '已发布 · 待开选'
      return '批次配置中'
    },
    healthTone() {
      if (this.current?.status === 'ARCHIVED') return 'is-neutral'
      if (this.current?.status === 'LOCKED') return 'is-success'
      if (this.stats && Number(this.stats.courseCount || 0) === 0) return 'is-warning'
      if (this.stats && ['OPEN', 'CLOSED'].includes(this.current?.status) && Number(this.stats.lowEnrollCount || 0) > 0) return 'is-warning'
      if (this.current?.status === 'OPEN') return 'is-success'
      return 'is-info'
    },
    healthDescription() {
      if (!this.stats) return '正在读取课程供给、容量与选课统计。'
      if (this.current?.status === 'ARCHIVED') return '批次已经归档，当前页面仅用于查阅事实。'
      if (this.current?.status === 'LOCKED') return '正式名单已经锁定；后续只进行复核与归档。'
      if (Number(this.stats.courseCount || 0) === 0) return '当前批次还没有课程供给；发布前至少添加一门课程。'
      if (['OPEN', 'CLOSED'].includes(this.current?.status) && Number(this.stats.lowEnrollCount || 0) > 0) return `当前有 ${this.stats.lowEnrollCount} 门课程低于开课人数下限，请在锁定名单前核对处置。`
      if (this.current?.status === 'OPEN') return '当前批次处于开选状态；容量与余量使用后端实时统计。'
      if (this.current?.status === 'CLOSED') return '选课已经截止；下一步应核对低人数课程并形成正式名单。'
      return '当前页面未发现由课程供给或低人数统计暴露的显式风险。'
    },
    phaseDescription() {
      const status = this.current?.status
      const map = {
        DRAFT: '先完成课程供给与批次规则配置，再发布给学生。',
        PUBLISHED: '批次已经发布，核对真实选课时间窗后进入开选。',
        OPEN: '学生正在办理选退课；重点关注容量、余量与当前轮次。',
        CLOSED: '学生选退已经停止，进入低人数课程处置和正式名单确认。',
        LOCKED: '名单事实已经锁定，不再进行普通选退课变更。',
        ARCHIVED: '批次生命周期已经结束，保留历史课程、名单和统计供查阅。'
      }
      return map[status] || '按批次状态机管理课程供给、轮次、容量与名单。'
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
    nextActionFor(status) { return _NEXT[status] || '查看批次详情' },
    lifecycleAction(status) { return { DRAFT: 'PUBLISH', PUBLISHED: 'OPEN', OPEN: 'CLOSE', CLOSED: 'LOCK' }[status] || '' },
    preflightMessage(result) {
      const blockers = (result && result.blockers) || []
      if (!blockers.length) return '当前动作预检未通过，请刷新后重试。'
      return blockers.map((item) => `${item.message}${item.howToResolve ? `；处理：${item.howToResolve}` : ''}`).join('；')
    },
    async refreshPreflight() {
      const batchId = this.current && this.current.batchId
      const status = this.current && this.current.status
      const action = this.lifecycleAction(status)
      if (!batchId || !action) {
        this.preflightRequestSeq += 1
        this.preflight = null
        this.preflightLoading = false
        return null
      }
      const requestSeq = ++this.preflightRequestSeq
      this.preflightLoading = true
      const res = await api.batchPreflight(batchId, action)
      if (
        requestSeq !== this.preflightRequestSeq ||
        !this.current ||
        this.current.batchId !== batchId ||
        this.current.status !== status
      ) return null
      this.preflightLoading = false
      this.preflight = res.code === 0 ? res.data : { allowed: false, blockers: [{ message: res.message || '预检失败' }] }
      return this.preflight
    },
    formatDateTime(value, compact = false) {
      if (!value) return ''
      const date = new Date(value)
      if (Number.isNaN(date.getTime())) return String(value)
      const options = compact
        ? { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }
        : { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }
      return new Intl.DateTimeFormat('zh-CN', options).format(date).replace(/\//g, '-')
    },
    batchWindowText(batch, compact = false) {
      if (!batch) return '未设置'
      const start = this.formatDateTime(batch.selectStartAt, compact)
      const end = this.formatDateTime(batch.selectEndAt, compact)
      if (start && end) return `${start} → ${end}`
      if (start) return `${start} 开选`
      if (end) return `${end} 截止`
      return '未设置自动时间窗'
    },
    metricValue(key) {
      if (!this.stats || this.stats[key] === undefined || this.stats[key] === null) return '—'
      return this.stats[key]
    },
    courseFillPct(row) {
      const capacity = Number(row?.capacity || 0)
      const selected = Number(row?.selectedCount || 0)
      if (!capacity) return 0
      return Math.max(0, Math.min(100, Math.round(selected / capacity * 100)))
    },
    async load() {
      this.loading = true; this.error = ''
      const res = await api.listBatches({ page: 1, pageSize: 50 })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
        if (!this.current && this.rows.length) {
          const preferred = this.rows.find((row) => ['OPEN', 'PUBLISHED', 'CLOSED'].includes(row.status)) || this.rows[0]
          await this.select(preferred)
        } else if (this.current) {
          const fresh = this.rows.find((row) => row.batchId === this.current.batchId)
          if (fresh) this.current = fresh
        }
      } else this.error = res.message
      this.loading = false
    },
    async select(b) {
      this.current = b
      this.drawResult = null
      this.preflight = null
      await this.refreshDetail()
      await this.refreshPreflight()
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
    async lifecycle(fn, label) {
      const action = { publishBatch: 'PUBLISH', openBatch: 'OPEN', closeBatch: 'CLOSE', lockBatch: 'LOCK' }[fn]
      if (action) {
        const checked = await this.refreshPreflight()
        if (!checked || !checked.allowed) {
          toast.error(this.preflightMessage(checked))
          return
        }
      }
      this.confirmTitle = label
      this.confirmMessage = `确认对批次「${this.current.batchName}」执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api[fn](this.current.batchId)
        if (res.code === 0) { toast.success(label + '成功'); this.preflightRequestSeq += 1; this.preflight = null; this.current = res.data; await this.load(); await this.refreshDetail(); await this.refreshPreflight() }
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
    onConfirm() {
      const a = this.pendingAction
      this.pendingAction = null
      this.confirmVisible = false
      if (a) a()
    }
  }
}
</script>

<style scoped>
.aasel-layout { display: grid; grid-template-columns: minmax(280px, 320px) minmax(0, 1fr); gap: 18px; align-items: start; }
.aasel-list-card,
.aasel-section,
.aasel-placeholder { border: 1px solid #e3eaf4; border-radius: 18px; background: #fff; box-shadow: 0 14px 34px -30px rgba(15, 23, 42, .38); }
.aasel-list-card { position: sticky; top: 18px; overflow: hidden; }
.aasel-list-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 18px 18px 14px; border-bottom: 1px solid #edf1f7; background: linear-gradient(180deg, #fff, #fbfdff); }
.aasel-list-head h2,
.aasel-section-head h3 { margin: 4px 0 0; color: #172033; font-size: 16px; }
.aasel-eyebrow { color: #2468d8; font-size: 10.5px; font-weight: 750; letter-spacing: .08em; }
.aasel-list-count { min-width: 30px; padding: 5px 8px; border-radius: 999px; background: #eef5ff; color: #2468d8; font-size: 11px; font-weight: 700; text-align: center; }
.aasel-batches { list-style: none; margin: 0; padding: 10px; display: grid; gap: 8px; max-height: calc(100vh - 220px); overflow: auto; }
.aasel-batch { display: grid; gap: 9px; padding: 13px 14px; border: 1px solid transparent; border-radius: 13px; background: #f8fafc; cursor: pointer; transition: border-color .16s ease, box-shadow .16s ease, background .16s ease; outline: none; }
.aasel-batch:hover,
.aasel-batch:focus-visible { border-color: #c9d9f2; background: #fff; box-shadow: 0 8px 22px -20px rgba(37, 99, 235, .45); }
.aasel-batch.is-active { border-color: #91b7ef; background: linear-gradient(135deg, #f7fbff, #eef5ff); box-shadow: inset 3px 0 0 #2f6fd2; }
.aasel-batch-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.aasel-batch-top strong { color: #1c2940; font-size: 13px; line-height: 1.45; }
.aasel-batch p { margin: 0; color: #718096; font-size: 10.5px; line-height: 1.45; }
.aasel-batch-next { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding-top: 8px; border-top: 1px dashed #dfe7f1; }
.aasel-batch-next span { color: #8895a7; font-size: 10px; }
.aasel-batch-next b { color: #44546a; font-size: 10.5px; font-weight: 650; }

.aasel-detail { min-width: 0; display: grid; gap: 14px; }
.aasel-preflight-alert { margin: 0; }
.aasel-placeholder { display: grid; justify-items: center; gap: 8px; min-height: 300px; align-content: center; padding: 28px; text-align: center; }
.aasel-placeholder-icon { display: grid; place-items: center; width: 54px; height: 54px; border-radius: 16px; background: #eef5ff; color: #2468d8; font-weight: 800; }
.aasel-placeholder strong { color: #172033; font-size: 15px; }
.aasel-placeholder span { max-width: 460px; color: #718096; font-size: 12px; line-height: 1.7; }

.aasel-hero { position: relative; display: grid; grid-template-columns: minmax(0, 1fr) 250px; gap: 20px 24px; overflow: hidden; padding: 24px 26px; border: 1px solid #dbe6f6; border-radius: 20px; background: radial-gradient(circle at 90% 12%, rgba(73, 124, 215, .15), transparent 30%), linear-gradient(135deg, #fff 0%, #f8fbff 62%, #eff5ff 100%); box-shadow: 0 20px 48px -38px rgba(37, 99, 235, .55); }
.aasel-hero.is-open { border-color: #bfe5cf; background: radial-gradient(circle at 90% 12%, rgba(34, 197, 94, .13), transparent 30%), linear-gradient(135deg, #fff, #fbfffc 62%, #effbf3); }
.aasel-hero.is-closed { border-color: #f2d7aa; background: radial-gradient(circle at 90% 12%, rgba(245, 158, 11, .13), transparent 30%), linear-gradient(135deg, #fff, #fffdf8 62%, #fff8e9); }
.aasel-hero.is-locked,
.aasel-hero.is-archived { border-color: #dce2ea; background: radial-gradient(circle at 90% 12%, rgba(100, 116, 139, .10), transparent 30%), linear-gradient(135deg, #fff, #fbfcfd 62%, #f4f6f8); }
.aasel-hero-topline { display: flex; align-items: center; gap: 10px; }
.aasel-hero h2 { margin: 10px 0 7px; color: #132038; font-size: 25px; letter-spacing: -.02em; }
.aasel-hero-main > p { max-width: 780px; margin: 0; color: #5f6f84; font-size: 13px; line-height: 1.75; }
.aasel-hero-meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.aasel-hero-meta span { display: inline-flex; align-items: center; gap: 6px; padding: 6px 9px; border: 1px solid rgba(112, 139, 176, .15); border-radius: 999px; background: rgba(255,255,255,.72); color: #66758a; font-size: 10.5px; }
.aasel-hero-meta b { color: #32445e; font-weight: 700; }
.aasel-next-card { align-self: stretch; display: grid; align-content: center; gap: 7px; padding: 18px; border: 1px solid #dbe8fb; border-radius: 15px; background: rgba(255,255,255,.76); }
.aasel-next-card > span,
.aasel-next-action small { color: #8793a5; font-size: 10px; }
.aasel-next-card > strong { color: #235ea8; font-size: 17px; }
.aasel-next-card > p { margin: 0; color: #64748b; font-size: 11px; line-height: 1.6; }
.aasel-next-card.is-success { border-color: #c7ead3; }
.aasel-next-card.is-success > strong { color: #18794e; }
.aasel-next-card.is-warning { border-color: #f0d7ad; }
.aasel-next-card.is-warning > strong { color: #a85b0b; }
.aasel-next-card.is-neutral { border-color: #dde3ea; }
.aasel-next-card.is-neutral > strong { color: #536174; }
.aasel-next-action { display: grid; gap: 3px; margin-top: 4px; padding-top: 9px; border-top: 1px solid #e8edf4; }
.aasel-next-action b { color: #27364c; font-size: 11px; }
.aasel-actions { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 8px; padding-top: 2px; }

.aasel-metrics { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
.aasel-metrics article { min-width: 0; padding: 15px 16px; border: 1px solid #e3eaf3; border-radius: 14px; background: #fff; box-shadow: 0 12px 26px -26px rgba(15, 23, 42, .55); }
.aasel-metrics span,
.aasel-metrics strong,
.aasel-metrics small { display: block; }
.aasel-metrics span { color: #78879a; font-size: 10.5px; }
.aasel-metrics strong { margin-top: 5px; color: #172033; font-size: 22px; font-variant-numeric: tabular-nums; }
.aasel-metrics small { margin-top: 4px; color: #97a2b2; font-size: 9.8px; line-height: 1.4; }
.aasel-metrics article.is-risk { border-color: #f1cfa0; background: #fffcf5; }
.aasel-metrics article.is-risk strong { color: #ad5e0d; }

.aasel-section { overflow: hidden; }
.aasel-section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding: 18px 20px; border-bottom: 1px solid #edf1f7; background: linear-gradient(180deg, #fff, #fcfdff); }
.aasel-section-head p { margin: 5px 0 0; color: #718096; font-size: 11px; line-height: 1.6; }
.aasel-table-wrap { padding: 4px 10px 10px; overflow-x: auto; }
.aasel-inline-empty { display: grid; grid-template-columns: 38px minmax(0, 1fr); gap: 12px; align-items: center; margin: 16px; padding: 16px; border: 1px dashed #d6e1ef; border-radius: 13px; background: #fafcff; }
.aasel-inline-empty > span { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 11px; background: #eef5ff; color: #2468d8; font-weight: 750; }
.aasel-inline-empty strong { color: #26364c; font-size: 12px; }
.aasel-inline-empty p { margin: 4px 0 0; color: #748296; font-size: 10.8px; line-height: 1.6; }

.aasel-capacity { min-width: 150px; }
.aasel-capacity > div:first-child { display: flex; align-items: baseline; gap: 4px; color: #65758a; font-size: 11px; }
.aasel-capacity strong { color: #25364e; font-size: 13px; font-variant-numeric: tabular-nums; }
.aasel-capacity-bar { height: 6px; margin-top: 6px; overflow: hidden; border-radius: 999px; background: #edf2f7; }
.aasel-capacity-bar i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #70a4eb, #2f6fd2); }
.aasel-form { display: flex; flex-direction: column; gap: 12px; }

@media (max-width: 1280px) {
  .aasel-metrics { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 1080px) {
  .aasel-layout { grid-template-columns: 1fr; }
  .aasel-list-card { position: static; }
  .aasel-batches { grid-template-columns: repeat(2, minmax(0, 1fr)); max-height: none; }
}
@media (max-width: 760px) {
  .aasel-hero { grid-template-columns: 1fr; padding: 20px; }
  .aasel-actions { grid-column: auto; }
  .aasel-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .aasel-batches { grid-template-columns: 1fr; }
  .aasel-section-head { flex-direction: column; }
}
@media (max-width: 520px) {
  .aasel-metrics { grid-template-columns: 1fr; }
}
</style>
