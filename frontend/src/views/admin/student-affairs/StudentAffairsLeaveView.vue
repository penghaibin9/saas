<template>
  <AppPageShell
    title="请假销假"
    subtitle="承接请假审批、销假确认、续假审批和超期未归扫描，所有数据继续按后端角色与班级范围返回。"
    role-name="SCHOOL_ADMIN / COUNSELOR"
    data-scope-name="学工数据范围"
    watermark-purpose="学工请假销假查看"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.leave.scan" variant="secondary" :loading="actioning" @click="scanOverdue">
        扫描超期
      </AppPermissionButton>
      <AppPermissionButton code="studentAffairs.leave.refresh" variant="secondary" @click="load">
        刷新
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载学工请假销假数据..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <div class="sa-tabs">
        <button v-for="tab in tabs" :key="tab.key" type="button" :class="{ active: activePanel === tab.key }" @click="goPanel(tab.key)">
          {{ tab.label }}
        </button>
      </div>

      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <div class="sa-layout">
        <AppSectionCard :title="panelTitle">
          <div v-if="activePanel === 'rules'" class="sa-rules">
            <div v-for="rule in ruleItems" :key="rule.title" class="sa-rule">
              <strong>{{ rule.title }}</strong>
              <span>{{ rule.desc }}</span>
            </div>
          </div>

          <div v-else>
            <div v-if="scanResult" class="sa-notice">{{ scanResult }}</div>
            <table class="sa-table">
              <thead>
                <tr>
                  <th>学生</th>
                  <th>类型</th>
                  <th>时间</th>
                  <th>状态</th>
                  <th>流程</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in visibleLeaves" :key="item.id">
                  <td>
                    <strong>{{ item.realName || '未命名学生' }}</strong>
                    <small>{{ item.studentNo || item.studentId }}</small>
                  </td>
                  <td>{{ leaveTypeLabel(item.leaveType) }}</td>
                  <td>{{ shortTime(item.startTime) }} 至 {{ shortTime(item.endTime) }}</td>
                  <td><AppStatusTag :type="leaveStatusKind(item.affairsStatus)" :label="item.affairsStatus || item.legacyStatus" /></td>
                  <td>{{ item.workflowInstanceId ? `流程 ${item.workflowInstanceId}` : '未建流程' }}</td>
                  <td class="sa-actions">
                    <AppPermissionButton code="studentAffairs.leave.detail" size="sm" variant="secondary" @click="openDetail(item.id)">
                      详情
                    </AppPermissionButton>
                    <AppPermissionButton code="studentAffairs.leave.approve" size="sm" :loading="actioning" @click="approve(item.id)">
                      通过
                    </AppPermissionButton>
                    <AppPermissionButton code="studentAffairs.leave.return" size="sm" variant="secondary" :loading="actioning" @click="returnBack(item.id)">
                      退回
                    </AppPermissionButton>
                    <AppPermissionButton code="studentAffairs.leave.reject" size="sm" variant="secondary" :loading="actioning" @click="reject(item.id)">
                      驳回
                    </AppPermissionButton>
                  </td>
                </tr>
                <tr v-if="!visibleLeaves.length">
                  <td colspan="6" class="sa-empty">当前范围内暂无待处理请假记录</td>
                </tr>
              </tbody>
            </table>
          </div>
        </AppSectionCard>

        <AppSectionCard title="请假详情">
          <AppDescriptionList v-if="selected" :items="detailItems" :columns="1" bordered />
          <AppAuditTrail v-if="selected" class="sa-audit" :records="auditRecords" compact :show-ip="false" />
          <div v-else class="sa-empty">从左侧列表选择一条请假记录查看详情</div>
        </AppSectionCard>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppAuditTrail,
  AppDescriptionList,
  AppGlobalState,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import { studentAffairsApi } from '@/modules/student-affairs/api/studentAffairs.api'

