import { graduationTeacherPagingApi } from './graduationTeacherPagingApi'

// 各毕设队列共用服务端分页合同；批次切换/刷新会使旧分页响应失效。
export function graduationTeacherQueue(names) {
  return {
    data() {
      return { graduationQueues: Object.fromEntries(names.map(name => [name, {
        items: [], page: 0, total: 0, hasMore: false, loading: false, error: '', epoch: 0
      }])) }
    },
    methods: {
      resetGraduationQueues() {
        for (const queue of Object.values(this.graduationQueues)) {
          queue.epoch++
          Object.assign(queue, { items: [], page: 0, total: 0, hasMore: false, loading: false, error: '' })
        }
      },
      async loadGraduationQueue(name, append = false) {
        const queue = this.graduationQueues[name]
        if (append && (queue.loading || !queue.hasMore)) return false
        const epoch = ++queue.epoch
        const page = append ? queue.page + 1 : 1
        queue.loading = true
        queue.error = ''
        if (!append) Object.assign(queue, { items: [], page: 0, total: 0, hasMore: false })
        try {
          const rows = await graduationTeacherPagingApi[name](page)
          if (epoch !== queue.epoch) return false
          const meta = rows._pageMeta || {}
          queue.items = append ? [...queue.items, ...rows] : rows
          queue.page = meta.page ?? page
          queue.total = meta.total ?? queue.items.length
          queue.hasMore = !!meta.hasMore
          return true
        } catch (error) {
          if (epoch === queue.epoch) queue.error = error?.message || '加载失败，请重试'
          return false
        } finally {
          if (epoch === queue.epoch) queue.loading = false
        }
      }
    }
  }
}
