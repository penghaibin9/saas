<template>
  <ModulePageShell
    title="排课管理 · 规则与冲突"
    :subtitle="'排课规则中心 · 教师可用时间采纳 · 批次全量冲突报告（HARD/SOFT 分级）'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aasg-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aasg-tab', { 'is-active': tab === t.key }]" @click="tab = t.key">{{ t.label }}</button>
    </div>

    <!-- 排课规则 -->
    <div v-if="tab === 'rules'" class="mp-stack">
      <div class="aasg-bar">
        <AppTermEntityPicker v-model="termId" placeholder="全部学期" style="max-width:240px" @change="loadRules" />
        <AppButton variant="primary" size="small" @click="openRule">新增规则</AppButton>
      </div>
      <EmptyState v-if="!rules.length" title="暂无排课规则" description="配置教师可用时间要求/教室类型/周学时约束" />
      <DataTable v-else :columns="ruleColumns" :rows="rules" row-key="ruleId">
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

    <!-- 自动排课 -->
    <div v-else-if="tab === 'auto'" class="mp-stack">
      <div class="aasg-bar">
        <AppScheduleBatchPicker v-model="autoBatchId" style="max-width:260px" />
        <AppButton variant="ghost" size="small" :loading="autoLoading" @click="runAuto(true)">试排预览</AppButton>
        <AppButton variant="primary" size="small" :loading="autoLoading" @click="doAuto">一键自动排课</AppButton>
        <AppButton variant="ghost" size="small" @click="doClearAuto">清除自动排课结果</AppButton>
      </div>
      <AppInlineAlert type="info" :description="'自动排课只处理「已确认、已设周学时、未标记不排课」的教学任务；只占用自动排课结果，教务员手工排的课不会被覆盖。排不下的任务会给出漏排原因与处置建议。'" />
      <template v-if="autoResult">
        <div class="aasg-summary">
          <span class="is-ok">已排入 {{ autoResult.placedSessions }} 节 / {{ autoResult.placedTasks }} 个任务</span>
          <span :class="{ 'is-bad': autoResult.missedTasks }">漏排 {{ autoResult.missedTasks }} 个任务</span>
          <span>可用教室 {{ autoResult.roomPoolSize }} 间</span>
          <span v-if="autoResult.dryRun" class="is-warn">试排结果（未落库）</span>
        </div>
        <div v-if="autoMissSummary.length" class="aasg-section">
          <div class="aasg-section-title">漏排原因分布（按此调整参数/教室/任务后再次排课）</div>
          <div class="aasg-reasons">
            <span v-for="s in autoMissSummary" :key="s.reason" class="aasg-reason-chip">{{ s.reasonLabel }} × {{ s.count }}</span>
          </div>
        </div>
        <DataTable v-if="autoMisses.length" :columns="missColumns" :rows="autoMisses" row-key="taskId">
          <template #cell-course="{ row }">{{ row.courseName }}<span v-if="row.className" class="aasg-sub">（{{ row.className }}）</span></template>
          <template #cell-progress="{ row }">{{ row.placedSessions }} / {{ row.needSessions }} 节</template>
          <template #cell-reason="{ row }"><span class="aasg-tag is-hard">{{ row.reasonLabel }}</span></template>
          <template #cell-detail="{ row }"><span class="aasg-advice">{{ row.detail }}</span></template>
        </DataTable>
        <EmptyState v-else-if="!autoResult.missedTasks" title="全部排课成功" description="所有待排任务均已排入，无漏排" />
      </template>
      <EmptyState v-else title="尚未执行自动排课" description="填入课表批次 ID，先试排预览确认无误后再一键落库" />
    </div>

    <!-- 冲突报告 -->
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

    <AppDrawer :visible="ruleVisible" title="新增排课规则" @close="ruleVisible = false">
      <div class="aasg-form">
        <AppFormItem label="规则键" required><AppTextInput v-model="ruleForm.ruleKey" placeholder="如 maxDailySlots / avoidEvening" :disabled="saving" /></AppFormItem>
        <AppFormItem label="学期"><AppTermEntityPicker v-model="ruleForm.termId" placeholder="选择学期（可空）" :disabled="saving" /></AppFormItem>
        <AppFormItem label="规则值(JSON)"><AppTextInput v-model="ruleForm.ruleValueRaw" placeholder='如 {"max":8}' :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="ruleVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="saveRule">保存</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage"
                      :require-reason="confirmRequireReason" :reason-label="confirmReasonLabel" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 排课管理增强（/admin/academic-affairs/scheduling）：规则中心 + 教师可用时间采纳 + 全量冲突报告。 */
