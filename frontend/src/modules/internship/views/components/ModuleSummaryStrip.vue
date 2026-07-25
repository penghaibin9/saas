<template>
  <section class="msr" aria-label="模块概况">
    <!-- 当前批次（全模块统一口径：来自实习总览接口，不在页面伪造） -->
    <div class="msr__batch">
      <span v-if="batchLoading" class="msr__muted">批次信息加载中…</span>
      <template v-else-if="batch">
        <span class="msr__chip msr__chip--batch">当前批次：{{ batch.batchName }}</span>
        <span class="msr__chip" :class="batch.batchStatus === '进行中' ? 'msr__chip--on' : ''">{{ batch.batchStatus }}</span>
        <span class="msr__muted">{{ batch.batchRange }}</span>
      </template>
      <template v-else-if="batchError">
        <span class="msr__muted">批次信息暂不可用</span>
        <button class="msr__link" @click="loadBatch(true)">重试</button>
      </template>
      <template v-else>
        <span class="msr__muted">当前没有进行中的实习批次，请先创建或启用实习批次</span>
        <button class="msr__link" @click="$router.push('/admin/internship/batches')">去批次设置</button>
      </template>
    </div>

    <!-- 模块核心指标（只展示调用方传入的真实数据；没有统计口径就明示，不写常量、不造数） -->
    <div v-if="metrics.length" class="msr__metrics">
      <div v-for="m in metrics" :key="m.label" class="msr__metric">
        <span class="msr__metric-val" :class="m.tone ? 'is-' + m.tone : ''">{{ m.value }}</span>
        <span class="msr__metric-lbl">{{ m.label }}</span>
      </div>
    </div>
    <div v-else-if="note" class="msr__note">{{ note }}</div>

    <!-- 待处理（真实队列数，点击直达） -->
    <div v-if="pending.length" class="msr__pending">
      <button
        v-for="p in pending"
        :key="p.label"
        class="msr__todo"
        :class="{ 'is-zero': !p.count }"
        @click="goPending(p)"
      >
        <span class="msr__todo-count">{{ p.count }}</span>
        <span class="msr__todo-lbl">{{ p.label }}</span>
      </button>
    </div>
  </section>
</template>

<script>
import { internshipApi } from '@/modules/internship/api/internship.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

/** 模块级缓存：同一次会话内 12 个模块主页共用一次批次概况请求（按批次缓存，切批次自动失效） */
let _batchCache = null
let _batchCacheKey = ''
function fetchBatchSummary(force, batchId) {
  const key = String(batchId || '')
  if (force || !_batchCache || _batchCacheKey !== key) {
    _batchCacheKey = key
    // 批次上下文必需：无 batchId 时不打后端（岗位实习总览强制要求 batchId，空参会 400）
    _batchCache = internshipApi.getDashboardSummary({ batchId: key }).catch((e) => {
      _batchCache = null
      _batchCacheKey = ''
      throw e
    })
  }
  return _batchCache
}

/**
 * ModuleSummaryStrip — 岗位实习中心二级模块主页统一「任务化摘要条」。
 * 职责：当前批次（统一来自实习总览接口）+ 模块真实指标 + 待处理直达。
 * 铁律：指标与待办一律由调用方传入真实接口数据；本组件不造数、不写常量、
 * 没有统计口径时由调用方传 note（如「暂无统计口径」）明示。
 */
export default {
  name: 'ModuleSummaryStrip',
  props: {
    /** [{ label, value, tone?: 'good'|'warn'|'bad' }] 仅真实数据 */
    metrics: { type: Array, default: () => [] },
    /** [{ label, count, to }] 待处理队列（count 为真实数，to 为跳转路由） */
    pending: { type: Array, default: () => [] },
    /** 指标缺失时的说明文案（业务语言，如「暂无统计口径」） */
    note: { type: String, default: '' }
  },
  data() {
    return { batch: null, batchLoading: true, batchError: false }
  },
  created() {
    this.loadBatch()
  },
  methods: {
    async loadBatch(force = false) {
      this.batchLoading = true
      this.batchError = false
      const batchId = useInternshipBatchStore().selectedBatchId
      // 未选定批次：不请求总览接口（避免空 batchId 触发 400），直接给出「去批次设置」引导
      if (!batchId) {
        this.batch = null
        this.batchLoading = false
        return
      }
      try {
        const res = await fetchBatchSummary(force, batchId)
        if (res && res.code === 0 && res.data && res.data.batchName) {
          this.batch = res.data
        } else {
          this.batch = null
        }
      } catch {
        this.batch = null
        this.batchError = true
      } finally {
        this.batchLoading = false
      }
    },
    goPending(p) {
      if (!p.to) return
      if (p.to !== this.$route.fullPath) this.$router.push(p.to)
    }
  }
}
</script>

