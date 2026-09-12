#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
commit.py — 一键提交脚本（Python 版，Windows 可直接运行）
用法：python commit.py "提交说明"（不写说明则默认"更新笔记"）
功能：检查改动 → git add -A → git commit → git push，无改动时自动跳过。
说明：与 commit.sh 行为一致；推送走 SSH（GitHub 443 端口已配置）。
"""
import os
import subprocess
import sys


def run_git(args):
    """执行 git 命令，失败即抛异常退出。"""
    subprocess.run(["git"] + args, check=True)


def main():
    # 切换到脚本所在目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    # 检查是否有未提交的改动
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if not result.stdout.strip():
        print("没有改动，无需提交。")
        return

    msg = sys.argv[1] if len(sys.argv) > 1 else "更新笔记"

    print("==> 暂存改动")
    run_git(["add", "-A"])

    print(f"==> 提交：{msg}")
    run_git(["commit", "-m", msg])

    print("==> 推送到 GitHub")
    run_git(["push"])

    print("完成，已同步到 GitHub。")


if __name__ == "__main__":
    main()
