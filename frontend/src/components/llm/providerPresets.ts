export interface LlmProviderPreset {
  id: string;
  name: string;
  shortName: string;
  description: string;
  baseUrl: string;
  docsUrl: string;
  defaultModel: string;
  models: string[];
}

export const LLM_PROVIDER_PRESETS: LlmProviderPreset[] = [
  {
    id: 'openai',
    name: 'OpenAI',
    shortName: 'OpenAI',
    description: 'OpenAI 官方 Chat Completions 兼容地址',
    baseUrl: 'https://api.openai.com/v1',
    docsUrl: 'https://platform.openai.com/docs/api-reference/chat',
    defaultModel: 'gpt-4.1-mini',
    models: ['gpt-4.1-mini', 'gpt-4.1', 'gpt-4o-mini'],
  },
  {
    id: 'qwen',
    name: '通义千问 Qwen',
    shortName: 'Qwen',
    description: '阿里云百炼 DashScope OpenAI 兼容模式',
    baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    docsUrl: 'https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope',
    defaultModel: 'qwen-plus',
    models: ['qwen-plus', 'qwen-max', 'qwen-turbo', 'qwq-plus'],
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    shortName: 'DeepSeek',
    description: '支持通用对话与 reasoning_content 推理流',
    baseUrl: 'https://api.deepseek.com/v1',
    docsUrl: 'https://api-docs.deepseek.com/',
    defaultModel: 'deepseek-chat',
    models: ['deepseek-chat', 'deepseek-reasoner'],
  },
  {
    id: 'moonshot',
    name: 'Moonshot / Kimi',
    shortName: 'Kimi',
    description: 'Moonshot 开放平台 OpenAI-compatible API',
    baseUrl: 'https://api.moonshot.cn/v1',
    docsUrl: 'https://platform.moonshot.cn/docs/api/chat',
    defaultModel: 'moonshot-v1-8k',
    models: ['moonshot-v1-8k', 'moonshot-v1-32k', 'moonshot-v1-128k'],
  },
  {
    id: 'siliconflow',
    name: 'SiliconFlow 硅基流动',
    shortName: 'SiliconFlow',
    description: '聚合多种开源与国产模型的统一兼容接口',
    baseUrl: 'https://api.siliconflow.cn/v1',
    docsUrl: 'https://docs.siliconflow.cn/cn/api-reference/chat-completions/chat-completions',
    defaultModel: 'Qwen/Qwen3-8B',
    models: ['Qwen/Qwen3-8B', 'deepseek-ai/DeepSeek-V3'],
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    shortName: 'Gemini',
    description: 'Gemini API 的 OpenAI compatibility 接口',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
    docsUrl: 'https://ai.google.dev/gemini-api/docs/openai',
    defaultModel: 'gemini-2.5-flash',
    models: ['gemini-2.5-flash', 'gemini-2.5-pro'],
  },
];
