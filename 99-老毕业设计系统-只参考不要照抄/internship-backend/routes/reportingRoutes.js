const express = require('express');
const reportingController = require('../controllers/reportingController');

const router = express.Router();

router.get('/config',  reportingController.config);
router.get('/preview', reportingController.preview);
router.get('/export',  reportingController.export);
router.post('/push',   reportingController.push);

module.exports = router;
