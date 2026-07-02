const stipendModel = require('../models/stipendModel');
const { AppError } = require('../utils/errors');

/**
 * 实习报酬 Service（业务编排 + 合规域规则）
 * controller 只做角色判断与 HTTP 适配；业务规则与合规判定集中在此，可独立单测。
 */

// 合规域规则：实习报酬应 ≥ 相同岗位试用期工资的 80%（教育部规定）。纯函数，可测。
function complianceInfo(amount, baseRef) {
  const a = Number(amount), b = Number(baseRef);
  if (!Number.isFinite(b) || b <= 0) return { compliant: null, ratio: null, label: '待核（未填参考工资）' };
  const ratio = a / b;
  const compliant = ratio >= 0.8;
  return { compliant, ratio: Math.round(ratio * 100) / 100, label: compliant ? '合规' : `低于试用期80%（当前${Math.round(ratio * 100)}%）` };
}

async function create(dto, operatorId) {
  // dto 已经 zod 校验；此处做域级兜底
  if (!dto.student_id) throw AppError.badRequest('请指定学生');
  const id = await stipendModel.create({ ...dto, student_id: Number(dto.student_id), created_by: operatorId });
  const row = await stipendModel.findById(id);
  row.compliance = complianceInfo(row.amount, row.base_salary_ref);
  row.compliant = row.compliance.compliant; // 兼容旧字段
  return row;
}

module.exports = { complianceInfo, create };
