import { describe, it, expect } from 'vitest'

import { parseErrorDetail } from '../parseError'

describe('parseErrorDetail', () => {
  it('returns string detail from response body', async () => {
    const response = mockResponse(JSON.stringify({ detail: 'Invalid date format' }))
    const result = await parseErrorDetail(response, 'fallback')
    expect(result).toBe('Invalid date format')
  })

  it('returns fallback for empty string detail', async () => {
    const response = mockResponse(JSON.stringify({ detail: '' }))
    const result = await parseErrorDetail(response, 'fallback')
    expect(result).toBe('fallback')
  })

  it('returns first message from array detail', async () => {
    const response = mockResponse(
      JSON.stringify({ detail: [{ msg: 'validation error' }] }),
    )
    const result = await parseErrorDetail(response, 'fallback')
    expect(result).toBe('validation error')
  })

  it('returns field-prefixed messages from array detail', async () => {
    const response = mockResponse(
      JSON.stringify({
        detail: [
          { field: 'title', message: 'String should have at least 1 character' },
        ],
      }),
    )
    const result = await parseErrorDetail(response, 'fallback')
    expect(result).toBe('Title: String should have at least 1 character')
  })

  it('joins multiple array detail items', async () => {
    const response = mockResponse(
      JSON.stringify({
        detail: [
          { field: 'title', message: 'Too short' },
          { field: 'body', message: 'Required' },
        ],
      }),
    )
    const result = await parseErrorDetail(response, 'fallback')
    expect(result).toBe('Title: Too short, Body: Required')
  })

  it('prefers message over msg in array items', async () => {
    const response = mockResponse(
      JSON.stringify({ detail: [{ message: 'preferred', msg: 'fallback' }] }),
    )
    const result = await parseErrorDetail(response, 'fallback')
    expect(result).toBe('preferred')
  })

  it('returns fallback for non-object detail', async () => {
    const response = mockResponse(JSON.stringify({ detail: 42 }))
    const result = await parseErrorDetail(response, 'fallback')
    expect(result).toBe('fallback')
  })

  it('returns fallback for missing detail field', async () => {
    const response = mockResponse(JSON.stringify({ error: 'something' }))
    const result = await parseErrorDetail(response, 'fallback')
    expect(result).toBe('fallback')
  })

  it('returns fallback for invalid JSON', async () => {
    const response = mockResponse('not json')
    const result = await parseErrorDetail(response, 'fallback')
    expect(result).toBe('fallback')
  })

  it('returns fallback for empty array detail', async () => {
    const response = mockResponse(JSON.stringify({ detail: [] }))
    const result = await parseErrorDetail(response, 'fallback')
    expect(result).toBe('fallback')
  })
})

function mockResponse(body: string): { text: () => Promise<string> } {
  return { text: () => Promise.resolve(body) }
}
