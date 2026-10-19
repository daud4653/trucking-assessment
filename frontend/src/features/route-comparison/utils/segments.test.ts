import { describe, expect, it } from 'vitest'
import { checkpoint } from '@/test/fixtures'
import { cumulativeMiles, splitRouteByCheckpoints } from './segments'

const line: [number, number][] = [
  [-90, 40],
  [-90, 40.5],
  [-90, 41],
]

describe('splitRouteByCheckpoints', () => {
  it('cuts the line at the represented mile boundaries', () => {
    const total = cumulativeMiles(line).at(-1) ?? 0
    const half = total / 2
    const segments = splitRouteByCheckpoints(line, total, [
      checkpoint({ id: 'a', represents_from_miles: 0, represents_to_miles: half / 2 }),
      checkpoint({ id: 'b', represents_from_miles: half / 2, represents_to_miles: total }),
    ])
    expect(segments).toHaveLength(2)
    const [first, second] = segments
    expect(first?.coordinates[0]).toEqual([-90, 40])
    expect(first?.coordinates.at(-1)?.[1]).toBeCloseTo(40.25, 3)
    expect(second?.coordinates[0]?.[1]).toBeCloseTo(40.25, 3)
    expect(second?.coordinates).toContainEqual([-90, 40.5])
    expect(second?.coordinates.at(-1)).toEqual([-90, 41])
  })

  it('scales simplified geometry to the reported route distance', () => {
    const segments = splitRouteByCheckpoints(line, 100, [
      checkpoint({ id: 'a', represents_from_miles: 0, represents_to_miles: 50 }),
    ])
    expect(segments[0]?.coordinates.at(-1)?.[1]).toBeCloseTo(40.5, 3)
  })

  it('keeps unknown checkpoints as null level', () => {
    const segments = splitRouteByCheckpoints(line, 100, [
      checkpoint({ id: 'a', risk_level: null, represents_from_miles: 0, represents_to_miles: 100 }),
    ])
    expect(segments[0]?.level).toBeNull()
  })

  it('returns nothing for degenerate input', () => {
    expect(splitRouteByCheckpoints([[-90, 40]], 10, [checkpoint()])).toEqual([])
  })
})
