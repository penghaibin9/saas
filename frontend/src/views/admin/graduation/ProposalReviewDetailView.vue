<template>
  <ModulePageShell
    :title="detail ? detail.studentName + ' · 开题批阅' : '开题批阅'"
    :subtitle="detail ? detail.topicTitle : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
      <div class="mp-stack">
        <AppSectionCard :title="'开题报告 · ' + detail.version">
          <template #header-extra>
            <StatusTag v-if="detail.isResubmit" type="info" label="重交件" />
          </template>
          <AppDescriptionList :items="proposalMetaItems" :columns="1" />
            <div style="margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.8">
              <p style="margin: 0 0 var(--space-2)"><b style="color: var(--text-primary)">选题背景：</b>{{ detail.content.background }}</p>
              <p style="margin: 0 0 var(--space-2)"><b style="color: var(--text-primary)">研究方案与进度：</b>{{ detail.content.plan }}</p>
              <p style="margin: 0"><b style="color: var(--text-primary)">预期成果：</b>{{ detail.content.outcome }}</p>
            </div>
            <div v-if="detail.attachments.length" style="margin-top: var(--space-3)">
              <p class="mp-note" style="margin-bottom: var(--space-2)">附件材料</p>
              <AppFileList :files="attachmentFiles" :previewable="false" :downloadable="false" :removable="false" />
            </div>
        </AppSectionCard>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">历史版本</span></div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="(v, i) in detail.versions" :key="i" class="mp-timeline__item" :class="'is-' + (v.tone === 'processing' ? 'warning' : v.tone)">
                <div class="mp-timeline__title">{{ v.title }}</div>
                <div v-if="v.desc" class="mp-timeline__desc">{{ v.desc }}</div>
                <div class="mp-timeline__time">{{ v.time }}</div>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">批阅</span></div>
          <div class="mp-card__body">
            <template v-if="detail.status === 'PENDING_REVIEW'">
              <div v-if="!canReview" class="mp-note" style="margin-bottom: var(--space-3); color: var(--warning-600)">
                {{ reviewReason }}（以下操作已置灰，仅指导教师可批阅）
              </div>
              <div class="mp-radio" :class="{ 'is-active': action === 'APPROVE' }" @click="canReview && (action = 'APPROVE')">
                <input type="radio" :checked="action === 'APPROVE'" :disabled="!canReview" style="margin-top: 3px" />
                <div>
                  <div class="mp-radio__title">通过</div>
                  <div class="mp-radio__desc">进入指导中阶段，可附批注意见</div>
                </div>
              </div>
              <div class="mp-radio" :class="{ 'is-active': action === 'REJECT' }" @click="canReview && (action = 'REJECT')">
                <input type="radio" :checked="action === 'REJECT'" :disabled="!canReview" style="margin-top: 3px" />
                <div>
                  <div class="mp-radio__title">驳回修改</div>
                  <div class="mp-radio__desc">驳回原因必填（≥5 字），学生端收到不可关闭的退回提醒</div>
                </div>
              </div>
              <label class="mp-note" style="display: block; margin: var(--space-3) 0 var(--space-1)">
                {{ action === 'REJECT' ? '驳回原因（必填，≥5 字）' : '批注意见（选填）' }}
              </label>
              <textarea v-model="comment" class="mp-textarea" :disabled="!canReview" placeholder="批注将随批阅结果同步学生端…"></textarea>
              <p v-if="formError" class="mp-form-err">{{ formError }}</p>
              <div style="display: flex; gap: var(--space-2); margin-top: var(--space-3)">
                <AppPermissionButton
                  :allowed="canReview"
                  :reason="reviewReason"
                  variant="primary"
                  :loading="submitting"
                  style="flex: 1"
                  @click="submit('APPROVE')"
                >✓ 通过</AppPermissionButton>
                <AppPermissionButton
                  :allowed="canReview"
                  :reason="reviewReason"
                  variant="warning"
                  :loading="submitting"
                  style="flex: 1"
                  @click="submit('REJECT')"
                >↩ 驳回修改</AppPermissionButton>
              </div>
              <p class="mp-note" style="text-align: center; margin-top: var(--space-2)">批阅动作写入审批留痕，学生端即时同步状态</p>
            </template>
            <template v-else-if="detail.status === 'APPROVED'">
              <div class="mp-kv"><span class="mp-kv__k">书面开题</span><span class="mp-kv__v">已通过</span></div>
              <div v-if="detail.defenseResult" class="mp-kv"><span class="mp-kv__k">开题答辩</span>
                <span class="mp-kv__v">{{ detail.defenseResult === 'PASS' ? '现场答辩通过' : '现场答辩不通过' }}{{ detail.defenseComment ? '：' + detail.defenseComment : '' }}</span>
              </div>
              <template v-else>
                <label class="mp-note" style="display:block;margin:var(--space-3) 0 var(--space-1)">开题答辩评语（不通过时必填≥5字）</label>
                <textarea v-model="defenseComment" class="mp-textarea" placeholder="现场开题答辩评语…"></textarea>
                <div style="display:flex;gap:var(--space-2);margin-top:var(--space-3)">
                  <AppButton variant="primary" :loading="submitting" style="flex:1" @click="submitDefense('PASS')">✓ 答辩通过</AppButton>
                  <AppButton variant="warning" :loading="submitting" style="flex:1" @click="submitDefense('FAIL')">✕ 答辩不通过</AppButton>
                </div>
                <p class="mp-note" style="text-align:center;margin-top:var(--space-2)">开题答辩为现场环节，区别于上方书面审核</p>
              </template>
            </template>
            <EmptyState v-else :title="'该开题报告已驳回'" description="批阅结果已同步学生端，留痕见下方审批记录" />
          </div>
        </section>

        <AppSectionCard title="审批留痕">
          <AppAuditTrail :records="trailRecords" empty-text="暂无批阅记录" compact :show-ip="false" />
        </AppSectionCard>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 开题批阅详情（/admin/graduation/proposals/:id）。
 * 闭环：查看材料/附件/历史版本 → 通过 / 驳回（原因必填）→ 留痕 → 学生端补交。
 * 权限：批阅按钮按 permissionActions.reviewProposal 控制（管理员视角置灰并提示原因）。
 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppPermissionButton, AppAuditTrail, AppFileList, AppSectionCard, AppDescriptionList } from '@/components/common'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { toast } from '@/utils/toast'

