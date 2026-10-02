import { describe, expect, it } from 'vitest';
import { plural } from './plural';

describe('plural', () => {
  it('follows Czech count agreement', () => {
    const word = (n) => plural(n, 'fotografie', 'fotografie', 'fotografií');
    expect([0, 1, 2, 4, 5, 11, 22].map(word)).toEqual([
      'fotografií', 'fotografie', 'fotografie', 'fotografie', 'fotografií', 'fotografií', 'fotografií',
    ]);
    expect([1, 3, 7].map((n) => plural(n, 'odznak', 'odznaky', 'odznaků')))
      .toEqual(['odznak', 'odznaky', 'odznaků']);
  });
});
