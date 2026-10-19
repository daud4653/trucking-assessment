import { expect, test } from '@playwright/test'
import { mockApi, PLAN_ID } from './mock-api'

async function fillTrip(page: import('@playwright/test').Page) {
  await page.getByRole('combobox', { name: 'Origin' }).fill('Chicago')
  await page.getByRole('option', { name: /Chicago/ }).click()
  await page.getByRole('combobox', { name: 'Destination' }).fill('Peoria')
  await page.getByRole('option', { name: /Peoria/ }).click()
}

test('plans a trip and compares ranked routes', async ({ page }) => {
  await mockApi(page, { planDelayMs: 400 })
  await page.goto('/')
  await expect(page.getByText('No trip yet')).toBeVisible()
  await fillTrip(page)
  await page.getByRole('button', { name: 'Compare routes' }).click()
  await expect(page.getByRole('button', { name: 'Planning routes…' })).toBeDisabled()

  await expect(page).toHaveURL(new RegExp(`/plans/${PLAN_ID}`))
  const options = page.getByRole('region', { name: 'Route options' }).or(page.locator('section[aria-labelledby="route-comparison-heading"]'))
  await expect(options.getByRole('button', { pressed: true })).toContainText('Route A')
  await expect(options.getByText('Recommended')).toBeVisible()
  await expect(options.getByText('No Travel segment')).toBeVisible()
  await expect(page.getByText('2 checkpoints lack complete forecast data.')).toBeVisible()
})

test('selecting a route and checkpoint explains the classification', async ({ page }) => {
  await mockApi(page)
  await page.goto(`/plans/${PLAN_ID}`)
  await page.getByRole('button', { name: /Route C/ }).click()
  await expect(page.getByRole('heading', { name: /Checkpoints · Route C/ })).toBeVisible()
  await expect(page.getByText(/this route contains a No Travel segment/)).toBeVisible()

  await page.getByRole('button', { name: /Mile 100\.0, no_travel risk/ }).click()
  const detail = page.getByRole('article', { name: /Checkpoint at mile 100/ })
  await expect(detail).toContainText('No Travel: wind is 58 mph')
  await expect(detail).toContainText('55 mph or above')

  await page.getByRole('button', { name: /Mile 200\.0, unknown risk/ }).click()
  await expect(page.getByRole('article', { name: /Checkpoint at mile 200/ })).toContainText(
    'No forecast available: not assessed',
  )
})

test('forecast slider moves through 48 hourly frames without new requests', async ({ page }) => {
  await mockApi(page)
  // Counts completed fetches; React StrictMode in dev may abort and repeat
  // the first one during its double mount.
  let corridorResponses = 0
  page.on('requestfinished', (request) => {
    if (request.url().includes('corridor-forecast')) corridorResponses += 1
  })
  await page.goto(`/plans/${PLAN_ID}`)
  const slider = page.getByRole('slider')
  await expect(slider).toBeEnabled()
  const initial = await page.locator('output[for="forecast-offset"]').textContent()

  await slider.focus()
  await page.keyboard.press('End')
  await expect(page.getByText('+48 h')).toBeVisible()
  await expect(page.locator('output[for="forecast-offset"]')).not.toHaveText(initial ?? '')
  await page.keyboard.press('ArrowLeft')
  await expect(page.getByText('+47 h')).toBeVisible()

  await page.getByRole('radio', { name: 'Wind' }).check({ force: true })
  await expect(page.getByRole('figure', { name: /Sustained wind legend/ })).toContainText('45 to below 55 mph')
  expect(corridorResponses).toBe(1)
})

test('shows field errors returned by the server', async ({ page }) => {
  await mockApi(page, {
    planError: {
      status: 422,
      body: { error: { code: 'location_not_found', message: "No location matched 'Peoria'.", details: { destination: ["No location matched 'Peoria'."] } } },
    },
  })
  await page.goto('/')
  await fillTrip(page)
  await page.getByRole('button', { name: 'Compare routes' }).click()
  await expect(page.locator('#destination-error')).toHaveText("No location matched 'Peoria'.")
})

test('validates the form before submitting', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')
  await page.getByLabel('Load weight (lb)').fill('90000')
  await page.getByRole('button', { name: 'Compare routes' }).click()
  await expect(page.locator('#origin-error')).toBeVisible()
  await expect(page.getByText('Maximum supported load is 80,000 lb.')).toBeVisible()
})

test('expired plan shows a recoverable error', async ({ page }) => {
  await page.route('**/api/v1/route-plans/*/', (r) =>
    r.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ error: { code: 'plan_not_found', message: 'Route plan not found or expired.' } }),
    }),
  )
  await page.goto(`/plans/${PLAN_ID}`)
  await expect(page.getByText('This plan has expired or does not exist.')).toBeVisible()
})
