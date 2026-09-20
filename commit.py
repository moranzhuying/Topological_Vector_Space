#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
commit.py — 一键提交脚本（Python 版，Windows 可直接运行）

用法：
    python commit.py                     # 以默认说明「更新笔记」提交并推送
    python commit.py "说明"               # 以指定说明提交并推送
    python commit.py "说明" -y            # 跳过确认
    python commit.py "说明" --dry-run     # 只显示将要提交的内容，不实际执行
    python commit.py "说明;另一条" --log config    # 同时写入 CHANGELOG 的「tex 配置调整」
    python commit.py "说明;另一条" --log content   # 同时写入 CHANGELOG 的「正文内容调整」
    python commit.py "说明" --log auto            # 按关键词自动判断分类

说明：
    · 提交说明中用分号分隔的多个片段，写入 CHANGELOG 时会拆成多个列表项。
    · --log 会在提交前改写 CHANGELOG.md，将其与本次改动一并提交。
    · 推送走 SSH（GitHub 443 端口已配置）。
"""
import os
import re
import subprocess
import sys
import time
from datetime import datetime

DEFAULT_MSG = "更新笔记"

# 自动分类用的关键词（命中即归入「tex 配置调整」，否则归「正文内容调整」）
CONFIG_KEYS = ["符号", "symbols", "structure", "cwl", "补全", "编号", "目录",
               "README", "CHANGELOG", "脚本", "commit", "setup_mode", "脱敏",
               "忽略", "配置", "模板", "环境参数", "记号", "编译", "初始提交"]

USAGE = """用法：python commit.py [说明] [-y] [--dry-run] [--log config|content|auto]

  说明          提交说明，省略则用「更新笔记」
  -y            跳过提交前确认
  --dry-run     只显示将提交的文件与说明，不实际执行
  --log 分类    同时把说明写入 CHANGELOG.md，分类取 config / content / auto
