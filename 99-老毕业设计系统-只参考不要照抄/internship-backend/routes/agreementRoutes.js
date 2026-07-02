const express = require('express');
const { agreementController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 查看：所有角色（控制器内按角色收窄范围）
router.get('/',    authMiddleware, agreementController.list);
router.get('/:id', authMiddleware, agreementController.detail);

// 发起 / 盖章生效 / 作废：院校 & 分院
router.post('/',             authMiddleware, requireRole(1, 2), agreementController.create);
router.put('/:id/activate',  authMiddleware, requireRole(1, 2), agreementController.activate);
router.put('/:id/void',      authMiddleware, requireRole(1, 2), agreementController.voidAgreement);

// 学生签署
router.put('/:id/student-sign', authMiddleware, requireRole(4), agreementController.studentSign);
// 教师会签（院校/分院亦可代签）
router.put('/:id/teacher-sign', authMiddleware, requireRole(1, 2, 3), agreementController.teacherSign);

module.exports = router;
