const express = require('express');
const { benchmarkController } = require('../controllers');
const { authMiddleware, requireRole } = require('../middlewares/auth');

const router = express.Router();
const u = [benchmarkController.upload];
function optionalFile(req, res, next) {
  const ct = req.headers['content-type'] || '';
  if (ct.includes('multipart/form-data')) return benchmarkController.upload(req, res, next);
  next();
}

router.get('/doc-types', authMiddleware, benchmarkController.docTypes);
router.get('/flow-status', authMiddleware, benchmarkController.flowStatus);

router.get('/student-options', authMiddleware, requireRole(1, 2, 3), benchmarkController.studentOptions);

router.get('/task-books', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.listTaskBooks);
router.post('/task-books', authMiddleware, requireRole(3), ...u, benchmarkController.upsertTaskBook);
router.put('/task-books/confirm', authMiddleware, requireRole(4), benchmarkController.confirmTaskBook);
router.get('/task-books/:id', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.getTaskBook);

router.get('/parent-consents', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.listParentConsents);
router.post('/parent-consents', authMiddleware, requireRole(4), optionalFile, benchmarkController.createParentConsent);
router.put('/parent-consents/:id/review', authMiddleware, requireRole(1, 2, 3), benchmarkController.reviewParentConsent);

router.get('/appraisals', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.listAppraisals);
router.post('/appraisals', authMiddleware, requireRole(4), optionalFile, benchmarkController.upsertAppraisal);
router.put('/appraisals/:id/review', authMiddleware, requireRole(1, 2, 3), benchmarkController.reviewAppraisal);
router.get('/appraisals/:id', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.getAppraisal);

router.get('/teacher-visits', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.listVisits);
router.post('/teacher-visits', authMiddleware, requireRole(3), optionalFile, benchmarkController.createVisit);

router.get('/employment', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.getEmployment);
router.get('/employment/stats', authMiddleware, requireRole(1, 2, 3), benchmarkController.employmentStats);
router.post('/employment', authMiddleware, requireRole(4), benchmarkController.upsertEmployment);

router.get('/alternatives', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.listAlternatives);
router.post('/alternatives', authMiddleware, requireRole(4), optionalFile, benchmarkController.createAlternative);
router.put('/alternatives/:id/review', authMiddleware, requireRole(1, 2), benchmarkController.reviewAlternative);

router.post('/intern-complete', authMiddleware, requireRole(4), benchmarkController.completeIntern);

router.get('/topic-pool', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.listTopicPool);
router.post('/topic-pool', authMiddleware, requireRole(3), benchmarkController.createTopicPool);
router.get('/topic-rounds', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.listRounds);
router.post('/topic-rounds', authMiddleware, requireRole(1, 2), benchmarkController.createRound);
router.put('/topic-rounds/:id/status', authMiddleware, requireRole(1, 2), benchmarkController.setRoundStatus);
router.post('/topic-choices', authMiddleware, requireRole(4), benchmarkController.submitChoices);
router.get('/topic-rounds/:roundId/choices', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.listChoices);

router.get('/intern-score-config', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.getScoreConfig);
router.put('/intern-score-config', authMiddleware, requireRole(1, 2), benchmarkController.saveScoreConfig);
router.post('/intern-scores/compute', authMiddleware, requireRole(1, 2, 3), benchmarkController.computeInternScore);
router.get('/intern-scores/mine', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.getInternScore);
router.put('/intern-scores/:studentId/publish', authMiddleware, requireRole(1, 2, 3), benchmarkController.publishInternScore);

router.get('/urge-list', authMiddleware, requireRole(1, 2, 3), benchmarkController.urgeList);
router.post('/urge-notify', authMiddleware, requireRole(1, 2, 3), benchmarkController.urgeNotify);

router.post('/checkin-makeup', authMiddleware, requireRole(4), optionalFile, benchmarkController.makeupCheckin);
router.put('/checkin-makeup/:id/review', authMiddleware, requireRole(3), benchmarkController.reviewMakeup);

router.post('/plagiarism/:achievementId', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.runPlagiarism);
router.get('/plagiarism/:achievementId', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.getPlagiarism);

router.get('/export/chsi', authMiddleware, requireRole(1, 2), benchmarkController.chsiExport);
router.get('/export/intern-handbook', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.internHandbook);
router.get('/export/gd-archive', authMiddleware, requireRole(1, 2, 3, 4), benchmarkController.gdArchive);

router.get('/class-teacher/dashboard', authMiddleware, requireRole(3), benchmarkController.classTeacherDashboard);
router.get('/defense/mine', authMiddleware, requireRole(4), benchmarkController.myDefense);
router.put('/gd-grades/:studentId/publish', authMiddleware, requireRole(1, 2, 3), benchmarkController.publishGdGrade);

module.exports = router;
