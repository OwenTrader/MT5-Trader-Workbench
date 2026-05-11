import { test, expect, _electron as electron } from '@playwright/test'

test('launches the workbench shell and shows dashboard', async () => {
  const app = await electron.launch({ 
    args: ['out/main/index.js'],
    timeout: 60000 
  })
  try {
    const window = await app.firstWindow()
    await window.waitForLoadState('domcontentloaded')

    await expect(window).toHaveTitle(/Trader Workbench/)

    // Verify Dashboard content
    await window.waitForSelector('h1', { timeout: 30000 })
    const dashboardTitle = await window.textContent('h1')
    expect(dashboardTitle).toMatch(/工作台总览|Dashboard|价格预警中心|Price Alerts/)
  } finally {
    await app.evaluate(async ({ app }) => {
      app.exit(0)
    })
  }
})
