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
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">开题报告 · {{ detail.version }}</span>
            <StatusTag v-if="detail.isResubmit" type="info" label="重交件" />
          </div>
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">学生</span><span class="mp-kv__v">{{ detail.studentName }} · {{ detail.className }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">指导教师</span><span class="mp-kv__v">{{ detail.advisorName }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">提交时间</span><span class="mp-kv__v">{{ detail.submitAt }}（学生端 P15）</span></div>
            <div style="margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.8">
              <p style="margin: 0 0 var(--space-2)"><b style="color: var(--text-primary)">选题背景：</b>{{ detail.content.background }}</p>
              <p style="margin: 0 0 var(--space-2)"><b style="color: var(--text-primary)">研究方案与进度：</b>{{ detail.content.plan }}</p>
              <p style="margin: 0"><b style="color: var(--text-primary)">预期成果：</b>{{ detail.content.outcome }}</p>
            </div>
            <div v-if="detail.attachments.length" style="margin-top: var(--space-3); display: flex; gap: var(--space-2); flex-wrap: wrap">
              <StatusTag v-for="a in detail.attachments" :key="a" type="info" :label="'📎 ' + a" />
            </div>
          </div>
        </section>

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
                <AppButton variant="primary" :disabled="!canReview" :title="reviewReason" :loading="submitting" style="flex: 1" @click="submit('APPROVE')">✓ 通过</AppButton>
                <AppButton variant="warning" :disabled="!canReview" :title="reviewReason" :loading="submitting" style="flex: 1" @click="submit('REJECT')">↩ 驳回修改</AppButton>
              </div>
              <p class="mp-note" style="text-align: center; margin-top: var(--space-2)">批阅动作写入审批留痕，学生端即时同步状态</p>
            </template>
            <EmptyState v-else :title="'该开题报告' + (detail.status === 'APPROVED' ? '已通过' : '已驳回')" description="批阅结果已同步学生端，留痕见下方审批记录" />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">审批留痕</span></div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead><tr><th>操作人</th><th>时间</th><th>动作</th><th>说明</th></tr></thead>
              <tbody>
                <tr v-for="(t, i) in detail.trail" :key="i">
                  <td class="is-who">{{ t.who }}</td>
                  <td>{{ t.time }}</td>
                  <td>{{ t.action }}</td>
                  <td>{{ t.affected }}</td>
                </tr>
                <tr v-if="!detail.trail.length"><td colspan="4" class="mp-note">暂无批阅记录</td></tr>
              </tbody>
            </table>
          </div>
        </section>
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
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { toast } from '@/utils/toast'

export default {
  name: 'ProposalReviewDetailView',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppButton },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', detail: null, action: 'APPROVE', comment: '', formError: '', submitting: false }
  },
  computed: {
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
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
