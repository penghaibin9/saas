const express = require('express');
const { enterprisePortalController } = require('../controllers');
const { requireRole } = require('../middlewares/auth');

// 企业导师(角色5)专用门户。挂载处已经过 authMiddleware + requirePasswordChanged。
const router = express.Router();
const onlyEnterprise = requireRole(5);

router.get('/me',                       onlyEnterprise, enterprisePortalController.me);
router.get('/dashboard',                onlyEnterprise, enterprisePortalController.dashboard);
router.get('/positions',                onlyEnterprise, enterprisePortalController.listPositions);
router.post('/positions',               onlyEnterprise, enterprisePortalController.createPosition);
router.put('/positions/:id',            onlyEnterprise, enterprisePortalController.updatePosition);
router.get('/applications',             onlyEnterprise, enterprisePortalController.listApplications);
router.put('/applications/:id/confirm', onlyEnterprise, enterprisePortalController.confirmHire);
router.get('/interns',                  onlyEnterprise, enterprisePortalController.listInterns);
router.get('/checkins',                 onlyEnterprise, enterprisePortalController.listCheckins);

module.exports = router;
