#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_cwl.py — 从 structure.sty 自动提取数学符号，更新 TeXStudio 补全文件 custom.cwl

用法：
    python update_cwl.py [输出路径]

默认输出：C:\\Users\\Administrator\\AppData\\Roaming\\texstudio\\completion\\user\\custom.cwl
逻辑：
    1. 只解析 structure.sty 的 [模块 VI]（数学符号定义库）部分；
    2. 提取其中所有 \\newcommand / \\renewcommand 的命令名（及行尾注释）；
    3. 生成 `\\NAME#m` 形式的补全条目（#m 为 TeXStudio 的说明文本，附注释）；
    4. 替换 custom.cwl 中的自动生成段（从 `# Algebra symbols.` 或自动生成标记起），
       文件其余部分（#include、\\ref、定理环境等）原样保留。

改动 structure.sty 的符号后，运行本脚本即可同步；TeXStudio 重启后生效。
"""
import re
import sys
import pathlib

STRUCTURE = r"D:\Note\LaTeX模板\笔记写作\structure.sty"
DEFAULT_CWL = r"C:\Users\Administrator\AppData\Roaming\texstudio\completion\user\custom.cwl"

# 只匹配 \newcommand 与 \renewcommand，命令名由字母组成（含 @）
CMD_RE = re.compile(r"\\(?:re)?newcommand\{\\([A-Za-z@]+)\}")
# 行尾注释：% 后到行尾
COMMENT_RE = re.compile(r"%\s*(.+?)\s*$")

# 自动生成段的起止标记
AUTO_MARKER = "# ============ 自动生成段：structure.sty 数学符号 (update_cwl.py) ============"
OLD_MARKER = "# Algebra symbols."


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
    cwl_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CWL
    symbols = extract_symbols(STRUCTURE)
    section = build_section(symbols)

    cwl = pathlib.Path(cwl_path)
    content = cwl.read_text(encoding="utf-8") if cwl.exists() else ""

    # 截取自动生成段之前的头部（保留用户手动维护的内容）
    head = content
    for marker in (AUTO_MARKER, OLD_MARKER):
        if marker in content:
            head = content.split(marker)[0]
            break

    new_content = head.rstrip() + "\n\n" + section + "\n"
    cwl.write_text(new_content, encoding="utf-8")
    print(f"已更新 {cwl_path}")
    print(f"符号数量: {len(symbols)}")


if __name__ == "__main__":
    main()
