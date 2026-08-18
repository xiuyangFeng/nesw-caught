import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClient = {
  getQuantLatest: vi.fn(),
  getQuantDataStatus: vi.fn(),
  getQuantRadar: vi.fn(),
  getQuantProposal: vi.fn(),
  runQuantRecommendations: vi.fn(),
};

vi.mock('../api/client', () => ({
  apiClient,
}));

const emptyLatest = {
  available: true,
  run: null,
  items: [],
  empty_reason: 'no_run_yet',
  empty_reason_detail: '尚未运行机会流水线',
};

describe('deskStore', () => {
  beforeEach(() => {
    Object.values(apiClient).forEach((fn) => fn.mockReset());
  });

  it('loads latest recommendations and data status', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useDeskStore } = await import('./deskStore');
    setActivePinia(createPinia());
    const store = useDeskStore();

    apiClient.getQuantLatest.mockResolvedValue({ data: emptyLatest, degraded: false });
    apiClient.getQuantDataStatus.mockResolvedValue({
      data: { regime: 'normal', note: '合成', pit_ready: true, dataset_version: 'synthetic-v0', factor_version: 'synthetic-v0', rule_version: 'v', backfill_progress_pct: 0 },
      degraded: false,
    });
    apiClient.getQuantRadar.mockResolvedValue({ data: { candidates: [] }, degraded: false });
    apiClient.getQuantProposal.mockResolvedValue({
      data: { cash_weight: 1, items: [], note: '无合格机会时现金为 100%。' },
      degraded: false,
    });

    await store.loadDesk();

    expect(store.latest.empty_reason).toBe('no_run_yet');
    expect(store.hasQualified).toBe(false);
    expect(store.proposal.cash_weight).toBe(1);
    expect(store.loading).toBe(false);
    expect(store.error).toBeNull();
  });

  it('reruns the synthetic pipeline', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useDeskStore } = await import('./deskStore');
    setActivePinia(createPinia());
    const store = useDeskStore();

    apiClient.runQuantRecommendations.mockResolvedValue({
      data: { ...emptyLatest, empty_reason: 'no_positive_edge' },
      degraded: false,
    });
    apiClient.getQuantLatest.mockResolvedValue({
      data: { ...emptyLatest, empty_reason: 'no_positive_edge' },
      degraded: false,
    });
    apiClient.getQuantDataStatus.mockResolvedValue({ data: { regime: 'normal', note: '', pit_ready: true, dataset_version: 'v', factor_version: 'v', rule_version: 'v', backfill_progress_pct: 0 }, degraded: false });
    apiClient.getQuantRadar.mockResolvedValue({ data: { candidates: [] }, degraded: false });
    apiClient.getQuantProposal.mockResolvedValue({
      data: { cash_weight: 1, items: [], note: '现金为合法结果' },
      degraded: false,
    });

    await store.rerun('abstain');

    expect(apiClient.runQuantRecommendations).toHaveBeenCalledWith('abstain');
    expect(store.latest.empty_reason).toBe('no_positive_edge');
    expect(store.running).toBe(false);
  });

  it('records error when load fails', async () => {
    const { createPinia, setActivePinia } = await import('pinia');
    const { useDeskStore } = await import('./deskStore');
    setActivePinia(createPinia());
    const store = useDeskStore();

    apiClient.getQuantLatest.mockRejectedValue(new Error('backend offline'));

    await expect(store.loadDesk()).rejects.toThrow('backend offline');
    expect(store.loading).toBe(false);
    expect(store.error).toBe('backend offline');
  });
});
