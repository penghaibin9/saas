/**
 * SECURITY-P0 · 前端"加密"边界占位（docs/security/03-前端加密边界与后端加密预留.md）。
 *
 * 铁律：
 *  1. 前端不保存密钥，不硬编码任何密钥（含 SM2/SM4/RSA 公私钥、盐值）。
 *  2. 前端"加密"不是安全存储：任何写进 JS/localStorage 的"密文+密钥"都视同明文。
 *  3. 传输安全靠 HTTPS/TLS（网关层），字段级加密靠后端与密钥管理系统（KMS）。
 *  4. 本模块仅提供"公钥加密占位"：公钥必须由后端接口运行时下发，仅存内存。
 */

let serverPublicKey = '' // 仅内存持有，刷新即失；禁止持久化

/** 运行时注入后端下发的公钥（如 /api/security/public-key）。禁止传入硬编码常量。 */
export function setServerPublicKey(pem) {
  serverPublicKey = String(pem || '')
}

export function hasServerPublicKey() {
  return !!serverPublicKey
}

/**
 * 公钥加密占位：真实实现待后端确定算法（RSA-OAEP / SM2）后接入 WebCrypto 或国密库。
 * 当前 mock 阶段没有可用公钥与后端解密端点，直接抛错防止"假加密"上线。
 * @throws {Error} 未注入公钥或未接入真实实现时抛出
 */
export function encryptWithServerPublicKey(plaintext) {
  void plaintext
  if (!serverPublicKey) {
    throw new Error('[crypto-boundary] 服务端公钥未下发：字段加密必须由后端提供公钥并在服务端解密，前端禁止自造密钥')
  }
  throw new Error('[crypto-boundary] 加密实现未接入：待后端确定算法（RSA-OAEP/SM2）后启用，禁止在前端硬编码算法密钥')
}
