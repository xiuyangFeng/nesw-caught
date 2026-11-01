import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { FocusSector } from '../../types/api';

const { getFocusSectors, addFocusSector, removeFocusSector } = vi.hoisted(() => ({
  getFocusSectors: vi.fn(),
  addFocusSector: vi.fn(),
  removeFocusSector: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  apiClient: { getFocusSectors, addFocusSector, removeFocusSector },
}));

import FocusSectorsBar from './FocusSectorsBar.vue';

const aiSector: FocusSector = { name: '白酒', source: 'ai', symbols: ['600519.SH', '000858.SZ'] };
const userSector: FocusSector = { name: '半导体', source: 'user', symbols: [] };

describe('FocusSectorsBar', () => {
  beforeEach(() => {
    [getFocusSectors, addFocusSector, removeFocusSector].forEach((fn) => fn.mockReset());
  });

  it('shows the hint when there are no focus sectors', async () => {
    getFocusSectors.mockResolvedValue({ data: [], degraded: false });
    const wrapper = mount(FocusSectorsBar);
    await flushPromises();

    expect(wrapper.get('[data-role="focus-sectors-empty"]').text()).toBe('AI 会根据自选股自动推断板块，也可以手动添加');
  });

  it('renders chips with source marker and symbol tooltip', async () => {
    getFocusSectors.mockResolvedValue({ data: [aiSector, userSector], degraded: false });
    const wrapper = mount(FocusSectorsBar);
    await flushPromises();

    const chips = wrapper.findAll('[data-role="focus-sector-chip"]');
    expect(chips).toHaveLength(2);
    expect(chips[0].text()).toContain('白酒');
    expect(chips[0].get('[data-role="focus-sector-source"]').text()).toBe('AI');
    expect(chips[0].attributes('title')).toContain('600519.SH、000858.SZ');
    expect(chips[1].get('[data-role="focus-sector-source"]').text()).toBe('手动');
    expect(chips[1].attributes('title')).toBe('手动添加');
    expect(wrapper.find('[data-role="focus-sectors-empty"]').exists()).toBe(false);
  });

  it('adds a sector and renders the returned full list', async () => {
    getFocusSectors.mockResolvedValue({ data: [aiSector], degraded: false });
    addFocusSector.mockResolvedValue({ data: [aiSector, userSector], degraded: false });
    const wrapper = mount(FocusSectorsBar);
    await flushPromises();

    await wrapper.get('[data-role="focus-sector-input"]').setValue(' 半导体 ');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(addFocusSector).toHaveBeenCalledWith('半导体');
    expect(wrapper.findAll('[data-role="focus-sector-chip"]')).toHaveLength(2);
    expect((wrapper.get('[data-role="focus-sector-input"]').element as HTMLInputElement).value).toBe('');
  });

  it('removes a sector and reloads the list', async () => {
    getFocusSectors
      .mockResolvedValueOnce({ data: [aiSector, userSector], degraded: false })
      .mockResolvedValueOnce({ data: [userSector], degraded: false });
    removeFocusSector.mockResolvedValue({ data: undefined, degraded: false });
    const wrapper = mount(FocusSectorsBar);
    await flushPromises();

    await wrapper.findAll('[data-role="focus-sector-remove"]')[0].trigger('click');
    await flushPromises();

    expect(removeFocusSector).toHaveBeenCalledWith('白酒');
    expect(getFocusSectors).toHaveBeenCalledTimes(2);
    const chips = wrapper.findAll('[data-role="focus-sector-chip"]');
    expect(chips).toHaveLength(1);
    expect(chips[0].text()).toContain('半导体');
  });

  it('shows an error when adding fails', async () => {
    getFocusSectors.mockResolvedValue({ data: [], degraded: false });
    addFocusSector.mockRejectedValue(new Error('板块名称过长'));
    const wrapper = mount(FocusSectorsBar);
    await flushPromises();

    await wrapper.get('[data-role="focus-sector-input"]').setValue('x');
    await wrapper.get('form').trigger('submit');
    await flushPromises();

    expect(wrapper.get('[data-role="focus-sectors-error"]').text()).toContain('板块名称过长');
  });
});
