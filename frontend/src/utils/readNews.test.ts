import { computed } from 'vue';
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

  it('useReadNewsIds 是响应式的,可作为 computed 依赖', () => {
    // 用真实的 Vue computed 验证响应性契约（Task 9 依赖此契约作为 computed 依赖源）：
    // 若返回的 Set 不是 reactive，computed 缓存不会因 markNewsRead 而失效，
    // count.value 会一直停留在初始值 0，无法仅靠同引用上的 has() 断言发现该问题。
    const ids = useReadNewsIds();
    const count = computed(() => ids.size);
    expect(count.value).toBe(0);
    markNewsRead(42);
    expect(count.value).toBe(1);
    expect(computed(() => ids.has(42)).value).toBe(true);
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
