<template>
  <ModulePageShell title="就业材料审核详情" :subtitle="detail ? `${detail.material.name} · ${detail.material.className}` : ''" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="就业材料审核">
    <template #actions>
      <button type="button" class="emp-back" @click="$router.back()">← 返回审核列表</button>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="detail">
      <div class="emp-detail-grid">
        <div class="emp-col">
          <section class="emp-section">
            <div class="emp-section__head">
              <h3 class="emp-section__title">
                {{ labelOf('materialType', detail.material.materialType) }}
                <StatusTag :type="materialTagType[detail.material.status] || 'default'" :label="labelOf('materialStatus', detail.material.status)" dot style="margin-left: 8px" />
              </h3>
            </div>
            <!-- TP-E03/TP-E05：老师必须能一眼分清「正式安全文件」和「历史文件名文本」。
                 正式证据 = 已建立 EMPLOYMENT_MATERIAL 正式绑定 + 文件可用 + 安全扫描通过，
                 服务端已给出 fileId/bindingId/scanStatus/fileVersion；只有历史 file_name
                 的记录不是证据，不能显示成"可核验"。 -->
            <div class="emp-preview" :class="{ 'is-legacy': detail.material.legacyFileNameOnly }">
              <span class="emp-preview__icon">{{ detail.material.formalEvidence ? '▤' : '⚠' }}</span>
              <b>{{ detail.material.file?.fileName || detail.material.fileName || '（未提供文件）' }}</b>
              <template v-if="detail.material.formalEvidence">
                <span>
                  提交于 {{ detail.material.submitTime }} ·
                  正式材料（文件 #{{ detail.material.file.fileId }} · 第 {{ detail.material.file.fileVersion }} 版 ·
                  安全扫描 {{ scanText(detail.material.file.scanStatus) }}）
                </span>
              </template>
              <template v-else-if="detail.material.legacyFileNameOnly">
                <span>提交于 {{ detail.material.submitTime }} · 历史文本记录，未建立正式文件绑定，<b>不可作为核验凭据</b></span>
              </template>
              <template v-else>
                <span>提交于 {{ detail.material.submitTime }} · 尚未上传正式材料文件</span>
              </template>
            </div>
            <div v-if="detail.material.returnReason" class="emp-return-box">
              最近退回原因：{{ detail.material.returnReason }}
            </div>

            <div class="emp-review-ops">
              <AppButton variant="primary" :disabled="!canOperate" :title="operateTip" @click="approveVisible = true">审核通过</AppButton>
              <AppButton variant="danger" :disabled="!canOperate" :title="operateTip" @click="returnVisible = true">退回修改</AppButton>
            </div>
          </section>

          <section v-if="detail.student" class="emp-section" style="margin-top: var(--space-4)">
            <div class="emp-section__head">
              <h3 class="emp-section__title">关联学生</h3>
              <button type="button" class="emp-section__more" @click="$router.push(`/admin/employment/students/${detail.student.id}`)">查看就业详情 →</button>
            </div>
            <div class="emp-kv">
              <div class="emp-kv__item"><span class="emp-kv__label">姓名</span><span class="emp-kv__value">{{ detail.student.name }}</span></div>
              <div class="emp-kv__item"><span class="emp-kv__label">学号</span><span class="emp-kv__value">{{ detail.student.studentNo }}</span></div>
              <div class="emp-kv__item"><span class="emp-kv__label">班级</span><span class="emp-kv__value">{{ detail.student.className }}</span></div>
              <div class="emp-kv__item"><span class="emp-kv__label">去向</span><span class="emp-kv__value">{{ labelOf('destinationType', detail.student.destinationType) }}</span></div>
              <div class="emp-kv__item"><span class="emp-kv__label">单位 / 院校</span><span class="emp-kv__value">{{ detail.student.companyName || '—' }}</span></div>
              <div class="emp-kv__item"><span class="emp-kv__label">联系电话（脱敏）</span><span class="emp-kv__value">{{ detail.student.phone }}</span></div>
            </div>
          </section>
        </div>

        <div class="emp-col">
          <section class="emp-section">
            <h3 class="emp-section__title">审核留痕</h3>
            <AuditTrailPanel :logs="detail.auditLogs" />
          </section>
        </div>
      </div>

      <AppConfirmDialog
        v-model:visible="approveVisible"
        title="审核通过"
        :message="approveMessage"
        type="primary"
        confirm-text="确认通过"
        :submitting="submitting"
        @confirm="onApprove"
      />
      <AppConfirmDialog
        v-model:visible="returnVisible"
        title="退回修改"
        :message="`退回《${detail.material.fileName}》，学生将收到补充材料通知。`"
        type="warning"
        confirm-text="确认退回"
        require-reason
        reason-label="退回原因"
        reason-placeholder="请写明缺失或不合规内容，便于学生补充（不少于 5 个字）"
        :submitting="submitting"
        @confirm="onReturn"
      />
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 5：/admin/employment/materials/:materialId 材料审核详情（通过 / 退回原因必填 / 留痕）。 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState } from '@/components/business'
import { AppConfirmDialog } from '@/components/common'
import { AppButton } from '@/components/ui'
import { AuditTrailPanel } from '@/modules/employment/components'
import * as api from '@/modules/employment/api/employment.api'
import { MATERIAL_TAG_TYPE, toLabelMap } from '@/modules/employment/constants/employment.constants'
import { toast } from '@/utils/toast'

