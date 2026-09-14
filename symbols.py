#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
symbols.py — 笔记符号管理面板（交互式）

直接运行本脚本即进入数字面板，可多选（英文逗号分隔，如 1,3,5）：

    1. 设置笔记文件夹并扫描差异   设置根目录；扫描各子文件夹与模板的差异，
                                  只更新有差异的部分，无差异则跳过
    2. 提取各子文件夹的符号       收集子文件夹中模板没有的新符号，记入提取档案
    3. 回填提取的符号             先写入 structure.sty，再刷新 custom.cwl
    4. 检验并删除未使用的符号     检验各子文件夹正文未引用的符号，确认后删除
    5. 引入新的记号               向各子文件夹 structure.sty 的 [模块 VI] 插入定义
    6. 退出

配置文件：脚本同目录 symbols.conf（root / template / cwl），命令行参数优先。
提取档案：脚本同目录 symbols_extract.json（本机使用，不入版本控制）
          结构：{ "子文件夹": { "年-月-日": { "命令名": "定义行" } } }

命令行模式（不进面板，便于批处理）：
    python symbols.py --all --write        回填 + 刷新补全 + 分发
    python symbols.py --cwl --write        只刷新 TeXStudio 补全
    python symbols.py --distribute --write 只分发
    python symbols.py --drop NAME --write  删除指定符号
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys
import pathlib

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
CONF_NAME = "symbols.conf"
EXTRACT_NAME = "symbols_extract.json"

DEF_RE = re.compile(r"^[ \t]*\\(?:re)?newcommand\{\\([A-Za-z@]+)\}")
SEC_START = "[模块 VI]"
SEC_END = "[模块 VII]"
CMD_NAME_RE = re.compile(r"^[A-Za-z]+$")

AUTO_MARKERS = [
    "# ============ 自动生成段：structure.sty 数学符号 (symbols.py) ============",
    "# ============ 自动生成段：structure.sty 数学符号 (update_cwl.py) ============",
    "# Algebra symbols.",
]


# ================================================================ 基础 IO

def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return fh.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def split_comment(line):
    """拆成 (代码, 注释)，注释指第一个未被转义的 % 之后的内容。"""
    for i, ch in enumerate(line):
        if ch == "%" and (i == 0 or line[i - 1] != "\\"):
            return line[:i].rstrip(), line[i + 1:].strip()
    return line.rstrip(), ""


def stamp():
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def today():
    return datetime.date.today().strftime("%Y-%m-%d")


def norm(line):
    return " ".join(line.split())


def backup(path, tag=None):
    name = f"{path.name}.bak-{tag or stamp()}"
    target = path.with_name(name)
    shutil.copy2(path, target)
    return target


# ================================================================ 配置

