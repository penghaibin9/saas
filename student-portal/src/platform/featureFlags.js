/** 功能开关工具：判定 portal-config.features[key]（总开关关闭时一律 false）。 */
export function featureEnabled(config, key) {
  return !!config?.enabled && !!config?.features?.[key]
}

export const FEATURE_KEYS = [
  'upload', 'export', 'proofDownload', 'profileCorrection',
  'messageReceipt', 'materialCenter', 'workItems', 'aiAssistant'
]
