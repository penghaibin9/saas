<template>
  <ModulePageShell
    title="学工归档"
    subtitle="归档批次 · 档案包收集 · 学院审核 / 学工处确认 · 水印包"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="学工归档"
  >
    <section class="sa-summary-strip">
      <div class="sa-summary-strip__content">
        <span class="sa-summary-strip__eyebrow">当前归档任务</span>
        <h2 class="sa-summary-strip__title">
          {{ current ? `${current.batchName} · ${statusLabel(current.status)}` : '请先选择现有批次或新建归档批次' }}
        </h2>
        <p class="sa-summary-strip__text">
          {{ current ? `当前已生成 ${packages.length} 个学生档案包。按照流程完成收集、学院审核、学工处确认后，系统登记正式水印归档包。` : '归档按批次推进。先建批次并圈定学生，确保每名学生档案包生成成功后再进入审核。' }}
        </p>
      </div>
      <div class="sa-summary-strip__actions">
        <AppPermissionButton :allowed="canBtn('studentAffairs.archive.batch.manage')" code="studentAffairs.archive.batch.manage" variant="primary" size="sm" @click="openBatch">新建归档批次</AppPermissionButton>
      </div>
    </section>

    <div class="sa-workflow-strip" aria-label="学工归档流程">
      <div class="sa-workflow-step" data-step="1"><strong>新建批次</strong><br>明确批次名称和归档学年</div>
      <div class="sa-workflow-step" data-step="2"><strong>圈定学生</strong><br>为每名学生生成独立档案包</div>
      <div class="sa-workflow-step" data-step="3"><strong>学院审核</strong><br>核对档案范围、内容与生成状态</div>
      <div class="sa-workflow-step" data-step="4"><strong>学工处确认</strong><br>确认无缺失后生成正式水印包</div>
      <div class="sa-workflow-step" data-step="5"><strong>完成归档</strong><br>归档批次转为只读并保留审计</div>
    </div>

    <div class="av-workspace">
      <div class="av-side">
        <div class="av-side__head">
          <div>
            <strong>归档批次</strong>
            <small>按当前数据范围分页展示</small>
          </div>
          <AppPermissionButton :allowed="canBtn('studentAffairs.archive.batch.manage')" code="studentAffairs.archive.batch.manage" variant="primary" size="sm" @click="openBatch">建批次</AppPermissionButton>
        </div>
        <EmptyState v-if="!batches.length" title="暂无批次" description="点“建批次”创建第一个归档批次" />
        <ul v-else class="av-blist">
          <li
            v-for="b in batches"
            :key="b.batchId"
            class="av-bitem"
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
        <p class="av-side__note">选择批次后，右侧展示当前流程、可执行动作和全部学生档案包。</p>
      </div>

      <div class="av-detail">
        <EmptyState v-if="!current" title="请选择或新建批次" description="选中批次后，可查看当前阶段、下一步动作与档案包生成情况" />
        <template v-else>
          <div class="av-dhead">
            <div>
              <span class="av-dhead__label">当前批次</span>
              <h3 class="av-dname">{{ current.batchName }}<span v-if="current.yearCode" class="av-year">{{ current.yearCode }}</span></h3>
            </div>
            <button type="button" class="av-refresh" title="刷新" @click="reload">↻</button>
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
              <span>当前阶段</span>
              <strong>{{ statusLabel(current.status) }}</strong>
              <p v-if="current.status === 'DRAFT'">下一步：圈定本批次归档学生并生成档案包。</p>
              <p v-else-if="current.status === 'COLLECTING'">下一步：检查全部档案包生成情况，再推进学院审核。</p>
              <p v-else-if="current.status === 'COLLEGE_REVIEW'">下一步：学院核对档案范围和内容，确认后提交学工处。</p>
              <p v-else-if="current.status === 'SA_CONFIRM'">下一步：学工处完成最终确认并生成正式水印归档包。</p>
              <p v-else>该批次已完成归档，当前仅供查看和追溯。</p>
            </div>
            <div class="av-actions">
              <AppPermissionButton :allowed="canBtn('studentAffairs.archive.batch.manage')" v-if="canCollect" code="studentAffairs.archive.batch.manage" variant="primary" size="sm" :loading="acting" @click="openCollect">圈定学生</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.archive.batch.manage')" v-if="advanceLabel" code="studentAffairs.archive.batch.manage" variant="primary" size="sm" :loading="acting" @click="onAdvance">{{ advanceLabel }}</AppPermissionButton>
              <span v-if="current.status === 'ARCHIVED'" class="av-archived">✓ 已归档（水印包已登记）</span>
            </div>
          </div>

          <div class="av-pkgs">
            <div class="av-pkgs__head">
              <div><strong>学生档案包</strong><small>每名学生一份，需全部生成成功后再推进审核</small></div>
              <span v-if="packages.length" class="av-pkgs__count">{{ packages.length }} 份</span>
            </div>
            <EmptyState v-if="!packages.length" title="暂无档案包" description="点击“圈定学生”后，系统将为每名学生生成独立档案包" />
            <ul v-else class="av-pkglist">
              <li v-for="p in packages" :key="p.packageId" class="av-pkg">
                <span class="av-pkg__student">学生 #{{ p.studentId }}</span>
                <span class="av-pkg__status" :class="`is-${String(p.status || '').toLowerCase()}`">{{ pkgStatusLabel(p.status) }}</span>
                <span v-if="p.exportTaskId" class="av-pkg__task">水印包 #{{ p.exportTaskId }}</span>
              </li>
            </ul>
          </div>
        </template>
      </div>
    </div>

    <AppDrawer v-model:visible="batchModal.visible" title="新建归档批次">
      <div class="av-form">
        <div class="av-form__note">批次建立后，按批次圈定学生并生成档案包。批次名称建议包含届别、学年或归档对象。</div>
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

    <AppDrawer v-model:visible="collectModal.visible" title="圈定学生生成档案包">
      <div class="av-form">
        <div class="av-form__note">只选择本批次确需归档的学生。提交后系统为每名学生生成一份独立档案包。</div>
        <AppFormItem label="学生（可多选）" required>
          <AppStudentPicker v-model="collectModal.studentIds" multiple placeholder="按姓名 / 学号搜索添加学生" />
        </AppFormItem>
        <AppInlineAlert v-if="collectModal.error" type="danger" :description="collectModal.error" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="acting" @click="collectModal.visible = false">取消</AppButton>
        <AppButton variant="primary" :loading="acting" @click="submitCollect">生成档案包</AppButton>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 学工归档（/admin/student-affairs/archive）—— 13A P7。
 * 真实对接 /api/v1/student-affairs/archive/*：建批次 → 圈定学生生成档案包 → 学院审核 → 学工处确认 → 归档(登记水印包)。
 * 后端按批次 ID 管理，无列表端点，本页维护本会话已建批次。
 */
