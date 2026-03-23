# Dev Launcher Port Guard Design

**背景**

`make dev` 当前直接并行拉起 backend、frontend 和 market worker，但没有处理两个关键问题：

1. `8000` 或 `5174` 已被旧开发进程占用时，新进程会启动失败。
2. backend 启动失败或很快退出时，frontend 可能仍然存活，用户会看到页面，但所有 `/api/*` 请求经 Vite 代理后报 `ECONNREFUSED 127.0.0.1:8000`，K 线因没有 mock fallback 会直接显示加载失败。

**目标**

让 `scripts/dev.sh` 在本地开发场景下更稳：

- 启动前清理 `8000` 和 `5174` 上的旧监听进程
- backend 启动后等待健康可达，再继续启动 frontend 和 worker
- 任一核心进程在启动阶段早退时立即失败退出，不留下“前端还活着、后端已经死掉”的半启动状态

**方案**

在 `scripts/dev.sh` 中增加三个小型 shell helper：

- `kill_listeners_for_port(port)`：通过 `lsof` 找出监听指定端口的 PID 并终止，忽略当前脚本尚未启动的空结果
- `wait_for_http(url, retries, delay)`：轮询 backend 的 HTTP 接口，确认服务已经真正可达
- `wait_for_process_start(pid, name)`：在短窗口内检测进程是否提前退出，若已退出则立即返回失败

启动顺序调整为：

1. 清理 `8000`、`5174`
2. 启动 backend
3. 短窗口检查 backend 进程没有立刻退出
4. 轮询 `GET /api/stream/status`，确认 backend 可用
5. 启动 frontend 和 market worker
6. 继续维持现有“任一子进程退出则整体退出并清理”的模型

**取舍**

- 不引入新的 Python 启动器，保持现有 bash 方案，修改面最小
- 不尝试识别“是否属于本项目”的监听进程；在 `make dev` 语义下，端口冲突即视为旧开发进程，直接清理
- backend 就绪判断复用已有 API，而不是新增健康探针契约

**测试策略**

- 为 `backend/tests/test_dev_launcher.py` 增加静态断言，覆盖新增 helper、端口清理和 backend readiness wait
- 手动验证 `make dev` / `scripts/dev.sh` 在端口已被占用时能自动清理并成功启动

**风险**

- 启动脚本会主动终止占用 `8000`、`5174` 的监听进程，因此仅适用于本地开发，不适合生产环境
- 测试仍是脚本内容级静态校验，不做完整进程集成测试
