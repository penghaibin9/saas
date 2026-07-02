const { checkinModel, assignmentModel, benchmarkModel, systemConfigModel } = require('../models');
const { success, error } = require('../utils/response');
const { clampPagination } = require('../utils/validate');
const { distanceInMeters, isValidLat, isValidLng } = require('../utils/geo');
const { createUploader, keyToUrl } = require('../utils/upload');
const checkinRisk = require('../utils/checkinRisk');

// 打卡照片上传器（仅图片）
const photoUploader = createUploader({ prefix: 'checkin', allowedExt: ['.jpg', '.jpeg', '.png'], maxSize: 10 * 1024 * 1024 });

const checkinController = {
  // 打卡照片中间件（multipart 时使用，字段名 photo）
  uploadPhoto: photoUploader.single('photo'),

  // 学生打卡：校验是否在实习企业有效范围内
  async checkin(req, res) {
    try {
      const { latitude, longitude, address, remark } = req.body;
      // 班次：day=全天 / am=上班(上午) / pm=下班(下午)；默认 day
      const slot = ['day', 'am', 'pm'].includes(req.body.slot) ? req.body.slot : 'day';
      const slotLabel = { day: '今日', am: '上班', pm: '下班' }[slot];
      if (!isValidLat(latitude) || !isValidLng(longitude)) {
        return error(res, '定位坐标不合法', 400);
      }

      const assignment = await assignmentModel.findActiveByStudent(req.user.id);
      if (!assignment) return error(res, '你当前没有有效的实习分配，无法打卡', 400);

      if (await checkinModel.hasCheckedInToday(req.user.id, slot)) {
        return error(res, `${slotLabel}已经打过卡了`, 409);
      }

      const photo_url = req.file ? keyToUrl(req.file.filename) : null;

      // 反作弊：模拟定位/精度异常/位移突变评估（留痕，高风险标记待教师复核）
      const last = await checkinModel.findLastGeoByStudent(req.user.id);
      const risk = checkinRisk.assess(
        { lat: latitude, lng: longitude, accuracy: req.body.accuracy, isMock: req.body.is_mock ?? req.body.mock },
        last ? { lat: last.latitude, lng: last.longitude, time: last.checkin_time } : null
      );

      let distance = null;
      let withinRange = true;
      const radius = Number(assignment.checkin_radius) || 0;
      const hasGeo = assignment.latitude != null && assignment.longitude != null;

      if (hasGeo && radius > 0) {
        distance = distanceInMeters(
          Number(latitude), Number(longitude),
          Number(assignment.latitude), Number(assignment.longitude)
        );
        withinRange = distance <= radius;
        // 围栏模式：hard(默认)=超范围拒绝；soft=允许打卡但标记为"超范围"供教师审阅
        let fenceMode = 'hard';
        try {
          const cfg = await systemConfigModel.getAll();
          if (cfg && cfg.checkin_fence_mode === 'soft') fenceMode = 'soft';
        } catch (_) {}
        if (!withinRange && fenceMode === 'hard') {
          return error(res, `不在有效打卡范围内（距实习单位 ${distance} 米，允许 ${radius} 米）`, 400, {
            distance, radius
          });
        }
      }

      // 高风险（疑似作弊）一并标记为待审，超范围或风险均提示
      const flagged = !withinRange || risk.level === 'high';
      const id = await checkinModel.create({
        student_id: req.user.id,
        assignment_id: assignment.id,
        enterprise_id: assignment.enterprise_id,
        latitude, longitude, distance, within_range: withinRange && risk.level !== 'high',
        address, photo_url, remark, slot,
        accuracy: req.body.accuracy, is_mock: req.body.is_mock ?? req.body.mock,
        device_id: req.body.device_id, risk_level: risk.level, risk_reason: risk.reasons.join('；') || null,
      });
      try { await benchmarkModel.addCheckinPoints(req.user.id); } catch (_) {}
      let msg = `${slotLabel}打卡成功`;
      if (risk.level === 'high') msg = `${slotLabel}打卡已记录，但检测到异常（${risk.reasons.join('；')}），已标记待教师核实`;
      else if (!withinRange) msg = `${slotLabel}打卡成功（超出有效范围，已标记待审）`;
      return success(res, { id, distance, within_range: withinRange, photo_url, slot, risk: { level: risk.level, reasons: risk.reasons } }, msg, 201);
    } catch (err) {
      return error(res, '打卡失败：' + err.message, 500);
    }
  },

  async list(req, res) {
    try {
      const { student_id, enterprise_id, date_from, date_to } = req.query;
      const user = req.user;
      const filter = {
        studentId:    student_id    !== undefined ? Number(student_id)    : undefined,
        enterpriseId: enterprise_id !== undefined ? Number(enterprise_id) : undefined,
        dateFrom: date_from, dateTo: date_to
      };
      if (user.role === 4) filter.studentId = user.id;
      if (user.role === 3) filter.teacherId = user.id;
      if (user.role === 2) filter.collegeId = user.collegeId;
      if (user.role === 5) filter.enterpriseId = user.enterpriseId || -1; // 企业导师仅限本企业

      const result = await checkinModel.findAll(filter, clampPagination(req.query));
      return success(res, result, '获取打卡记录成功');
    } catch (err) {
      return error(res, '获取打卡记录失败：' + err.message, 500);
    }
  },

  // 管理员/教师为学生补录打卡（按学生当前实习分配的企业）
  async manual(req, res) {
    try {
      const { student_id, checkin_time, remark } = req.body;
      if (!student_id) return error(res, '请指定学生', 400);

      const assignment = await assignmentModel.findActiveByStudent(Number(student_id));
      if (!assignment) return error(res, '该学生没有有效的实习分配', 400);
      // 教师仅能为自己指导的学生补录；分院仅本学院
      if (req.user.role === 3 && assignment.teacher_id !== req.user.id) {
        return error(res, '只能为自己指导的学生补录', 403);
      }

      const id = await checkinModel.create({
        student_id: Number(student_id),
        assignment_id: assignment.id,
        enterprise_id: assignment.enterprise_id,
        latitude: assignment.latitude, longitude: assignment.longitude,
        distance: 0, within_range: 1,
        address: '管理员补录', remark: remark || '补录',
        checkin_time: checkin_time || undefined
      });
      return success(res, { id }, '补录成功', 201);
    } catch (err) {
      return error(res, '补录失败：' + err.message, 500);
    }
  },

  // 学生本人的打卡概况
  async mine(req, res) {
    try {
      const total = await checkinModel.countByStudent(req.user.id);
      const assignment = await assignmentModel.findActiveByStudent(req.user.id);
      // 是否启用双时段（上班/下班）打卡
      let doubleSlot = false;
      try { const cfg = await systemConfigModel.getAll(); doubleSlot = cfg && cfg.checkin_double_slot === '1'; } catch (_) {}
      let checkedToday, checkedAm = false, checkedPm = false;
      if (doubleSlot) {
        checkedAm = await checkinModel.hasCheckedInToday(req.user.id, 'am');
        checkedPm = await checkinModel.hasCheckedInToday(req.user.id, 'pm');
        checkedToday = checkedAm && checkedPm; // 双时段全部完成才算今日完成
      } else {
        checkedToday = await checkinModel.hasCheckedInToday(req.user.id, 'day');
      }
      return success(res, {
        total,
        checkedToday, doubleSlot, checkedAm, checkedPm,
        enterprise: assignment ? assignment.enterprise_name : null,
        checkinRadius: assignment ? assignment.checkin_radius : null,
        enterpriseLat: assignment ? assignment.latitude : null,
        enterpriseLng: assignment ? assignment.longitude : null,
        hasAssignment: !!assignment
      }, '获取打卡概况成功');
    } catch (err) {
      return error(res, '获取打卡概况失败：' + err.message, 500);
    }
  }
};

module.exports = checkinController;