import { ModulePageShell, EmptyState } from '@/components/business'
import {
  AppFormItem, AppInlineAlert, AppPagination, AppPermissionButton, AppStatusTag, AppStudentPicker, AppTextInput
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
const PKG_STATUS = { PENDING_GEN: '待生成', GENERATED: '已生成', ARCHIVED: '已归档' }

export default {
  name: 'ArchiveManageView',
  components: {
    ModulePageShell, EmptyState, StatusTag: AppStatusTag, AppStudentPicker,
    AppDrawer, AppFormItem, AppInlineAlert, AppPagination, AppPermissionButton, AppTextInput, AppButton
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      FLOW, batches: [], current: null, packages: [], acting: false,
      batchPagination: { page: 1, pageSize: 20, total: 0 },
      batchModal: { visible: false, batchName: '', yearCode: '', error: '' },
      collectModal: { visible: false, studentIds: [], error: '' }
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
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async loadBatches() {
      const res = await studentAffairsApi.getArchiveBatches({
        page: this.batchPagination.page,
        pageSize: this.batchPagination.pageSize
      })
      if (res.code === 0 && res.data) {
        this.batches = res.data.items || []
        this.batchPagination.total = res.data.total || 0
      }
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
      return PKG_STATUS[s] || s
    },
    selectBatch(b) {
      this.current = b
      this.reload()
    },
    async reload() {
      if (!this.current) return
      const res = await studentAffairsApi.getArchiveBatch(this.current.batchId)
      if (res.code === 0 && res.data) {
        this.current = { ...this.current, ...res.data }
        this.packages = res.data.packages || []
        const idx = this.batches.findIndex((x) => x.batchId === this.current.batchId)
        if (idx > -1) this.batches.splice(idx, 1, { ...this.batches[idx], status: this.current.status })
      } else {
        toast.error(res.message || '加载批次失败')
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
      this.collectModal = { visible: true, studentIds: [], error: '' }
    },
    async submitCollect() {
      const ids = Array.isArray(this.collectModal.studentIds) ? this.collectModal.studentIds : []
      if (!ids.length) { this.collectModal.error = '请至少圈定一名学生'; return }
      this.acting = true
      const res = await studentAffairsApi.collectArchive(this.current.batchId, ids, this.current.version)
      this.acting = false
      if (res.code === 0) {
        toast.success(`已生成 ${res.data.packagesCreated} 个档案包`)
        this.collectModal.visible = false
        this.reload()
      } else {
        this.collectModal.error = res.message || '生成失败'
        toast.error(this.collectModal.error)
      }
    },
    async onAdvance() {
      this.acting = true
      const res = await studentAffairsApi.advanceArchive(this.current.batchId, 'APPROVE', this.current.version)
      this.acting = false
      if (res.code === 0) {
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
.av-workspace { display: grid; grid-template-columns: minmax(240px, 300px) minmax(0, 1fr); gap: var(--space-4); align-items: start; }
.av-side { border: 1px solid var(--border-base); border-radius: var(--radius-lg); background: var(--bg-card); min-height: 360px; padding: var(--space-3); }
.av-side__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-2); margin-bottom: var(--space-3); color: var(--text-primary); }
.av-side__head > div { display: grid; gap: 2px; }
.av-side__head small { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 400; }
.av-blist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.av-bitem { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); padding: 10px 11px; border: 1px solid var(--border-base); border-radius: var(--radius-md); cursor: pointer; transition: border-color .12s, background .12s; }
.av-bitem:hover { border-color: var(--primary-200, #bfdbfe); background: var(--primary-50, #eff6ff); }
.av-bitem.is-active { border-color: var(--primary-500); background: var(--primary-50); box-shadow: inset 3px 0 0 var(--primary-500); }
.av-bitem__name { display: grid; gap: 2px; min-width: 0; color: var(--text-primary); font-size: var(--font-size-sm); font-weight: 600; }
.av-bitem__name small { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 400; }
.av-side__note { margin: var(--space-3) 0 0; padding-top: var(--space-3); border-top: 1px solid var(--border-light); color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.6; }
.av-detail { border: 1px solid var(--border-base); border-radius: var(--radius-lg); background: var(--bg-card); min-height: 360px; padding: var(--space-4); min-width: 0; }
.av-dhead { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); padding-bottom: var(--space-3); border-bottom: 1px solid var(--border-light); }
.av-dhead__label { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.av-dname { margin: 3px 0 0; font-size: var(--font-size-lg); color: var(--text-primary); }
.av-year { font-size: var(--font-size-sm); color: var(--text-tertiary); margin-left: var(--space-2); font-weight: 400; }
.av-refresh { border: 1px solid var(--border-base); background: var(--bg-card); border-radius: var(--radius-base); width: 32px; height: 32px; cursor: pointer; color: var(--text-secondary); }
.av-flow { display: grid; grid-template-columns: repeat(5, minmax(100px, 1fr)); gap: var(--space-2); margin-bottom: var(--space-4); }
.av-step { display: flex; align-items: center; gap: var(--space-2); padding: 9px 10px; border: 1px solid var(--border-light); border-radius: var(--radius-md); background: var(--bg-section); }
.av-step__dot { width: 22px; height: 22px; flex: 0 0 22px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-size: var(--font-size-xs); background: var(--gray-200, #e2e8f0); color: var(--text-tertiary); }
.av-step.is-done { border-color: var(--success-200, #bbf7d0); background: var(--success-50, #f0fdf4); }
.av-step.is-done .av-step__dot { background: var(--success-500, #22c55e); color: #fff; }
.av-step.is-current { border-color: var(--primary-300, #93c5fd); background: var(--primary-50); }
.av-step.is-current .av-step__dot { background: var(--primary-600); color: #fff; }
.av-step__label { font-size: var(--font-size-xs); color: var(--text-secondary); }
.av-step.is-current .av-step__label { color: var(--primary-700); font-weight: 600; }
.av-next-action { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-4); align-items: center; margin-bottom: var(--space-4); padding: var(--space-3) var(--space-4); border: 1px solid var(--primary-100); border-radius: var(--radius-lg); background: var(--primary-50); }
.av-next-action span { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.av-next-action strong { display: block; margin-top: 2px; color: var(--text-primary); }
.av-next-action p { margin: 4px 0 0; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.55; }
.av-actions { display: flex; align-items: center; justify-content: flex-end; gap: var(--space-2); flex-wrap: wrap; }
.av-archived { font-size: var(--font-size-sm); color: var(--success-700, #15803d); font-weight: 600; }
.av-pkgs { min-width: 0; }
.av-pkgs__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); }
.av-pkgs__head > div { display: grid; gap: 2px; }
.av-pkgs__head small { color: var(--text-tertiary); font-size: var(--font-size-xs); font-weight: 400; }
.av-pkgs__count { padding: 3px 9px; border-radius: var(--radius-full); background: var(--bg-section); color: var(--text-secondary); font-size: var(--font-size-xs); }
.av-pkglist { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-2); }
.av-pkg { display: flex; align-items: center; gap: var(--space-3); min-width: 0; padding: 10px 12px; border: 1px solid var(--border-base); border-radius: var(--radius-md); font-size: var(--font-size-sm); color: var(--text-primary); }
.av-pkg__student { font-weight: 600; }
.av-pkg__status { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.av-pkg__status.is-generated, .av-pkg__status.is-archived { color: var(--success-700, #15803d); }
.av-pkg__status.is-pending_gen { color: var(--warning-700, #b45309); }
.av-pkg__task { margin-left: auto; font-size: var(--font-size-xs); color: var(--primary-600); }
.av-form { display: flex; flex-direction: column; gap: var(--space-4); }
.av-form__note { padding: 10px 12px; border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.av-side__pager { margin-top: var(--space-3); }
@media (max-width: 1080px) { .av-workspace { grid-template-columns: 1fr; } .av-side { min-height: 0; } .av-flow { grid-template-columns: repeat(3, minmax(100px, 1fr)); } }
@media (max-width: 720px) { .av-flow, .av-pkglist { grid-template-columns: 1fr; } .av-next-action { grid-template-columns: 1fr; } .av-actions { justify-content: flex-start; } }
</style>
