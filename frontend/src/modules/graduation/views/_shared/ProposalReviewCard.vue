<template>
  <div class="prc">
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <template v-else-if="detail">
      <p v-if="formError" class="mp-form-err prc-conflict">{{ formError }}</p>
      <GraduationDocumentReviewWorkspace
        :queue="[detail]" :current-index="0" :current-record="detail" :detail="detail"
        :files="secureVersionFiles" :versions="secureVersionFiles" :canonical-file-version-id="canonicalFileVersionId"
        :review-ready="Boolean(detail.reviewReady) && !versionConflict" :expected-version="detail.materialVersion"
        :comment="comment" :submitting="submitting" :auto-next="false" mode="proposal"
        :provider="previewProvider" :descriptor="previewDescriptor" :active-file-key="activePreviewFileKey"
        :active-version-id="activePreviewVersionId" :version-conflict="versionConflict"
        :allow-download="Boolean(activePreviewFile?.canDownload)" :narrow="compact"
        @select-file="selectPreviewFile" @select-version="selectPreviewVersion" @download="downloadActivePreview" @reload="load({ preserveDraft: true })"
      >
        <template #review>
          <div class="prc-content">
            <p><b>选题背景：</b>{{ detail.content?.background || '—' }}</p>
            <p><b>研究方案与进度：</b>{{ detail.content?.plan || '—' }}</p>
            <p><b>预期成果：</b>{{ detail.content?.outcome || '—' }}</p>
          </div>

          <template v-if="detail.status === 'PENDING_REVIEW'">
            <div v-if="!canReview" class="prc-blocked">{{ reviewReason }}（以下操作已置灰）</div>
            <label class="mp-note">批阅意见（驳回时必填，≥5 字）</label>
            <textarea v-model="comment" class="mp-textarea" rows="5" placeholder="批注将随批阅结果同步学生端…" @input="saveDraft"></textarea>
            <AppTemplateChips v-if="canReview" :options="REJECT_REASON_CHIPS" @pick="appendComment" />
            <div class="prc-actions">
              <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="primary" :loading="submitting" @click="submit('APPROVE')">✓ 通过当前版本</AppPermissionButton>
              <AppPermissionButton :allowed="canReview" :reason="reviewReason" variant="warning" :loading="submitting" @click="submit('REJECT')">↩ 驳回当前版本</AppPermissionButton>
            </div>
          </template>

          <template v-else-if="detail.status === 'APPROVED'">
            <div class="mp-kv"><span class="mp-kv__k">书面开题</span><span class="mp-kv__v">已通过</span></div>
            <div v-if="detail.reviewComment" class="mp-kv"><span class="mp-kv__k">批注意见</span><span class="mp-kv__v">{{ detail.reviewComment }}</span></div>
            <div v-if="detail.defenseResult" class="mp-kv"><span class="mp-kv__k">开题答辩</span><span class="mp-kv__v">{{ detail.defenseResult === 'PASS' ? '现场答辩通过' : '现场答辩不通过' }}{{ detail.defenseComment ? '：' + detail.defenseComment : '' }}</span></div>
            <template v-else>
              <label class="mp-note">开题答辩评语（不通过时必填 ≥5 字）</label>
              <textarea v-model="defenseComment" class="mp-textarea" rows="3" placeholder="现场开题答辩评语…"></textarea>
              <AppTemplateChips :options="DEFENSE_COMMENT_CHIPS" @pick="appendDefense" />
              <div class="prc-actions">
                <AppButton variant="primary" :loading="submitting" @click="submitDefense('PASS')">✓ 答辩通过</AppButton>
                <AppButton variant="warning" :loading="submitting" @click="submitDefense('FAIL')">✕ 答辩不通过</AppButton>
              </div>
            </template>
          </template>

          <template v-else>
            <div class="mp-kv"><span class="mp-kv__k">批阅结果</span><span class="mp-kv__v">已驳回修改</span></div>
            <div v-if="detail.reviewComment" class="mp-kv"><span class="mp-kv__k">驳回原因</span><span class="mp-kv__v">{{ detail.reviewComment }}</span></div>
          </template>
        </template>
      </GraduationDocumentReviewWorkspace>

      <div class="mp-grid-2 prc-bottom" :class="{ 'is-compact': compact }">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">业务历史版本</span></div>
          <div class="mp-card__body">
            <ul class="mp-timeline">
              <li v-for="(v, i) in detail.versions" :key="i" class="mp-timeline__item" :class="'is-' + (v.tone === 'processing' ? 'warning' : v.tone)">
                <div class="mp-timeline__title">{{ v.title }}</div><div v-if="v.desc" class="mp-timeline__desc">{{ v.desc }}</div><div class="mp-timeline__time">{{ fmtTime(v.time) }}</div>
              </li>
            </ul>
          </div>
        </section>
        <AppSectionCard title="审批留痕"><AppAuditTrail :records="trailRecords" empty-text="暂无批阅记录" compact :show-ip="false" /></AppSectionCard>
      </div>
    </template>
  </div>
