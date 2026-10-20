<template>
  <ModulePageShell :title="isEdit ? '招聘季设置' : '新建招聘季'" subtitle="安排本轮招募时间与学生投递要求" watermark-purpose="招聘季设置">
    <template #actions><AppButton variant="ghost" :disabled="submitting" @click="goBack">{{ isEdit ? '返回招聘季详情' : '返回招聘与邀请' }}</AppButton><AppButton v-if="!loading && !error && !noPermission && !readonly" variant="primary" :loading="submitting" :disabled="conflicted" @click="save">保存草稿</AppButton></template>
    <NoPermissionState v-if="noPermission" @back="goBack" />
    <LoadingState v-else-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="init" />
    <div v-else class="cf-workspace">
      <aside class="cf-outline" aria-label="设置分区">
        <p class="cf-kicker">本轮招募</p>
        <strong>{{ form.campaignName || '尚未命名的招聘季' }}</strong>
        <span>{{ detail ? statusLabel(detail.status) : '新建草稿' }}</span>
        <nav><button v-for="(item, index) in sections" :key="item.key" type="button" @click="focusSection(item.key)"><span>0{{ index + 1 }}</span>{{ item.label }}</button></nav>
        <p>{{ readonly ? '查阅本轮时间与规则，返回详情可查看招募进展。' : '保存后仍为草稿。核对安排后，在详情的“状态办理”中开启本轮招募。' }}</p>
      </aside>
      <div class="cf-main">
        <AppInlineAlert v-if="readonly" type="info" title="当前设置只读" :description="detail?.status !== 'DRAFT' ? '本轮已离开草稿状态，时间与规则不能再修改。' : '当前身份没有招聘季维护权限。'" />
        <AppForm ref="campaignForm" :model="form" :rules="formRules" layout="vertical" @submit="save">
          <fieldset :disabled="readonly || submitting" class="cf-fields">
            <section ref="identity" tabindex="-1" class="cf-section">
              <header><h2>基本信息</h2><p>将本轮企业招募归入一个实习批次。</p></header>
              <div class="cf-grid">
                <AppFormItem v-slot="{ id }" label="所属实习批次" prop="batchId" required><AppSelect :id="id" v-model="form.batchId" :options="batchOptions" :disabled="readonly || submitting" /></AppFormItem>
                <AppFormItem v-slot="{ id }" label="招聘季编码" prop="campaignCode" required hint="学校内唯一，例如 2027-AUTUMN-R1"><AppTextInput :id="id" v-model="form.campaignCode" :maxlength="100" :disabled="readonly || submitting" /></AppFormItem>
                <AppFormItem v-slot="{ id }" label="招聘季名称" prop="campaignName" required><AppTextInput :id="id" v-model="form.campaignName" :maxlength="200" :disabled="readonly || submitting" placeholder="如 2027届秋季实习企业招募" /></AppFormItem>
                <AppFormItem v-slot="{ id }" label="招募轮次" prop="roundNo" required hint="同一实习批次内，轮次不能重复"><AppNumberInput :id="id" v-model="form.roundNo" :min="1" :disabled="readonly || submitting" /></AppFormItem>
                <AppFormItem v-slot="{ id }" class="cf-full" label="备注" prop="remark"><AppTextarea :id="id" v-model="form.remark" :rows="2" :maxlength="500" :disabled="readonly || submitting" placeholder="补充本轮招募安排，选填" /></AppFormItem>
              </div>
              <p v-if="batchOptionsError" class="cf-error" role="alert">{{ batchOptionsError }}</p>
              <div v-if="batchOptionsMore && !readonly" class="cf-batches"><span>未找到批次，可继续加载后续批次。</span><AppButton variant="ghost" :loading="batchOptionsLoading" @click="loadMoreBatches">加载更多批次</AppButton></div>
            </section>
            <section ref="schedule" tabindex="-1" class="cf-section">
              <header><h2>时间安排</h2><p>按本地时间填写，精确到秒。未确定的窗口可以整组留空后保存草稿。</p></header>
              <div v-for="(item, index) in windows" :key="item.start" class="cf-window">
                <div class="cf-window-title"><span>{{ index + 1 }}</span><div><h3>{{ item.label }}</h3><p>{{ item.hint }}</p></div></div>
                <AppFormItem v-slot="{ id }" :label="item.label + '开始'" :prop="item.start"><input :id="id" v-model="form[item.start]" class="cf-date" type="datetime-local" step="1" /></AppFormItem>
                <AppFormItem v-slot="{ id }" :label="item.label + '结束'" :prop="item.end"><input :id="id" v-model="form[item.end]" class="cf-date" type="datetime-local" step="1" /></AppFormItem>
              </div>
              <AppFormItem v-slot="{ id }" label="企业访问截止" prop="enterpriseAccessEndAt" hint="企业账号最晚可用到此时间，不能早于上方任一已配置窗口的结束时间。"><input :id="id" v-model="form.enterpriseAccessEndAt" class="cf-date cf-cutoff" type="datetime-local" step="1" /></AppFormItem>
              <p class="cf-note">邀请企业前，还需填写企业邀请窗口和企业访问截止时间。</p>
            </section>
            <section ref="materials" tabindex="-1" class="cf-section">
              <header><h2>投递材料</h2><p>这些要求会在学生正式投递时核验。</p></header>
              <AppInlineAlert v-if="legacyPolicy" type="warning" title="保留现有材料规则" description="本轮包含旧版规则，此处仅查阅原配置。保存其他设置不会覆盖这些规则。" />
              <pre v-if="legacyPolicy" class="cf-legacy">{{ JSON.stringify(detail.applicationMaterialPolicy, null, 2) }}</pre>
              <template v-else>
                <label class="cf-check cf-rule"><input v-model="form.applicationMaterialPolicy.profileRequired" type="checkbox" /><span><strong>提交前须建立个人资料</strong><small>学生需先保存个人实习资料。</small></span></label>
                <fieldset class="cf-options"><legend>个人资料必填内容</legend><label v-for="item in materialSections" :key="item.value" class="cf-check"><input v-model="form.applicationMaterialPolicy.requiredSections" type="checkbox" :value="item.value" />{{ item.label }}</label></fieldset>
                <fieldset class="cf-options"><legend>须具备的材料类型</legend><label v-for="item in materialTypes" :key="item.value" class="cf-check"><input v-model="form.applicationMaterialPolicy.requiredItemTypes" type="checkbox" :value="item.value" />{{ item.label }}</label></fieldset>
                <div class="cf-grid cf-rule-grid">
                  <label class="cf-check"><input v-model="form.applicationMaterialPolicy.applicationStatementRequired" type="checkbox" />每个志愿须填写申请说明</label>
                  <AppFormItem v-slot="{ id }" label="申请说明最低字数" prop="minStatementLength" hint="设为 0 表示不设最低字数；大于 0 时每个志愿都需达到该字数。"><AppNumberInput :id="id" v-model="form.applicationMaterialPolicy.minStatementLength" :min="0" :max="5000" :disabled="readonly || submitting" /></AppFormItem>
                </div>
                <label class="cf-check cf-rule"><input v-model="form.applicationMaterialPolicy.resumePdfEnabled" type="checkbox" /><span><strong>允许生成投递简历 PDF</strong><small>按已有材料快照和访问权限生成。</small></span></label>
                <fieldset class="cf-options"><legend>学生可选择的联系方式共享方式</legend><label v-for="item in contactModes" :key="item.value" class="cf-check"><input v-model="form.applicationMaterialPolicy.allowedContactSharingModes" type="checkbox" :value="item.value" />{{ item.label }}</label></fieldset>
                <p class="cf-note">这里只设定可选方式，学生投递时仍需选择共享模式及是否共享电话、邮箱。</p>
                <p v-if="!form.applicationMaterialPolicy.allowedContactSharingModes.length" class="cf-error" role="status">未选择任何共享方式，学生将无法完成正式投递。可先保存草稿，开启前请补齐。</p>
              </template>
            </section>
            <section ref="confirmation" tabindex="-1" class="cf-section">
              <header><h2>确认规则</h2><p>决定录用结果确认条件及教师处理时限。</p></header>
              <label class="cf-check cf-rule"><input v-model="form.enterpriseConfirmRequired" type="checkbox" /><span><strong>学校确认前须有企业录用意向</strong><small>确认分配时核验本轮企业决定。</small></span></label>
              <AppFormItem v-slot="{ id }" label="教师确认时限（小时）" prop="teacherConfirmSlaHours" required hint="企业作出录用意向、锁定志愿后开始计时；可设 1–168 小时。"><AppNumberInput :id="id" v-model="form.teacherConfirmSlaHours" :min="1" :max="168" :disabled="readonly || submitting" /></AppFormItem>
            </section>
          </fieldset>
          <div class="cf-submit">
            <div><p v-if="saveError" class="cf-error" role="alert">{{ saveError }}</p><span v-else>{{ readonly ? '当前只读，可返回详情查看本轮进展' : '仅保存草稿，不会自动开启招募或邀请企业' }}</span></div>
            <AppButton variant="ghost" :disabled="submitting" @click="goBack">返回</AppButton>
            <AppButton v-if="!readonly" variant="primary" :loading="submitting" :disabled="conflicted" @click="save">保存草稿</AppButton>
          </div>
        </AppForm>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppForm, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppNumberInput, AppInlineAlert } from '@/components/common'
