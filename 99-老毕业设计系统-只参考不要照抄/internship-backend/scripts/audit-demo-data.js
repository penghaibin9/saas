/** 演示数据质量审计：只读，确保演示不是“有数量没流程”。 */
require('dotenv').config();
const fs = require('fs');
const path = require('path');
const pool = require('../config/db');
const checks = [];
const check = (name, ok, detail) => checks.push({ name, ok: !!ok, detail });
async function count(sql, params) { const [[r]] = await pool.query(sql, params); return Number(r.n || 0); }

async function main() {
  const demoUsers = await count("SELECT COUNT(*) n FROM t_user WHERE username LIKE 'demo\\_%' AND is_deleted=0");
  check('标准演示账号规模', demoUsers >= 35, `${demoUsers} 个账号`);
  for (const role of [1, 3, 4, 5]) {
    const n = await count("SELECT COUNT(*) n FROM t_user WHERE username LIKE 'demo\\_%' AND role=? AND is_deleted=0", [role]);
    check(`角色 ${role} 有演示账号`, n > 0, `${n} 个`);
  }
  const assigned = await count("SELECT COUNT(*) n FROM t_assignment a JOIN t_user u ON u.id=a.student_id WHERE u.username LIKE 'demo\\_%' AND a.status=1 AND a.is_deleted=0");
  check('学生有效实习分配', assigned >= 20, `${assigned} 人`);
  const geoEnt = await count("SELECT COUNT(*) n FROM t_enterprise WHERE name LIKE '%有限公司' AND latitude IS NOT NULL AND longitude IS NOT NULL AND checkin_radius>0 AND is_deleted=0");
  check('企业坐标与围栏', geoEnt >= 8, `${geoEnt} 家`);
  for (const [table, label, min] of [['t_application','岗位申请',10],['t_checkin','打卡',50],['t_intern_log','周报月报',30],['t_leave','请假',5],['t_insurance','保险',20],['t_gd_topic','毕业设计选题',10]]) {
    const n = await count(`SELECT COUNT(*) n FROM ${table}`);
    check(label, n >= min, `${n} 条`);
  }
  for (const [table, label] of [['t_application','申请'],['t_intern_log','周报'],['t_leave','请假']]) {
    const n = await count(`SELECT COUNT(DISTINCT status) n FROM ${table}`);
    check(`${label}状态覆盖`, n >= 3, `${n} 种状态`);
  }
  for (const name of ['demo-consent.pdf', 'demo-appraisal.pdf', 'demo-paper.pdf']) {
    check(`样例附件 ${name}`, fs.existsSync(path.join(__dirname, '..', 'uploads', name)), '可下载');
  }
  for (const c of checks) console.log(`${c.ok ? '✅' : '❌'} ${c.name}：${c.detail}`);
  const failed = checks.filter((c) => !c.ok).length;
  console.log(`\n演示数据质量：${checks.length - failed}/${checks.length} 项通过。`);
  if (failed) process.exitCode = 1;
}
main().finally(() => pool.end()).catch((e) => { console.error(e); process.exitCode = 1; });