import { ModulePageShell, DataTable, StatusTag, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppFormItem, AppInlineAlert, AppConfirmDialog, AppTermEntityPicker, AppScheduleBatchPicker } from '@/components/common'
import { academicAffairsApi, academicAffairsSchedulingApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaSchedulingConsoleView',
  components: { ModulePageShell, DataTable, StatusTag, EmptyState, AppButton, AppDrawer, AppTextInput, AppFormItem, AppInlineAlert, AppConfirmDialog, AppTermEntityPicker, AppScheduleBatchPicker },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'rules',
      tabs: [{ key: 'rules', label: '排课规则' }, { key: 'availability', label: '教师可用时间' }, { key: 'auto', label: '自动排课' }, { key: 'conflict', label: '冲突报告' }],
      termId: '', rules: [], avails: [], conflictBatchId: '', conflict: null,
      autoBatchId: '', autoResult: null, autoLoading: false,
      confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      confirmRequireReason: false, confirmReasonLabel: '',
      missColumns: [{ key: 'course', title: '课程' }, { key: 'teacherName', title: '教师' }, { key: 'progress', title: '已排/需排' }, { key: 'reason', title: '漏排原因' }, { key: 'detail', title: '处置建议' }],
      ruleColumns: [{ key: 'ruleKey', title: '规则键' }, { key: 'value', title: '值' }, { key: 'ops', title: '操作' }],
      availColumns: [{ key: 'teacherName', title: '教师' }, { key: 'slot', title: '时段' }, { key: 'reason', title: '原因' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      ruleVisible: false, ruleForm: { ruleKey: '', termId: '', ruleValueRaw: '' }, formError: '', saving: false
    }
  },
  watch: { tab(v) { if (v === 'availability') this.loadAvails() } },
  computed: {
    autoMisses() { return (this.autoResult && this.autoResult.misses) || [] },
    autoMissSummary() {
      const m = this.autoResult && this.autoResult.misses
      if (!m || !m.length) return []
      const by = {}
      m.forEach((x) => { by[x.reason] = by[x.reason] || { reason: x.reason, reasonLabel: x.reasonLabel, count: 0 }; by[x.reason].count += 1 })
      return Object.values(by).sort((a, b) => b.count - a.count)
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.loadRules()
  },
  methods: {
    dimLabel(d) { return { TEACHER: '教师冲突', CLASS: '班级冲突', CLASSROOM: '教室冲突' }[d] || d },
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
        try { ruleValue = JSON.parse(this.ruleForm.ruleValueRaw) } catch { this.formError = '规则值不是合法 JSON'; return }
      }
      this.saving = true
      const res = await api.saveRule({ ruleKey: this.ruleForm.ruleKey, termId: this.ruleForm.termId || undefined, ruleValue })
      this.saving = false
      if (res.code === 0) { toast.success('已保存'); this.ruleVisible = false; this.loadRules() } else this.formError = res.message
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
      this.confirmRequireReason = true
      this.confirmReasonLabel = '驳回原因（≥5 字）'
      this.confirmTitle = '驳回停课/换课申请'; this.confirmMessage = '请填写驳回原因，将记入审计并通知申请教师。'
      this.pendingAction = async (reason) => {
        const res = await api.reviewAvailability(id, 'REJECT', (reason || '').trim())
        if (res.code === 0) { toast.success('已驳回'); this.loadAvails() } else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    async loadConflict() {
      if (!this.conflictBatchId) { toast.error('请选择课表批次'); return }
      const res = await api.conflictReport(this.conflictBatchId)
      if (res.code === 0) this.conflict = res.data
      else toast.error(res.message)
    },
    async runAuto(dryRun) {
      if (!this.autoBatchId) { toast.error('请选择课表批次'); return }
      this.autoLoading = true
      const res = await api.autoSchedule(this.autoBatchId, dryRun)
      this.autoLoading = false
      if (res.code === 0) { this.autoResult = res.data; toast.success(dryRun ? '试排完成（未落库）' : `已排入 ${res.data.placedSessions} 节`) }
      else toast.error(res.message)
    },
    doAuto() {
      if (!this.autoBatchId) { toast.error('请选择课表批次'); return }
      this.confirmRequireReason = false
      this.confirmTitle = '自动排课'
      this.confirmMessage = '确定要对该批次执行自动排课并落库吗？只新增自动排课结果，教务员手工排的课不受影响。'
      this.pendingAction = () => this.runAuto(false)
      this.confirmVisible = true
    },
    doClearAuto() {
      if (!this.autoBatchId) { toast.error('请选择课表批次'); return }
      this.confirmRequireReason = false
      this.confirmTitle = '清除自动排课结果'
      this.confirmMessage = '确定清除该批次的全部自动排课结果吗？手工/导入排的课会保留。'
      this.pendingAction = async () => {
        const res = await api.clearAuto(this.autoBatchId)
        if (res.code === 0) { toast.success(`已清除 ${res.data.cleared} 节`); this.autoResult = null }
        else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    onConfirm(payload = {}) { const a = this.pendingAction; this.pendingAction = null; this.confirmRequireReason = false; if (a) a(payload && payload.reason) }
  }
}
</script>

<style scoped>
.aasg-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; }
.aasg-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aasg-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aasg-bar { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
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
.aasg-reasons { display: flex; flex-wrap: wrap; gap: 8px; }
.aasg-reason-chip { padding: 3px 10px; border-radius: 12px; background: #fef3c7; color: #b45309; font-size: 12px; }
.aasg-advice { color: var(--text-secondary, #64748b); font-size: 12px; }
.aasg-sub { color: var(--text-secondary, #94a3b8); font-size: 12px; }
</style>
