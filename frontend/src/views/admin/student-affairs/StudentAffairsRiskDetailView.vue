<template>
  <AppPageShell
    title="风险详情"
    subtitle="查看单条风险记录的学生、来源、脱敏状态和处置闭环动作。"
    role-name="SCHOOL_ADMIN / COUNSELOR"
    data-scope-name="学工数据范围"
    watermark-purpose="学工风险详情查看"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.risk.back" variant="secondary" @click="$router.push('/admin/student-affairs/risk')">
        返回列表
      </AppPermissionButton>
      <AppPermissionButton code="studentAffairs.risk.refresh" variant="secondary" @click="load">
        刷新
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载风险详情..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/risk')"
    >
      <div class="sa-detail-layout">
        <AppSectionCard title="风险档案">
          <div class="sa-heading">
            <div>
              <h2>{{ detail.title || '风险记录' }}</h2>
              <p>{{ detail.realName || '未命名学生' }} · {{ detail.studentNo || detail.studentId }}</p>
            </div>
            <AppRiskTag :level="detail.riskLevel" />
          </div>

          <AppDescriptionList :items="detailItems" :columns="2" bordered>
            <template #detail>
              <span v-if="detail.mentalMasked" class="sa-masked">心理关注明细已按角色脱敏</span>
              <AppSensitiveText v-else :value="detail.detail" />
            </template>
          </AppDescriptionList>
        </AppSectionCard>

        <AppSectionCard title="处置动作">
          <div class="sa-actions">
            <AppPermissionButton code="studentAffairs.risk.assign" variant="secondary" :loading="actioning" @click="assign">
              分派
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.process" :loading="actioning" @click="process">
              处置
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.follow" variant="secondary" :loading="actioning" @click="follow">
              持续跟进
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.transfer" variant="secondary" :loading="actioning" @click="transfer">
              转办
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.escalate" variant="secondary" :loading="actioning" @click="escalate">
              升级
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.takeover" variant="secondary" :loading="actioning" @click="takeover">
              接管
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.close" variant="secondary" :loading="actioning" @click="close">
              关闭
            </AppPermissionButton>
            <AppPermissionButton code="studentAffairs.risk.reopen" variant="secondary" :loading="actioning" @click="reopen">
              重开
            </AppPermissionButton>
          </div>
          <AppAuditTrail class="sa-audit" :records="auditRecords" compact :show-ip="false" />
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
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppSensitiveText
} from '@/components/common'
import { studentAffairsApi } from '@/modules/student-affairs/api/studentAffairs.api'

export default {
  name: 'StudentAffairsRiskDetailView',
  components: {
    AppAuditTrail,
    AppDescriptionList,
    AppGlobalState,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSectionCard,
    AppSensitiveText
  },
  data() {
    return {
      loading: true,
      actioning: false,
      errorMessage: '',
      detail: {}
    }
  },
  computed: {
    riskId() {
      return this.$route.params.riskId
    },
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    detailItems() {
      const x = this.detail
      return [
        { label: '学生', value: `${x.realName || ''} ${x.studentNo || ''}`.trim() },
        { label: '来源', value: this.sourceLabel(x.source) },
        { label: '来源编号', value: x.sourceRefId },
        { label: '风险等级', value: x.riskLevel },
        { label: '状态', value: x.statusLabel || x.status },
        { label: '责任人', value: x.ownerId || '待分派' },
        { key: 'detail', label: '风险明细', value: x.detail, span: 2 },
        { label: '归档状态', value: x.isArchived ? '已归档' : '未归档' },
        { label: '版本', value: x.version }
      ]
    },
    auditRecords() {
      return [
        {
          id: 'risk-current',
          action: '当前风险状态',
          actor: '学工中心',
          target: this.detail.statusLabel || this.detail.status,
          reason: '详情由后端风险接口返回，心理来源明细按角色脱敏',
          result: '成功'
        }
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
        const res = await studentAffairsApi.getRiskRecord(this.riskId)
        this.detail = res.data || {}
      } catch (e) {
        this.errorMessage = e.message || '风险详情加载失败'
      } finally {
        this.loading = false
      }
    },
    async assign() {
      const ownerId = window.prompt('请输入责任人 ID', this.detail.ownerId || '')
      if (!ownerId) return
      await this.runAction(() => studentAffairsApi.assignRisk(this.riskId, ownerId))
    },
    async process() {
      const content = window.prompt('请输入处置内容', '已联系学生并记录处置过程')
      if (!content) return
      await this.runAction(() => studentAffairsApi.processRisk(this.riskId, content))
    },
    async follow() {
      const content = window.prompt('请输入跟进说明', '转入持续跟进')
      if (content === null) return
      await this.runAction(() => studentAffairsApi.followRisk(this.riskId, content))
    },
    async transfer() {
      const newOwnerId = window.prompt('请输入新责任人 ID')
      if (!newOwnerId) return
      const reason = window.prompt('请输入转办原因', '职责调整，转交处理') || ''
      await this.runAction(() => studentAffairsApi.transferRisk(this.riskId, newOwnerId, reason))
    },
    async escalate() {
      const reason = window.prompt('请输入升级原因', '风险等级提升，需要上级关注')
      if (reason === null) return
      await this.runAction(() => studentAffairsApi.escalateRisk(this.riskId, reason))
    },
    async takeover() {
      const content = window.prompt('请输入接管说明', '上级接管处置')
      if (content === null) return
      await this.runAction(() => studentAffairsApi.takeoverRisk(this.riskId, content))
    },
    async close() {
      const conclusion = window.prompt('请输入关闭结论（至少 5 个字）', '学生情况稳定，风险解除')
      if (!conclusion) return
      await this.runAction(() => studentAffairsApi.closeRisk(this.riskId, conclusion))
    },
    async reopen() {
      const reason = window.prompt('请输入重开原因', '风险复发，需要重新跟进')
      if (reason === null) return
      await this.runAction(() => studentAffairsApi.reopenRisk(this.riskId, reason))
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
        DORM_ABNORMAL: '宿舍异常',
        MENTAL: '心理关注',
        MANUAL: '人工建单'
      })[source] || source || '未设置'
    }
  }
}
</script>

<style scoped>
.sa-detail-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.8fr);
  gap: var(--space-4);
}
.sa-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.sa-heading h2 {
  margin: 0 0 var(--space-1);
  font-size: var(--font-size-xl);
  letter-spacing: 0;
}
.sa-heading p {
  margin: 0;
  color: var(--text-tertiary);
}
.sa-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.sa-audit {
  margin-top: var(--space-4);
}
.sa-masked {
  color: var(--text-tertiary);
}
@media (max-width: 960px) {
  .sa-detail-layout {
    grid-template-columns: 1fr;
  }
}
</style>
