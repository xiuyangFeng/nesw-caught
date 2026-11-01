import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { NewsAi, NewsImpact } from '../../types/api';

const { getNewsAi, updateNewsImpacts } = vi.hoisted(() => ({
  getNewsAi: vi.fn(),
  updateNewsImpacts: vi.fn(),
}));

vi.mock('../../api/client', () => ({
  apiClient: { getNewsAi, updateNewsImpacts },
}));

import NewsAiImpactCard from './NewsAiImpactCard.vue';

const screen = {
  importance: 3,
  overseas: true,
  deep_read: true,
  title_zh: '美联储意外降息 50 个基点',
  reason: '全球流动性拐点',
  status: 'ok',
  screened_at: '2026-11-01T01:00:00Z',
};

function buildImpact(overrides: Partial<NewsImpact> = {}): NewsImpact {
  return {
    id: 1,
    target_type: 'stock',
    code: '600519.SH',
    name: '贵州茅台',
    direction: 'bullish',
    strength: 'strong',
    rationale: '流动性宽松利好消费龙头',
    source: 'ai',
    ...overrides,
  };
}

function buildAi(overrides: Partial<NewsAi> = {}): NewsAi {
  return {
    news_id: 7,
    screen,
    analysis: {
      summary_zh: '美联储降息 50bp，超出市场预期。',
      view: '短期利好 A 股权重与消费板块',
      major: true,
      status: 'ok',
      error: null,
      analyzed_at: '2026-11-01T01:05:00Z',
    },
    impacts: [
      buildImpact(),
      buildImpact({ id: 2, target_type: 'sector', code: null, name: '银行', direction: 'bearish', strength: 'medium', rationale: '息差收窄', source: 'user' }),
    ],
    ...overrides,
  };
}

async function mountCard(data: NewsAi) {
  getNewsAi.mockResolvedValue({ data, degraded: false });
  const wrapper = mount(NewsAiImpactCard, { props: { newsId: 7 } });
  await flushPromises();
  return wrapper;
}

