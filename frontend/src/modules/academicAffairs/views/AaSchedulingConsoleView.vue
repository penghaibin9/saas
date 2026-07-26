<template>
  <ModulePageShell
    title="排课管理 · 规则与冲突"
    subtitle="先配置可排时间、每日负荷和教室约束，再试排、分析漏排并处理冲突"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aasg-tabs">
      <button v-for="item in tabs" :key="item.key" :class="['aasg-tab', { 'is-active': tab === item.key }]" @click="tab = item.key">
        {{ item.label }}
      </button>
    </div>

    <!-- V2-03 第一施工卡：排课规则中心 -->
    <div v-if="tab === 'rules'" class="mp-stack">
      <AppInlineAlert
        type="info"
        title="规则只影响自动排课"
        description="手工排课和导入结果不会被规则自动改写；批次级规则覆盖学期默认规则，已发布课表不允许再修改参数。"
      />

      <AppInlineAlert
        v-if="!canManageRules"
        type="warning"
        title="当前角色为只读查看"
        description="学院和任课教师可以查看学校排课口径，但只有教务处或学校管理员可以修改。"
      />
      <AppInlineAlert
        v-if="termArchived"
        type="warning"
        title="该学期已经归档"
        description="归档学期的排课规则已冻结，只能查看，不能新增、修改或删除。"
      />
      <AppInlineAlert
        v-if="slotLoadWarning"
        type="warning"
        title="作息节次读取失败"
        :description="slotLoadWarning"
      />

      <AppSectionCard title="规则范围">
        <div class="aasg-bar">
          <label class="aasg-field is-term">
            <span>学期</span>
            <AppTermEntityPicker v-model="termId" placeholder="请选择学期" @change="onTermChange" />
          </label>
          <div class="aasg-grow" />
          <AppButton
            v-if="canManageRules"
            variant="primary"
            size="small"
            :disabled="!canWriteRules || catalogLoading"
            @click="openRuleEditor"
          >
            新增规则
          </AppButton>
        </div>
        <div v-if="termInfo" class="aasg-term-facts">
          <span>{{ termInfo.termName || `${termInfo.yearCode || ''} 第${termInfo.termNo || '—'}学期` }}</span>
          <span>教学周 {{ termInfo.teachingWeeks || '未配置' }} 周</span>
          <StatusTag :type="termArchived ? 'warning' : 'success'" :label="termStatusLabel(termInfo.status)" dot />
        </div>
      </AppSectionCard>

      <AppSectionCard v-if="editorVisible" :title="editingRuleId ? '修改排课规则' : '新增排课规则'">
        <div class="aasg-editor">
          <label class="aasg-field">
            <span>业务参数</span>
            <select v-model="ruleForm.ruleKey" class="aasg-input" :disabled="saving || Boolean(editingRuleId)" @change="onRuleKeyChange">
              <option value="">请选择参数</option>
              <option v-for="meta in catalog" :key="meta.ruleKey" :value="meta.ruleKey">{{ meta.group }} · {{ meta.label }}</option>
            </select>
          </label>

          <label class="aasg-field">
            <span>生效范围</span>
            <select v-model="ruleForm.scopeType" class="aasg-input" :disabled="saving || Boolean(editingRuleId)" @change="onScopeChange">
              <option value="TERM">本学期默认</option>
              <option value="BATCH">指定课表批次</option>
            </select>
          </label>

          <label v-if="ruleForm.scopeType === 'BATCH'" class="aasg-field">
            <span>课表批次</span>
            <AppScheduleBatchPicker v-model="ruleForm.batchId" :disabled="saving || Boolean(editingRuleId)" />
          </label>

          <div v-if="selectedMeta" class="aasg-meta">
            <strong>{{ selectedMeta.label }}</strong>
            <span>{{ selectedMeta.description }}</span>
          </div>

          <div v-if="selectedMeta?.control === 'WEEK_RANGE'" class="aasg-control-grid is-two">
            <label class="aasg-field"><span>起始周</span><input v-model.number="ruleForm.value.startWeek" class="aasg-input" type="number" min="1" max="30" /></label>
            <label class="aasg-field"><span>结束周</span><input v-model.number="ruleForm.value.endWeek" class="aasg-input" type="number" min="1" :max="termInfo?.teachingWeeks || 30" /></label>
          </div>

          <div v-else-if="selectedMeta?.control === 'WEEKDAY_MULTI'" class="aasg-choice-panel">
            <div class="aasg-choice-title">选择允许自动排课的星期</div>
            <label v-for="day in weekdayOptions" :key="day.value" class="aasg-check">
              <input v-model="ruleForm.value" type="checkbox" :value="day.value" />{{ day.label }}
            </label>
          </div>

          <div v-else-if="selectedMeta?.control === 'SLOT_MULTI'" class="aasg-choice-panel">
            <div class="aasg-choice-title">选择允许自动排课的节次</div>
            <label v-for="slot in availableSlots" :key="slot.slotNo" class="aasg-check">
              <input v-model="ruleForm.value" type="checkbox" :value="slot.slotNo" />{{ slotLabel(slot) }}
            </label>
          </div>

          <div v-else-if="selectedMeta?.control === 'FORBIDDEN_GRID'" class="aasg-forbidden">
            <div class="aasg-choice-title">勾选全校统一禁排时段</div>
            <div v-for="day in weekdayOptions" :key="day.value" class="aasg-forbidden-row">
              <strong>{{ day.label }}</strong>
              <label class="aasg-check is-whole-day">
                <input type="checkbox" :checked="isForbidden(day.value, null)" @change="toggleForbidden(day.value, null)" />整天
              </label>
              <label v-for="slot in availableSlots" :key="`${day.value}-${slot.slotNo}`" class="aasg-check">
                <input
                  type="checkbox"
                  :disabled="isForbidden(day.value, null)"
                  :checked="isForbidden(day.value, slot.slotNo)"
                  @change="toggleForbidden(day.value, slot.slotNo)"
                />第{{ slot.slotNo }}节
              </label>
            </div>
          </div>

          <label v-else-if="selectedMeta?.control === 'INTEGER'" class="aasg-field is-number">
            <span>{{ selectedMeta.label }}</span>
            <div class="aasg-number-wrap">
              <input v-model.number="ruleForm.value" class="aasg-input" type="number" :min="selectedMeta.min" :max="selectedMeta.max" />
              <em>{{ selectedMeta.unit || '' }}</em>
            </div>
          </label>

          <div v-else-if="selectedMeta?.control === 'BOOLEAN'" class="aasg-choice-panel">
            <div class="aasg-choice-title">{{ selectedMeta.label }}</div>
            <label class="aasg-radio"><input v-model="ruleForm.value" type="radio" :value="true" />开启</label>
            <label class="aasg-radio"><input v-model="ruleForm.value" type="radio" :value="false" />关闭</label>
          </div>

          <label class="aasg-field">
            <span>备注</span>
            <textarea v-model.trim="ruleForm.remark" class="aasg-textarea" maxlength="500" placeholder="说明本校采用该参数的原因或使用边界（选填）" />
          </label>

          <AppInlineAlert v-if="formError" type="danger" title="无法保存" :description="formError" />
          <div class="aasg-editor-actions">
            <AppButton :disabled="saving" @click="closeRuleEditor">取消</AppButton>
            <AppButton variant="primary" :loading="saving" :disabled="!canWriteRules" @click="saveRule">保存规则</AppButton>
          </div>
        </div>
      </AppSectionCard>

      <ErrorState v-if="ruleError" :description="ruleError" @retry="loadRules" />
      <LoadingState v-else-if="ruleLoading || catalogLoading" />
      <template v-else>
        <EmptyState
          v-if="!rules.length"
          title="该学期尚未配置排课规则"
          description="系统会使用安全默认值运行自动排课；建议教务处结合本校教学周、作息节次和教师管理制度逐项确认。"
        />
        <DataTable v-else :columns="ruleColumns" :rows="rules" row-key="ruleId">
          <template #cell-rule="{ row }">
            <div class="mp-cell-main">{{ row.ruleLabel }}</div>
            <div class="mp-cell-sub">{{ row.ruleGroup }}</div>
          </template>
          <template #cell-scope="{ row }">
            <div class="mp-cell-main">{{ scopeLabel(row) }}</div>
            <div class="mp-cell-sub">{{ row.batchId ? `批次 ${row.batchId}` : '作为该学期默认参数' }}</div>
          </template>
          <template #cell-value="{ row }">
            <div :class="['mp-cell-main', { 'is-danger-text': row.invalidValue }]">{{ row.valueSummary || '未设置' }}</div>
            <div v-if="row.remark" class="mp-cell-sub">{{ row.remark }}</div>
            <div v-if="row.validationMessage" class="mp-cell-sub is-danger-text">{{ row.validationMessage }}</div>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="row.invalidValue ? 'danger' : 'success'" :label="row.invalidValue ? '配置异常' : '已启用'" dot />
          </template>
          <template #cell-ops="{ row }">
            <template v-if="canWriteRules">
              <button v-if="catalogByKey[row.ruleKey]" class="mp-link" @click="editRule(row)">修改</button>
              <button class="mp-link is-danger" @click="confirmDeleteRule(row)">删除</button>
            </template>
            <span v-else class="mp-cell-sub">只读</span>
          </template>
        </DataTable>
      </template>

      <AppSectionCard v-if="catalog.length" title="学校未配置时采用的安全默认值">
        <div class="aasg-default-grid">
          <div v-for="meta in catalog" :key="meta.ruleKey">
            <strong>{{ meta.label }}</strong>
            <span>{{ formatValue(meta, meta.defaultValue) }}</span>
          </div>
        </div>
      </AppSectionCard>
    </div>

    <!-- 教师可用时间：本轮保持既有流程 -->
    <div v-else-if="tab === 'availability'" class="mp-stack">
      <EmptyState v-if="!avails.length" title="暂无教师不可排时间提交" description="教师提交不可排课时段后在此采纳" />
      <DataTable v-else :columns="availColumns" :rows="avails" row-key="availabilityId">
        <template #cell-slot="{ row }">周{{ row.weekday }} 第{{ row.slotNo }}节</template>
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'ADOPTED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'primary'" :label="availabilityStatusLabel(row.status)" dot /></template>
        <template #cell-ops="{ row }">
          <button v-if="row.status === 'PENDING'" class="mp-link" @click="reviewAvail(row.availabilityId, 'ADOPT')">采纳</button>
          <button v-if="row.status === 'PENDING'" class="mp-link is-danger" @click="rejectAvail(row.availabilityId)">驳回</button>
        </template>
      </DataTable>
    </div>

    <!-- 自动排课：本轮不改算法 -->
    <div v-else-if="tab === 'auto'" class="mp-stack">
      <div class="aasg-bar">
        <AppScheduleBatchPicker v-model="autoBatchId" style="max-width:260px" />
        <AppButton variant="ghost" size="small" :loading="autoLoading" @click="runAuto(true)">试排预览</AppButton>
        <AppButton variant="primary" size="small" :loading="autoLoading" @click="doAuto">一键自动排课</AppButton>
        <AppButton variant="ghost" size="small" @click="doClearAuto">清除自动排课结果</AppButton>
      </div>
      <AppInlineAlert type="info" description="自动排课只处理已确认、已设周学时且未标记不排课的教学任务；手工排课不会被覆盖，排不下的任务会返回明确原因。" />
      <template v-if="autoResult">
        <div class="aasg-summary">
          <span class="is-ok">已排入 {{ autoResult.placedSessions }} 节 / {{ autoResult.placedTasks }} 个任务</span>
          <span :class="{ 'is-bad': autoResult.missedTasks }">漏排 {{ autoResult.missedTasks }} 个任务</span>
          <span>可用教室 {{ autoResult.roomPoolSize }} 间</span>
          <span v-if="autoResult.dryRun" class="is-warn">试排结果（未落库）</span>
        </div>
        <div v-if="autoMissSummary.length" class="aasg-section">
          <div class="aasg-section-title">漏排原因分布</div>
          <div class="aasg-reasons"><span v-for="item in autoMissSummary" :key="item.reason" class="aasg-reason-chip">{{ item.reasonLabel }} × {{ item.count }}</span></div>
        </div>
        <DataTable v-if="autoMisses.length" :columns="missColumns" :rows="autoMisses" row-key="taskId">
          <template #cell-course="{ row }">{{ row.courseName }}<span v-if="row.className" class="aasg-sub">（{{ row.className }}）</span></template>
          <template #cell-progress="{ row }">{{ row.placedSessions }} / {{ row.needSessions }} 节</template>
          <template #cell-reason="{ row }"><span class="aasg-tag is-hard">{{ row.reasonLabel }}</span></template>
          <template #cell-detail="{ row }"><span class="aasg-advice">{{ row.detail }}</span></template>
        </DataTable>
        <EmptyState v-else-if="!autoResult.missedTasks" title="全部排课成功" description="所有待排任务均已排入，无漏排" />
      </template>
      <EmptyState v-else title="尚未执行自动排课" description="选择课表批次后先试排预览，确认结果再正式落库" />
    </div>

    <!-- 冲突报告：本轮保持既有能力 -->
    <div v-else class="mp-stack">
      <div class="aasg-bar">
        <AppScheduleBatchPicker v-model="conflictBatchId" style="max-width:260px" />
        <AppButton variant="primary" size="small" @click="loadConflict">生成冲突报告</AppButton>
      </div>
      <template v-if="conflict">
        <div class="aasg-summary">
          <span :class="{ 'is-bad': conflict.hardCount }">HARD 物理冲突 {{ conflict.hardCount }}</span>
          <span :class="{ 'is-warn': conflict.softCount }">SOFT 软冲突 {{ conflict.softCount }}</span>
          <span :class="conflict.canPrePublish ? 'is-ok' : 'is-bad'">{{ conflict.canPrePublish ? '可预发布' : '存在HARD冲突，禁止预发布' }}</span>
        </div>
        <div v-if="conflict.hardConflicts.length" class="aasg-section">
          <div class="aasg-section-title">HARD 冲突（必须清零）</div>
          <ul class="aasg-conflicts">
            <li v-for="(item, index) in conflict.hardConflicts" :key="`hard-${index}`">
              <span class="aasg-tag is-hard">{{ dimLabel(item.dimension) }}</span>
              周{{ item.weekday }}第{{ item.slotNo }}节：{{ item.itemA.courseName }}（{{ item.itemA.className }}） ⨯ {{ item.itemB.courseName }}（{{ item.itemB.className }}）
            </li>
          </ul>
        </div>
        <div v-if="conflict.softConflicts.length" class="aasg-section">
          <div class="aasg-section-title">SOFT 冲突（教师不可排时间）</div>
          <ul class="aasg-conflicts">
            <li v-for="(item, index) in conflict.softConflicts" :key="`soft-${index}`">
              <span class="aasg-tag is-soft">{{ item.item.teacherName }}</span>
              周{{ item.weekday }}第{{ item.slotNo }}节：{{ item.item.courseName }}（教师已登记不可排）
            </li>
          </ul>
        </div>
        <EmptyState v-if="!conflict.hardCount && !conflict.softCount" title="无冲突" description="该批次课表无 HARD/SOFT 冲突，可预发布" />
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      :title="confirmTitle"
      :message="confirmMessage"
      :require-reason="confirmRequireReason"
      :reason-label="confirmReasonLabel"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppConfirmDialog, AppTermEntityPicker, AppScheduleBatchPicker, AppSectionCard } from '@/components/common'
