<template>
  <ModulePageShell
    title="学工归档"
    subtitle="批次收集、审核与归档"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="学工归档"
  >


    <AppGlobalState :state="listLoading ? 'loading' : listError ? 'error' : 'ready'" :description="listError" @retry="loadBatches">
    <div class="archive-workspace">
      <div class="av-side">
        <div class="av-side__head">
          <div>
            <strong>归档批次</strong>

          </div>
          <AppPermissionButton :allowed="canBtn('studentAffairs.archive.batch.manage')" code="studentAffairs.archive.batch.manage" variant="primary" size="sm" @click="openBatch">新建批次</AppPermissionButton>
        </div>
        <p v-if="!batches.length" class="av-empty">暂无归档批次</p>
        <ul v-else class="av-blist">
          <li
            v-for="b in batches"
            :key="b.batchId"
            class="av-bitem" role="button" tabindex="0"
            :aria-pressed="Boolean(current && current.batchId === b.batchId)"
            @keydown.enter="selectBatch(b)" @keydown.space.prevent="selectBatch(b)"
            :class="{ 'is-active': current && current.batchId === b.batchId }"
            @click="selectBatch(b)"
          >
            <span class="av-bitem__name">{{ b.batchName }}<small v-if="b.yearCode">{{ b.yearCode }}</small></span>
            <StatusTag :type="statusType(b.status)" :label="statusLabel(b.status)" dot />
          </li>
        </ul>
        <AppPagination
          v-if="batchPagination.total > batchPagination.pageSize"
          class="av-side__pager"
          :page="batchPagination.page"
          :page-size="batchPagination.pageSize"
          :total="batchPagination.total"
          :show-size-changer="false"
          @change="onBatchPageChange"
        />

      </div>

      <div class="av-detail">
        <p v-if="!current" class="av-empty">选择批次，查看归档进度与学生档案包</p>
        <AppGlobalState v-else :state="detailLoading ? 'loading' : detailError ? 'error' : 'ready'" :description="detailError" @retry="reload">
          <div class="av-dhead">
            <div>

              <h3 class="av-dname">{{ current.batchName }}<span v-if="current.yearCode" class="av-year">{{ current.yearCode }}</span></h3>
            </div>
            <div class="av-dhead__actions">
              <AppButton variant="secondary" @click="openPackageLedger">查看档案包台账</AppButton>
              <AppButton variant="ghost" :loading="detailLoading" @click="reload">刷新</AppButton>
            </div>
          </div>

          <div class="av-flow" aria-label="当前归档进度">
            <div
              v-for="(st, i) in FLOW"
              :key="st.key"
              class="av-step"
              :class="{ 'is-done': flowIndex > i, 'is-current': flowIndex === i }"
            >
              <span class="av-step__dot">{{ flowIndex > i ? '✓' : i + 1 }}</span>
              <span class="av-step__label">{{ st.label }}</span>
            </div>
          </div>

          <div class="av-next-action">
            <div>

              <p v-if="current.status === 'DRAFT'">选择归档学生，预检后生成档案包。</p>
              <p v-else-if="current.status === 'COLLECTING'">档案包全部生成后，提交学院审核。</p>
              <p v-else-if="current.status === 'COLLEGE_REVIEW'">核对档案后，提交学工处确认。</p>
              <p v-else-if="current.status === 'SA_CONFIRM'">确认无误后归档，生成正式水印包。</p>
              <p v-else>该批次已完成归档，当前仅供查看和追溯。</p>
            </div>
            <div class="av-actions">
              <AppPermissionButton :allowed="canBtn('studentAffairs.archive.batch.manage')" v-if="canCollect" code="studentAffairs.archive.batch.manage" variant="primary" size="sm" :loading="acting" @click="openCollect">圈定学生</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.archive.batch.manage')" v-if="advanceLabel" code="studentAffairs.archive.batch.manage" variant="primary" size="sm" :loading="acting" @click="advanceVisible = true">{{ advanceLabel }}</AppPermissionButton>
              <span v-if="current.status === 'ARCHIVED'" class="av-archived">✓ 已归档（水印包已登记）</span>
            </div>
          </div>

          <div class="av-pkgs">
            <div class="av-pkgs__head">
              <strong>学生档案包</strong>
              <span v-if="packages.length" class="av-pkgs__count">{{ packages.length }}</span>
            </div>
            <p v-if="!packages.length" class="av-empty">暂无档案包</p>
            <ul v-else class="av-pkglist">
              <li v-for="p in packages" :key="p.packageId" class="av-pkg">
                <span class="av-pkg__student">{{ p.realName || p.studentName || ('学生 #' + p.studentId) }}</span>
                <span class="av-pkg__status" :class="`is-${String(p.status || '').toLowerCase()}`">{{ pkgStatusLabel(p.status) }}</span>
                <span v-if="p.exportTaskId" class="av-pkg__task">水印包 #{{ p.exportTaskId }}</span>
              </li>
            </ul>
          </div>
        </AppGlobalState>
      </div>
    </div>

    </AppGlobalState>

    <AppDrawer v-model:visible="batchModal.visible" title="新建归档批次" mode="modal" size="medium">
      <div class="av-form">
        <div class="av-form__note">建议用届别或学年命名，便于后续查找。</div>
        <AppFormItem label="批次名称" required>
          <AppTextInput v-model="batchModal.batchName" placeholder="如：2026 届毕业生学工归档" :disabled="acting" />
        </AppFormItem>
        <AppFormItem label="学年">
          <AppTextInput v-model="batchModal.yearCode" placeholder="如：2025-2026（选填）" :disabled="acting" />
        </AppFormItem>
        <AppInlineAlert v-if="batchModal.error" type="danger" :description="batchModal.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="acting" @click="batchModal.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="acting" @click="submitBatch">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer v-model:visible="collectModal.visible" title="圈定学生生成档案包" mode="modal" size="medium">
      <div class="av-form">
        <div class="av-form__note">先核对学生范围，再确认生成；已在批次中的学生会跳过。</div>
        <AppFormItem label="学生（可多选）" required>
          <AppStudentPicker v-model="collectModal.studentIds" multiple placeholder="按姓名 / 学号搜索添加学生" @change="invalidateCollectPreview" />
        </AppFormItem>
        <div v-if="collectModal.preview" class="av-preview">
          <div class="av-preview__head"><span>范围预检已完成</span><strong>{{ collectModal.preview.selectedCount }} 人</strong></div>
          <div class="av-preview__metrics">
            <div><span>将新建</span><strong>{{ collectModal.preview.newCount }}</strong></div>
            <div><span>已在批次中</span><strong>{{ collectModal.preview.duplicateCount }}</strong></div>
          </div>
          <ul class="av-preview__students">
            <li v-for="student in collectModal.preview.students" :key="student.studentId">
              <span>{{ student.studentName || ('学生 #' + student.studentId) }}<small>{{ student.studentNo || '无学号' }}</small></span>
              <em :class="{ duplicate: student.result === 'ALREADY_INCLUDED' }">{{ student.result === 'ALREADY_INCLUDED' ? '已存在，跳过' : '可生成' }}</em>
            </li>
          </ul>
          <p>预检完成后，请核对学生再确认生成。</p>
        </div>
        <AppInlineAlert v-if="collectModal.error" type="danger" :description="collectModal.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="acting" @click="collectModal.visible = false">取消</AppButton>
        <AppButton v-if="collectModal.preview" variant="secondary" :disabled="acting" @click="previewCollect">重新预检</AppButton>
        <AppButton variant="primary" :loading="acting" @click="collectModal.preview ? submitCollect() : previewCollect()">{{ collectModal.preview ? '确认生成档案包' : '先预检范围' }}</AppButton>
      </template>
    </AppDrawer>
    <AppConfirmDialog v-model:visible="advanceVisible" :title="advanceLabel || '确认归档操作'" :confirm-text="advanceLabel || '确认'" :submitting="acting" @confirm="onAdvance">
      <p v-if="current">{{ current.batchName }} · {{ packages.length }} 份档案包</p>
      <p>请确认档案范围与材料已核对无误，再推进下一阶段。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/**
 * 学工归档（/admin/student-affairs/archive）—— 13A P7。
 * 真实对接 /api/v1/student-affairs/archive/*：建批次 → 圈定学生生成档案包 → 学院审核 → 学工处确认 → 归档(登记水印包)。
 * 批次列表、预检和推进均使用正式归档接口。
 */
