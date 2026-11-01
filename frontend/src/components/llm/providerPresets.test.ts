import { describe, expect, it } from 'vitest';

import { LLM_PROVIDER_PRESETS } from './providerPresets';

describe('LLM_PROVIDER_PRESETS', () => {
  it('contains common OpenAI-compatible services with valid docs and model defaults', () => {
    const ids = LLM_PROVIDER_PRESETS.map((preset) => preset.id);
    expect(ids).toEqual(expect.arrayContaining(['openai', 'qwen', 'deepseek', 'moonshot']));

    for (const preset of LLM_PROVIDER_PRESETS) {
      // 中转类预设的地址/文档因人而异，留空由用户填写；非空时必须是 https。
      if (preset.baseUrl) {
        expect(new URL(preset.baseUrl).protocol).toBe('https:');
      }
      if (preset.docsUrl) {
        expect(new URL(preset.docsUrl).protocol).toBe('https:');
      }
      expect(preset.models.length).toBeGreaterThan(0);
      expect(preset.defaultModel).toBe(preset.models[0]);
    }
  });

  it('offers a gpt-6.1-terra relay preset with an empty base url and per-1M prices', () => {
    const terra = LLM_PROVIDER_PRESETS.find((preset) => preset.id === 'terra');
    expect(terra).toBeDefined();
    expect(terra!.defaultModel).toBe('gpt-6.1-terra');
    expect(terra!.name).toContain('中转');
    expect(terra!.baseUrl).toBe('');
    expect(terra!.inputPricePer1m).toBe(0.15);
    expect(terra!.outputPricePer1m).toBe(0.75);
  });
});
