<template>
  <ModulePageShell
    title="排课管理 · 规则与冲突"
    :subtitle="'排课规则/约束 · 教师可用时间采纳 · 冲突报告 · 教室可用时间 · 自动排课预留 · 排课结果 · 排课调整'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aasg-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aasg-tab', { 'is-active': tab === t.key }]" @click="tab = t.key">{{ t.label }}</button>
    </div>

    <!-- 排课规则 -->
    <div v-if="tab === 'rules'" class="mp-stack">
      <div class="aasg-bar">
        <AppTextInput v-model="termId" placeholder="学期 ID（可空=全部）" style="max-width:200px" @change="loadRules" />
        <AppButton variant="primary" size="small" @click="openRule">新增规则</AppButton>
      </div>
      <EmptyState v-if="!generalRules.length" title="暂无排课规则" description="配置教师可用时间要求/教室类型/周学时约束" />
      <DataTable v-else :columns="ruleColumns" :rows="generalRules" row-key="ruleId">
        <template #cell-value="{ row }">{{ row.ruleValue ? JSON.stringify(row.ruleValue) : '—' }}</template>
        <template #cell-ops="{ row }"><button class="mp-link is-danger" @click="delRule(row.ruleId)">删除</button></template>
      </DataTable>
    </div>

    <!-- 教师可用时间 -->
    <div v-else-if="tab === 'availability'" class="mp-stack">
      <EmptyState v-if="!avails.length" title="暂无教师可用时间提交" description="教师提交不可排课时段后在此采纳" />
      <DataTable v-else :columns="availColumns" :rows="avails" row-key="availabilityId">
        <template #cell-slot="{ row }">周{{ row.weekday }} 第{{ row.slotNo }}节</template>
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'ADOPTED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'primary'" :label="row.status" dot /></template>
        <template #cell-ops="{ row }">
          <button v-if="row.status === 'PENDING'" class="mp-link" @click="reviewAvail(row.availabilityId, 'ADOPT')">采纳</button>
          <button v-if="row.status === 'PENDING'" class="mp-link is-danger" @click="rejectAvail(row.availabilityId)">驳回</button>
        </template>
      </DataTable>
    </div>

    <!-- 冲突报告 -->
    <div v-else-if="tab === 'conflict'" class="mp-stack">
      <div class="aasg-bar">
        <AppTextInput v-model="conflictBatchId" placeholder="课表批次 ID" style="max-width:200px" />
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
            <li v-for="(h, i) in conflict.hardConflicts" :key="'h' + i">
              <span class="aasg-tag is-hard">{{ dimLabel(h.dimension) }}</span>
              周{{ h.weekday }}第{{ h.slotNo }}节：{{ h.itemA.courseName }}（{{ h.itemA.className }}） ⨯ {{ h.itemB.courseName }}（{{ h.itemB.className }}）
            </li>
          </ul>
        </div>
        <div v-if="conflict.softConflicts.length" class="aasg-section">
          <div class="aasg-section-title">SOFT 冲突（撞教师不可排课时段，可备注放行）</div>
          <ul class="aasg-conflicts">
            <li v-for="(s, i) in conflict.softConflicts" :key="'s' + i">
              <span class="aasg-tag is-soft">{{ s.item.teacherName }}</span>
              周{{ s.weekday }}第{{ s.slotNo }}节：{{ s.item.courseName }}（教师已登记不可排）
            </li>
          </ul>
        </div>
        <EmptyState v-if="!conflict.hardCount && !conflict.softCount" title="无冲突" description="该批次课表无 HARD/SOFT 冲突，可预发布" />
      </template>
    </div>

    <!-- 排课约束（03号卡：复用排课规则中心，ruleKey 限定为约束类枚举） -->
    <div v-else-if="tab === 'constraint'" class="mp-stack">
      <p class="mp-note">约束是排课规则的明细子集：教师每日上限节数 / 同课程间隔最小天数 / 体育课后N节禁排文化课，与「排课规则」共用同一后端存储，仅分类展示。</p>
      <div class="aasg-bar">
        <AppTextInput v-model="termId" placeholder="学期 ID（可空=全部）" style="max-width:200px" @change="loadRules" />
        <AppButton variant="primary" size="small" @click="openConstraint">新增约束</AppButton>
      </div>
      <EmptyState v-if="!constraintRules.length" title="暂无排课约束" description="点击「新增约束」配置硬性/软性排课限制" />
      <DataTable v-else :columns="ruleColumns" :rows="constraintRules" row-key="ruleId">
        <template #cell-value="{ row }">{{ constraintLabel(row.ruleKey) }}：{{ row.ruleValue ? JSON.stringify(row.ruleValue) : '—' }}</template>
        <template #cell-ops="{ row }"><button class="mp-link is-danger" @click="delRule(row.ruleId)">删除</button></template>
      </DataTable>
    </div>

    <!-- 教室可用时间（05号卡） -->
    <div v-else-if="tab === 'room'" class="mp-stack">
      <div class="aasg-bar">
        <AppTextInput v-model="roomBatchId" placeholder="课表批次 ID" style="max-width:160px" />
        <AppTextInput v-model="roomClassroom" placeholder="教室名称，如 A101" style="max-width:200px" @keyup.enter="loadRoomView" />
        <AppButton variant="primary" size="small" @click="loadRoomView">查询教室占用</AppButton>
      </div>
      <EmptyState v-if="!roomItems.length" :title="roomNote || '请输入批次ID与教室名称查询'" description="辅助人工排课选教室，减少反复试错触发冲突" />
      <AppSectionCard v-else :title="`教室 ${roomClassroom} 占用情况`">
        <AaScheduleGrid :items="roomItems" :slots="slots" :editable="false" />
      </AppSectionCard>
    </div>

    <!-- 自动排课预留（07号卡：结果导入通道，不写算法本体） -->
    <div v-else-if="tab === 'import'" class="mp-stack">
      <p class="mp-note">本轮不实现自动排课算法，仅提供「结果导入通道」：第三方顾问/算法排好的课表通过 Excel 批量导入本系统。</p>
      <div class="aasg-bar">
        <AppTextInput v-model="importBatchId" placeholder="课表批次 ID（状态需=DRAFT/PRE_PUBLISHED）" style="max-width:280px" />
        <AppButton size="small" @click="downloadTemplate">下载导入模板</AppButton>
        <input ref="importFile" type="file" accept=".xlsx" class="aasg-file" @change="onFilePicked" />
        <AppButton variant="primary" size="small" :disabled="!importBatchId || !pickedFile || importing" @click="doImportXlsx">
          {{ importing ? '导入中…' : '上传导入' }}
        </AppButton>
        <span class="aasg-disabled-btn" title="暂未开通，如需自动排课请联系供应商">自动排课（暂未开通）</span>
      </div>
      <div v-if="importResult" class="aasg-section">
        <div class="aasg-section-title">导入结果：成功 {{ importResult.imported }} 条，冲突 {{ (importResult.conflicts || []).length }} 条</div>
        <ul v-if="importResult.conflicts && importResult.conflicts.length" class="aasg-conflicts">
          <li v-for="c in importResult.conflicts" :key="c.row">第 {{ c.row }} 行：{{ c.detail }}</li>
        </ul>
      </div>
    </div>

    <!-- 排课结果（10号卡：预发布前汇总核对） -->
    <div v-else-if="tab === 'result'" class="mp-stack">
      <div class="aasg-bar">
        <AppTextInput v-model="resultBatchId" placeholder="课表批次 ID" style="max-width:200px" @keyup.enter="loadSummary" />
        <AppButton variant="primary" size="small" @click="loadSummary">查询汇总</AppButton>
      </div>
      <template v-if="summary">
        <div class="aasg-metrics">
          <div class="aasg-metric"><span class="aasg-metric__label">已排/应排任务</span><span class="aasg-metric__value">{{ summary.scheduledTasks }}/{{ summary.totalTasks }}</span></div>
          <div class="aasg-metric"><span class="aasg-metric__label">完成率</span><span class="aasg-metric__value">{{ summary.completionRate }}%</span></div>
          <div class="aasg-metric"><span class="aasg-metric__label">已排/应排学时</span><span class="aasg-metric__value">{{ summary.scheduledHours }}/{{ summary.expectedHours }}</span></div>
          <div class="aasg-metric" :class="{ 'is-bad': summary.hardConflicts }"><span class="aasg-metric__label">HARD 冲突</span><span class="aasg-metric__value">{{ summary.hardConflicts }}</span></div>
          <div class="aasg-metric" :class="{ 'is-warn': summary.softConflicts }"><span class="aasg-metric__label">SOFT 冲突</span><span class="aasg-metric__value">{{ summary.softConflicts }}</span></div>
        </div>
        <div class="aasg-bar">
          <span :class="summary.canPrePublish ? 'is-ok' : 'is-bad'">{{ summary.canPrePublish ? '可预发布' : '存在HARD冲突，禁止预发布' }}</span>
          <button class="mp-btn" @click="$router.push('/admin/academic-affairs/schedule')">前往批次列表操作预发布</button>
          <button class="mp-btn" @click="$router.push(`/admin/academic-affairs/schedule/${resultBatchId}/views`)">查看三视图</button>
        </div>
      </template>
    </div>

    <!-- 排课调整（11号卡：预发布阶段教师异议 → 定点改排） -->
    <div v-else-if="tab === 'adjust'" class="mp-stack">
      <AppSectionCard title="提交本人课表异议（教师端）">
        <div class="aasg-assign-form">
          <label>课表批次ID<input v-model.trim="objectForm.batchId" class="aa-input" /></label>
          <label>排课条目ID<input v-model.trim="objectForm.itemId" class="aa-input" /></label>
          <label class="aasg-assign-form__grow">异议原因（≥5字）<input v-model.trim="objectForm.reason" class="aa-input" /></label>
          <AppButton variant="primary" size="small" :disabled="submittingObjection" @click="submitObjection">提交异议</AppButton>
        </div>
      </AppSectionCard>

      <div class="aasg-bar">
        <AppTextInput v-model="adjustBatchId" placeholder="课表批次 ID" style="max-width:200px" @keyup.enter="loadObjections" />
        <AppButton variant="primary" size="small" @click="loadObjections">加载异议清单</AppButton>
      </div>
      <EmptyState v-if="!objections.length" title="暂无异议" description="预发布批次教师提出异议后在此定点改排" />
      <DataTable v-else :columns="objColumns" :rows="objections" row-key="itemId">
        <template #cell-slot="{ row }">周{{ row.weekday }} 第{{ row.slotNo }}节</template>
        <template #cell-ops="{ row }"><button class="mp-link" @click="openAdjust(row)">改排</button></template>
      </DataTable>
    </div>

    <AppDrawer :visible="ruleVisible" title="新增排课规则" @close="ruleVisible = false">
      <div class="aasg-form">
        <AppFormItem label="规则键" required><AppTextInput v-model="ruleForm.ruleKey" placeholder="如 maxDailySlots / avoidEvening" :disabled="saving" /></AppFormItem>
        <AppFormItem label="学期 ID"><AppTextInput v-model="ruleForm.termId" placeholder="可空" :disabled="saving" /></AppFormItem>
        <AppFormItem label="规则值(JSON)"><AppTextInput v-model="ruleForm.ruleValueRaw" placeholder='如 {"max":8}' :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="ruleVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="saveRule">保存</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="constraintVisible" title="新增排课约束" @close="constraintVisible = false">
      <div class="aasg-form">
        <AppFormItem label="约束类型" required>
          <AppSelect v-model="constraintForm.ruleKey" :options="CONSTRAINT_OPTIONS" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="学期 ID"><AppTextInput v-model="constraintForm.termId" placeholder="可空" :disabled="saving" /></AppFormItem>
        <AppFormItem label="约束值" required><AppNumberInput v-model="constraintForm.value" :min="0" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="constraintVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="saveConstraint">保存</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="adjustDlg.visible"
      :title="`排课调整 · ${adjustDlg.courseName || ''}`"
      type="primary"
      confirm-text="确认改排"
      :submitting="adjustDlg.submitting"
      @confirm="doAdjust"
    >
      <div class="aasg-assign-form">
        <label>星期<input v-model.number="adjustDlg.weekday" type="number" min="1" max="7" class="aa-input" /></label>
        <label>节次<input v-model.number="adjustDlg.slotNo" type="number" min="1" class="aa-input" /></label>
        <label>教室<input v-model.trim="adjustDlg.classroom" class="aa-input" /></label>
        <label>单双周
          <select v-model="adjustDlg.weekParity" class="aa-input">
            <option value="ALL">全周</option>
            <option value="ODD">单周</option>
            <option value="EVEN">双周</option>
          </select>
        </label>
      </div>
    </AppConfirmDialog>
    <!-- 驳回原因保持「选填」：原实现为 window.prompt 且未做任何长度校验（reason || ''），
         此处不加 require-reason，避免把选填字段悄悄变成必填 -->
    <AppConfirmDialog
      v-model:visible="reasonDialog.visible" title="驳回教师可用时间申报" type="danger"
      confirm-text="确认驳回" :submitting="reasonDialog.submitting" @confirm="onReasonConfirm"
    >
      <label class="aasg-reason-label">驳回原因（选填）
        <textarea v-model.trim="reasonDialog.reason" class="aa-input" rows="3" placeholder="如：该时段已排本人其它课程" />
      </label>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 排课管理增强（/admin/academic-affairs/scheduling）：规则/约束 + 教师可用时间采纳 + 冲突报告
 * + 教室可用时间（05）+ 自动排课预留(Excel导入通道)（07）+ 排课结果汇总（10）+ 排课调整（11）。 */
