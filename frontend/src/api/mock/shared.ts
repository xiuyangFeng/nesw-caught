// mock 数据公共基础设施：统一的“当前时间”基准与相对时间格式化工具。
// 各业务域 mock 模块共享这份基准时间，避免拆分后各文件各取各的 `new Date()` 导致时间基准漂移。

export const now = new Date();

export const isoMinutesAgo = (minutes: number) => new Date(now.getTime() - minutes * 60_000).toISOString();
export const isoMinutesFromNow = (minutes: number) => new Date(now.getTime() + minutes * 60_000).toISOString();
