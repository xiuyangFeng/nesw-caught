import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import type { OpsLlmUsage } from '../../types/api';
import OpsLlmUsageCard from './OpsLlmUsageCard.vue';

function buildLlmUsage(overrides: Partial<OpsLlmUsage> = {}): OpsLlmUsage {
  return {
    window_hours: 24,
    call_count: 42,
    total_tokens: 123456,
    prompt_tokens: 100000,
    completion_tokens: 23456,
    models: [
      { model_name: 'gpt-4o-mini', call_count: 30, total_tokens: 90000, prompt_tokens: 70000, completion_tokens: 20000 },
    ],
    ...overrides,
  };
}

describe('OpsLlmUsageCard', () => {
  it('falls back to a 24h window and zeroed stats plus the no-calls hint when usage is null', () => {
    const wrapper = mount(OpsLlmUsageCard, { props: { llmUsage: null } });

    expect(wrapper.text()).toContain('近 24h');
    expect(wrapper.text()).toContain('0 次');
    expect(wrapper.text()).toContain('近 24h 无 LLM 调用');
  });

  it('renders the token stat grid and a row per model when usage is present', () => {
    const wrapper = mount(OpsLlmUsageCard, { props: { llmUsage: buildLlmUsage() } });

    expect(wrapper.text()).toContain('42 次');
    expect(wrapper.text()).toContain('123,456');
    expect(wrapper.text()).toContain('100,000');
    expect(wrapper.text()).toContain('23,456');
    expect(wrapper.text()).toContain('gpt-4o-mini');
    expect(wrapper.text()).toContain('90,000 tok · 30 次');
    expect(wrapper.text()).not.toContain('近 24h 无 LLM 调用');
  });

  it('shows the no-calls hint when usage is present but has zero models', () => {
    const wrapper = mount(OpsLlmUsageCard, {
      props: { llmUsage: buildLlmUsage({ models: [], call_count: 0, total_tokens: 0, prompt_tokens: 0, completion_tokens: 0 }) },
    });

    expect(wrapper.text()).toContain('近 24h 无 LLM 调用');
  });
});