import { ModulePageShell, DataTable, StatusTag, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppSectionCard, AppTextInput, AppFormItem, AppInlineAlert, AppSelect, AppNumberInput, AppConfirmDialog } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi, academicAffairsSchedulingApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const CONSTRAINT_KEYS = {
  teacherDailyMax: '教师每日上限节数',
  courseIntervalMin: '同课程间隔最小天数',
  peAfterBanCulture: '体育课后N节禁排文化课'
}
const CONSTRAINT_OPTIONS = Object.entries(CONSTRAINT_KEYS).map(([value, label]) => ({ value, label }))

export default {
  name: 'AaSchedulingConsoleView',
  components: {
    ModulePageShell, DataTable, StatusTag, EmptyState, AppButton, AppDrawer, AppSectionCard,
    AppTextInput, AppFormItem, AppInlineAlert, AppSelect, AppNumberInput, AppConfirmDialog, AaScheduleGrid
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'rules',
      tabs: [
        { key: 'rules', label: '排课规则' }, { key: 'availability', label: '教师可用时间' },
        { key: 'conflict', label: '冲突报告' }, { key: 'constraint', label: '排课约束' },
        { key: 'room', label: '教室可用时间' }, { key: 'import', label: '自动排课预留' },
        { key: 'result', label: '排课结果' }, { key: 'adjust', label: '排课调整' }
      ],
      CONSTRAINT_OPTIONS,
      termId: '', rules: [], avails: [], conflictBatchId: '', conflict: null,
      ruleColumns: [{ key: 'ruleKey', title: '规则键' }, { key: 'value', title: '值' }, { key: 'ops', title: '操作' }],
      availColumns: [{ key: 'teacherName', title: '教师' }, { key: 'slot', title: '时段' }, { key: 'reason', title: '原因' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      objColumns: [{ key: 'teacherName', title: '教师' }, { key: 'courseName', title: '课程' }, { key: 'slot', title: '时段' }, { key: 'objectionReason', title: '异议原因' }, { key: 'ops', title: '操作' }],
      ruleVisible: false, ruleForm: { ruleKey: '', termId: '', ruleValueRaw: '' }, formError: '', saving: false,
      constraintVisible: false, constraintForm: { ruleKey: 'teacherDailyMax', termId: '', value: 1 },
      // 05 教室可用时间
      roomBatchId: '', roomClassroom: '', roomItems: [], roomNote: '', slots: [],
      // 07 自动排课预留
      importBatchId: '', pickedFile: null, importing: false, importResult: null,
      // 10 排课结果
      resultBatchId: '', summary: null,
      // 11 排课调整
      objectForm: { batchId: '', itemId: '', reason: '' }, submittingObjection: false,
      adjustBatchId: '', objections: [],
      adjustDlg: { visible: false, submitting: false, itemId: '', batchId: '', courseName: '', weekday: 1, slotNo: 1, classroom: '', weekParity: 'ALL' },
      reasonDialog: { visible: false, submitting: false, reason: '', action: null }
    }
  },
  computed: {
    generalRules() { return this.rules.filter((r) => !CONSTRAINT_KEYS[r.ruleKey]) },
    constraintRules() { return this.rules.filter((r) => CONSTRAINT_KEYS[r.ruleKey]) }
  },
  watch: {
    tab(v) { if (v === 'availability') this.loadAvails() },
    '$route.query.tab'(v) { if (v && this.tabs.some((t) => t.key === v)) this.tab = v }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.loadRules()
    this.loadSlots()
  },
  methods: {
    dimLabel(d) { return { TEACHER: '教师冲突', CLASS: '班级冲突', CLASSROOM: '教室冲突' }[d] || d },
    constraintLabel(key) { return CONSTRAINT_KEYS[key] || key },
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async loadRules() {
      const res = await api.listRules(this.termId ? { termId: this.termId } : {})
      this.rules = res.code === 0 ? (res.data.items || []) : []
    },
    async loadAvails() {
      const res = await api.listAvailability({})
      this.avails = res.code === 0 ? (res.data.items || []) : []
    },
    openRule() { this.ruleForm = { ruleKey: '', termId: this.termId, ruleValueRaw: '' }; this.formError = ''; this.ruleVisible = true },
    async saveRule() {
      if (!this.ruleForm.ruleKey) { this.formError = '规则键必填'; return }
      let ruleValue = null
      if (this.ruleForm.ruleValueRaw) {
        try { ruleValue = JSON.parse(this.ruleForm.ruleValueRaw) } catch (e) { this.formError = '规则值不是合法 JSON'; return }
      }
      this.saving = true
      const res = await api.saveRule({ ruleKey: this.ruleForm.ruleKey, termId: this.ruleForm.termId || undefined, ruleValue })
      this.saving = false
      if (res.code === 0) { toast.success('已保存'); this.ruleVisible = false; this.loadRules() } else this.formError = res.message
    },
    openConstraint() { this.constraintForm = { ruleKey: 'teacherDailyMax', termId: this.termId, value: 1 }; this.formError = ''; this.constraintVisible = true },
    async saveConstraint() {
      this.saving = true
      const res = await api.saveRule({
        ruleKey: this.constraintForm.ruleKey,
        termId: this.constraintForm.termId || undefined,
        ruleValue: { value: this.constraintForm.value }
      })
      this.saving = false
      if (res.code === 0) { toast.success('已保存'); this.constraintVisible = false; this.loadRules() } else this.formError = res.message
    },
    async delRule(id) {
      const res = await api.deleteRule(id)
      if (res.code === 0) { toast.success('已删除'); this.loadRules() } else toast.error(res.message)
    },
    async reviewAvail(id, action) {
      const res = await api.reviewAvailability(id, action)
      if (res.code === 0) { toast.success('已采纳'); this.loadAvails() } else toast.error(res.message)
    },
    rejectAvail(id) {
      this.reasonDialog = {
        visible: true, submitting: false, reason: '',
        action: async (reason) => {
          const res = await api.reviewAvailability(id, 'REJECT', reason || '')
          if (res.code !== 0) { toast.error(res.message); return false }
          toast.success('已驳回'); this.loadAvails(); return true
        }
      }
    },
    /** 失败时保留弹窗与已填内容，仅成功才关闭（避免接口失败后用户重打一遍） */
    async onReasonConfirm() {
      const action = this.reasonDialog.action
      if (!action) return
      this.reasonDialog.submitting = true
      const ok = await action(this.reasonDialog.reason)
      this.reasonDialog.submitting = false
      if (ok) this.reasonDialog.visible = false
    },
    async loadConflict() {
      if (!this.conflictBatchId) { toast.error('请填课表批次 ID'); return }
      const res = await api.conflictReport(this.conflictBatchId)
      if (res.code === 0) this.conflict = res.data
      else toast.error(res.message)
    },
    // 05 教室可用时间
    async loadRoomView() {
      if (!this.roomBatchId || !this.roomClassroom) { toast.error('请填写批次ID与教室名称'); return }
      const res = await academicAffairsApi.getScheduleRoomView(this.roomBatchId, this.roomClassroom)
      if (res.code === 0) { this.roomItems = res.data.items || []; this.roomNote = res.data.note || '' }
      else toast.error(res.message || '查询失败')
    },
    // 07 自动排课预留
    async downloadTemplate() {
      await academicAffairsApi.downloadScheduleImportTemplate()
    },
    onFilePicked(e) { this.pickedFile = (e.target.files && e.target.files[0]) || null },
    async doImportXlsx() {
      if (!this.importBatchId || !this.pickedFile) return
      this.importing = true
      const res = await academicAffairsApi.uploadScheduleImportXlsx(this.importBatchId, this.pickedFile)
      this.importing = false
      if (res.code === 0) { this.importResult = res.data; toast.success('导入完成') }
      else toast.error(res.message || '导入失败')
      this.pickedFile = null
      if (this.$refs.importFile) this.$refs.importFile.value = ''
    },
    // 10 排课结果
    async loadSummary() {
      if (!this.resultBatchId) { toast.error('请填课表批次 ID'); return }
      const res = await academicAffairsApi.getScheduleSummary(this.resultBatchId)
      if (res.code === 0) this.summary = res.data
      else toast.error(res.message || '查询失败')
    },
    // 11 排课调整
    async submitObjection() {
      if (!this.objectForm.batchId || !this.objectForm.itemId) { toast.error('请填写批次ID与条目ID'); return }
      if (!this.objectForm.reason || this.objectForm.reason.length < 5) { toast.error('异议原因不少于5字'); return }
      this.submittingObjection = true
      const res = await academicAffairsApi.teacherObjectSchedule(this.objectForm.batchId, this.objectForm.itemId, this.objectForm.reason)
      this.submittingObjection = false
      if (res.code === 0) { toast.success('异议已提交'); this.objectForm = { batchId: '', itemId: '', reason: '' } }
      else toast.error(res.message || '提交失败')
    },
    async loadObjections() {
      if (!this.adjustBatchId) { toast.error('请填课表批次 ID'); return }
      const res = await academicAffairsApi.getScheduleObjections(this.adjustBatchId)
      this.objections = res.code === 0 ? (res.data.items || []) : []
    },
    openAdjust(row) {
      this.adjustDlg = {
        visible: true, submitting: false, itemId: row.itemId, batchId: this.adjustBatchId,
        courseName: row.courseName, weekday: row.weekday, slotNo: row.slotNo,
        classroom: row.classroom || '', weekParity: row.weekParity || 'ALL'
      }
    },
    async doAdjust() {
      this.adjustDlg.submitting = true
      const res = await academicAffairsApi.adjustScheduleItem(this.adjustDlg.batchId, this.adjustDlg.itemId, {
        weekday: this.adjustDlg.weekday, slotNo: this.adjustDlg.slotNo,
        classroom: this.adjustDlg.classroom || undefined, weekParity: this.adjustDlg.weekParity
      })
      this.adjustDlg.submitting = false
      if (res.code === 0) { this.adjustDlg.visible = false; toast.success('已改排'); this.loadObjections() }
      else toast.error(res.message || '改排失败（可能存在冲突）')
    }
  }
}
</script>

<style scoped>
.aasg-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; flex-wrap: wrap; }
.aasg-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; white-space: nowrap; }
.aasg-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aasg-bar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.aasg-summary { display: flex; gap: 16px; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; margin-bottom: 12px; font-size: 13px; }
.aasg-summary .is-bad { color: var(--danger-color, #dc2626); font-weight: 600; }
.aasg-summary .is-warn { color: var(--warning-color, #d97706); font-weight: 600; }
.aasg-summary .is-ok { color: var(--success-color, #16a34a); font-weight: 600; }
.aasg-section-title { font-weight: 500; margin: 12px 0 8px; }
.aasg-conflicts { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aasg-conflicts li { padding: 8px 12px; background: var(--fill-light, #f8fafc); border-radius: 6px; font-size: 13px; }
.aasg-tag { display: inline-block; padding: 1px 8px; border-radius: 4px; margin-right: 8px; font-size: 12px; }
.aasg-tag.is-hard { background: #fee2e2; color: #dc2626; }
.aasg-tag.is-soft { background: #fef3c7; color: #d97706; }
.aasg-form { display: flex; flex-direction: column; gap: 12px; }
.aasg-file { font-size: 13px; }
.aasg-disabled-btn { display: inline-flex; align-items: center; padding: 0 12px; height: 30px; border-radius: 6px; background: var(--fill-100, #f2f3f5); color: var(--text-400, #8a9099); font-size: 13px; cursor: not-allowed; }
.aasg-metrics { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; }
.aasg-metric { min-width: 140px; padding: 12px 16px; border-radius: 8px; background: var(--fill-light, #f8fafc); display: flex; flex-direction: column; gap: 4px; }
.aasg-metric.is-bad { background: #fef2f2; }
.aasg-metric.is-warn { background: #fffbeb; }
.aasg-metric__label { font-size: 12px; color: var(--text-500, #646a73); }
.aasg-metric__value { font-size: 20px; font-weight: 600; color: var(--text-900, #1f2329); }
.aasg-assign-form { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.aasg-assign-form__grow { grid-column: 1 / -1; }
.aasg-assign-form label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aasg-reason-label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aasg-reason-label textarea.aa-input { height: auto; padding: 8px 10px; resize: vertical; }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.mp-btn { height: 30px; padding: 0 12px; border-radius: 6px; border: 1px solid var(--border-300, #d0d3d9); background: var(--bg-white, #fff); cursor: pointer; font-size: 13px; }
</style>
