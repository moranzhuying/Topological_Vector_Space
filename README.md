# 拓扑向量空间

Bourbaki《数学原本》(Éléments de mathématique) 中《拓扑向量空间》一卷的自学笔记。

## 内容

凸集与局部凸空间、拓扑向量空间的对偶、Hilbert 空间初等理论、连续线性映射空间、拓扑张量积、核映射与核空间、取值于赋值除环的拓扑向量空间。

## 编译

须使用 XeLaTeX（`structure.sty` 依赖 ctexbook 与 XeLaTeX 特性）：

```bash
xelatex main.tex
```

`main.pdf` 未纳入版本控制，需本地编译生成。

## 目录结构

```
main.tex          编译入口
structure.sty     样式包：页面设置、定理环境（tcolorbox）、引用（hyperref + cleveref）、数学符号库
quiver.sty        交换图支持
Content/          分章正文，每章一个目录，由 index.tex 汇总 \input
commit.py         一键提交并推送到 GitHub
setup_mode.py     习题编排模式切换（独立习题集 / 章末习题）
symbols.py        符号库管理：刷新补全 / 回填模板 / 分发到各笔记
```

## 脚本

```bash
python commit.py "提交说明"    # 提交并推送，说明可省略（默认「更新笔记」）
python setup_mode.py 1|2      # 切换习题编排模式
python symbols.py                 # 预览符号库差异（路径见 symbols.conf）
python symbols.py --all --write   # 回填模板 + 刷新补全 + 分发到各笔记
```

## 说明

正文使用英文标点；定理与证明环境由 `structure.sty` 提供。编译产物（aux / log / out / toc / synctex.gz / pdf）与备份文件已在 `.gitignore` 中排除。
