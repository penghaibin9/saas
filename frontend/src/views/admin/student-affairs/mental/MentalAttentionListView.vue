<template>
  <AppPageShell
    title="心理关注名单"
    subtitle="强敏感红线：列表仅显示摘要与「需关注」标记；心理明细须授权角色 + 填写原因方可查看，且全程留痕。"
    role-name="心理老师 / 授权辅导员 / 学工处(专项授权)"
    data-scope-name="PSY_STUDENT 逐生授权范围"
    watermark-purpose="心理关注名单查看"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.risk.psyDetail.view" :loading="actioning" @click="createReferral">
        登记转介
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载心理关注名单..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <AppSectionCard title="关注名单（明细遮蔽）">
        <div class="sa-toolbar">
          <select v-model="filters.level" @change="load">
            <option value="">全部等级</option>
            <option value="GENERAL">一般关注</option>
            <option value="FOCUS">重点关注</option>
            <option value="CRISIS">危机</option>
          </select>
          <span class="sa-hint">共 {{ total }} 条 · 明细默认脱敏</span>
        </div>

        <table class="sa-table">
          <thead>
            <tr>
              <th>学生</th>
              <th>关注等级</th>
              <th>状态</th>
              <th>事由摘要</th>
              <th>转介去向</th>
              <th>最近回访</th>
              <th>心理明细</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in items" :key="row.referralId">
              <td>
                <strong>{{ row.realName || '未命名学生' }}</strong>
                <small>{{ row.studentNo || row.studentId }}</small>
              </td>
              <td><AppStatusTag :type="levelKind(row.level)" :label="row.levelLabel || row.level" /></td>
              <td><AppStatusTag :type="statusKind(row.status)" :label="row.statusLabel || row.status" /></td>
              <td>{{ row.reasonSummary || '—' }}</td>
              <td>{{ row.channel || '—' }}</td>
              <td>{{ (row.lastFollowTime || '').slice(0, 16) || '—' }}</td>
              <td>
                <span :class="{ 'sa-mask': row.noteMasked }">{{ row.note }}</span>
              </td>
              <td class="sa-actions">
                <AppPermissionButton code="studentAffairs.risk.psyDetail.view" size="sm" variant="secondary" :loading="actioning" @click="reveal(row)">
                  查看明细
                </AppPermissionButton>
                <AppPermissionButton v-if="row.status !== 'CLOSED'" code="studentAffairs.risk.psyDetail.view" size="sm" variant="secondary" :loading="actioning" @click="follow(row)">
                  回访
                </AppPermissionButton>
                <AppPermissionButton v-if="row.status !== 'CLOSED'" code="studentAffairs.risk.psyDetail.view" size="sm" :loading="actioning" @click="close(row)">
                  关闭
                </AppPermissionButton>
              </td>
            </tr>
            <tr v-if="!items.length">
              <td colspan="8" class="sa-empty">当前授权范围内暂无心理关注记录</td>
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
  name: 'MentalAttentionListView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag },
  data() {
    return { loading: true, actioning: false, errorMessage: '', items: [], total: 0, filters: { level: '' } }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    metricCards() {
      const crisis = this.items.filter((r) => r.level === 'CRISIS' && r.status !== 'CLOSED').length
      const following = this.items.filter((r) => r.status === 'FOLLOWING').length
      const closed = this.items.filter((r) => r.status === 'CLOSED').length
      return [
        { key: 'total', label: '关注记录', value: this.total, accent: 'primary' },
        { key: 'crisis', label: '在册危机', value: crisis, accent: crisis ? 'risk' : 'success' },
        { key: 'following', label: '回访中', value: following, accent: following ? 'warning' : 'info' },
        { key: 'closed', label: '已结案', value: closed, accent: 'success' }
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
        const res = await studentAffairsApi.listMentalAttention({ level: this.filters.level, page: 1, pageSize: 50 })
        this.items = res.data.items || []
        this.total = res.data.total || this.items.length
      } catch (e) {
        this.errorMessage = e.message || '心理关注名单加载失败'
      } finally {
        this.loading = false
      }
    },
    async reveal(row) {
      const reason = window.prompt('查看心理明细为敏感操作，请填写查看原因（不少于 5 字，将写入安全审计）：', '')
      if (!reason) return
      if (reason.trim().length < 5) {
        window.alert('原因不少于 5 字')
        return
      }
      this.actioning = true
      try {
        const res = await studentAffairsApi.getMentalReferral(row.referralId, reason.trim())
        if (res.data.noteMasked) {
          window.alert('您在该生的心理明细无查看授权（需 PSY_STUDENT 专项授权），仅可见摘要。')
        } else {
          row.note = res.data.note
          row.noteMasked = false
          window.alert('已记录查看原因并写入安全审计（SENSITIVE_VIEW）。')
        }
      } catch (e) {
        this.errorMessage = e.message || '查看明细失败'
      } finally {
        this.actioning = false
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
      const level = window.prompt('关注等级 GENERAL/FOCUS/CRISIS', 'FOCUS') || 'FOCUS'
      const channel = window.prompt('转介去向（校医院/专业机构/家长/校内咨询，可空）', '校内咨询') || ''
      await this.runAction(() => studentAffairsApi.createMentalReferral({
        studentId, level: level.trim().toUpperCase(), channel, reasonSummary: reasonSummary.trim()
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
.sa-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
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
.sa-hint {
  color: var(--text-tertiary);
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
.sa-mask {
  color: var(--text-tertiary);
  font-style: italic;
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
