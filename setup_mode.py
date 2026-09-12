#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup_mode.py - 习题编排模式切换脚本
======================================

管理本模板的两种习题编排模式：

  模式 1（独立习题集）: 正文零习题，习题集作为另一本书放在 ExerciseBook/ 下，
      与 Content/ 同级。习题集有自己的 main.tex 编译入口，用 xr-hyper 跨文档
      引用笔记（\\externaldocument[note-]{../main}）。

  模式 2（讲义）      : 习题作为 Section 置于每章章末，目录 Content/NN_Chapter/Exercise/，
      排在最后一个 Section 之后、本章小结之前。

脚本行为（对所选模式的目标目录）：
  1. 目录不存在          -> 按正文结构创建骨架（index.tex + 占位小节 .tex）
  2. 目录存在且结构一致  -> 跳过
  3. 目录存在但结构不一致 -> 补建缺失小节 .tex，重写 index.tex 使其 \\input 全部小节；
      原 index.tex 备份为同目录 .tex.bak

结构对齐粒度：镜像到 Section 级（正文每个 Section 对应一个 NN_exercise.tex 小节文件，
NN 与正文 Section 目录的数字前缀一致）。

脚本同时管理 main.tex 中 \\noteref 的覆盖行：
  模式 1 -> 移除覆盖行（保持 structure.sty 默认：跨文档引用 note- 前缀）
  模式 2 -> 写入覆盖行（\\renewcommand{\\noteref}[1]{\\ref{#1}} 本地引用）

用法:
  python setup_mode.py          # 交互选择模式
  python setup_mode.py 1        # 直接指定模式 1
  python setup_mode.py 2        # 直接指定模式 2
"""

import os
import re
import sys
import shutil

# ---------- 路径与常量 ----------
ROOT = os.path.dirname(os.path.abspath(__file__))
CONTENT = os.path.join(ROOT, "Content")
MAIN_TEX = os.path.join(ROOT, "main.tex")
EXBOOK = os.path.join(ROOT, "ExerciseBook")       # 模式 1 习题集根目录
EXBOOK_CONTENT = os.path.join(EXBOOK, "Content")  # 模式 1 习题集正文

NOTEREF_LINE = "\\renewcommand{\\noteref}[1]{\\ref{#1}}"

CHAPTER_RE = re.compile(r"^\d+_.+$")      # NN_ 前缀目录 = Chapter 或 Section
CHAPTER_TITLE_RE = re.compile(r"\\chapter\s*\{([^}]*)\}")
SECTION_TITLE_RE = re.compile(r"\\section\s*\{([^}]*)\}")


def info(msg):
    print("[setup_mode] " + msg)


def warn(msg):
    print("[setup_mode] WARN: " + msg)


# ---------- 正文结构扫描 ----------
def chapter_dirs():
    """返回 Content 下所有 NN_ 前缀的 Chapter 目录名（排除 Preface/Appendix 等）。"""
    if not os.path.isdir(CONTENT):
        warn("Content/ 目录不存在: " + CONTENT)
        return []
    names = [n for n in sorted(os.listdir(CONTENT))
             if CHAPTER_RE.match(n) and os.path.isdir(os.path.join(CONTENT, n))]
    return names


def section_nums(chapter):
    """返回某章内 NN_ 前缀 Section 目录的数字前缀列表（如 [01, 02, 03]）。"""
    ch_dir = os.path.join(CONTENT, chapter)
    nums = []
    if not os.path.isdir(ch_dir):
        return nums
    for n in sorted(os.listdir(ch_dir)):
        m = CHAPTER_RE.match(n)
        if m and os.path.isdir(os.path.join(ch_dir, n)):
            prefix = n.split("_", 1)[0]
            nums.append(prefix)
    return nums


def chapter_title(chapter):
    """提取正文 Chapter 的 \\chapter 标题，用于模式 1 习题集章标题。失败返回 None。"""
    idx = os.path.join(CONTENT, chapter, "index.tex")
    if os.path.isfile(idx):
        with open(idx, encoding="utf-8") as f:
            m = CHAPTER_TITLE_RE.search(f.read())
        if m:
            title = m.group(1).strip()
            if "\\" not in title:   # 避免数学命令进书签/标题导致编译问题
                return title
    return None


# ---------- 占位文件内容生成 ----------
def exercise_file_content(chapter, sec_num, sec_dirname, heading):
    """生成习题小节文件内容。heading: "section"（模式 1 习题集）或 "subsection"（模式 2 讲义）。"""
    cmd = "\\section" if heading == "section" else "\\subsection"
    return (
        cmd + "{第 " + sec_num + " 节 习题}\n"
        "\n"
        "% 对应正文 Section: " + sec_dirname + "\n"
        "% 引用正文定理/定义请用 \\noteref{标签} (两种模式自动适配引用方式).\n"
        "\n"
        "\\begin{exercise}{题目一}{exr:" + chapter + "-" + sec_num + "-1}\n"
        "    题目内容.\n"
        "\\end{exercise}\n"
        "\n"
        "\\begin{solution}\n"
        "    解答内容.\n"
        "\\end{solution}\n"
    )


def exercise_index_content(chapter, sec_nums, mode):
    """模式 2 的 Exercise/index.tex 内容。"""
    lines = ["\\section{习题}", ""]
    for n in sec_nums:
        lines.append(
            "\\input{./Content/" + chapter + "/Exercise/" + n + "_exercise}")
    return "\n".join(lines) + "\n"


def mode1_chapter_index_content(chapter, title, sec_nums):
    """模式 1 习题集 Chapter 的 index.tex 内容 (在 ExerciseBook/ 目录内编译)."""
    head = "\\chapter{" + (title + " 习题" if title else chapter + " 习题") + "}"
    lines = [head, ""]
    for n in sec_nums:
        lines.append(
            "\\input{./Content/" + chapter + "/" + n + "_exercise}")
    return "\n".join(lines) + "\n"


def mode1_main_tex_content():
    """模式 1 习题集根目录 main.tex 骨架。"""
    return (
        "\\documentclass[10pt,a4paper,oneside,scheme=plain]{ctexbook}\n"
        "\n"
        "\\usepackage{../structure}\n"
        "\\usepackage{xr-hyper}\n"
        "\n"
        "% 跨文档引用笔记 main.aux: 笔记侧标签在习题集中统一带 note- 前缀\n"
        "% (配合 structure.sty 中 \\noteref 的默认定义 \\ref{note-...}).\n"
        "% 注意: 需先在项目根目录编译笔记 main.tex 生成 main.aux.\n"
        "\\externaldocument[note-]{../main}\n"
        "\n"
        "\\author{Yukina}\n"
        "\\title{\\Huge\\textbf{习题集}}\n"
        "\\date{\\today}\n"
        "\n"
        "\\begin{document}\n"
        "\n"
        "\\frontmatter\n"
        "\\maketitle\n"
        "\\tableofcontents\n"
        "\n"
        "\\mainmatter\n"
        "\n"
        "% 在 ExerciseBook/ 目录内编译: latexmk -xelatex main.tex\n"
        "\\input{./Content/01_Test_Chapter/index}\n"
        "\\input{./Content/02_Test_Chapter/index}\n"
        "\n"
        "\\end{document}\n"
    )


# ---------- 模式 2: 每章 Exercise/ ----------
def ensure_mode2_chapter(chapter):
    """确保 Content/NN_Chapter/Exercise/ 存在且与正文 Section 结构一致。"""
    sec_nums = section_nums(chapter)
    ex_dir = os.path.join(CONTENT, chapter, "Exercise")
    changed = False

    if not sec_nums:
        info("章 " + chapter + " 没有 NN_ Section 目录, 跳过")
        return False

    if not os.path.isdir(ex_dir):
        os.makedirs(ex_dir)
        info("创建 " + os.path.relpath(ex_dir, ROOT))

    # 1) 补建缺失的小节文件
    for n in sec_nums:
        fpath = os.path.join(ex_dir, n + "_exercise.tex")
        if not os.path.isfile(fpath):
            sec_dirname = next(
                (d for d in sorted(os.listdir(os.path.join(CONTENT, chapter)))
                 if d.startswith(n + "_") and os.path.isdir(os.path.join(CONTENT, chapter, d))),
                n + "_Section")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(exercise_file_content(chapter, n, sec_dirname, "subsection"))
            info("新建 " + os.path.relpath(fpath, ROOT))
            changed = True

    # 2) index.tex: 缺失则创建; 已存在则检查 \\input 是否齐全
    idx = os.path.join(ex_dir, "index.tex")
    desired = exercise_index_content(chapter, sec_nums, 2)

    if not os.path.isfile(idx):
        with open(idx, "w", encoding="utf-8") as f:
            f.write(desired)
        info("新建 " + os.path.relpath(idx, ROOT))
        changed = True
    else:
        with open(idx, encoding="utf-8") as f:
            cur = f.read()
        # 判断是否已包含全部期望的 \input 行
        want_lines = [ln for ln in desired.splitlines() if ln.startswith("\\input")]
        have_lines = set(cur.splitlines())
        missing = [ln for ln in want_lines if ln not in have_lines]
        if missing:
            shutil.copy2(idx, idx + ".bak")
            info("备份原 " + os.path.relpath(idx, ROOT) + " -> index.tex.bak")
            with open(idx, "w", encoding="utf-8") as f:
                f.write(desired)
            info("重写 " + os.path.relpath(idx, ROOT) + " (补入缺失 \\input)")
            changed = True
        else:
            info("章 " + chapter + " 的 Exercise/ 结构一致, 跳过")

    # 3) 章 index.tex: 模式 2 接入 Exercise/index (最后一个 Section 之后、Summary 之前);
    #    模式 1 移除该接入行
    if manage_chapter_index(chapter, 2):
        changed = True

    return changed


def manage_chapter_index(chapter, mode):
    """把 \\input{.../Exercise/index} 接入/移出章 index.tex。返回是否改动。"""
    idx = os.path.join(CONTENT, chapter, "index.tex")
    if not os.path.isfile(idx):
        return False
    with open(idx, encoding="utf-8") as f:
        lines = f.read().splitlines(keepends=True)

    ex_line = "\\input{./Content/" + chapter + "/Exercise/index}"
    has_ex = any(ln.strip() == ex_line for ln in lines)
    changed = False

    if mode == 2 and not has_ex:
        # 定位 Summary 行, 在其之前插入; 无 Summary 则追加到末尾
        summary_idx = next(
            (i for i, ln in enumerate(lines)
             if ln.strip().startswith("\\input") and "Summary/index" in ln),
            None)
        insert = ex_line + "\n"
        if summary_idx is not None:
            lines.insert(summary_idx, insert)
        else:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append(insert)
        changed = True
        info("章 index: 接入 " + ex_line)
    elif mode == 1 and has_ex:
        lines = [ln for ln in lines if ln.strip() != ex_line]
        changed = True
        info("章 index: 移除 " + ex_line)

    if changed:
        shutil.copy2(idx, idx + ".bak")
        info("备份原 " + os.path.relpath(idx, ROOT) + " -> index.tex.bak")
        with open(idx, "w", encoding="utf-8") as f:
            f.writelines(lines)
    return changed


# ---------- 模式 1: ExerciseBook/ ----------
def ensure_mode1():
    """确保 ExerciseBook/ 存在且镜像正文 Chapter -> Section 结构。"""
    chapters = chapter_dirs()
    if not chapters:
        return False
    changed = False

    if not os.path.isdir(EXBOOK):
        os.makedirs(EXBOOK)
        info("创建 " + os.path.relpath(EXBOOK, ROOT))
        changed = True
    if not os.path.isdir(EXBOOK_CONTENT):
        os.makedirs(EXBOOK_CONTENT)
        info("创建 " + os.path.relpath(EXBOOK_CONTENT, ROOT))
        changed = True

    # 习题集 main.tex
    main_idx = os.path.join(EXBOOK, "main.tex")
    if not os.path.isfile(main_idx):
        with open(main_idx, "w", encoding="utf-8") as f:
            f.write(mode1_main_tex_content())
        info("新建 " + os.path.relpath(main_idx, ROOT))
        changed = True

    # 逐章镜像
    for chapter in chapters:
        sec_nums = section_nums(chapter)
        ch_dir = os.path.join(EXBOOK_CONTENT, chapter)
        if not os.path.isdir(ch_dir):
            os.makedirs(ch_dir)
            info("创建 " + os.path.relpath(ch_dir, ROOT))
            changed = True

        if not sec_nums:
            info("章 " + chapter + " 没有 NN_ Section 目录, 跳过习题小节")
            continue

        # 小节文件
        for n in sec_nums:
            fpath = os.path.join(ch_dir, n + "_exercise.tex")
            if not os.path.isfile(fpath):
                sec_dirname = next(
                    (d for d in sorted(os.listdir(os.path.join(CONTENT, chapter)))
                     if d.startswith(n + "_") and os.path.isdir(os.path.join(CONTENT, chapter, d))),
                    n + "_Section")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(exercise_file_content(chapter, n, sec_dirname, "section"))
                info("新建 " + os.path.relpath(fpath, ROOT))
                changed = True

        # 章 index.tex
        idx = os.path.join(ch_dir, "index.tex")
        title = chapter_title(chapter)
        desired = mode1_chapter_index_content(chapter, title, sec_nums)
        if not os.path.isfile(idx):
            with open(idx, "w", encoding="utf-8") as f:
                f.write(desired)
            info("新建 " + os.path.relpath(idx, ROOT))
            changed = True
        else:
            with open(idx, encoding="utf-8") as f:
                cur = f.read()
            want_lines = [ln for ln in desired.splitlines() if ln.startswith("\\input")]
            have_lines = set(cur.splitlines())
            missing = [ln for ln in want_lines if ln not in have_lines]
            if missing:
                shutil.copy2(idx, idx + ".bak")
                info("备份原 " + os.path.relpath(idx, ROOT) + " -> index.tex.bak")
                with open(idx, "w", encoding="utf-8") as f:
                    f.write(desired)
                info("重写 " + os.path.relpath(idx, ROOT) + " (补入缺失 \\input)")
                changed = True
            else:
                info("章 " + chapter + " 习题结构一致, 跳过")

    return changed


# ---------- main.tex 中 \\noteref 覆盖行管理 ----------
def manage_main_tex(mode):
    """模式 1: 移除覆盖行; 模式 2: 确保覆盖行存在。"""
    if not os.path.isfile(MAIN_TEX):
        warn("main.tex 不存在, 跳过 \\noteref 管理")
        return False
    with open(MAIN_TEX, encoding="utf-8") as f:
        content = f.read()

    has_line = NOTEREF_LINE in content
    changed = False

    if mode == 1 and has_line:
        # 删除覆盖行及其上方连续的注释块/空行（保留正文其他内容）
        lines = content.splitlines(keepends=True)
        out = []
        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped == NOTEREF_LINE:
                changed = True
                i += 1
                continue
            # 若当前行是注释/空行, 且其后若干行内就是覆盖行, 则一并删除
            if stripped == "" or stripped.startswith("%"):
                j = i + 1
                while j < len(lines) and (lines[j].strip() == "" or lines[j].strip().startswith("%")):
                    j += 1
                if j < len(lines) and lines[j].strip() == NOTEREF_LINE:
                    changed = True
                    i += 1
                    continue
            out.append(lines[i])
            i += 1
        if changed:
            with open(MAIN_TEX, "w", encoding="utf-8") as f:
                f.writelines(out)
            info("main.tex: 已移除 \\noteref 覆盖行及注释块 (模式 1, 保持跨文档默认)")
    elif mode == 2 and not has_line:
        # 在 \usepackage{quiver} 后插入覆盖行
        block = (
            "\n% 讲义模式 (模式 2): 习题内嵌正文, \\noteref 直接引用本文档内的标签.\n"
            "% 由 setup_mode.py 管理: 模式 1 时本行会被移除.\n"
            + NOTEREF_LINE + "\n"
        )
        if "\\usepackage{quiver}" in content:
            content = content.replace("\\usepackage{quiver}",
                                      "\\usepackage{quiver}" + block, 1)
        else:
            content += block
        with open(MAIN_TEX, "w", encoding="utf-8") as f:
            f.write(content)
        info("main.tex: 已写入 \\noteref 覆盖行 (模式 2, 本地引用)")
        changed = True
    else:
        info("main.tex: \\noteref 覆盖行状态已与模式 " + str(mode) + " 一致, 无改动")

    return changed


# ---------- 主流程 ----------
def main():
    if len(sys.argv) >= 2 and sys.argv[1] in ("1", "2"):
        mode = int(sys.argv[1])
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
        ans = input("选择习题编排模式 (1 = 独立习题集 ExerciseBook/, 2 = 讲义每章 Exercise/): ").strip()
        if ans not in ("1", "2"):
            warn("无效输入, 退出")
            sys.exit(1)
        mode = int(ans)

    info("=== 模式 " + str(mode) + " ===")
    if mode == 1:
        changed = ensure_mode1()
        # 模式 1: 各章正文不接入 Exercise, 从章 index 移除
        for ch in chapter_dirs():
            if manage_chapter_index(ch, 1):
                changed = True
    else:
        changed = False
        chapters = chapter_dirs()
        for ch in chapters:
            if ensure_mode2_chapter(ch):
                changed = True

    manage_main_tex(mode)

    print()
    if changed:
        info("完成: 有新建/备份/重写操作, 请重新编译验证 (XeLaTeX).")
    else:
        info("完成: 目标目录结构与正文一致, 无改动.")


if __name__ == "__main__":
    main()
