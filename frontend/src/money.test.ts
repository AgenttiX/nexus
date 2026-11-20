import { expect, test } from 'vitest'

import { formatEuros } from './money'

test('formats euros from numbers and decimal strings', () => {
  expect(formatEuros(1234.5)).toBe('€1,234.50')
  expect(formatEuros('-45.90')).toBe('-€45.90')
})
