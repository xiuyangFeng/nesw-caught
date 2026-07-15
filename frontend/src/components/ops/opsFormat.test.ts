import { describe, expect, it } from 'vitest';

import { ageLabel, latencyLabel, numberLabel, ratePct, sourceTone, timeLabel, workerTone } from './opsFormat';

describe('opsFormat', () => {
  describe('timeLabel', () => {
    it('returns -- for null/undefined', () => {
      expect(timeLabel(null)).toBe('--');
      expect(timeLabel(undefined)).toBe('--');
    });

    it('formats an ISO timestamp with the HKT suffix', () => {
      expect(timeLabel('2026-07-14T02:00:00Z')).toMatch(/HKT$/);
    });
  });

  describe('ageLabel', () => {
    it('returns 无心跳 for null/undefined', () => {
      expect(ageLabel(null)).toBe('无心跳');
      expect(ageLabel(undefined)).toBe('无心跳');
    });

    it('formats seconds, minutes and hours at the right thresholds', () => {
      expect(ageLabel(45)).toBe('45s 前');
      expect(ageLabel(90)).toBe('2m 前');
      expect(ageLabel(7200)).toBe('2.0h 前');
    });
  });

  describe('ratePct', () => {
    it('returns -- for null/undefined', () => {
      expect(ratePct(null)).toBe('--');
      expect(ratePct(undefined)).toBe('--');
    });

    it('formats a 0-1 rate as a one-decimal percentage', () => {
      expect(ratePct(0.982)).toBe('98.2%');
    });
  });

  describe('latencyLabel', () => {
    it('returns -- for null/undefined', () => {
      expect(latencyLabel(null)).toBe('--');
      expect(latencyLabel(undefined)).toBe('--');
    });

    it('rounds milliseconds', () => {
      expect(latencyLabel(412.6)).toBe('413ms');
    });
  });

  describe('numberLabel', () => {
    it('formats with thousands separators', () => {
      expect(numberLabel(1234567)).toBe('1,234,567');
    });
  });

  describe('workerTone', () => {
    it('maps ok/degraded/other statuses to the right tone', () => {
      expect(workerTone('ok')).toBe('ok');
      expect(workerTone('degraded')).toBe('warning');
      expect(workerTone('stalled')).toBe('neutral');
    });
  });

  describe('sourceTone', () => {
    it('prioritizes disabled over failure count', () => {
      expect(sourceTone(0, true)).toBe('critical');
      expect(sourceTone(10, true)).toBe('critical');
    });

    it('escalates by consecutive failure count when not disabled', () => {
      expect(sourceTone(0, false)).toBe('ok');
      expect(sourceTone(2, false)).toBe('neutral');
      expect(sourceTone(5, false)).toBe('warning');
    });
  });
});
