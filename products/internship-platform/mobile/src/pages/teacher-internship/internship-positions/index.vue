<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="岗位核对" subtitle="查看指导批次的岗位安排与条件" show-back fallback-url="/pages/teacher/workbench/index" />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack">
        <view class="card ip__context"><view><text class="ip__eyebrow">当前实习批次</text><text class="ip__batch">{{ context.selectedBatch?.name || '暂无指导批次' }}</text></view><picker :range="batchLabels" :value="batchIndex" @change="changeBatch"><text class="ip__switch">切换 ▾</text></picker></view>
        <view class="ip__search"><input v-model="keyword" maxlength="100" placeholder="搜索岗位或企业" confirm-type="search" @confirm="search" /><button size="mini" @click="search">搜索</button></view>
        <view class="ip__filters" role="radiogroup" aria-label="岗位状态筛选"><button v-for="filter in filters" :key="filter.value" role="radio" :aria-checked="status === filter.value" :class="{ 'is-on': status === filter.value }" @click="chooseFilter(filter.value)">{{ filter.label }}</button></view>
        <view class="ip__count"><text>{{ total }} 个岗位</text><text>核对资料 · 只读</text></view>
        <MobileGlobalState v-if="!rows.length" state="empty" title="当前条件下暂无岗位" description="可调整筛选或切换指导批次。岗位审核和发布由学校经办人办理。" />
        <button v-for="row in rows" :key="row.id" class="card ip__position" role="button" :aria-label="`${row.title}，${row.companyName || '企业信息待核对'}，${row.statusLabel}，查看岗位详情`" @click="openPosition(row)">
          <view class="ip__row"><text class="ip__title">{{ row.title }}</text><MobileStatusTag :label="row.statusLabel" :type="row.statusTone" /></view>
          <text class="ip__company">{{ row.companyName || '企业信息待核对' }}</text>
          <text class="ip__meta">{{ row.workLocation || '地区待补充' }} · {{ row.majorRequirement || '专业要求未说明' }}</text>
          <view class="ip__bottom"><text>{{ row.salaryRange || '报酬条件见详情' }}</text><text>剩余 {{ row.remaining ?? '—' }} / {{ row.headcount ?? '—' }} 人　›</text></view>
        </button>
        <view v-if="total > pageSize" class="ip__paging"><button size="mini" :disabled="page <= 1" @click="turn(-1)">上一页</button><text>{{ page }} / {{ Math.ceil(total / pageSize) }}</text><button size="mini" :disabled="page * pageSize >= total" @click="turn(1)">下一页</button></view>
        <MobileInlineAlert type="info" description="岗位上架不等于每位学生当前可选；还需符合招聘季开放范围和本人的资格条件。" />
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import { useInternshipContextStore } from '@/stores/internshipContext'
import { teacherInternshipPositions } from '@/services/internshipApi'
import { positionFilters, positionQuery, positionListUrl, positionDetailUrl } from '@/modules/internshipPositionModel'
import { go } from '@/utils/nav'
export default {
  data: () => ({ state: 'loading', error: '', rows: [], total: 0, page: 1, pageSize: 20, keyword: '', status: '', requestedBatch: '', sequence: 0, filters: positionFilters }),
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.context.batches.map(batch => batch.name || '实习批次') },
    batchIndex() { return Math.max(0, this.context.batches.findIndex(batch => String(batch.id) === this.context.selectedBatchId)) },
    query() { return { batchId: this.context.selectedBatchId, keyword: this.keyword, status: this.status, page: this.page } }
  },
  onLoad(query) { const parsed = positionQuery(query); this.requestedBatch = parsed.batchId; this.page = parsed.page; this.keyword = parsed.keyword; this.status = parsed.status },
  onShow() { this.load() },
  onUnload() { this.sequence++ },
  methods: {
    async load() {
      const sequence = ++this.sequence; this.state = 'loading'; this.error = ''; this.rows = []; this.total = 0
      try {
        await this.context.load(true)
        if (sequence !== this.sequence) return
        if (this.requestedBatch) {
          if (!this.context.selectBatch(this.requestedBatch)) throw new Error('此批次不在当前指导学生范围内')
          this.requestedBatch = ''
        }
        if (!this.context.can('internship.position.view')) { this.state = 'forbidden'; return }
        if (!this.context.selectedBatchId) { this.state = 'ready'; return }
        const result = await teacherInternshipPositions(this.context.selectedBatchId, { keyword: this.keyword, status: this.status, page: this.page, pageSize: this.pageSize })
        if (sequence !== this.sequence) return
        if (String(result.batchId) !== this.context.selectedBatchId) throw new Error('岗位批次不一致，请重新读取')
        this.rows = result.items || []; this.total = result.total || 0; this.state = 'ready'
      } catch (e) { if (sequence === this.sequence) { this.error = e.message || '岗位暂时无法读取'; this.state = 'error' } }
    },
    navigate(query) { if (this.state === 'ready') uni.redirectTo({ url: positionListUrl(query) }) },
    search() { this.navigate({ ...this.query, page: 1 }) },
    chooseFilter(status) { this.navigate({ ...this.query, status, page: 1 }) },
    changeBatch(event) { const batch = this.context.batches[Number(event.detail.value)]; if (batch) this.navigate({ ...this.query, batchId: batch.id, page: 1 }) },
    turn(step) { const page = this.page + step; if (page > 0 && page <= Math.ceil(this.total / this.pageSize)) this.navigate({ ...this.query, page }) },
    openPosition(row) { if (this.state === 'ready') go(positionDetailUrl(row.id, this.query)) }
  }
}
</script>
<style scoped>
.ip__context,.ip__row,.ip__count,.ip__bottom,.ip__paging{display:flex;align-items:center;justify-content:space-between;gap:12px}.ip__eyebrow,.ip__company,.ip__meta{display:block;color:var(--text-tertiary);font-size:12px;line-height:1.7}.ip__batch{display:block;font-size:16px;font-weight:600;margin-top:5px}.ip__switch{color:var(--brand-primary);font-size:13px;white-space:nowrap}.ip__search{display:flex;align-items:center;gap:12px;background:var(--bg-card);border:1px solid var(--border-light);border-radius:10px;padding:8px 12px}.ip__search input{flex:1;min-width:0;font-size:14px}.ip__search button{margin:0;background:transparent;color:var(--brand-primary)}.ip__search button::after,.ip__position::after,.ip__filters button::after{border:0}.ip__filters{display:flex;flex-wrap:wrap;gap:8px}.ip__filters button{display:flex;align-items:center;justify-content:center;flex:0 0 auto;min-height:40px;margin:0;padding:6px 12px;font-size:12px;line-height:1.5;background:var(--bg-card);color:var(--text-secondary);border:1px solid var(--border-light);border-radius:999px}.ip__filters .is-on{background:var(--brand-50);border-color:var(--brand-200);color:var(--brand-primary);font-weight:600}.ip__count,.ip__paging{font-size:12px;color:var(--text-tertiary)}.ip__position{display:block;width:100%;margin:0;text-align:left;line-height:1.6}.ip__row{align-items:flex-start}.ip__title{font-size:17px;font-weight:600;flex:1;min-width:0;overflow-wrap:anywhere}.ip__company{font-size:14px;color:var(--text-secondary);margin:8px 0}.ip__meta{overflow-wrap:anywhere}.ip__bottom{border-top:1px solid var(--border-light);padding-top:13px;margin-top:16px;font-size:12px;color:var(--text-secondary);flex-wrap:wrap}.ip__paging button{margin:0}
</style>
