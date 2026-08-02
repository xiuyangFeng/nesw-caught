import { describe, expect, it } from 'vitest';

import { LLM_PROVIDER_PRESETS } from './providerPresets';

describe('LLM_PROVIDER_PRESETS', () => {
  it('contains common OpenAI-compatible services with valid docs and model defaults', () => {
    const ids = LLM_PROVIDER_PRESETS.map((preset) => preset.id);
    expect(ids).toEqual(expect.arrayContaining(['openai', 'qwen', 'deepseek', 'moonshot']));

    for (const preset of LLM_PROVIDER_PRESETS) {
      expect(new URL(preset.baseUrl).protocol).toBe('https:');
      expect(new URL(preset.docsUrl).protocol).toBe('https:');
      expect(preset.models.length).toBeGreaterThan(0);
      expect(preset.defaultModel).toBe(preset.models[0]);
    }
  });
});
