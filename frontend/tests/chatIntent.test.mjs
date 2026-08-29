import assert from 'node:assert/strict'
import test from 'node:test'

test('stream intent labels distinguish consultation, preference updates, and replanning', async () => {
  const { loadingLabelForIntent } = await import('../src/utils/chatIntent.ts')

  assert.equal(loadingLabelForIntent('consult'), '正在回答旅行问题...')
  assert.equal(loadingLabelForIntent('update_preferences'), '正在更新出发信息...')
  assert.equal(loadingLabelForIntent('replan'), '正在调整行程...')
  assert.equal(loadingLabelForIntent('plan'), '正在生成行程...')
})

test('a completed consult response wins over its intent loading label', async () => {
  const { loadingLabelForStreamEvent } = await import('../src/utils/chatIntent.ts')

  assert.equal(loadingLabelForStreamEvent('done', {
    data: { values: { intent: 'consult', messages: [{ type: 'ai', content: '十月早晚偏凉，带外套。' }] } },
  }), undefined)
})

test('a failed workflow never returns an intent loading label', async () => {
  const { loadingLabelForStreamEvent } = await import('../src/utils/chatIntent.ts')

  assert.equal(loadingLabelForStreamEvent('done', {
    values: { intent: 'update_preferences', terminal_status: 'failed' },
  }), undefined)
})
