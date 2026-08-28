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
