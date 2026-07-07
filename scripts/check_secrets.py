#!/usr/bin/env python3
import os
import re
import sys

# 正则表达式检测常见敏感 Key
PATTERNS = {
    "OpenAI/DeepSeek API Key": re.compile(r"\bsk-[a-zA-Z0-9]{32,}\b"),
    "Tavily API Key": re.compile(r"\btvly-[a-zA-Z0-9\-]{30,}\b"),
    "TwitterAPI.io API Key": re.compile(r"\bnew1_[a-zA-Z0-9]{32}\b"),
}

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
                        # 对每一行使用正则进行扫描
                        for key_type, pattern in PATTERNS.items():
                            matches = pattern.findall(line)
                            for match in matches:
                                # 过滤掉测试代码中包含 "sk-test" 或 "sk-test-..." 的占位 Key
                                if "sk-test" in match:
                                    continue
                                findings.append({
                                    "file": os.path.relpath(filepath, root_dir),
                                    "line": line_num,
                                    "type": key_type,
                                    "value": f"{match[:6]}...{match[-4:]}" if len(match) > 10 else "***"
                                })
            except Exception as e:
                # 忽略读取异常
                pass
    return findings

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
