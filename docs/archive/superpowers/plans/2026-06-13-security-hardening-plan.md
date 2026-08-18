# 2026-06-13 安全加固实施计划

## 实施阶段拆解

### 阶段 1: 密钥与防提交机制 (Git 级防御)
- **1.1 优化 `.gitignore`**
  - 增加针对 `.env` 子目录版本、`app_token`、`secret_key` 等文件的显式屏蔽规则，确保密钥绝不会意外提交。
- **1.2 编写静态密钥检查脚本 `scripts/check_secrets.py`**
  - 使用正则在提交前和静态测试中扫描项目是否含有明文的 API Key。

### 阶段 2: 飞书密钥本地加密 (数据级防御)
- **2.1 修改 `FeishuNotifyConfig` 数据模型**
  - 增加解密属性 `decrypted_app_secret`。
- **2.2 修改 `FeishuNotifyConfigRepository` 存储逻辑**
  - 接入 `encrypt_key` 和 `decrypt_key`，在 upsert 时将明文 `app_secret` 进行 Fernet 加密存储。
- **2.3 替换调用点**
  - 把 `FeishuClient` 的发送和初始化从原先直接读取 `config.app_secret` 改为使用 `config.decrypted_app_secret`。
- **2.4 编写或更新测试**
  - 针对飞书配置加密逻辑编写单元测试（遵循 TDD，先写失败测试，然后实现，再通过测试）。

### 阶段 3: 防御 Base URL 劫持窃取 (逻辑级防御)
- **3.1 修改 `LLMProviderConfigRepository.upsert_config` 逻辑**
  - 判断如果在修改时，`base_url` 被变更，但 `api_key` 没有提供新明文（即包含星号掩码），抛出 `ValueError`。
- **3.2 编写单元测试**
  - 验证当只更改大模型 API 路径却不重新提供明文 key 时，操作被安全地拦截，原有密钥不泄露。

### 阶段 4: 本地临时认证令牌 (App Token) 机制与 Host 绑定限制 (网络级防御)
- **4.1 将 host 限制为 `127.0.0.1`**
  - 替换 `Makefile` 和 `scripts/dev.sh` 中前端 `npm run dev` 和后端 `uvicorn` 的 `--host 0.0.0.0` 为 `--host 127.0.0.1`。
- **4.2 后端生成与校验 `app_token`**
  - 在 `backend/app/core/auth.py` 中编写 token 生成、读取以及 FastAPI 依赖 `verify_app_token`。
  - 在后端启动生命周期 `lifespan` 阶段自动生成（只对 600 权限的本地文件有效）。
- **4.3 全局应用依赖**
  - 在 `backend/app/api/router.py` 的全局 `api_router` 加上 `dependencies=[Depends(verify_app_token)]`，并对 `/health` 等基础探活做免除或只在特定子路由放行。
- **4.4 前端打包注入与 Fetch 拦截**
  - 在 `frontend/vite.config.ts` 里加入读取 `data/.app_token` 并注入 `define: { __APP_TOKEN__: ... }`。
  - 在 `frontend/src/main.ts` 或相关入口中，全局 monkey patch 包装 `window.fetch`，对于 `/api/` 开头的请求自动带上请求头 `X-App-Token`。
- **4.5 编写安全拦截测试**
  - 验证没有发送 `X-App-Token` 头部或值错误时，所有 API 接口返回 401。

### 阶段 5: 回收验证与收尾
- **5.1 运行所有测试**
  - 运行 `pytest` 确认全部通过。
  - 运行 `npm run build` 确认前端编译通过。
- **5.2 记录变更日志**
  - 回填 [docs/code-change-log.md](file:///Users/xiuyang/Desktop/news-caught/docs/code-change-log.md) 和 [README.md](file:///Users/xiuyang/Desktop/news-caught/README.md)。
