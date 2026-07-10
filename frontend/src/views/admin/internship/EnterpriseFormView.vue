<template>
  <ModulePageShell
    :title="isEdit ? '编辑企业' : '新增企业'"
    :subtitle="pageSubtitle"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="企业库维护"
  >
    <template #actions>
      <AppButton variant="ghost" @click="goBack">← 返回企业库</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="init" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-stack">
      <AppInlineAlert
        v-if="isEdit"
        type="info"
        title="合作状态与黑名单不在本页修改"
        description="资质审核、暂停/恢复合作、拉黑/移出黑名单属于状态机动作，请回到企业库列表在行内操作（二次确认并写入留痕）。"
      />

      <AppForm
        ref="entForm"
        :model="form"
        :rules="formRules"
        layout="horizontal"
        label-width="128px"
        @submit="onSubmit"
      >
        <!-- 基本信息 -->
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">基本信息</span></div>
          <div class="mp-card__body">
            <div class="ef-grid">
              <AppFormItem label="企业名称" prop="name" required>
                <AppTextInput v-model="form.name" placeholder="营业执照全称" />
              </AppFormItem>
              <AppFormItem label="行业" prop="industry">
                <AppSelect v-model="form.industry" :options="industryOptions" placeholder="请选择" />
              </AppFormItem>
              <AppFormItem label="来源" prop="source">
                <AppSelect v-model="form.source" :options="sourceOptions" placeholder="请选择" />
              </AppFormItem>
              <AppFormItem label="地区" prop="region">
                <AppTextInput v-model="form.region" placeholder="省/市" />
              </AppFormItem>
              <AppFormItem label="规模" prop="scale">
                <AppTextInput v-model="form.scale" placeholder="微/小/中/大型" />
              </AppFormItem>
              <AppFormItem class="ef-grid__full" label="详细地址" prop="address">
                <AppTextInput v-model="form.address" />
              </AppFormItem>
            </div>
          </div>
        </section>

        <!-- 联系与资质 -->
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">联系与资质</span>
            <span class="ef-aside">联系电话为敏感字段：列表默认脱敏，明文查看/导出走审计</span>
          </div>
          <div class="mp-card__body">
            <div class="ef-grid">
              <AppFormItem label="联系人" prop="contactPerson">
                <AppTextInput v-model="form.contactPerson" />
              </AppFormItem>
              <AppFormItem
                label="联系电话"
                prop="contactPhone"
                :hint="isEdit ? `当前：${(detail && detail.contactPhoneMasked) || '未登记'} · 留空表示不修改` : '敏感字段，列表默认脱敏'"
              >
                <AppTextInput v-model="form.contactPhone" :placeholder="isEdit ? '留空保持原号码不变' : '敏感字段，列表默认脱敏'" />
              </AppFormItem>
              <AppFormItem class="ef-grid__full" label="统一社会信用代码" prop="creditCode" hint="租户内唯一，重复将被后端拦截">
                <AppTextInput v-model="form.creditCode" placeholder="租户内唯一" />
              </AppFormItem>
            </div>
          </div>
        </section>

        <!-- 备注 -->
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">备注</span></div>
          <div class="mp-card__body">
            <AppFormItem label="备注" prop="remark">
              <AppTextarea v-model="form.remark" :rows="3" placeholder="企业补充说明（可选）" />
            </AppFormItem>
          </div>
        </section>

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
 * 口径：合作状态 / 黑名单是状态机动作（列表行内确认弹窗），不在本表单修改；
 *       联系电话为敏感字段：详情只回传脱敏值，编辑态留空 = 不修改，不回填脱敏串防止覆盖真实号码。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppSubmitBar
} from '@/components/common'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

const blankForm = () => ({
  name: '', creditCode: '', industry: '', source: '', region: '',
  scale: '', address: '', contactPerson: '', contactPhone: '', remark: ''
})

export default {
  name: 'EnterpriseFormView',
  components: {
    ModulePageShell, LoadingState, ErrorState, AppButton,
    AppInlineAlert, AppForm, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppSubmitBar
  },
  data() {
    return {
      ctx: null,
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
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.scopeName || ''
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
      return '新增合作企业主档，创建后初始为「待审核」，资质审核通过后进入合作中'
    },
    formRules() {
      return {
        name: [{ required: true, message: '企业名称必填' }]
      }
    }
  },
  watch: {
    '$route.params.id'() {
      // 同组件在 /new 与 /:id/edit 间切换时重新初始化；离开表单路由时跳过
      if (!this.isFormRoute) return
      this.detail = null
      this.init()
    }
  },
  created() {
    internshipApi.getContext().then((res) => {
      if (res.code === 0) this.ctx = res.data
    })
    this.init()
  },
  methods: {
    goBack() {
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && back.startsWith('/admin/internship/enterprises')) this.$router.back()
      else this.$router.push('/admin/internship/enterprises')
    },
    async init() {
      this.error = ''
      if (!this.isEdit) {
        this.detail = null
        this.form = blankForm()
        this.loading = false
        return
      }
      this.loading = true
      const id = this.$route.params.id
      const res = await internshipApi.getEnterpriseDetail(id)
      if (id !== this.$route.params.id) return
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
        contactPhone: '', // 敏感字段：详情只回传脱敏值，留空 = 不修改
        remark: d.remark || ''
      }
    },
    async onSubmit() {
      if (this.submitting) return
      const { valid } = await this.$refs.entForm.validate()
      if (!valid) return
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
      // 联系电话：新建时始终提交；编辑时留空表示不修改（不能把脱敏串写回后端）
      if (!this.isEdit || (f.contactPhone || '').trim()) body.contactPhone = (f.contactPhone || '').trim()
      this.submitting = true
      try {
        const res = this.isEdit
          ? await internshipApi.updateEnterprise(this.$route.params.id, body)
          : await internshipApi.createEnterprise(body)
        if (res.code === 0) {
          toast.success(this.isEdit ? '已保存并写入留痕' : '已新增企业（初始待审核）并写入留痕')
          this.goBack()
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
.ef-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-1) var(--space-6);
}
.ef-grid__full {
  grid-column: 1 / -1;
}
.ef-aside {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
@media (max-width: 960px) {
  .ef-grid {
    grid-template-columns: 1fr;
  }
}
</style>
