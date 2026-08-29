import assert from 'node:assert/strict'
import test from 'node:test'

test('adoptReference surfaces a non-2xx API message', async () => {
  const previousFetch = globalThis.fetch
  globalThis.fetch = async () => new Response(
    JSON.stringify({ message: '参考行程不存在' }),
    { status: 404, headers: { 'Content-Type': 'application/json' } },
  )

  try {
    const module = await import('../src/api/reference.ts')
    const adoptReference = module.adoptReference ?? module.default.adoptReference
    await assert.rejects(
      () => adoptReference(404, { thread_id: 'thr_1' }, () => {}),
      /参考行程不存在/,
    )
  } finally {
    globalThis.fetch = previousFetch
  }
})

test('adapted reference items distinguish estimated, free, and pending prices while retaining user travelers', async () => {
  const { adaptGeneratedTripPlan } = await import('../src/utils/chatPlanAdapter.ts')
  const plan = adaptGeneratedTripPlan({
    values: {
      terminal_status: 'confirmed',
      is_finished: true,
      travelers: 4,
      budget: { total: 120, detail: { tickets: 120 } },
      daily_itinerary: [{
        date: '2026-09-01',
        items: [
          { activity: '故宫', cost: 60, estimate_source: 'rule', image_url: 'https://images.example.test/gugong.jpg' },
          { activity: '免费公园', cost: 0, estimate_source: 'free' },
          { activity: '待补全景点', estimate_source: 'pending' },
        ],
      }],
    },
  })

  assert.equal(plan.trip.people, 4)
  assert.equal(plan.itinerary[0].priceLabel, '规则估算 ¥60')
  assert.equal(plan.itinerary[0].imageUrl, 'https://images.example.test/gugong.jpg')
  assert.equal(plan.itinerary[1].priceLabel, '免费')
  assert.equal(plan.itinerary[2].priceLabel, '待估算')
})
