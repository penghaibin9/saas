const express = require('express');
const { applicationController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 查询（各角色按权限过滤）
router.get('/',    authMiddleware, applicationController.list);
router.get('/:id', authMiddleware, applicationController.detail);

// 学生提交/撤回申请
router.post('/',          authMiddleware, requireRole(4), applicationController.apply);
router.delete('/:id',     authMiddleware, requireRole(4), applicationController.withdraw);

// 教师审核
router.put('/:id/teacher-review', authMiddleware, requireRole(3), applicationController.teacherReview);

// 管理员审核 & 分配教师 & 登记录用结果
router.put('/:id/admin-review',    authMiddleware, requireRole(1, 2), applicationController.adminReview);
router.put('/:id/assign-teacher',  authMiddleware, requireRole(1, 2), applicationController.assignTeacher);
router.put('/:id/recruit-result',  authMiddleware, requireRole(1, 2), applicationController.recruitResult);

module.exports = router;