export default {
  name: 'EmploymentMaterialDetailView',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, AppConfirmDialog, AppButton, AuditTrailPanel },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      submitting: false,
      detail: null,
      statusOptions: {},
      approveVisible: false,
      returnVisible: false,
      materialTagType: MATERIAL_TAG_TYPE
    }
  },
  computed: {
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    reviewPerm() {
      return this.ctx?.permissionActions?.['employment.material.review']
    },
    canOperate() {
      const pending = ['SUBMITTED', 'REVIEWING'].includes(this.detail?.material?.status)
      return pending && (this.reviewPerm ? this.reviewPerm.allowed : true)
    },
    operateTip() {
      if (!['SUBMITTED', 'REVIEWING'].includes(this.detail?.material?.status)) return '该材料已完成审核'
      return this.reviewPerm && !this.reviewPerm.allowed ? this.reviewPerm.reason : ''
    },
    approveMessage() {
      const m = this.detail?.material || {}
      const name = m.file?.fileName || m.fileName || '该材料'
      // TP-E04：材料审核的闭环只在证据成立时才会顺带完成去向核验，文案必须与
      // 后端实际会发生的事一致，不能一律宣称"标记为已核验"。
      if (m.formalEvidence) {
        return `确认通过《${name}》？该材料具备正式文件绑定与安全扫描记录，通过后将同时完成去向核验并计入就业统计，全程留痕。`
      }
      const why = m.legacyFileNameOnly
        ? '该材料只有历史文件名文本，没有正式文件绑定与安全扫描记录'
        : '该材料尚未上传正式文件'
      return `确认通过《${name}》？${why}，不构成可核验的正式证据——通过后只会记录「材料已通过」，去向核验状态保持不变，需在学生详情页的「去向核验」中单独处理。`
    }
  },
  created() {
    this.load()
  },
  methods: {
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || value || '—'
    },
    scanText(status) {
      return { CLEAN: '已通过', NOT_REQUIRED: '无需扫描', PENDING: '待扫描', INFECTED: '未通过' }[status] || status || '未知'
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const [ctx, status, detail] = await Promise.all([
          api.getEmploymentContext(),
          api.getStatusOptions(),
          api.getMaterialReviewDetail(this.$route.params.materialId)
        ])
        if (ctx.code === 0) this.ctx = ctx.data
        if (status.code === 0) this.statusOptions = status.data
        if (detail.code === 0) this.detail = detail.data
        else this.error = detail.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    async onApprove() {
      this.submitting = true
      try {
        const res = await api.approveMaterial(this.detail.material.id, {})
        if (res.code === 0) {
          // 服务端如实回传这一步到底做成了什么（destinationVerified），前端照抄，
          // 不再把"材料通过"一律说成"已核验"。
          toast.success(res.data?.destinationVerified
            ? '材料审核通过，去向核验已同步完成，已写入留痕'
            : '材料审核通过，已写入留痕；因缺少正式证据，去向核验状态未变更')
          this.approveVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onReturn({ reason }) {
      this.submitting = true
      try {
        const res = await api.returnMaterial(this.detail.material.id, { reason })
        if (res.code === 0) {
          toast.success('材料已退回，原因已通知学生并留痕')
          this.returnVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import './employment-page.css';

.emp-return-box {
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--warning-50);
  border: 1px solid var(--warning-100);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--warning-700);
}
.emp-review-ops {
  margin-top: var(--space-4);
  display: flex;
  gap: var(--space-2);
}
.emp-preview.is-legacy { border-color: var(--warning-6, #e6a23c); background: var(--warning-1, #fdf6ec); }
</style>
