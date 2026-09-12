#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_symbols.py — 把各笔记 structure.sty 中新增的符号定义自动回填到模板

用法：
    python merge_symbols.py                    # 预览（默认不改动任何文件）
    python merge_symbols.py --write            # 实际回填（自动备份模板）
    python merge_symbols.py --write --update-cwl   # 回填后顺带更新 TeXStudio 补全

常用参数：
    --root DIR        笔记根目录（扫描其下所有含 structure.sty 的子目录）
    --template PATH   模板 structure.sty 的路径
    --notes NAME...   只扫描指定的笔记目录
    --write           真正写入模板（不加此参数只预览）
    --update-cwl      回填后调用同目录的 update_cwl.py 刷新补全

默认值推断：
    模板路径：脚本同目录的 .cwl_source（首行）> 脚本同目录的 structure.sty
    笔记根目录：脚本所在目录的父目录（当其下含 >=2 个带 structure.sty 的子目录时）
               > 脚本所在目录

行为约定（与模板既有的「（合并自 XXX）」风格保持一致）：
    1. 只比对符号库区段（[模块 VI] 到 [模块 VII] 之间）内的 \\newcommand / \\renewcommand；
    2. 模板中没有的命令，追加到符号库末尾，并在注释里标注来源笔记；
    3. 同名但定义不同的命令属于冲突，只报告、不写入，避免误覆盖模板定义；
    4. 写入前自动备份模板为 structure.sty.bak-<时间戳>。
