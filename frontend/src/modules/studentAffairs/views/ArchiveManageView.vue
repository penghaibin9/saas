<template>
  <ModulePageShell
    title="学工归档"
    subtitle="归档批次 · 档案包收集 · 学院审核 / 学工处确认 · 水印包"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="学工归档"
  >
    <div class="av-workspace">
      <!-- 批次列表（本会话已建） -->
      <div class="av-side">
        <div class="av-side__head">
          归档批次
          <button type="button" class="av-btn av-btn--primary av-btn--sm" @click="openBatch">建批次</button>
        </div>
        <EmptyState v-if="!batches.length" title="暂无批次" description="点「建批次」新建归档批次" />
        <ul v-else class="av-blist">
          <li
            v-for="b in batches"
            :key="b.batchId"
            class="av-bitem"
            :class="{ 'is-active': current && current.batchId === b.batchId }"
            @click="selectBatch(b)"
          >
            <span class="av-bitem__name">{{ b.batchName }}</span>
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
        <p class="av-side__note">说明：进入自动加载归档批次（按数据范围，分页展示）；点批次查看流转与档案包。</p>
      </div>

      <!-- 批次详情 -->
      <div class="av-detail">
        <EmptyState v-if="!current" title="请选择或新建批次" description="查看流转进度与档案包" />
        <template v-else>
          <div class="av-dhead">
            <h3 class="av-dname">{{ current.batchName }}<span v-if="current.yearCode" class="av-year">{{ current.yearCode }}</span></h3>
            <button type="button" class="av-refresh" title="刷新" @click="reload">↻</button>
          </div>

          <!-- 流转进度 -->
          <div class="av-flow">
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

          <div class="av-actions">
            <button v-if="canCollect" type="button" class="av-btn av-btn--primary" :disabled="acting" @click="openCollect">圈定学生</button>
            <button v-if="advanceLabel" type="button" class="av-btn av-btn--primary" :disabled="acting" @click="onAdvance">{{ advanceLabel }}</button>
            <span v-if="current.status === 'ARCHIVED'" class="av-archived">✓ 已归档（水印包已登记）</span>
          </div>

          <!-- 档案包：后端 getBatch 一次性返回该批次全部档案包，无 page/total 字段，暂不加分页控件 -->
          <div class="av-pkgs">
            <div class="av-pkgs__head">档案包<span v-if="packages.length">{{ packages.length }}</span></div>
            <EmptyState v-if="!packages.length" title="暂无档案包" description="「圈定学生」后每生生成一个档案包" />
            <ul v-else class="av-pkglist">
              <li v-for="p in packages" :key="p.packageId" class="av-pkg">
                <span>学生#{{ p.studentId }}</span>
                <span class="av-pkg__status">{{ pkgStatusLabel(p.status) }}</span>
                <span v-if="p.exportTaskId" class="av-pkg__task">水印包 #{{ p.exportTaskId }}</span>
              </li>
            </ul>
          </div>
        </template>
      </div>
    </div>

    <!-- 建批次 -->
    <AppDrawer v-model:visible="batchModal.visible" title="新建归档批次">
      <div class="av-form">
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

    <!-- 圈定学生 -->
    <AppDrawer v-model:visible="collectModal.visible" title="圈定学生生成档案包">
      <div class="av-form">
        <AppFormItem label="学生（可多选）" required>
          <AppStudentPicker v-model="collectModal.studentIds" multiple :remote-search="searchStudents" placeholder="按姓名 / 学号搜索添加学生" />
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
  AppFormItem, AppInlineAlert, AppPagination, AppStatusTag, AppStudentPicker, AppTextInput
} from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { AppButton } from '@/components/ui'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

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
    AppDrawer, AppFormItem, AppInlineAlert, AppPagination, AppTextInput, AppButton
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
    searchStudents(keyword) {
      return studentAffairsApi.searchStudents(keyword)
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
      const res = await studentAffairsApi.collectArchive(this.current.batchId, ids)
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
      const res = await studentAffairsApi.advanceArchive(this.current.batchId, 'APPROVE')
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
.av-workspace {
  display: grid;
  grid-template-columns: minmax(220px, 280px) 1fr;
  gap: var(--space-4);
  align-items: start;
}
.av-side {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-3);
}
.av-side__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-3);
}
.av-blist {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.av-bitem {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  cursor: pointer;
}
.av-bitem.is-active {
  border-color: var(--primary-500);
  background: var(--primary-50);
}
.av-bitem__name {
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.av-side__note {
  margin-top: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.av-detail {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-4);
}
.av-dhead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.av-dname {
  margin: 0;
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.av-year {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
  margin-left: var(--space-2);
}
.av-refresh {
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  border-radius: var(--radius-base);
  width: 28px;
  height: 28px;
  cursor: pointer;
  color: var(--text-secondary);
}
.av-flow {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}
.av-step {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-full);
}
.av-step__dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-xs);
  background: var(--bg-muted, #f0f0f0);
  color: var(--text-tertiary);
}
.av-step.is-done .av-step__dot {
  background: var(--success-500, #22c55e);
  color: #fff;
}
.av-step.is-current .av-step__dot {
  background: var(--primary-600);
  color: #fff;
}
.av-step__label {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
}
.av-step.is-current .av-step__label {
  color: var(--primary-700);
  font-weight: 600;
}
.av-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-base);
}
.av-archived {
  font-size: var(--font-size-sm);
  color: var(--success-700, #15803d);
}
.av-pkgs__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}
.av-pkglist {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.av-pkg {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.av-pkg__status {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.av-pkg__task {
  margin-left: auto;
  font-size: var(--font-size-xs);
  color: var(--primary-600);
}
.av-btn {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.av-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.av-btn--sm {
  height: 24px;
  padding: 0 var(--space-2);
  font-size: var(--font-size-xs);
}
.av-btn--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
}
.av-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.av-side__pager {
  margin-top: var(--space-3);
}
</style>