"""


def git(args):
    """执行 git 命令，返回 (是否成功, 标准输出, 标准错误)。"""
    r = subprocess.run(["git"] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode == 0, r.stdout.strip(), r.stderr.strip()


def classify(msg):
    low = msg.lower()
    return "config" if any(k.lower() in low for k in CONFIG_KEYS) else "content"


def update_changelog(path, msg, mode):
    """把提交说明写入 CHANGELOG.md 对应日期下，返回 (是否写入, 说明)。"""
    if not os.path.isfile(path):
        return False, "未找到 CHANGELOG.md"

    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()

    section = {"config": "## tex 配置调整", "content": "## 正文内容调整"}[mode]
    if section not in text:
        return False, f"CHANGELOG.md 中未找到「{section}」节"

    now = datetime.now()
    year, month, day = f"{now.year} 年", f"{now.month} 月", now.strftime("%Y-%m-%d")
    items = [p.strip() for p in re.split(r"[;；]", msg) if p.strip()]

    head, _, tail = text.partition(section)

    # 该分类段的正文（到下一个 ## 为止）
    m = re.search(r"^(## .*)$", tail, re.M)
    body = tail[:m.start()] if m else tail
    rest = tail[m.start():] if m else ""

    # 定位/新建「日」小节，并计算当天已有的提交次数
    day_head = f"##### {day}"
    if day_head in body:
        # 统计该日已有的「第 N 次提交」数目
        seg_start = body.index(day_head)
        nxt = re.search(r"^##### ", body[seg_start + len(day_head):], re.M)
        seg_end = seg_start + len(day_head) + (nxt.start() if nxt else len(body) - seg_start - len(day_head))
        seg = body[seg_start:seg_end]
        count = len(re.findall(r"^\*\*第 \d+ 次提交\*\*", seg, re.M))
        new_block = f"**第 {count + 1} 次提交**\n\n" + "".join(f"- {i}\n" for i in items) + "\n"
        body = body[:seg_end].rstrip("\n") + "\n\n" + new_block + body[seg_end:].lstrip("\n")
    else:
        new_block = (f"{day_head}\n\n**第 1 次提交**\n\n"
                     + "".join(f"- {i}\n" for i in items) + "\n")
        # 依 年 → 月 → 日 的倒序定位插入点
        block = ""
        if f"### {year}" not in body:
            block = f"### {year}\n\n"
        if f"#### {month}" not in body:
            block += f"#### {month}\n\n"
        if f"### {year}" in body:
            yi = body.index(f"### {year}")
            if f"#### {month}" in body[yi:]:
                mi = yi + body[yi:].index(f"#### {month}")
                # 插到该月下最前（倒序）
                line_end = body.index("\n", mi) + 1
                body = body[:line_end] + "\n" + new_block + body[line_end:].lstrip("\n")
            else:
                # 该年存在但本月没有：插到该年标题行之后
                line_end = body.index("\n", yi) + 1
                body = body[:line_end] + "\n" + block + new_block + body[line_end:].lstrip("\n")
        else:
            # 该年不存在：插到本分类段最前
            body = block + new_block + "\n" + body.lstrip("\n")

    out = head + section + "\n\n" + body.strip("\n") + "\n" + ("\n" + rest.lstrip("\n") if rest else "")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    label = "tex 配置调整" if mode == "config" else "正文内容调整"
    return True, f"已写入 CHANGELOG.md 的「{label}」（{day}）"


def diagnose(err):
    """把 git 的报错归类成可读的提示。"""
    low = (err or "").lower()
    if "permission denied" in low or "publickey" in low:
        return "认证失败 —— SSH 密钥未被 GitHub 接受。请检查密钥与连通性。"
    if "could not resolve" in low or "name or service not known" in low:
        return "域名解析失败 —— 检查网络与 DNS 设置。"
    if "timed out" in low or "timeout" in low or "connection refused" in low:
        return "连接超时或被拒 —— 检查网络；若使用代理，请确认 git 的 http.proxy 设置。"
    if "no configured push destination" in low or "no remote" in low:
        return "未配置远程仓库 —— 请先执行 git remote add origin <仓库地址>。"
    if "repository not found" in low or "does not exist" in low:
        return "仓库不存在或无权限 —— 检查仓库名与账户，确认远程仓库已创建。"
    if "non-fast-forward" in low or "rejected" in low:
        return "远程有新提交，本地落后 —— 先执行 git pull --rebase 再推送。"
    return f"推送失败：{err.splitlines()[0][:120] if err else '未知原因'}"


def push_with_fallback():
    """推送，失败时自动重试并尝试备选通道。返回 (是否成功, 说明)。"""
    for i, delay in enumerate([0, 3, 6]):
        if delay:
            print(f"    …等待 {delay} 秒后重试（第 {i} 次）")
            time.sleep(delay)
        ok, _, err = git(["push"])
        if ok:
            return True, "已推送" if i == 0 else f"已推送（第 {i + 1} 次尝试成功）"
        last = err or "未知原因"

    # 备选通道：SSH 换端口（443 不通时试 22，反之亦然）
    url = git(["remote", "get-url", "origin"])[1] or ""
    if url.lower().startswith("git@"):
        print("    …尝试备选通道：改用 22 端口")
        env_old = os.environ.get("GIT_SSH_COMMAND")
        os.environ["GIT_SSH_COMMAND"] = "ssh -p 22 -o StrictHostKeyChecking=accept-new"
        try:
            ok, _, err = git(["push"])
        finally:
            if env_old is None:
                os.environ.pop("GIT_SSH_COMMAND", None)
            else:
                os.environ["GIT_SSH_COMMAND"] = env_old
        if ok:
            print("    ✓ 已通过 22 端口推送。若长期有效，可把 ~/.ssh/config 里的 Port 改为 22")
            return True, "已推送（22 端口）"
        last = err or last

    return False, diagnose(last)


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    argv = sys.argv[1:]
    if any(a in ("-h", "--help") for a in argv):
        print(USAGE)
        return 0

    dry = "--dry-run" in argv
    yes = "-y" in argv
    log_mode = None
    if "--log" in argv:
        i = argv.index("--log")
        log_mode = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("-") else "auto"
        del argv[i:i + 2]
    argv = [a for a in argv if not a.startswith("-")]
    msg = argv[0] if argv else DEFAULT_MSG

    # 1) 检查改动
    ok, status, err = git(["status", "--porcelain"])
    if not ok:
        print(f"[错误] 不是 git 仓库，或 git 不可用：\n  {err}")
        return 1
    if not status:
        print("没有改动，无需提交。")
        return 0

    files = status.splitlines()
    print(f"将要提交 {len(files)} 个文件的改动：")
    for line in files[:15]:
        print(f"  {line}")
    if len(files) > 15:
        print(f"  …（其余 {len(files) - 15} 个）")
    print(f"\n提交说明：{msg}")

    # 2) CHANGELOG 联动
    if log_mode:
        mode = classify(msg) if log_mode == "auto" else log_mode
        if mode not in ("config", "content"):
            print(f"[错误] --log 的分类应为 config / content / auto，收到「{log_mode}」")
            return 1
        if dry:
            print(f"[预览] 将写入 CHANGELOG.md（{mode}）")
        else:
            written, info = update_changelog(os.path.join(os.getcwd(), "CHANGELOG.md"), msg, mode)
            print(("[提示] " if not written else "[OK] ") + info)
            if not written and log_mode != "auto":
                return 1

    if dry:
        print("\n[预览] --dry-run：未执行任何 git 操作。")
        return 0

    # 3) 确认
    if not yes and sys.stdin.isatty():
        ans = input("\n确认提交并推送？[y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("已取消。")
            return 0

    # 4) 暂存与提交
    print("\n==> 暂存改动")
    ok, _, err = git(["add", "-A"])
    if not ok:
        print(f"[错误] 暂存失败：\n  {err}")
        return 1

    print(f"==> 提交：{msg}")
    ok, _, err = git(["commit", "-m", msg])
    if not ok:
        print(f"[错误] 提交失败：\n  {err}")
        return 1

    # 5) 推送（失败时重试、尝试备选通道，并明确告知本地已提交）
    print("==> 推送到 GitHub")
    ok, info = push_with_fallback()
    if not ok:
        print(f"[警告] {info}")
        print("\n本地提交已成功，仅未推送到远程。")
        print("网络恢复后单独运行下面这条命令即可：")
        print("  git push")
        return 1

    print(f"完成，{info}。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