import { ModulePageShell } from '@/components/business'
import {
  AppGlobalState, AppConfirmDialog, AppFormItem, AppInlineAlert, AppPagination, AppPermissionButton, AppStatusTag, AppStudentPicker, AppTextInput
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppButton } from '@/components/ui'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const FLOW = [
  { key: 'DRAFT', label: '草稿' },
  { key: 'COLLECTING', label: '收集中' },
  { key: 'COLLEGE_REVIEW', label: '学院审核' },
  { key: 'SA_CONFIRM', label: '学工处确认' },
  { key: 'ARCHIVED', label: '已归档' }
]
const STATUS_TYPE = { DRAFT: 'default', COLLECTING: 'processing', COLLEGE_REVIEW: 'warning', SA_CONFIRM: 'warning', ARCHIVED: 'success' }
const PKG_STATUS = {
  PENDING_GEN: '排队生成', GENERATING: '生成中', PENDING_SUPPLEMENT: '生成失败，待处理',
  SUBMITTED: '已生成', RETURNED: '已退回', ARCHIVED: '已归档'
}

export default {
  name: 'ArchiveManageView',
  components: {
    ModulePageShell, StatusTag: AppStatusTag, AppStudentPicker,
    AppDrawer, AppGlobalState, AppConfirmDialog, AppFormItem, AppInlineAlert, AppPagination, AppPermissionButton, AppTextInput, AppButton
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      listLoading: true, listError: '', detailLoading: false, detailError: '', detailRequest: 0, advanceVisible: false,
      FLOW, batches: [], current: null, packages: [], acting: false,
      batchPagination: { page: 1, pageSize: 20, total: 0 },
      batchModal: { visible: false, batchName: '', yearCode: '', error: '' },
      collectModal: { visible: false, studentIds: [], error: '', preview: null }
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    flowIndex() {
      if (!this.current) return -1
      return FLOW.findIndex((f) => f.key === this.current.status)
    },
    canCollect() {
      return this.current && ['DRAFT', 'COLLECTING'].includes(this.current.status)
    },
    advanceLabel() {
      const s = this.current && this.current.status
      return { COLLECTING: '推进到学院审核', COLLEGE_REVIEW: '推进到学工处确认', SA_CONFIRM: '确认归档（生成水印包）' }[s] || ''
    }
  },
  mounted() {
    this.loadBatches()
  },
  watch: {
    '$route.query.batchId'(value) {
      if (!this.listLoading) this.applyRouteBatch(value)
    }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async loadBatches() {
      this.listLoading = true
      this.listError = ''
      const res = await studentAffairsApi.getArchiveBatches({
        page: this.batchPagination.page,
        pageSize: this.batchPagination.pageSize
      })
      if (res.code === 0 && res.data) {
        this.batches = res.data.items || []
        this.batchPagination.total = res.data.total || 0
        const routeBatchId = String(this.$route.query.batchId || '')
        if (routeBatchId) this.applyRouteBatch(routeBatchId)
        else if (!this.current && this.batches.length) this.selectBatch(this.batches[0])
      } else { this.listError = res.message || '归档批次加载失败' }
      this.listLoading = false
    },
    onBatchPageChange(next) {
      this.batchPagination.page = (next && next.page) || 1
      this.loadBatches()
    },
    statusType(s) {
      return STATUS_TYPE[s] || 'default'
    },
    statusLabel(s) {
      const f = FLOW.find((x) => x.key === s)
      return f ? f.label : s
    },
    pkgStatusLabel(s) {
      return PKG_STATUS[s] || (s ? '状态待确认' : '—')
    },
    applyRouteBatch(value) {
      const batchId = String(value || '')
      if (!/^[1-9]\d*$/.test(batchId) || String(this.current?.batchId || '') === batchId) return
      const row = this.batches.find((item) => String(item.batchId) === batchId)
      this.selectBatch(row || { batchId, batchName: `归档批次 #${batchId}` }, false)
    },
    syncBatchRoute(batchId) {
      const value = String(batchId || '')
      if (!value || String(this.$route.query.batchId || '') === value) return
      this.$router.replace({ query: { ...this.$route.query, batchId: value } })
    },
    selectBatch(b, syncRoute = true) {
      if (this.acting) return
      this.packages = []
      this.current = b
      if (syncRoute) this.syncBatchRoute(b.batchId)
      this.reload()
    },
    openPackageLedger() {
      if (!this.current) return
      this.$router.push({ path: '/admin/student-affairs/archive/packages', query: { batchId: String(this.current.batchId) } })
    },
    async reload() {
      if (!this.current) return
      const requestId = ++this.detailRequest
      this.detailLoading = true
      this.detailError = ''
      const res = await studentAffairsApi.getArchiveBatch(this.current.batchId)
      if (requestId !== this.detailRequest) return
      this.detailLoading = false
      if (res.code === 0 && res.data) {
        this.current = { ...this.current, ...res.data }
        this.packages = res.data.packages || []
        const idx = this.batches.findIndex((x) => x.batchId === this.current.batchId)
        if (idx > -1) this.batches.splice(idx, 1, { ...this.batches[idx], status: this.current.status })
      } else {
        this.detailError = res.message || '加载批次失败'
      }
    },
    openBatch() {
      this.batchModal = { visible: true, batchName: '', yearCode: '', error: '' }
    },
    async submitBatch() {
      const m = this.batchModal
      const batchName = (m.batchName || '').trim()
      const yearCode = (m.yearCode || '').trim()
      if (!batchName) { m.error = '请填写批次名称'; return }
      this.acting = true
      const res = await studentAffairsApi.createArchiveBatch({ batchName, yearCode })
      this.acting = false
      if (res.code === 0 && res.data) {
        toast.success('批次已创建')
        this.batchModal.visible = false
        this.batchPagination.page = 1
        await this.loadBatches()
        this.selectBatch(res.data)
      } else { m.error = res.message || '创建失败' }
    },
    openCollect() {
      this.collectModal = { visible: true, studentIds: [], error: '', preview: null }
    },
    invalidateCollectPreview() {
      this.collectModal.preview = null
      this.collectModal.error = ''
    },
    async previewCollect() {
      const ids = Array.isArray(this.collectModal.studentIds) ? this.collectModal.studentIds : []
      if (!ids.length) { this.collectModal.error = '请至少圈定一名学生'; return }
      this.acting = true
      this.collectModal.error = ''
      const res = await studentAffairsApi.previewArchiveCollect(this.current.batchId, ids, this.current.version)
      this.acting = false
      if (res.code === 0) this.collectModal.preview = res.data
      else this.collectModal.error = res.message || '范围预检失败'
    },
    async submitCollect() {
      const ids = Array.isArray(this.collectModal.studentIds) ? this.collectModal.studentIds : []
      if (!ids.length) { this.collectModal.error = '请至少圈定一名学生'; return }
      if (!this.collectModal.preview) { this.collectModal.error = '请先完成范围预检'; return }
      this.acting = true
      const res = await studentAffairsApi.collectArchive(this.current.batchId, ids, this.current.version)
      this.acting = false
      if (res.code === 0) {
        toast.success(`已提交 ${res.data.packagesQueued ?? res.data.packagesCreated ?? 0} 个档案包生成任务`)
        this.collectModal.visible = false
        this.reload()
      } else {
        this.collectModal.error = res.message || '生成失败'
        toast.error(this.collectModal.error)
      }
    },
    async onAdvance() {
      if (this.acting) return
      this.acting = true
      const res = await studentAffairsApi.advanceArchive(this.current.batchId, 'APPROVE', this.current.version)
      this.acting = false
      if (res.code === 0) {
        this.advanceVisible = false
        toast.success(res.data.status === 'ARCHIVED' ? '已归档，水印包已登记' : '已推进')
        this.reload()
      } else {
        toast.error(res.message || '推进失败')
      }
    }
  }
}
</script>

