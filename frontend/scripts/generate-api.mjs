#!/usr/bin/env node
/**
 * 从后端 FastAPI 导出 OpenAPI schema 并生成 TypeScript 类型。
 *
 * 用法(在 frontend/ 下):
 *   npm run generate:api        重新生成 openapi.json 与 src/types/generated/api.d.ts
 *   npm run check:api-drift     重新生成到临时目录并与仓库内文件比对,发现漂移则退出码 1
 *
 * 后端 Python 解释器默认使用 `conda run -n news-caught python`,
 * CI 等无 conda 环境可通过环境变量 OPENAPI_PYTHON 覆盖(如 OPENAPI_PYTHON=python)。
 */
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const REPO_ROOT = path.resolve(FRONTEND_DIR, '..');
const EXPORT_SCRIPT = path.join(REPO_ROOT, 'scripts', 'export_openapi.py');
const OPENAPI_PATH = path.join(FRONTEND_DIR, 'openapi.json');
const GENERATED_PATH = path.join(FRONTEND_DIR, 'src', 'types', 'generated', 'api.d.ts');

const BANNER = [
  '// 本文件由 `npm run generate:api` 从后端 FastAPI 的 OpenAPI schema 自动生成。',
  '// 自动生成勿手改!后端 schema 变更后请重新运行 npm run generate:api。',
  '',
].join('\n');

const checkMode = process.argv.includes('--check');

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: 'inherit', ...options });
  if (result.error) {
    console.error(`[generate-api] failed to run ${command}: ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) {
    console.error(`[generate-api] ${command} ${args.join(' ')} exited with ${result.status}`);
    process.exit(result.status ?? 1);
  }
}

function exportOpenapi(outputPath) {
  const pythonCmd = (process.env.OPENAPI_PYTHON ?? 'conda run -n news-caught python').split(' ');
  run(pythonCmd[0], [...pythonCmd.slice(1), EXPORT_SCRIPT, outputPath], { cwd: REPO_ROOT });
}

function generateTypes(openapiPath, outputPath) {
  const bin = path.join(FRONTEND_DIR, 'node_modules', '.bin', process.platform === 'win32' ? 'openapi-typescript.cmd' : 'openapi-typescript');
  run(bin, [openapiPath, '-o', outputPath], { cwd: FRONTEND_DIR });
  writeFileSync(outputPath, BANNER + readFileSync(outputPath, 'utf8'));
}

if (!checkMode) {
  exportOpenapi(OPENAPI_PATH);
  generateTypes(OPENAPI_PATH, GENERATED_PATH);
  console.log('[generate-api] wrote frontend/openapi.json and src/types/generated/api.d.ts');
} else {
  const tempDir = mkdtempSync(path.join(tmpdir(), 'openapi-drift-'));
  try {
    const freshOpenapi = path.join(tempDir, 'openapi.json');
    const freshTypes = path.join(tempDir, 'api.d.ts');
    exportOpenapi(freshOpenapi);
    generateTypes(freshOpenapi, freshTypes);

    const drifted = [];
    for (const [committed, fresh, label] of [
      [OPENAPI_PATH, freshOpenapi, 'frontend/openapi.json'],
      [GENERATED_PATH, freshTypes, 'frontend/src/types/generated/api.d.ts'],
    ]) {
      const committedContent = existsSync(committed) ? readFileSync(committed, 'utf8') : null;
      if (committedContent !== readFileSync(fresh, 'utf8')) {
        drifted.push(label);
      }
    }

    if (drifted.length > 0) {
      console.error('[check:api-drift] 检测到前后端 API 类型漂移,以下文件与后端当前 schema 不一致:');
      for (const label of drifted) {
        console.error(`  - ${label}`);
      }
      console.error('[check:api-drift] 请运行 `npm run generate:api` 并提交更新后的生成文件。');
      process.exit(1);
    }
    console.log('[check:api-drift] OK: 生成文件与后端 schema 一致');
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}
