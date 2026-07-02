const wf = require('../models/workflowModel');
const { AppError } = require('../utils/errors');

/**
 * 配置化流程引擎 Service（编排）
 * 读取每校的流程定义驱动单据状态流转；动作合法性与角色权限均由配置决定，不写死。
 */

async function ensureInstance(def, bizType, bizId) {
  let inst = await wf.getInstance(bizType, bizId);
  if (inst) return inst;
  const start = (def.states || []).find((s) => s.is_start) || (def.states || [])[0];
  if (!start) throw AppError.badState('流程未配置起始状态');
  const id = await wf.createInstance(bizType, bizId, def.id, start.code);
  return wf.getInstance(bizType, bizId) || { id, biz_type: bizType, biz_id: bizId, def_id: def.id, cur_state: start.code };
}

const workflowService = {
  // 查看某单据当前状态 + 当前用户可执行的动作 + 历史
  async current(bizType, bizId, user) {
    const def = await wf.getDef(bizType);
    if (!def) throw AppError.notFound('流程未配置：' + bizType);
    const inst = await ensureInstance(def, bizType, bizId);
    const stateName = (def.states.find((s) => s.code === inst.cur_state) || {}).name || inst.cur_state;
    const isEnd = !!(def.states.find((s) => s.code === inst.cur_state) || {}).is_end;
    return {
      bizType, bizId: Number(bizId), state: inst.cur_state, stateName, isEnd,
      actions: wf.availableActions(def.transitions, inst.cur_state, user.role),
      history: await wf.history(inst.id),
    };
  },

  // 驱动一次流转
  async dispatch(bizType, bizId, action, user, remark) {
    const def = await wf.getDef(bizType);
    if (!def) throw AppError.notFound('流程未配置：' + bizType);
    const inst = await ensureInstance(def, bizType, bizId);
    const tr = wf.resolveTransition(def.transitions, inst.cur_state, action);
    if (!tr) throw AppError.badState(`当前状态「${inst.cur_state}」不允许动作「${action}」`);
    if (!wf.canPerform(tr, user.role)) throw AppError.forbidden('当前角色无权执行该动作');
    await wf.moveTo(inst.id, tr.to_state);
    await wf.addHistory(inst.id, {
      from_state: inst.cur_state, to_state: tr.to_state, action,
      operator: user.id, operator_name: user.realName || user.username, remark,
    });
    const toMeta = def.states.find((s) => s.code === tr.to_state) || {};
    return { bizType, bizId: Number(bizId), state: tr.to_state, stateName: toMeta.name || tr.to_state, isEnd: !!toMeta.is_end };
  },

  // 管理：列出/取/配置/启停流程定义
  listDefs: () => wf.listDefs(),
  async getDef(bizType) { const d = await wf.getDef(bizType); if (!d) throw AppError.notFound('流程未配置：' + bizType); return d; },
  async replaceDefinition(bizType, def) {
    if (!def || !Array.isArray(def.states) || !def.states.length) throw AppError.badRequest('states 不能为空');
    if (!def.states.some((s) => s.is_start)) throw AppError.badRequest('必须有一个起始状态(is_start)');
    await wf.replaceDefinition(bizType, def);
    return wf.getDef(bizType);
  },
  setEnabled: (bizType, enabled) => wf.setEnabled(bizType, enabled),
  seedDefaults: () => wf.seedDefaults(),
};

module.exports = workflowService;
