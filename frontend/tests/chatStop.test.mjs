import assert from 'node:assert/strict'
import test from 'node:test'

test('stopChat requests cancellation for the active conversation', async () => {
  const previousFetch = globalThis.fetch
  let request
  globalThis.fetch = async (url, options) => {
    request = { url, options }
    return new Response(JSON.stringify({ code: 200, data: { thread_id: 'thr_stop' } }), {
      headers: { 'Content-Type': 'application/json' },
    })
  }

  try {
    const { stopChat } = await import('../src/api/chat.ts')
    await stopChat('thr_stop')

    assert.equal(request.url, '/api/v1/chat/stop/thr_stop')
    assert.equal(request.options.method, 'POST')
    assert.equal(request.options.headers['X-User-Id'], '1')
  } finally {
    globalThis.fetch = previousFetch
  }
})
