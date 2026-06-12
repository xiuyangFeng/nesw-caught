export function formatKlinePeriod(interval: string | undefined, range: string | undefined): string {
  if (interval === '1d' && range === '1y') {
    return '日K';
  }
  if (interval === '1wk' && range === '5y') {
    return '周K';
  }
  if (interval === '1mo' && range === '10y') {
    return '月K';
  }
  if (interval === '1mo' && range === 'max') {
    return '年K';
  }
  return interval ?? '--';
}

export function formatKlineRange(interval: string | undefined, range: string | undefined): string {
  if (interval === '1d' && range === '1y') {
    return '近1年';
  }
  if (interval === '1wk' && range === '5y') {
    return '近5年';
  }
  if (interval === '1mo' && range === '10y') {
    return '近10年';
  }
  if (interval === '1mo' && range === 'max') {
    return '长期';
  }
  return range ?? '--';
}

export function indicatorPointByTime<T extends { time: string }>(points: T[], time: string | null) {
  if (!points.length) {
    return null;
  }
  if (!time) {
    return points.at(-1) ?? null;
  }
  return points.find((point) => point.time === time) ?? points.at(-1) ?? null;
}
