<template>
  <div v-if="hasQueue" class="rqb">
    <button class="rqb__back" @click="backToList">← 返回列表</button>
    <span class="rqb__pos">
      {{ queue.title || '处理队列' }} · 第 <b>{{ index + 1 }}</b> / {{ total }} 条
    </span>
    <span v-if="finished" class="rqb__done">本队列已全部处理完毕</span>
    <span class="rqb__sp" />
    <button class="rqb__nav" :disabled="!prevId" @click="goPrev">‹ 上一条</button>
    <button class="rqb__nav" :disabled="!nextId" @click="goNext">下一条 ›</button>
  </div>
  <div v-else class="rqb rqb--bare">
    <button class="rqb__back" @click="backToList">← 返回列表</button>
  </div>
</template>

<script>
import { readReviewQueue, queuePosition } from '@/modules/internship/composables/reviewQueue'
import { toast } from '@/utils/toast'

/**
 * ReviewQueueBar — 连续处理导航条（岗位实习模块内部组件）。
 * 由详情页/工作区放在页面顶部：
 *   <ReviewQueueBar ref="queueBar" :current-id="id" kind="weekly-report"
 *                   :make-path="(id) => '/admin/internship/reports/' + id"
 *                   list-fallback="/admin/internship/reports" />
 * 页面在「通过 / 退回」等动作成功后调用 this.$refs.queueBar.advance()：
 * 有下一条 → 自动进入下一条；没有 → 提示队列完成并停留（可返回列表）。
 * 深链直接进入（无队列上下文）时退化为仅「返回列表」。
 */
export default {
  name: 'ReviewQueueBar',
  props: {
    currentId: { type: [String, Number], required: true },
    kind: { type: String, required: true },
    makePath: { type: Function, required: true },
    listFallback: { type: String, required: true }
  },
  data() {
    return { queue: null, finished: false }
  },
  computed: {
    hasQueue() {
      return !!this.queue && this.pos.index > -1
    },
    pos() {
      return this.queue ? queuePosition(this.queue, this.currentId) : { index: -1, total: 0, prevId: '', nextId: '' }
    },
    index() { return this.pos.index },
    total() { return this.pos.total },
    prevId() { return this.pos.prevId },
    nextId() { return this.pos.nextId }
  },
  watch: {
    currentId() { this.finished = false }
  },
  created() {
    this.queue = readReviewQueue(this.kind)
  },
  methods: {
    goPrev() {
      if (this.prevId) this.$router.push(this.makePath(this.prevId))
    },
    goNext() {
      if (this.nextId) this.$router.push(this.makePath(this.nextId))
    },
    /** 处理成功后由页面调用：进入下一条或宣告队列完成 */
    advance() {
      if (this.nextId) {
        this.$router.push(this.makePath(this.nextId))
        return true
      }
      this.finished = true
      if (this.hasQueue) toast.success('本队列已全部处理完毕')
      return false
    },
    backToList() {
      if (this.queue && this.queue.listPath) {
        this.$router.push({ path: this.queue.listPath, query: this.queue.listQuery || {} })
      } else {
        this.$router.push(this.listFallback)
      }
    }
  }
}
</script>

<style scoped>
.rqb {
  display: flex;
  align-items: center;
  gap: var(--space-3, 12px);
  padding: 8px 12px;
  border: 1px solid var(--bd, #e5e7eb);
  border-radius: 10px;
  background: var(--card-bg, #fff);
  font-size: 13px;
}
.rqb--bare {
  border: none;
  background: transparent;
  padding-left: 0;
}
.rqb__back {
  border: 0;
  background: none;
  padding: 0;
  color: var(--brand, #2563eb);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}
.rqb__pos {
  color: var(--t2, #374151);
  white-space: nowrap;
}
.rqb__pos b { font-weight: 700; }
.rqb__done {
  color: var(--success, #059669);
  font-weight: 500;
}
.rqb__sp { flex: 1; }
.rqb__nav {
  height: 28px;
  padding: 0 12px;
  border: 1px solid var(--bd, #d1d5db);
  border-radius: 8px;
  background: var(--card-bg, #fff);
  color: var(--t1, #111827);
  font-size: 12.5px;
  cursor: pointer;
}
.rqb__nav:disabled {
  color: var(--t3, #9ca3af);
  cursor: not-allowed;
  background: var(--fill-2, #f9fafb);
}
</style>
