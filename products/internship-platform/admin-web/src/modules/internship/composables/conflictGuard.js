/**
 * 岗位实习 · 写操作冲突（409）统一处置（模块内部，能力不出中心）。
 *
 * 背景：上一批给巡访计划、投诉、企业考察等写链加了条件更新（版本 + 期望状态），
 * 两人撞车时输家现在拿到 409 而不是静默覆盖。后端更严谨了，但前端如果只弹一个
 * 错误 toast，老师刚敲的整段处理意见就跟着弹窗一起没了——体感反而更糟。
 *
 * 本文件提供三件事：
 * 1. `isConflict(res)`  判定这次失败是不是撞车（而不是无权限/参数错）；
 * 2. `captureConflict()` 撞车后拉一次最新真值，生成提示状态；
 * 3. `emptyConflict()`  重新打开弹窗/切换记录时清场。
 *
 * 三条红线：
 * - **不清空老师填的内容**：调用方在冲突分支里只 return，不动表单、不关弹窗；
 * - **不自动重放**：绝不替老师再提交一次，最新状态摆出来由他自己决定覆盖还是放弃；
 * - **不伪造真值**：刷新失败就如实标 stale，不拿旧数据冒充最新。
 */

/** 后端 fail() 的数字码：DATA_CONFLICT / APPROVAL_VERSION_CONFLICT 都映射到 409001 */
export const CONFLICT_CODE = 409001

/** 字符串契约码（bizCode）；模块内 api 包装层目前只透传数字 code，这里一并兜住 */
export const CONFLICT_BIZ_CODES = ['DATA_CONFLICT', 'APPROVAL_VERSION_CONFLICT']

export const CONFLICT_HINT = '这条记录刚被其他人处理过，下面是最新状态，请确认后重新提交'

/**
 * 是否为写冲突。
 * @param {{code?:number|string, bizCode?:string}|null} res 模块 api 包装层返回的响应
 */
export function isConflict(res) {
  if (!res || res.code === 0) return false
  if (Number(res.code) === CONFLICT_CODE) return true
  const codes = [res.bizCode, typeof res.code === 'string' ? res.code : '']
  return codes.some((c) => CONFLICT_BIZ_CODES.includes(c))
}

/** 弹窗打开 / 切换记录时的初始态 */
export function emptyConflict() {
  return { active: false, message: '', detail: '', latest: [], stale: false, kept: '' }
}

/**
 * 撞车善后：拉一次最新真值，生成给老师看的提示状态。
 *
 * @param {object} opts
 * @param {object} opts.res      失败响应（取后端原文作为补充说明）
 * @param {Function} [opts.refresh] 重新拉取详情的异步函数；抛错时标 stale，不静默吞掉
 * @param {Function} [opts.latest]  refresh 之后调用，返回 [{label, value}] 给老师看的最新字段
 * @param {string} [opts.kept]   老师刚填的正文。刷新真值后，如果这条记录已经被别人办完，
 *                               页面上的表单会整块换成「已处理」态、输入框跟着消失——
 *                               把原文带在提示里还给他，至少能复制走，不算白敲。
 * @returns {Promise<{active:boolean,message:string,detail:string,latest:Array,stale:boolean,kept:string}>}
 */
export async function captureConflict({ res, refresh, latest, kept = '' } = {}) {
  const state = {
    active: true,
    message: CONFLICT_HINT,
    detail: (res && res.message) || '',
    latest: [],
    stale: false,
    kept: kept || ''
  }
  if (typeof refresh === 'function') {
    try {
      await refresh()
    } catch {
      state.stale = true
      return state
    }
  }
  if (typeof latest === 'function') {
    try {
      state.latest = latest() || []
    } catch {
      state.stale = true
    }
  }
  return state
}
