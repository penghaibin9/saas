<template>
  <AppPageShell
    title="风险预警"
    subtitle="聚合学业、请假、宿舍、心理等来源的风险记录，PC 端负责分派、处置、升级和闭环入口。"
    role-name="SCHOOL_ADMIN / COUNSELOR"
    data-scope-name="学工数据范围"
    watermark-purpose="学工风险预警查看"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.risk.scan" variant="secondary" :loading="actioning" @click="scanTimeout">
        扫描超时
      </AppPermissionButton>
      <AppPermissionButton code="studentAffairs.risk.create" :loading="actioning" @click="createRisk">
        新建风险
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载学工风险预警数据..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard v-if="isRulePanel" title="风险规则摘要">
        <div class="sa-rules">
          <div v-for="rule in ruleItems" :key="rule.title" class="sa-rule">
            <strong>{{ rule.title }}</strong>
            <span>{{ rule.desc }}</span>
          </div>
        </div>
      </AppSectionCard>

      <AppSectionCard v-else title="风险学生与处置">
        <div class="sa-toolbar">
          <select v-model="filters.source" @change="reload">
            <option value="">全部来源</option>
            <option value="ACADEMIC_WARNING">学业预警</option>
            <option value="LEAVE_OVERDUE">请假异常</option>
            <option value="DORM">宿舍异常</option>
            <option value="MENTAL">心理关注</option>
          </select>
          <select v-model="filters.riskLevel" @change="reload">
            <option value="">全部等级</option>
            <option value="LOW">低</option>
            <option value="MEDIUM">中</option>
            <option value="HIGH">高</option>
            <option value="CRITICAL">重大</option>
          </select>
          <select v-model="filters.status" @change="reload">
            <option value="">全部状态</option>
            <option value="NEW">新建</option>
            <option value="ASSIGNED">已分派</option>
            <option value="PROCESSING">处置中</option>
            <option value="FOLLOWING">持续跟进</option>
            <option value="ESCALATED">已升级</option>
            <option value="CLOSED">已关闭</option>
          </select>
          <span v-if="scanResult" class="sa-scan">{{ scanResult }}</span>
        </div>

        <table class="sa-table">
          <thead>
            <tr>
              <th>学生</th>
              <th>来源</th>
              <th>等级</th>
              <th>状态</th>
              <th>责任人</th>
              <th>摘要</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="risk in risks" :key="risk.riskId">
              <td>
                <strong>{{ risk.realName || '未命名学生' }}</strong>
                <small>{{ risk.studentNo || risk.studentId }}</small>
              </td>
              <td>{{ sourceLabel(risk.source) }}</td>
              <td><AppRiskTag :level="risk.riskLevel" /></td>
              <td><AppStatusTag :type="statusKind(risk.status)" :label="risk.statusLabel || risk.status" /></td>
              <td>{{ risk.ownerId || '待分派' }}</td>
              <td>
                <span>{{ risk.title || '风险记录' }}</span>
                <small v-if="risk.mentalMasked">心理来源明细已按角色脱敏</small>
              </td>
              <td class="sa-actions">
                <AppPermissionButton code="studentAffairs.risk.detail" size="sm" variant="secondary" @click="$router.push(`/admin/student-affairs/risk/${risk.riskId}`)">
                  详情
                </AppPermissionButton>
                <AppPermissionButton code="studentAffairs.risk.assign" size="sm" variant="secondary" :loading="actioning" @click="assign(risk)">
                  分派
                </AppPermissionButton>
                <AppPermissionButton code="studentAffairs.risk.process" size="sm" :loading="actioning" @click="process(risk)">
                  处置
                </AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!risks.length">
              <td colspan="7" class="sa-empty">当前范围内暂无风险记录</td>
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
  AppRiskTag,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  name: 'StudentAffairsRiskListView',
  components: {
    AppGlobalState,
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSectionCard,
    AppStatusTag
  },
  data() {
    return {
      loading: true,
      actioning: false,
      errorMessage: '',
      risks: [],
      total: 0,
      scanResult: '',
      filters: {
        source: '',
        riskLevel: '',
        status: ''
      }
    }
  },
  computed: {
    isRulePanel() {
      return this.$route.name === 'student-affairs-risk-rules'
    },
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    metricCards() {
      const high = this.risks.filter((item) => ['HIGH', 'CRITICAL'].includes(item.riskLevel)).length
      const open = this.risks.filter((item) => item.status !== 'CLOSED').length
      const mentalMasked = this.risks.filter((item) => item.mentalMasked).length
      return [
        { key: 'total', label: '风险记录', value: this.total, accent: 'primary' },
        { key: 'high', label: '高风险', value: high, accent: high ? 'risk' : 'success' },
        { key: 'open', label: '未闭环', value: open, accent: open ? 'warning' : 'success' },
        { key: 'mental', label: '心理脱敏', value: mentalMasked, accent: 'primary' }
      ]
    },
    ruleItems() {
      return [
        { title: '来源去重', desc: '同一学生、同一来源、同一 sourceRefId 重复建单由后端拦截。' },
        { title: '心理明细脱敏', desc: '心理来源 detail 只对授权角色展示，普通辅导员只看到脱敏摘要。' },
        { title: '处置后关闭', desc: '风险关闭前必须存在处置记录，关闭后写入学生 360 时间线。' },
        { title: '超时扫描', desc: '超时扫描负责自动分派和升级，接口幂等，PC 端只触发真实后端任务。' }
      ]
    }
  },
  watch: {
    '$route.name'() {
      this.scanResult = ''
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
        const res = await studentAffairsApi.listRiskRecords({ ...this.filters, page: 1, pageSize: 50 })
        this.risks = res.data.items || []
        this.total = res.data.total || this.risks.length
      } catch (e) {
        this.errorMessage = e.message || '风险数据加载失败'
      } finally {
        this.loading = false
      }
    },
    reload() {
      this.scanResult = ''
      this.load()
    },
    async createRisk() {
      const studentId = window.prompt('请输入学生 ID')
      if (!studentId) return
      const title = window.prompt('请输入风险标题', '学工风险预警')
      if (!title) return
      await this.runAction(() => studentAffairsApi.createRiskRecord({
        studentId,
        source: 'MANUAL',
        sourceRefId: `manual-${Date.now()}`,
        riskLevel: 'MEDIUM',
        title,
        detail: title
      }))
    },
    async assign(risk) {
      const ownerId = window.prompt('请输入责任人 ID', risk.ownerId || '')
      if (!ownerId) return
      await this.runAction(() => studentAffairsApi.assignRisk(risk.riskId, ownerId))
    },
    async process(risk) {
      const content = window.prompt('请输入处置记录', '已联系学生并记录处置过程')
      if (!content) return
      await this.runAction(() => studentAffairsApi.processRisk(risk.riskId, content))
    },
    async scanTimeout() {
      this.actioning = true
      try {
        const res = await studentAffairsApi.scanRiskTimeout()
        this.scanResult = `本次扫描自动分派 ${res.data.assigned || 0} 条，升级 ${res.data.escalated || 0} 条`
        await this.load()
      } catch (e) {
        this.errorMessage = e.message || '风险超时扫描失败'
      } finally {
        this.actioning = false
      }
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
    sourceLabel(source) {
      return ({
        ACADEMIC_WARNING: '学业预警',
        LEAVE_OVERDUE: '请假异常',
        DORM: '宿舍异常',
        MENTAL: '心理关注',
        MANUAL: '人工建单'
      })[source] || source || '未设置'
    },
    statusKind(status) {
      if (status === 'CLOSED') return 'success'
      if (status === 'ESCALATED') return 'danger'
      if (['PROCESSING', 'FOLLOWING'].includes(status)) return 'warning'
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
.sa-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.sa-toolbar select {
  min-width: 140px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-surface);
  padding: var(--space-2) var(--space-3);
}
.sa-scan {
  color: var(--warning-700);
  background: var(--warning-50);
  border: 1px solid var(--warning-200);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
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
.sa-table small,
.sa-rule span {
  display: block;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.sa-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sa-empty {
  color: var(--text-tertiary);
  padding: var(--space-4);
  text-align: center;
}
.sa-rules {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}
.sa-rule {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  padding: var(--space-4);
}
@media (max-width: 960px) {
  .sa-grid--metrics,
  .sa-rules {
    grid-template-columns: 1fr;
  }
}
</style>
