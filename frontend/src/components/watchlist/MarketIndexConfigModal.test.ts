import { flushPromises, mount } from '@vue/test-utils';
import { reactive } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MarketIndexConfigModal from './MarketIndexConfigModal.vue';

const store = reactive({
  indexConfigs: [
    { id: 1, symbol: '^GSPC', market: 'us', display_name: '标普500', kind: 'index', sort_order: 0, enabled: true },
    { id: 2, symbol: '^IXIC', market: 'us', display_name: '纳斯达克', kind: 'index', sort_order: 1, enabled: false },
    { id: 5, symbol: '000300.SS', market: 'cn', display_name: '沪深300', kind: 'index', sort_order: 0, enabled: true },
  ],
  configSaving: false,
  configError: null as string | null,
  loadIndexConfig: vi.fn(async () => undefined),
  createIndexConfig: vi.fn(async () => undefined),
  updateIndexConfig: vi.fn(async () => undefined),
  deleteIndexConfig: vi.fn(async () => undefined),
});

vi.mock('../../stores/marketOverviewStore', () => ({
  useMarketOverviewStore: () => store,
}));

function mountModal(open = true) {
  return mount(MarketIndexConfigModal, { props: { open } });
}

describe('MarketIndexConfigModal', () => {
  beforeEach(() => {
    store.indexConfigs = [
      { id: 1, symbol: '^GSPC', market: 'us', display_name: '标普500', kind: 'index', sort_order: 0, enabled: true },
      { id: 2, symbol: '^IXIC', market: 'us', display_name: '纳斯达克', kind: 'index', sort_order: 1, enabled: false },
      { id: 5, symbol: '000300.SS', market: 'cn', display_name: '沪深300', kind: 'index', sort_order: 0, enabled: true },
    ];
    store.configSaving = false;
    store.configError = null;
    store.loadIndexConfig.mockClear();
    store.createIndexConfig.mockClear();
    store.updateIndexConfig.mockClear();
    store.deleteIndexConfig.mockClear();
  });

  it('loads the config list when opened and groups rows by market', async () => {
    const wrapper = mountModal(true);
    await flushPromises();

    expect(store.loadIndexConfig).toHaveBeenCalledTimes(1);
    expect(wrapper.get('[data-role="config-group-us"]').text()).toContain('^GSPC');
    expect(wrapper.get('[data-role="config-group-cn"]').text()).toContain('000300.SS');
  });

  it('blocks add submit when symbol or display name is empty', async () => {
    const wrapper = mountModal(true);
    await flushPromises();

    await wrapper.get('[data-role="config-add-submit"]').trigger('click');
    expect(store.createIndexConfig).not.toHaveBeenCalled();
    expect(wrapper.get('[data-role="config-add-error"]').text()).toContain('请填写指数代码');

    await wrapper.get('[data-role="config-add-symbol"]').setValue('^NDX');
    await wrapper.get('[data-role="config-add-submit"]').trigger('click');
    expect(store.createIndexConfig).not.toHaveBeenCalled();
    expect(wrapper.get('[data-role="config-add-error"]').text()).toContain('请填写展示名称');
  });

  it('creates a new config through the store action and clears the form', async () => {
    const wrapper = mountModal(true);
    await flushPromises();

    await wrapper.get('[data-role="config-add-market"]').setValue('eu');
    await wrapper.get('[data-role="config-add-symbol"]').setValue('^FTSE');
    await wrapper.get('[data-role="config-add-name"]').setValue('富时100');
    await wrapper.get('[data-role="config-add-kind"]').setValue('index');
    await wrapper.get('[data-role="config-add-submit"]').trigger('click');
    await flushPromises();

    expect(store.createIndexConfig).toHaveBeenCalledWith({
      symbol: '^FTSE',
      market: 'eu',
      display_name: '富时100',
      kind: 'index',
    });
    expect((wrapper.get('[data-role="config-add-symbol"]').element as HTMLInputElement).value).toBe('');
  });

  it('toggles enabled via the store update action', async () => {
    const wrapper = mountModal(true);
    await flushPromises();

    await wrapper.get('[data-role="config-toggle-1"]').trigger('click');
    await flushPromises();

    expect(store.updateIndexConfig).toHaveBeenCalledWith(1, { enabled: false });
  });

  it('saves row edits (display name and sort order) via PATCH payload', async () => {
    const wrapper = mountModal(true);
    await flushPromises();

    await wrapper.get('[data-role="config-name-input-1"]').setValue('标普500指数');
    await wrapper.get('[data-role="config-sort-input-1"]').setValue('3');
    await wrapper.get('[data-role="config-save-1"]').trigger('click');
    await flushPromises();

    expect(store.updateIndexConfig).toHaveBeenCalledWith(1, {
      display_name: '标普500指数',
      sort_order: 3,
    });
  });

  it('deletes a row only after confirmation', async () => {
    const confirmMock = vi.fn(() => false);
    vi.stubGlobal('confirm', confirmMock);

    const wrapper = mountModal(true);
    await flushPromises();

    await wrapper.get('[data-role="config-delete-1"]').trigger('click');
    expect(store.deleteIndexConfig).not.toHaveBeenCalled();

    confirmMock.mockReturnValue(true);
    await wrapper.get('[data-role="config-delete-1"]').trigger('click');
    await flushPromises();
    expect(store.deleteIndexConfig).toHaveBeenCalledWith(1);

    vi.unstubAllGlobals();
  });

  it('emits close when the close button is clicked', async () => {
    const wrapper = mountModal(true);
    await flushPromises();

    await wrapper.get('[data-role="market-index-config-close"]').trigger('click');

    expect(wrapper.emitted('close')).toHaveLength(1);
  });

  it('surfaces store mutation errors inline and keeps the modal open', async () => {
    store.configError = '同市场下 symbol 已存在';
    store.createIndexConfig.mockRejectedValueOnce(new Error('conflict'));

    const wrapper = mountModal(true);
    await flushPromises();

    await wrapper.get('[data-role="config-add-symbol"]').setValue('^GSPC');
    await wrapper.get('[data-role="config-add-name"]').setValue('重复项');
    await wrapper.get('[data-role="config-add-submit"]').trigger('click');
    await flushPromises();

    expect(wrapper.get('[data-role="config-store-error"]').text()).toContain('同市场下 symbol 已存在');
    expect(wrapper.emitted('close')).toBeUndefined();
  });
});
