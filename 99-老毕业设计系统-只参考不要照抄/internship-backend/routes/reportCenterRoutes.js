const express = require('express');
const reportCenterController = require('../controllers/reportCenterController');

const router = express.Router();

router.get('/overview', reportCenterController.overview);
router.get('/catalog',  reportCenterController.catalog);

module.exports = router;
