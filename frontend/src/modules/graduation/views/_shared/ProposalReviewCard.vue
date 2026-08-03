<template>
  <div class="prc">
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="detail" class="mp-stack">
      <AppSectionCard :title="'开题报告 · ' + detail.version">
        <template #header-extra>
          <StatusTag :status="detail.status" :label="detail.statusLabel" dot />
          <StatusTag v-if="detail.isResubmit" type="info" label="重交件" style="margin-left: var(--space-1)" />
        </template>
        <AppDescriptionList :items="proposalMetaItems" :columns="compact ? 1 : 2" />
        <div class="prc-content">
          <p><b>选题背景：</b>{{ detail.content.background || '—' }}</p>
          <p><b>研究方案与进度：</b>{{ detail.content.plan || '—' }}</p>
          <p style="margin-bottom: 0"><b>预期成果：</b>{{ detail.content.outcome || '—' }}</p>
        </div>
        <div v-if="detail.attachments.length" style="margin-top: var(--space-3)">
          <p class="mp-note" style="margin-bottom: var(--space-2)">旧接口附件引用（仅兼容展示）</p>
          <AppFileList :files="attachmentFiles" :previewable="false" :downloadable="false" :removable="false" />
        </div>
      </AppSectionCard>

      <AppSectionCard title="当前安全版本（本次审核锁定）">
        <template #header-extra>
          <StatusTag
            :type="detail.reviewReady ? 'success' : 'warning'"
            :label="detail.reviewReady ? `安全门通过 · ${secureVersionFiles.length} 个版本` : '暂不可审核'"
          />
        </template>
        <div v-if="detail.migrationRequired" class="version-warning">
          该历史记录尚未完成公共版本回填。系统会在正式审核动作前执行安全回填；回填失败时禁止通过。
        </div>
        <div v-else-if="!detail.reviewReady" class="version-warning">
          当前版本仍在扫描、扫描失败或版本关系已变化。请刷新后确认，系统不会绕过安全门审核。
        </div>
        <SecureFileList
          :items="secureVersionFiles"
          :loading="loading"
          empty-text="尚无可审核的安全文件版本"
          @preview="previewVersion"
          @download="downloadVersion"
          @refresh="load"
        />
        <div v-if="secureVersionFiles.length" class="version-table-wrap">
          <table class="version-table">
            <thead>
              <tr><th>材料</th><th>版本</th><th>versionId</th><th>扫描</th><th>审核态</th><th>SHA-256</th></tr>
            </thead>
            <tbody>
              <tr v-for="item in secureVersionFiles" :key="item.versionId">
                <td>{{ item.materialName || item.fileName }}</td>
                <td>v{{ item.versionNo }}</td>
                <td class="mono">{{ item.versionId }}</td>
                <td>{{ item.scanStatus }}</td>
                <td>{{ item.versionStatus }}</td>
                <td class="mono hash" :title="item.sha256">{{ shortHash(item.sha256) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="mp-note" style="margin-top: var(--space-2)">
          教师通过或驳回时，后端会再次锁定这些 versionId 并核验 FileObject、扫描结论和 SHA-256。
        </p>
      </AppSectionCard>

      <section class="mp-card">
        <div class="mp-card__head"><span class="mp-card__title">批阅</span></div>
        <div class="mp-card__body">
          <template v-if="detail.status === 'PENDING_REVIEW'">
            <div v-if="!canReview" class="mp-note" style="margin-bottom: var(--space-2); color: var(--warning-600)">
              {{ reviewReason }}（以下操作已置灰）
            </div>
            <label class="mp-note" style="display: block; margin-bottom: var(--space-1)">批阅意见（驳回时必填，≥5 字）</label>
            <textarea v-model="comment" class="mp-textarea" :disabled="!canReview" rows="3" placeholder="批注将随批阅结果同步学生端…"></textarea>
            <AppTemplateChips v-if="canReview" :options="REJECT_REASON_CHIPS" @pick="(t) => (comment = comment ? comment + '\n' + t : t)" />
            <p v-if="formError" class="mp-form-err">{{ formError }}</p>
            <div style="display: flex; gap: var(--space-2); margin-top: var(--space-3)">
              <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="primary" :loading="submitting" style="flex: 1" @click="submit('APPROVE')">✓ 通过当前版本</AppPermissionButton>
              <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="warning" :loading="submitting" style="flex: 1" @click="submit('REJECT')">↩ 驳回当前版本</AppPermissionButton>
            </div>
            <p class="mp-note" style="text-align: center; margin-top: var(--space-2)">批阅结果写入业务留痕与公共文件版本状态，学生端即时同步</p>
          </template>
          <template v-else-if="detail.status === 'APPROVED'">
            <div class="mp-kv"><span class="mp-kv__k">书面开题</span><span class="mp-kv__v">已通过</span></div>
            <div v-if="detail.reviewComment" class="mp-kv"><span class="mp-kv__k">批注意见</span><span class="mp-kv__v">{{ detail.reviewComment }}</span></div>
            <div v-if="detail.defenseResult" class="mp-kv"><span class="mp-kv__k">开题答辩</span>
              <span class="mp-kv__v">{{ detail.defenseResult === 'PASS' ? '现场答辩通过' : '现场答辩不通过' }}{{ detail.defenseComment ? '：' + detail.defenseComment : '' }}</span>
            </div>
            <template v-else>
              <label class="mp-note" style="display: block; margin: var(--space-3) 0 var(--space-1)">开题答辩评语（不通过时必填 ≥5 字）</label>
              <textarea v-model="defenseComment" class="mp-textarea" rows="2" placeholder="现场开题答辩评语…"></textarea>
              <AppTemplateChips :options="DEFENSE_COMMENT_CHIPS" @pick="(t) => (defenseComment = defenseComment ? defenseComment + '\n' + t : t)" />
              <div style="display: flex; gap: var(--space-2); margin-top: var(--space-3)">
                <AppButton variant="primary" :loading="submitting" style="flex: 1" @click="submitDefense('PASS')">✓ 答辩通过</AppButton>
                <AppButton variant="warning" :loading="submitting" style="flex: 1" @click="submitDefense('FAIL')">✕ 答辩不通过</AppButton>
              </div>
              <p class="mp-note" style="text-align: center; margin-top: var(--space-2)">开题答辩为现场环节，区别于上方书面审核</p>
            </template>
          </template>
          <template v-else>
            <div class="mp-kv"><span class="mp-kv__k">批阅结果</span><span class="mp-kv__v">已驳回修改</span></div>
            <div v-if="detail.reviewComment" class="mp-kv"><span class="mp-kv__k">驳回原因</span><span class="mp-kv__v">{{ detail.reviewComment }}</span></div>
            <p class="mp-note" style="margin-top: var(--space-2)">学生重交后将生成新的 FileVersion，旧版本继续保留追溯</p>
          </template>
        </div>
      </section>

      <div class="mp-grid-2 prc-bottom" :class="{ 'is-compact': compact }">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">业务历史版本</span></div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="(v, i) in detail.versions" :key="i" class="mp-timeline__item" :class="'is-' + (v.tone === 'processing' ? 'warning' : v.tone)">
                <div class="mp-timeline__title">{{ v.title }}</div>
                <div v-if="v.desc" class="mp-timeline__desc">{{ v.desc }}</div>
                <div class="mp-timeline__time">{{ fmtTime(v.time) }}</div>
              </li>
            </ul>
          </div>
        </section>
        <AppSectionCard title="审批留痕">
          <AppAuditTrail :records="trailRecords" empty-text="暂无批阅记录" compact :show-ip="false" />
        </AppSectionCard>
      </div>
    </div>
  </div>
</template>

<script>
/** ProposalReviewCard — 开题批阅卡。审核动作锁定公共 FileVersion。 */
import { StatusTag, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppPermissionButton, AppAuditTrail, AppFileList, AppSectionCard, AppDescriptionList, AppTemplateChips } from '@/components/common'
import SecureFileList from '@/components/file/SecureFileList.vue'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { graduationMaterialCenterApi } from '@/modules/graduation/api/graduation-material-center.api'
import { toast } from '@/utils/toast'
import { formatDateTime } from '@/utils/dateUtils'

const REJECT_REASON_CHIPS = ['材料不完整，请补充', '内容质量不达标，需修改', '格式不符合学校规范', '与选题方向不符']
const DEFENSE_COMMENT_CHIPS = ['选题有实际意义，完成度高', '回答问题思路清晰', '论文结构完整，工作量饱满', '部分问题回答不够深入']

export default {
  name: 'ProposalReviewCard',
  components: { StatusTag, LoadingState, ErrorState, AppButton, AppPermissionButton, AppAuditTrail, AppFileList, AppSectionCard, AppDescriptionList, AppTemplateChips, SecureFileList },
  props: {
    ctx: { type: Object, required: true },
    proposalId: { type: [String, Number], required: true },
    compact: { type: Boolean, default: false }
  },
  emits: ['reviewed', 'conflict'],
  data() {
    return {
      REJECT_REASON_CHIPS, DEFENSE_COMMENT_CHIPS,
      loading: true, error: '', detail: null, comment: '', formError: '', submitting: false, defenseComment: ''
    }
  },
  computed: {
    proposalMetaItems() {
      if (!this.detail) return []
      const cls = this.detail.className ? ' · ' + this.detail.className : ''
      return [
        { label: '学生', value: `${this.detail.studentName}${cls}` },
        { label: '课题', value: this.detail.topicTitle || '—' },
        { label: '指导教师', value: this.detail.advisorName || '—' },
        { label: '提交时间', value: this.fmtTime(this.detail.submitAt) || '—' }
      ]
    },
    attachmentFiles() {
      return (this.detail?.attachments || []).map((name, i) => ({ id: i, name }))
    },
    secureVersionFiles() {
      return graduationMaterialCenterApi.normalizeVersions(this.detail?.currentSafeVersions || [])
    },
    trailRecords() {
      return (this.detail?.trail || []).map((t, i) => ({ id: i, action: t.action, actor: t.who, at: this.fmtTime(t.time), target: t.affected }))
    },
    canReview() {
      const pa = this.ctx.permissionActions.reviewProposal
      return !!(pa && pa.visible && pa.allowed && this.detail?.reviewReady)
    },
    reviewReason() {
      if (this.detail && !this.detail.reviewReady) {
        return this.detail.migrationRequired ? '历史材料尚未完成公共版本回填' : '当前材料版本未通过安全门禁'
      }
      const pa = this.ctx.permissionActions.reviewProposal
      return pa && !pa.allowed ? pa.reason : ''
    }
  },
  watch: {
    proposalId: { immediate: true, handler() { this.load() } }
  },
  methods: {
    fmtTime(s) { return formatDateTime(s, '') },
    shortHash(value) {
      const text = String(value || '')
      return text.length > 16 ? `${text.slice(0, 8)}…${text.slice(-8)}` : (text || '—')
    },
    async load() {
      this.loading = true
      this.error = ''
      this.formError = ''
      this.comment = ''
      this.defenseComment = ''
      const res = await graduationApi.getProposalReviewDetail(this.proposalId)
      if (res.code === 0) this.detail = res.data
      else this.error = res.message
      this.loading = false
    },
    async previewVersion(item) {
      try { await graduationMaterialCenterApi.previewMaterial(item) } catch (error) { toast.error(error?.message || '预览失败') }
    },
    async downloadVersion(item) {
      try { await graduationMaterialCenterApi.downloadMaterial(item) } catch (error) { toast.error(error?.message || '下载失败') }
    },
    async submit(action) {
      if (!this.canReview) return
      this.formError = ''
      if (action === 'REJECT' && (!this.comment || this.comment.trim().length < 5)) {
        this.formError = '驳回原因必填且不少于 5 个字'
        return
      }
      this.submitting = true
      const res = await graduationApi.reviewProposal(this.detail.id, {
        action,
        comment: this.comment,
        expectedVersion: this.detail.materialVersion,
        fileVersionId: this.detail.fileVersionId
      })
      this.submitting = false
      if (res.code === 0) {
        toast.success('批阅完成：' + res.data.statusLabel + '，已锁定版本并同步学生端')
        this.comment = ''
        this.$emit('reviewed', res.data)
        this.load()
      } else if (res.message && (res.message.includes('已批阅') || res.message.includes('已被处理'))) {
        this.formError = res.message
        this.$emit('conflict')
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
.prc-content { margin-top: var(--space-3); font-size: var(--font-size-sm); color: var(--text-secondary); line-height: 1.8; }
.prc-content p { margin: 0 0 var(--space-2); }
.prc-content b { color: var(--text-primary); }
.prc-bottom.is-compact { grid-template-columns: 1fr; }
.version-warning { margin-bottom: var(--space-3); padding: 10px 12px; border-radius: 8px; background: var(--warning-50); color: var(--warning-700); font-size: 13px; }
.version-table-wrap { margin-top: var(--space-3); overflow-x: auto; }
.version-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.version-table th, .version-table td { padding: 9px 10px; border-bottom: 1px solid var(--border-light); text-align: left; white-space: nowrap; }
.version-table th { color: var(--text-tertiary); font-weight: 600; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.hash { max-width: 180px; overflow: hidden; text-overflow: ellipsis; }
</style>
