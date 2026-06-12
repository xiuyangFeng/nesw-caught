import { describe, expect, it } from 'vitest';

import { SENTIMENT_COLORS, buildMarkers, getDominantSentiment } from './useKlineMarkers';
import type { NewsEventMarker } from '../types/api';

describe('useKlineMarkers helpers', () => {
  it('uses 红涨绿跌 sentiment colors', () => {
    expect(SENTIMENT_COLORS.positive).toBe('#ff6f86');
    expect(SENTIMENT_COLORS.negative).toBe('#39c884');
  });

  it('picks dominant sentiment and builds marker metadata', () => {
    const event: NewsEventMarker = {
      time: '2024-01-02',
      items: [
        { id: 1, sentiment: 'positive', title: 'A', summary: '' },
        { id: 2, sentiment: 'positive', title: 'B', summary: '' },
        { id: 3, sentiment: 'negative', title: 'C', summary: '' },
      ],
    };

    expect(getDominantSentiment(event.items)).toBe('positive');

    const [marker] = buildMarkers([event]);
    expect(marker).toMatchObject({
      time: '2024-01-02',
      position: 'belowBar',
      color: '#ff6f86',
      shape: 'circle',
      text: '3',
      size: 5,
    });
  });
});
