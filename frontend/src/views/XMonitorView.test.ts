import { mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import XMonitorView from './XMonitorView.vue';

const translationState = reactive<Record<string, { status: string; translated_text: string | null; error: string | null }>>({});

const xMonitorStore = reactive({
  accounts: [
    {
      id: 1,
      handle: 'DeItaone',
      display_name: 'Delta One',
      market_focus: 'us',
      is_active: true,
      priority: 100,
      tier: 'core',
      source: 'manual',
      notes: 'Macro and market headlines',
    },
    {
      id: 2,
      handle: 'MutedDesk',
      display_name: 'Muted Desk',
      market_focus: 'us',
      is_active: true,
      priority: 5,
      tier: 'muted',
      source: 'manual',
      notes: 'Too noisy',
    },
  ],
  posts: [
    {
      id: 1,
      account_handle: 'DeItaone',
      account_display_name: 'Delta One',
      content_text: 'NVDA suppliers remain in focus',
      canonical_url: 'https://x.com/DeItaone/status/190001',
      market: 'us',
      sentiment_label: 'unknown',
      relevance_score: null,
      posted_at: '2026-03-19T08:00:00Z',
      captured_at: '2026-03-19T08:01:00Z',
      symbols: ['NVDA'],
    },
    {
      id: 2,
      account_handle: 'MutedDesk',
      account_display_name: 'Muted Desk',
      content_text: 'This muted post should stay hidden',
      canonical_url: 'https://x.com/MutedDesk/status/190004',
      market: 'us',
      sentiment_label: 'unknown',
      relevance_score: null,
      posted_at: '2026-03-19T08:04:00Z',
      captured_at: '2026-03-19T08:05:00Z',
      symbols: [],
    },
  ],
  radar: {
    priority_signals: [
      {
        id: 11,
        signal_type: 'macro_event',
        title: 'Tariff pressure is building around AI semis',
        summary: 'Two tracked accounts are flagging tariff and export-control risk around AI chips.',
        market: 'us',
        topic_tag: 'macro',
        macro_tag: 'tariff',
        primary_symbol: 'NVDA',
        priority_score: 95,
        confidence_score: 0.88,
        source_count: 2,
        first_seen_at: '2026-03-19T07:40:00Z',
        last_seen_at: '2026-03-19T08:04:00Z',
      },
    ],
    macro_clusters: [
      {
        macro_tag: 'tariff',
        title: 'Tariff Watch',
        signal_count: 1,
        source_count: 2,
        top_signal_ids: [11],
      },
    ],
    evidence_stream: [
      {
        id: 1,
        account_handle: 'DeItaone',
        account_display_name: 'Delta One',
        content_text: 'NVDA suppliers remain in focus',
        canonical_url: 'https://x.com/DeItaone/status/190001',
        market: 'us',
        sentiment_label: 'unknown',
        relevance_score: null,
        posted_at: '2026-03-19T08:00:00Z',
        captured_at: '2026-03-19T08:01:00Z',
        symbols: ['NVDA'],
      },
    ],
  },
  searchQuery: 'NVDA',
  searchResults: [
    {
      id: 0,
      account_handle: 'SawyerMerritt',
      account_display_name: 'Sawyer Merritt',
      content_text: 'NVDA demand remains strong',
      canonical_url: 'https://x.com/SawyerMerritt/status/190003',
      market: 'us',
      sentiment_label: 'unknown',
      relevance_score: null,
      posted_at: '2026-03-19T08:02:00Z',
      captured_at: '2026-03-19T08:02:00Z',
      symbols: ['NVDA'],
    },
  ],
  health: {
    enabled: true,
    configured: true,
    healthy: true,
    status: 'configured',
    provider_name: 'twitterapi.io',
    min_interval_seconds: 6,
    refresh_cooldown_hours: 3,
    last_success_at: '2026-03-19T08:05:00Z',
    last_failure_at: null,
    consecutive_failures: 0,
    total_fetches: 2,
    total_failures: 0,
    avg_latency_ms: 320,
    last_error: null,
  },
  loading: false,
  healthLoading: false,
  refreshLoading: false,
  searchLoading: false,
  accountMutationLoading: false,
  importExportLoading: false,
  refreshError: null as string | null,
  accountMutationError: null as string | null,
  importExportError: null as string | null,
  usingMock: false,
  stale: false,
  lastLoadedAt: null,
  lastRefresh: null,
  searchTierFilter: '',
  filters: reactive({
    account_handle: '',
    market: '',
    q: '',
  }),
  translationsByKey: translationState,
  getTranslationKey: vi.fn((post) => post.canonical_url ?? `${post.account_handle}:${post.posted_at ?? post.captured_at}:${post.content_text}`),
  getAccountByHandle: vi.fn((handle: string) => xMonitorStore.accounts.find((item) => item.handle === handle) ?? null),
  bootstrap: vi.fn().mockResolvedValue(undefined),
  loadAccounts: vi.fn().mockResolvedValue(undefined),
  loadPosts: vi.fn().mockResolvedValue(undefined),
  loadRadar: vi.fn().mockResolvedValue(undefined),
  refreshPosts: vi.fn().mockResolvedValue(undefined),
  searchPosts: vi.fn().mockResolvedValue(undefined),
  createAccount: vi.fn().mockResolvedValue(true),
  updateAccount: vi.fn().mockResolvedValue(true),
  deleteAccount: vi.fn().mockResolvedValue(true),
  importAccounts: vi.fn().mockResolvedValue({ created_count: 0, updated_count: 0, skipped_count: 0 }),
  exportAccounts: vi.fn().mockResolvedValue({ exported_count: 0 }),
  translatePost: vi.fn().mockImplementation(async (post) => {
    const key = post.canonical_url ?? `${post.account_handle}:${post.posted_at ?? post.captured_at}:${post.content_text}`;
    translationState[key] = {
      status: 'success',
      translated_text: `中文：${post.content_text}`,
      error: null,
    };
  }),
});

vi.mock('../stores/xMonitorStore', () => ({
  useXMonitorStore: () => xMonitorStore,
}));

describe('XMonitorView', () => {
  beforeEach(() => {
    xMonitorStore.bootstrap.mockClear();
    xMonitorStore.loadAccounts.mockClear();
    xMonitorStore.loadPosts.mockClear();
    xMonitorStore.loadRadar.mockClear();
    xMonitorStore.refreshPosts.mockClear();
    xMonitorStore.searchPosts.mockClear();
    xMonitorStore.createAccount.mockClear();
    xMonitorStore.updateAccount.mockClear();
    xMonitorStore.deleteAccount.mockClear();
    xMonitorStore.importAccounts.mockClear();
    xMonitorStore.exportAccounts.mockClear();
    xMonitorStore.translatePost.mockClear();
    xMonitorStore.getTranslationKey.mockClear();
    xMonitorStore.getAccountByHandle.mockClear();
    xMonitorStore.searchTierFilter = '';
    Object.keys(translationState).forEach((key) => {
      delete translationState[key];
    });
  });

  it('renders radar sections, account management controls, and hides muted posts by default', () => {
    const wrapper = mount(XMonitorView);

    expect(wrapper.text()).toContain('X Radar');
    expect(wrapper.text()).toContain('Priority Radar');
    expect(wrapper.text()).toContain('Macro Watch');
    expect(wrapper.text()).toContain('Evidence Feed');
    expect(wrapper.text()).toContain('Tariff pressure is building around AI semis');
    expect(wrapper.text()).toContain('Tariff Watch');
    expect(wrapper.text()).toContain('账号管理');
    expect(wrapper.text()).toContain('core');
    expect(wrapper.text()).toContain('muted');
    expect(wrapper.find('[data-role="account-create-form"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="account-list"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('NVDA suppliers remain in focus');
    expect(wrapper.text()).not.toContain('This muted post should stay hidden');
  });

  it('submits the create-account form through the store', async () => {
    const wrapper = mount(XMonitorView);

    await wrapper.find('[data-role="create-handle"]').setValue('@NewDesk');
    await wrapper.find('[data-role="create-display-name"]').setValue('New Desk');
    await wrapper.find('[data-role="create-market"]').setValue('us');
    await wrapper.find('[data-role="create-tier"]').setValue('watch');
    await wrapper.find('[data-role="create-priority"]').setValue('30');
    await wrapper.find('[data-role="create-notes"]').setValue('High conviction');
    await wrapper.find('[data-role="account-create-form"]').trigger('submit');

    expect(xMonitorStore.createAccount).toHaveBeenCalledWith({
      handle: 'NewDesk',
      display_name: 'New Desk',
      market_focus: 'us',
      is_active: true,
      priority: 30,
      tier: 'watch',
      notes: 'High conviction',
    });
  });

  it('toggles account active state and deletes accounts via store actions', async () => {
    const wrapper = mount(XMonitorView);

    const toggleButtons = wrapper.findAll('[data-role="toggle-account"]');
    const deleteButtons = wrapper.findAll('[data-role="delete-account"]');

    await toggleButtons[0].trigger('click');
    await deleteButtons[0].trigger('click');

    expect(xMonitorStore.updateAccount).toHaveBeenCalledWith('DeItaone', { is_active: false });
    expect(xMonitorStore.deleteAccount).toHaveBeenCalledWith('DeItaone');
  });

  it('triggers import and export actions', async () => {
    const wrapper = mount(XMonitorView);

    await wrapper.find('[data-role="import-accounts"]').trigger('click');
    await wrapper.find('[data-role="export-accounts"]').trigger('click');

    expect(xMonitorStore.importAccounts).toHaveBeenCalledTimes(1);
    expect(xMonitorStore.exportAccounts).toHaveBeenCalledTimes(1);
  });

  it('translates monitored posts on demand and renders translated text', async () => {
    const wrapper = mount(XMonitorView);

    const translateButtons = wrapper.findAll('button[data-role="translate-button"]');
    await translateButtons[0].trigger('click');

    expect(xMonitorStore.translatePost).toHaveBeenCalledWith(xMonitorStore.posts[0]);
    expect(wrapper.text()).toContain('中文：NVDA suppliers remain in focus');
  });
});