import { AppButton } from '@/components/ui'
import { NoPermissionState } from '@/modules/internship/components'
import { recruitmentCampaignApi } from '@/modules/internship/api/recruitment-campaign.api'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { canCode } from '@/modules/internship/composables/permission'
import { campaignStatusLabel } from '@/modules/internship/constants/recruitmentCampaign.constants'
import { campaignFormModel, campaignFormErrors, campaignFormBody, unsupportedMaterialPolicy, CAMPAIGN_WINDOWS, MATERIAL_SECTIONS, MATERIAL_TYPES, CONTACT_MODES } from '@/modules/internship/utils/campaignForm'
import { toast } from '@/utils/toast'

export default {
  name: 'RecruitmentCampaignFormView',
  components: { ModulePageShell, LoadingState, ErrorState, AppForm, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppNumberInput, AppInlineAlert, AppButton, NoPermissionState },
  props: { ctx: { type: Object, required: true } },
  data() { return { alive: true, sequence: 0, loading: true, error: '', detail: null, form: campaignFormModel(), submitting: false,
    saveError: '', conflicted: false, batchOptions: [], batchOptionsPage: 0, batchOptionsMore: false, batchOptionsLoading: false, batchOptionsError: '',
    windows: CAMPAIGN_WINDOWS, materialSections: MATERIAL_SECTIONS, materialTypes: MATERIAL_TYPES, contactModes: CONTACT_MODES,
    sections: [{ key: 'identity', label: '基本信息' }, { key: 'schedule', label: '时间安排' }, { key: 'materials', label: '投递材料' }, { key: 'confirmation', label: '确认规则' }] } },
  computed: {
    isEdit() { return !!this.$route.params.id },
    contextKey() { return JSON.stringify([this.$route.params.id || '', this.$route.query.batchId || '', this.ctx?.ctxKey || '']) },
    canManage() { return this.allowed('internship.recruitment.manage', 'internship.enterprise.manage') },
    noPermission() { return this.isEdit ? !this.allowed('internship.recruitment.view', 'internship.enterprise.view') : !this.canManage },
    readonly() { return !this.canManage || (this.isEdit && this.detail?.status !== 'DRAFT') },
    legacyPolicy() { return !!this.detail && unsupportedMaterialPolicy(this.detail.applicationMaterialPolicy || {}) },
    formRules() {
      const keys = ['batchId', 'campaignCode', 'campaignName', 'roundNo', 'teacherConfirmSlaHours', 'remark', 'minStatementLength', 'enterpriseAccessEndAt', ...CAMPAIGN_WINDOWS.flatMap((w) => [w.start, w.end])]
      const errors = campaignFormErrors(this.form, { preservePolicy: this.legacyPolicy })
      // AppForm skips custom validators for empty values. A missing paired endpoint must still fail.
      return Object.fromEntries(keys.map((key) => [key, [{ required: !!errors[key], message: errors[key], validator: () => errors[key] || true }]]))
    }
  },
  watch: {
    contextKey() { this.init() },
    // Number stepper buttons emit model updates without native input/change events.
    form: { deep: true, flush: 'sync', handler() { if (!this.loading && !this.readonly) window.__SAAS_DIRTY_FORM_GUARD__?.markDirty?.() } }
  },
  created() { this.init() },
  beforeUnmount() { this.alive = false; this.sequence++ },
  methods: {
    allowed(...codes) { return Array.isArray(this.ctx?.permissionPatterns) && codes.some((code) => canCode(this.ctx, code)) },
    statusLabel: campaignStatusLabel,
    current(sequence, key) { return this.alive && sequence === this.sequence && key === this.contextKey },
    focusSection(key) { this.$refs[key]?.scrollIntoView({ behavior: 'smooth', block: 'start' }); this.$refs[key]?.focus({ preventScroll: true }) },
    async init() {
      const sequence = ++this.sequence, key = this.contextKey, id = this.$route.params.id, batchId = this.$route.query.batchId || ''
      this.loading = true; this.error = ''; this.saveError = ''; this.conflicted = false; this.submitting = false; this.detail = null
      this.batchOptions = []; this.batchOptionsPage = 0; this.batchOptionsMore = true; this.batchOptionsLoading = false; this.batchOptionsError = ''
      try {
        if (this.noPermission) return
        let detail = null
        if (id) {
          const response = await recruitmentCampaignApi.getCampaignDetail(id)
          if (!this.current(sequence, key)) return
          if (response.code !== 0) throw new Error(response.message || '招聘季加载失败')
          detail = response.data
          if (batchId && String(detail.batchId) !== String(batchId)) throw new Error('招聘季不属于当前批次，请从所属批次重新进入')
        }
        if (!this.current(sequence, key)) return
        this.detail = detail; this.form = campaignFormModel(detail || {}, batchId)
        await this.loadMoreBatches()
        if (!this.current(sequence, key)) return
        // A selected batch may be outside the first page or lack list permission. Resolve it independently.
        if (this.form.batchId && !this.batchOptions.some((b) => b.value === this.form.batchId)) {
          const result = await internshipApi.getBatchDetail(this.form.batchId)
          if (!this.current(sequence, key)) return
          this.batchOptions.unshift({ value: this.form.batchId, label: result.code === 0 ? result.data.batchName : `批次 ${this.form.batchId}（名称暂不可用）` })
        }
      } catch (e) { if (this.current(sequence, key)) this.error = e.message || '加载失败' }
      finally { if (this.current(sequence, key)) this.loading = false }
    },
    async loadMoreBatches() {
      if (this.batchOptionsLoading) return
      const sequence = this.sequence, key = this.contextKey, page = this.batchOptionsPage + 1
      this.batchOptionsLoading = true; this.batchOptionsError = ''
      try {
        const response = await internshipApi.getBatches({ page, pageSize: 200 })
        if (!this.current(sequence, key)) return
        if (response.code !== 0) throw new Error(response.message || '批次选项加载失败')
        const rows = response.data.list || []
        for (const b of rows) if (!this.batchOptions.some((o) => o.value === String(b.id))) this.batchOptions.push({ value: String(b.id), label: b.batchName })
        this.batchOptionsPage = page
        this.batchOptionsMore = Number.isFinite(Number(response.data.total)) ? page * 200 < Number(response.data.total) : rows.length === 200
      } catch (e) { if (this.current(sequence, key)) this.batchOptionsError = e.message || '批次选项加载失败' }
      finally { if (this.current(sequence, key)) this.batchOptionsLoading = false }
    },
    goBack() {
      if (this.submitting) return
      const query = { ...this.$route.query }; delete query.epPage; delete query.epStatus
      if (this.isEdit) query.section = query.section || 'schedule'
      else delete query.section
      return this.$router.push({ path: '/admin/internship/recruitment-campaigns' + (this.isEdit ? '/' + this.$route.params.id : ''), query })
    },
    async save() {
      if (this.noPermission || this.readonly || this.loading || this.error || this.submitting || this.conflicted || !this.$refs.campaignForm) return
      const sequence = this.sequence, key = this.contextKey, id = this.$route.params.id, query = { ...this.$route.query }
      this.submitting = true; this.saveError = ''
      try {
        const result = await this.$refs.campaignForm.validate()
        if (!this.current(sequence, key) || this.readonly) return
        if (!result?.valid) {
          this.saveError = '请检查标注的必填项和时间安排'
          this.submitting = false
          await this.$nextTick()
          if (this.current(sequence, key)) this.$el?.querySelector('.app-form-item.is-error input, .app-form-item.is-error select')?.focus()
          return
        }
        const incompleteTime = [...(this.$el?.querySelectorAll('input[type="datetime-local"]') || [])].find((input) => input.validity.badInput)
        if (incompleteTime) {
          this.saveError = '请补全正在填写的日期时间，或将该窗口整组清空'; this.submitting = false
          await this.$nextTick()
          if (this.current(sequence, key)) incompleteTime.focus()
          return
        }
        const body = campaignFormBody(this.form, this.detail)
        const response = id ? await recruitmentCampaignApi.updateCampaign(id, body) : await recruitmentCampaignApi.createCampaign(body)
        if (!this.current(sequence, key)) return
        if (response.code !== 0) {
          this.conflicted = !!id && (/CONFLICT|409|409001/.test(String(response.code)) || /版本|已更新|仅.*DRAFT|仅.*草稿/.test(response.message || ''))
          this.saveError = (response.message || '保存失败，请重试') + (this.conflicted ? '。填写内容已保留，请先核对最新详情再重新进入编辑。' : '')
          return
        }
        window.__SAAS_DIRTY_FORM_GUARD__?.markSaved?.()
        toast.success('招聘季草稿已保存')
        delete query.epPage; delete query.epStatus
        await this.$router.push({ path: '/admin/internship/recruitment-campaigns/' + response.data.id, query: { ...query, batchId: String(response.data.batchId), section: 'schedule' } })
      } catch (e) { if (this.current(sequence, key)) this.saveError = e.message || '保存失败，填写内容已保留' }
      finally { if (this.current(sequence, key)) this.submitting = false }
    }
  }
}
</script>

