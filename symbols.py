#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
symbols.py — 笔记符号库统一管理（刷新补全 / 回填模板 / 分发到各笔记）

一个脚本管理笔记根目录下所有笔记的 structure.sty 符号：

  1. 刷新补全  --cwl         从符号来源提取符号，更新 TeXStudio 的 custom.cwl
  2. 回填模板  --merge       把各笔记的新符号与新注释汇总进模板（各笔记 -> 模板）
  3. 分发同步  --distribute  把模板的 structure.sty 覆盖到各笔记（模板 -> 各笔记）
  4. 一键全套  --all         依次执行：回填 -> 刷新补全 -> 分发

默认不加动作参数时只做预览，不修改任何文件；所有写入操作都需显式加 --write。

用法：
    python symbols.py                          # 预览：配置、各笔记与模板的差异
    python symbols.py --cwl --write            # 刷新 TeXStudio 补全
    python symbols.py --merge --write          # 回填：各笔记 -> 模板
    python symbols.py --distribute --write     # 分发：模板 -> 各笔记
    python symbols.py --all --write            # 一键：回填 + 刷新补全 + 分发
    python symbols.py --drop orbit --distribute --cwl --write   # 弃用某符号并同步
    python symbols.py --root "D:\\电子笔记"      # 临时指定笔记根目录

配置（脚本同目录的 symbols.conf，格式 key = value，# 开头为注释）：
    root = D:\\电子笔记                                       # 笔记根目录
    template = D:\\Note\\LaTeX模板\\笔记写作\\structure.sty     # 符号来源
    cwl = %APPDATA%\\texstudio\\completion\\user\\custom.cwl   # 补全文件（可省略）

命令行参数优先于配置文件。根目录下每个含 structure.sty 的子目录视为一本笔记。

判定规则：
    新增符号   模板中没有              -> 回填时追加到符号库末尾（标注来源）
    注释更新   定义体相同、仅注释不同  -> 回填时以笔记的注释为准
    冲突       定义体不同              -> 只报告，绝不自动覆盖
    笔记缺失   模板有、某笔记没有      -> 只报告（可能该笔记已弃用该符号）
