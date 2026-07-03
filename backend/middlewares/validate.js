const { AppError } = require('../utils/errors');

/**
 * 入参校验中间件（zod 契约层）— 移植自旧系统
 * 用法：router.post('/x', validate(schema), controller.x)  // 默认校验 body
 *       validate(schema, 'query') / validate(schema, 'params')
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