<style scoped>
.archive-workspace { display: grid; grid-template-columns: 240px minmax(0,1fr); min-height: 320px; }
.av-side { min-width: 0; padding-right: 16px; border-right: 1px solid var(--border-light); }
.av-side__head, .av-dhead, .av-pkgs__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 0 12px; }
.av-dhead__actions { display: flex; align-items: center; gap: 8px; }
.av-side__head strong, .av-pkgs__head strong { font-size: 14px; }
.av-blist, .av-pkglist { list-style: none; margin: 0; padding: 0; }
.av-bitem { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 12px 10px; border-bottom: 1px solid var(--border-light); cursor: pointer; }
.av-bitem:hover { background: var(--bg-section); }
.av-bitem.is-active { background: var(--primary-50); box-shadow: inset 3px 0 var(--primary-500); }
.av-bitem:focus-visible { outline: 2px solid var(--primary-500); outline-offset: -2px; }
.av-bitem__name { min-width: 0; overflow-wrap: anywhere; font-size: 13px; font-weight: 600; }
.av-bitem__name small { display: block; margin-top: 4px; font-weight: 400; color: var(--text-tertiary); }
.av-detail { min-width: 0; padding-left: 20px; }
.av-dname { margin: 0; font-size: 17px; }
.av-year { margin-left: 10px; font-size: 13px; font-weight: 400; color: var(--text-tertiary); }
.av-flow { display: flex; flex-wrap: wrap; gap: 10px 16px; padding: 12px 0; border-bottom: 1px solid var(--border-light); }
.av-step { display: flex; align-items: center; gap: 6px; color: var(--text-tertiary); font-size: 12px; }
.av-step__dot { display: grid; place-items: center; width: 20px; height: 20px; border-radius: 50%; border: 1px solid var(--border-base); }
.av-step.is-current { color: var(--primary-600); font-weight: 600; }
.av-step.is-current .av-step__dot { background: var(--primary-50); border-color: currentColor; }
.av-step.is-done { color: var(--success-700); }
.av-next-action { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; padding: 14px 0 20px; }
.av-next-action p { margin: 0; font-size: 13px; color: var(--text-secondary); }
.av-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.av-archived { font-size: 13px; color: var(--success-700); }
.av-pkgs__count { font-variant-numeric: tabular-nums; color: var(--text-tertiary); font-size: 13px; }
.av-pkg { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; padding: 12px 0; border-bottom: 1px solid var(--border-light); font-size: 13px; }
.av-pkg__student { flex: 1; font-weight: 500; }
.av-pkg__task { color: var(--text-tertiary); }
.av-pkg__status.is-submitted, .av-pkg__status.is-archived { color: var(--success-700); }
.av-pkg__status.is-pending_supplement, .av-pkg__status.is-returned { color: var(--danger-700); }
.av-empty { padding: 56px 12px; text-align: center; font-size: 13px; color: var(--text-tertiary); }
.av-form { display: grid; gap: 16px; }
.av-form__note { font-size: 13px; color: var(--text-secondary); }
.av-preview { border-top: 1px solid var(--border-light); padding-top: 16px; }
.av-preview__head, .av-preview__metrics { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.av-preview__head { font-size: 14px; }
.av-preview__metrics { justify-content: flex-start; }
.av-preview__metrics > div { display: flex; gap: 8px; color: var(--text-secondary); font-size: 13px; }
.av-preview__metrics strong { color: var(--text-primary); }
.av-preview__students { max-height: 220px; overflow: auto; margin: 0; padding: 0; list-style: none; }
.av-preview__students li { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0; border-top: 1px solid var(--border-light); font-size: 13px; }
.av-preview__students small { margin-left: 8px; color: var(--text-tertiary); }
.av-preview__students em { color: var(--success-700); font-style: normal; }
.av-preview__students em.duplicate { color: var(--warning-700); }
.av-preview > p { color: var(--text-tertiary); font-size: 12px; }
.av-side__pager { margin-top: 12px; }
@media (max-width: 720px) { .archive-workspace { grid-template-columns: minmax(0,1fr); } .av-side { border-right: 0; border-bottom: 1px solid var(--border-light); padding: 0 0 16px; } .av-detail { padding: 16px 0 0; } .av-empty { padding: 28px 8px; } }
</style>
