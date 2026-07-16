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
        <AppPagination v-if="risks.length" v-model:page="paging.page" v-model:pageSize="paging.pageSize"
                       :total="paging.total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>

    <!-- 新建风险：学生 ID + 标题两个字段，用抽屉承载 -->
    <AppDrawer v-model:visible="createDrawer.visible" title="新建风险">
      <div class="sa-form">
        <AppFormItem label="学生 ID" required :error="createDrawer.errors.studentId">
          <AppTextInput v-model="createDrawer.form.studentId" placeholder="请输入学生 ID" :disabled="actioning" />
        </AppFormItem>
        <AppFormItem label="风险标题" required :error="createDrawer.errors.title">
          <AppTextInput v-model="createDrawer.form.title" placeholder="如：学工风险预警" :disabled="actioning" />
        </AppFormItem>
        <AppInlineAlert v-if="createDrawer.errorMessage" type="danger" :description="createDrawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="sa-btn" :disabled="actioning" @click="createDrawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.risk.create" :loading="actioning" @click="submitCreateRisk">
          新建
        </AppPermissionButton>
      </template>
    </AppDrawer>

    <!-- 分派/处置 —— 统一走带原因校验的二次确认弹窗 -->
    <AppConfirmDialog
      v-model:visible="dialog.visible"
      :title="dialog.title"
      :message="dialog.message"
      :type="dialog.type"
      :confirm-text="dialog.confirmText"
      require-reason
      :reason-label="dialog.reasonLabel"
      :reason-placeholder="dialog.reasonPlaceholder"
      :reason-min-length="dialog.reasonMinLength"
      :submitting="actioning"
      @confirm="onDialogConfirm"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog,
  AppFormItem,
  AppGlobalState,
  AppInlineAlert,
  AppMetricCard,
  AppPageShell,
  AppPagination,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppStatusTag,
  AppTextInput
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  name: 'StudentAffairsRiskListView',
  components: {
    AppConfirmDialog,
    AppDrawer,
    AppFormItem,
    AppGlobalState,
    AppInlineAlert,
    AppMetricCard,
    AppPageShell,
    AppPagination,
    AppPermissionButton,
    AppRiskTag,
    AppSectionCard,
    AppStatusTag,
    AppTextInput
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
      },
      paging: { page: 1, pageSize: 20, total: 0 },
      createDrawer: { visible: false, form: { studentId: '', title: '' }, errors: {}, errorMessage: '' },
      // 分派/处置共用同一个确认弹窗，riskId 记录当前操作的目标行。
      dialog: {
        visible: false, action: '', riskId: '', title: '', message: '', type: 'primary', confirmText: '确认',
        reasonLabel: '原因', reasonPlaceholder: '', reasonMinLength: 1
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
        const res = await studentAffairsApi.listRiskRecords({ ...this.filters, page: this.paging.page, pageSize: this.paging.pageSize })
        this.risks = res.data.items || []
        this.total = res.data.total || this.risks.length
        this.paging.total = this.total
      } catch (e) {
        this.errorMessage = e.message || '风险数据加载失败'
      } finally {
        this.loading = false
      }
    },
    reload() {
      this.scanResult = ''
      this.paging.page = 1
      this.load()
    },
    createRisk() {
      this.createDrawer = { visible: true, form: { studentId: '', title: '' }, errors: {}, errorMessage: '' }
    },
    async submitCreateRisk() {
      const { form, errors } = this.createDrawer
      errors.studentId = form.studentId.trim() ? '' : '请输入学生 ID'
      errors.title = form.title.trim() ? '' : '请输入风险标题'
      if (errors.studentId || errors.title) return
      this.actioning = true
      this.createDrawer.errorMessage = ''
      try {
        await studentAffairsApi.createRiskRecord({
          studentId: form.studentId.trim(),
          source: 'MANUAL',
          sourceRefId: `manual-${Date.now()}`,
          riskLevel: 'MEDIUM',
          title: form.title.trim(),
          detail: form.title.trim()
        })
        this.createDrawer.visible = false
        await this.load()
      } catch (e) {
        this.createDrawer.errorMessage = e.message || '新建失败'
      } finally {
        this.actioning = false
      }
    },
    openDialog(action, riskId, opts) {
      this.dialog = {
        visible: true, action, riskId,
        type: 'primary', confirmText: '确认',
        reasonLabel: '原因', reasonPlaceholder: '', reasonMinLength: 1,
        ...opts
      }
    },
    assign(risk) {
      this.openDialog('assign', risk.riskId, {
        title: '分派责任人',
        message: `为「${risk.realName || '该学生'}」的风险分派责任人。`,
        confirmText: '确认分派',
        reasonLabel: '责任人 ID',
        reasonPlaceholder: risk.ownerId ? `当前责任人：${risk.ownerId}，请输入新的责任人 ID` : '请输入责任人 ID'
      })
    },
    process(risk) {
      this.openDialog('process', risk.riskId, {
        title: '处置风险',
        message: `记录「${risk.realName || '该学生'}」本次风险的处置过程。`,
        confirmText: '确认处置',
        reasonLabel: '处置记录',
        reasonPlaceholder: '如：已联系学生并记录处置过程'
      })
    },
    async onDialogConfirm(payload) {
      const reason = (payload && payload.reason) || ''
      const id = this.dialog.riskId
      const call = {
        assign: () => studentAffairsApi.assignRisk(id, reason),
        process: () => studentAffairsApi.processRisk(id, reason)
      }[this.dialog.action]
      if (!call) return
      await this.runAction(call)
      this.dialog.visible = false
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
.sa-table + .app-pagination {
  margin-top: var(--space-3);
}
.sa-form { display: flex; flex-direction: column; gap: var(--space-4); }
.sa-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.sa-btn:hover { border-color: var(--border-dark); }
.sa-btn:disabled { opacity: 0.6; cursor: not-allowed; }
@media (max-width: 960px) {
  .sa-grid--metrics,
  .sa-rules {
    grid-template-columns: 1fr;
  }
}
</style>
