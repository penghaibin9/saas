/**
 * 租户配额校验（学生数）。
 * 仅 multi(SaaS) 模式且当前租户设了 max_students 时生效；single(私有化) 永远不限。
 * 当前学生数取当前租户库（config/db 已按租户路由），配额取 master 注册表。
 */
const tenancy = require('../config/tenancy');
const pool = require('../config/db');
const tenantModel = require('../models/tenantModel');

async function studentQuotaExceeded() {
  if (tenancy.MODE !== 'multi') return false;
  const t = tenancy.currentTenant();
  if (!t || !t.code || t.code === tenancy.DEFAULT_TENANT_CODE) return false;
  let meta;
  try { meta = await tenantModel.findByCode(t.code); } catch (_) { return false; }
  if (!meta || !meta.max_students) return false;
  try {
    const [[r]] = await pool.query("SELECT COUNT(*) c FROM t_user WHERE role = 4 AND is_deleted = 0");
    return Number(r.c) >= Number(meta.max_students);
  } catch (_) { return false; }
}

module.exports = { studentQuotaExceeded };
