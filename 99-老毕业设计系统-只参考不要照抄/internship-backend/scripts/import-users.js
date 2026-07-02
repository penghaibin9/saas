/**
 * 批量导入师生账号（学校上线入职用）
 *
 * 用法：
 *   node scripts/import-users.js <路径.xlsx> [--sheet=Sheet1] [--password=Abc12345] [--dry]
 *
 * Excel 列（中文表头，缺列自动忽略）：
 *   用户名 | 姓名 | 角色 | 学号工号 | 手机号 | 邮箱 | 学院 | 专业 | 班级
 *   - 角色取值：学生 / 教师(指导教师) / 分院管理员 / 院校管理员 / 企业导师
 *   - 学院/专业/班级 按名称解析为 ID（库中不存在则该行跳过并告警，不会自动新建）
 *
 * 行为：
 *   - 初始密码统一为 --password（默认 Abc12345，需字母+数字且≥6位），并强制首登改密；
 *   - 已存在的用户名将被跳过（幂等，可重复运行）；
 *   - --dry 仅校验与预览，不写库。
 */
require('dotenv').config();
const path = require('path');
const fs = require('fs');
const XLSX = require('xlsx');
const pwdHash = require('../utils/password');
const pool = require('../config/db');

const ROLE_MAP = {
  '学生': 4, '指导教师': 3, '教师': 3, '分院管理员': 2, '院校管理员': 1, '管理员': 1, '企业导师': 5
};

function parseArgs() {
  const args = process.argv.slice(2);
  const file = args.find(a => !a.startsWith('--'));
  const opt = {};
  args.filter(a => a.startsWith('--')).forEach(a => {
    const [k, v] = a.replace(/^--/, '').split('=');
    opt[k] = v === undefined ? true : v;
  });
  return { file, opt };
}

function pick(row, ...keys) {
  for (const k of keys) {
    if (row[k] !== undefined && row[k] !== null && String(row[k]).trim() !== '') return String(row[k]).trim();
  }
  return '';
}

async function resolveId(table, name, extraWhere = '', extraParams = []) {
  if (!name) return null;
  const [rows] = await pool.query(
    `SELECT id FROM ${table} WHERE name = ? AND is_deleted = 0 ${extraWhere} LIMIT 1`,
    [name, ...extraParams]
  );
  return rows[0] ? rows[0].id : null;
}

async function main() {
  const { file, opt } = parseArgs();
  if (!file || !fs.existsSync(file)) {
    console.error('❌ 请提供有效的 Excel 路径：node scripts/import-users.js <路径.xlsx>');
    process.exit(1);
  }
  const password = opt.password || process.env.IMPORT_DEFAULT_PASSWORD || 'Abc12345';
  if (!/^(?=.*[A-Za-z])(?=.*\d).{6,}$/.test(password)) {
    console.error('❌ 初始密码需至少 6 位且同时包含字母和数字');
    process.exit(1);
  }
  const dry = !!opt.dry;
  const hash = await pwdHash.hash(password);

  const wb = XLSX.readFile(file);
  const sheetName = opt.sheet || wb.SheetNames[0];
  const sheet = wb.Sheets[sheetName];
  if (!sheet) { console.error('❌ 找不到工作表：' + sheetName); process.exit(1); }
  const rows = XLSX.utils.sheet_to_json(sheet, { defval: '' });
  console.log(`📄 读取 ${rows.length} 行（工作表：${sheetName}）${dry ? ' [DRY-RUN]' : ''}`);

  let created = 0, skipped = 0, failed = 0;
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const ln = i + 2; // Excel 行号（含表头）
    const username = pick(row, '用户名', 'username');
    const realName = pick(row, '姓名', 'real_name', 'name');
    const roleText = pick(row, '角色', 'role');
    const role = ROLE_MAP[roleText] || (Number(roleText) >= 1 && Number(roleText) <= 5 ? Number(roleText) : null);

    if (!username || !realName || !role) {
      console.warn(`  ⚠️ 第${ln}行 跳过：用户名/姓名/角色 不完整（${username}/${realName}/${roleText}）`);
      failed++; continue;
    }

    const [exist] = await pool.query('SELECT id FROM t_user WHERE username = ? AND is_deleted = 0 LIMIT 1', [username]);
    if (exist.length) { skipped++; continue; }

    const collegeName = pick(row, '学院', 'college');
    const majorName = pick(row, '专业', 'major');
    const className = pick(row, '班级', 'class');
    const collegeId = await resolveId('t_college', collegeName);
    if (collegeName && !collegeId) { console.warn(`  ⚠️ 第${ln}行 跳过：学院「${collegeName}」不存在`); failed++; continue; }
    const majorId = majorName ? await resolveId('t_major', majorName, collegeId ? 'AND college_id = ?' : '', collegeId ? [collegeId] : []) : null;
    if (majorName && !majorId) { console.warn(`  ⚠️ 第${ln}行 跳过：专业「${majorName}」不存在`); failed++; continue; }
    const classId = className ? await resolveId('t_class', className, collegeId ? 'AND college_id = ?' : '', collegeId ? [collegeId] : []) : null;
    if (className && !classId) { console.warn(`  ⚠️ 第${ln}行 跳过：班级「${className}」不存在`); failed++; continue; }

    const user = {
      username, password: hash, real_name: realName, role,
      phone: pick(row, '手机号', 'phone') || null,
      email: pick(row, '邮箱', 'email') || null,
      eeid: pick(row, '学号工号', '学号', '工号', 'eeid') || null,
      college_id: collegeId, major_id: majorId, class_id: classId,
      status: 1, must_change_password: 1
    };

    if (dry) { created++; continue; }
    try {
      await pool.query(
        `INSERT INTO t_user (username, password, real_name, phone, email, role, college_id, enterprise_id, major_id, class_id, eeid, status, must_change_password)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)`,
        [user.username, user.password, user.real_name, user.phone, user.email, user.role,
         user.college_id, null, user.major_id, user.class_id, user.eeid, user.status]);
      created++;
    } catch (e) {
      console.warn(`  ⚠️ 第${ln}行 写入失败：${e.message}`);
      failed++;
    }
  }

  console.log(`\n==== 导入完成${dry ? '（DRY-RUN，未写库）' : ''} ====`);
  console.log(`  新增：${created}  跳过(已存在)：${skipped}  失败：${failed}`);
  console.log(`  初始密码：${password}（首次登录强制修改）`);
  process.exit(0);
}

main().catch(e => { console.error(e); process.exit(1); });
