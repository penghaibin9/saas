/**
 * 列表分批渲染 mixin（上拉加载）
 * ------------------------------------------------------------
 * 背景：mobile 列表接口后端已按上限（如 30/60/80）返回，不会一次性吐全校数据；
 * 但页面若一次性把整段数组渲染出来，长列表仍会造成首屏 setData 过大、滚动卡顿。
 * 本 mixin 提供「渐进渲染」：初始只渲染 pageSize 条，滚动到底（onReachBottom）追加一批。
 * 它不改变网络请求，也不做假分页——纯粹降低单次渲染节点数，并给出标准上拉体验与到底提示。
 *
 * 重要（mp-weixin 限制）：uni-app 在编译 mp-weixin 时，**不会**把 mixin 里的页面生命周期
 * （onReachBottom/onPullDownRefresh 等）注入到页面 Page() 配置里——只有写在页面组件本身的才生效。
 * 因此本 mixin 只提供数据与方法，onReachBottom 必须写在各页面里，转调 this.pagedReachBottom()。
 *
 * 用法：
 *   import { listPaging } from '@/utils/listPaging'
 *   export default {
 *     mixins: [listPaging(20)],
 *     onReachBottom() { this.pagedReachBottom() },   // ← 必须写在页面本身（mp-weixin 才会注册）
 *     methods: { pagingList() { return this.当前完整数组 } }  // 供上拉时判断是否还有更多
 *   }
 *   模板：
 *     <view v-for="x in pagedSlice(fullList)" :key="x.id">…</view>
 *     <view v-if="pagedFooter(fullList) === 'more'" class="paging-tip" @click="pagedLoadMore">上拉加载更多</view>
 *     <view v-else-if="pagedFooter(fullList) === 'end'" class="paging-tip">没有更多了</view>
 *   切换 tab / 筛选时重置到第一批：
 *     watch: { tab() { this.pagedReset() } }
 */
export function listPaging(pageSize = 20) {
  const size = Math.max(1, pageSize)
  return {
    data() {
      return { pagerShown: size, pagerSize: size }
    },
    methods: {
      /** 取当前应渲染的前 N 条 */
      pagedSlice(arr) {
        const a = Array.isArray(arr) ? arr : []
        return a.slice(0, this.pagerShown)
      },
      /** 底部状态：'more'=还有更多 / 'end'=已全部展示（空列表返回 '' 交给页面空态处理） */
      pagedFooter(arr) {
        const total = Array.isArray(arr) ? arr.length : 0
        if (total === 0) return ''
        return this.pagerShown < total ? 'more' : 'end'
      },
      /** 回到第一批（切换 tab/筛选/下拉刷新时调用） */
      pagedReset() {
        if (this.pagerShown !== this.pagerSize) this.pagerShown = this.pagerSize
      },
      /** 追加一批 */
      pagedLoadMore() {
        this.pagerShown += this.pagerSize
      },
      /** 页面 onReachBottom 转调此方法：页面若提供 pagingList()，仅在确有更多时增长，
       *  避免滚动到底反复触发导致 pagerShown 无界增大 */
      pagedReachBottom() {
        if (typeof this.pagingList === 'function') {
          const arr = this.pagingList() || []
          if (this.pagerShown < arr.length) this.pagedLoadMore()
        } else {
          this.pagedLoadMore()
        }
      }
    }
  }
}

export default listPaging