def load_config():
    conf = SCRIPT_DIR / CONF_NAME
    cfg = {}
    if conf.is_file():
        for line in read_text(conf).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith(";"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if value:
                cfg[key.strip().lower()] = os.path.expandvars(value)
    return cfg, conf


def save_config(cfg, conf_path):
    lines = [
        "# symbols.py 配置",
        "# 每行格式：键 = 值  以 # 或 ; 开头的行是注释",
        "# 本文件含本机路径，已加入 .gitignore，不上传",
        "",
        "# 笔记根目录：其下每个含 structure.sty 的子目录都被视为一本笔记",
        f"root = {cfg.get('root', '')}",
        "",
        "# 符号来源（模板的 structure.sty）",
        f"template = {cfg.get('template', '')}",
        "",
        "# TeXStudio 补全文件（支持 %APPDATA% 等环境变量）",
        f"cwl = {cfg.get('cwl', '')}",
        "",
    ]
    write_text(conf_path, "\n".join(lines))


def default_cwl():
    appdata = os.environ.get("APPDATA")
    if appdata:
        return str(pathlib.Path(appdata) / "texstudio" / "completion" / "user" / "custom.cwl")
    return str(SCRIPT_DIR / "custom.cwl")


def resolve_root(cli_root, cfg):
    if cli_root:
        return pathlib.Path(cli_root)
    if cfg.get("root"):
        return pathlib.Path(cfg["root"])
    parent = SCRIPT_DIR.parent
    try:
        subs = [d for d in parent.iterdir() if d.is_dir() and (d / "structure.sty").is_file()]
    except OSError:
        subs = []
    return parent if len(subs) >= 2 else SCRIPT_DIR


def resolve_template(cli_template, cfg):
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
    same = SCRIPT_DIR / "structure.sty"
    return same if same.is_file() else None


def resolve_cwl(cli_cwl, cfg):
    if cli_cwl:
        return pathlib.Path(cli_cwl)
    if cfg.get("cwl"):
        return pathlib.Path(cfg["cwl"])
    return pathlib.Path(default_cwl())


# ================================================================ 提取档案

def load_extract():
    path = SCRIPT_DIR / EXTRACT_NAME
    if not path.is_file():
        return {}, path
    try:
        return json.loads(read_text(path)), path
    except Exception:
        print("  ! 提取档案损坏，按空处理")
        return {}, path


def save_extract(data, path):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


# ================================================================ 符号解析

def parse_symbols(sty_path):
    """返回 {命令名: (原行, 代码, 注释)}，范围 [模块 VI] 到 [模块 VII]。"""
    text = read_text(sty_path)
    start = text.find(SEC_START)
    seg = text[start:] if start != -1 else text
    end = seg.find(SEC_END)
    if end != -1:
        seg = seg[:end]
    out = {}
    for line in seg.splitlines():
        m = DEF_RE.match(line)
        if not m:
            continue
        code, comment = split_comment(line)
        out[m.group(1)] = (line.rstrip(), code, comment)
    return out


def find_notes(root, template, only=None, exclude=None):
    notes = []
    try:
        entries = sorted(root.iterdir())
    except OSError as exc:
        print(f"  无法读取目录 {root}：{exc}")
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


def diff_notes(template_symbols, notes):
    """比对各笔记与模板，返回 additions / comments / conflicts / missing。"""
    additions, comments, conflicts, missing = {}, {}, [], {}
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
                    comments.setdefault(name, {"line": line, "sources": []})["sources"].append(note)
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


def rewrite_comment(line, marker):
    """把一行重新拼上注释标记，返回新行。"""
    code, comment = split_comment(line)
    if comment:
        return f"{code}    % {comment} {marker}"
    return f"{code}    % {marker}"


def insert_into_symbol_lib(sty_path, new_lines, replace_map=None):
    """向 [模块 VI] 末尾追加 new_lines；replace_map 为 {命令名: 新行}。"""
    text = read_text(sty_path)
    lines = text.splitlines(keepends=True)
    start = next((i for i, l in enumerate(lines) if SEC_START in l), None)
    end = next((i for i, l in enumerate(lines) if SEC_END in l), None)
    if start is None or end is None or end <= start:
        return False
    if replace_map:
        for i in range(start, end):
            m = DEF_RE.match(lines[i])
            if m and m.group(1) in replace_map:
                keep = "\r\n" if lines[i].endswith("\r\n") else "\n"
                lines[i] = replace_map[m.group(1)] + keep
    defs = [i for i in range(start, end) if DEF_RE.match(lines[i])]
    last = max(defs) if defs else end - 1
    eol = "\r\n" if "\r\n" in text else "\n"
    payload = [(l.rstrip("\r\n") + eol) for l in new_lines]
    lines = lines[:last + 1] + payload + lines[last + 1:]
    write_text(sty_path, "".join(lines))
    return True


def distribute(template_path, notes, quiet=False):
    """模板 -> 各笔记（逐个备份）。返回同步数量。"""
    template_text = read_text(template_path)
    changed = []
    for note, sty in notes:
        try:
            if read_text(sty) != template_text:
                changed.append((note, sty))
        except Exception:
            continue
    if not changed:
        if not quiet:
            print(f"  已一致，无需同步（共 {len(notes)} 个）。")
        return 0
    tag = stamp()
    for note, sty in changed:
        backup(sty, tag)
        write_text(sty, template_text)
        if not quiet:
            print(f"  [已同步] {note}")
    return len(changed)


def refresh_cwl(template_path, cwl_path):
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
    cwl.parent.mkdir(parents=True, exist_ok=True)
    backup(cwl) if cwl.is_file() else None
    write_text(cwl, head.rstrip() + eol + eol + section + eol)
    print(f"  已刷新补全：{len(symbols)} 个符号 -> {cwl}")
    return len(symbols)


# ================================================================ 输入辅助

def ask(prompt, default=None, required=True):
    while True:
        tip = prompt
        if default:
            tip += f"（回车保持 {default}）"
        elif not required:
            tip += "（可选，回车跳过）"
        try:
            value = input(f"  {tip}：").strip()
        except EOFError:
            print()
            return default or ""
        if value:
            return value
        if default:
            return default
        if not required:
            return ""
        print("  ! 该项为必填，请重新输入。")


def ask_yes_no(prompt):
    while True:
        try:
            value = input(f"  {prompt} (Y/N)：").strip().upper()
        except EOFError:
            print()
            return False
        if value in ("Y", "YES", "是"):
            return True
        if value in ("N", "NO", "否"):
            return False
        print("  ! 请输入 Y 或 N。")


def parse_choices(text, max_n):
    parts = [p for p in re.split(r"[,，、\s]+", text.strip()) if p]
    if not parts:
        return None, "没有识别到任何选项"
    out = []
    for p in parts:
        if not p.isdigit():
            return None, f"无法识别：{p}"
        n = int(p)
        if not 1 <= n <= max_n:
            return None, f"选项超出范围：{n}"
        if n not in out:
            out.append(n)
    return out, None


# ================================================================ 各选项动作

def action_setup(ctx):
    """1. 设置笔记文件夹并扫描差异（只更新有差异的部分）。"""
    print("\n[1] 设置笔记文件夹并扫描差异")
    current = str(ctx["root"])
    path = ask("请输入笔记文件夹路径", default=current)
    target = pathlib.Path(path.strip('"').strip("'"))
    if not target.is_dir():
        print(f"  ! 目录不存在：{target}")
        return
    ctx["root"] = target
    if str(target) != current:
        ctx["cfg"]["root"] = str(target)
        save_config(ctx["cfg"], ctx["conf"])
        print(f"  已保存笔记根目录：{target}")
    else:
        print(f"  笔记根目录保持：{target}")

    notes = find_notes(target, ctx["template"])
    print(f"  扫描到 {len(notes)} 个子文件夹：{'、'.join(n for n, _ in notes)}")
    if not notes:
        return
    template_symbols = parse_symbols(ctx["template"])
    diff = diff_notes(template_symbols, notes)

    stale = []
    tpl_text = read_text(ctx["template"])
    for note, sty in notes:
        try:
            if read_text(sty) != tpl_text:
                stale.append(note)
        except Exception:
            continue
    if not stale:
        print("  各子文件夹与模板一致，无需更新。")
    else:
        print(f"  发现 {len(stale)} 个子文件夹存在差异：{'、'.join(stale)}")
        print("  正在只更新有差异的部分……")
        n = distribute(ctx["template"], notes, quiet=True)
        print(f"  已更新 {n} 个子文件夹。")

    if diff["additions"]:
        print(f"  另发现 {len(diff['additions'])} 个待提取的新符号"
              f"（{'、'.join('\\' + k for k in sorted(diff['additions']))}）")
    if diff["conflicts"]:
        print(f"  ! {len(diff['conflicts'])} 处定义冲突未自动处理：")
        for name, note, line, other in diff["conflicts"][:5]:
            print(f"      \\{name} [{note}]")
            print(f"        笔记：{line}")
            print(f"        另一处：{other}")


def action_extract(ctx):
    """2. 提取各子文件夹的符号，记入提取档案。"""
    print("\n[2] 提取各子文件夹的符号")
    notes = find_notes(ctx["root"], ctx["template"])
    if not notes:
        print("  ! 未扫描到子文件夹。")
        return {}
    template_symbols = parse_symbols(ctx["template"])
    diff = diff_notes(template_symbols, notes)
    additions = diff["additions"]
    if not additions:
        print("  没有可提取的新符号（各子文件夹与模板一致）。")
        return {}

    data, path = load_extract()
    day = today()
    total = 0
    for note in sorted({s for info in additions.values() for s in info["sources"]}):
        bucket = data.setdefault(note, {}).setdefault(day, {})
        for name in sorted(additions):
            if note not in additions[name]["sources"]:
                continue
            bucket[name] = additions[name]["line"]
            total += 1
        print(f"  [{note}] {day} 提取 {len(bucket)} 个符号")
    save_extract(data, path)
    print(f"  已写入提取档案：{path.name}（本次合计 {total} 条）")
    return additions


def action_backfill(ctx):
    """3. 回填提取的符号：先 structure.sty，再 custom.cwl。"""
    print("\n[3] 回填提取的符号")
    data, path = load_extract()
    pending = {note: days for note, days in data.items() if any(days.values())}
    if not pending:
        print("  ! 尚无提取记录。")
        if ask_yes_no("是否现在提取各子文件夹的符号？"):
            action_extract(ctx)
            data, path = load_extract()
            pending = {note: days for note, days in data.items() if any(days.values())}
        if not pending:
            print("  已跳过回填。")
            return

    template_symbols = parse_symbols(ctx["template"])
    new_lines, replace_map, skipped = [], {}, []
    for note in sorted(pending):
        for day in sorted(pending[note]):
            marker = f"提取自 {note}-{day}"
            for name in pending[note][day]:
                line = pending[note][day][name]
                if name in template_symbols:
                    tline = template_symbols[name][0]
                    if marker not in tline:
                        replace_map[name] = rewrite_comment(line, marker)
                    else:
                        skipped.append(name)
                    continue
                new_lines.append(rewrite_comment(line, marker))

    if not new_lines and not replace_map:
        print("  提取档案中的符号均已在模板中，无需回填。")
    else:
        backup(ctx["template"])
        ok = insert_into_symbol_lib(ctx["template"], new_lines, replace_map)
        if not ok:
            print("  ! 模板结构异常，已中止。")
            return
        print(f"  已写入模板 structure.sty：新增 {len(new_lines)} 个，"
              f"补注来源 {len(replace_map)} 个")
        notes = find_notes(ctx["root"], ctx["template"])
        n = distribute(ctx["template"], notes, quiet=False)
        if n == 0:
            print("  各子文件夹均已包含这些符号。")
    if skipped:
        print(f"  （{len(skipped)} 个符号已标注过来源，未重复处理）")

    refresh_cwl(ctx["template"], ctx["cwl"])


def action_unused(ctx):
    """4. 检验并删除未使用的符号。"""
    print("\n[4] 检验并删除未使用的符号")
    notes = find_notes(ctx["root"], ctx["template"])
    if not notes:
        print("  ! 未扫描到子文件夹。")
        return

    per_note = {}
    for note, sty in notes:
        try:
            symbols = parse_symbols(sty)
        except Exception:
            continue
        chunks = []
        main = sty.parent / "main.tex"
        if main.is_file():
            chunks.append(read_text(main))
        content = sty.parent / "Content"
        if content.is_dir():
            for tex in sorted(content.rglob("*.tex")):
                try:
                    chunks.append(read_text(tex))
                except Exception:
                    pass
        blob = "\n".join(chunks)
        unused = []
        for name in symbols:
            if not re.search(r"\\" + re.escape(name) + r"(?![A-Za-z])", blob):
                unused.append(name)
        per_note[note] = unused

    print("  各子文件夹正文未引用的符号：")
    for note in sorted(per_note):
        names = sorted(per_note[note])
        if names:
            print(f"    [{note}] {len(names)} 个：{'、'.join('\\' + n for n in names)}")
        else:
            print(f"    [{note}] 无")

    common = None
    for names in per_note.values():
        s = set(names)
        common = s if common is None else (common & s)
    common = sorted(common or [])
    if not common:
        print("\n  没有「所有子文件夹都未使用」的符号，无需删除。")
        return
    print(f"\n  所有子文件夹都未使用的符号（可安全删除）：{len(common)} 个")
    for name in common:
        print(f"    \\{name}")
    if not ask_yes_no("\n  是否从符号库删除这些符号？"):
        print("  已取消，未删除任何符号。")
        return

    template_symbols = parse_symbols(ctx["template"])
    keep_lines = []
    text = read_text(ctx["template"])
    lines = text.splitlines(keepends=True)
    removed = []
    for line in lines:
        m = DEF_RE.match(line)
        if m and m.group(1) in common:
            removed.append(m.group(1))
            continue
        keep_lines.append(line)
    if not removed:
        print("  模板中未找到这些符号。")
        return
    backup(ctx["template"])
    write_text(ctx["template"], "".join(keep_lines))
    print(f"  已从模板删除 {len(removed)} 个符号：{'、'.join('\\' + n for n in removed)}")
    distribute(ctx["template"], notes, quiet=False)
    refresh_cwl(ctx["template"], ctx["cwl"])


def action_add(ctx):
    """5. 引入新的记号（交互录入，规则同 LaTeX 的 \\newcommand）。"""
    print("\n[5] 引入新的记号")
    print("  说明：命令名只允许字母；定义不能为空；注释可选。")

    name = ""
    while not name:
        raw = ask("命令名（不含反斜杠，必填）")
        if not raw:
            continue
        candidate = raw.lstrip("\\")
        if not CMD_NAME_RE.match(candidate):
            print("  ! 命令名只允许英文字母（与 LaTeX 规则一致），请重新输入。")
            continue
        template_symbols = parse_symbols(ctx["template"])
        if candidate in template_symbols:
            print(f"  ! 命令 \\{candidate} 已存在：{template_symbols[candidate][0]}")
            if not ask_yes_no("  是否覆盖它的定义？"):
                continue
        name = candidate

    definition = ""
    while not definition:
        raw = ask("定义（必填，例如 \\operatorname{Orb}）")
        if not raw:
            print("  ! 定义为必填，请重新输入。")
            continue
        if raw.count("{") != raw.count("}"):
            print("  ! 花括号不配对，请重新输入。")
            continue
        definition = raw.strip()

    comment = ask("注释", required=False)

    line = f"\\newcommand{{\\{name}}}{{{definition}}}"
    if comment:
        line += f"    % {comment}"

    notes = find_notes(ctx["root"], ctx["template"])
    if not notes:
        print("  ! 未扫描到子文件夹，已中止。")
        return
    backup(ctx["template"])
    ok = insert_into_symbol_lib(ctx["template"], [line])
    if not ok:
        print("  ! 模板结构异常，已中止。")
        return
    print(f"  已写入模板：{line}")
    n = distribute(ctx["template"], notes, quiet=True)
    print(f"  已同步到 {n} 个子文件夹的 structure.sty（[模块 VI] 末尾）")
    print("  提示：如需让 TeXStudio 补全识别该记号，请再执行选项 3。")


# ================================================================ 面板

def show_panel(ctx):
    notes = find_notes(ctx["root"], ctx["template"])
    data, _ = load_extract()
    pending = sum(len(v) for days in data.values() for v in days.values())

    print()
    print("=" * 62)
    print("  笔记符号管理面板")
    print("=" * 62)
    print(f"  笔记根目录：{ctx['root']}")
    print(f"  符号来源　：{ctx['template']}")
    print(f"  补全文件　：{ctx['cwl']}")
    print(f"  子文件夹　：{len(notes)} 个")
    if pending:
        print(f"  待回填　　：提取档案中累计 {pending} 条记录")
    print("-" * 62)
    print("  1. 设置笔记文件夹并扫描差异（只更新有差异的部分）")
    print("  2. 提取各子文件夹的符号")
    print("  3. 回填提取的符号（先 structure.sty，再 custom.cwl）")
    print("  4. 检验并删除未使用的符号")
    print("  5. 引入新的记号")
    print("  6. 退出")
    print("-" * 62)
    print("  可多选，用英文逗号分隔（如 1,3,5）")


def run_panel(ctx):
    while True:
        show_panel(ctx)
        try:
            raw = input("\n  请输入选项：")
        except EOFError:
            print("\n  已退出。")
            return
        raw = raw.strip()
        if not raw:
            continue
        choices, err = parse_choices(raw, 6)
        if err:
            print(f"  ! 输入有误：{err}")
            try:
                input("  按回车继续…")
            except EOFError:
                return
            continue
        if 6 in choices:
            print("\n  已退出。")
            return
        for c in choices:
            try:
                if c == 1:
                    action_setup(ctx)
                elif c == 2:
                    action_extract(ctx)
                elif c == 3:
                    action_backfill(ctx)
                elif c == 4:
                    action_unused(ctx)
                elif c == 5:
                    action_add(ctx)
            except KeyboardInterrupt:
                print("\n  已中断当前操作。")
        try:
            input("\n  按回车返回面板…")
        except EOFError:
            return


# ================================================================ 命令行

def cli_run(args, ctx):
    notes = find_notes(ctx["root"], ctx["template"])
    if not notes:
        print("未扫描到子文件夹。")
        return 1
    template_symbols = parse_symbols(ctx["template"])
    diff = diff_notes(template_symbols, notes)

    print(f"笔记根目录：{ctx['root']}")
    print(f"符号来源　：{ctx['template']}")
    print(f"子文件夹　：{len(notes)} 个")
    print(f"模板符号　：{len(template_symbols)} 个")
    if diff["additions"]:
        print(f"新增待回填：{'、'.join('\\' + k for k in sorted(diff['additions']))}")
    if diff["comments"]:
        print(f"注释差异　：{len(diff['comments'])} 处")
    if diff["conflicts"]:
        print(f"定义冲突　：{len(diff['conflicts'])} 处（不会自动覆盖）")

    do_m = args.merge or args.all
    do_d = args.distribute or args.all
    do_c = args.cwl or args.all
    do_x = bool(args.drop)
    if not (do_m or do_d or do_c or do_x):
        print("\n未指定动作；直接运行脚本可进入交互面板。")
        return 0
    if not args.write:
        print("\n预览模式：加 --write 才会写入。")
        return 0

    if do_m and (diff["additions"] or diff["comments"]):
        marker = f"合并自 {'、'.join(sorted({s for i in diff['additions'].values() for s in i['sources']}))}"
        block = [rewrite_comment(i["line"], marker) for i in diff["additions"].values()]
        repl = {k: rewrite_comment(v["line"], f"更新于 {today()}") for k, v in diff["comments"].items()}
        backup(ctx["template"])
        insert_into_symbol_lib(ctx["template"], block, repl)
        print(f"已回填：新增 {len(block)} 个，注释更新 {len(repl)} 处")
    if do_x:
        text = read_text(ctx["template"])
        lines = text.splitlines(keepends=True)
        wanted = {n.lstrip("\\") for n in args.drop}
        kept, removed = [], []
        for line in lines:
            m = DEF_RE.match(line)
            if m and m.group(1) in wanted:
                removed.append(m.group(1))
                continue
            kept.append(line)
        if removed:
            backup(ctx["template"])
            write_text(ctx["template"], "".join(kept))
            print(f"已删除：{'、'.join('\\' + n for n in removed)}")
        else:
            print("未找到指定符号。")
    if do_c:
        refresh_cwl(ctx["template"], ctx["cwl"])
    if do_d:
        print("分发到各子文件夹：")
        distribute(ctx["template"], notes)
    return 0


def main():
    parser = argparse.ArgumentParser(description="笔记符号管理（直接运行进入交互面板）")
    parser.add_argument("--cwl", action="store_true", help="刷新 TeXStudio 补全")
    parser.add_argument("--merge", action="store_true", help="回填：各笔记 -> 模板")
    parser.add_argument("--distribute", action="store_true", help="分发：模板 -> 各笔记")
    parser.add_argument("--drop", nargs="*", default=None, help="从模板删除指定符号")
    parser.add_argument("--all", action="store_true", help="回填 + 刷新补全 + 分发")
    parser.add_argument("--write", action="store_true", help="真正写入（默认仅预览）")
    parser.add_argument("--root", default=None, help="笔记根目录")
    parser.add_argument("--template", default=None, help="符号来源 structure.sty")
    parser.add_argument("--cwl-path", default=None, help="TeXStudio 补全文件路径")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass

    cfg, conf = load_config()
    root = resolve_root(args.root, cfg)
    template = resolve_template(args.template, cfg)
    cwl = resolve_cwl(args.cwl_path, cfg)

    if template is None or not template.is_file():
        print("找不到符号来源 structure.sty。")
        print("请在 symbols.conf 中设置 template，或用 --template 指定。")
        return 1

    ctx = {"root": root, "template": template, "cwl": cwl, "cfg": cfg, "conf": conf}

    has_action = args.cwl or args.merge or args.distribute or args.drop or args.all
    if has_action:
        return cli_run(args, ctx)
    run_panel(ctx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
