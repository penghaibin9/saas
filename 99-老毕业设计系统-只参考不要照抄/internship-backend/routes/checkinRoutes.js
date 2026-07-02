const express = require('express');
const { checkinController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 学生打卡 & 个人打卡概况（支持拍照存证：multipart 字段 photo，可选）
router.post('/',     authMiddleware, requireRole(4), checkinController.uploadPhoto, checkinController.checkin);
router.get('/mine',  authMiddleware, requireRole(4), checkinController.mine);

// 管理员/教师为学生补录打卡
router.post('/manual', authMiddleware, requireRole(1, 2, 3), checkinController.manual);

// 打卡记录查询（学生本人 / 教师所带 / 管理员按学院）
router.get('/',      authMiddleware, checkinController.list);

module.exports = router;
