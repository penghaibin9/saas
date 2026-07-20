<template>
  <ModulePageShell title="职业教育国家标准库" subtitle="检索教育部专业目录与专业教学标准，并绑定到学校真实专业"
    :role-name="ctx.currentRole.roleName" :data-scope-name="ctx.dataScope.scopeName">
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <ModuleHero title="国家标准全文库" subtitle="保留官方来源、版本、PDF哈希和结构化章节；不替代学校人才培养方案"
          :stats="heroStats" />
        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">搜索官方目录、简介与标准正文</span><span class="mp-note">可搜专业代码、专业名称、课程和岗位关键词</span></header>
          <div class="mp-card__body standard-search">
            <input v-model.trim="filters.keyword" placeholder="例如：510203、软件技术、Java、岗位实习" @keyup.enter="search" />
            <select v-model="filters.educationLevel"><option value="">全部层次</option><option value="SECONDARY_VOCATIONAL">中职</option><option value="HIGHER_VOCATIONAL_SPECIALIST">高职专科</option><option value="VOCATIONAL_BACHELOR">职业本科</option></select>
            <select v-model="filters.documentType"><option value="">全部文档</option><option value="PROFESSIONAL_TEACHING_STANDARD">2025 专业教学标准</option><option value="PROFESSIONAL_PROFILE">2022 专业简介</option></select>
            <select v-model="filters.textStatus"><option value="">全部正文状态</option><option value="EXTRACTED">全文已提取</option><option value="EXTRACTION_FAILED">提取待重试</option></select>
            <button class="mp-btn mp-btn--primary" @click="search">搜索</button>
          </div>
        </section>
        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">检索结果（{{ result.total }}）</span><span class="mp-note">引用时以官方来源和当前有效版本为准</span></header>
          <div class="mp-card__body">
            <p v-if="!result.list.length" class="mp-note">暂无符合条件的标准；若库尚未同步，请由平台管理员运行官方同步任务。</p>
            <article v-for="item in result.list" :key="item.id" class="standard-row">
              <div><b>{{ item.majorCode }} · {{ item.majorName }}</b><small>{{ typeLabel(item.documentType) }} · {{ levelLabel(item.educationLevel) }} · {{ item.categoryName }} / {{ item.majorClassName }} · {{ item.versionLabel }}</small><p>{{ item.snippet || '正文未公开，仅保留官方目录元数据' }}</p></div>
              <StatusTag :type="item.textStatus === 'EXTRACTED' ? 'success' : 'warning'" :label="item.textStatus" />
              <button class="mp-btn" @click="openDetail(item.id)">查看章节</button>
            </article>
          </div>
        </section>
        <section v-if="detail" class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">{{ detail.title }}</span><a :href="detail.sourceUrl" target="_blank" rel="noopener noreferrer">教育部原始来源</a></header>
          <div class="mp-card__body">
            <div class="standard-meta">{{ typeLabel(detail.documentType) }} · {{ detail.majorCode }} · {{ detail.versionLabel }} · {{ detail.pageCount }}页 · {{ detail.charCount }}字</div>
            <div class="bind-bar"><select v-model="binding.schoolMajorId"><option value="">选择本校专业（可选绑定）</option><option v-for="m in schoolMajors" :key="m.id" :value="m.id">{{ m.code || '无代码' }} · {{ m.name }}</option></select><input v-model.trim="binding.confirmText" placeholder="代码不一致时输入：确认跨专业绑定" /><button class="mp-btn mp-btn--primary" :disabled="!binding.schoolMajorId" @click="bindStandard">绑定为本校执行依据</button></div>
            <details v-for="section in detail.sections" :key="section.code" class="standard-section"><summary>{{ section.no }}. {{ section.title }}</summary><pre>{{ section.content }}</pre></details>
          </div>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleHero, StatusTag, LoadingState, ErrorState } from '@/components/business'
import { standardsApi } from '@/modules/system/api/standards.api'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

export default {
  name: 'NationalStandardsView', components: { ModulePageShell, ModuleHero, StatusTag, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() { return { loading: true, error: '', stats: {}, result: { list: [], total: 0 }, detail: null, schoolMajors: [], filters: { keyword: '', educationLevel: '', documentType: '', textStatus: '', page: 1, pageSize: 30 }, binding: { schoolMajorId: '', confirmText: '' } } },
  computed: { heroStats() { return [{ label: '官方专业目录', value: String(this.stats.majors || 0), tone: 'primary' }, { label: '2025 教学标准', value: String(this.stats.teachingStandards || 0), tone: 'success' }, { label: '2022 专业简介', value: String(this.stats.professionalProfiles || 0), tone: 'info' }] } },
  created() { this.load() },
  methods: {
    levelLabel(value) { return ({ SECONDARY_VOCATIONAL: '中职', HIGHER_VOCATIONAL_SPECIALIST: '高职专科', VOCATIONAL_BACHELOR: '职业本科' })[value] || value },
    typeLabel(value) { return ({ PROFESSIONAL_TEACHING_STANDARD: '专业教学标准', PROFESSIONAL_PROFILE: '专业简介' })[value] || value },
    flattenMajors(tree) { return (tree || []).flatMap((college) => (college.children || []).filter((x) => x.type === 'MAJOR')) },
    async load() { this.loading = true; this.error = ''; try { const [stats, result, org] = await Promise.all([standardsApi.stats(), standardsApi.documents(this.filters), systemApi.getDepartmentTree()]); this.stats = stats; this.result = result; this.schoolMajors = this.flattenMajors(org.data || org) } catch (e) { this.error = e.message || '国家标准库加载失败' } finally { this.loading = false } },
    async search() { try { this.result = await standardsApi.documents(this.filters); this.detail = null } catch (e) { toast.error(e.message || '搜索失败') } },
    async openDetail(id) { try { this.detail = await standardsApi.detail(id); this.binding = { schoolMajorId: '', confirmText: '' } } catch (e) { toast.error(e.message || '标准正文加载失败') } },
    async bindStandard() { try { await standardsApi.bind({ schoolMajorId: this.binding.schoolMajorId, documentId: this.detail.id, confirmText: this.binding.confirmText }); toast.success('已绑定国家标准，学校仍可在此基础上制定更高要求') } catch (e) { toast.error(e.message || '绑定失败') } }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.standard-search,.bind-bar{display:flex;gap:var(--space-3);align-items:center;flex-wrap:wrap}.standard-search input{min-width:340px}.standard-search input,.standard-search select,.bind-bar input,.bind-bar select{border:1px solid var(--border-light);border-radius:var(--radius-md);padding:9px 11px;background:var(--bg-card);color:var(--text-primary)}.standard-row{display:flex;gap:var(--space-3);align-items:center;padding:var(--space-3) 0;border-bottom:1px dashed var(--border-light)}.standard-row>div{flex:1}.standard-row small{display:block;color:var(--text-tertiary);margin-top:4px}.standard-row p{margin:8px 0 0;color:var(--text-secondary);line-height:1.6}.standard-meta{margin-bottom:var(--space-3);color:var(--text-secondary)}.bind-bar{padding:var(--space-3);margin-bottom:var(--space-3);background:var(--bg-section-blue);border-radius:var(--radius-md)}.standard-section{border-top:1px solid var(--border-light);padding:var(--space-3) 0}.standard-section summary{cursor:pointer;font-weight:600}.standard-section pre{white-space:pre-wrap;word-break:break-word;font-family:inherit;line-height:1.8;color:var(--text-secondary)}@media(max-width:900px){.standard-row{align-items:flex-start;flex-direction:column}.standard-search input{min-width:0;width:100%}}
</style>
