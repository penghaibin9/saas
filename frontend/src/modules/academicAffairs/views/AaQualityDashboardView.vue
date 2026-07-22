<template>
  <ModulePageShell
    title="教学质量"
    subtitle="运行质量看板 · 督导听课 · 巡课记录 · 教学检查 · 教学事故 · 质量整改 · 整改跟进 · 质量归档"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aaql-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aaql-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <!-- 运行质量看板 + 质量报告导出（原有能力，原样保留） -->
    <div v-if="tab === 'dashboard'" class="mp-stack">
      <div class="aaql-bar"><AppButton variant="primary" size="small" @click="openExport">导出质量报告</AppButton></div>
      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <template v-else>
        <div class="aaql-grid">
          <div v-for="i in indicators" :key="i.key" class="aaql-card">
            <div class="aaql-value">{{ i.value }}<span class="aaql-unit">{{ i.unit }}</span></div>
            <div class="aaql-label">{{ i.label }}</div>
            <div v-if="i.numerator != null" class="aaql-sub">{{ i.numerator }} / {{ i.denominator }}</div>
          </div>
        </div>
        <div class="aaql-section-title">质量报告导出历史</div>
        <EmptyState v-if="!reports.length" title="暂无导出记录" description="点击上方「导出质量报告」生成" />
        <DataTable v-else :columns="reportColumns" :rows="reports" row-key="exportId">
          <template #cell-occurredAt="{ row }">{{ fmt(row.occurredAt) }}</template>
        </DataTable>
      </template>
    </div>

    <!-- 01督导听课/02巡课记录/03教学检查/04教学事故：共用问题记录表，recordType 区分 -->
    <div v-else-if="isRecordTab" class="mp-stack">
      <AppInlineAlert v-if="tab === 'incident'" type="warning"
        description="教学事故认定标准与处理规则须依据学校教学事故认定管理办法，本页只提供上报/认定/关闭的记录与流转容器；认定（确认）动作仅限全校范围教务管理角色，学院范围角色可上报但不可认定。" />
      <div class="aaql-bar">
        <AppButton variant="primary" size="small" @click="openRecCreate">{{ recMeta.createLabel }}</AppButton>
        <AppSelect v-model="recStatusFilter" :options="recStatusOptions" placeholder="全部状态" @change="loadRecords" />
      </div>
      <LoadingState v-if="recLoading" />
      <EmptyState v-else-if="!recRows.length" :title="`暂无${recMeta.label}记录`" :description="`点击上方「${recMeta.createLabel}」新建`" />
      <DataTable v-else :columns="recColumns" :rows="recRows" row-key="recordId" row-clickable @row-click="viewRecDetail">
        <template #cell-status="{ row }"><StatusTag :type="recStatusType(row.status)" :label="recStatusLabel(row.status)" dot /></template>
        <template #cell-needRectify="{ row }"><span v-if="row.needRectify" class="aaql-flag">需整改</span></template>
        <template #cell-ops="{ row }">
          <button class="mp-link" @click.stop="viewRecDetail(row)">详情</button>
          <button v-if="row.status === 'SUBMITTED'" class="mp-link" @click.stop="confirmRec(row)">确认</button>
          <button v-if="row.status === 'CONFIRMED'" class="mp-link" @click.stop="closeRec(row)">关闭</button>
          <button v-if="row.status === 'SUBMITTED'" class="mp-link is-danger" @click.stop="cancelRec(row)">撤销</button>
          <button v-if="row.status !== 'SUBMITTED'" class="mp-link" @click.stop="openRectifyFromRecord(row)">发起整改</button>
        </template>
      </DataTable>
    </div>

    <!-- 05质量整改（发起视角）/ 06整改跟进（跟进视角）：共用整改任务表 -->
    <div v-else-if="isRectTab" class="mp-stack">
      <AppInlineAlert v-if="tab === 'followUp'" type="info" description="跟进视角：默认只显示未关闭的整改任务，逾期任务以「已逾期」标红提示。复核关闭/驳回仅限全校范围教务管理角色。" />
      <div class="aaql-bar">
        <AppButton variant="primary" size="small" @click="openRectCreate">发起质量整改任务</AppButton>
        <AppSelect v-model="rectStatusFilter" :options="rectStatusOptions" placeholder="全部状态" @change="loadRectifications" />
      </div>
      <LoadingState v-if="rectLoading" />
      <EmptyState v-else-if="!displayRectRows.length" title="暂无整改任务" description="从问题记录「发起整改」或点击上方「发起质量整改任务」新建" />
      <DataTable v-else :columns="rectColumns" :rows="displayRectRows" row-key="rectId" row-clickable @row-click="viewRectDetail">
        <template #cell-status="{ row }"><StatusTag :type="rectStatusType(row)" :label="rectStatusLabel(row)" dot /></template>
        <template #cell-deadline="{ row }">{{ fmt(row.deadline) || '—' }}</template>
        <template #cell-ops="{ row }">
          <button class="mp-link" @click.stop="viewRectDetail(row)">详情</button>
          <button v-if="['PENDING','IN_PROGRESS'].includes(row.status)" class="mp-link" @click.stop="openProgress(row)">记录跟进</button>
          <button v-if="['PENDING','IN_PROGRESS'].includes(row.status)" class="mp-link" @click.stop="openSubmitRect(row)">提交复核</button>
          <button v-if="row.status === 'SUBMITTED'" class="mp-link" @click.stop="openReview(row, 'APPROVE')">复核通过</button>
          <button v-if="row.status === 'SUBMITTED'" class="mp-link is-danger" @click.stop="openReview(row, 'REJECT')">驳回</button>
        </template>
      </DataTable>
    </div>

    <!-- 09质量归档：读侧聚合 + 导出 -->
    <div v-else-if="tab === 'archive'" class="mp-stack">
      <div class="aaql-bar">
        <AppTermEntityPicker v-model="archiveTermId" placeholder="全部学期" style="max-width:220px" @change="loadArchive" />
        <AppButton size="small" variant="ghost" :loading="archiveExporting" @click="doArchiveExport('records')">导出问题记录 xlsx</AppButton>
        <AppButton size="small" variant="ghost" :loading="archiveExporting" @click="doArchiveExport('rectifications')">导出整改任务 xlsx</AppButton>
      </div>
      <LoadingState v-if="archiveLoading" />
      <template v-else>
        <div class="aaql-section-title">按类型统计（01/02/03/04）</div>
        <div class="aaql-grid">
          <div v-for="rt in recordTypeKeys" :key="rt" class="aaql-card">
            <div class="aaql-value">{{ (archiveData.byType && archiveData.byType[rt] && archiveData.byType[rt].total) || 0 }}</div>
            <div class="aaql-label">{{ recTypeLabel(rt) }}</div>
            <div class="aaql-sub">已确认 {{ (archiveData.byType && archiveData.byType[rt] && archiveData.byType[rt].confirmed) || 0 }} · 已关闭 {{ (archiveData.byType && archiveData.byType[rt] && archiveData.byType[rt].closed) || 0 }}</div>
          </div>
        </div>
        <div class="aaql-section-title">整改任务统计（05/06）</div>
        <div class="aaql-grid">
          <div class="aaql-card"><div class="aaql-value">{{ archiveData.rectification && archiveData.rectification.total || 0 }}</div><div class="aaql-label">整改任务总数</div></div>
          <div class="aaql-card"><div class="aaql-value">{{ archiveData.rectification && archiveData.rectification.closed || 0 }}</div><div class="aaql-label">已关闭</div></div>
          <div class="aaql-card"><div class="aaql-value" :class="{ 'aaql-danger': (archiveData.rectification && archiveData.rectification.overdue) > 0 }">{{ archiveData.rectification && archiveData.rectification.overdue || 0 }}</div><div class="aaql-label">已逾期未关闭</div></div>
        </div>
        <AppInlineAlert type="info" description="质量归档为按学期读侧聚合+导出，不新建独立封存表；导出记录本身即留痕（写审计）。若需要与「教务归档」学期封存联动，待该二级模块统一规划。" />
      </template>
    </div>

    <!-- 报告导出 -->
    <AppDrawer :visible="exportVisible" title="导出教务运行质量报告" @close="exportVisible = false">
      <div class="aaql-form">
        <AppFormItem label="导出用途" required>
          <AppTextInput ref="purposeInput" v-model="exportPurpose" placeholder="如 期末教学质量分析（≥5字，写审计）" :disabled="exporting" />
          <AppQuickPhrases scene-key="common.exportPurpose" @pick="onPickPurpose" />
        </AppFormItem>
        <AppInlineAlert type="info" description="报告含挂科率/预警/发布率/毕业通过率等质量指标，导出带水印+审计。" />
        <AppInlineAlert v-if="exportError" type="danger" :description="exportError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="exporting" @click="exportVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="exporting" @click="doExport">导出 xlsx</AppButton>
      </template>
    </AppDrawer>

    <!-- 问题记录：新建 -->
    <AppDrawer :visible="recCreateVisible" :title="recMeta.createLabel" @close="recCreateVisible = false">
      <div class="aaql-form">
        <AppFormItem label="标题" required><AppTextInput v-model="recForm.title" :placeholder="recMeta.titlePlaceholder" :disabled="recSaving" /></AppFormItem>
        <AppFormItem v-if="recMeta.showTeacher" label="涉及教师"><AppTextInput v-model="recForm.teacherName" placeholder="教师姓名（选填）" :disabled="recSaving" /></AppFormItem>
        <AppFormItem v-if="recMeta.showCourse" label="涉及课程"><AppTextInput v-model="recForm.courseName" placeholder="课程名称（选填）" :disabled="recSaving" /></AppFormItem>
        <AppFormItem label="发生时间"><AppDateTimePicker v-model="recForm.occurredAt" :disabled="recSaving" /></AppFormItem>
        <AppFormItem label="地点/教室"><AppTextInput v-model="recForm.location" placeholder="选填" :disabled="recSaving" /></AppFormItem>
        <AppFormItem v-if="recMeta.showScore" label="评分（0-100）"><AppNumberInput v-model="recForm.score" :min="0" :max="100" :disabled="recSaving" /></AppFormItem>
        <AppFormItem :label="recMeta.categoryLabel"><AppTextInput v-model="recForm.category" :placeholder="recMeta.categoryPlaceholder" :disabled="recSaving" /></AppFormItem>
        <AppFormItem label="结论"><AppTextInput v-model="recForm.conclusion" placeholder="如 合格/待整改/不合格（自由文本）" :disabled="recSaving" /></AppFormItem>
        <AppFormItem label="详细描述"><AppTextarea v-model="recForm.description" :rows="3" placeholder="选填" :disabled="recSaving" /></AppFormItem>
        <AppFormItem v-if="tab === 'incident'" label="处理意见"><AppTextarea v-model="recForm.handlingNote" :rows="2" placeholder="人工填写，系统不自动判定处理结论" :disabled="recSaving" /></AppFormItem>
        <AppFormItem label="需要转入整改"><AppRadioGroup v-model="recForm.needRectify" :options="[{ label: '是', value: true }, { label: '否', value: false }]" /></AppFormItem>
        <AppInlineAlert v-if="recFormError" type="danger" :description="recFormError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="recSaving" @click="recCreateVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="recSaving" @click="submitRecCreate">提交</AppButton>
      </template>
    </AppDrawer>

    <!-- 问题记录：详情 -->
    <AppDrawer :visible="recDetailVisible" title="记录详情" @close="recDetailVisible = false">
      <AppDescriptionList v-if="recCurrent" :items="recDescItems" :columns="2">
        <template #status><StatusTag :type="recStatusType(recCurrent.status)" :label="recStatusLabel(recCurrent.status)" dot /></template>
      </AppDescriptionList>
    </AppDrawer>

    <!-- 整改任务：发起（含来源问题记录一键发起） -->
    <AppDrawer :visible="rectCreateVisible" :title="rectSourceRecord ? `从「${rectSourceRecord.title}」发起整改` : '发起质量整改任务'" @close="rectCreateVisible = false">
      <div class="aaql-form">
        <AppFormItem label="整改标题" required><AppTextInput v-model="rectForm.title" placeholder="如 XX课程教学检查整改" :disabled="rectSaving" /></AppFormItem>
        <AppFormItem label="整改要求" required><AppTextarea v-model="rectForm.requirement" :rows="3" placeholder="≥5字，写审计" :disabled="rectSaving" /></AppFormItem>
        <AppFormItem label="责任人"><AppTextInput v-model="rectForm.responsibleName" placeholder="选填，默认取来源记录涉及教师" :disabled="rectSaving" /></AppFormItem>
        <AppFormItem label="整改期限"><AppDateTimePicker v-model="rectForm.deadline" :disabled="rectSaving" /></AppFormItem>
        <AppInlineAlert v-if="rectFormError" type="danger" :description="rectFormError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="rectSaving" @click="rectCreateVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="rectSaving" @click="submitRectCreate">发起</AppButton>
      </template>
    </AppDrawer>

    <!-- 整改任务：详情 + 跟进时间线 -->
    <AppDrawer :visible="rectDetailVisible" title="整改任务详情" @close="rectDetailVisible = false">
      <div v-if="rectCurrent" class="aaql-detail">
        <AppDescriptionList :items="rectDescItems" :columns="2">
          <template #status><StatusTag :type="rectStatusType(rectCurrent)" :label="rectStatusLabel(rectCurrent)" dot /></template>
          <template #deadline><b :class="{ 'aaql-danger': rectCurrent.overdue }">{{ fmt(rectCurrent.deadline) || '—' }}<span v-if="rectCurrent.overdue">（已逾期）</span></b></template>
        </AppDescriptionList>
        <div class="aaql-section-title">跟进时间线</div>
        <AppTimeline :items="rectTimelineItems" />
      </div>
    </AppDrawer>

    <!-- 跟进说明 / 提交复核 -->
    <AppDrawer :visible="rectNoteVisible" :title="rectNoteMode === 'progress' ? '记录整改跟进' : '提交整改说明待复核'" @close="rectNoteVisible = false">
      <div class="aaql-form">
        <AppFormItem :label="rectNoteMode === 'progress' ? '跟进说明' : '整改说明'" required>
          <AppTextarea v-model="rectNoteText" :rows="4" placeholder="请填写具体进展或整改结果说明" :disabled="rectSaving" />
        </AppFormItem>
        <AppInlineAlert v-if="rectFormError" type="danger" :description="rectFormError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="rectSaving" @click="rectNoteVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="rectSaving" @click="submitRectNote">提交</AppButton>
      </template>
    </AppDrawer>

    <!-- 复核（通过/驳回） -->
    <AppDrawer :visible="reviewVisible" :title="reviewAction === 'APPROVE' ? '复核通过并关闭' : '驳回整改'" @close="reviewVisible = false">
      <div class="aaql-form">
        <AppFormItem :label="reviewAction === 'APPROVE' ? '复核结论（选填）' : '驳回原因'" :required="reviewAction === 'REJECT'">
          <AppTextarea v-model="reviewReason" :rows="3" :placeholder="reviewAction === 'REJECT' ? '≥5字，写审计' : '选填'" :disabled="rectSaving" />
        </AppFormItem>
        <AppInlineAlert v-if="rectFormError" type="danger" :description="rectFormError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="rectSaving" @click="reviewVisible = false">取消</AppButton>
        <AppButton :variant="reviewAction === 'APPROVE' ? 'primary' : 'danger'" :loading="rectSaving" @click="submitReview">确定</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 教学质量（/admin/academic-affairs/quality）：运行质量看板+报告导出 +
 *  01督导听课/02巡课记录/03教学检查/04教学事故（共用问题记录）+
 *  05质量整改/06整改跟进（共用整改任务，发起/跟进两视角）+ 09质量归档（读侧聚合+导出）。
 *  R3 续工：docs/03-业务模块设计/教务中心/施工包/教学质量/三级施工卡/{01..06,09}-*.md。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppRadioGroup, AppFormItem, AppInlineAlert, AppTimeline, AppDateTimePicker, AppQuickPhrases, AppDescriptionList, AppTermEntityPicker } from '@/components/common'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { academicAffairsApi, academicAffairsQualityApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _REC_TYPE_META = {
  supervision: { type: 'SUPERVISION', label: '督导听课', createLabel: '登记听课记录',
                titlePlaceholder: '如 2026春第3周推门听课', categoryLabel: '分类',
                categoryPlaceholder: '选填，自由文本', showScore: true, showTeacher: true, showCourse: true },
  patrol: { type: 'PATROL', label: '巡课记录', createLabel: '登记巡课记录',
           titlePlaceholder: '如 教学楼A栋日常巡查', categoryLabel: '问题分类',
           categoryPlaceholder: '如 迟到早退/教学秩序/设备故障（自由文本）', showScore: false, showTeacher: true, showCourse: false },
  inspection: { type: 'INSPECTION', label: '教学检查', createLabel: '登记检查结果',
               titlePlaceholder: '如 期末命题专项检查', categoryLabel: '检查类型',
               categoryPlaceholder: '如 期末命题/毕业论文选题/教材评估（自由文本）', showScore: true, showTeacher: true, showCourse: true },
  incident: { type: 'INCIDENT', label: '教学事故', createLabel: '上报教学事故',
             titlePlaceholder: '简要事件描述', categoryLabel: '严重程度',
             categoryPlaceholder: '如 轻微/一般/严重（自由文本，非系统锁定标准，具体认定以学校制度为准）',
             showScore: false, showTeacher: true, showCourse: true }
}
const _REC_TYPE_KEYS = Object.keys(_REC_TYPE_META)
const _REC_STATUS_LABEL = { SUBMITTED: '待确认', CONFIRMED: '已确认', CLOSED: '已关闭' }
const _REC_STATUS_TYPE = { SUBMITTED: 'primary', CONFIRMED: 'warning', CLOSED: 'default' }
const _RECT_STATUS_LABEL = { PENDING: '待整改', IN_PROGRESS: '整改中', SUBMITTED: '待复核', CLOSED: '已关闭' }
const _RECT_STATUS_TYPE = { PENDING: 'primary', IN_PROGRESS: 'warning', SUBMITTED: 'processing', CLOSED: 'default' }

export default {
  name: 'AaQualityDashboardView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppDrawer,
               AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppRadioGroup, AppFormItem, AppInlineAlert,
               AppTimeline, AppDateTimePicker, AppQuickPhrases, AppDescriptionList, AppTermEntityPicker },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'dashboard',
      tabs: [
        { key: 'dashboard', label: '运行质量看板' },
        { key: 'supervision', label: '督导听课' },
        { key: 'patrol', label: '巡课记录' },
        { key: 'inspection', label: '教学检查' },
        { key: 'incident', label: '教学事故' },
        { key: 'rectify', label: '质量整改' },
        { key: 'followUp', label: '整改跟进' },
        { key: 'archive', label: '质量归档' }
      ],
      // dashboard
      loading: true, error: '', indicators: [], reports: [],
      reportColumns: [{ key: 'operator', title: '导出人' }, { key: 'roleName', title: '角色' }, { key: 'detail', title: '用途' }, { key: 'occurredAt', title: '时间' }],
      exportVisible: false, exportPurpose: '', exportError: '', exporting: false,
      // 问题记录（01/02/03/04）
      recLoading: false, recRows: [], recStatusFilter: '',
      recStatusOptions: [{ label: '全部状态', value: '' }, { label: '待确认', value: 'SUBMITTED' }, { label: '已确认', value: 'CONFIRMED' }, { label: '已关闭', value: 'CLOSED' }],
      recColumns: [{ key: 'title', title: '标题' }, { key: 'teacherName', title: '教师' }, { key: 'courseName', title: '课程' },
                  { key: 'conclusion', title: '结论' }, { key: 'status', title: '状态' }, { key: 'needRectify', title: '' }, { key: 'ops', title: '操作' }],
      recCreateVisible: false, recForm: {}, recFormError: '', recSaving: false,
      recDetailVisible: false, recCurrent: null,
      // 整改任务（05/06）
      rectLoading: false, rectRows: [], rectStatusFilter: '',
      rectStatusOptions: [{ label: '全部状态', value: '' }, { label: '待整改', value: 'PENDING' }, { label: '整改中', value: 'IN_PROGRESS' }, { label: '待复核', value: 'SUBMITTED' }, { label: '已关闭', value: 'CLOSED' }],
      rectColumns: [{ key: 'title', title: '标题' }, { key: 'sourceTitle', title: '来源' }, { key: 'responsibleName', title: '责任人' },
                   { key: 'deadline', title: '期限' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      rectCreateVisible: false, rectForm: {}, rectFormError: '', rectSaving: false, rectSourceRecord: null,
      rectDetailVisible: false, rectCurrent: null,
      rectNoteVisible: false, rectNoteMode: '', rectNoteText: '', rectNoteTargetId: '',
      reviewVisible: false, reviewAction: '', reviewReason: '', reviewTargetId: '',
      // 归档
      archiveLoading: false, archiveData: {}, archiveTermId: '', archiveExporting: false
    }
  },
  computed: {
    isRecordTab() { return _REC_TYPE_KEYS.includes(this.tab) },
    isRectTab() { return this.tab === 'rectify' || this.tab === 'followUp' },
    recMeta() { return _REC_TYPE_META[this.tab] || {} },
    recordTypeKeys() { return _REC_TYPE_KEYS.map((k) => _REC_TYPE_META[k].type) },
    /** 跟进视角（06）未显式选状态时默认隐藏已关闭，并把逾期任务排到最前；发起视角（05）显示全部。 */
    displayRectRows() {
      let rows = this.rectRows
      if (this.tab === 'followUp' && !this.rectStatusFilter) {
        rows = rows.filter((r) => r.status !== 'CLOSED')
      }
      if (this.tab === 'followUp') {
        rows = [...rows].sort((a, b) => (b.overdue === a.overdue ? 0 : b.overdue ? 1 : -1))
      }
      return rows
    },
    /** 记录详情键值 → AppDescriptionList items（仅展示层映射，数据取自 recCurrent，不改数据流）。 */
    recDescItems() {
      const r = this.recCurrent
      if (!r) return []
      const items = [
        { label: '类型', value: this.recTypeLabel(r.recordType) },
        { label: '标题', value: r.title },
        { key: 'status', label: '状态', value: '' },
        { label: '教师', value: r.teacherName || '—' },
        { label: '课程', value: r.courseName || '—' },
        { label: '发生时间', value: this.fmt(r.occurredAt) || '—' },
        { label: '地点', value: r.location || '—' },
        { label: '分类/等级', value: r.category || '—' }
      ]
      if (r.score != null) items.push({ label: '评分', value: r.score })
      items.push({ label: '结论', value: r.conclusion || '—' })
      items.push({ label: '详细描述', value: r.description || '—', span: 2 })
      if (r.handlingNote) items.push({ label: '处理意见', value: r.handlingNote, span: 2 })
      items.push({ label: '记录人', value: r.recorderName || '—' })
      if (r.confirmedByName) items.push({ label: '确认人', value: `${r.confirmedByName}（${this.fmt(r.confirmedAt)}）` })
      return items
    },
    /** 整改任务详情键值 → AppDescriptionList items（status/deadline 用具名插槽保留标签与逾期红色）。 */
    rectDescItems() {
      const r = this.rectCurrent
      if (!r) return []
      const items = [
        { label: '标题', value: r.title },
        { key: 'status', label: '状态', value: '' }
      ]
      if (r.sourceTitle) items.push({ label: '来源记录', value: `${r.sourceTitle}（${this.recTypeLabel(r.sourceType)}）` })
      items.push({ label: '整改要求', value: r.requirement, span: 2 })
      items.push({ label: '责任人', value: r.responsibleName || '—' })
      items.push({ key: 'deadline', label: '期限', value: '' })
      if (r.resultNote) items.push({ label: '复核结论', value: r.resultNote, span: 2 })
      return items
    },
    /** 整改详情跟进时间线：progressLog[{time,operator,action,note}] → AppTimeline items。 */
    rectTimelineItems() {
      const log = (this.rectCurrent && this.rectCurrent.progressLog) || []
      const actionLabel = { CREATE: '发起整改', PROGRESS: '记录跟进', SUBMIT: '提交复核', APPROVE: '复核通过', REJECT: '复核驳回' }
      const actionType = { CREATE: 'primary', PROGRESS: 'processing', SUBMIT: 'warning', APPROVE: 'success', REJECT: 'danger' }
      return log.map((e) => ({
        time: e.time ? String(e.time).replace('T', ' ').slice(0, 19) : '',
        title: actionLabel[e.action] || e.action,
        operator: e.operator,
        description: e.note,
        type: actionType[e.action] || 'default'
      }))
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    this.$watch(
      () => this.$route && this.$route.query && this.$route.query.tab,
      (v) => {
        const next = v && this.tabs.some((t) => t.key === v) ? v : 'dashboard'
        if (next !== this.tab) { this.tab = next; this.afterTabLoad() }
      },
      { immediate: true }
    )
    if (this.tab === 'dashboard') this.load()
  },
  methods: {
    onPickPurpose(text) {
      const el = this.$refs.purposeInput && this.$refs.purposeInput.$refs.input
      const { value, selStart, selEnd } = insertAtCursor(el, this.exportPurpose, text)
      this.exportPurpose = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    fmt(s) { return s ? String(s).replace('T', ' ').slice(0, 16) : '' },
    recTypeLabel(rt) { const m = Object.values(_REC_TYPE_META).find((x) => x.type === rt); return m ? m.label : rt },
    recStatusLabel(s) { return _REC_STATUS_LABEL[s] || s },
    recStatusType(s) { return _REC_STATUS_TYPE[s] || 'default' },
    rectStatusLabel(r) { return r.overdue && r.status !== 'CLOSED' ? '已逾期' : (_RECT_STATUS_LABEL[r.status] || r.status) },
    rectStatusType(r) { return r.overdue && r.status !== 'CLOSED' ? 'danger' : (_RECT_STATUS_TYPE[r.status] || 'default') },
    switchTab(k) {
      if (k === this.tab) return
      this.$router.push({ path: this.$route.path, query: k === 'dashboard' ? {} : { tab: k } })
    },
    afterTabLoad() {
      if (this.tab === 'dashboard') this.load()
      else if (this.isRecordTab) this.loadRecords()
      else if (this.isRectTab) this.loadRectifications()
      else if (this.tab === 'archive') this.loadArchive()
    },
    // ── 看板 ──
    async load() {
      this.loading = true; this.error = ''
      const [d, r] = await Promise.all([api.dashboard(), api.reports({ pageSize: 50 })])
      if (d.code === 0) this.indicators = d.data.indicators
      else this.error = d.message
      this.reports = r.code === 0 ? r.data.list : []
      this.loading = false
    },
    openExport() { this.exportPurpose = ''; this.exportError = ''; this.exportVisible = true },
    async doExport() {
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) { this.exportError = '用途至少5字'; return }
      this.exporting = true
      const res = await api.exportReport({ purpose: this.exportPurpose.trim() })
      this.exporting = false
      if (res.code === 0) {
        this._download(res.data, 'academic_quality_report.xlsx')
        toast.success('已导出'); this.exportVisible = false; this.load()
      } else this.exportError = res.message
    },
    _download(blob, filename) {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
      URL.revokeObjectURL(url)
    },
    // ── 01/02/03/04 问题记录 ──
    async loadRecords() {
      this.recLoading = true
      const res = await api.listRecords({ recordType: this.recMeta.type, status: this.recStatusFilter || undefined, pageSize: 100 })
      this.recRows = res.code === 0 ? res.data.list : []
      this.recLoading = false
    },
    openRecCreate() {
      this.recForm = { needRectify: false }
      this.recFormError = ''
      this.recCreateVisible = true
    },
    async submitRecCreate() {
      if (!this.recForm.title || !this.recForm.title.trim()) { this.recFormError = '标题必填'; return }
      this.recSaving = true
      const res = await api.createRecord({ recordType: this.recMeta.type, ...this.recForm })
      this.recSaving = false
      if (res.code === 0) { toast.success('已创建'); this.recCreateVisible = false; this.loadRecords() }
      else this.recFormError = res.message
    },
    async viewRecDetail(row) {
      const res = await api.getRecord(row.recordId)
      if (res.code === 0) { this.recCurrent = res.data; this.recDetailVisible = true }
      else toast.error(res.message)
    },
    async confirmRec(row) {
      const res = await api.confirmRecord(row.recordId)
      if (res.code === 0) { toast.success('已确认'); this.loadRecords() } else toast.error(res.message)
    },
    async closeRec(row) {
      const res = await api.closeRecord(row.recordId)
      if (res.code === 0) { toast.success('已关闭'); this.loadRecords() } else toast.error(res.message)
    },
    async cancelRec(row) {
      const res = await api.cancelRecord(row.recordId)
      if (res.code === 0) { toast.success('已撤销'); this.loadRecords() } else toast.error(res.message)
    },
    // ── 05/06 质量整改与跟进 ──
    async loadRectifications() {
      this.rectLoading = true
      const res = await api.listRectifications({ status: this.rectStatusFilter || undefined, pageSize: 100 })
      this.rectRows = res.code === 0 ? res.data.list : []
      this.rectLoading = false
    },
    openRectCreate() {
      this.rectSourceRecord = null
      this.rectForm = {}
      this.rectFormError = ''
      this.rectCreateVisible = true
    },
    openRectifyFromRecord(row) {
      this.rectSourceRecord = row
      this.rectForm = { title: `${row.title} · 整改` }
      this.rectFormError = ''
      this.rectCreateVisible = true
    },
    async submitRectCreate() {
      if (!this.rectForm.title || !this.rectForm.title.trim()) { this.rectFormError = '标题必填'; return }
      if (!this.rectForm.requirement || this.rectForm.requirement.trim().length < 5) { this.rectFormError = '整改要求必填且不少于5字'; return }
      this.rectSaving = true
      const res = this.rectSourceRecord
        ? await api.rectifyFromRecord(this.rectSourceRecord.recordId, this.rectForm)
        : await api.createRectification(this.rectForm)
      this.rectSaving = false
      if (res.code === 0) {
        toast.success('已发起')
        this.rectCreateVisible = false
        if (this.isRectTab) this.loadRectifications()
      } else this.rectFormError = res.message
    },
    async viewRectDetail(row) {
      const res = await api.getRectification(row.rectId)
      if (res.code === 0) { this.rectCurrent = res.data; this.rectDetailVisible = true }
      else toast.error(res.message)
    },
    openProgress(row) { this.rectNoteMode = 'progress'; this.rectNoteTargetId = row.rectId; this.rectNoteText = ''; this.rectFormError = ''; this.rectNoteVisible = true },
    openSubmitRect(row) { this.rectNoteMode = 'submit'; this.rectNoteTargetId = row.rectId; this.rectNoteText = ''; this.rectFormError = ''; this.rectNoteVisible = true },
    async submitRectNote() {
      if (!this.rectNoteText || this.rectNoteText.trim().length < 2) { this.rectFormError = '说明必填'; return }
      this.rectSaving = true
      const res = this.rectNoteMode === 'progress'
        ? await api.addProgress(this.rectNoteTargetId, this.rectNoteText.trim())
        : await api.submitRectification(this.rectNoteTargetId, this.rectNoteText.trim())
      this.rectSaving = false
      if (res.code === 0) { toast.success('已提交'); this.rectNoteVisible = false; this.loadRectifications() }
      else this.rectFormError = res.message
    },
    openReview(row, action) { this.reviewAction = action; this.reviewTargetId = row.rectId; this.reviewReason = ''; this.rectFormError = ''; this.reviewVisible = true },
    async submitReview() {
      if (this.reviewAction === 'REJECT' && (!this.reviewReason || this.reviewReason.trim().length < 5)) { this.rectFormError = '驳回原因必填且不少于5字'; return }
      this.rectSaving = true
      const res = await api.reviewRectification(this.reviewTargetId, this.reviewAction, this.reviewReason.trim())
      this.rectSaving = false
      if (res.code === 0) { toast.success('已复核'); this.reviewVisible = false; this.loadRectifications() }
      else this.rectFormError = res.message
    },
    // ── 09 质量归档 ──
    async loadArchive() {
      this.archiveLoading = true
      const res = await api.archiveOverview({ termId: this.archiveTermId || undefined })
      this.archiveData = res.code === 0 ? res.data : {}
      this.archiveLoading = false
    },
    async doArchiveExport(domain) {
      this.archiveExporting = true
      const res = await api.archiveExport(domain, { termId: this.archiveTermId || undefined, purpose: `质量归档导出-${domain}` })
      this.archiveExporting = false
      if (res.code === 0) { this._download(res.data, `quality_archive_${domain}.xlsx`); toast.success('已导出') }
      else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
.aaql-tabs { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 16px; border-bottom: 1px solid var(--border-color, #e5e7eb); }
.aaql-tab { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aaql-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 500; }
.aaql-bar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }
.aaql-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 12px; margin-bottom: 20px; }
.aaql-card { padding: 16px; background: var(--fill-light, #f8fafc); border-radius: 10px; }
.aaql-value { font-size: 26px; font-weight: 700; color: var(--primary-color, #2563eb); }
.aaql-value.aaql-danger { color: var(--danger-color, #dc2626); }
.aaql-unit { font-size: 14px; margin-left: 2px; color: var(--text-secondary, #64748b); }
.aaql-label { margin-top: 4px; font-size: 13px; color: var(--text-secondary, #64748b); }
.aaql-sub { margin-top: 2px; font-size: 12px; color: var(--text-tertiary, #94a3b8); }
.aaql-section-title { font-weight: 500; margin: 8px 0 12px; }
.aaql-form { display: flex; flex-direction: column; gap: 12px; }
.aaql-flag { font-size: 12px; padding: 1px 6px; border-radius: 4px; background: var(--warning-bg, #fef3c7); color: var(--warning-color, #b45309); }
.aaql-detail { display: flex; flex-direction: column; gap: 10px; }
.aaql-detail-row { display: flex; flex-direction: column; gap: 2px; font-size: 13px; }
.aaql-detail-row span { color: var(--text-tertiary, #94a3b8); font-size: 12px; }
.aaql-detail-row b.aaql-danger { color: var(--danger-color, #dc2626); }
.aaql-detail-row p { margin: 0; white-space: pre-wrap; word-break: break-word; }
</style>