describe('NewsAiImpactCard', () => {
  beforeEach(() => {
    getNewsAi.mockReset();
    updateNewsImpacts.mockReset();
  });

  it('renders importance, overseas tag, translation, summary, view and impact rows', async () => {
    const wrapper = await mountCard(buildAi());

    expect(getNewsAi).toHaveBeenCalledWith(7);
    expect(wrapper.get('[data-role="news-ai-importance"]').text()).toBe('重大');
    expect(wrapper.find('[data-role="news-ai-overseas"]').exists()).toBe(true);
    expect(wrapper.get('[data-role="news-ai-title-zh"]').text()).toBe('美联储意外降息 50 个基点');
    expect(wrapper.get('[data-role="news-ai-summary"]').text()).toContain('超出市场预期');
    expect(wrapper.get('[data-role="news-ai-view"]').text()).toContain('明确看法');
    expect(wrapper.get('[data-role="news-ai-view"]').text()).toContain('短期利好 A 股权重与消费板块');

    const rows = wrapper.findAll('[data-role="news-ai-impact-row"]');
    expect(rows).toHaveLength(2);
    expect(rows[0].text()).toContain('贵州茅台');
    expect(rows[0].text()).toContain('600519.SH');
    const bullChip = rows[0].get('[data-role="news-ai-impact-chip"]');
    expect(bullChip.text()).toBe('利多·强');
    expect(bullChip.classes()).toContain('text-positive');
    expect(rows[0].find('[data-role="news-ai-impact-corrected"]').exists()).toBe(false);

    const bearChip = rows[1].get('[data-role="news-ai-impact-chip"]');
    expect(bearChip.text()).toBe('利空·中');
    expect(bearChip.classes()).toContain('text-negative');
    expect(rows[1].find('[data-role="news-ai-impact-corrected"]').exists()).toBe(true);
  });

  it('shows the not-yet-processed state when screen is null', async () => {
    const wrapper = await mountCard({ news_id: 7, screen: null, analysis: null, impacts: [] });

    expect(wrapper.get('[data-role="news-ai-not-screened"]').text()).toBe('AI 尚未处理这条新闻');
    expect(wrapper.find('[data-role="news-ai-edit"]').exists()).toBe(true);
  });

  it('shows importance, reason and the below-threshold hint when not deep-read', async () => {
    const wrapper = await mountCard({
      news_id: 7,
      screen: { ...screen, importance: 1, overseas: false, deep_read: false, reason: '常规行业动态' },
      analysis: null,
      impacts: [],
    });

    expect(wrapper.get('[data-role="news-ai-importance"]').text()).toBe('一般');
    expect(wrapper.find('[data-role="news-ai-overseas"]').exists()).toBe(false);
    const block = wrapper.get('[data-role="news-ai-not-deep-read"]');
    expect(block.text()).toContain('常规行业动态');
    expect(block.text()).toContain('未达精读标准');
  });

  it('shows the analysis error text', async () => {
    const wrapper = await mountCard(
      buildAi({
        analysis: { summary_zh: null, view: null, major: false, status: 'error', error: 'JSON 解析失败', analyzed_at: '2026-11-01T01:05:00Z' },
        impacts: [],
      }),
    );

    expect(wrapper.get('[data-role="news-ai-analysis-error"]').text()).toContain('JSON 解析失败');
  });

  it('edits direction/strength, deletes a row, adds a row and PUTs the full list', async () => {
    const wrapper = await mountCard(buildAi());
    const updated = buildAi({
      impacts: [
        buildImpact({ direction: 'bearish', strength: 'weak', source: 'user' }),
        buildImpact({ id: 3, target_type: 'sector', code: null, name: '白酒', direction: 'bullish', strength: 'medium', rationale: '需求回暖', source: 'user' }),
      ],
    });
    updateNewsImpacts.mockResolvedValue({ data: updated, degraded: false });

    await wrapper.get('[data-role="news-ai-edit"]').trigger('click');
    const drafts = wrapper.findAll('[data-role="news-ai-draft-row"]');
    expect(drafts).toHaveLength(2);

    await drafts[0].get('[data-role="news-ai-row-direction"]').setValue('bearish');
    await drafts[0].get('[data-role="news-ai-row-strength"]').setValue('weak');
    await drafts[1].get('[data-role="news-ai-row-delete"]').trigger('click');
    expect(wrapper.findAll('[data-role="news-ai-draft-row"]')).toHaveLength(1);

    await wrapper.get('[data-role="news-ai-add-type"]').setValue('sector');
    await wrapper.get('[data-role="news-ai-add-name"]').setValue(' 白酒 ');
    await wrapper.get('[data-role="news-ai-add-direction"]').setValue('bullish');
    await wrapper.get('[data-role="news-ai-add-strength"]').setValue('medium');
    await wrapper.get('[data-role="news-ai-add-rationale"]').setValue('需求回暖');
    await wrapper.get('[data-role="news-ai-add-submit"]').trigger('click');
    expect(wrapper.findAll('[data-role="news-ai-draft-row"]')).toHaveLength(2);

    await wrapper.get('[data-role="news-ai-note"]').setValue('降息对茅台其实偏空');
    await wrapper.get('[data-role="news-ai-save"]').trigger('click');
    await flushPromises();

    expect(updateNewsImpacts).toHaveBeenCalledWith(7, {
      impacts: [
        {
          target_type: 'stock',
          code: '600519.SH',
          name: '贵州茅台',
          direction: 'bearish',
          strength: 'weak',
          rationale: '流动性宽松利好消费龙头',
        },
        { target_type: 'sector', code: null, name: '白酒', direction: 'bullish', strength: 'medium', rationale: '需求回暖' },
      ],
      note: '降息对茅台其实偏空',
    });

    // 保存后退出编辑并按返回结果重新渲染
    expect(wrapper.find('[data-role="news-ai-editor"]').exists()).toBe(false);
    const rows = wrapper.findAll('[data-role="news-ai-impact-row"]');
    expect(rows).toHaveLength(2);
    expect(rows[0].get('[data-role="news-ai-impact-chip"]').text()).toBe('利空·弱');
    expect(rows[1].text()).toContain('白酒');
  });

  it('cancel restores the original rows without calling the API', async () => {
    const wrapper = await mountCard(buildAi());

    await wrapper.get('[data-role="news-ai-edit"]').trigger('click');
    await wrapper.findAll('[data-role="news-ai-row-delete"]')[0].trigger('click');
    await wrapper.get('[data-role="news-ai-cancel"]').trigger('click');

    expect(updateNewsImpacts).not.toHaveBeenCalled();
    expect(wrapper.findAll('[data-role="news-ai-impact-row"]')).toHaveLength(2);
  });

  it('keeps editing and shows the error when saving fails; omits an empty note', async () => {
    const wrapper = await mountCard({ news_id: 7, screen: null, analysis: null, impacts: [] });
    updateNewsImpacts.mockRejectedValue(new Error('name 不能为空'));

    await wrapper.get('[data-role="news-ai-edit"]').trigger('click');
    await wrapper.get('[data-role="news-ai-save"]').trigger('click');
    await flushPromises();

    expect(updateNewsImpacts).toHaveBeenCalledWith(7, { impacts: [] });
    expect(wrapper.get('[data-role="news-ai-save-error"]').text()).toContain('name 不能为空');
    expect(wrapper.find('[data-role="news-ai-editor"]').exists()).toBe(true);
  });

  it('hides the edit button when loading failed so a save cannot wipe unseen impacts', async () => {
    getNewsAi.mockRejectedValue(new Error('backend offline'));
    const wrapper = mount(NewsAiImpactCard, { props: { newsId: 7 } });
    await flushPromises();

    expect(wrapper.get('[data-role="news-ai-load-error"]').text()).toContain('backend offline');
    expect(wrapper.find('[data-role="news-ai-edit"]').exists()).toBe(false);
  });

  it('treats degraded (mock fallback) data as a load error and disables editing', async () => {
    getNewsAi.mockResolvedValue({ data: buildAi({ screen: null, analysis: null, impacts: [] }), degraded: true });
    const wrapper = mount(NewsAiImpactCard, { props: { newsId: 7 } });
    await flushPromises();

    expect(wrapper.find('[data-role="news-ai-load-error"]').exists()).toBe(true);
    expect(wrapper.find('[data-role="news-ai-edit"]').exists()).toBe(false);
  });

  it('ignores a save response that arrives after switching to another news item', async () => {
    let resolveSave: (value: unknown) => void = () => {};
    updateNewsImpacts.mockReturnValue(new Promise((resolve) => { resolveSave = resolve; }));
    const wrapper = await mountCard(buildAi());
    await wrapper.get('[data-role="news-ai-edit"]').trigger('click');
    await wrapper.get('[data-role="news-ai-save"]').trigger('click');

    const other = buildAi({ news_id: 8, impacts: [] });
    getNewsAi.mockResolvedValue({ data: other, degraded: false });
    await wrapper.setProps({ newsId: 8 });
    await flushPromises();

    resolveSave({ data: buildAi(), degraded: false });
    await flushPromises();
    expect(wrapper.findAll('[data-role="news-ai-impact-row"]')).toHaveLength(0);
  });
});
