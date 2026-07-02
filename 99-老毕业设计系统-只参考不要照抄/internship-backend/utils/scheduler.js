/**
 * 轻量定时任务调度器（零依赖，基于 setInterval）。
 * 当前任务：保险到期预警 + 未投保预警。
 * 说明：每 24 小时跑一次；并对外暴露 runInsuranceScan() 供管理员手动触发/演示。
 */
const { insuranceModel, userModel } = require('../models');
const { notify } = require('./notify');
const { withLock } = require('./lock');
const tenancy = require('../config/tenancy');

const EXPIRE_WARN_DAYS = Number(process.env.INSURANCE_WARN_DAYS) || 15;

/**
 * 执行一次保险扫描：
 *  1) 即将到期保单 → 通知学生本人（含短信渠道）
 *  2) 在册实习但未投保/已过期 → 通知院校管理员，并提醒对应学生
 * @returns {Promise<{expiring:number, uninsured:number}>}
 */
async function runInsuranceScan() {
  let expiringCount = 0;
  let uninsuredCount = 0;

  // 1) 到期预警
  try {
    const expiring = await insuranceModel.findExpiringSoon(EXPIRE_WARN_DAYS);
    expiringCount = expiring.length;
    for (const ins of expiring) {
      const dl = Number(ins.days_left);
      const phrase = dl < 0 ? `已过期 ${-dl} 天` : dl === 0 ? '今日到期' : `将于 ${dl} 天后到期`;
      if (ins.student_id) {
        await notify(
          ins.student_id, '实习保险到期提醒',
          `你的实习保险（${ins.company || '保单'} ${ins.policy_no || ''}）${phrase}，请及时续保以保障实习权益`,
          'warning', { sms: true }
        );
      }
    }
  } catch (e) {
    console.warn('保险到期扫描失败:', e.message);
  }

  // 2) 未投保预警
  try {
    const uninsured = await insuranceModel.findUninsuredInterns();
    uninsuredCount = uninsured.length;
    if (uninsuredCount > 0) {
      // 通知院校管理员汇总
      const admins = await userModel.findAll({ role: 1 }, { page: 1, pageSize: 50 });
      for (const a of (admins.list || [])) {
        await notify(
          a.id, '未投保实习学生预警',
          `当前有 ${uninsuredCount} 名在册实习学生未投保或保险已过期，请及时核实办理`,
          'warning'
        );
      }
      // 提醒未投保学生本人
      for (const s of uninsured) {
        if (s.student_id) {
          await notify(
            s.student_id, '实习保险未办理提醒',
            '系统检测到你尚未办理有效实习保险，请尽快联系指导教师/实训中心办理',
            'warning', { sms: true }
          );
        }
      }
    }
  } catch (e) {
    console.warn('未投保扫描失败:', e.message);
  }

  console.log(`📋 保险扫描完成：到期预警 ${expiringCount} 条，未投保 ${uninsuredCount} 人`);
  return { expiring: expiringCount, uninsured: uninsuredCount };
}

// 集群安全 + 多租户：分布式锁保证多实例只跑一份；按租户迭代覆盖每所学校独立库。
// single 模式 forEachTenant 仅默认库执行一次（行为不变）；multi 模式遍历所有活跃租户。
function scheduledScan() {
  return withLock('insurance_scan', 23 * 3600, async () => {
    const results = await tenancy.forEachTenant(() => runInsuranceScan());
    const ok = results.filter((r) => r.ok).length;
    console.log(`📋 保险/未投保扫描完成：覆盖 ${results.length} 个租户（成功 ${ok}${ok < results.length ? '，失败 ' + (results.length - ok) : ''}）`);
  })
    .then((ran) => { if (!ran) console.log('⏭️  保险扫描已被其他实例执行，本实例跳过'); })
    .catch((e) => console.warn('保险扫描调度异常：', e.message));
}

// ── V2：每日全租户用量聚合（计费对账前置）──
// multi 模式才有意义（遍历各校库统计学生/AI 用量写回控制面计量表）；single 模式跳过。
async function runBillingAggregate() {
  if (tenancy.MODE !== 'multi') return { skipped: true };
  const billingService = require('../services/billingService');
  const r = await billingService.refreshAll();
  console.log(`💰 用量聚合完成（${r.period}）：覆盖 ${r.count} 校`);
  return r;
}
function scheduledBilling() {
  if (tenancy.MODE !== 'multi') return;
  return withLock('billing_aggregate', 23 * 3600, () => runBillingAggregate())
    .then((ran) => { if (!ran) console.log('⏭️  用量聚合已被其他实例执行，本实例跳过'); })
    .catch((e) => console.warn('用量聚合调度异常：', e.message));
}

let _started = false;
let _bootTimer = null;
let _dailyTimer = null;
let _billBootTimer = null;
let _billDailyTimer = null;
function start() {
  if (_started) return;
  _started = true;
  const DAY = 24 * 60 * 60 * 1000;
  // 启动 30 秒后跑首次（避开启动高峰），之后每天一次；均经分布式锁，集群下只跑一份
  _bootTimer = setTimeout(scheduledScan, 30 * 1000);
  _dailyTimer = setInterval(scheduledScan, DAY);
  // 用量聚合：启动 90 秒后首次（错峰），之后每天一次
  _billBootTimer = setTimeout(scheduledBilling, 90 * 1000);
  _billDailyTimer = setInterval(scheduledBilling, DAY);
  console.log('⏰ 定时任务已启动：保险到期/未投保 每日扫描 + 用量聚合（集群安全）');
}

// 优雅退出时清理定时器，避免进程无法退出
function stop() {
  if (_bootTimer) clearTimeout(_bootTimer);
  if (_dailyTimer) clearInterval(_dailyTimer);
  if (_billBootTimer) clearTimeout(_billBootTimer);
  if (_billDailyTimer) clearInterval(_billDailyTimer);
  _bootTimer = _dailyTimer = _billBootTimer = _billDailyTimer = null;
  _started = false;
}

module.exports = { start, stop, runInsuranceScan, runBillingAggregate };
