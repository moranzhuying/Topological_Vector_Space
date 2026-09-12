#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_cwl.py — 从 structure.sty 自动提取数学符号，更新 TeXStudio 补全文件 custom.cwl

用法：
    python update_cwl.py [输出路径] [-s 符号来源]
    python update_cwl.py -s "D:\\路径\\structure.sty" "D:\\路径\\custom.cwl"

符号来源按以下顺序确定（前者优先）：
    1. 命令行 -s / --structure
    2. 环境变量 NOTE_STRUCTURE
    3. 脚本同目录的 .cwl_source 文件（首行写 structure.sty 的路径，可用 # 注释；
       该文件不入版本控制，供「多本笔记共用同一套模板符号库」的场景使用）
    4. 脚本同目录的 structure.sty（默认，自包含）

输出默认写入 %APPDATA%\\texstudio\\completion\\user\\custom.cwl；
取不到 APPDATA 时退回到脚本同目录下的 custom.cwl。

逻辑：
    1. 只解析 structure.sty 的 [模块 VI]（数学符号定义库）部分；
    2. 提取其中所有 \\newcommand / \\renewcommand 的命令名（及行尾注释）；
    3. 生成 `\\NAME#m` 形式的补全条目（#m 为 TeXStudio 的说明文本，附注释）；
    4. 替换 custom.cwl 中的自动生成段（从 `# Algebra symbols.` 或自动生成标记起），
       文件其余部分（#include、\\ref、定理环境等）原样保留。

改动 structure.sty 的符号后，运行本脚本即可同步；TeXStudio 重启后生效。
"""
import argparse
import os
import re
import sys
import pathlib

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

# 只匹配 \newcommand 与 \renewcommand，命令名由字母组成（含 @）
CMD_RE = re.compile(r"\\(?:re)?newcommand\{\\([A-Za-z@]+)\}")
# 行尾注释：% 后到行尾
COMMENT_RE = re.compile(r"%\s*(.+?)\s*$")

# 自动生成段的起止标记
AUTO_MARKER = "# ============ 自动生成段：structure.sty 数学符号 (update_cwl.py) ============"
OLD_MARKER = "# Algebra symbols."


def resolve_structure(cli_path=None):
    """按优先级确定符号来源：命令行 > 环境变量 > .cwl_source > 脚本同目录。"""
    if cli_path:
        return pathlib.Path(cli_path)

    env_path = os.environ.get("NOTE_STRUCTURE")
    if env_path:
        return pathlib.Path(env_path)

    src = SCRIPT_DIR / ".cwl_source"
    if src.is_file():
        for line in src.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return pathlib.Path(line)

    return SCRIPT_DIR / "structure.sty"


def default_cwl_path():
    """TeXStudio 补全文件默认位置：由 %APPDATA% 推导，不写死用户路径。"""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return str(pathlib.Path(appdata) / "texstudio" / "completion" / "user" / "custom.cwl")
    return str(SCRIPT_DIR / "custom.cwl")


def extract_symbols(structure_path):
    """从 structure.sty 的 [模块 VI] 提取 (命令名, 注释) 列表。"""
    text = pathlib.Path(structure_path).read_text(encoding="utf-8")
    idx = text.find("[模块 VI]")
    if idx != -1:
        text = text[idx:]
    symbols = []
    for line in text.splitlines():
        m = CMD_RE.match(line.strip())
        if not m:
            continue
        name = m.group(1)
        comment = ""
        cm = COMMENT_RE.search(line)
        if cm:
            comment = cm.group(1).strip()
        symbols.append((name, comment))
    return symbols


def build_section(symbols):
    """生成自动补全段文本。"""
    lines = [AUTO_MARKER]
    for name, comment in symbols:
        if comment:
            lines.append(r"\{}#m {}".format(name, comment))
        else:
            lines.append(r"\{}#m".format(name))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="从 structure.sty 提取数学符号，更新 TeXStudio 补全文件 custom.cwl")
    parser.add_argument(
        "output", nargs="?", default=None,
        help="输出 cwl 文件路径（默认为 TeXStudio 用户补全目录）")
    parser.add_argument(
        "-s", "--structure", default=None,
        help="符号来源 structure.sty 的路径")
    args = parser.parse_args()

    structure = resolve_structure(args.structure)
    if not structure.is_file():
        print(f"找不到 structure.sty：{structure}")
        print("可用 -s 指定路径，或设置环境变量 NOTE_STRUCTURE，")
        print("或在脚本同目录建 .cwl_source 文件写入路径。")
        return 1

    cwl_path = args.output or default_cwl_path()
    symbols = extract_symbols(structure)
    section = build_section(symbols)

    cwl = pathlib.Path(cwl_path)
    content = cwl.read_text(encoding="utf-8") if cwl.exists() else ""

    # 截取自动生成段之前的头部（保留用户手动维护的内容）
    head = content
    for marker in (AUTO_MARKER, OLD_MARKER):
        if marker in content:
            head = content.split(marker)[0]
            break

    cwl.parent.mkdir(parents=True, exist_ok=True)
    new_content = head.rstrip() + "\n\n" + section + "\n"
    cwl.write_text(new_content, encoding="utf-8")
    print(f"符号来源: {structure}")
    print(f"已更新 {cwl_path}")
    print(f"符号数量: {len(symbols)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