<style scoped>
.msr {
  display: flex;
  align-items: center;
  gap: 12px var(--space-5, 20px);
  flex-wrap: wrap;
  padding: 12px 16px;
  border: 1px solid var(--pri-100, var(--bd, #e5e7eb));
  border-radius: 14px;
  background: linear-gradient(105deg, var(--pri-bg, #f8fbff), var(--card-bg, #fff) 42%);
  box-shadow: 0 4px 12px rgba(15, 23, 42, .035);
}
.msr__batch {
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
  flex-wrap: wrap;
  padding-right: var(--space-4, 16px);
  border-right: 1px solid var(--card-b, #edf0f3);
}
.msr__chip {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 14px;
  font-size: 12px;
  background: rgba(255, 255, 255, .82);
  border: 1px solid var(--card-b, #e5e7eb);
  color: var(--t2, #374151);
  white-space: nowrap;
}
.msr__chip--batch {
  font-weight: var(--font-weight-medium, 500);
  color: var(--pri, #2563eb);
  border-color: var(--pri-100, #dbeafe);
}
.msr__chip--on {
  background: var(--success-bg, #ecfdf5);
  color: var(--success, #059669);
}
.msr__muted {
  font-size: 12px;
  color: var(--t3, #9ca3af);
}
.msr__link {
  border: 0;
  background: none;
  padding: 0;
  font-size: 12px;
  color: var(--brand, #2563eb);
  cursor: pointer;
}
.msr__metrics {
  display: flex;
  align-items: center;
  gap: 8px 18px;
  flex-wrap: wrap;
}
.msr__metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 58px;
}
.msr__metric-val {
  font-size: 20px;
  line-height: 1;
  font-weight: var(--font-weight-bold, 700);
  color: var(--t1, #111827);
}
.msr__metric-val.is-warn {
  color: var(--warning, #d97706);
}
.msr__metric-val.is-bad {
  color: var(--danger, #dc2626);
}
.msr__metric-val.is-good {
  color: var(--success, #059669);
}
.msr__metric-lbl {
  font-size: 11px;
  color: var(--t3, #6b7280);
}
.msr__note {
  font-size: 12px;
  color: var(--t3, #9ca3af);
}
.msr__pending {
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
  flex-wrap: wrap;
  margin-left: auto;
  padding-left: var(--space-4, 16px);
  border-left: 1px solid var(--card-b, #edf0f3);
}
.msr__todo {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  padding: 0 12px;
  border-radius: 16px;
  border: 1px solid var(--warning-bd, #fde68a);
  background: var(--warning-bg, #fffbeb);
  color: var(--t2, #92400e);
  font-size: 12px;
  cursor: pointer;
  transition: .16s ease;
}
.msr__todo:hover:not(.is-zero) {
  border-color: var(--warning, #d97706);
  box-shadow: 0 3px 8px rgba(180, 83, 9, .12);
  transform: translateY(-1px);
}
.msr__todo.is-zero {
  border-color: var(--bd, #e5e7eb);
  background: var(--fill-2, #f9fafb);
  color: var(--t3, #9ca3af);
}
.msr__todo-count {
  font-weight: var(--font-weight-bold, 700);
}
@media (max-width: 900px) {
  .msr__batch, .msr__pending { width: 100%; padding-left: 0; padding-right: 0; border: 0; }
  .msr__pending { margin-left: 0; }
}
</style>