"""
import argparse
import datetime
import os
import re
import shutil
import sys
import pathlib

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
CONF_NAME = "symbols.conf"

DEF_RE = re.compile(r"^[ \t]*\\(?:re)?newcommand\{\\([A-Za-z@]+)\}")
SEC_START = "[模块 VI]"
SEC_END = "[模块 VII]"

# 自动生成段的标记：生成时用第一个；替换时任一命中即截断（兼容旧版 update_cwl.py）
AUTO_MARKERS = [
    "# ============ 自动生成段：structure.sty 数学符号 (symbols.py) ============",
    "# ============ 自动生成段：structure.sty 数学符号 (update_cwl.py) ============",
    "# Algebra symbols.",
]


# ---------------------------------------------------------------- 基础读写

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


def timestamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def norm(line):
    return " ".join(line.split())


# ---------------------------------------------------------------- 配置

def load_config():
    """读取脚本同目录的 symbols.conf，返回 (配置字典, 配置文件路径)。"""
    conf_path = SCRIPT_DIR / CONF_NAME
    cfg = {}
    if not conf_path.is_file():
        return cfg, conf_path
    for line in read_text(conf_path).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            cfg[key.strip().lower()] = os.path.expandvars(value)
    return cfg, conf_path


def resolve_root(cli_root, cfg):
    """笔记根目录：命令行 > 配置文件 > 脚本父目录（含多本笔记时）> 脚本目录。"""
    if cli_root:
        return pathlib.Path(cli_root)
    if cfg.get("root"):
        return pathlib.Path(cfg["root"])
    parent = SCRIPT_DIR.parent
    try:
        subs = [d for d in parent.iterdir()
                if d.is_dir() and (d / "structure.sty").is_file()]
    except OSError:
        subs = []
    return parent if len(subs) >= 2 else SCRIPT_DIR


def resolve_template(cli_template, cfg):
    """符号来源：命令行 > 配置文件 > 脚本同目录 .cwl_source > 脚本同目录 structure.sty。"""
    if cli_template:
        return pathlib.Path(cli_template)
    if cfg.get("template"):
        return pathlib.Path(cfg["template"])
    src = SCRIPT_DIR / ".cwl_source"
    if src.is_file():
        for line in read_text(src).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return pathlib.Path(os.path.expandvars(line))
    same_dir = SCRIPT_DIR / "structure.sty"
    if same_dir.is_file():
        return same_dir
    return None


def resolve_cwl(cli_cwl, cfg):
    """补全文件：命令行 > 配置文件 > %APPDATA% 默认位置 > 脚本同目录。"""
    if cli_cwl:
        return pathlib.Path(cli_cwl)
    if cfg.get("cwl"):
        return pathlib.Path(cfg["cwl"])
    appdata = os.environ.get("APPDATA")
    if appdata:
        return pathlib.Path(appdata) / "texstudio" / "completion" / "user" / "custom.cwl"
    return SCRIPT_DIR / "custom.cwl"


# ---------------------------------------------------------------- 符号解析

def parse_symbols(sty_path):
    """解析 structure.sty 的符号库区段（[模块 VI] 到 [模块 VII]），
    返回 {命令名: (原行, 代码部分, 注释)}。"""
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
        code, comment = split_comment(line)
        symbols[m.group(1)] = (line.rstrip(), code, comment)
    return symbols


def find_notes(root, template, only=None, exclude=None):
    """收集根目录下 (笔记名, structure.sty 路径)，跳过符号来源自身。"""
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
            if template is not None and sty.resolve() == template.resolve():
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
    """比对各笔记与模板。

    返回 dict：
        additions  新符号     name -> {"line", "sources"}
        comments   注释更新   name -> {"line", "sources"}
        conflicts  真冲突     [(name, note, line, 模板行)]
        missing    笔记缺失   name -> [note, ...]
    """
    additions, comments = {}, {}
    conflicts = []
    missing = {}

    for note, sty in notes:
        try:
            symbols = parse_symbols(sty)
        except Exception as exc:
            print(f"  跳过 {note}：解析失败（{exc}）")
            continue

        for name, (line, code, _) in symbols.items():
            if name in template_symbols:
                tline, tcode, _ = template_symbols[name]
                if norm(code) != norm(tcode):
                    conflicts.append((name, note, line, tline))
                elif norm(line) != norm(tline):
                    if name in comments and norm(comments[name]["line"]) != norm(line):
                        conflicts.append((name, note, line, comments[name]["line"]))
                        continue
                    item = comments.setdefault(name, {"line": line, "sources": []})
                    if note not in item["sources"]:
                        item["sources"].append(note)
                continue

            if name in additions:
                if norm(line) != norm(additions[name]["line"]):
                    conflicts.append((name, note, line, additions[name]["line"]))
                else:
                    additions[name]["sources"].append(note)
            else:
                additions[name] = {"line": line, "sources": [note]}

        for name in template_symbols:
            if name not in symbols:
                missing.setdefault(name, []).append(note)

    return {"additions": additions, "comments": comments,
            "conflicts": conflicts, "missing": missing}


def build_block(additions):
    """生成待追加的符号行（按名字排序，注释标注来源）。"""
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


# ---------------------------------------------------------------- 报告

def report(template_symbols, diff):
    additions, comments = diff["additions"], diff["comments"]
    conflicts, missing = diff["conflicts"], diff["missing"]

    print(f"\n模板现有符号：{len(template_symbols)} 个")

    if additions:
        print(f"\n[新增] {len(additions)} 个符号待回填，来自：")
        by_source = {}
        for name, info in additions.items():
            by_source.setdefault("、".join(info["sources"]), []).append(name)
        for src, names in sorted(by_source.items()):
            print(f"  {src}：{'、'.join('\\' + n for n in sorted(names))}")
        print("  将追加到符号库末尾：")
        for line in build_block(additions):
            print(f"    {line}")
    else:
        print("\n[新增] 无")

    if comments:
        print(f"\n[注释] {len(comments)} 个符号的定义体相同、注释不同（回填时以笔记的注释为准）：")
        for name in sorted(comments)[:5]:
            print(f"    \\{name}  ->  {split_comment(comments[name]['line'])[1]}")
        if len(comments) > 5:
            print(f"    ... 其余 {len(comments) - 5} 个")
    else:
        print("[注释] 无差异")

    if conflicts:
        print(f"\n[冲突] {len(conflicts)} 处定义体不同，已跳过、绝不自动覆盖：")
        for name, note, line, other in conflicts:
            print(f"    \\{name}  [{note}]")
            print(f"        笔记：{line}")
            print(f"        另一处：{other}")
    else:
        print("[冲突] 无")

    if missing:
        print(f"\n[缺失] {len(missing)} 个模板符号在某些笔记中不存在（可能已弃用，仅提示）：")
        for name, notes in sorted(missing.items()):
            print(f"    \\{name}  缺失于：{'、'.join(notes)}")


# ---------------------------------------------------------------- 动作

def do_merge(template_path, block_lines, comment_updates):
    """把注释更新与新增符号写入模板（写入前备份）。"""
    text = read_text(template_path)
    lines = text.splitlines()

    start = next((i for i, l in enumerate(lines) if SEC_START in l), None)
    end = next((i for i, l in enumerate(lines) if SEC_END in l), None)
    if start is None or end is None or end <= start:
        print("模板结构异常：找不到 [模块 VI] / [模块 VII] 标记，已中止。")
        return False

    # 1) 注释更新：替换模板中同名符号行（定义体相同才允许，调用方已保证）
    replaced = 0
    for name, info in comment_updates.items():
        for i in range(start, end):
            m = DEF_RE.match(lines[i])
            if m and m.group(1) == name:
                lines[i] = info["line"]
                replaced += 1
                break

    # 2) 新增符号：追加到符号库末尾
    defs = [i for i in range(start, end) if DEF_RE.match(lines[i])]
    if not defs and not block_lines:
        print("符号库区段内没有符号定义，已中止。")
        return False
    last_def = max(defs) if defs else end - 1
    lines = lines[:last_def + 1] + block_lines + lines[last_def + 1:]

    stamp = timestamp()
    backup = template_path.with_name(template_path.name + f".bak-{stamp}")
    shutil.copy2(template_path, backup)

    eol = "\r\n" if "\r\n" in text else "\n"
    new_text = eol.join(lines)
    if text.endswith(eol):
        new_text += eol
    write_text(template_path, new_text)
    print(f"\n已回填到 {template_path}")
    print(f"  注释更新 {replaced} 处，新增符号 {len(block_lines)} 个")
    print(f"  备份：{backup.name}")
    return True


def do_drop(template_path, names):
    """从模板删除指定符号（用于弃用旧记号），通常与 --distribute 连用。"""
    wanted = {n.lstrip("\\") for n in names}
    text = read_text(template_path)
    lines = text.splitlines(keepends=True)
    kept, removed = [], []
    for ln in lines:
        m = DEF_RE.match(ln)
        if m and m.group(1) in wanted:
            removed.append(m.group(1))
            continue
        kept.append(ln)
    if not removed:
        print(f"\n模板中未找到指定符号：{'、'.join(sorted(wanted))}")
        return False

    stamp = timestamp()
    backup = template_path.with_name(template_path.name + f".bak-{stamp}")
    shutil.copy2(template_path, backup)
    write_text(template_path, "".join(kept))
    print(f"\n已从模板删除 {len(removed)} 个符号：{'、'.join('\\' + n for n in sorted(removed))}")
    print(f"  备份：{backup.name}")
    if wanted - set(removed):
        print(f"  未找到：{'、'.join(sorted(wanted - set(removed)))}")
    return True


def do_distribute(template_path, notes, write=True):
    """把模板的 structure.sty 覆盖到各笔记（逐个备份）。"""
    template_text = read_text(template_path)
    same, changed = [], []
    for note, sty in notes:
        try:
            current = read_text(sty)
        except Exception as exc:
            print(f"  跳过 {note}：读取失败（{exc}）")
            continue
        (same if current == template_text else changed).append((note, sty))

    print(f"\n分发模板到各笔记：已一致 {len(same)} 个，待同步 {len(changed)} 个")
    if not changed:
        return
    if not write:
        for note, _ in changed:
            print(f"  [待同步] {note}")
        return
    stamp = timestamp()
    for note, sty in changed:
        backup = sty.with_name(sty.name + f".bak-{stamp}")
        shutil.copy2(sty, backup)
        write_text(sty, template_text)
        print(f"  [已同步] {note}  （备份 {backup.name}）")


def do_cwl(template_path, cwl_path, write=False):
    """从符号来源提取符号，刷新 TeXStudio 补全文件。"""
    symbols = parse_symbols(template_path)
    entries = []
    for name in sorted(symbols):
        _, _, comment = symbols[name]
        entries.append(r"\{}#m {}".format(name, comment) if comment else r"\{}#m".format(name))
    section = "\n".join([AUTO_MARKERS[0]] + entries)

    cwl = pathlib.Path(cwl_path)
    content = read_text(cwl) if cwl.is_file() else ""

    head = content
    for marker in AUTO_MARKERS:
        if marker in content:
            head = content.split(marker)[0]
            break

    eol = "\r\n" if "\r\n" in content else ("\n" if content else os.linesep)
    new_content = head.rstrip() + eol + eol + section + eol

    print(f"\n补全来源：{template_path}")
    print(f"补全文件：{cwl_path}")
    print(f"符号数量：{len(symbols)}")
    if not write:
        print("  （预览，未写入）")
        return
    cwl.parent.mkdir(parents=True, exist_ok=True)
    write_text(cwl, new_content)
    print("  已刷新 TeXStudio 补全。")


# ---------------------------------------------------------------- 主流程

def main():
    parser = argparse.ArgumentParser(
        description="笔记符号库统一管理：刷新补全 / 回填模板 / 分发到各笔记")
    parser.add_argument("--cwl", action="store_true", help="刷新 TeXStudio 补全")
    parser.add_argument("--merge", action="store_true", help="回填：各笔记 -> 模板")
    parser.add_argument("--distribute", action="store_true", help="分发：模板 -> 各笔记")
    parser.add_argument("--drop", nargs="*", default=None,
                        help="从模板删除指定符号（弃用旧记号时用），建议与 --distribute 连用")
    parser.add_argument("--all", action="store_true", help="一键执行：回填 + 刷新补全 + 分发")
    parser.add_argument("--write", action="store_true", help="真正写入（默认仅预览）")
    parser.add_argument("--root", default=None, help="笔记根目录（其下每本笔记一个子目录）")
    parser.add_argument("--template", default=None, help="符号来源 structure.sty 路径")
    parser.add_argument("--cwl-path", default=None, help="TeXStudio 补全文件路径")
    parser.add_argument("--notes", nargs="*", default=None, help="只处理指定的笔记目录")
    parser.add_argument("--exclude", nargs="*", default=None, help="排除指定目录（如习题集）")
    args = parser.parse_args()

    cfg, conf_path = load_config()
    root = resolve_root(args.root, cfg)
    template = resolve_template(args.template, cfg)
    cwl_path = resolve_cwl(args.cwl_path, cfg)

    print(f"配置文件：{conf_path if conf_path.is_file() else '(未创建，使用默认值)'}")
    print(f"笔记根目录：{root}")
    if template is None or not template.is_file():
        print("符号来源：找不到 structure.sty")
        print("\n请用 --template 指定，或在 symbols.conf 里设置 template，")
        print("或在脚本同目录建 .cwl_source 文件写入其路径。")
        return 1
    print(f"符号来源：{template}")
    print(f"补全文件：{cwl_path}")

    notes = find_notes(root, template,
                       set(args.notes) if args.notes else None,
                       set(args.exclude) if args.exclude else None)
    print(f"扫描到笔记：{len(notes)} 个")
    if notes:
        print(f"  {'、'.join(name for name, _ in notes)}")
    if not notes:
        print("未发现笔记目录（检查 --root 或 symbols.conf 中的 root）。")
        return 0

    template_symbols = parse_symbols(template)
    diff = collect(template_symbols, notes)
    report(template_symbols, diff)

    do_m = args.merge or args.all
    do_d = args.distribute or args.all
    do_c = args.cwl or args.all
    do_x = bool(args.drop)

    if not (do_m or do_d or do_c or do_x):
        print("\n当前只做预览。可选动作（均需再加 --write 才会写入）：")
        print("  --cwl               刷新 TeXStudio 补全")
        print("  --merge             把新符号与新注释回填进模板")
        print("  --distribute        把模板分发到各笔记")
        print("  --drop NAME...      从模板删除指定符号（弃用旧记号）")
        print("  --all               一键执行：回填 + 刷新补全 + 分发")
        return 0

    if not args.write:
        print("\n【预览】将要执行的动作：")
        if do_m:
            print(f"  回填模板：新增 {len(diff['additions'])} 个符号，"
                  f"更新 {len(diff['comments'])} 处注释")
        if do_x:
            print(f"  删除符号：{'、'.join(args.drop)}")
        if do_c:
            print(f"  刷新补全：{len(template_symbols)} 个符号 -> {cwl_path}")
        if do_d:
            do_distribute(template, notes, write=False)
        if do_m and diff["comments"]:
            print("  注意：回填会以笔记的注释覆盖模板，随后分发会统一到所有笔记")
        print("\n当前为预览模式，未改动任何文件。确认无误后加 --write 执行。")
        return 0

    # 执行顺序固定为：回填 -> 删除 -> 刷新补全 -> 分发
    # （先回填再删除，避免回填把待删符号又加回来）
    if do_m and (diff["additions"] or diff["comments"]):
        do_merge(template, build_block(diff["additions"]), diff["comments"])
    if do_x:
        do_drop(template, args.drop)
    if do_c:
        do_cwl(template, cwl_path, write=True)
    if do_d:
        do_distribute(template, notes, write=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