import { academicAffairsApi, academicAffairsSchedulingApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const MANAGE_ROLES = new Set(['PLATFORM_SUPER_ADMIN', 'SCHOOL_ADMIN', 'ACADEMIC_ADMIN'])
const DEFAULT_DAYS = [
  { value: 1, label: '周一' }, { value: 2, label: '周二' }, { value: 3, label: '周三' },
  { value: 4, label: '周四' }, { value: 5, label: '周五' }, { value: 6, label: '周六' },
  { value: 7, label: '周日' }
]

export default {
  name: 'AaSchedulingConsoleView',
  components: { ModulePageShell, DataTable, StatusTag, EmptyState, LoadingState, ErrorState, AppButton, AppInlineAlert, AppConfirmDialog, AppTermEntityPicker, AppScheduleBatchPicker, AppSectionCard },
  data() {
    return {
      ctx: { currentRole: { roleName: '', roleCode: '' }, dataScope: { scopeName: '' } },
      tab: 'rules',
      tabs: [{ key: 'rules', label: '排课规则' }, { key: 'availability', label: '教师不可排时间' }, { key: 'auto', label: '自动排课' }, { key: 'conflict', label: '冲突报告' }],
      termId: '', termInfo: null,
      rules: [], catalog: [], timeSlots: [],
      ruleLoading: false, catalogLoading: false, ruleError: '', slotLoadWarning: '',
      editorVisible: false, editingRuleId: '', saving: false, formError: '',
      ruleForm: { ruleKey: '', scopeType: 'TERM', batchId: '', value: null, remark: '' },
      avails: [], conflictBatchId: '', conflict: null,
      autoBatchId: '', autoResult: null, autoLoading: false,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      confirmRequireReason: false, confirmReasonLabel: '',
      ruleColumns: [
        { key: 'rule', title: '业务参数' }, { key: 'scope', title: '生效范围', width: '190px' },
        { key: 'value', title: '当前配置' }, { key: 'status', title: '状态', width: '110px' },
        { key: 'ops', title: '操作', width: '130px' }
      ],
      missColumns: [{ key: 'course', title: '课程' }, { key: 'teacherName', title: '教师' }, { key: 'progress', title: '已排/需排' }, { key: 'reason', title: '漏排原因' }, { key: 'detail', title: '处置建议' }],
      availColumns: [{ key: 'teacherName', title: '教师' }, { key: 'slot', title: '时段' }, { key: 'reason', title: '原因' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }]
    }
  },
  computed: {
    canManageRules() { return MANAGE_ROLES.has(String(this.ctx.currentRole.roleCode || '').toUpperCase()) },
    termArchived() { return String(this.termInfo?.status || '').toUpperCase() === 'ARCHIVED' },
    canWriteRules() { return Boolean(this.canManageRules && this.termId && !this.termArchived) },
    catalogByKey() { return Object.fromEntries(this.catalog.map(item => [item.ruleKey, item])) },
    selectedMeta() { return this.catalogByKey[this.ruleForm.ruleKey] || null },
    weekdayOptions() { return this.selectedMeta?.options?.length ? this.selectedMeta.options : DEFAULT_DAYS },
    availableSlots() {
      if (this.timeSlots.length) return this.timeSlots
      return Array.from({ length: 8 }, (_, index) => ({ slotNo: index + 1, slotName: `第${index + 1}节` }))
    },
    autoMisses() { return this.autoResult?.misses || [] },
    autoMissSummary() {
      const rows = this.autoResult?.misses || []
      const grouped = {}
      rows.forEach((row) => {
        grouped[row.reason] = grouped[row.reason] || { reason: row.reason, reasonLabel: row.reasonLabel, count: 0 }
        grouped[row.reason].count += 1
      })
      return Object.values(grouped).sort((a, b) => b.count - a.count)
    }
  },
  watch: {
    tab(value) { if (value === 'availability') this.loadAvails() }
  },
  async created() {
    const queryTab = this.$route?.query?.tab
    if (queryTab && this.tabs.some(item => item.key === queryTab)) this.tab = queryTab
    await this.loadContext()
    await Promise.all([this.loadCatalog(), this.loadTimeSlots()])
    const current = await academicAffairsApi.getCurrentTerm()
    if (current.code === 0 && current.data?.termId) this.termId = String(current.data.termId)
    await this.onTermChange()
  },
  methods: {
    async loadContext() {
      const response = await academicAffairsApi.getContext()
      if (response.code === 0) this.ctx = response.data
    },
    async loadCatalog() {
      this.catalogLoading = true
      const response = await api.ruleCatalog()
      this.catalogLoading = false
      if (response.code === 0) this.catalog = response.data.items || []
      else this.ruleError = response.message || '排课规则目录加载失败'
    },
    async loadTimeSlots() {
      const response = await academicAffairsApi.getTimeSlots(false)
      if (response.code === 0) {
        this.timeSlots = (response.data || []).map(row => ({
          slotNo: Number(row.slotNo), slotName: row.slotName || `第${row.slotNo}节`,
          startTime: row.startTime || '', endTime: row.endTime || ''
        })).filter(row => Number.isInteger(row.slotNo) && row.slotNo > 0)
      } else {
        this.slotLoadWarning = '暂时无法读取学校作息，将显示第1—8节作为只读兜底；保存时后端仍会按真实启用节次校验。'
      }
    },
    async onTermChange() {
      this.closeRuleEditor()
      this.termInfo = null
      if (!this.termId) { this.rules = []; this.ruleError = '请选择学期后查看排课规则'; return }
      const detail = await academicAffairsApi.getTermDetail(this.termId)
      if (detail.code === 0) this.termInfo = detail.data
      else this.ruleError = detail.message || '学期状态加载失败'
      await this.loadRules()
    },
    async loadRules() {
      if (!this.termId || this.ruleLoading) return
      this.ruleLoading = true; this.ruleError = ''
      const response = await api.listRules({ termId: this.termId })
      this.ruleLoading = false
      if (response.code === 0) this.rules = response.data.items || []
      else { this.rules = []; this.ruleError = response.message || '排课规则加载失败' }
    },
    openRuleEditor() {
      if (!this.canWriteRules) return
      this.editingRuleId = ''
      this.ruleForm = { ruleKey: '', scopeType: 'TERM', batchId: '', value: null, remark: '' }
      this.formError = ''; this.editorVisible = true
    },
    closeRuleEditor() {
      this.editorVisible = false; this.editingRuleId = ''; this.formError = ''
    },
    onRuleKeyChange() {
      const meta = this.selectedMeta
      this.ruleForm.value = meta ? structuredClone(meta.defaultValue) : null
      this.formError = ''
    },
    onScopeChange() {
      if (this.ruleForm.scopeType !== 'BATCH') this.ruleForm.batchId = ''
      this.formError = ''
    },
    editRule(row) {
      if (!this.canWriteRules || !this.catalogByKey[row.ruleKey]) return
      this.editingRuleId = row.ruleId
      this.ruleForm = {
        ruleKey: row.ruleKey,
        scopeType: row.batchId ? 'BATCH' : 'TERM',
        batchId: row.batchId || '',
        value: structuredClone(row.ruleValue ?? this.catalogByKey[row.ruleKey].defaultValue),
        remark: row.remark || ''
      }
      this.formError = ''; this.editorVisible = true
      this.$nextTick(() => document.querySelector('.aasg-editor')?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
    },
    localRuleError() {
      const meta = this.selectedMeta
      if (!this.termId) return '请选择规则所属学期'
      if (!meta) return '请选择业务参数'
      if (this.ruleForm.scopeType === 'BATCH' && !this.ruleForm.batchId) return '请选择课表批次'
      const value = this.ruleForm.value
      if (meta.control === 'WEEK_RANGE') {
        const start = Number(value?.startWeek); const end = Number(value?.endWeek)
        if (!Number.isInteger(start) || !Number.isInteger(end) || start < 1 || end < 1) return '起始周和结束周必须是正整数'
        if (start > end) return '起始周不能晚于结束周'
        if (this.termInfo?.teachingWeeks && end > Number(this.termInfo.teachingWeeks)) return `结束周不能超过该学期教学周数 ${this.termInfo.teachingWeeks}`
      }
      if (['WEEKDAY_MULTI', 'SLOT_MULTI'].includes(meta.control) && (!Array.isArray(value) || !value.length)) return `${meta.label}至少选择一项`
      if (meta.control === 'INTEGER') {
        const number = Number(value)
        if (!Number.isInteger(number) || number < meta.min || number > meta.max) return `${meta.label}必须在 ${meta.min}—${meta.max} 之间`
      }
      if (meta.control === 'BOOLEAN' && typeof value !== 'boolean') return `${meta.label}必须选择开启或关闭`
      return ''
    },
    async saveRule() {
      if (this.saving || !this.canWriteRules) return
      const error = this.localRuleError()
      if (error) { this.formError = error; return }
      this.saving = true; this.formError = ''
      const response = await api.saveRule({
        ruleKey: this.ruleForm.ruleKey,
        termId: this.termId,
        batchId: this.ruleForm.scopeType === 'BATCH' ? this.ruleForm.batchId : undefined,
        ruleValue: structuredClone(this.ruleForm.value),
        remark: this.ruleForm.remark || undefined
      })
      this.saving = false
      if (response.code === 0) {
        toast.success(`${response.data.ruleLabel || '排课规则'}已保存`)
        this.closeRuleEditor(); await this.loadRules()
      } else this.formError = response.message || '保存排课规则失败'
    },
    confirmDeleteRule(row) {
      this.confirmRequireReason = false
      this.confirmTitle = `删除“${row.ruleLabel}”`
      this.confirmMessage = '删除后自动排课将恢复该参数的安全默认值。历史审计记录仍会保留。'
      this.pendingAction = async () => {
        const response = await api.deleteRule(row.ruleId)
        if (response.code === 0) { toast.success('规则已删除'); await this.loadRules() }
        else toast.error(response.message || '删除规则失败')
      }
      this.confirmVisible = true
    },
    isForbidden(weekday, slotNo) {
      return Array.isArray(this.ruleForm.value) && this.ruleForm.value.some(row => Number(row.weekday) === Number(weekday) && (row.slotNo == null ? slotNo == null : Number(row.slotNo) === Number(slotNo)))
    },
    toggleForbidden(weekday, slotNo) {
      const rows = Array.isArray(this.ruleForm.value) ? [...this.ruleForm.value] : []
      if (slotNo == null) {
        const active = this.isForbidden(weekday, null)
        this.ruleForm.value = active ? rows.filter(row => Number(row.weekday) !== Number(weekday)) : [...rows.filter(row => Number(row.weekday) !== Number(weekday)), { weekday }]
        return
      }
      const signature = row => Number(row.weekday) === Number(weekday) && Number(row.slotNo) === Number(slotNo)
      const active = rows.some(signature)
      this.ruleForm.value = active
        ? rows.filter(row => !signature(row))
        : [...rows.filter(row => !(Number(row.weekday) === Number(weekday) && row.slotNo == null)), { weekday, slotNo }]
    },
    scopeLabel(row) { return row.batchId ? '指定课表批次' : '本学期默认' },
    termStatusLabel(status) { return ({ DRAFT: '编制中', PUBLISHED: '已发布', FROZEN: '已冻结', ARCHIVED: '已归档' })[status] || status || '未知状态' },
    availabilityStatusLabel(status) { return ({ PENDING: '待处理', ADOPTED: '已采纳', REJECTED: '已驳回' })[status] || status || '—' },
    slotLabel(slot) { return `${slot.slotName || `第${slot.slotNo}节`}${slot.startTime ? ` · ${slot.startTime}-${slot.endTime || ''}` : ''}` },
    formatValue(meta, value) {
      if (meta.control === 'WEEK_RANGE') return `第${value.startWeek}—${value.endWeek}周`
      if (meta.control === 'WEEKDAY_MULTI') return value.map(number => DEFAULT_DAYS.find(day => day.value === number)?.label || number).join('、')
      if (meta.control === 'SLOT_MULTI') return value.map(number => `第${number}节`).join('、')
      if (meta.control === 'FORBIDDEN_GRID') return value.length ? `${value.length}个禁排设置` : '不设统一禁排'
      if (meta.control === 'INTEGER') return `${value}${meta.unit || ''}`
      if (meta.control === 'BOOLEAN') return value ? '开启' : '关闭'
      return '—'
    },
    dimLabel(value) { return ({ TEACHER: '教师冲突', CLASS: '班级冲突', CLASSROOM: '教室冲突' })[value] || value },
    async loadAvails() {
      const response = await api.listAvailability({ termId: this.termId || undefined })
      this.avails = response.code === 0 ? (response.data.items || []) : []
      if (response.code !== 0) toast.error(response.message || '教师不可排时间加载失败')
    },
    async reviewAvail(id, action) {
      const response = await api.reviewAvailability(id, action)
      if (response.code === 0) { toast.success('已采纳'); await this.loadAvails() }
      else toast.error(response.message || '处理失败')
    },
    rejectAvail(id) {
      this.confirmRequireReason = true; this.confirmReasonLabel = '驳回原因（≥5字）'
      this.confirmTitle = '驳回教师不可排时间'; this.confirmMessage = '原因将写入处理记录并供申请教师查看。'
      this.pendingAction = async (reason) => {
        const response = await api.reviewAvailability(id, 'REJECT', String(reason || '').trim())
        if (response.code === 0) { toast.success('已驳回'); await this.loadAvails() }
        else toast.error(response.message || '驳回失败')
      }
      this.confirmVisible = true
    },
    async loadConflict() {
      if (!this.conflictBatchId) { toast.error('请选择课表批次'); return }
      const response = await api.conflictReport(this.conflictBatchId)
      if (response.code === 0) this.conflict = response.data
      else toast.error(response.message || '冲突报告生成失败')
    },
    async runAuto(dryRun) {
      if (!this.autoBatchId) { toast.error('请选择课表批次'); return }
      this.autoLoading = true
      const response = await api.autoSchedule(this.autoBatchId, dryRun)
      this.autoLoading = false
      if (response.code === 0) { this.autoResult = response.data; toast.success(dryRun ? '试排完成（未落库）' : `已排入 ${response.data.placedSessions} 节`) }
      else toast.error(response.message || '自动排课失败')
    },
    doAuto() {
      if (!this.autoBatchId) { toast.error('请选择课表批次'); return }
      this.confirmRequireReason = false; this.confirmTitle = '执行自动排课'
      this.confirmMessage = '仅新增自动排课结果，手工和导入课位不会被覆盖。'
      this.pendingAction = () => this.runAuto(false); this.confirmVisible = true
    },
    doClearAuto() {
      if (!this.autoBatchId) { toast.error('请选择课表批次'); return }
      this.confirmRequireReason = false; this.confirmTitle = '清除自动排课结果'
      this.confirmMessage = '只清除该批次由系统自动生成的课位，手工和导入课位继续保留。'
      this.pendingAction = async () => {
        const response = await api.clearAuto(this.autoBatchId)
        if (response.code === 0) { toast.success(`已清除 ${response.data.cleared} 节`); this.autoResult = null }
        else toast.error(response.message || '清除失败')
      }
      this.confirmVisible = true
    },
    async onConfirm(payload = {}) {
      const action = this.pendingAction
      this.pendingAction = null; this.confirmVisible = false; this.confirmRequireReason = false
      if (action) await action(payload.reason || '')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aasg-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; }
.aasg-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aasg-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aasg-bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: end; }
.aasg-grow { flex: 1; }.aasg-field { display: flex; flex-direction: column; gap: 6px; min-width: 220px; color: var(--text-700, #4e5969); font-size: 13px; }
.aasg-field.is-term { width: 280px; }.aasg-input { min-height: 36px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); }
.aasg-textarea { min-height: 78px; padding: 9px 10px; resize: vertical; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; font: inherit; }
.aasg-term-facts { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; margin-top: 12px; color: var(--text-600, #475569); font-size: 13px; }
.aasg-editor { display: flex; flex-direction: column; gap: 15px; }.aasg-meta { display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; border-radius: 8px; background: var(--fill-light, #f8fafc); }
.aasg-meta span { color: var(--text-secondary, #64748b); font-size: 13px; }.aasg-control-grid { display: grid; gap: 12px; }.aasg-control-grid.is-two { grid-template-columns: repeat(2, minmax(0, 220px)); }
.aasg-choice-panel, .aasg-forbidden { padding: 13px 14px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; }.aasg-choice-title { margin-bottom: 10px; font-weight: 600; }
.aasg-check, .aasg-radio { display: inline-flex; align-items: center; gap: 5px; margin: 3px 14px 3px 0; font-size: 13px; }.aasg-forbidden-row { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; padding: 8px 0; border-top: 1px solid var(--border-100, #f1f5f9); }
.aasg-forbidden-row:first-of-type { border-top: 0; }.aasg-forbidden-row strong { width: 48px; }.aasg-check.is-whole-day { padding-right: 10px; border-right: 1px solid var(--border-200, #e5e7eb); }
.aasg-number-wrap { display: flex; align-items: center; gap: 8px; }.aasg-number-wrap .aasg-input { width: 140px; }.aasg-number-wrap em { font-style: normal; color: var(--text-secondary, #64748b); }
.aasg-editor-actions { display: flex; justify-content: flex-end; gap: 8px; }.aasg-default-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.aasg-default-grid > div { padding: 12px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 7px; }.aasg-default-grid strong, .aasg-default-grid span { display: block; }.aasg-default-grid span { margin-top: 5px; color: var(--text-secondary, #64748b); font-size: 12px; }
.is-danger-text { color: var(--danger-color, #dc2626); }.aasg-summary { display: flex; flex-wrap: wrap; gap: 16px; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.aasg-summary .is-bad { color: var(--danger-color, #dc2626); font-weight: 600; }.aasg-summary .is-warn { color: var(--warning-color, #d97706); font-weight: 600; }.aasg-summary .is-ok { color: var(--success-color, #16a34a); font-weight: 600; }
.aasg-section-title { font-weight: 500; margin: 12px 0 8px; }.aasg-conflicts { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }.aasg-conflicts li { padding: 8px 12px; background: var(--fill-light, #f8fafc); border-radius: 6px; font-size: 13px; }
.aasg-tag { display: inline-block; padding: 1px 8px; border-radius: 4px; margin-right: 8px; font-size: 12px; }.aasg-tag.is-hard { background: #fee2e2; color: #dc2626; }.aasg-tag.is-soft { background: #fef3c7; color: #d97706; }
.aasg-reasons { display: flex; flex-wrap: wrap; gap: 8px; }.aasg-reason-chip { padding: 3px 10px; border-radius: 12px; background: #fef3c7; color: #b45309; font-size: 12px; }.aasg-advice, .aasg-sub { color: var(--text-secondary, #64748b); font-size: 12px; }
@media (max-width: 900px) { .aasg-default-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.aasg-control-grid.is-two { grid-template-columns: 1fr; } }
@media (max-width: 620px) { .aasg-default-grid { grid-template-columns: 1fr; }.aasg-field, .aasg-field.is-term { width: 100%; min-width: 0; } }
</style>