"""
import argparse
import datetime
import re
import shutil
import subprocess
import sys
import pathlib

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

DEF_RE = re.compile(r"^[ \t]*\\(?:re)?newcommand\{\\([A-Za-z@]+)\}")
SEC_START = "[模块 VI]"
SEC_END = "[模块 VII]"


def read_text(path):
    """按原始换行符读取，不做 CRLF 转换。"""
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write_text(path, text):
    """按 text 内容原样写入，不做换行转换。"""
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def split_comment(line):
    """把一行拆成 (代码部分, 注释文本)；注释指第一个未被转义的 % 之后的内容。"""
    for i, ch in enumerate(line):
        if ch == "%" and (i == 0 or line[i - 1] != "\\"):
            return line[:i].rstrip(), line[i + 1:].strip()
    return line.rstrip(), ""


def parse_symbols(sty_path):
    """解析 structure.sty 符号库区段，返回 {命令名: (原行, 注释)}。"""
    text = read_text(sty_path)
    start = text.find(SEC_START)
    seg = text[start:] if start != -1 else text
    end = seg.find(SEC_END)
    if end != -1:
        seg = seg[:end]

    symbols = {}
    for line in seg.splitlines():
        m = DEF_RE.match(line)
        if not m:
            continue
        _, comment = split_comment(line)
        symbols[m.group(1)] = (line.rstrip(), comment)
    return symbols


def resolve_template(cli_path):
    if cli_path:
        return pathlib.Path(cli_path)
    src = SCRIPT_DIR / ".cwl_source"
    if src.is_file():
        for line in src.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return pathlib.Path(line)
    same_dir = SCRIPT_DIR / "structure.sty"
    if same_dir.is_file():
        return same_dir
    return None


def resolve_root(cli_path):
    if cli_path:
        return pathlib.Path(cli_path)
    parent = SCRIPT_DIR.parent
    try:
        subs = [d for d in parent.iterdir()
                if d.is_dir() and (d / "structure.sty").is_file()]
    except OSError:
        subs = []
    return parent if len(subs) >= 2 else SCRIPT_DIR


def find_notes(root, template, only=None, exclude=None):
    """收集 (笔记名, structure.sty 路径)，跳过模板自身。"""
    notes = []
    try:
        entries = sorted(root.iterdir())
    except OSError as exc:
        print(f"无法读取根目录 {root}：{exc}")
        return notes
    for d in entries:
        if not d.is_dir():
            continue
        sty = d / "structure.sty"
        if not sty.is_file():
            continue
        try:
            if sty.resolve() == template.resolve():
                continue
        except OSError:
            pass
        if only and d.name not in only:
            continue
        if exclude and d.name in exclude:
            continue
        notes.append((d.name, sty))
    return notes


def collect(template_symbols, notes):
    """返回 (待回填符号, 冲突列表)。"""
    additions = {}
    conflicts = []

    def norm(line):
        return " ".join(line.split())

    for note, sty in notes:
        try:
            symbols = parse_symbols(sty)
        except Exception as exc:
            print(f"跳过 {note}：解析失败（{exc}）")
            continue
        for name, (line, comment) in symbols.items():
            if name in template_symbols:
                tline = template_symbols[name][0]
                if norm(line) != norm(tline):
                    conflicts.append((name, note, line, tline))
                continue
            if name in additions:
                if norm(line) != norm(additions[name]["line"]):
                    conflicts.append((name, note, line, additions[name]["line"]))
                else:
                    additions[name]["sources"].append(note)
            else:
                additions[name] = {"line": line, "comment": comment, "sources": [note]}
    return additions, conflicts


def build_block(additions):
    """生成待插入的行（按命令名排序，注释中标注来源）。"""
    lines = []
    for name in sorted(additions):
        info = additions[name]
        sources = "、".join(info["sources"])
        code, comment = split_comment(info["line"])
        if comment:
            lines.append(f"{code}    % {comment}（合并自 {sources}）")
        else:
            lines.append(f"{code}    % （合并自 {sources}）")
    return lines


def write_template(template_path, block_lines):
    """把新符号行追加到符号库末尾，写入前备份。"""
    text = read_text(template_path)
    lines = text.splitlines()

    start = next((i for i, l in enumerate(lines) if SEC_START in l), None)
    end = next((i for i, l in enumerate(lines) if SEC_END in l), None)
    if start is None or end is None or end <= start:
        print("模板结构异常：找不到 [模块 VI] / [模块 VII] 标记，已中止。")
        return False

    defs = [i for i in range(start, end) if DEF_RE.match(lines[i])]
    if not defs:
        print("符号库区段内没有找到符号定义，已中止。")
        return False
    last_def = max(defs)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = template_path.with_name(template_path.name + f".bak-{stamp}")
    shutil.copy2(template_path, backup)

    eol = "\r\n" if "\r\n" in text else "\n"
    new_lines = lines[:last_def + 1] + block_lines + lines[last_def + 1:]
    new_text = eol.join(new_lines)
    if text.endswith(eol):
        new_text += eol
    write_text(template_path, new_text)
    print(f"已回填 {len(block_lines)} 个符号到 {template_path}")
    print(f"换行符：{'CRLF' if eol == chr(13) + chr(10) else 'LF'}")
    print(f"备份：{backup}")
    return True


def run_update_cwl():
    script = SCRIPT_DIR / "update_cwl.py"
    if not script.is_file():
        print("未找到 update_cwl.py，跳过补全刷新。")
        return
    print("==> 刷新 TeXStudio 补全")
    subprocess.run([sys.executable, str(script)], cwd=str(SCRIPT_DIR), check=False)


def main():
    parser = argparse.ArgumentParser(
        description="把各笔记 structure.sty 中新增的符号回填到模板")
    parser.add_argument("--root", default=None, help="笔记根目录")
    parser.add_argument("--template", default=None, help="模板 structure.sty 路径")
    parser.add_argument("--notes", nargs="*", default=None, help="只扫描指定的笔记目录")
    parser.add_argument("--exclude", nargs="*", default=None, help="排除指定目录（如习题集）")
    parser.add_argument("--write", action="store_true", help="真正写入模板（默认仅预览）")
    parser.add_argument("--update-cwl", action="store_true", help="回填后刷新 TeXStudio 补全")
    args = parser.parse_args()

    template = resolve_template(args.template)
    if template is None or not template.is_file():
        print("找不到模板 structure.sty。请用 --template 指定，")
        print("或在脚本同目录建 .cwl_source 文件写入其路径。")
        return 1

    root = resolve_root(args.root)
    notes = find_notes(root, template,
                       set(args.notes) if args.notes else None,
                       set(args.exclude) if args.exclude else None)

    print(f"模板：{template}")
    print(f"扫描根目录：{root}")
    print(f"待扫描笔记：{len(notes)} 个")
    if notes:
        print(f"  {'、'.join(name for name, _ in notes)}")
    if not notes:
        print("未发现其他笔记目录（可用 --root 指定根目录）。")
        return 0

    template_symbols = parse_symbols(template)
    additions, conflicts = collect(template_symbols, notes)

    print()
    print(f"模板现有符号：{len(template_symbols)} 个")

    if conflicts:
        print(f"\n存在 {len(conflicts)} 处冲突（同名但定义不同，已跳过，请手工确认）：")
        for name, note, line, other in conflicts:
            print(f"  \\{name}  [{note}]")
            print(f"      {line}")
            print(f"      另一处：{other}")

    if not additions:
        print("\n没有需要回填的新符号。")
        return 0

    print(f"\n发现 {len(additions)} 个新符号，来自：")
    by_source = {}
    for name, info in additions.items():
        by_source.setdefault("、".join(info["sources"]), []).append(name)
    for src, names in sorted(by_source.items()):
        print(f"  {src}：{'、'.join('\\' + n for n in sorted(names))}")

    block_lines = build_block(additions)
    print("\n将追加到符号库末尾的内容：")
    print("-" * 60)
    for line in block_lines:
        print(line)
    print("-" * 60)

    if not args.write:
        print("\n当前为预览模式，未改动任何文件。确认无误后加 --write 执行。")
        return 0

    if write_template(template, block_lines) and args.update_cwl:
        run_update_cwl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
