import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import KlineDrawingSelectionPopover from './KlineDrawingSelectionPopover.vue';

describe('KlineDrawingSelectionPopover', () => {
  it('renders single-select styling controls and multi-select group actions', async () => {
    const single = mount(KlineDrawingSelectionPopover, {
      props: {
        drawing: {
          id: 'drawing-1',
          symbol: '0700.HK',
          toolType: 'trend_line',
          createdAt: '2026-03-28T00:00:00.000Z',
          updatedAt: '2026-03-28T00:00:00.000Z',
          locked: false,
          visible: true,
          style: { color: '#ffb66d', lineWidth: 2, lineStyle: 'solid', fillOpacity: 0.18 },
          anchors: [
            { time: '2026-03-18', price: 533.2 },
            { time: '2026-03-19', price: 550.5 },
          ],
          payload: {},
        },
        selectedDrawings: [],
      },
    });

    expect(single.get('[data-role="drawing-selection-popover"]').text()).toContain('删除');
    await single.get('[data-role="drawing-line-dashed"]').trigger('click');
    expect(single.emitted('styleChange')?.[0]?.[0]).toEqual({ lineStyle: 'dashed' });

    const multi = mount(KlineDrawingSelectionPopover, {
      props: {
        drawing: null,
        selectedDrawings: [
          {
            id: 'drawing-1',
            symbol: '0700.HK',
            toolType: 'trend_line',
            createdAt: '2026-03-28T00:00:00.000Z',
            updatedAt: '2026-03-28T00:00:00.000Z',
            locked: false,
            visible: true,
            style: { color: '#ffb66d', lineWidth: 2, lineStyle: 'solid', fillOpacity: 0.18 },
            anchors: [
              { time: '2026-03-18', price: 533.2 },
              { time: '2026-03-19', price: 550.5 },
            ],
            payload: {},
          },
          {
            id: 'drawing-2',
            symbol: '0700.HK',
            toolType: 'horizontal_line',
            createdAt: '2026-03-28T00:00:00.000Z',
            updatedAt: '2026-03-28T00:00:00.000Z',
            locked: false,
            visible: true,
            style: { color: '#7dd3fc', lineWidth: 2, lineStyle: 'dashed', fillOpacity: 0 },
            anchors: [{ time: '2026-03-18', price: 540 }],
            payload: {},
          },
        ],
      },
    });

    expect(multi.get('[data-role="drawing-selection-popover"]').text()).toContain('已选 2 个对象');
    await multi.get('[data-role="drawing-group-lock-toggle"]').trigger('click');
    expect(multi.emitted('drawingGroupLockToggle')).toHaveLength(1);
    await multi.get('[data-role="drawing-group-delete"]').trigger('click');
    expect(multi.emitted('drawingGroupDelete')).toHaveLength(1);
  });
});