<style scoped>
.cf-workspace { display:grid; grid-template-columns:190px minmax(0,1fr); gap:24px; align-items:start; }
.cf-outline { position:sticky; top:170px; display:flex; flex-direction:column; gap:8px; padding:16px 0; color:var(--t2); }
.cf-outline strong { color:var(--t1); font-size:15px; line-height:1.6; overflow-wrap:anywhere; }
.cf-outline > span,.cf-kicker { font-size:12px; color:var(--t3); }
.cf-outline p { margin:0; font-size:12px; line-height:1.7; }
.cf-outline nav { display:grid; gap:6px; margin:14px 0; }
.cf-outline button { display:flex; gap:14px; align-items:center; border:0; border-radius:6px; padding:11px 10px; color:var(--t1); background:transparent; font:inherit; font-size:13px; text-align:left; cursor:pointer; }
.cf-outline button:hover,.cf-outline button:focus-visible { background:var(--primary-50); color:var(--primary-600); }
.cf-outline button span { color:var(--t3); font-size:11px; font-variant-numeric:tabular-nums; }
.cf-main { min-width:0; container-type:inline-size; }
.cf-fields { border:0; padding:0; margin:0; min-width:0; }
.cf-section { background:var(--bg-card); border:1px solid var(--border-base); border-radius:10px; padding:24px; margin-bottom:16px; scroll-margin-top:170px; }
.cf-section header { margin-bottom:22px; }
.cf-section h2 { margin:0; color:var(--t1); font-size:16px; font-weight:600; }
.cf-section header p,.cf-note { margin:7px 0 0; font-size:12px; color:var(--t3); line-height:1.7; }
.cf-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:0 22px; }
.cf-full { grid-column:1/-1; }
.cf-window { display:grid; grid-template-columns:minmax(130px,.8fr) repeat(2,minmax(0,1fr)); gap:16px; align-items:start; border-bottom:1px solid var(--border-base); margin-bottom:16px; }
.cf-window-title { display:flex; gap:9px; padding-top:4px; }
.cf-window-title > span { display:grid; place-items:center; flex:0 0 22px; height:22px; border-radius:50%; background:var(--primary-50); color:var(--primary-600); font-size:11px; }
.cf-window h3 { margin:0; font-size:13px; color:var(--t1); }
.cf-window p { margin:6px 0 0; font-size:11px; line-height:1.6; color:var(--t3); }
.cf-date { width:100%; min-width:0; box-sizing:border-box; height:36px; padding:0 8px; border:1px solid var(--border-base); border-radius:6px; background:var(--bg-card); color:var(--t1); font:inherit; font-size:12px; }
.cf-date:focus-visible { outline:2px solid var(--primary-400); outline-offset:2px; }
.cf-date:disabled { background:var(--bg-page); color:var(--t2); }
.cf-cutoff { max-width:340px; }
.cf-check { display:flex; align-items:center; gap:9px; font-size:13px; color:var(--t1); line-height:1.6; cursor:pointer; }
.cf-check input { width:16px; height:16px; margin:0; flex-shrink:0; accent-color:var(--primary-600); }
.cf-check small { display:block; margin-top:3px; color:var(--t3); font-size:12px; font-weight:400; }
.cf-rule { padding:0 0 18px; }
.cf-rule strong { font-weight:500; }
.cf-options { display:flex; flex-wrap:wrap; gap:14px 24px; padding:12px 0 20px; margin:0; border:0; min-width:0; }
.cf-options legend { font-size:13px; color:var(--t2); font-weight:500; }
.cf-rule-grid { align-items:start; padding-top:10px; }
.cf-error { color:var(--danger-600); font-size:12px; line-height:1.6; margin:0; }
.cf-batches { display:flex; align-items:center; gap:12px; font-size:12px; color:var(--t3); }
.cf-legacy { white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; color:var(--t2); }
.cf-submit { display:flex; align-items:center; gap:10px; padding:14px 18px; background:var(--bg-card); border:1px solid var(--border-base); border-radius:8px; }
.cf-submit > div { flex:1; color:var(--t3); font-size:12px; }
@media (max-width:1200px) { .cf-workspace { grid-template-columns:150px minmax(0,1fr); gap:16px; } .cf-section { padding:20px; } .cf-window { grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px 14px; } .cf-window-title { grid-column:1/-1; padding:0; } .cf-window-title p { display:none; } }
@media (max-width:800px) { .cf-workspace { display:block; } .cf-outline { position:static; padding:0; } .cf-outline > strong,.cf-outline > span,.cf-outline > p { display:none; } .cf-outline nav { display:flex; flex-wrap:wrap; margin:0 0 12px; gap:4px; } .cf-outline button { padding:9px 8px; gap:6px; } .cf-section { padding:18px; } }
@media (max-width:540px) { .cf-grid,.cf-window { grid-template-columns:minmax(0,1fr); } .cf-submit { flex-wrap:wrap; } .cf-submit > div { flex-basis:100%; } }
/* The fixed application menus also reduce usable width on a wide desktop. */
@container (max-width:760px) { .cf-window { grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px 14px; } .cf-window-title { grid-column:1/-1; padding:0; } .cf-window-title p { display:none; } }
@container (max-width:520px) { .cf-grid,.cf-window { grid-template-columns:minmax(0,1fr); } .cf-submit { flex-wrap:wrap; } .cf-submit > div { flex-basis:100%; } }
</style>
