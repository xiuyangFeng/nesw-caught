/**
 * LLM Token 用量统计相关类型，与后端 `/api/llm/stats` 的返回结构对应。
 *
 * 保留手写的原因：后端 routes/llm.py 的 GET /api/llm/stats 端点未声明
 * response_model（后端已知问题），OpenAPI 中该端点的 200 响应 schema 为空，
 * openapi-typescript 无法生成对应类型。待后端补上 response_model 后，
 * 应改为从 src/types/generated/api.d.ts 取别名并删除本文件的手写定义。
 */

export interface TokenOverallStats {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface TokenModelStats {
  model_name: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  call_count: number;
}

export interface TokenOperationStats {
  operation_type: string;
  total_tokens: number;
}

export interface TokenDailyStats {
  date: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface TokenStats {
  overall: TokenOverallStats;
  models: TokenModelStats[];
  operations: TokenOperationStats[];
  daily: TokenDailyStats[];
}
