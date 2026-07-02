const { AppError } = require('../utils/errors');

/**
 * 入参校验中间件（zod 契约层）
 * 用法：router.post('/x', validate(schema), controller.x)  // 默认校验 body
 *       validate(schema, 'query') / validate(schema, 'params')
 * 校验通过后把"已解析/强转"的结果写回 req[source]；失败抛 AppError(400) 交统一异常处理。
 */
function validate(schema, source = 'body') {
  return (req, res, next) => {
    const r = schema.safeParse(req[source] || {});
    if (!r.success) {
      const issues = r.error.issues.map((i) => `${i.path.join('.') || '参数'}: ${i.message}`);
      return next(new AppError('VALIDATION', '参数校验失败：' + issues.join('；'), 400, { issues }));
    }
    req[source] = r.data;
    next();
  };
}

module.exports = { validate };
