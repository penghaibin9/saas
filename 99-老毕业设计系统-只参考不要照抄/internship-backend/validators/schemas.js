const { z } = require('zod');

/**
 * 入参契约（zod）。既用于运行期校验（middlewares/validate），
 * 也作为 OpenAPI 文档的来源（openapi/spec 引用同一批 schema）。
 */

const period = z.string().regex(/^\d{4}-(0[1-9]|1[0-2])$/, '格式应为 YYYY-MM');
const phone = z.string().regex(/^1[3-9]\d{9}$/, '手机号格式不正确');

const authLogin = z.object({
  username: z.string().min(1, '用户名不能为空'),
  password: z.string().min(1, '密码不能为空'),
}).strip();

const authRegister = z.object({
  username: z.string().min(3, '用户名至少3位').max(50),
  password: z.string().min(6, '密码至少6位'),
  real_name: z.string().min(1, '真实姓名不能为空'),
  phone: phone.optional(),
  email: z.string().email('邮箱格式不正确').optional(),
  college_id: z.coerce.number().int().optional(),
  major_id: z.coerce.number().int().optional(),
  class_id: z.coerce.number().int().optional(),
  eeid: z.string().optional(),
}).strip();

const stipendCreate = z.object({
  student_id: z.coerce.number().int().positive('请指定学生'),
  period,
  amount: z.coerce.number().nonnegative('金额不合法').optional(),
  base_salary_ref: z.coerce.number().nonnegative().optional(),
  method: z.enum(['bank', 'cash', 'wechat', 'alipay']).optional(),
  enterprise_name: z.string().max(200).optional(),
  pay_date: z.string().optional(),
  remark: z.string().max(255).optional(),
}).strip();

const platformProvision = z.object({
  code: z.string().regex(/^[a-z0-9][a-z0-9_-]{1,62}$/, 'code 仅限小写字母数字下划线连字符，字母数字开头'),
  name: z.string().min(1, '学校名称不能为空'),
  plan: z.string().optional(),
  expire_date: z.string().optional(),
  region: z.string().optional(),
  contact_name: z.string().optional(),
  contact_phone: phone.optional(),
  adminUser: z.string().optional(),
}).strip();

// ── 配置化流程引擎 ──
const wfDispatch = z.object({
  action: z.string().min(1, '请指定动作'),
  remark: z.string().max(255).optional(),
}).strip();

const wfDefinition = z.object({
  name: z.string().optional(),
  states: z.array(z.object({
    code: z.string().min(1), name: z.string().min(1),
    is_start: z.coerce.boolean().optional(), is_end: z.coerce.boolean().optional(),
  })).min(1, 'states 不能为空'),
  transitions: z.array(z.object({
    from_state: z.string().min(1), to_state: z.string().min(1), action: z.string().min(1),
    name: z.string().optional(), roles: z.string().optional(), perm_code: z.string().optional(),
  })).default([]),
}).strip();

module.exports = { authLogin, authRegister, stipendCreate, platformProvision, wfDispatch, wfDefinition };
