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
                  @click="escalate(row)"
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
  </AppPageShell>
</template>

<script>
import {
  AppGlobalState,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  name: 'MentalCrisisView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag },
  data() {
    return { loading: true, actioning: false, errorMessage: '', items: [] }
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
    async escalate(row) {
      if (!window.confirm(`确认将「${row.realName || row.studentId}」升级为心理危机？将自动生成风险中枢记录并进入处置闭环。`)) return
      const content = window.prompt('请填写升级说明（可空）', '出现危机信号，立即升级并接入风险处置') || ''
      await this.runAction(() => studentAffairsApi.escalateMentalReferral(row.referralId, content.trim()))
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
