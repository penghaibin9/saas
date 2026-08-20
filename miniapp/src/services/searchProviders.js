/**
 * V3 §9.4 Shared Search Shell 的 side-aware provider。
 *
 * common/search 是两端共用的壳。V3 深审 P0-10：如果 Student 分支把它改成
 * student-only 的服务端搜索，教师端的消息搜索就被一起改坏了。
 *
 * 因此壳只负责输入框、防抖、结果框架与 epoch 失效，**不绑定任何一端的 API**；
 * 具体搜什么由这里按 side 分流：
 *   - student：服务端受限搜索（仅本人可见的消息/办理）；
 *   - teacher：教师侧尚未接入服务端搜索（Teacher T8/T9 的范围），
 *     暂时保留原有的本地消息 stash 行为，不冒充服务端能力。
 */
// 注意：本模块被主包页面 common/search 引用，因此只能依赖 realApi（无 mock 图），
// 不能 import studentApi/teacherApi —— 否则会把两端 API 与 mock 重新提升进主包（S1.5）。
import { studentSearch } from '@/services/realApi'
import { getSearchPool } from '@/utils/msgStash'

export const MIN_KEYWORD_LENGTH = 2

/** 学生端：服务端受限搜索。范围与脱敏由后端保证，客户端不放宽。 */
const studentProvider = {
  side: 'student',
  serverSide: true,
  placeholder: '搜索本人消息、通知与办理',
  async search(keyword) {
    const data = await studentSearch(keyword, 20)
    return {
      items: (data && data.items) || [],
      note: (data && data.note) || ''
    }
  }
}

/**
 * 教师端：仍是本地消息 stash 过滤。
 * 明确标 serverSide=false，页面据此提示「仅搜索已加载的消息」，不假装是全量检索。
 */
const teacherProvider = {
  side: 'teacher',
  serverSide: false,
  placeholder: '搜索已加载的消息标题',
  async search(keyword) {
    const value = String(keyword || '').trim().toLowerCase()
    const pool = getSearchPool() || []
    const items = pool
      .filter((row) => `${row.title || ''}${row.module || ''}`.toLowerCase().includes(value))
      .map((row) => ({
        kind: 'MESSAGE',
        id: `stash:${row.id}`,
        title: row.title,
        summary: row.module || '消息',
        time: row.time,
        action: null,
        stashed: row
      }))
    return { items, note: '仅搜索本机已加载的消息' }
  }
}

export function resolveSearchProvider(side) {
  return side === 'teacher' ? teacherProvider : studentProvider
}

export default resolveSearchProvider
