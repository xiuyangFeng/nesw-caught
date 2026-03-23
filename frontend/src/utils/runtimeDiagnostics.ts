import type { MarketWorkerStatus, StreamStatus } from '../types/api';
import { formatMarketTime, minutesSince } from './time';

export type RuntimeConnectionState = 'idle' | 'connecting' | 'live' | 'degraded' | 'offline';
export type RuntimeActionTarget = 'watchlist' | 'stream' | 'none';

export interface RuntimeDiagnostic {
  tone: 'success' | 'warning' | 'danger' | 'default';
  headline: string;
  detail: string;
  actionLabel: string;
  actionTarget: RuntimeActionTarget;
}

interface RuntimeDiagnosticInput {
  connectionState: RuntimeConnectionState;
  streamStatus: StreamStatus | null;
  usingMock: boolean;
  marketWorkerStatus: MarketWorkerStatus | null;
}

function isWorkerStale(status: MarketWorkerStatus): boolean {
  const referenceTime = status.last_success_at ?? status.last_heartbeat_at;
  const minutes = minutesSince(referenceTime);
  return minutes === null ? true : minutes > 10;
}

function describeWorkerReference(status: MarketWorkerStatus): string {
  const referenceTime = status.last_success_at ?? status.last_heartbeat_at;
  if (!referenceTime) {
    return '暂无最近成功或心跳记录';
  }
  const label = status.last_success_at ? '最近成功' : '最近心跳';
  return `${label}停在 ${formatMarketTime(referenceTime, 'us')} ET`;
}

export function getRuntimeDiagnostic(input: RuntimeDiagnosticInput): RuntimeDiagnostic {
  if (input.connectionState === 'offline') {
    return {
      tone: 'danger',
      headline: 'SSE 增量事件流已断开',
      detail: '新闻与行情的增量事件暂停，当前只能依赖已有快照和低频轮询。',
      actionLabel: '先检查后端 SSE 服务或等待自动重连恢复。',
      actionTarget: 'stream',
    };
  }

  if (input.connectionState === 'degraded' || input.usingMock || input.streamStatus?.status === 'degraded') {
    return {
      tone: 'warning',
      headline: '当前处于降级数据路径',
      detail: input.streamStatus?.last_error
        ? `事件流最近错误：${input.streamStatus.last_error}`
        : '前端正在使用降级路径，实时性和完整性都可能下降。',
      actionLabel: '先核对后端和 Redis 事件链路，再观察 Watchlist 是否继续更新。',
      actionTarget: 'stream',
    };
  }

  if (!input.marketWorkerStatus) {
    return {
      tone: 'danger',
      headline: 'market worker 未上报运行状态',
      detail: 'Web API 还没有收到 market_quote_producer 的 heartbeat 或成功记录。',
      actionLabel: '确认 market-worker 进程已经启动并能写入 runtime 状态。',
      actionTarget: 'stream',
    };
  }

  if (input.marketWorkerStatus.status === 'degraded') {
    return {
      tone: 'warning',
      headline: 'market worker 最近执行失败',
      detail: input.marketWorkerStatus.last_error
        ? `最近错误：${input.marketWorkerStatus.last_error}`
        : 'worker 已进入 degraded 状态，最近一轮行情生产没有稳定完成。',
      actionLabel: '打开 Watchlist 并执行“立即刷新一轮”，确认错误是否已消除。',
      actionTarget: 'watchlist',
    };
  }

  if (isWorkerStale(input.marketWorkerStatus)) {
    return {
      tone: 'warning',
      headline: 'market worker 心跳已经陈旧',
      detail: describeWorkerReference(input.marketWorkerStatus),
      actionLabel: '打开 Watchlist 执行“立即刷新一轮”，并确认 worker 仍在持续产出。',
      actionTarget: 'watchlist',
    };
  }

  return {
    tone: 'success',
    headline: '行情生产链路运行正常',
    detail: describeWorkerReference(input.marketWorkerStatus),
    actionLabel: '当前无需动作，继续观察后续增量更新即可。',
    actionTarget: 'none',
  };
}
