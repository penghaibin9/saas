<template>
  <ModulePageShell
    :title="isEdit ? '编辑企业' : '新增企业'"
    :subtitle="pageSubtitle"
    watermark-purpose="企业库维护"
  >
    <template #actions>
      <AppButton variant="ghost" @click="goBack">{{ isEdit ? '返回企业详情' : '返回企业库' }}</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="init" />
    <LoadingState v-else-if="loading" />
    <AppInlineAlert v-else-if="readonly" type="info" title="当前资料不可编辑" :description="readonlyReason" />
    <div v-else class="mp-stack">
      <AppForm
        ref="entForm"
        :model="form"
        :rules="formRules"
        layout="vertical"
        class="ef-form"
        @submit="onSubmit"
      >
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">企业资料</span><span class="ef-aside">用于识别合作企业与办理准入</span></div>
          <div class="mp-card__body">
            <div class="ef-grid">
              <AppFormItem v-slot="{ id }" class="ef-grid__full" label="企业名称" prop="name" required>
                <AppTextInput :id="id" v-model="form.name" placeholder="填写营业执照上的企业全称" />
              </AppFormItem>
              <AppFormItem v-slot="{ id }" label="统一社会信用代码" prop="creditCode" hint="按营业执照填写 18 位代码">
                <AppTextInput :id="id" v-model="form.creditCode" placeholder="统一社会信用代码" />
              </AppFormItem>
              <AppFormItem v-slot="{ id }" label="企业规模" prop="scale">
                <AppTextInput :id="id" v-model="form.scale" placeholder="如：中型企业" />
              </AppFormItem>
              <AppFormItem v-slot="{ id }" label="所属行业" prop="industry">
                <AppSelect :id="id" v-model="form.industry" :options="industryOptions" placeholder="选择行业" />
              </AppFormItem>
              <AppFormItem v-slot="{ id }" label="合作来源" prop="source">
                <AppSelect :id="id" v-model="form.source" :options="sourceOptions" placeholder="选择来源" />
              </AppFormItem>
              <AppFormItem class="ef-grid__full" label="地区" prop="region">
                <AppChinaRegionPicker v-model="form.region" level="city" placeholder="请选择企业所在省 / 市" />
              </AppFormItem>
              <AppFormItem v-slot="{ id }" class="ef-grid__full" label="详细地址" prop="address">
                <AppTextInput :id="id" v-model="form.address" placeholder="街道、园区与门牌号" />
              </AppFormItem>
            </div>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">对接信息</span>
            <span class="ef-aside">便于学校联系企业、推进合作</span>
          </div>
          <div class="mp-card__body">
            <div class="ef-grid">
              <AppFormItem v-slot="{ id }" label="联系人" prop="contactPerson">
                <AppTextInput :id="id" v-model="form.contactPerson" placeholder="企业对接人姓名" />
              </AppFormItem>
              <AppFormItem
                v-slot="{ id }"
                label="联系电话"
                prop="contactPhone"
                :hint="isEdit ? `当前：${(detail && detail.contactPhoneMasked) || '未登记'} · 留空表示不修改` : '敏感字段，列表默认脱敏'"
              >
                <AppTextInput :id="id" v-model="form.contactPhone" :placeholder="isEdit ? '留空保持原号码不变' : '填写联系电话'" />
              </AppFormItem>
              <AppFormItem v-slot="{ id }" class="ef-grid__full" label="合作说明" prop="remark">
                <AppTextarea :id="id" v-model="form.remark" :rows="4" placeholder="记录企业合作背景、沟通事项或补充说明（可选）" />
              </AppFormItem>
            </div>
          </div>
        </section>

        <p class="ef-next">{{ isEdit ? '保存后返回企业详情，继续查看资质、考察与合作记录。' : '保存后进入企业详情，继续办理资质审核与企业考察。' }}</p>

        <AppSubmitBar
          :loading="submitting"
          :submit-text="isEdit ? '保存修改' : '创建企业'"
          cancel-text="取消"
          @submit="onSubmit"
          @cancel="goBack"
        />
      </AppForm>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 企业表单独立页（新建 + 编辑一体，替代企业库列表页原「新增/编辑抽屉」）。
 * 路由（由主流程挂载，本文件不改 routes.js）：
 *   /admin/internship/enterprises/new       → 新建（创建后初始「待审核」）
 *   /admin/internship/enterprises/:id/edit  → 编辑（getEnterpriseDetail 回填）
 * 提交走真实 internshipApi.createEnterprise / updateEnterprise。
 * 口径：合作状态 / 黑名单通过详情状态机办理；
 *       联系电话为敏感字段：详情只回传脱敏值，编辑态留空 = 不修改，不回填脱敏串防止覆盖真实号码。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppSubmitBar,
  AppChinaRegionPicker
} from '@/components/common'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

const blankForm = () => ({
  name: '', creditCode: '', industry: '', source: '', region: '',
  scale: '', address: '', contactPerson: '', contactPhone: '', remark: ''
})

