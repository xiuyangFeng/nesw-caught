import { beforeEach, describe, expect, it } from 'vitest';

import { isNewsRead, markNewsRead, resetReadNewsForTest, useReadNewsIds } from './readNews';

describe('readNews', () => {
  beforeEach(() => {
    resetReadNewsForTest();
  });

  it('标记后 isNewsRead 为 true 且持久化到 localStorage', () => {
    expect(isNewsRead(1)).toBe(false);
    markNewsRead(1);
    expect(isNewsRead(1)).toBe(true);
    expect(JSON.parse(localStorage.getItem('news-caught:read-news-ids') ?? '[]')).toContain(1);
  });

  it('useReadNewsIds 返回响应式集合', () => {
    const ids = useReadNewsIds();
    markNewsRead(42);
    expect(ids.has(42)).toBe(true);
  });

  it('超过 2000 条时 FIFO 淘汰最早的', () => {
    for (let i = 0; i < 2001; i += 1) {
      markNewsRead(i);
    }
    expect(isNewsRead(0)).toBe(false);
    expect(isNewsRead(2000)).toBe(true);
    expect(useReadNewsIds().size).toBe(2000);
  });

  it('重复标记不改变集合大小', () => {
    markNewsRead(7);
    markNewsRead(7);
    expect(useReadNewsIds().size).toBe(1);
  });
});
