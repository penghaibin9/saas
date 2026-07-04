/**
 * 统一业务异常类型
 * ───────────────────────────────────────────────────────────
 * Service/Domain 层抛出 AppError，由全局错误中间件统一转成 { success:false, code, message }。
 *   throw new AppError('FORBIDDEN', '只能批阅本人指导报告', 403)
 *   AppError.notFound('报告不存在')
 */
class AppError extends Error {
  constructor(code, message, status = 400, data = null) {
    super(message);
    this.name = 'AppError';
    this.isAppError = true;
    this.code = code || 'BAD_REQUEST';
    this.status = status;
    this.data = data;
  }
  static badRequest(msg, data) { return new AppError('BAD_REQUEST', msg, 400, data); }
  static unauthorized(msg) { return new AppError('UNAUTHORIZED', msg || '未认证', 401); }
  static forbidden(msg) { return new AppError('FORBIDDEN', msg || '权限不足', 403); }
  static notFound(msg) { return new AppError('NOT_FOUND', msg || '资源不存在', 404); }
  static conflict(msg, data) { return new AppError('CONFLICT', msg, 409, data); }
  static badState(msg) { return new AppError('BAD_STATE', msg, 400); }
}

module.exports = { AppError };