export default {
  name: 'StudentAffairsLeaveView',
  components: {
    AppAuditTrail,
    AppDescriptionList,
    AppGlobalState,
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppSectionCard,
    AppStatusTag
  },
  data() {
    return {
      loading: true,
      actioning: false,
      errorMessage: '',
      leaves: [],
      total: 0,
      selected: null,
      scanResult: ''
    }
  },
  computed: {
    activePanel() {
      return this.$route.params.panel || 'approvals'
    },
    tabs() {
      return [
        { key: 'approvals', label: '审批' },
        { key: 'exceptions', label: '异常' },
        { key: 'rules', label: '规则' }
      ]
    },
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    visibleLeaves() {
      if (this.activePanel === 'exceptions') {
        return this.leaves.filter((item) => ['OVERDUE', 'RETURNED', 'REJECTED'].includes(item.affairsStatus))
      }
      return this.leaves
    },
    panelTitle() {
      if (this.activePanel === 'exceptions') return '请假异常与超期未归'
      if (this.activePanel === 'rules') return '请假规则摘要'
      return '待审批请假'
    },
    metricCards() {
      const overdue = this.leaves.filter((item) => item.affairsStatus === 'OVERDUE').length
      const longLeave = this.leaves.filter((item) => Number(item.days || item.leaveDays || 0) >= 3).length
      return [
        { key: 'pending', label: '待处理', value: this.total, accent: 'primary' },
        { key: 'overdue', label: '超期未归', value: overdue, accent: overdue ? 'risk' : 'success' },
        { key: 'long', label: '长假', value: longLeave, accent: 'warning' }
      ]
    },
    ruleItems() {
      return [
        { title: '短假单节点', desc: '短假由辅导员节点完成审批，后端仍以真实工作流推进。' },
        { title: '长假多级审批', desc: '长假先经辅导员，再进入学院节点，终态同步旧在校服务状态列。' },
        { title: '销假闭环', desc: '销假确认后写入学生 360 时间线，形成 LEAVE_CLOSED 事件。' },
        { title: '超期扫描', desc: '扫描接口幂等，只把到期未销假的记录转入超期提醒。' }
      ]
    },
    detailItems() {
      const x = this.selected || {}
      return [
        { label: '学生', value: `${x.realName || ''} ${x.studentNo || ''}`.trim() },
        { label: '请假类型', value: this.leaveTypeLabel(x.leaveType) },
        { label: '起止时间', value: `${this.shortTime(x.startTime)} 至 ${this.shortTime(x.endTime)}` },
        { label: '学工状态', value: x.affairsStatus },
        { label: '旧状态映射', value: x.legacyStatus },
        { label: '请假原因', value: x.reason, span: 1 },
        { label: '工作流实例', value: x.workflowInstanceId || '未建流程' }
      ]
    },
    auditRecords() {
      if (!this.selected) return []
      return [
        {
          id: 'leave-flow',
          action: '请假流程状态',
          actor: '学工中心',
          target: this.selected.affairsStatus || this.selected.legacyStatus,
          reason: '记录来自后端请假详情，不在前端补写审计',
          result: '成功'
        }
      ]
    }
  },
  watch: {
    '$route.params.panel'() {
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
        const res = await studentAffairsApi.listPendingLeaves({ page: 1, pageSize: 50 })
        this.leaves = res.data.items || []
        this.total = res.data.total || this.leaves.length
        if (!this.selected && this.leaves.length) this.selected = this.leaves[0]
      } catch (e) {
        this.errorMessage = e.message || '请假数据加载失败'
      } finally {
        this.loading = false
      }
    },
    goPanel(panel) {
      const path = panel === 'approvals' ? '/admin/student-affairs/leave' : `/admin/student-affairs/leave/${panel}`
      this.$router.push(path)
    },
    async openDetail(id) {
      try {
        const res = await studentAffairsApi.getLeaveDetail(id)
        this.selected = res.data
      } catch (e) {
        this.errorMessage = e.message || '请假详情加载失败'
      }
    },
    async approve(id) {
      await this.runAction(() => studentAffairsApi.approveLeave(id, '同意'), id)
    },
    async returnBack(id) {
      const reason = window.prompt('请输入退回原因（至少 5 个字）', '材料不齐，请补充后重新提交')
      if (!reason) return
      await this.runAction(() => studentAffairsApi.returnLeave(id, reason), id)
    },
    async reject(id) {
      const reason = window.prompt('请输入驳回原因（至少 5 个字）', '不符合请假条件，予以驳回')
      if (!reason) return
      await this.runAction(() => studentAffairsApi.rejectLeave(id, reason), id)
    },
    async scanOverdue() {
      this.actioning = true
      try {
        const res = await studentAffairsApi.scanLeaveOverdue()
        this.scanResult = `本次扫描处理 ${res.data.count || 0} 条超期未销假记录`
        await this.load()
      } catch (e) {
        this.errorMessage = e.message || '超期扫描失败'
      } finally {
        this.actioning = false
      }
    },
    async runAction(fn, id) {
      this.actioning = true
      try {
        const res = await fn()
        this.selected = res.data
        await this.load()
        if (id) await this.openDetail(id)
      } catch (e) {
        this.errorMessage = e.message || '操作失败'
      } finally {
        this.actioning = false
      }
    },
    leaveTypeLabel(type) {
      return ({ SICK: '病假', PERSONAL: '事假', GOOUT: '外出' })[type] || type || '未设置'
    },
    leaveStatusKind(status) {
      if (['APPROVED', 'CLOSED'].includes(status)) return 'success'
      if (['OVERDUE', 'REJECTED'].includes(status)) return 'danger'
      if (['RETURNED', 'COLLEGE_REVIEW'].includes(status)) return 'warning'
      return 'info'
    },
    shortTime(value) {
      return value ? String(value).replace('T', ' ').slice(0, 16) : '-'
    }
  }
}
</script>

<style scoped>
.sa-tabs {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}
.sa-tabs button {
  border: 1px solid var(--border-base);
  background: var(--bg-surface);
  color: var(--text-secondary);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-4);
  cursor: pointer;
}
.sa-tabs button.active {
  border-color: var(--primary-500);
  color: var(--primary-700);
  background: var(--primary-50);
}
.sa-grid--metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.sa-layout {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
  gap: var(--space-4);
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
.sa-empty,
.sa-notice {
  color: var(--text-tertiary);
  padding: var(--space-4);
  text-align: center;
}
.sa-notice {
  text-align: left;
  border: 1px solid var(--warning-200);
  background: var(--warning-50);
  color: var(--warning-700);
  border-radius: var(--radius-base);
  margin-bottom: var(--space-3);
}
.sa-rules {
  display: grid;
  gap: var(--space-3);
}
.sa-rule {
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  padding: var(--space-4);
}
.sa-audit {
  margin-top: var(--space-4);
}
@media (max-width: 960px) {
  .sa-grid--metrics,
  .sa-layout {
    grid-template-columns: 1fr;
  }
}
</style>
