<template>
  <AppPageShell
    title="心理危机升级"
    subtitle="危机升级复用风险中枢：升级后自动生成 source=MENTAL 的风险记录并接入风险处置闭环；升级幂等，不重复建单。"
    role-name="心理老师 / 授权辅导员 / 学工处(专项授权)"
    data-scope-name="PSY_STUDENT 逐生授权范围"
    watermark-purpose="心理危机升级处理"
  >
    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载心理危机记录..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard title="危机与可升级记录">
        <DataTable
          v-if="items.length"
          :columns="crisisColumns"
          :rows="items"
          row-key="referralId"
          :row-class="(row) => (row.level === 'CRISIS' ? 'sa-crisis' : '')"
        >
          <template #cell-student="{ row }">
            <div class="mp-cell-main">{{ row.realName || '未命名学生' }}</div>
            <div class="mp-cell-sub">{{ row.studentNo || row.studentId }}</div>
          </template>
          <template #cell-level="{ row }"><AppStatusTag :type="levelKind(row.level)" :label="row.levelLabel || row.level" /></template>
          <template #cell-status="{ row }"><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></template>
          <template #cell-reason="{ row }">{{ row.reasonSummary || '—' }}</template>
          <template #cell-risk="{ row }">
            <a v-if="row.riskId" class="sa-link" @click="gotoRisk(row.riskId)">风险 #{{ row.riskId }} →</a>
            <span v-else class="sa-muted">未升级</span>
          </template>
          <template #cell-actions="{ row }">
            <div class="sa-actions">
              <AppPermissionButton :allowed="canBtn('studentAffairs.mental.manage')"
                v-if="row.status !== 'CLOSED' && !row.riskId"
                code="studentAffairs.mental.manage"
                size="sm"
                danger
                :loading="actioning"
                @click="escalate(row)"
              >
                升级危机
              </AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.risk.view')"
                v-if="row.riskId"
                code="studentAffairs.risk.view"
                size="sm"
                variant="secondary"
                @click="gotoRisk(row.riskId)"
              >
                查看风险
              </AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前授权范围内暂无心理关注记录</p>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 升级为心理危机：原为 window.confirm + window.prompt 两步——
         先盲点一个确认框、再弹个单行框填说明。现合并为一屏，影响说明与说明输入同时可见。 -->
    <AppConfirmDialog
      v-model:visible="dlg.visible" :title="`升级为心理危机 · ${dlg.who}`" type="danger"
      confirm-text="确认升级"
      description="升级后将自动生成风险中枢记录并进入处置闭环，同时通知相关责任人。该动作留痕，请谨慎操作。"
      :submitting="actioning" @confirm="submitEscalate"
    >
      <AppFormItem label="升级说明（可空）">
        <AppTextarea ref="contentInput" v-model="dlg.content" :rows="3" :maxlength="500" :disabled="actioning"
                     placeholder="写清触发升级的危机信号与已采取的动作" />
        <AppQuickPhrases scene-key="sa.mental.escalate" @pick="onPickContent" />
      </AppFormItem>
    </AppConfirmDialog>
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog,
  AppFormItem,
  AppGlobalState,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppQuickPhrases,
  AppSectionCard,
  AppStatusTag,
  AppTextarea
} from '@/components/common'
import { DataTable } from '@/components/business'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'


const CRISIS_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'level', title: '关注等级' },
  { key: 'status', title: '状态' },
  { key: 'reason', title: '事由摘要' },
  { key: 'risk', title: '关联风险' },
  { key: 'actions', title: '操作', align: 'right', width: '200px' }
]

export default {
  name: 'MentalCrisisView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog,
    AppFormItem,
    AppGlobalState,
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppQuickPhrases,
    AppSectionCard,
    AppStatusTag,
    AppTextarea,
    DataTable
  },
  data() {
    return {
      crisisColumns: CRISIS_COLUMNS,
      loading: true, actioning: false, errorMessage: '', items: [],
      dlg: { visible: false, row: null, who: '', content: '' }
    }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    metricCards() {
      const crisis = this.items.filter((r) => r.level === 'CRISIS').length
      const escalated = this.items.filter((r) => r.status === 'ESCALATED' || r.riskId).length
      const openCrisis = this.items.filter((r) => r.level === 'CRISIS' && r.status !== 'CLOSED').length
      return [
        { key: 'crisis', label: '危机记录', value: crisis, accent: crisis ? 'risk' : 'success' },
        { key: 'open', label: '在办危机', value: openCrisis, accent: openCrisis ? 'risk' : 'success' },
        { key: 'escalated', label: '已接风险中枢', value: escalated, accent: 'primary' },
        { key: 'total', label: '关注在册', value: this.items.length, accent: 'info' }
      ]
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const res = await studentAffairsApi.listMentalAttention({ page: 1, pageSize: 100 })
        this.items = res.data.items || []
      } catch (e) {
        this.errorMessage = e.message || '心理危机记录加载失败'
      } finally {
        this.loading = false
      }
    },
    escalate(row) {
      // 原为 confirm + prompt 两步；合并成一个弹窗：影响说明与升级说明同屏，不用先盲点确认再填字。
      // 预填话术沿用改造前的原文，未改动。
      this.dlg = {
        visible: true,
        row,
        who: row.realName || row.studentNo || row.studentId,
        content: '出现危机信号，立即升级并接入风险处置'
      }
    },
    onPickContent(text) {
      const el = this.$refs.contentInput && this.$refs.contentInput.$refs.el
      if (!el) { this.dlg.content += text; return }
      const r = insertAtCursor(el, this.dlg.content, text)
      this.dlg.content = r.value
      this.$nextTick(() => applyInsertion(el, r.selStart, r.selEnd))
    },
    async submitEscalate() {
      const ok = await this.runAction(() =>
        studentAffairsApi.escalateMentalReferral(this.dlg.row.referralId, (this.dlg.content || '').trim()))
      if (ok) this.dlg.visible = false
    },
    gotoRisk(riskId) {
      this.$router.push(`/admin/student-affairs/risk/${riskId}`)
    },
    /** @returns {boolean} 是否成功；失败时保留弹窗与已填内容。 */
    async runAction(fn) {
      this.actioning = true
      this.errorMessage = ''
      try {
        await fn()
        await this.load()
        return true
      } catch (e) {
        this.errorMessage = e.message || '操作失败'
        return false
      } finally {
        this.actioning = false
      }
    },
    levelKind(level) {
      if (level === 'CRISIS') return 'danger'
      if (level === 'FOCUS') return 'warning'
      return 'info'
    },
    statusKind(status) {
      if (status === 'CLOSED') return 'success'
      if (status === 'ESCALATED') return 'danger'
      if (status === 'FOLLOWING') return 'warning'
      return 'info'
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
/* 危机行高亮：类由 DataTable 的 row-class 挂在子组件内部 <tr> 上，父级 scoped 样式须 :deep() 穿透 */
:deep(.dt__tr.sa-crisis) .dt__td {
  background: var(--danger-50, var(--warning-50));
}
.sa-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sa-link {
  color: var(--primary-600);
  cursor: pointer;
}
.sa-muted {
  color: var(--text-tertiary);
}
.sa-empty {
  color: var(--text-tertiary);
  padding: var(--space-4);
  text-align: center;
}
@media (max-width: 960px) {
  .sa-grid--metrics {
    grid-template-columns: 1fr;
  }
}
@import '@/styles/module-page.css';
</style>
