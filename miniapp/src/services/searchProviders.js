/**
 * V3 §9.4 Shared Search Shell 的 side-aware provider。
 * common/search 只负责输入、防抖、结果框架与 epoch；数据源由 side provider 决定。
 * Teacher T9 改走服务端 Teacher Messages filter，不再搜索本机 stash。
 */
import { studentSearch } from '@/services/realApi'
import { getTeacherMessagesPage } from '@/services/teacherMessagesV3Api'

export const MIN_KEYWORD_LENGTH = 2

const studentProvider = {
  side: 'student', serverSide: true, placeholder: '搜索本人消息、通知与办理',
  async search(keyword) {
    const data = await studentSearch(keyword, 20)
    return { items: (data && data.items) || [], note: (data && data.note) || '' }
  }
}

const teacherProvider = {
  side: 'teacher', serverSide: true, placeholder: '搜索教师消息标题',
  async search(keyword) {
    const data = await getTeacherMessagesPage({ tab: 'all', q: keyword, pageSize: 20 })
    return {
      items: ((data && data.items) || []).map((row) => ({ ...row, summary: row.module || '教师消息', stashed: row })),
      note: data && data.nextCursor ? '显示前 20 条匹配结果，请缩小关键词继续查找' : ''
    }
  }
}

export function resolveSearchProvider(side) {
  return side === 'teacher' ? teacherProvider : studentProvider
}

export default resolveSearchProvider
