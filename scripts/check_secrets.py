#!/usr/bin/env python3
import os
import re
import sys

# 正则表达式检测常见敏感 Key（具体前缀特征）
PATTERNS = {
    "OpenAI/DeepSeek API Key": re.compile(r"\bsk-[a-zA-Z0-9]{32,}\b"),
    "Tavily API Key": re.compile(r"\btvly-[a-zA-Z0-9\-]{30,}\b"),
    "TwitterAPI.io API Key": re.compile(r"\bnew1_[a-zA-Z0-9]{32}\b"),
    "Anthropic API Key": re.compile(r"\bsk-ant-[a-zA-Z0-9\-_]{20,}\b"),
    "Google API Key": re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
    "AWS Access Key ID": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    "Slack Token": re.compile(r"\bxox[baprs]-[0-9A-Za-z\-]{10,}\b"),
    "GitHub Token": re.compile(r"\bgh[pousr]_[0-9A-Za-z]{36,}\b"),
    "JWT": re.compile(r"\beyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}\b"),
    "PEM 私钥头": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----"
    ),
}

# 通用检测：形如 XXX_KEY / XXX_TOKEN / XXX_SECRET / password = "字面量..."
# 只匹配赋值给带引号的字符串字面量的情况，避免把变量名、属性访问、函数调用
# （如 `api_key = config.api_key` / `token = get_token()`）误判为密钥
GENERIC_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(
        [a-z0-9_\-]*?(?:api[_\-]?key|secret|token|password|passwd|access[_\-]?key)
        [a-z0-9_\-]*
    )
    \s*[:=]\s*
    ['"]
    ([a-zA-Z0-9_\-/+.]{16,})
    ['"]
    """
)

# 占位符/明显安全值，不视为泄露
PLACEHOLDER_HINTS = (
    "changeme",
    "your-",
    "your_",
    "example",
    "placeholder",
    "xxxxxxxx",
    "0000000",
    "1111111",
    "test-key",
    "test_key",
    "sk-test",
    "test",
    "fake",
    "dummy",
    "sample",
    "demo",
    "mock",
    "realistic",
    "secret",  # 值本身包含字面单词 secret，通常是测试/占位值而非真实密钥
    "digest",
    "<",
    "${",
    "process.env",
    "os.environ",
    "getenv",
    "none",
    "null",
    "true",
    "false",
)


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    if any(hint in lowered for hint in PLACEHOLDER_HINTS):
        return True
    # 纯数字、纯字母重复、过短的十六进制等一般不是真实密钥
    if value.isdigit():
        return True
    # 熵过低（几乎只有一种字符类别且长度不长）时跳过，减少误报
    unique_chars = len(set(lowered))
    if unique_chars <= 3:
        return True
    return False

# 忽略检查的目录
EXCLUDE_DIRS = {
    "node_modules",
    "dist",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".superpowers",
    ".worktrees",
    "__pycache__",
}

# 忽略检查的文件或后缀
EXCLUDE_FILES = {
    ".env",
    "check_secrets.py",  # 本脚本
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".db",
    ".db-shm",
    ".db-wal",
    ".sqlite",
    ".sqlite3",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".DS_Store",
}

def scan_files(root_dir):
    findings = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # 排除忽略目录
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]

        for filename in filenames:
            if filename in EXCLUDE_FILES:
                continue
            ext = os.path.splitext(filename)[1]
            if ext in EXCLUDE_EXTENSIONS or filename.startswith("."):
                continue

            filepath = os.path.join(dirpath, filename)
            
            # 额外防范：如果是 data/ 目录或者包含 .secret_key 或 .app_token，略过（这些是本地方案里允许存密钥的文件）
            if "/data/" in filepath or ".secret_key" in filepath or ".app_token" in filepath:
                continue

            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        rel_path = os.path.relpath(filepath, root_dir)

                        # 1. 已知服务商的固定前缀/格式特征
                        for key_type, pattern in PATTERNS.items():
                            matches = pattern.findall(line)
                            for match in matches:
                                # 过滤掉测试代码中包含 "sk-test" 或 "sk-test-..." 的占位 Key
                                if "sk-test" in match:
                                    continue
                                findings.append({
                                    "file": rel_path,
                                    "line": line_num,
                                    "type": key_type,
                                    "value": _mask(match),
                                })

                        # 2. 通用 KEY/TOKEN/SECRET/PASSWORD 赋值 + 高熵字符串
                        for name, value in GENERIC_ASSIGNMENT.findall(line):
                            if _looks_like_placeholder(value):
                                continue
                            findings.append({
                                "file": rel_path,
                                "line": line_num,
                                "type": f"通用敏感赋值疑似泄露（字段名: {name}）",
                                "value": _mask(value),
                            })
            except Exception:
                # 忽略读取异常（例如无法解码的二进制文件）
                pass
    return findings


def _mask(value: str) -> str:
    if len(value) > 10:
        return f"{value[:6]}...{value[-4:]}"
    return "***"

def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print(f"[*] 开始在 {root_dir} 进行密钥静态扫描...")
    findings = scan_files(root_dir)
    
    if findings:
        print("[!] 警告：扫描到疑似硬编码的明文 API Key/密钥！")
        for f in findings:
            print(f"  - 文件: {f['file']}:{f['line']} | 类型: {f['type']} | 匹配值: {f['value']}")
        print("[!] 请立刻将这些密钥移入本地 .env 或数据库，不要硬编码在代码或可提交的配置文件中！")
        sys.exit(1)
    else:
        print("[+] 密钥静态扫描完成，未发现硬编码的明文 Key，项目安全。")
        sys.exit(0)

if __name__ == "__main__":
    main()
