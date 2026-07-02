const express = require('express');
const { teacherController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 教师工作台相关
router.get('/students', authMiddleware, requireRole(3), teacherController.myStudents);
router.put('/students/:id/reset-password', authMiddleware, requireRole(3), teacherController.resetStudentPassword);

module.exports = router;
