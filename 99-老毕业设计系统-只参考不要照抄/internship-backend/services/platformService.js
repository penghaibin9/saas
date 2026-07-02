const path = require('path');
const { spawn } = require('child_process');
const crypto = require('crypto');
const tenancy = require('../config/tenancy');
const tenantModel = require('../models/tenantModel');
const { AppError } = require('../utils/errors');
// 平台异常：复用统一 AppError（保持 new AppErr(msg, status) 调用点不变）
class AppErr extends AppError { constructor(msg, status) { super('PLATFORM', msg, status || 400); } }

/**
 * SaaS 平台运营 Service（控制面业务编排）
 * 跨租户操作：开通学校、套餐/配额、停复服务、用量刷新。仅平台管理员可调。
 */

function curMonth() { return new Date().toISOString().slice(0, 7); }

// 开通一所学校：复用经测试的 provision-tenant.js（建库→迁移→种管理员→登记），子进程隔离执行
function runProvision(code, name, adminUser, adminPass) {
  return new Promise((resolve) => {
    const script = path.join(__dirname, '..', 'scripts', 'provision-tenant.js');
    const child = spawn(process.execPath, [script, code, name, adminUser, adminPass], { env: process.env });
    let out = '', err = '';
    child.stdout.on('data', (d) => { out += d; });
    child.stderr.on('data', (d) => { err += d; });
    child.on('close', (c) => resolve({ code: c, out, err }));
    child.on('error', (e) => resolve({ code: 1, out, err: e.message }));
  });
}

const platformService = {
  async listTenants() {
    const tenants = await tenantModel.list();
    const period = curMonth();
    // 附最近一次计量用量 + 配额，便于控制台一屏看超限
    for (const t of tenants) {
      const u = await tenantModel.getUsage(t.code, period).catch(() => null);
      t.usage = u ? { students: u.students, ai_calls: u.ai_calls, storage_mb: u.storage_mb, period } : null;
      t.over_student = u && t.max_students ? u.students > t.max_students : false;
      t.expired = t.expire_date ? new Date(t.expire_date) < new Date() : false;
    }
    return { tenants, plans: await tenantModel.listPlans() };
  },

  async getTenant(code) {
    const t = await tenantModel.findByCode(code);
    if (!t) return null;
    t.events = await tenantModel.events(code, 30);
    t.usage = await tenantModel.getUsage(code, curMonth());
    return t;
  },

  // 开通学校（必须 multi 模式）
  async provision({ code, name, plan, expire_date, region, contact_name, contact_phone, adminUser = 'admin' }, operator) {
    if (tenancy.MODE !== 'multi') throw new AppErr('单库(single)模式不支持多校开通，请设 TENANCY_MODE=multi', 400);
    if (!/^[a-z0-9][a-z0-9_-]{1,62}$/.test(code || '')) throw new AppErr('code 仅限小写字母数字下划线连字符，字母数字开头', 400);
    if (!name) throw new AppErr('学校名称不能为空', 400);
    if (await tenantModel.findByCode(code)) throw new AppErr('该 code 已存在', 409);

    const adminPass = 'Sch@' + crypto.randomBytes(4).toString('hex'); // 随机初始密码（首登强制改密）
    const r = await runProvision(code, name, adminUser, adminPass);
    if (r.code !== 0) throw new AppErr('开通失败：' + (r.err || r.out || '').slice(-300), 500);

    // provision 脚本已登记基础租户行；这里补套餐/配额/联系信息
    if (plan) await tenantModel.setPlan(code, plan);
    await tenantModel.setQuota(code, {}); // 触发 loadTenants
    if (expire_date || region || contact_name || contact_phone) {
      const M = tenancy.masterPool();
      await M.query('UPDATE t_tenant SET expire_date=COALESCE(?,expire_date), region=COALESCE(?,region), contact_name=COALESCE(?,contact_name), contact_phone=COALESCE(?,contact_phone) WHERE code=?',
        [expire_date || null, region || null, contact_name || null, contact_phone || null, code]);
    }
    await tenancy.loadTenants();
    await tenantModel.recordEvent(code, 'provision', { name, plan, adminUser }, operator);
    return { code, name, db_name: `internship_${code}`, adminUser, adminPass };
  },

  async setPlan(code, planCode, operator) {
    if (!await tenantModel.findByCode(code)) throw new AppErr('租户不存在', 404);
    await tenantModel.setPlan(code, planCode);
    await tenantModel.recordEvent(code, 'update', { plan: planCode }, operator);
  },

  async setQuota(code, quota, operator) {
    if (!await tenantModel.findByCode(code)) throw new AppErr('租户不存在', 404);
    await tenantModel.setQuota(code, quota);
    await tenantModel.recordEvent(code, 'update', { quota }, operator);
  },

  async renew(code, expire_date, operator) {
    if (!await tenantModel.findByCode(code)) throw new AppErr('租户不存在', 404);
    await tenantModel.setExpire(code, expire_date);
    await tenantModel.recordEvent(code, 'renew', { expire_date }, operator);
  },

  async suspend(code, operator) {
    if (!await tenantModel.findByCode(code)) throw new AppErr('租户不存在', 404);
    await tenantModel.setStatus(code, 0);
    await tenantModel.recordEvent(code, 'suspend', null, operator);
  },
  async resume(code, operator) {
    if (!await tenantModel.findByCode(code)) throw new AppErr('租户不存在', 404);
    await tenantModel.setStatus(code, 1);
    await tenantModel.recordEvent(code, 'resume', null, operator);
  },

  // 实时刷新某校用量（直连其库统计学生数 + 当月 AI 调用），写回计量表
  async refreshUsage(code) {
    const t = await tenantModel.findByCode(code);
    if (!t) throw new AppErr('租户不存在', 404);
    const pool = tenancy.poolFor(t.db_name);
    let students = 0, ai_calls = 0;
    try { const [[r]] = await pool.query("SELECT COUNT(*) c FROM t_user WHERE role=4 AND is_deleted=0"); students = Number(r.c) || 0; } catch (_) {}
    try { const [[r]] = await pool.query('SELECT calls FROM t_ai_usage WHERE period=? LIMIT 1', [curMonth()]); ai_calls = r ? Number(r.calls) : 0; } catch (_) {}
    await tenantModel.upsertUsage(code, curMonth(), { students, ai_calls, storage_mb: 0 });
    return { code, period: curMonth(), students, ai_calls, max_students: t.max_students, over_student: t.max_students ? students > t.max_students : false };
  },
};

module.exports = platformService;
module.exports.AppErr = AppErr;
