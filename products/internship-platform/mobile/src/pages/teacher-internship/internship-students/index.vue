<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习学生" subtitle="本批次名单与资格进度" show-back fallback-url="/pages/teacher/workbench/index" />
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view class="page-pad stack">
        <view class="card its__context"><view><text class="its__eyebrow">当前实习批次</text><text class="its__batch">{{ context.selectedBatch?.name || context.selectedBatch?.batchName || '请选择批次' }}</text></view>
          <picker :range="batchLabels" :value="batchIndex" @change="changeBatch"><view class="its__switch">切换 ▾</view></picker>
        </view>
        <view class="its__search"><input v-model="keyword" placeholder="搜索姓名或学号" confirm-type="search" @confirm="search" /><button size="mini" @click="search">搜索</button></view>
        <view class="its__filters"><button v-for="item in filters" :key="item.value" :class="{ 'is-on': eligibility === item.value }" @click="chooseFilter(item.value)">{{ item.label }}</button></view>
        <view class="its__count"><text>{{ total }} 名学生</text><text>点击学生查看实习档案</text></view>
        <MobileGlobalState v-if="!rows.length" state="empty" title="当前条件下暂无学生" description="可调整搜索条件或切换批次。名单按当前身份的数据范围显示。" />
        <view v-for="row in rows" :key="row.id" class="card its__student" @click="openStudent(row)">
          <view class="its__row"><view class="its__avatar">{{ row.name?.slice(0, 1) }}</view><view class="flex-1"><text class="its__name">{{ row.name }}</text><text class="its__meta">{{ maskedNo(row.studentNo) }} · {{ row.className }}</text></view><MobileStatusTag :label="row.eligibilityLabel" :type="tone(row.eligibilityStatus)" /></view>
          <view class="its__placement"><text>{{ row.positionName || row.destinationLabel || '岗位待落实' }}</text><text>{{ row.statusLabel }} ›</text></view>
        </view>
        <view v-if="total > pageSize" class="its__paging"><button size="mini" :disabled="page <= 1" @click="turn(-1)">上一页</button><text>{{ page }} / {{ Math.ceil(total / pageSize) }}</text><button size="mini" :disabled="page * pageSize >= total" @click="turn(1)">下一页</button></view>
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import { useInternshipContextStore } from '@/stores/internshipContext'
import { teacherInternshipRoster } from '@/services/internshipApi'
import { go } from '@/utils/nav'
export default {
  data: () => ({ state: 'loading', error: '', rows: [], total: 0, page: 1, pageSize: 20, keyword: '', eligibility: '', requestedBatch: '', sequence: 0,
    filters: [{ value: '', label: '全部' }, { value: 'PENDING', label: '待认定' }, { value: 'QUALIFIED', label: '合格' }, { value: 'UNQUALIFIED', label: '不合格' }] }),
  computed: {
    context() { return useInternshipContextStore() },
    batchLabels() { return this.context.batches.map((b) => b.name || b.batchName || '实习批次') },
    batchIndex() { return Math.max(0, this.context.batches.findIndex((b) => String(b.id) === this.context.selectedBatchId)) }
  },
  onLoad(query) { this.requestedBatch = String(query?.batchId || '') },
  onShow() { this.load() },
  onUnload() { this.sequence++ },
  methods: {
    tone(status) { return status === 'QUALIFIED' ? 'success' : status === 'UNQUALIFIED' ? 'danger' : 'warning' },
    maskedNo(value) { const no = String(value || ''); return no.length > 4 ? no.slice(0, 2) + '****' + no.slice(-2) : '****' },
    async load() {
      const seq = ++this.sequence; this.state = 'loading'; this.error = ''
      try {
        await this.context.load(true)
        if (seq !== this.sequence) return
        if (this.requestedBatch) {
          if (!this.context.selectBatch(this.requestedBatch)) throw new Error('此批次不在当前可查看范围')
          this.requestedBatch = ''
        }
        if (!this.context.can('internship.student.view')) { this.state = 'forbidden'; return }
        if (!this.context.selectedBatchId) { this.rows = []; this.total = 0; this.state = 'ready'; return }
        const result = await teacherInternshipRoster(this.context.selectedBatchId, { keyword: this.keyword, eligibility: this.eligibility, page: this.page, pageSize: this.pageSize })
        if (seq !== this.sequence) return
        this.rows = result.items || []; this.total = result.total || 0; this.state = 'ready'
      } catch (e) { if (seq === this.sequence) { this.error = e.message || '名单加载失败，请重试'; this.state = 'error' } }
    },
    changeBatch(event) { const batch = this.context.batches[Number(event.detail.value)]; if (batch && this.context.selectBatch(batch.id)) { this.page = 1; this.load() } },
    search() { this.page = 1; this.load() },
    chooseFilter(value) { this.eligibility = value; this.search() },
    turn(direction) { this.page += direction; this.load() },
    openStudent(row) { go('/pages/teacher-internship/internship-students/detail?id=' + encodeURIComponent(row.id) + '&batchId=' + encodeURIComponent(row.batchId)) }
  }
}
</script>
<style scoped>
.its__context,.its__row,.its__placement,.its__paging{display:flex;align-items:center;justify-content:space-between;gap:12px}.its__eyebrow{display:block;font-size:11px;color:var(--text-tertiary)}.its__batch{display:block;font-size:15px;line-height:1.6;font-weight:600;margin-top:5px}.its__switch{font-size:13px;color:var(--brand-primary);white-space:nowrap}
.its__search{display:flex;align-items:center;gap:12px;background:var(--bg-card);border:1px solid var(--border-light);border-radius:10px;padding:8px 12px}.its__search input{flex:1;font-size:14px;min-width:0}.its__search button{margin:0;color:var(--brand-primary);background:transparent}.its__search button::after{border:0}
.its__filters{display:flex;gap:8px}.its__filters button{flex:1;padding:8px 2px;margin:0;font-size:13px;line-height:1.5;color:var(--text-secondary);background:transparent;border-radius:8px}.its__filters button::after{border:0}.its__filters button.is-on{background:var(--brand-50);color:var(--brand-primary);font-weight:600}
.its__count{display:flex;justify-content:space-between;font-size:12px;color:var(--text-tertiary)}.its__avatar{display:flex;align-items:center;justify-content:center;width:38px;height:38px;flex:none;border-radius:12px;color:var(--brand-primary);background:var(--brand-50);font-size:16px}.its__name{display:block;font-size:16px;font-weight:600}.its__meta{display:block;font-size:11px;line-height:1.7;color:var(--text-tertiary);margin-top:3px}.its__placement{border-top:1px solid var(--border-light);padding-top:13px;margin-top:16px;font-size:12px;color:var(--text-secondary)}.its__paging{font-size:12px;color:var(--text-tertiary)}.its__paging button{margin:0}
</style>
