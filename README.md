# News Caught

本项目包含：

- `backend/`: FastAPI + SQLAlchemy 后端
- `frontend/`: Vue 3 + Vite 前端

## 环境准备

推荐直接用根目录的 `environment.yml` 创建 conda 环境：

```bash
cd /Users/xiuyang/Desktop/news-caught
conda env create -f environment.yml
conda activate news-caught
```

如果环境已经存在，更新环境：

```bash
conda env update -f environment.yml --prune
conda activate news-caught
```

然后安装前端 Node 依赖：

```bash
npm --prefix frontend install
```

## 启动项目

启动后端：

```bash
conda run -n news-caught uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

启动前端：

```bash
npm --prefix frontend run dev
```

前端开发服务器默认地址是 `http://127.0.0.1:5174`，并将 `/api` 代理到 `http://127.0.0.1:8000`。

## 常用命令

也可以直接使用根目录 `Makefile`：

```bash
make setup
make dev
make backend
make frontend
make test
```

如果你想一次启动前后端开发服务：

```bash
make dev
```

`make dev` 会同时启动：

- 后端 `http://127.0.0.1:8000`
- 前端 `http://127.0.0.1:5174`

按 `Ctrl+C` 会一起停止两个进程。

## 验证

后端测试：

```bash
conda run -n news-caught pytest backend/tests
```

前端构建检查：

```bash
npm --prefix frontend run build
```

## 变更记录要求

项目根目录下的 [ANGENT.md](/Users/xiuyang/Desktop/news-caught/ANGENT.md) 已生效。

从现在开始，任何代码、配置、文档、脚本、接口或测试修改，都必须同步回填到：

- [docs/code-change-log.md](/Users/xiuyang/Desktop/news-caught/docs/code-change-log.md)

如果修改完成但没有更新该记录文件，则该修改视为不完整。
