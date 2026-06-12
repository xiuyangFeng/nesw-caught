# Dev Launcher Market Worker Design

## Context

当前自选股行情 producer 已经独立为 `market-worker`，这让运行边界更清晰，但开发体验退化了：执行 `make dev` 时只会启动后端和前端，若忘记再单独起一个 worker，自选股接口就只能看到旧快照或 `unavailable`。

本轮目标是让本地统一开发入口重新完整，默认托管 market worker。

## Options

### Approach A: 扩展 `scripts/dev.sh`

在现有 dev launcher 中增加第三个后台进程 `market-worker`，并纳入同一套清理和存活检测逻辑。

优点：

- 改动最小，完全复用现有 `make dev -> scripts/dev.sh` 入口
- 用户习惯不需要变化
- 对本地开发最直接有效

缺点：

- `make dev` 的终端输出会更多

### Approach B: 新增 `make dev-full`

保留现有 `make dev`，另加一个全量开发命令。

优点：

- 不改现有命令语义

缺点：

- 用户仍然容易误用旧入口
- 文档和团队习惯会分叉

## Recommended Design

采用 Approach A。

### Behavior

`scripts/dev.sh` 启动三个进程：

1. backend
2. frontend
3. `market-worker`

任何一个进程退出时，脚本都应退出并清理其余两个进程。

### Logging

沿用当前简单 stdout 提示风格，额外打印：

- `starting market worker`

### Cleanup

在现有 `cleanup()` 中新增 `MARKET_WORKER_PID`，保证 `Ctrl+C`、异常退出和子进程崩溃时都能一并停止 worker。

### Testing

使用轻量测试锁定脚本内容和关键行为：

- `scripts/dev.sh` 包含 `market-worker` 启动命令
- cleanup 逻辑包含 `MARKET_WORKER_PID`
- README 对 `make dev` 的描述更新为三进程

## Expected Outcome

完成后，`make dev` 将恢复为“本地完整开发环境”入口，默认具备连续行情生产能力。
