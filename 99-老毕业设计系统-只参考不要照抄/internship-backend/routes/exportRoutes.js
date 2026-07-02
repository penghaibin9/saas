const express = require('express');
const { exportController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();

// 导出
router.get('/applications', authMiddleware, exportController.exportApplications);
router.get('/reports',      authMiddleware, exportController.exportReports);
router.get('/users',        authMiddleware, requireRole(1, 2), exportController.exportUsers);
router.get('/intern-archive', authMiddleware, requireRole(1, 2, 3), exportController.exportInternArchive);
router.get('/assignments',    authMiddleware, requireRole(1, 2, 3), exportController.exportAssignments);
router.get('/checkins',       authMiddleware, requireRole(1, 2, 3), exportController.exportCheckins);
router.get('/gd-topics',      authMiddleware, requireRole(1, 2, 3), exportController.exportGdTopics);
router.get('/gd-grades',      authMiddleware, requireRole(1, 2, 3), exportController.exportGdGrades);

// 导入学生 / 教师
router.get('/template',          authMiddleware, requireRole(1, 2), exportController.downloadTemplate);
router.get('/teachers/template', authMiddleware, requireRole(1, 2), exportController.downloadTeacherTemplate);
router.post('/students',         authMiddleware, requireRole(1, 2), exportController.uploadMiddleware, exportController.importStudents);
router.post('/teachers',         authMiddleware, requireRole(1, 2), exportController.uploadMiddleware, exportController.importTeachers);

module.exports = router;