</template>

<script>
import { LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppPermissionButton, AppAuditTrail, AppSectionCard, AppTemplateChips } from '@/components/common'
import GraduationDocumentReviewWorkspace from '@/modules/graduation/components/GraduationDocumentReviewWorkspace.vue'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { graduationMaterialCenterApi } from '@/modules/graduation/api/graduation-material-center.api'
import { graduationActionErrorMessage, graduationConflictMessage, isGraduationConflictResponse } from '@/modules/graduation/utils/form-state'
import { toast } from '@/utils/toast'
import { formatDateTime } from '@/utils/dateUtils'

const REJECT_REASON_CHIPS = ['材料不完整，请补充', '内容质量不达标，需修改', '格式不符合学校规范', '与选题方向不符']
const DEFENSE_COMMENT_CHIPS = ['选题有实际意义，完成度高', '回答问题思路清晰', '论文结构完整，工作量饱满', '部分问题回答不够深入']

export default {
  name: 'ProposalReviewCard',
  components: { LoadingState, ErrorState, AppButton, AppPermissionButton, AppAuditTrail, AppSectionCard, AppTemplateChips, GraduationDocumentReviewWorkspace },
  props: { ctx: { type: Object, required: true }, proposalId: { type: [String, Number], required: true }, compact: { type: Boolean, default: false } },
  emits: ['reviewed', 'conflict'],
  data() {
    return {
      REJECT_REASON_CHIPS, DEFENSE_COMMENT_CHIPS,
      previewProvider: graduationMaterialCenterApi.createPreviewProvider(),
      loading: true, error: '', detail: null, comment: '', formError: '', submitting: false, defenseComment: '',
      activePreviewFileKey: null, activePreviewVersionId: null, versionConflict: null, previewDraftKey: ''
    }
  },
  computed: {
    secureVersionFiles() { return graduationMaterialCenterApi.normalizeVersions(this.detail?.currentSafeVersions || []) },
    canonicalFileVersionId() { return this.detail?.fileVersionId ?? null },
    activePreviewFile() {
      return this.secureVersionFiles.find((item) => String(this.fileKey(item)) === String(this.activePreviewFileKey))
        || this.secureVersionFiles.find((item) => String(this.versionKey(item)) === String(this.activePreviewVersionId))
        || this.secureVersionFiles[0] || null
    },
    previewDescriptor() { return this.activePreviewFile ? graduationMaterialCenterApi.previewDescriptor(this.activePreviewFile) : null },
    trailRecords() { return (this.detail?.trail || []).map((t, i) => ({ id: i, action: t.action, actor: t.who, at: this.fmtTime(t.time), target: t.affected })) },
    canReview() {
      const pa = this.ctx.permissionActions.reviewProposal
      return !!(pa && pa.visible && pa.allowed && this.detail?.reviewReady && !this.versionConflict && String(this.activePreviewVersionId ?? '') === String(this.canonicalFileVersionId ?? ''))
    },
    reviewReason() {
      if (this.detail && !this.detail.reviewReady) return this.detail.migrationRequired ? '历史材料尚未完成公共版本回填' : '当前材料版本未通过安全门禁'
      const pa = this.ctx.permissionActions.reviewProposal
      if (pa && !pa.allowed) return pa.reason || '当前角色无开题批阅权限'
      if (this.versionConflict) return '学生已重交新版本，请切换最新版本后重新核验'
      if (String(this.activePreviewVersionId ?? '') !== String(this.canonicalFileVersionId ?? '')) return '当前正在阅读历史版本，历史版本只读不可批阅'
      return ''
    }
  },
  watch: { proposalId: { immediate: true, handler() { this.load() } } },
  beforeUnmount() { this.saveDraft() },
  methods: {
    fmtTime(s) { return formatDateTime(s, '') },
    versionKey(item) { return item?.fileVersionId ?? item?.versionId ?? item?.id ?? null },
    fileKey(item) { return item?.fileKey ?? item?.fileId ?? this.versionKey(item) },
    draftKey(fileVersionId = this.canonicalFileVersionId) { return this.detail?.id && fileVersionId != null ? `gd-proposal-review-draft:${this.detail.id}:${fileVersionId}` : '' },
    saveDraft() {
      const key = this.previewDraftKey || this.draftKey()
      if (!key) return
      try { if (this.comment) sessionStorage.setItem(key, this.comment); else sessionStorage.removeItem(key) } catch { /* unavailable */ }
    },
    restoreDraft() {
      this.previewDraftKey = this.draftKey()
      if (!this.previewDraftKey) return
      try { this.comment = sessionStorage.getItem(this.previewDraftKey) || this.comment || '' } catch { /* unavailable */ }
    },
    clearDraft() { if (this.previewDraftKey) { try { sessionStorage.removeItem(this.previewDraftKey) } catch { /* ignore */ } }; this.previewDraftKey = '' },
    appendComment(text) { this.comment = this.comment ? `${this.comment}\n${text}` : text; this.saveDraft() },
    appendDefense(text) { this.defenseComment = this.defenseComment ? `${this.defenseComment}\n${text}` : text },
    selectPreviewFile(item) {
      if (!item) return
      this.activePreviewFileKey = this.fileKey(item)
      this.activePreviewVersionId = this.versionKey(item)
      if (this.versionConflict && String(this.activePreviewVersionId) === String(this.canonicalFileVersionId) && this.detail?.reviewReady) this.versionConflict = null
    },
    selectPreviewVersion(item) { this.selectPreviewFile(item) },
    async downloadActivePreview() {
      if (!this.activePreviewFile?.canDownload) return
      try { await graduationMaterialCenterApi.downloadMaterial(this.activePreviewFile) } catch (error) { toast.error(error?.message || '下载失败') }
    },
    async load({ preserveDraft = false } = {}) {
      const drafts = preserveDraft ? { comment: this.comment, defenseComment: this.defenseComment } : null
      const oldCanonical = this.canonicalFileVersionId
      const oldActive = this.activePreviewVersionId
      if (!preserveDraft) this.saveDraft()
      this.loading = true; this.error = ''; this.formError = ''
      if (!preserveDraft) { this.comment = ''; this.defenseComment = '' }
      const res = await graduationApi.getProposalReviewDetail(this.proposalId)
      if (res.code === 0) {
        this.detail = res.data
        const latest = this.canonicalFileVersionId
        if (oldCanonical != null && latest != null && String(oldCanonical) !== String(latest)) {
          this.versionConflict = { old: oldCanonical, latest }
          this.activePreviewVersionId = oldActive ?? oldCanonical
        } else {
          this.versionConflict = null
          this.activePreviewVersionId = latest
        }
        const active = this.secureVersionFiles.find((item) => String(this.versionKey(item)) === String(this.activePreviewVersionId)) || this.secureVersionFiles[0] || null
        this.activePreviewFileKey = active ? this.fileKey(active) : null
        this.restoreDraft()
      } else this.error = graduationActionErrorMessage(res, '开题详情加载失败，请稍后重试')
      if (drafts) { this.comment = drafts.comment; this.defenseComment = drafts.defenseComment; this.saveDraft() }
      this.loading = false
    },
    async submit(action) {
      if (!this.canReview) return
      this.formError = ''
      if (action === 'REJECT' && (!this.comment || this.comment.trim().length < 5)) { this.formError = '驳回原因必填且不少于 5 个字'; return }
      const draft = this.comment
      this.submitting = true
      const res = await graduationApi.reviewProposal(this.detail.id, { action, comment: draft, expectedVersion: this.detail.materialVersion, fileVersionId: this.detail.fileVersionId })
      this.submitting = false
      if (res.code === 0) {
        this.clearDraft(); this.comment = ''; await this.load(); toast.success('批阅完成：' + res.data.statusLabel + '，已锁定 canonical FileVersion 并同步学生端'); this.$emit('reviewed', res.data)
      } else if (isGraduationConflictResponse(res)) {
        const conflictMessage = graduationConflictMessage(res); await this.load({ preserveDraft: true }); this.comment = draft; this.saveDraft(); this.formError = conflictMessage; this.$emit('conflict', res)
      } else { this.formError = graduationActionErrorMessage(res, '批阅未完成，请稍后重试'); this.saveDraft() }
    },
    async submitDefense(result) {
      if (result === 'FAIL' && (!this.defenseComment || this.defenseComment.trim().length < 5)) { toast.error('开题答辩不通过时评语必填且不少于 5 字'); return }
      this.submitting = true
      const res = await graduationMoreApi.holdProposalDefense(this.detail.id, result, this.defenseComment)
      this.submitting = false
      if (res.code === 0) { toast.success('开题答辩已录入'); this.defenseComment = ''; await this.load({ preserveDraft: true }) }
      else if (isGraduationConflictResponse(res)) { const conflictMessage = graduationConflictMessage(res); await this.load({ preserveDraft: true }); this.formError = conflictMessage }
      else this.formError = graduationActionErrorMessage(res, '开题答辩录入失败，请稍后重试')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.prc{min-width:0}.prc-conflict{margin:0 0 10px;padding:10px 12px;border-radius:8px;background:var(--warning-50);color:var(--warning-700)}.prc-content{display:grid;gap:8px;padding:8px;border-radius:8px;background:var(--gray-50,#f8fafc);font-size:13px;color:var(--text-secondary);line-height:1.6}.prc-content p{margin:0}.prc-content b{color:var(--text-primary)}.prc-blocked{padding:8px;border-radius:8px;background:var(--warning-50,#fffbeb);color:var(--warning-700,#a16207);font-size:12px}.prc-actions{display:grid;grid-template-columns:1fr 1fr;gap:8px}.prc-actions>*{width:100%}.prc-bottom{margin-top:12px}.prc-bottom.is-compact{grid-template-columns:1fr}.mp-textarea{width:100%;resize:vertical}
</style>
