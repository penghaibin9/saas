<template>
  <AppPageShell
    title="谈话转介与回访"
    subtitle="转介 → 回访 → 关闭 的持续跟进工作台；聚焦待回访(已转介/回访中)记录，明细遮蔽、查看留痕。"
    role-name="心理老师 / 授权辅导员"
    data-scope-name="PSY_STUDENT 逐生授权范围"
    watermark-purpose="心理转介回访处理"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.risk.psyDetail.view" :loading="actioning" @click="createReferral">
        登记转介
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载转介回访工作台..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard title="待回访转介（已转介 / 回访中）">
        <table class="sa-table">
          <thead>
            <tr>
              <th>学生</th>
              <th>关注等级</th>
              <th>状态</th>
              <th>事由摘要</th>
              <th>转介去向</th>
              <th>最近回访</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in openItems" :key="row.referralId">
              <td>
                <strong>{{ row.realName || '未命名学生' }}</strong>
                <small>{{ row.studentNo || row.studentId }}</small>
              </td>
              <td><AppStatusTag :type="levelKind(row.level)" :label="row.levelLabel || row.level" /></td>
              <td><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></td>
              <td>{{ row.reasonSummary || '—' }}</td>
              <td>{{ row.channel || '—' }}</td>
              <td>{{ (row.lastFollowTime || '').slice(0, 16) || '尚未回访' }}</td>
              <td class="sa-actions">
                <AppPermissionButton code="studentAffairs.risk.psyDetail.view" size="sm" @click="follow(row)">
                  回访
                </AppPermissionButton>
                <AppPermissionButton code="studentAffairs.risk.psyDetail.view" size="sm" variant="secondary" @click="close(row)">
                  关闭
                </AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!openItems.length">
              <td colspan="7" class="sa-empty">暂无待回访转介</td>
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
import { studentAffairsApi } from '@/modules/student-affairs/api/studentAffairs.api'

export default {
  name: 'MentalReferralFollowView',
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
    openItems() {
      return this.items.filter((r) => r.status === 'REFERRED' || r.status === 'FOLLOWING')
    },
    metricCards() {
      const referred = this.items.filter((r) => r.status === 'REFERRED').length
      const following = this.items.filter((r) => r.status === 'FOLLOWING').length
      const neverFollowed = this.openItems.filter((r) => !r.lastFollowTime).length
      return [
        { key: 'open', label: '待回访', value: this.openItems.length, accent: this.openItems.length ? 'warning' : 'success' },
        { key: 'referred', label: '已转介待跟进', value: referred, accent: 'info' },
        { key: 'following', label: '回访中', value: following, accent: 'primary' },
        { key: 'never', label: '尚未回访', value: neverFollowed, accent: neverFollowed ? 'risk' : 'success' }
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
        this.errorMessage = e.message || '转介回访工作台加载失败'
      } finally {
        this.loading = false
      }
    },
    async createReferral() {
      const studentId = window.prompt('请输入学生 ID')
      if (!studentId) return
      const reasonSummary = window.prompt('请输入转介事由摘要（人工填写，非诊断，不少于 5 字）', '')
      if (!reasonSummary || reasonSummary.trim().length < 5) {
        if (reasonSummary !== null) window.alert('事由摘要不少于 5 字')
        return
      }
      const channel = window.prompt('转介去向（校医院/专业机构/家长/校内咨询，可空）', '校内咨询') || ''
      await this.runAction(() => studentAffairsApi.createMentalReferral({
        studentId, level: 'FOCUS', channel, reasonSummary: reasonSummary.trim()
      }))
    },
    async follow(row) {
      const content = window.prompt('请输入本次回访记录（不少于 5 字）', '')
      if (!content || content.trim().length < 5) {
        if (content !== null) window.alert('回访记录不少于 5 字')
        return
      }
      await this.runAction(() => studentAffairsApi.followMentalReferral(row.referralId, content.trim()))
    },
    async close(row) {
      const conclusion = window.prompt('请输入关闭结论（不少于 5 字）', '')
      if (!conclusion || conclusion.trim().length < 5) {
        if (conclusion !== null) window.alert('结论不少于 5 字')
        return
      }
      await this.runAction(() => studentAffairsApi.closeMentalReferral(row.referralId, conclusion.trim()))
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
@media (max-width: 960px) {
  .sa-grid--metrics {
    grid-template-columns: 1fr;
  }
}
</style>
