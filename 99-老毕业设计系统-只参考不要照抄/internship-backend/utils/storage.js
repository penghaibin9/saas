/**
 * 对象存储抽象层（local 默认 / 阿里云 OSS / AWS S3）
 * ───────────────────────────────────────────────────────────
 * 解决「多实例/容器下本地磁盘 uploads 互不可见」的问题：
 *   · STORAGE_DRIVER=local（默认）：写本地磁盘，行为与改造前完全一致（私有化单机够用）；
 *   · STORAGE_DRIVER=oss / s3：上传到对象存储，多实例共享，URL 指向 bucket。
 * SDK 懒加载（ali-oss / @aws-sdk/client-s3），未配置/未安装则保持 local，不阻断。
 *
 * 环境变量（remote 时）：
 *   OSS: OSS_REGION OSS_BUCKET OSS_ACCESS_KEY_ID OSS_ACCESS_KEY_SECRET OSS_PUBLIC_BASE
 *   S3:  S3_REGION S3_BUCKET S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY S3_PUBLIC_BASE [S3_ENDPOINT]
 */
const path = require('path');
const fs = require('fs');
const multer = require('multer');
const crypto = require('crypto');

const DRIVER = (process.env.STORAGE_DRIVER || 'local').toLowerCase();
const UPLOADS_DIR = path.join(__dirname, '../uploads');
if (!fs.existsSync(UPLOADS_DIR)) fs.mkdirSync(UPLOADS_DIR, { recursive: true });

function isRemote() { return DRIVER === 'oss' || DRIVER === 's3'; }

/** 由存储键得到可访问 URL（local→/uploads/key；远端→公网基址/key） */
function keyToUrl(key) {
  if (!key) return null;
  if (DRIVER === 'oss') return (process.env.OSS_PUBLIC_BASE || '').replace(/\/$/, '') + '/' + key;
  if (DRIVER === 's3') return (process.env.S3_PUBLIC_BASE || '').replace(/\/$/, '') + '/' + key;
  return '/uploads/' + key;
}

// —— 远端上传适配（懒加载 SDK）——
let _ossClient = null;
function ossClient() {
  if (_ossClient) return _ossClient;
  const OSS = require('ali-oss');
  _ossClient = new OSS({
    region: process.env.OSS_REGION, bucket: process.env.OSS_BUCKET,
    accessKeyId: process.env.OSS_ACCESS_KEY_ID, accessKeySecret: process.env.OSS_ACCESS_KEY_SECRET,
  });
  return _ossClient;
}
let _s3Client = null;
function s3Client() {
  if (_s3Client) return _s3Client;
  const { S3Client } = require('@aws-sdk/client-s3');
  _s3Client = new S3Client({
    region: process.env.S3_REGION, endpoint: process.env.S3_ENDPOINT || undefined,
    credentials: { accessKeyId: process.env.S3_ACCESS_KEY_ID, secretAccessKey: process.env.S3_SECRET_ACCESS_KEY },
  });
  return _s3Client;
}

async function putRemote(localPath, key) {
  if (DRIVER === 'oss') {
    await ossClient().put(key, localPath);
  } else if (DRIVER === 's3') {
    const { PutObjectCommand } = require('@aws-sdk/client-s3');
    await s3Client().send(new PutObjectCommand({
      Bucket: process.env.S3_BUCKET, Key: key, Body: fs.createReadStream(localPath),
    }));
  }
}

/**
 * 返回一个 multer 存储引擎：本地写 uploads；远端写本地临时后推送对象存储再删临时。
 * 控制器统一用 storage.keyToUrl(req.file.filename) 取访问 URL。
 */
function multerStorage({ prefix = 'file', allowedExt = [] } = {}) {
  const disk = multer.diskStorage({
    destination: (req, file, cb) => cb(null, UPLOADS_DIR),
    filename: (req, file, cb) => {
      const ext = path.extname(file.originalname).toLowerCase();
      const safeExt = allowedExt.includes(ext) ? ext : '';
      cb(null, `${prefix}_${crypto.randomBytes(16).toString('hex')}${safeExt}`);
    },
  });
  if (!isRemote()) return disk;

  // 远端：复用 disk 写临时，再上传对象存储
  return {
    _handleFile(req, file, cb) {
      disk._handleFile(req, file, (err, info) => {
        if (err) return cb(err);
        putRemote(info.path, info.filename)
          .then(() => { fs.unlink(info.path, () => {}); cb(null, { ...info, remote: true }); })
          .catch((e) => { fs.unlink(info.path, () => {}); cb(e); });
      });
    },
    _removeFile(req, file, cb) { disk._removeFile(req, file, cb); },
  };
}

module.exports = { DRIVER, isRemote, keyToUrl, multerStorage, UPLOADS_DIR };