export default {
  name: 'EnterpriseFormView',
  props: { ctx: { type: Object, required: true } },
  components: {
    ModulePageShell, LoadingState, ErrorState, AppButton,
    AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppSubmitBar,
    AppChinaRegionPicker
  },
  data() {
    return {
      loadSequence: 0,
      loading: false,
      error: '',
      submitting: false,
      detail: null,
      form: blankForm()
    }
  },
  computed: {
    isEdit() {
      return !!this.$route.params.id
    },
    isFormRoute() {
      const p = this.$route.path
      return p.endsWith('/new') || p.endsWith('/edit')
    },
    readonly() {
      return this.ctx?.permissionActions?.[this.isEdit ? 'editEnterprise' : 'createEnterprise']?.allowed !== true || this.detail?.coopStatus === 'ARCHIVED'
    },
    readonlyReason() {
      if (this.detail?.coopStatus === 'ARCHIVED') return '企业已归档，可返回详情查看历史资料与办理记录。'
      return this.ctx?.permissionActions?.[this.isEdit ? 'editEnterprise' : 'createEnterprise']?.reason || '当前角色没有企业资料维护权限。'
    },
    industryOptions() {
      return this.ctx?.statusOptions?.enterpriseIndustry || []
    },
    sourceOptions() {
      return this.ctx?.statusOptions?.enterpriseSource || []
    },
    pageSubtitle() {
      if (this.isEdit) {
        return this.detail ? `${this.detail.name} · ${this.detail.creditCode || '无信用代码'} · ${this.detail.coopStatusLabel || ''}` : ''
      }
      return '登记企业身份与对接信息，保存后继续办理准入'
    },
    formRules() {
      return {
        name: [{ required: true, message: '企业名称必填' }]
      }
    }
  },
  watch: {
    '$route.params.id'() {
      if (!this.isFormRoute) return
      this.detail = null
      this.init()
    }
  },
  created() {
    this.init()
  },
  mounted() {
    this.$nextTick(() => {
      const heading = this.$el?.querySelector('h1')
      if (!heading) return
      heading.setAttribute('tabindex', '-1')
      heading.style.scrollMarginTop = '170px'
      heading.focus({ preventScroll: true })
      heading.scrollIntoView({ block: 'start', behavior: 'instant' })
    })
  },
  beforeUnmount() { this.loadSequence++ },
  methods: {
    goBack() {
      this.$router.push({ path: this.isEdit ? `/admin/internship/enterprises/${this.$route.params.id}` : '/admin/internship/enterprises', query: { ...this.$route.query } })
    },
    async init() {
      const sequence = ++this.loadSequence
      this.error = ''
      this.detail = null
      this.form = blankForm()
      if (!this.isEdit) {
        this.detail = null
        this.form = blankForm()
        this.loading = false
        return
      }
      this.loading = true
      const id = this.$route.params.id
      const res = await internshipApi.getEnterpriseDetail(id)
      if (sequence !== this.loadSequence || id !== this.$route.params.id) return
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '企业不存在或无权查看'
        return
      }
      const d = res.data
      this.detail = d
      this.form = {
        name: d.name || '',
        creditCode: d.creditCode || '',
        industry: d.industry || '',
        source: d.source || '',
        region: d.region || '',
        scale: d.scale || '',
        address: d.address || '',
        contactPerson: d.contactPerson || '',
        contactPhone: '',
        remark: d.remark || ''
      }
    },
    async onSubmit() {
      if (this.submitting || this.loading || this.error || this.readonly) return
      const sequence = this.loadSequence
      const id = this.$route.params.id
      const editing = this.isEdit
      const { valid } = await this.$refs.entForm.validate()
      if (!valid || sequence !== this.loadSequence || this.readonly) return
      const f = this.form
      const body = {
        name: (f.name || '').trim(),
        creditCode: (f.creditCode || '').trim(),
        industry: f.industry || '',
        source: f.source || '',
        region: (f.region || '').trim(),
        scale: (f.scale || '').trim(),
        address: (f.address || '').trim(),
        contactPerson: (f.contactPerson || '').trim(),
        remark: (f.remark || '').trim()
      }
      if (!this.isEdit || (f.contactPhone || '').trim()) body.contactPhone = (f.contactPhone || '').trim()
      if (this.isEdit) body.expectedVersion = this.detail?.version
      this.submitting = true
      try {
        const res = editing
          ? await internshipApi.updateEnterprise(id, body)
          : await internshipApi.createEnterprise(body)
        if (sequence !== this.loadSequence || id !== this.$route.params.id) return
        if (res.code === 0) {
          if (typeof window !== 'undefined') window.__SAAS_DIRTY_FORM_GUARD__?.markSaved?.()
          toast.success(this.isEdit ? '已保存并写入留痕' : '已新增企业（初始待审核）并写入留痕')
          this.$router.push({ path: `/admin/internship/enterprises/${editing ? id : res.data.id}`, query: { ...this.$route.query } })
        } else {
          toast.error(res.message || '保存失败')
        }
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ef-form { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr); gap: 20px; align-items: start; }
.ef-form :deep(.app-form-item) { margin-bottom: 0; }
.ef-form :deep(.app-form-item__label) { line-height: 22px; margin-bottom: 6px; }
.ef-form > :deep(.app-submit-bar), .ef-next { grid-column: 1 / -1; }
.ef-next { margin: 0; color: var(--text-secondary); font-size: var(--font-size-sm); }
.ef-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.ef-grid__full {
  grid-column: 1 / -1;
}
.ef-aside {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
@media (max-width: 960px) {
  .ef-form { grid-template-columns: 1fr; }
  .ef-grid {
    grid-template-columns: 1fr;
  }
}
</style>