export default {
  name: 'ProposalReviewDetailView',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppPermissionButton, AppAuditTrail, AppFileList, AppSectionCard, AppDescriptionList },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', detail: null, action: 'APPROVE', comment: '', formError: '', submitting: false, defenseComment: '' }
  },
  computed: {
    proposalMetaItems() {
      if (!this.detail) return []
      return [
        { label: '学生', value: `${this.detail.studentName} · ${this.detail.className}` },
        { label: '指导教师', value: this.detail.advisorName },
        { label: '提交时间', value: `${this.detail.submitAt}（学生端 P15）` }
      ]
    },
    attachmentFiles() {
      return (this.detail?.attachments || []).map((name, i) => ({ id: i, name }))
    },
    trailRecords() {
      return (this.detail?.trail || []).map((t, i) => ({
        id: i,
        action: t.action,
        actor: t.who,
        at: t.time,
        target: t.affected
      }))
    },
    canReview() {
      const pa = this.ctx.permissionActions.reviewProposal
      return !!(pa && pa.visible && pa.allowed)
    },
    reviewReason() {
      const pa = this.ctx.permissionActions.reviewProposal
      return pa && !pa.allowed ? pa.reason : ''
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getProposalReviewDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    },
    async submit(action) {
      if (!this.canReview) return
      this.action = action
      this.formError = ''
      if (action === 'REJECT' && (!this.comment || this.comment.trim().length < 5)) {
        this.formError = '驳回原因必填且不少于 5 个字'
        return
      }
      this.submitting = true
      const res = await graduationApi.reviewProposal(this.detail.id, { action, comment: this.comment })
      this.submitting = false
      if (res.code === 0) {
        toast.success('批阅完成：' + res.data.statusLabel + '，已留痕并同步学生端')
        this.comment = ''
        this.load()
      } else {
        this.formError = res.message
      }
    },
    async submitDefense(result) {
      if (result === 'FAIL' && (!this.defenseComment || this.defenseComment.trim().length < 5)) {
        toast.error('开题答辩不通过时评语必填且不少于 5 字'); return
      }
      this.submitting = true
      const res = await graduationMoreApi.holdProposalDefense(this.detail.id, result, this.defenseComment)
      this.submitting = false
      if (res.code === 0) { toast.success('开题答辩已录入'); this.defenseComment = ''; this.load() }
      else toast.error(res.message || '录入失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
