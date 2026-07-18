/**
 * 设计令牌读取助手。
 * canvas（lightweight-charts）与部分 JS 侧场景无法直接消费 var(--xxx)，
 * 需要在 JS 侧取回令牌的具体计算值；jsdom 等无令牌环境回落到 fallback（保持既有视觉）。
 * 单主题应用，图表初始化时读取一次即可，无需监听主题变化。
 */
export function readCssVar(name: string, fallback: string): string {
  if (typeof document === 'undefined' || typeof getComputedStyle !== 'function') {
    return fallback;
  }
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

/**
 * 读取 hex 令牌并附加透明度，输出 rgba(r, g, b, alpha)。
 * 令牌缺失或非 #rrggbb 形式时按原样返回读取结果（此时透明度不生效）。
 */
export function readCssVarWithAlpha(name: string, alpha: number, fallbackHex: string): string {
  const color = readCssVar(name, fallbackHex);
  const match = /^#([0-9a-f]{6})$/i.exec(color);
  if (!match) {
    return color;
  }
  const value = parseInt(match[1], 16);
  return `rgba(${(value >> 16) & 255}, ${(value >> 8) & 255}, ${value & 255}, ${alpha})`;
}
