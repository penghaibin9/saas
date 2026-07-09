<template>
  <ModulePageShell
    title="题目库"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <div class="gd-actions">
        <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
        <AppExportButton
          v-if="exportVisible"
          :export-fn="exportTopicsLibFn"
        >导出 Excel</AppExportButton>
      </div>
    </template>

    <!-- 分类 / 容量概览 -->
    <div v-if="activePanel === 'category' && categoryStats.length" class="mp-stats">
      <div v-for="c in categoryStats.slice(0, 6)" :key="c.category" class="mp-stat" @click="drillCategory(c.category)">
        <div class="mp-stat__val">{{ c.count }}</div>
        <div class="mp-stat__lbl">{{ c.category }}</div>
        <div class="mp-stat__sub">入池 {{ c.inPool }} · 满员 {{ c.full }}</div>
      </div>
    </div>
    <div v-if="activePanel === 'capacity' && libStats" class="mp-stats">
      <div class="mp-stat"><div class="mp-stat__val">{{ libStats.inPool }}</div><div class="mp-stat__lbl">在池题目</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ libStats.availableCount }}</div><div class="mp-stat__lbl">可选余量</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ libStats.fullCount }}</div><div class="mp-stat__lbl">已满员</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ libStats.uncategorized }}</div><div class="mp-stat__lbl">未分类</div></div>
    </div>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDesc" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-title="{ row }">
          <div class="mp-cell-main">{{ row.title }}</div>
          <div class="mp-cell-sub">{{ row.topicNo || '无编号' }} · {{ row.majorName || '—' }}</div>
        </template>
        <template #cell-category="{ row }">
          <StatusTag v-if="row.category" type="info" :label="row.category" />
          <span v-else class="mp-note">未分类</span>
        </template>
        <template #cell-source="{ row }">
          <StatusTag :type="sourceTone(row.sourceType)" :label="row.sourceLabel" />
          <div v-if="row.enterpriseName" class="mp-cell-sub">{{ row.enterpriseName }}</div>
        </template>
        <template #cell-advisor="{ row }">{{ row.advisorName || '—' }}</template>
        <template #cell-capacity="{ row }">
          <span :class="{ 'mp-note': row.isFull }">{{ row.selected }}/{{ row.capacity }}</span>
          <span v-if="row.isFull" class="mp-cell-sub">已满员</span>
          <span v-else class="mp-cell-sub">余 {{ row.remaining }}</span>
        </template>
        <template #cell-requirements="{ row }">
          <span v-if="row.hasRequirements" class="mp-cell-sub">{{ truncate(row.requirements, 48) }}</span>
          <StatusTag v-else type="warning" label="待补全" />
        </template>
        <template #cell-attachments="{ row }">
          <span v-if="row.attachmentCount">{{ row.attachmentCount }} 个附件</span>
          <StatusTag v-else type="warning" label="无附件" />
        </template>
        <template #cell-review="{ row }">
          <StatusTag :type="row.reviewTone" :label="row.reviewLabel" dot />
          <div v-if="row.reviewComment" class="mp-cell-sub">{{ row.reviewComment }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.statusTone" :label="row.statusLabel" />
        </template>
        <template #cell-historyTopic="{ row }">
          <div class="mp-cell-main">{{ row.topicTitle || '—' }}</div>
          <div class="mp-cell-sub">ID {{ row.topicId || '—' }}</div>
        </template>
        <template #cell-historyAction="{ row }">
          <StatusTag type="info" :label="row.action" />
        </template>
        <template #cell-historyOperator="{ row }">
          <div>{{ row.operator }}</div>
          <div v-if="row.roleName" class="mp-cell-sub">{{ row.roleName }}</div>
        </template>
        <template #cell-historyDetail="{ row }">
          <div class="mp-cell-sub">{{ row.detail || '—' }}</div>
          <div v-if="row.beforeVal || row.afterVal" class="mp-cell-sub">{{ row.beforeVal }} → {{ row.afterVal }}</div>
        </template>
        <template #cell-historyTime="{ row }">{{ row.occurredAt || '—' }}</template>
        <template #cell-actions="{ row }">
          <template v-if="isHistoryPanel">
            <button v-if="row.topicId" class="mp-link" @click="openDetailById(row.topicId)">查看题目</button>
          </template>
          <template v-else>
            <button class="mp-link" @click="openDetail(row)">详情</button>
            <button
              v-if="canEdit(row)"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openEdit(row)"
            >编辑</button>
            <button
              v-if="activePanel === 'capacity' && row.status !== 'ARCHIVED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openCapacity(row)"
            >调容量</button>
            <button
              v-if="activePanel === 'requirements' && row.status !== 'ARCHIVED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openRequirements(row)"
            >补要求</button>
            <button
              v-if="activePanel === 'attachments' && row.status !== 'ARCHIVED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openAttachments(row)"
            >管附件</button>
            <button
              v-if="activePanel === 'category' && row.status !== 'ARCHIVED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="openCategoryEdit(row)"
            >改分类</button>
            <button
              v-if="row.reviewStatus === 'DRAFT' || row.reviewStatus === 'REJECTED'"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="askSubmitReview(row)"
            >提交审核</button>
            <template v-if="activePanel === 'pending' && row.reviewStatus === 'PENDING_REVIEW'">
              <button class="mp-link" style="margin-left: var(--space-2)" @click="askReview(row, 'APPROVE')">通过</button>
              <button class="mp-link" style="margin-left: var(--space-2)" @click="askReview(row, 'REJECT')">驳回</button>
            </template>
            <button
              v-if="row.status === 'CONFIRMED' && row.reviewStatus === 'APPROVED' && !panelOnlyOps"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="askDisable(row)"
            >停用</button>
            <button
              v-if="row.status === 'DISABLED' && !panelOnlyOps"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="askEnable(row)"
            >启用</button>
            <button
              v-if="row.status !== 'ARCHIVED' && !panelOnlyOps"
              class="mp-link"
              style="margin-left: var(--space-2)"
              @click="askArchive(row)"
            >归档</button>
          </template>
        </template>
      </DataTable>
    </div>

    <!-- 申报 / 编辑 -->
    <AppDrawer v-model:visible="editVisible" :title="editing ? '编辑题目' : applyTitle">
      <form class="ie-form" @submit.prevent="submitForm">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">题目名称 <i>*</i></span>
          <input v-model.trim="form.title" class="ie-in" placeholder="2~300字" />
        </label>
        <label class="ie-fld"><span class="ie-lbl">毕设批次</span>
          <select v-model="form.batchId" class="ie-in">
            <option value="">不关联批次</option>
            <option v-for="b in batchOpts" :key="b.id" :value="b.id">{{ b.batchName }}</option>
          </select>
        </label>
        <label class="ie-fld"><span class="ie-lbl">题目编号</span><input v-model.trim="form.topicNo" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">指导教师</span><input v-model.trim="form.advisorName" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">专业</span><input v-model.trim="form.majorName" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">分类</span>
          <select v-model="form.category" class="ie-in">
            <option value="">请选择</option>
            <option v-for="c in GD_TOPIC_CATEGORY" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <label class="ie-fld"><span class="ie-lbl">难度</span>
          <select v-model="form.difficulty" class="ie-in">
            <option value="">请选择</option>
            <option v-for="d in GD_TOPIC_DIFFICULTY" :key="d.value" :value="d.value">{{ d.label }}</option>
          </select>
        </label>
        <label v-if="form.sourceType === 'ENTERPRISE'" class="ie-fld ie-fld--full">
          <span class="ie-lbl">企业名称</span><input v-model.trim="form.enterpriseName" class="ie-in" />
        </label>
        <label class="ie-fld"><span class="ie-lbl">容量</span>
          <input v-model.number="form.capacity" type="number" min="1" max="99" class="ie-in" />
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">题目要求</span>
          <textarea v-model.trim="form.requirements" class="ie-in" rows="3" />
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">预期成果</span>
          <textarea v-model.trim="form.outcome" class="ie-in" rows="2" />
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">技能要求</span>
          <textarea v-model.trim="form.skills" class="ie-in" rows="2" />
        </label>
        <label v-if="!editing" class="ie-fld ie-fld--full">
          <input v-model="form.submitReview" type="checkbox" /> 保存后直接提交审核
        </label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="editVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 调容量 -->
    <AppDrawer v-model:visible="capacityVisible" title="调整题目容量">
      <form v-if="capacityRow" class="ie-form" @submit.prevent="submitCapacity">
        <p class="ie-hint">{{ capacityRow.title }}</p>
        <div class="gb-kv"><span>当前已选</span><span>{{ capacityRow.selected }} 人</span></div>
        <label class="ie-fld"><span class="ie-lbl">新容量 <i>*</i></span>
          <input v-model.number="capacityForm.capacity" type="number" :min="capacityRow.selected || 1" max="99" class="ie-in" />
        </label>
        <p v-if="capacityError" class="ie-err">{{ capacityError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="capacityVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 补要求 -->
    <AppDrawer v-model:visible="reqVisible" title="维护题目要求">
      <form v-if="reqRow" class="ie-form" @submit.prevent="submitRequirements">
        <p class="ie-hint">{{ reqRow.title }}</p>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">题目要求 <i>*</i></span>
          <textarea v-model.trim="reqForm.requirements" class="ie-in" rows="4" placeholder="不少于10字，说明研究/开发目标与验收标准" />
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">预期成果</span>
          <textarea v-model.trim="reqForm.outcome" class="ie-in" rows="2" />
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">技能要求</span>
          <textarea v-model.trim="reqForm.skills" class="ie-in" rows="2" />
        </label>
        <p v-if="reqError" class="ie-err">{{ reqError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="reqVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 管附件 -->
    <AppDrawer v-model:visible="attVisible" title="题目附件管理">
      <div v-if="attRow">
        <p class="ie-hint">{{ attRow.title }} · 已挂 {{ attForm.attachments.length }} 个附件</p>
        <div v-for="(a, idx) in attForm.attachments" :key="idx" class="att-row">
          <input v-model.trim="a.name" class="ie-in" placeholder="附件名称" />
          <input v-model.trim="a.url" class="ie-in" placeholder="文件地址 / 存储路径" />
          <button type="button" class="mp-link" @click="removeAttachment(idx)">删除</button>
        </div>
        <button type="button" class="mp-btn" style="margin-top: var(--space-3)" @click="addAttachment">＋ 添加附件</button>
        <p v-if="attError" class="ie-err">{{ attError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="attVisible = false">取消</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submitAttachments">保存</button>
        </div>
      </div>
    </AppDrawer>

    <!-- 改分类 -->
    <AppDrawer v-model:visible="catVisible" title="调整题目分类">
      <form v-if="catRow" class="ie-form" @submit.prevent="submitCategory">
        <p class="ie-hint">{{ catRow.title }}</p>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">分类 <i>*</i></span>
          <select v-model="catForm.category" class="ie-in">
            <option value="">请选择</option>
            <option v-for="c in GD_TOPIC_CATEGORY" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <p v-if="catError" class="ie-err">{{ catError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="catVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 详情 -->
    <AppDrawer v-model:visible="detailVisible" :title="detail ? detail.title : '题目详情'">
      <template v-if="detail">
        <div class="gb-kv"><span>来源</span><span>{{ detail.sourceLabel }}</span></div>
        <div class="gb-kv"><span>分类</span><span>{{ detail.category || '未分类' }}</span></div>
        <div class="gb-kv"><span>指导教师</span><span>{{ detail.advisorName || '—' }}</span></div>
        <div class="gb-kv"><span>审核</span><span>{{ detail.reviewLabel }} / {{ detail.statusLabel }}</span></div>
        <div class="gb-kv"><span>容量</span><span>{{ detail.selected }}/{{ detail.capacity }}（余 {{ detail.remaining }}）</span></div>
        <div v-if="detail.requirements" class="gb-sec"><p class="ie-hint">题目要求</p><p>{{ detail.requirements }}</p></div>
        <div v-if="detail.outcome" class="gb-sec"><p class="ie-hint">预期成果</p><p>{{ detail.outcome }}</p></div>
        <div v-if="detail.attachments && detail.attachments.length" class="gb-sec">
          <p class="ie-hint">附件（{{ detail.attachments.length }}）</p>
          <ul class="gb-trail">
            <li v-for="(a, i) in detail.attachments" :key="i" class="gb-trail__item">
              <span>{{ a.name || '未命名' }}</span>
              <span class="gb-trail__meta">{{ a.url || '—' }}</span>
            </li>
          </ul>
        </div>
        <div class="gb-sec">
          <p class="ie-hint">已选学生（{{ assigned.length }}）</p>
          <EmptyState v-if="!assigned.length" title="暂无学生" />
          <ul v-else class="gb-trail">
            <li v-for="s in assigned" :key="s.id" class="gb-trail__item">
              <span>{{ s.name }}（{{ s.studentNo }}）</span>
              <span class="gb-trail__meta">{{ s.className || '—' }}</span>
            </li>
          </ul>
        </div>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel"
      :submitting="submitting"
      @confirm="onConfirm"
    />

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入题目库"
      template-name="题目库导入模板.xlsx"
      :required-fields="['题目名称']"
      :preview-fields="['title', 'batchNo', 'topicNo', 'sourceType', 'advisorName', 'capacity', 'submitReview']"
      :download-template-fn="() => gdTopicApi.downloadImportTemplate()"
      :upload-fn="(file) => gdTopicApi.uploadImportXlsx(file)"
      :confirm-fn="({ rows }) => gdTopicApi.importConfirm(rows)"
      :download-errors-fn="({ rows, errors }) => gdTopicApi.downloadImportErrors(rows, errors)"
      @imported="onImported"
    />
  </ModulePageShell>
</template>

<script>
/** 题目库（/admin/graduation/topic-lib）：申报/审核/分类/容量/要求/附件/历史/归档 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppExportButton } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'
import {
  GD_TOPIC_SOURCE, GD_TOPIC_REVIEW, GD_TOPIC_STATUS, GD_TOPIC_CATEGORY,
  GD_TOPIC_DIFFICULTY, IS_FULL, ARCHIVE_VIEW
} from '@/modules/graduation/constants/graduation-topic.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({
  keyword: '', batchId: '', sourceType: '', category: '', reviewStatus: '',
  status: '', isFull: '', archiveView: 'active',
  hasRequirements: '', hasAttachments: '', missingCategory: '',
  topicId: '', action: ''
})

const EMPTY_FORM = (sourceType = 'TEACHER') => ({
  title: '', batchId: '', topicNo: '', sourceType, advisorName: '', majorName: '',
  category: '', difficulty: '', enterpriseName: '', capacity: 1,
  requirements: '', outcome: '', skills: '', submitReview: false
})

const PANEL_PRESETS = {
  list: () => ({ ...EMPTY_FILTERS(), archiveView: 'active' }),
  'teacher-apply': () => ({ ...EMPTY_FILTERS(), sourceType: 'TEACHER', archiveView: 'active' }),
  enterprise: () => ({ ...EMPTY_FILTERS(), sourceType: 'ENTERPRISE', archiveView: 'active' }),
  'student-proposed': () => ({ ...EMPTY_FILTERS(), sourceType: 'STUDENT', archiveView: 'active' }),
  pending: () => ({ ...EMPTY_FILTERS(), reviewStatus: 'PENDING_REVIEW', archiveView: 'active' }),
  category: () => ({ ...EMPTY_FILTERS(), archiveView: 'active' }),
  capacity: () => ({ ...EMPTY_FILTERS(), archiveView: 'active', reviewStatus: 'APPROVED', status: 'CONFIRMED' }),
  requirements: () => ({ ...EMPTY_FILTERS(), archiveView: 'active', hasRequirements: 'false' }),
  attachments: () => ({ ...EMPTY_FILTERS(), archiveView: 'active', hasAttachments: 'false' }),
  history: () => ({ ...EMPTY_FILTERS(), keyword: '', topicId: '', action: '', archiveView: '' }),
  archive: () => ({ ...EMPTY_FILTERS(), archiveView: 'archived' })
}

const PANEL_HINTS = {
  list: '全部在库题目',
  'teacher-apply': '教师申报题目',
  enterprise: '企业合作题目',
  'student-proposed': '学生自拟题目',
  pending: '待审核题目',
  category: '按分类统计与维护',
  capacity: '在池题目容量与余量',
  requirements: '待补全题目要求',
  attachments: '待挂附件题目',
  history: '题目操作审计链',
  archive: '已归档题目'
}

const SOURCE_TONE = { TEACHER: 'info', ENTERPRISE: 'processing', STUDENT: 'warning', ADMIN: 'default' }

const BASE_COLUMNS = [
  { key: 'title', title: '题目' },
  { key: 'source', title: '来源' },
  { key: 'advisor', title: '指导教师' },
  { key: 'capacity', title: '容量' },
  { key: 'review', title: '审核' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', width: '280px' }
]

const HISTORY_COLUMNS = [
  { key: 'historyTime', title: '时间', width: '160px' },
  { key: 'historyAction', title: '操作' },
  { key: 'historyTopic', title: '题目' },
  { key: 'historyOperator', title: '操作人' },
  { key: 'historyDetail', title: '详情' },
  { key: 'actions', title: '操作', width: '100px' }
]

const HISTORY_ACTIONS = [
  { value: '', label: '全部' },
  { value: 'CREATE', label: '创建' },
  { value: 'SUBMIT_REVIEW', label: '提交审核' },
  { value: 'REVIEW', label: '审核' },
  { value: 'UPDATE', label: '编辑' },
  { value: 'UPDATE_ATTACHMENTS', label: '附件' },
  { value: 'DISABLE', label: '停用' },
  { value: 'ENABLE', label: '启用' },
  { value: 'ARCHIVE', label: '归档' }
]

export default {
  name: 'TopicLibListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog, AppExcelImportDrawer, AppExportButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      GD_TOPIC_CATEGORY, GD_TOPIC_DIFFICULTY,
      loading: true, error: '', submitting: false, activePanel: 'list',
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      batchOpts: [], categoryStats: [], libStats: null,
      editVisible: false, editing: null, form: EMPTY_FORM(), formError: '',
      capacityVisible: false, capacityRow: null, capacityForm: { capacity: 1 }, capacityError: '',
      reqVisible: false, reqRow: null, reqForm: { requirements: '', outcome: '', skills: '' }, reqError: '',
      attVisible: false, attRow: null, attForm: { attachments: [] }, attError: '',
      catVisible: false, catRow: null, catForm: { category: '' }, catError: '',
      detailVisible: false, detail: null, assigned: [],
      importVisible: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null, payload: null }
    }
  },
  computed: {
    isHistoryPanel() { return this.activePanel === 'history' },
    panelOnlyOps() { return ['category', 'capacity', 'requirements', 'attachments'].includes(this.activePanel) },
    columns() {
      if (this.isHistoryPanel) return HISTORY_COLUMNS
      if (this.activePanel === 'category') {
        return [
          { key: 'title', title: '题目' },
          { key: 'category', title: '分类' },
          { key: 'advisor', title: '指导教师' },
          { key: 'capacity', title: '容量' },
          { key: 'status', title: '状态' },
          { key: 'actions', title: '操作', width: '180px' }
        ]
      }
      if (this.activePanel === 'capacity') {
        return [
          { key: 'title', title: '题目' },
          { key: 'advisor', title: '指导教师' },
          { key: 'capacity', title: '容量/余量' },
          { key: 'status', title: '状态' },
          { key: 'actions', title: '操作', width: '140px' }
        ]
      }
      if (this.activePanel === 'requirements') {
        return [
          { key: 'title', title: '题目' },
          { key: 'requirements', title: '题目要求' },
          { key: 'advisor', title: '指导教师' },
          { key: 'review', title: '审核' },
          { key: 'actions', title: '操作', width: '140px' }
        ]
      }
      if (this.activePanel === 'attachments') {
        return [
          { key: 'title', title: '题目' },
          { key: 'attachments', title: '附件' },
          { key: 'advisor', title: '指导教师' },
          { key: 'status', title: '状态' },
          { key: 'actions', title: '操作', width: '140px' }
        ]
      }
      return BASE_COLUMNS
    },
    filterFields() {
      if (this.isHistoryPanel) {
        return [
          { key: 'keyword', label: '关键词', type: 'text', placeholder: '题目 / 操作 / 详情' },
          { key: 'topicId', label: '题目ID', type: 'text', placeholder: '精确题目ID' },
          { key: 'action', label: '操作类型', type: 'select', options: HISTORY_ACTIONS }
        ]
      }
      const batchOpts = this.batchOpts.map((b) => ({ value: b.id, label: b.batchName }))
      const catOpts = [{ value: '', label: '全部' }, ...GD_TOPIC_CATEGORY.map((c) => ({ value: c, label: c })), { value: '__uncat__', label: '未分类' }]
      const base = [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '题目 / 教师 / 企业' },
        { key: 'batchId', label: '批次', type: 'select', options: batchOpts }
      ]
      if (this.activePanel === 'category') {
        return [...base, { key: 'category', label: '分类', type: 'select', options: catOpts }]
      }
      if (this.activePanel === 'capacity') {
        return [
          ...base,
          { key: 'isFull', label: '满员', type: 'select', options: IS_FULL }
        ]
      }
      if (this.activePanel === 'requirements') {
        return [
          ...base,
          { key: 'hasRequirements', label: '要求状态', type: 'select', options: [
            { value: 'false', label: '待补全' }, { value: 'true', label: '已填写' }, { value: '', label: '全部' }
          ] }
        ]
      }
      if (this.activePanel === 'attachments') {
        return [
          ...base,
          { key: 'hasAttachments', label: '附件状态', type: 'select', options: [
            { value: 'false', label: '无附件' }, { value: 'true', label: '已有附件' }, { value: '', label: '全部' }
          ] }
        ]
      }
      if (this.activePanel === 'list') {
        return [
          ...base,
          { key: 'sourceType', label: '来源', type: 'select', options: GD_TOPIC_SOURCE },
          { key: 'reviewStatus', label: '审核', type: 'select', options: GD_TOPIC_REVIEW },
          { key: 'status', label: '状态', type: 'select', options: GD_TOPIC_STATUS },
          { key: 'isFull', label: '满员', type: 'select', options: IS_FULL }
        ]
      }
      if (this.activePanel === 'archive') {
        return [{ key: 'keyword', label: '关键词', type: 'text', placeholder: '题目名称' }]
      }
      return base
    },
    toolbarActions() {
      const createPanels = ['list', 'teacher-apply', 'enterprise', 'student-proposed']
      const base = []
      if (createPanels.includes(this.activePanel)) {
        const labels = { list: '＋ 申报题目', 'teacher-apply': '＋ 教师申报', enterprise: '＋ 企业题目', 'student-proposed': '＋ 学生自拟' }
        base.push({ key: 'create', label: labels[this.activePanel], variant: 'primary' })
      }
      if (['list', 'teacher-apply', 'enterprise', 'student-proposed', 'pending', 'archive', 'category', 'capacity', 'requirements', 'attachments', 'history'].includes(this.activePanel)) {
        if (this.activePanel !== 'history') {
          base.push({ key: 'import', label: '导入 Excel' })
        }
      }
      if (this.activePanel === 'category') {
        base.unshift({ key: 'refreshStats', label: '刷新统计' })
      }
      return base
    },
    exportVisible() {
      return ['list', 'teacher-apply', 'enterprise', 'student-proposed', 'pending', 'archive', 'category', 'capacity', 'requirements', 'attachments', 'history'].includes(this.activePanel)
    },
    pageSubtitle() {
      const gap = this.libStats && this.activePanel === 'requirements'
        ? ` · 待补 ${this.libStats.requirementsGap} 题`
        : this.libStats && this.activePanel === 'attachments'
          ? ` · 缺附件 ${this.libStats.attachmentsGap} 题`
          : ''
      return `共 ${this.total} 条 · ${PANEL_HINTS[this.activePanel] || ''}${gap}`
    },
    emptyTitle() {
      const m = {
        pending: '暂无待审核题目', archive: '暂无归档题目',
        requirements: '题目要求均已补全', attachments: '附件均已挂接', history: '暂无操作记录'
      }
      return m[this.activePanel] || '暂无题目'
    },
    emptyDesc() {
      if (['teacher-apply', 'enterprise', 'student-proposed', 'list'].includes(this.activePanel)) {
        return '点「申报」创建题目，保存后可提交审核'
      }
      if (this.activePanel === 'requirements') return '可在题目申报时填写要求，或通过导入 Excel 批量维护'
      if (this.activePanel === 'attachments') return '为题目挂接任务书、参考资料等附件元数据'
      if (this.activePanel === 'history') return '题目创建、审核、容量调整等操作均会留痕'
      return '可调整筛选条件'
    },
    applyTitle() {
      const m = { 'teacher-apply': '教师申报题目', enterprise: '企业题目申报', 'student-proposed': '学生自拟题目', list: '申报题目' }
      return m[this.activePanel] || '申报题目'
    },
    defaultSourceType() {
      const m = { 'teacher-apply': 'TEACHER', enterprise: 'ENTERPRISE', 'student-proposed': 'STUDENT' }
      return m[this.activePanel] || 'TEACHER'
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'list').toString())
      }
    }
  },
  created() {
    this.loadBatchOpts()
  },
  methods: {
    truncate(s, n) {
      if (!s) return ''
      return s.length <= n ? s : `${s.slice(0, n)}…`
    },
    sourceTone(t) { return SOURCE_TONE[t] || 'default' },
    canEdit(row) {
      return row.status !== 'ARCHIVED' && row.reviewStatus !== 'PENDING_REVIEW' && !(row.selected > 0 && row.reviewStatus === 'APPROVED')
    },
    applyPanel(panel) {
      const key = PANEL_PRESETS[panel] ? panel : 'list'
      this.activePanel = key
      this.filters = (PANEL_PRESETS[key] || PANEL_PRESETS.list)()
      this.page = 1
      this.loadPanelExtras()
      this.load()
    },
    async loadPanelExtras() {
      if (this.activePanel === 'category' || this.activePanel === 'capacity' || this.activePanel === 'requirements' || this.activePanel === 'attachments') {
        const s = await gdTopicApi.getStats()
        if (s.code === 0) {
          this.libStats = s.data
          this.categoryStats = s.data.categoryStats || []
        }
      } else {
        this.categoryStats = []
        this.libStats = null
      }
    },
    drillCategory(cat) {
      if (cat === '未分类') {
        this.filters.category = ''
        this.filters.missingCategory = 'true'
      } else {
        this.filters.category = cat
        this.filters.missingCategory = ''
      }
      this.page = 1
      this.load()
    },
    async loadBatchOpts() {
      const b = await gdTopicApi.getBatchOptions()
      if (b.code === 0) this.batchOpts = b.data
    },
    buildParams() {
      if (this.isHistoryPanel) {
        return {
          page: this.page, pageSize: this.pageSize,
          keyword: this.filters.keyword || undefined,
          topicId: this.filters.topicId || undefined,
          action: this.filters.action || undefined
        }
      }
      const p = { page: this.page, pageSize: this.pageSize, keyword: this.filters.keyword || undefined, batchId: this.filters.batchId || undefined }
      if (this.filters.sourceType) p.sourceType = this.filters.sourceType
      if (this.filters.category && this.filters.category !== '__uncat__') p.category = this.filters.category
      if (this.filters.category === '__uncat__' || this.filters.missingCategory === 'true') p.missingCategory = true
      if (this.filters.reviewStatus) p.reviewStatus = this.filters.reviewStatus
      if (this.filters.status) p.status = this.filters.status
      if (this.filters.isFull === 'true') p.isFull = true
      if (this.filters.isFull === 'false') p.isFull = false
      if (this.filters.archiveView) p.archiveView = this.filters.archiveView
      if (this.filters.hasRequirements === 'true') p.hasRequirements = true
      if (this.filters.hasRequirements === 'false') p.hasRequirements = false
      if (this.filters.hasAttachments === 'true') p.hasAttachments = true
      if (this.filters.hasAttachments === 'false') p.hasAttachments = false
      return p
    },
    async load() {
      this.loading = true
      this.error = ''
      const r = this.isHistoryPanel
        ? await gdTopicApi.getTopicHistory(this.buildParams())
        : await gdTopicApi.getTopics(this.buildParams())
      this.loading = false
      if (r.code !== 0) { this.error = r.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = r.data.list
      this.total = r.data.total
    },
    search() { this.page = 1; this.load() },
    reset() {
      this.filters = (PANEL_PRESETS[this.activePanel] || PANEL_PRESETS.list)()
      this.page = 1
      this.load()
    },
    turnPage({ page, pageSize }) { this.page = page; this.pageSize = pageSize; this.load() },
    onToolbar(key) {
      if (key === 'create') this.openCreate()
      if (key === 'import') { this.importVisible = true }
      if (key === 'refreshStats') this.loadPanelExtras()
    },
    openCreate() {
      this.editing = null
      this.form = EMPTY_FORM(this.defaultSourceType)
      this.formError = ''
      this.editVisible = true
    },
    openEdit(row) {
      this.editing = row
      this.form = {
        title: row.title, batchId: row.batchId || '', topicNo: row.topicNo || '',
        sourceType: row.sourceType, advisorName: row.advisorName || '', majorName: row.majorName || '',
        category: row.category || '', difficulty: row.difficulty || '', enterpriseName: row.enterpriseName || '',
        capacity: row.capacity, requirements: row.requirements || '', outcome: row.outcome || '',
        skills: row.skills || '', submitReview: false
      }
      this.formError = ''
      this.editVisible = true
    },
    openCapacity(row) {
      this.capacityRow = row
      this.capacityForm = { capacity: row.capacity }
      this.capacityError = ''
      this.capacityVisible = true
    },
    async submitCapacity() {
      const cap = Number(this.capacityForm.capacity)
      if (!cap || cap < (this.capacityRow.selected || 1)) {
        this.capacityError = `容量不能小于已选人数（${this.capacityRow.selected || 0}）`
        return
      }
      this.submitting = true
      const r = await gdTopicApi.updateCapacity(this.capacityRow.id, cap)
      this.submitting = false
      if (r.code !== 0) { this.capacityError = r.message; return }
      toast.success('容量已更新')
      this.capacityVisible = false
      this.loadPanelExtras()
      this.load()
    },
    openRequirements(row) {
      this.reqRow = row
      this.reqForm = { requirements: row.requirements || '', outcome: row.outcome || '', skills: row.skills || '' }
      this.reqError = ''
      this.reqVisible = true
    },
    async submitRequirements() {
      if (!this.reqForm.requirements || this.reqForm.requirements.length < 10) {
        this.reqError = '题目要求至少10字'
        return
      }
      this.submitting = true
      const r = await gdTopicApi.updateTopic(this.reqRow.id, {
        title: this.reqRow.title,
        requirements: this.reqForm.requirements,
        outcome: this.reqForm.outcome,
        skills: this.reqForm.skills
      })
      this.submitting = false
      if (r.code !== 0) { this.reqError = r.message; return }
      toast.success('要求已保存')
      this.reqVisible = false
      this.loadPanelExtras()
      this.load()
    },
    openAttachments(row) {
      this.attRow = row
      this.attForm = { attachments: (row.attachments || []).map((a) => ({ ...a })) }
      if (!this.attForm.attachments.length) this.addAttachment()
      this.attError = ''
      this.attVisible = true
    },
    addAttachment() {
      this.attForm.attachments.push({ name: '', url: '', size: 0, uploadedAt: new Date().toISOString() })
    },
    removeAttachment(idx) {
      this.attForm.attachments.splice(idx, 1)
    },
    async submitAttachments() {
      const valid = this.attForm.attachments.filter((a) => (a.name || '').trim() && (a.url || '').trim())
      if (!valid.length) { this.attError = '至少填写一个有效附件（名称+地址）'; return }
      this.submitting = true
      const r = await gdTopicApi.updateAttachments(this.attRow.id, valid)
      this.submitting = false
      if (r.code !== 0) { this.attError = r.message; return }
      toast.success('附件已保存')
      this.attVisible = false
      this.loadPanelExtras()
      this.load()
    },
    openCategoryEdit(row) {
      this.catRow = row
      this.catForm = { category: row.category || '' }
      this.catError = ''
      this.catVisible = true
    },
    async submitCategory() {
      if (!this.catForm.category) { this.catError = '请选择分类'; return }
      this.submitting = true
      const r = await gdTopicApi.updateTopic(this.catRow.id, { title: this.catRow.title, category: this.catForm.category })
      this.submitting = false
      if (r.code !== 0) { this.catError = r.message; return }
      toast.success('分类已更新')
      this.catVisible = false
      this.loadPanelExtras()
      this.load()
    },
    async submitForm() {
      if (!this.form.title || this.form.title.length < 2) { this.formError = '题目名称至少2字'; return }
      this.submitting = true
      this.formError = ''
      const body = { ...this.form, batchId: this.form.batchId || null }
      const r = this.editing
        ? await gdTopicApi.updateTopic(this.editing.id, body)
        : await gdTopicApi.createTopic(body)
      this.submitting = false
      if (r.code !== 0) { this.formError = r.message; return }
      toast.success(this.editing ? '已保存' : '已创建')
      this.editVisible = false
      this.loadPanelExtras()
      this.load()
    },
    async openDetail(row) {
      const d = await gdTopicApi.getTopicDetail(row.id)
      if (d.code !== 0) { toast.error(d.message); return }
      this.detail = d.data
      const a = await gdTopicApi.getAssignedStudents(row.id)
      this.assigned = a.code === 0 ? (a.data || []) : []
      this.detailVisible = true
    },
    async openDetailById(topicId) {
      const d = await gdTopicApi.getTopicDetail(topicId)
      if (d.code !== 0) { toast.error(d.message); return }
      this.detail = d.data
      const a = await gdTopicApi.getAssignedStudents(topicId)
      this.assigned = a.code === 0 ? (a.data || []) : []
      this.detailVisible = true
    },
    askSubmitReview(row) {
      this.confirm = { visible: true, title: '提交审核', message: `确认提交「${row.title}」进入审核？`, type: 'primary', confirmText: '提交', requireReason: false, action: 'submitReview', row }
    },
    askReview(row, action) {
      this.confirm = {
        visible: true, title: action === 'APPROVE' ? '审核通过' : '驳回题目',
        message: action === 'APPROVE' ? `通过后题目入池，可分配给学生。` : `驳回须填写原因（≥5字）。`,
        type: action === 'APPROVE' ? 'primary' : 'danger', confirmText: action === 'APPROVE' ? '通过' : '驳回',
        requireReason: action === 'REJECT', reasonLabel: '驳回原因', action: 'review', row, payload: { action }
      }
    },
    askDisable(row) {
      this.confirm = { visible: true, title: '停用题目', message: '停用后不可再分配新学生，已选学生不受影响。', type: 'warning', confirmText: '停用', requireReason: true, reasonLabel: '停用原因', action: 'disable', row }
    },
    askEnable(row) {
      this.confirm = { visible: true, title: '启用题目', message: `确认重新启用「${row.title}」？`, type: 'primary', confirmText: '启用', requireReason: false, action: 'enable', row }
    },
    askArchive(row) {
      this.confirm = { visible: true, title: '归档题目', message: '归档后题目移出在库列表。', type: 'warning', confirmText: '归档', requireReason: false, reasonLabel: '归档原因', action: 'archive', row }
    },
    async onConfirm({ reason }) {
      const row = this.confirm.row
      const action = this.confirm.action
      this.submitting = true
      let r = { code: 1 }
      if (action === 'submitReview') r = await gdTopicApi.submitReview(row.id)
      else if (action === 'review') r = await gdTopicApi.reviewTopic(row.id, { action: this.confirm.payload.action, comment: reason || '' })
      else if (action === 'disable') r = await gdTopicApi.disableTopic(row.id, { reason })
      else if (action === 'enable') r = await gdTopicApi.enableTopic(row.id)
      else if (action === 'archive') r = await gdTopicApi.archiveTopic(row.id, { reason: reason || '' })
      this.submitting = false
      if (r.code !== 0) { toast.error(r.message); return }
      toast.success('操作成功')
      this.confirm.visible = false
      this.loadPanelExtras()
      this.load()
    },
    onImported() {
      this.importVisible = false
      toast.success('题目导入完成')
      this.loadPanelExtras()
      this.load()
    },
    exportTopicsLibFn() {
      const p = this.buildParams()
      delete p.page
      delete p.pageSize
      return this.isHistoryPanel ? gdTopicApi.exportTopicHistory(p) : gdTopicApi.exportTopics(p)
    }
  }
}
</script>

<style scoped>
.gd-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.gb-kv { display: flex; justify-content: space-between; padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-subtle); }
.gb-sec { margin-top: var(--space-4); }
.gb-trail { list-style: none; padding: 0; margin: 0; }
.gb-trail__item { display: flex; justify-content: space-between; padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-subtle); }
.gb-trail__meta { color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.mp-stats { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
.mp-stat { flex: 1; min-width: 120px; padding: var(--space-3); background: var(--color-bg-subtle); border-radius: var(--radius-md); cursor: pointer; }
.mp-stat__val { font-size: var(--font-size-xl); font-weight: 600; }
.mp-stat__lbl { color: var(--color-text-secondary); font-size: var(--font-size-sm); margin-top: var(--space-1); }
.mp-stat__sub { color: var(--color-text-tertiary); font-size: var(--font-size-xs); margin-top: var(--space-1); }
.att-row { display: grid; grid-template-columns: 1fr 1fr auto; gap: var(--space-2); margin-bottom: var(--space-2); align-items: center; }
</style>
