<template>
  <section class="aa-bulk" aria-label="批量注册工作区">
    <div class="aa-bulk__head">
      <div>
        <p class="aa-bulk__eyebrow">高频办理</p>
        <h3 class="aa-bulk__title">批量注册</h3>
        <p class="aa-bulk__desc">
          系统自动带入学生、班级、专业、当前学籍状态和资格说明；先预览，再确认。最终仍逐人走正式注册校验与学籍状态流水。
        </p>
      </div>
      <div class="aa-bulk__limit">单次最多 100 人</div>
    </div>

    <div class="aa-bulk__toolbar">
      <label class="aa-bulk__search">
        <span class="sr-only">搜索学生</span>
        <input
          v-model.trim="keyword"
          class="aa-bulk__input"
          type="search"
          placeholder="按姓名或学号搜索"
          @keyup.enter="search"
        />
      </label>
      <AppButton :disabled="loading" @click="search">{{ loading ? '查询中…' : '查询' }}</AppButton>
      <AppButton :disabled="loading || !rows.length" @click="toggleCurrentPage">
        {{ allCurrentPageSelected ? '取消本页选择' : '选择本页' }}
      </AppButton>
    </div>

    <div class="aa-bulk__summary" aria-live="polite">
      <div class="aa-bulk__metric"><strong>{{ total }}</strong><span>当前候选</span></div>
      <div class="aa-bulk__metric"><strong>{{ selectedIds.length }}</strong><span>已选择</span></div>
      <div class="aa-bulk__metric"><strong>{{ preview?.ready || 0 }}</strong><span>预览可执行</span></div>
      <div class="aa-bulk__metric"><strong>{{ preview?.blocked || 0 }}</strong><span>预览阻断</span></div>
    </div>

    <div v-if="error" class="aa-bulk__notice aa-bulk__notice--error" role="alert">
      {{ error }}
      <button type="button" class="aa-bulk__link" @click="load">重新加载</button>
    </div>

    <div v-else-if="loading" class="aa-bulk__notice">正在读取当前批次可注册候选…</div>

    <div v-else-if="!rows.length" class="aa-bulk__empty">
      <strong>当前没有匹配的可注册候选</strong>
      <span>可调整姓名/学号搜索条件，或先到注册资格、异常处理页面完成前置处理。</span>
    </div>

    <div v-else class="aa-bulk__table-wrap">
      <table class="aa-bulk__table">
        <thead>
          <tr>
            <th class="aa-bulk__check-col"><span class="sr-only">选择</span></th>
            <th>学生</th>
            <th>班级 / 专业</th>
            <th>当前学籍状态</th>
            <th>注册资格</th>
            <th>系统说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.studentId" :class="{ 'is-selected': isSelected(row.studentId) }">
            <td class="aa-bulk__check-col">
              <input
                :aria-label="`选择 ${row.realName || row.studentNo}`"
                type="checkbox"
                :checked="isSelected(row.studentId)"
                @change="toggleStudent(row.studentId)"
              />
            </td>
            <td>
              <div class="aa-bulk__student">
                <strong>{{ row.realName || '未命名学生' }}</strong>
                <span>{{ row.studentNo || '—' }}</span>
              </div>
            </td>
            <td>
              <div class="aa-bulk__org">
                <strong>{{ row.className || '班级待完善' }}</strong>
                <span>{{ row.majorName || '专业待完善' }}</span>
              </div>
            </td>
            <td><span class="aa-bulk__pill aa-bulk__pill--neutral">{{ row.currentStatusLabel || '—' }}</span></td>
            <td>
              <span class="aa-bulk__pill" :class="eligibilityClass(row.eligibilityStatus)">
                {{ eligibilityLabel(row.eligibilityStatus) }}
              </span>
            </td>
            <td class="aa-bulk__reason">{{ row.eligibilityExplanation || '系统将在确认时再次校验' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="rows.length" class="aa-bulk__pager">
      <span>第 {{ page }} / {{ totalPages }} 页</span>
      <div>
        <AppButton :disabled="loading || page <= 1" @click="changePage(page - 1)">上一页</AppButton>
        <AppButton :disabled="loading || page >= totalPages" @click="changePage(page + 1)">下一页</AppButton>
      </div>
    </div>

    <div class="aa-bulk__actions">
      <div>
        <strong>已选择 {{ selectedIds.length }} 人</strong>
        <span>预览不会写库；只有确认后才逐人进入正式注册写链。</span>
      </div>
      <AppButton type="primary" :disabled="previewing || applying || !selectedIds.length" @click="makePreview">
        {{ previewing ? '预览中…' : '预览批量注册' }}
      </AppButton>
    </div>

    <div v-if="preview" class="aa-bulk__preview" data-testid="bulk-registration-preview">
      <div class="aa-bulk__preview-head">
        <div>
          <p class="aa-bulk__eyebrow">确认前检查</p>
          <h4>预览结果：{{ preview.ready }} 人可执行，{{ preview.blocked }} 人被阻断</h4>
        </div>
        <span>{{ preview.batchName }}</span>
      </div>

      <ul class="aa-bulk__preview-list">
        <li v-for="item in preview.items" :key="item.studentId">
          <span class="aa-bulk__dot" :class="item.status === 'READY' ? 'is-ready' : 'is-blocked'" />
          <div>
            <strong>{{ item.realName || '不可用候选' }}<template v-if="item.studentNo"> · {{ item.studentNo }}</template></strong>
            <span>{{ item.message }}</span>
          </div>
          <span class="aa-bulk__pill" :class="item.status === 'READY' ? 'aa-bulk__pill--ready' : 'aa-bulk__pill--blocked'">
            {{ item.status === 'READY' ? '可执行' : '已阻断' }}
          </span>
        </li>
      </ul>

      <label class="aa-bulk__confirm-check">
        <input v-model="reviewed" type="checkbox" />
        <span>我已核对本次名单和阻断原因，确认让系统对每名可执行学生再次进行正式校验并注册。</span>
      </label>

      <div class="aa-bulk__preview-actions">
        <AppButton :disabled="applying" @click="cancelPreview">返回调整</AppButton>
        <AppButton type="primary" :disabled="applying || !reviewed || !preview.ready" @click="apply">
          {{ applying ? '正在正式注册…' : `确认注册 ${preview.ready} 人` }}
        </AppButton>
      </div>
    </div>

    <div v-if="result" class="aa-bulk__result" data-testid="bulk-registration-result">
      <strong>本次处理完成：成功 {{ result.succeeded }} 人，未成功 {{ result.failed }} 人。</strong>
      <span v-if="result.failed">未成功项目已保留真实业务原因，可处理后重新发起；系统没有把部分失败伪装成整批成功。</span>
      <span v-else>全部学生均已通过最终校验并进入正式注册事实链。</span>
    </div>
  </section>
</template>

<script>
import { AppButton } from '@/components/ui'
import { rosterRegistrationConvenienceApi } from '@/modules/academicAffairs/api/roster-registration-convenience.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaRegistrationBulkPanel',
  components: { AppButton },
  props: {
    batchId: { type: [String, Number], required: true }
  },
  emits: ['applied'],
  data() {
    return {
      keyword: '',
      page: 1,
      pageSize: 50,
      total: 0,
      rows: [],
      selectedIds: [],
      loading: false,
      error: '',
      previewing: false,
      preview: null,
      reviewed: false,
      applying: false,
      result: null
    }
  },
  computed: {
    totalPages() {
      return Math.max(1, Math.ceil(this.total / this.pageSize))
    },
    allCurrentPageSelected() {
      return this.rows.length > 0 && this.rows.every((row) => this.isSelected(row.studentId))
    }
  },
  created() {
    this.load()
  },
  methods: {
    eligibilityLabel(value) {
      return ({ ELIGIBLE: '已通过', INELIGIBLE: '不通过', PENDING: '待核验' })[value] || value || '待核验'
    },
    eligibilityClass(value) {
      if (value === 'ELIGIBLE') return 'aa-bulk__pill--ready'
      if (value === 'INELIGIBLE') return 'aa-bulk__pill--blocked'
      return 'aa-bulk__pill--pending'
    },
    isSelected(studentId) {
      return this.selectedIds.includes(String(studentId))
    },
    invalidatePreview() {
      this.preview = null
      this.reviewed = false
      this.result = null
    },
    toggleStudent(studentId) {
      const id = String(studentId)
      if (this.isSelected(id)) {
        this.selectedIds = this.selectedIds.filter((value) => value !== id)
      } else if (this.selectedIds.length >= 100) {
        toast.info('单次最多选择 100 名学生')
        return
      } else {
        this.selectedIds = [...this.selectedIds, id]
      }
      this.invalidatePreview()
    },
    toggleCurrentPage() {
      const pageIds = this.rows.map((row) => String(row.studentId))
      if (this.allCurrentPageSelected) {
        this.selectedIds = this.selectedIds.filter((id) => !pageIds.includes(id))
      } else {
        const merged = [...new Set([...this.selectedIds, ...pageIds])]
        if (merged.length > 100) {
          toast.info('选择本页后会超过 100 人，请缩小范围或分批办理')
          return
        }
        this.selectedIds = merged
      }
      this.invalidatePreview()
    },
    async search() {
      this.page = 1
      await this.load()
    },
    async changePage(page) {
      this.page = page
      await this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await rosterRegistrationConvenienceApi.getCandidates(this.batchId, {
        keyword: this.keyword,
        page: this.page,
        pageSize: this.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data.list
        this.total = res.data.total
        if (this.page > this.totalPages) this.page = this.totalPages
      } else {
        this.rows = []
        this.total = 0
        this.error = res.message || '候选名单加载失败'
      }
      this.loading = false
    },
    async makePreview() {
      if (!this.selectedIds.length || this.previewing) return
      this.previewing = true
      this.result = null
      const res = await rosterRegistrationConvenienceApi.previewBulkRegistration(this.batchId, this.selectedIds)
      this.previewing = false
      if (res.code !== 0) {
        toast.error(res.message || '批量注册预览失败')
        return
      }
      this.preview = res.data
      this.reviewed = false
    },
    cancelPreview() {
      this.preview = null
      this.reviewed = false
    },
    async apply() {
      if (!this.preview || !this.reviewed || !this.preview.ready || this.applying) return
      this.applying = true
      const res = await rosterRegistrationConvenienceApi.confirmBulkRegistration(this.batchId, this.selectedIds)
      this.applying = false
      if (res.code !== 0) {
        toast.error(res.message || '批量注册失败')
        return
      }
      this.result = res.data
      this.preview = null
      this.reviewed = false
      this.selectedIds = []
      if (res.data.failed) toast.info(`处理完成：成功 ${res.data.succeeded} 人，未成功 ${res.data.failed} 人`)
      else toast.success(`已完成 ${res.data.succeeded} 人注册`)
      await this.load()
      this.$emit('applied', res.data)
    }
  }
}
</script>

<style scoped>
.aa-bulk { border: 1px solid var(--border-200, #e4e7ec); border-radius: 14px; background: var(--bg-white, #fff); overflow: hidden; }
.aa-bulk__head { display: flex; justify-content: space-between; gap: 24px; padding: 22px 24px 18px; border-bottom: 1px solid var(--border-100, #eef0f3); }
.aa-bulk__eyebrow { margin: 0 0 4px; color: var(--primary-600, #2563eb); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.aa-bulk__title { margin: 0; color: var(--text-900, #1f2329); font-size: 20px; line-height: 1.4; }
.aa-bulk__desc { max-width: 760px; margin: 6px 0 0; color: var(--text-600, #667085); font-size: 13px; line-height: 1.65; }
.aa-bulk__limit { align-self: flex-start; padding: 6px 10px; border: 1px solid var(--primary-100, #dbeafe); border-radius: 999px; color: var(--primary-700, #1d4ed8); background: var(--primary-50, #eff6ff); font-size: 12px; white-space: nowrap; }
.aa-bulk__toolbar { display: flex; gap: 10px; align-items: center; padding: 16px 24px; }
.aa-bulk__search { flex: 1; min-width: 220px; }
.aa-bulk__input { width: 100%; height: 36px; padding: 0 12px; border: 1px solid var(--border-300, #d0d5dd); border-radius: 8px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font: inherit; outline: none; }
.aa-bulk__input:focus { border-color: var(--primary-500, #3b82f6); box-shadow: 0 0 0 3px rgba(59, 130, 246, .1); }
.aa-bulk__summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; padding: 0 24px 16px; }
.aa-bulk__metric { padding: 12px 14px; border: 1px solid var(--border-100, #eef0f3); border-radius: 10px; background: var(--bg-50, #f8fafc); }
.aa-bulk__metric strong { display: block; color: var(--text-900, #1f2329); font-size: 20px; line-height: 1.2; }
.aa-bulk__metric span { display: block; margin-top: 4px; color: var(--text-500, #7a8494); font-size: 12px; }
.aa-bulk__notice, .aa-bulk__empty { margin: 0 24px 16px; padding: 16px; border-radius: 10px; background: var(--bg-50, #f8fafc); color: var(--text-600, #667085); font-size: 13px; }
.aa-bulk__notice--error { color: #b42318; background: #fff4f2; }
.aa-bulk__link { margin-left: 8px; border: 0; background: transparent; color: inherit; text-decoration: underline; cursor: pointer; }
.aa-bulk__empty { display: flex; flex-direction: column; gap: 4px; }
.aa-bulk__empty strong { color: var(--text-800, #344054); }
.aa-bulk__table-wrap { margin: 0 24px; overflow-x: auto; border: 1px solid var(--border-100, #eef0f3); border-radius: 10px; }
.aa-bulk__table { width: 100%; min-width: 900px; border-collapse: collapse; table-layout: fixed; }
.aa-bulk__table th { padding: 10px 12px; background: var(--bg-50, #f8fafc); color: var(--text-500, #667085); font-size: 12px; font-weight: 600; text-align: left; }
.aa-bulk__table td { padding: 12px; border-top: 1px solid var(--border-100, #eef0f3); color: var(--text-700, #475467); font-size: 13px; vertical-align: middle; }
.aa-bulk__table tr.is-selected td { background: #f8fbff; }
.aa-bulk__table th:nth-child(2) { width: 16%; }
.aa-bulk__table th:nth-child(3) { width: 20%; }
.aa-bulk__table th:nth-child(4) { width: 14%; }
.aa-bulk__table th:nth-child(5) { width: 12%; }
.aa-bulk__check-col { width: 34px; text-align: center !important; }
.aa-bulk__student, .aa-bulk__org { display: flex; flex-direction: column; gap: 3px; }
.aa-bulk__student strong, .aa-bulk__org strong { color: var(--text-900, #1f2329); font-weight: 600; }
.aa-bulk__student span, .aa-bulk__org span { color: var(--text-500, #7a8494); font-size: 12px; }
.aa-bulk__reason { line-height: 1.55; word-break: break-word; }
.aa-bulk__pill { display: inline-flex; align-items: center; min-height: 24px; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 600; }
.aa-bulk__pill--ready { color: #067647; background: #ecfdf3; }
.aa-bulk__pill--blocked { color: #b42318; background: #fef3f2; }
.aa-bulk__pill--pending { color: #b54708; background: #fffaeb; }
.aa-bulk__pill--neutral { color: #344054; background: #f2f4f7; }
.aa-bulk__pager { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 24px; color: var(--text-500, #667085); font-size: 12px; }
.aa-bulk__pager > div { display: flex; gap: 8px; }
.aa-bulk__actions { display: flex; justify-content: space-between; gap: 20px; align-items: center; margin: 4px 24px 20px; padding: 14px 16px; border-radius: 10px; background: var(--bg-50, #f8fafc); }
.aa-bulk__actions > div { display: flex; flex-direction: column; gap: 3px; }
.aa-bulk__actions strong { color: var(--text-900, #1f2329); font-size: 13px; }
.aa-bulk__actions span { color: var(--text-500, #667085); font-size: 12px; }
.aa-bulk__preview { margin: 0 24px 20px; padding: 18px; border: 1px solid var(--primary-100, #dbeafe); border-radius: 12px; background: #fbfdff; }
.aa-bulk__preview-head { display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; }
.aa-bulk__preview-head h4 { margin: 0; color: var(--text-900, #1f2329); font-size: 16px; }
.aa-bulk__preview-head > span { color: var(--text-500, #667085); font-size: 12px; }
.aa-bulk__preview-list { margin: 14px 0; padding: 0; list-style: none; border-top: 1px solid var(--border-100, #eef0f3); }
.aa-bulk__preview-list li { display: grid; grid-template-columns: 10px 1fr auto; gap: 10px; align-items: center; padding: 10px 2px; border-bottom: 1px solid var(--border-100, #eef0f3); }
.aa-bulk__preview-list li > div { display: flex; flex-direction: column; gap: 2px; }
.aa-bulk__preview-list strong { color: var(--text-800, #344054); font-size: 13px; }
.aa-bulk__preview-list li > div span { color: var(--text-500, #667085); font-size: 12px; }
.aa-bulk__dot { width: 8px; height: 8px; border-radius: 50%; }
.aa-bulk__dot.is-ready { background: #12b76a; }
.aa-bulk__dot.is-blocked { background: #f04438; }
.aa-bulk__confirm-check { display: flex; gap: 9px; align-items: flex-start; padding: 12px; border-radius: 8px; background: #fff; color: var(--text-700, #475467); font-size: 12px; line-height: 1.55; }
.aa-bulk__confirm-check input { margin-top: 2px; }
.aa-bulk__preview-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
.aa-bulk__result { display: flex; flex-direction: column; gap: 4px; margin: 0 24px 20px; padding: 14px 16px; border-radius: 10px; color: #05603a; background: #ecfdf3; font-size: 13px; }
.aa-bulk__result span { color: #087443; font-size: 12px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 900px) {
  .aa-bulk__head, .aa-bulk__actions, .aa-bulk__preview-head { flex-direction: column; align-items: stretch; }
  .aa-bulk__summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .aa-bulk__toolbar { flex-wrap: wrap; }
  .aa-bulk__search { flex-basis: 100%; }
}
@media (max-width: 560px) {
  .aa-bulk__head, .aa-bulk__toolbar, .aa-bulk__summary, .aa-bulk__pager { padding-left: 16px; padding-right: 16px; }
  .aa-bulk__table-wrap, .aa-bulk__actions, .aa-bulk__preview, .aa-bulk__result, .aa-bulk__notice, .aa-bulk__empty { margin-left: 16px; margin-right: 16px; }
}
</style>
