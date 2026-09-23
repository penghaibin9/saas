<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="activeTab === 'batch'" variant="ghost" :loading="tickBusy" :disabled="saving || tickBusy" @click="runTimeTick">按时间批量开选/截止</AppButton>
      <AppButton v-if="activeTab === 'batch'" variant="primary" @click="openCreate">新建批次</AppButton>
    </template>

    <div class="aa-selection-layout">
      <aside v-if="pagination.total > 1" class="aa-selection-list-card">
        <div class="aa-selection-list-head">
          <div>
            <span class="aa-selection-eyebrow">批次导航</span>
            <h2>选课批次</h2>
          </div>
          <span class="aa-selection-list-count">{{ pagination.total }}</span>
        </div>

        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="暂无选课批次" description="点击右上角「新建批次」创建" />
        <ul v-else class="aa-selection-batches">
          <li
            v-for="b in rows"
            :key="b.batchId"
            :class="['aa-selection-batch', { 'is-active': current && current.batchId === b.batchId }]"
            tabindex="0"
            @click="select(b)"
            @keyup.enter="select(b)"
          >
            <div class="aa-selection-batch-top">
              <strong>{{ b.batchName }}</strong>
              <StatusTag :type="b.windowNotice ? 'warning' : statusType(b.status)" :label="batchStatusLabel(b)" dot />
            </div>
            <p>{{ batchWindowText(b, true) }}</p>
            <div class="aa-selection-batch-next">
              <span>下一动作</span>
              <b>{{ nextActionFor(b.status) }}</b>
            </div>
          </li>
        </ul>
        <AppPagination v-if="pagination.total" :total="pagination.total" :page="pagination.page" :page-size="pagination.pageSize" :show-size-changer="false" @change="onBatchPage" />
      </aside>

      <main class="aa-selection-detail">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <section v-else-if="!current" class="aa-selection-placeholder">
          <div class="aa-selection-placeholder-icon" aria-hidden="true">选</div>
          <strong>选择一个选课批次</strong>
          <span>从左侧进入批次后，可查看当前阶段、真实时间窗、容量、轮次、低人数风险与名单。</span>
        </section>

        <template v-else>
          <section class="aa-selection-hero" :class="`is-${String(current.status || '').toLowerCase()}`">
            <div class="aa-selection-hero-main">
              <div class="aa-selection-hero-topline">
                <span class="aa-selection-eyebrow">当前批次运行态 · 当前办理对象</span>
                <StatusTag :type="current.windowNotice ? 'warning' : statusType(current.status)" :label="batchStatusLabel(current)" dot />
              </div>
              <h2>{{ current.batchName }}</h2>
              <p>选课批次 · {{ current.batchCode || `SEL-${current.batchId}` }} · {{ current.termName || '当前学期' }}</p>
              <p class="aa-selection-source">来源：从选课批次正式记录进入；当前页面只处理所选批次，不跨对象执行。</p>
              <div class="aa-selection-hero-meta">
                <span><b>选课窗口</b>{{ batchWindowText(current) }}</span>
                <span><b>轮次策略</b>{{ roundSummary }}</span>
                <span v-if="current.remark"><b>备注</b>{{ current.remark }}</span>
              </div>
            </div>

            <aside class="aa-selection-owner-card">
              <span>当前责任</span><strong>选课管理岗</strong>
              <span>下一责任</span><strong>{{ nextOwner }}</strong>
            </aside>

            <div v-if="activeTab === 'batch'" class="aa-selection-actions" :inert="detailLoading || !!detailError || saving">
              <AppButton v-if="current.status === 'DRAFT'" variant="primary" size="small" @click="lifecycle('publishBatch', '发布')">发布</AppButton>
              <AppButton v-if="current.status === 'PUBLISHED'" variant="primary" size="small" @click="lifecycle('openBatch', '开选')">开选</AppButton>
              <AppButton v-if="current.status === 'OPEN'" variant="warning" size="small" @click="lifecycle('closeBatch', '截止')">截止</AppButton>
              <AppButton v-if="current.status === 'CLOSED'" variant="primary" size="small" @click="lifecycle('lockBatch', '锁定名单')">锁定名单</AppButton>
              <AppButton v-if="current.status === 'LOCKED'" variant="ghost" size="small" @click="lifecycle('archiveBatch', '归档')">归档</AppButton>
            </div>
          </section>

          <section class="aa-selection-steps" aria-label="选课批次办理阶段">
            <article v-for="(step, index) in lifecycleSteps" :key="step.key" :class="stepClass(index)">
              <i>{{ index < currentStep ? '✓' : index + 1 }}</i>
              <div><strong>{{ step.label }}</strong><small>{{ step.note }}</small></div>
            </article>
          </section>
          <AppInlineAlert v-if="current.windowNotice" type="warning" :description="current.windowNotice" />
          <AppInlineAlert v-if="tickReceipt" :type="tickReceipt.partial ? 'warning' : 'success'" :description="tickReceipt.message" />

          <AaSelectionSpecialWorkspace
            v-if="activeTab !== 'batch'"
            :mode="activeTab"
            :batch="current"
            :rounds="rounds"
            @batch-updated="onSpecialBatchUpdated"
            @denied="onSpecialDenied"
          />

          <template v-else>

          <AppInlineAlert
            v-if="preflight && !preflight.allowed"
            class="aa-selection-preflight-alert"
            type="danger"
            :description="preflightMessage(preflight)"
          />

          <LoadingState v-if="detailLoading" />
          <ErrorState v-else-if="detailError" :description="detailError" @retry="refreshDetail" />
          <template v-else>
          <section class="aa-selection-summary" :class="healthTone">
            <div><span>当前结论</span><strong>{{ healthLabel }}</strong><p>{{ healthDescription }}</p><small>建议下一动作：{{ nextActionFor(current.status) }}</small></div>
            <dl>
              <div><dt>课程供给</dt><dd>{{ metricValue('courseCount') }}</dd></div>
              <div><dt>总容量</dt><dd>{{ metricValue('totalCapacity') }}</dd></div>
              <div><dt>已选人次</dt><dd>{{ metricValue('totalSelected') }}</dd></div>
              <div><dt>低人数课程</dt><dd>{{ metricValue('lowEnrollCount') }}</dd></div>
            </dl>
          </section>

          <section class="aa-selection-section">
            <header class="aa-selection-section-head">
              <div>
                <span class="aa-selection-eyebrow">轮次控制</span>
                <h3>选课轮次</h3>
                <p>{{ rounds.length ? '轮次决定学生当前可选、可退以及是否需要抽签。' : '当前未建立轮次，继续使用批次级先到先得模式。' }}</p>
              </div>
              <AppButton v-if="!['LOCKED','ARCHIVED'].includes(current.status)" size="small" variant="ghost" @click="openAddRound">+ 添加轮次</AppButton>
            </header>

            <div v-if="rounds.length" class="aa-selection-table-wrap">
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
            <div v-else class="aa-selection-inline-empty">
              <span aria-hidden="true">轮</span>
              <div><strong>未配置独立轮次</strong><p>学生在已开选且时间窗有效时按先到先得选课；如需预选、正选或补退选，再建立轮次。</p></div>
            </div>

            <AppInlineAlert
              v-if="drawResult"
              type="success"
              :description="'摇号完成：中签 ' + drawResult.totalWinners + ' 人，未中签 ' + drawResult.totalLosers + ' 人（' + drawResult.courses.map(c => `${c.courseName} ${c.winners}/${c.applicants}`).join('；') + '）'"
            />
          </section>

          <section class="aa-selection-section">
            <header class="aa-selection-section-head">
              <div>
                <span class="aa-selection-eyebrow">课程供给</span>
                <h3>可选课程与实时容量</h3>
                <p>容量、已选与余量均来自当前批次真实课程供给；名单入口保留在每门课程。</p>
              </div>
              <AppButton v-if="['DRAFT','PUBLISHED'].includes(current.status)" size="small" variant="ghost" @click="openAddCourse">+ 添加课程</AppButton>
            </header>

            <EmptyState v-if="!courses.length" title="未配置课程" description="添加至少一门课程后方可发布" />
            <div v-else class="aa-selection-table-wrap">
              <DataTable :columns="courseColumns" :rows="courses" row-key="selectionCourseId">
                <template #cell-course="{ row }">
                  <div class="mp-cell-main">{{ row.courseName }}</div>
                  <div class="mp-cell-sub">{{ row.teacherName || '未派课' }} · {{ row.credit }} 学分</div>
                </template>
                <template #cell-fill="{ row }">
                  <div class="aa-selection-capacity">
                    <div><strong>{{ row.selectedCount }}</strong><span>/ {{ row.capacity }} · 余 {{ row.remain }}</span></div>
                    <div class="aa-selection-capacity-bar" aria-hidden="true"><i :style="{ width: `${courseFillPct(row)}%` }"></i></div>
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
              <AppPagination v-if="coursePagination.total" :total="coursePagination.total" :page="coursePagination.page" :page-size="coursePagination.pageSize" :show-size-changer="false" @change="onCoursePage" />
            </div>
          </section>
          </template>
          </template>
        </template>
      </main>
    </div>

    <AppDrawer :visible="createVisible" title="新建选课批次" mode="modal" size="medium" @close="createVisible = false">
      <div class="aa-selection-form">
        <AppFormItem label="批次名称" required>
          <AppTextInput v-model="form.batchName" placeholder="如 2024秋公共选修课选课" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="学期" required>
          <AppTermEntityPicker v-model="form.termId" placeholder="选择学期" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="选课学分上限">
          <AppNumberInput v-model="form.maxCredits" :min="0" :max="50" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="适用范围" required>
          <AppSelect v-model="form.scopeType" :options="[{ label: '指定行政班', value: 'CLASS' }, { label: '全校学生', value: 'SCHOOL' }]" :disabled="saving" />
        </AppFormItem>
        <AppFormItem v-if="form.scopeType === 'CLASS'" label="适用班级" required>
          <AppClassPicker v-model="form.classIds" multiple placeholder="选择允许参加本批次的行政班" :disabled="saving" />
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
      <div class="aa-selection-form">
        <AppFormItem label="教学任务" required>
          <AppTeachingTaskPicker
            v-model="courseForm.teachingTaskId"
            :remote-search="searchSelectionTasks"
            placeholder="选择当前批次学期的已就绪教学任务"
            :disabled="saving"
            @change="onSelectionTaskChange"
          />
        </AppFormItem>
        <AppInlineAlert
          v-if="courseForm.teachingTaskId"
          type="info"
          :description="selectionTaskFactText"
        />
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
      <div class="aa-selection-form">
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
      <LoadingState v-if="rosterLoading" />
      <ErrorState v-else-if="rosterError" :description="rosterError" @retry="loadRoster" />
      <EmptyState v-else-if="!rosterRows.length" title="暂无学生" description="该课程尚无有效选课记录" />
      <DataTable v-else :columns="rosterColumns" :rows="rosterRows" row-key="recordId">
        <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）</template>
        <template #cell-status="{ row }">{{ selectionRecordLabel(row.status) }}</template>
      </DataTable>
      <AppPagination v-if="rosterPagination.total" :total="rosterPagination.total" :page="rosterPagination.page" :page-size="rosterPagination.pageSize" :show-size-changer="false" @change="onRosterPage" />
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 选课管理 · 教务处控制台（/admin/academic-affairs/selection）：批次生命周期 + 课程供给 + 名单 + 统计。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppTeachingTaskPicker, AppTermEntityPicker, AppPagination, AppClassPicker } from '@/components/common'
import { academicAffairsApi, academicAffairsSelectionApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { academicIdentity, createAcademicRequestGate } from '../academicFlowContext.js'
import AaSelectionSpecialWorkspace from '../components/parallel-a/AaSelectionSpecialWorkspace.vue'
import { isDeniedResult } from '../components/parallel-a/resultState'
import { currentUserFromToken } from '@/services/http/client'

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
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AaSelectionSpecialWorkspace, AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect, AppTeachingTaskPicker, AppTermEntityPicker, AppPagination, AppClassPicker
  },
  data() {
    return {
      loading: true, error: '', rows: [],
      workspaceTabs: [{ key: 'batch', label: '选课批次' }, { key: 'rule', label: '选课规则' }, { key: 'reselect', label: '补选管理' }, { key: 'conflict', label: '冲突检测' }],
      pagination: { page: 1, pageSize: 50, total: 0 },
      coursePagination: { page: 1, pageSize: 20, total: 0 },
      current: null, courses: [], stats: null, detailLoading: false, detailError: '', disposed: false, selectionVersion: 0, writeSeq: 0,
      createVisible: false, form: { batchName: '', termId: '', maxCredits: 0, remark: '', scopeType: 'CLASS', classIds: [] }, formError: '',
      courseVisible: false,
      courseForm: { courseId: '', teachingTaskId: '', courseCode: '', courseName: '', teacherName: '', teachingClassName: '', capacity: 30, minCapacity: 1 },
      courseError: '',
      rosterVisible: false, rosterCourse: null, rosterRows: [], rosterLoading: false, rosterError: '', rosterPagination: { page: 1, pageSize: 20, total: 0 },
      saving: false, tickBusy: false, tickReceipt: null,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null, confirmContext: '',
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
    pageTitle() { return { batch: '选课批次', rule: '选课规则', reselect: '补选管理', conflict: '冲突检测' }[this.activeTab] || '选课管理' },
    pageSubtitle() { return { batch: '规则、轮次、课程与名单在同一批次办理', rule: '切批次必须重新读取，确认锁定原对象', reselect: '只处理当前窗口和当前范围的对象', conflict: '接口失败不当成零冲突' }[this.activeTab] || '' },
    activeTab() {
      const tab = String(this.$route?.query?.tab || 'batch')
      return this.workspaceTabs.some(item => item.key === tab) ? tab : 'batch'
    },
    lifecycleSteps() {
      return [
        { key: 'create', label: '创建批次', note: '上游事实可回查' },
        { key: 'rules', label: '课程与规则', note: '上游事实可回查' },
        { key: 'open', label: '开放选课', note: '按真实状态解锁' },
        { key: 'reselect', label: '补选关口', note: '按真实状态解锁' },
        { key: 'lock', label: '锁定名单', note: '按真实状态解锁' }
      ]
    },
    currentStep() { return ({ DRAFT: 1, PUBLISHED: 2, OPEN: 2, CLOSED: 3, LOCKED: 4, ARCHIVED: 5 })[this.current?.status] ?? 0 },
    nextOwner() { return ['LOCKED', 'ARCHIVED'].includes(this.current?.status) ? '师生课表读取岗' : '选课管理岗 → 名单锁定岗' },
    roundSummary() {
      if (this.detailLoading || this.detailError) return '轮次待核对'
      if (!this.rounds.length) return '无独立轮次 · 先到先得'
      const active = this.rounds.filter((row) => row.status === 'OPEN').length
      return `${this.rounds.length} 个轮次 · ${active} 个进行中`
    },
    selectionTaskFactText() {
      const f = this.courseForm
      if (!f.teachingTaskId) return ''
      const course = [f.courseCode, f.courseName].filter(Boolean).join(' · ') || '课程信息缺失'
      return `课程：${course}；教师：${f.teacherName || '未提供'}；教学班：${f.teachingClassName || '未提供'}。这些信息从正式教学任务带出，提交时不允许手工改写。`
    },
    healthLabel() {
      if (this.detailError) return '批次详情待核对'
      if (this.detailLoading) return '正在读取批次'
      if (this.current?.windowNotice) return this.batchStatusLabel(this.current)
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
      if (this.detailError) return 'is-warning'
      if (this.current?.windowNotice) return 'is-warning'
      if (this.current?.status === 'ARCHIVED') return 'is-neutral'
      if (this.current?.status === 'LOCKED') return 'is-success'
      if (this.stats && Number(this.stats.courseCount || 0) === 0) return 'is-warning'
      if (this.stats && ['OPEN', 'CLOSED'].includes(this.current?.status) && Number(this.stats.lowEnrollCount || 0) > 0) return 'is-warning'
      if (this.current?.status === 'OPEN') return 'is-success'
      return 'is-info'
    },
    healthDescription() {
      if (this.detailError) return '当前详情读取失败，请重试后核对课程、容量与轮次。'
      if (this.current?.windowNotice) return this.current.windowNotice
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
  watch: {
    '$route.fullPath'() { this.resetContext() },
    ctx() { this.resetContext() }
  },
  created() {
    this.listGate = createAcademicRequestGate(() => this.pageContext())
    this.detailGate = createAcademicRequestGate(() => this.commandContext())
    this.rosterGate = createAcademicRequestGate(() => this.commandContext())
    this.load()
  },
  beforeUnmount() { this.disposed = true; this.invalidateSelection(); this.listGate.invalidate() },
  methods: {
    stepClass(index) { return { 'is-done': index < this.currentStep, 'is-current': index === this.currentStep } },
    pageContext() { return JSON.stringify([this.disposed, this.academicFlow?.identity() || academicIdentity(currentUserFromToken(), this.ctx), this.$route?.fullPath]) },
    commandContext() { return JSON.stringify([this.pageContext(), this.selectionVersion, this.current?.batchId, this.current?.status]) },
    isCurrent(key) { return !this.disposed && key === this.commandContext() },
    switchWorkspace(tab) {
      if (tab === this.activeTab) return
      const query = { ...this.$route.query }
      if (tab === 'batch') delete query.tab
      else query.tab = tab
      this.$router.replace({ path: this.$route.path, query })
    },
    onSpecialBatchUpdated(batch) {
      if (!batch || !this.current || String(batch.batchId) !== String(this.current.batchId)) return
      this.current = batch
      const index = this.rows.findIndex(row => String(row.batchId) === String(batch.batchId))
      if (index >= 0) this.rows.splice(index, 1, batch)
    },
    onSpecialDenied(message) {
      this.clearSensitiveSelectionData()
      this.error = message || '无权读取当前批次数据，已清除先前显示内容'
    },
    invalidateSelection() {
      this.selectionVersion += 1; this.writeSeq += 1
      this.detailGate?.invalidate(); this.rosterGate?.invalidate(); this.preflightRequestSeq += 1
      this.pendingAction = null; this.confirmVisible = false; this.confirmContext = ''
      this.courseVisible = false; this.roundVisible = false; this.rosterVisible = false
      this.preflight = null; this.preflightLoading = false; this.drawResult = null; this.saving = false
    },
    clearSensitiveSelectionData() {
      this.invalidateSelection()
      this.rows = []; this.pagination.total = 0; this.current = null
      this.courses = []; this.coursePagination.total = 0; this.rounds = []; this.stats = null
      this.rosterCourse = null; this.rosterRows = []; this.rosterPagination.total = 0
    },
    resetContext() {
      if (!this.listGate || this.disposed) return
      this.invalidateSelection(); this.current = null; this.rows = []; this.courses = []; this.rounds = []; this.stats = null
      this.createVisible = false; this.tickReceipt = null; this.load()
    },
    async runTimeTick() {
      if (this.tickBusy || this.saving) return
      const context = this.pageContext()
      this.tickBusy = true; this.tickReceipt = null
      try {
        const res = await api.timeTick()
        if (this.disposed || context !== this.pageContext()) return
        if (res.code !== 0) { toast.error(res.message || '时间处理失败'); return }
        const d = res.data || {}, problems = [...(d.blocked || []), ...(d.deferred || [])]
        this.tickReceipt = {
          partial: problems.length > 0 || !!d.scanLimitReached,
          message: `已开选 ${d.opened ?? 0} 个，已截止 ${d.closed ?? 0} 个。${problems.map(item => `批次 ${item.batchId}：${item.message}`).join('；')}${d.scanLimitReached ? '本次已达处理上限，请再次执行以处理剩余批次。' : ''}`
        }
        await this.load()
        if (!this.disposed && context === this.pageContext() && this.current) await this.select(this.current)
      } catch (error) {
        if (!this.disposed && context === this.pageContext()) toast.error(error?.message || '处理结果待核实，请刷新批次后核对')
      } finally { this.tickBusy = false }
    },
    batchStatusLabel(batch) {
      if (batch.status === 'OPEN' && batch.windowState === 'ENDED') return '窗口已截止，待收口'
      if (batch.status === 'OPEN' && batch.windowState === 'NOT_STARTED') return '窗口未开始'
      return this.statusLabel(batch.status)
    },
    statusLabel(s) { return _LABEL[s] || (s ? '状态待确认' : '—') },
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
      const context = this.commandContext()
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
        !this.isCurrent(context) || requestSeq !== this.preflightRequestSeq ||
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
      const latest = this.listGate.begin()
      this.loading = true; this.error = ''
      const res = await api.listBatches({ page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (!latest()) return
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
        if (!this.current && this.rows.length) {
          const requestedBatchId = this.$route?.query?.batchId
          const preferred = this.rows.find((row) => requestedBatchId && String(row.batchId) === String(requestedBatchId)) || this.rows.find((row) => ['OPEN', 'PUBLISHED', 'CLOSED'].includes(row.status)) || this.rows[0]
          await this.select(preferred)
        } else if (this.current) {
          const fresh = this.rows.find((row) => String(row.batchId) === String(this.current.batchId))
          if (fresh) this.current = fresh
        }
      } else {
        if (isDeniedResult(res)) {
          this.clearSensitiveSelectionData()
          this.error = res.message || '无权读取选课管理数据，已清除先前显示内容'
        } else this.error = res.message || '选课批次读取失败，请重试'
      }
      if (latest()) this.loading = false
    },
    onBatchPage({ page }) { this.pagination.page = page; this.current = null; this.load() },
    async select(b) {
      this.invalidateSelection()
      this.courses = []; this.stats = null; this.rounds = []; this.coursePagination.total = 0
      this.rosterRows = []; this.rosterCourse = null; this.rosterPagination.total = 0
      this.detailLoading = true
      this.current = b
      this.coursePagination.page = 1
      this.detailError = ''
      const selectedVersion = this.selectionVersion
      const selectedPageContext = this.pageContext()
      const formal = await api.getBatch(b.batchId)
      if (this.disposed || selectedPageContext !== this.pageContext() || selectedVersion !== this.selectionVersion || String(this.current?.batchId) !== String(b.batchId)) return
      if (formal.code !== 0) {
        this.detailLoading = false
        if (isDeniedResult(formal)) {
          this.clearSensitiveSelectionData()
          this.error = formal.message || '无权读取当前批次，已清除先前显示内容'
        } else this.detailError = formal.message || '当前批次正式信息读取失败，请重试'
        return
      }
      this.current = formal.data
      if (!['batch', 'rule'].includes(this.activeTab)) { this.detailLoading = false; return }
      const context = this.commandContext()
      await this.refreshDetail()
      if (!this.isCurrent(context) || this.detailError) return
      if (this.activeTab === 'batch') await this.refreshPreflight()
    },
    async refreshDetail() {
      if (!this.current || this.disposed) return
      const batchId = this.current.batchId
      const latest = this.detailGate.begin()
      this.courses = []; this.stats = null; this.rounds = []; this.detailError = ''; this.detailLoading = true
      const [cs, st, rd] = await Promise.all([
        api.listCourses(batchId, { page: this.coursePagination.page, pageSize: this.coursePagination.pageSize }),
        api.batchStats(batchId),
        api.listRounds(batchId)
      ])
      if (!latest()) return
      this.detailLoading = false
      const failed = [cs, st, rd].find(result => result.code !== 0)
      if (failed) {
        if (isDeniedResult(failed)) {
          this.clearSensitiveSelectionData()
          this.detailError = failed.message || '无权读取当前批次，已清除先前显示内容'
        } else this.detailError = failed.message || '当前批次读取失败，请重试'
        return
      }
      this.courses = cs.code === 0 ? cs.data.list : []
      this.coursePagination.total = cs.code === 0 ? cs.data.total : 0
      this.stats = st.code === 0 ? st.data : null
      this.rounds = rd.code === 0 ? (rd.data.items || []) : []
    },
    onCoursePage({ page }) { this.coursePagination.page = page; this.refreshDetail() },
    selectionRecordLabel(s) { return { SELECTED: '已取得名额', PENDING: '待抽签', PENDING_LOTTERY: '待抽签', LOST: '未中签', LOTTERY_LOST: '未中签', DROPPED: '已退课', COURSE_CANCELLED: '课程已取消', LOCKED: '名单已锁定' }[s] || '状态待核对' },
    roundStatusLabel(s) { return { DRAFT: '草稿', OPEN: '进行中', CLOSED: '已关闭', DRAWN: '已摇号' }[s] || (s ? '状态待确认' : '—') },
    roundStatusType(s) {
      if (s === 'OPEN') return 'success'
      if (s === 'DRAWN') return 'default'
      if (s === 'CLOSED') return 'warning'
      return 'primary'
    },
    openAddRound() { this.roundForm = { roundName: '', mode: 'FCFS', ctrl: 'BOTH' }; this.roundError = ''; this.roundVisible = true },
    async submitRound() {
      if (this.saving || !this.current) return
      const context = this.commandContext()
      if (!this.roundForm.roundName) { this.roundError = '轮次名称必填'; return }
      this.saving = true
      const res = await api.createRound(this.current.batchId, {
        roundName: this.roundForm.roundName, mode: this.roundForm.mode,
        allowEnroll: this.roundForm.ctrl !== 'DROP_ONLY',
        allowDrop: this.roundForm.ctrl !== 'ENROLL_ONLY'
      })
      if (!this.isCurrent(context)) return
      this.saving = false
      if (res.code === 0) { toast.success('轮次已创建'); this.roundVisible = false; await this.refreshDetail() }
      else this.roundError = res.message
    },
    roundAction(row, fn, label) {
      const roundId = row.roundId
      const context = this.commandContext()
      this.confirmTitle = label
      this.confirmMessage = `确认对「第${row.roundNo}轮 ${row.roundName}」执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api[fn](roundId)
        if (!this.isCurrent(context)) return
        if (res.code === 0) {
          toast.success(res.message || label + '成功')
          if (fn === 'drawRound') this.drawResult = res.data
          await this.refreshDetail()
        } else toast.error(res.message)
      }
      this.confirmContext = context; this.confirmVisible = true
    },
    openCreate() { this.form = { batchName: '', termId: '', maxCredits: 0, remark: '', scopeType: 'CLASS', classIds: [] }; this.formError = ''; this.createVisible = true },
    async submitCreate() {
      if (this.saving) return
      const context = this.pageContext()
      if (!this.form.batchName) { this.formError = '批次名称必填'; return }
      if (!this.form.termId) { this.formError = '学期必选'; return }
      if (this.form.scopeType !== 'SCHOOL' && !this.form.classIds?.length) { this.formError = '请选择适用班级'; return }
      this.saving = true
      const body = { batchName: this.form.batchName, termId: this.form.termId, remark: this.form.remark }
      if (this.form.scopeType !== 'SCHOOL') body.applyScope = { classIds: this.form.classIds.map(String) }
      if (this.form.maxCredits > 0) body.rule = { maxCredits: this.form.maxCredits }
      try {
        const res = await api.createBatch(body)
        if (context !== this.pageContext() || this.disposed) return
        if (res.code === 0) {
          toast.success('已创建'); this.createVisible = false
          await this.select(res.data)
          await this.load()
        } else this.formError = res.message
      } catch (error) {
        if (context === this.pageContext() && !this.disposed) this.formError = error?.message || '创建结果待核对，请先刷新批次列表'
      } finally { this.saving = false }
    },
    async lifecycle(fn, label) {
      if (!this.current || this.saving || this.detailLoading || this.detailError) return
      const batch = { ...this.current }
      const context = this.commandContext()
      const action = { publishBatch: 'PUBLISH', openBatch: 'OPEN', closeBatch: 'CLOSE', lockBatch: 'LOCK' }[fn]
      if (action) {
        const checked = await this.refreshPreflight()
        if (!this.isCurrent(context)) return
        if (!checked || !checked.allowed) {
          toast.error(this.preflightMessage(checked))
          return
        }
      }
      this.confirmTitle = label
      this.confirmMessage = `确认对批次「${batch.batchName}」（${batch.batchId}）执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api[fn](batch.batchId)
        if (!this.isCurrent(context)) return
        if (res.code === 0) {
          toast.success(label + '成功')
          const passiveEpoch = ++this.preflightRequestSeq
          this.preflight = null
          this.current = res.data
          await this.load()
          await this.refreshDetail()
          if (passiveEpoch === this.preflightRequestSeq) await this.refreshPreflight()
        }
        else toast.error(res.message)
      }
      this.confirmContext = context; this.confirmVisible = true
    },
    openAddCourse() {
      this.courseForm = { courseId: '', teachingTaskId: '', courseCode: '', courseName: '', teacherName: '', teachingClassName: '', capacity: 30, minCapacity: 1 }
      this.courseError = ''
      this.courseVisible = true
    },
    async searchSelectionTasks(keyword = '') {
      const context = this.commandContext()
      const termId = this.current?.termId
      if (!termId) return []
      const taskRes = await academicAffairsApi.listAllTasks({
        termId,
        status: 'READY',
        keyword: String(keyword || '').trim() || undefined,
        page: 1,
        pageSize: 50
      })
      if (!this.isCurrent(context)) return []
      if (taskRes.code !== 0) throw new Error(taskRes.message || '已就绪教学任务加载失败')
      return (taskRes.data?.list || [])
        .map((row) => ({
          value: row.taskId,
          label: [row.courseCode, row.courseName].filter(Boolean).join(' · ') || `教学任务 ${row.taskId}`,
          desc: [row.teachingClassName || row.className, row.teacherName].filter(Boolean).join(' · '),
          raw: row
        }))
    },
    onSelectionTaskChange(value, items) {
      const raw = items?.[0]?.raw || null
      this.courseForm.teachingTaskId = value || ''
      this.courseForm.courseId = raw?.courseId || ''
      this.courseForm.courseCode = raw?.courseCode || ''
      this.courseForm.courseName = raw?.courseName || ''
      this.courseForm.teacherName = raw?.teacherName || ''
      this.courseForm.teachingClassName = raw?.teachingClassName || raw?.className || ''
      this.courseError = ''
    },
    async submitCourse() {
      if (this.saving || !this.current) return
      const context = this.commandContext()
      if (!this.courseForm.teachingTaskId || !this.courseForm.courseId) {
        this.courseError = '请选择当前批次学期的已就绪教学任务'
        return
      }
      this.saving = true
      const res = await api.addCourse(this.current.batchId, {
        courseId: this.courseForm.courseId,
        teachingTaskId: this.courseForm.teachingTaskId,
        capacity: this.courseForm.capacity, minCapacity: this.courseForm.minCapacity
      })
      if (!this.isCurrent(context)) return
      this.saving = false
      if (res.code === 0) { toast.success('已添加'); this.courseVisible = false; await this.refreshDetail() }
      else this.courseError = res.message
    },
    cancelCourse(row) {
      const courseId = row.selectionCourseId
      const context = this.commandContext()
      this.confirmTitle = '取消开课'
      this.confirmMessage = `确认取消「${row.courseName}」开课？已选学生将置为课程取消状态。`
      this.pendingAction = async () => {
        const res = await api.cancelCourse(courseId)
        if (!this.isCurrent(context)) return
        if (res.code === 0) { toast.success('已取消开课'); await this.refreshDetail() }
        else toast.error(res.message)
      }
      this.confirmContext = context; this.confirmVisible = true
    },
    async openRoster(row) {
      if (!row) return
      this.rosterCourse = row; this.rosterRows = []; this.rosterVisible = true; this.rosterPagination.page = 1
      await this.loadRoster()
    },
    async loadRoster() {
      if (!this.rosterCourse) return
      const latest = this.rosterGate.begin()
      this.rosterLoading = true; this.rosterError = ''
      const res = await api.courseRoster(this.rosterCourse.selectionCourseId, {
        page: this.rosterPagination.page,
        pageSize: this.rosterPagination.pageSize
      })
      if (!latest()) return
      this.rosterLoading = false
      if (res.code === 0) { this.rosterRows = res.data.list; this.rosterPagination.total = res.data.total }
      else {
        this.rosterRows = []; this.rosterPagination.total = 0
        if (isDeniedResult(res)) {
          this.rosterCourse = null; this.rosterVisible = false
          this.rosterError = res.message || '无权读取课程名单，已清除先前显示内容'
        } else this.rosterError = res.message || '名单读取失败，请重试'
      }
    },
    onRosterPage({ page }) { this.rosterPagination.page = page; this.loadRoster() },
    async onConfirm() {
      const a = this.pendingAction
      const context = this.confirmContext
      this.pendingAction = null
      this.confirmVisible = false
      if (!a || this.saving || !this.isCurrent(context)) return
      const sequence = ++this.writeSeq
      this.saving = true
      try { await a() } finally { if (sequence === this.writeSeq) this.saving = false }
    }
  }
}
</script>

<style scoped>
.aa-selection-layout { display: grid; gap: 14px; }
.aa-selection-list-card,
.aa-selection-section,
.aa-selection-placeholder { border: 1px solid #dfe7f1; border-radius: 12px; background: var(--bg-card); }
.aa-selection-list-card { overflow: hidden; }
.aa-selection-list-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 15px 16px; border-bottom: 1px solid #e6edf5; }
.aa-selection-list-head h2,
.aa-selection-section-head h3 { margin: 4px 0 0; color: var(--text-primary); font-size: 16px; }
.aa-selection-eyebrow { color: var(--pri); font-size: 12px; font-weight: 750; letter-spacing: .08em; }
.aa-selection-list-count { min-width: 30px; padding: 5px 8px; border-radius: 999px; background: #eef5ff; color: var(--pri); font-size: 12px; font-weight: 700; text-align: center; }
.aa-selection-batches { list-style: none; margin: 0; padding: 10px; display: grid; grid-template-columns: repeat(auto-fit,minmax(250px,1fr)); gap: 8px; max-height: 230px; overflow: auto; }
.aa-selection-batch { display: grid; gap: 9px; padding: 13px 14px; border: 1px solid #e3eaf4; border-radius: 10px; background: #fff; cursor: pointer; transition: border-color .16s ease, background .16s ease; outline: none; }
.aa-selection-batch:hover,
.aa-selection-batch:focus-visible { border-color: #c9d9f2; background: var(--bg-card); box-shadow: 0 8px 22px -20px rgba(37, 99, 235, .45); }
.aa-selection-batch.is-active { border-color: #8fb4eb; background: #f4f8ff; box-shadow: inset 3px 0 0 #2f6fd2; }
.aa-selection-batch-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.aa-selection-batch-top strong { color: #1c2940; font-size: 13px; line-height: 1.45; }
.aa-selection-batch p { margin: 0; color: #718096; font-size: 12px; line-height: 1.45; }
.aa-selection-batch-next { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding-top: 8px; border-top: 1px dashed #dfe7f1; }
.aa-selection-batch-next span { color: #8895a7; font-size: 12px; }
.aa-selection-batch-next b { color: #44546a; font-size: 12px; font-weight: 650; }

.aa-selection-detail { min-width: 0; display: grid; gap: 14px; }
.aa-selection-preflight-alert { margin: 0; }
.aa-selection-placeholder { display: grid; justify-items: center; gap: 8px; min-height: 300px; align-content: center; padding: 28px; text-align: center; }
.aa-selection-placeholder-icon { display: grid; place-items: center; width: 54px; height: 54px; border-radius: 16px; background: #eef5ff; color: var(--pri); font-weight: 800; }
.aa-selection-placeholder strong { color: var(--text-primary); font-size: 15px; }
.aa-selection-placeholder span { max-width: 460px; color: #718096; font-size: 12px; line-height: 1.7; }

.aa-selection-hero { position: relative; display: grid; grid-template-columns: minmax(0,1fr) 230px auto; gap: 18px 24px; align-items: center; padding: 16px; border: 1px solid #dce6f3; border-left: 3px solid #2f6fd2; border-radius: 12px; background: #fff; }
.aa-selection-hero.is-closed { border-left-color: #d48716; }
.aa-selection-hero.is-locked,.aa-selection-hero.is-archived { border-left-color: #718096; }
.aa-selection-hero-topline { display: flex; align-items: center; gap: 10px; }
.aa-selection-hero h2 { margin: 7px 0 3px; color: #132038; font-size: 16px; letter-spacing: 0; }
.aa-selection-hero-main > p { max-width: 780px; margin: 0; color: #64748b; font-size: 12px; line-height: 1.65; }
.aa-selection-hero-main > p.aa-selection-source { margin-top: 2px; color: #758398; }
.aa-selection-hero-meta { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 6px; }
.aa-selection-hero-meta span { display: inline-flex; align-items: center; gap: 5px; color: #66758a; font-size: 12px; }
.aa-selection-hero-meta b { color: #32445e; font-weight: 700; }
.aa-selection-owner-card { display:grid; grid-template-columns:auto 1fr; gap:4px 10px; align-items:baseline; }
.aa-selection-owner-card span { color:#7b8798; font-size:11px; }
.aa-selection-owner-card strong { color:#1e293b; font-size:12px; }
.aa-selection-actions { display: flex; flex-wrap: wrap; gap: 8px; justify-content:flex-end; }

.aa-selection-steps { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); padding:14px 16px; border:1px solid #dfe7f1; border-radius:12px; background:#fff; }
.aa-selection-steps article { position:relative; display:flex; align-items:center; justify-content:center; gap:9px; min-width:0; }
.aa-selection-steps article:not(:last-child)::after { content:""; position:absolute; top:14px; right:-10%; width:20%; height:1px; background:#d8e1ec; }
.aa-selection-steps i { display:grid; place-items:center; width:25px; height:25px; flex:0 0 25px; border:1px solid #d8e1ec; border-radius:50%; color:#8390a2; font-size:11px; font-style:normal; }
.aa-selection-steps strong,.aa-selection-steps small { display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.aa-selection-steps strong { color:#526174; font-size:12px; }
.aa-selection-steps small { margin-top:2px; color:#97a2b2; font-size:10px; }
.aa-selection-steps .is-done i { border-color:#b9dfc7; background:#eef9f1; color:#27824a; }
.aa-selection-steps .is-current i { border-color:#2f6fd2; background:#2f6fd2; color:#fff; }
.aa-selection-steps .is-current strong { color:#2f6fd2; }
.aa-selection-summary { display:flex; align-items:center; justify-content:space-between; gap:20px; padding:14px 16px; border:1px solid #dfe7f1; border-radius:12px; background:#f8fbff; }
.aa-selection-summary > div { min-width:220px; }
.aa-selection-summary > div > span { display:block; margin-bottom:3px; color:#7b8798; font-size:11px; }.aa-selection-summary strong { display:block; color:#1e3556; font-size:14px; }
.aa-selection-summary p { margin:4px 0 0; color:#66758a; font-size:12px; }
.aa-selection-summary small { display:block; margin-top:5px; color:#355f96; font-size:11px; }
.aa-selection-summary dl { display:flex; gap:28px; margin:0; }
.aa-selection-summary dl div { display:grid; gap:2px; }
.aa-selection-summary dt { color:#7b8798; font-size:11px; }
.aa-selection-summary dd { margin:0; color:#1f4f91; font-size:17px; font-weight:700; }
.aa-selection-summary.is-warning { border-color:#ecd3a5; background:#fff9ed; }

.aa-selection-section { overflow: hidden; }
.aa-selection-section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; padding: 14px 16px; border-bottom: 1px solid #e6edf5; background: #fff; }
.aa-selection-section-head p { margin: 5px 0 0; color: #718096; font-size: 12px; line-height: 1.6; }
.aa-selection-table-wrap { padding: 4px 10px 10px; overflow-x: auto; }
.aa-selection-inline-empty { display: grid; grid-template-columns: 38px minmax(0, 1fr); gap: 12px; align-items: center; margin: 16px; padding: 16px; border: 1px dashed #d6e1ef; border-radius: 13px; background: #fafcff; }
.aa-selection-inline-empty > span { display: grid; place-items: center; width: 38px; height: 38px; border-radius: 11px; background: #eef5ff; color: var(--pri); font-weight: 750; }
.aa-selection-inline-empty strong { color: #26364c; font-size: 12px; }
.aa-selection-inline-empty p { margin: 4px 0 0; color: #748296; font-size: 12px; line-height: 1.6; }

.aa-selection-capacity { min-width: 150px; }
.aa-selection-capacity > div:first-child { display: flex; align-items: baseline; gap: 4px; color: #65758a; font-size: 12px; }
.aa-selection-capacity strong { color: #25364e; font-size: 13px; font-variant-numeric: tabular-nums; }
.aa-selection-capacity-bar { height: 6px; margin-top: 6px; overflow: hidden; border-radius: 999px; background: #edf2f7; }
.aa-selection-capacity-bar i { display: block; height: 100%; border-radius: inherit; background: linear-gradient(90deg, #70a4eb, #2f6fd2); }
.aa-selection-form { display: flex; flex-direction: column; gap: 12px; }

@media (max-width: 1280px) {
  .aa-selection-hero { grid-template-columns:minmax(0,1fr) 210px; }
  .aa-selection-actions { grid-column:1/-1; }
}
@media (max-width: 1080px) {
  .aa-selection-summary { align-items:flex-start; flex-direction:column; }
}
@media (max-width: 760px) {
  .aa-selection-hero { grid-template-columns: 1fr; padding: 20px; }
  .aa-selection-actions { grid-column: auto; }
  .aa-selection-batches { grid-template-columns: 1fr; }
  .aa-selection-section-head { flex-direction: column; }
  .aa-selection-steps { grid-template-columns:1fr; gap:10px; }
  .aa-selection-steps article { justify-content:flex-start; }
  .aa-selection-steps article::after { display:none; }
  .aa-selection-summary dl { display:grid; grid-template-columns:repeat(2,1fr); width:100%; }
}
</style>
