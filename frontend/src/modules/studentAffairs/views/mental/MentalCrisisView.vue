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
        <table class="sa-table">
          <thead>
            <tr>
              <th>学生</th>
              <th>关注等级</th>
              <th>状态</th>
              <th>事由摘要</th>
              <th>关联风险</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in items" :key="row.referralId" :class="{ 'sa-crisis': row.level === 'CRISIS' }">
              <td>
                <strong>{{ row.realName || '未命名学生' }}</strong>
                <small>{{ row.studentNo || row.studentId }}</small>
              </td>
              <td><AppStatusTag :type="levelKind(row.level)" :label="row.levelLabel || row.level" /></td>
              <td><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></td>
              <td>{{ row.reasonSummary || '—' }}</td>
              <td>
                <a v-if="row.riskId" class="sa-link" @click="gotoRisk(row.riskId)">风险 #{{ row.riskId }} →</a>
                <span v-else class="sa-muted">未升级</span>
              </td>
              <td class="sa-actions">
                <AppPermissionButton
                  v-if="row.status !== 'CLOSED' && !row.riskId"
                  code="studentAffairs.risk.psyDetail.view"
                  size="sm"
                  danger
                  :loading="actioning"
                  @click="askEscalate(row)"
                >
                  升级危机
                </AppPermissionButton>
                <AppPermissionButton
                  v-if="row.riskId"
                  code="studentAffairs.risk.view"
                  size="sm"
                  variant="secondary"
                  @click="gotoRisk(row.riskId)"
                >
                  查看风险
                </AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!items.length">
              <td colspan="6" class="sa-empty">当前授权范围内暂无心理关注记录</td>
            </tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>

    <!--
      危机升级二次确认：原逻辑为 window.confirm(是否升级) + window.prompt(可选升级说明，默认预填文案，
      取消/清空按 '' 处理，前后端均未对该说明内容做最少字数校验)。
      本次仅将两步原生弹窗合并为一个 AppConfirmDialog + 可选说明输入框，
      不新增、也不放宽任何强制理由校验——原来就没有"必须填写理由才能升级"的红线，这里保持一致，
      仅保留"是否确认升级"这一个真正的强制确认动作。
    -->
    <AppConfirmDialog
      v-model:visible="escalateDialog.visible"
      title="确认升级为心理危机"
      :message="escalateMessage"
      type="danger"
      confirm-text="确认升级"
      :submitting="actioning"
      @confirm="confirmEscalate"
      @cancel="escalateDialog.visible = false"
    >
      <AppFormItem label="升级说明（可选，无最少字数限制）">
        <AppQuickPhrases scene-key="sa.mental.escalate" @pick="onPickEscalateContent" />
        <AppTextarea ref="escalateTa" v-model="escalateDialog.content" placeholder="出现危机信号，立即升级并接入风险处置" />
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
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'
import { insertAtCursor, applyInsertion } from '@/utils/insertAtCursor'

const DEFAULT_ESCALATE_CONTENT = '出现危机信号，立即升级并接入风险处置'

export default {
  name: 'MentalCrisisView',
  components: { AppConfirmDialog, AppFormItem, AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppQuickPhrases, AppSectionCard, AppStatusTag, AppTextarea },
  data() {
    return {
      loading: true,
      actioning: false,
      errorMessage: '',
      items: [],
      escalateDialog: { visible: false, row: null, content: DEFAULT_ESCALATE_CONTENT }
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
    },
    escalateMessage() {
      const row = this.escalateDialog.row
      const name = row ? (row.realName || row.studentNo || row.studentId) : ''
      return `确认将「${name}」升级为心理危机？将自动生成风险中枢记录并进入处置闭环，升级后不可撤销（幂等，不会重复建单）。`
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        // 注：/mental/list 接口支持 page/pageSize 真分页，但本页顶部的"危机记录/在办危机/
        // 已接风险中枢/关注在册"统计卡是基于同一次拉取结果直接聚合的。这是安全红线页面，
        // 若接入 AppPagination 并把 pageSize 从当前的 100 降到常规分页粒度，会让统计卡只反映
        // 当前页数据、可能低估危机在办数量，风险高于"分页体验不足"，因此保留原有"一次性拉取
        // 前 100 条"的方式，不接入分页控件。
        const res = await studentAffairsApi.listMentalAttention({ page: 1, pageSize: 100 })
        this.items = res.data.items || []
      } catch (e) {
        this.errorMessage = e.message || '心理危机记录加载失败'
      } finally {
        this.loading = false
      }
    },
    askEscalate(row) {
      this.escalateDialog = { visible: true, row, content: DEFAULT_ESCALATE_CONTENT }
    },
    onPickEscalateContent(text) {
      const el = this.$refs.escalateTa && this.$refs.escalateTa.$refs && this.$refs.escalateTa.$refs.el
      if (!el) return
      const { value, selStart, selEnd } = insertAtCursor(el, this.escalateDialog.content, text)
      this.escalateDialog.content = value
      this.$nextTick(() => applyInsertion(el, selStart, selEnd))
    },
    async confirmEscalate() {
      const row = this.escalateDialog.row
      const content = this.escalateDialog.content
      this.escalateDialog.visible = false
      if (!row) return
      await this.runAction(() => studentAffairsApi.escalateMentalReferral(row.referralId, (content || '').trim()))
    },
    gotoRisk(riskId) {
      this.$router.push(`/admin/student-affairs/risk/${riskId}`)
    },
    async runAction(fn) {
      this.actioning = true
      try {
        await fn()
        await this.load()
      } catch (e) {
        this.errorMessage = e.message || '操作失败'
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
.sa-table {
  width: 100%;
  border-collapse: collapse;
}
.sa-table th,
.sa-table td {
  border-bottom: 1px solid var(--border-light);
  padding: var(--space-3);
  text-align: left;
  vertical-align: top;
}
.sa-table small {
  display: block;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.sa-crisis {
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
</style>
