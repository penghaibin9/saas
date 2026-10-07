async function currentDialog(page, timeout = 10_000) {
  const dialog = page.getByRole('dialog').last()
  await dialog.waitFor({ state: 'visible', timeout })
  return dialog
}

export async function acceptInAppConfirm(page, { confirmText, timeout = 10_000 } = {}) {
  const dialog = await currentDialog(page, timeout)
  const button = confirmText
    ? dialog.getByRole('button', { name: confirmText, exact: true })
    : dialog.getByRole('button').last()
  await button.click()
}

export async function submitInAppPrompt(page, value, { confirmText, timeout = 10_000 } = {}) {
  const dialog = await currentDialog(page, timeout)
  const input = dialog.locator('textarea')
  await input.waitFor({ state: 'visible', timeout })
  await input.fill(String(value ?? ''))
  const button = confirmText
    ? dialog.getByRole('button', { name: confirmText, exact: true })
    : dialog.getByRole('button').last()
  await button.click()
}
