# setup_mode.py

切换习题的编排模式。

## 运行

```bash
python setup_mode.py        # 交互式选择
python setup_mode.py 1      # 直接指定模式 1
python setup_mode.py 2      # 直接指定模式 2
```

不带参数运行时，命令行窗口提示：

```
选择习题编排模式 (1 = 独立习题集 ExerciseBook/, 2 = 讲义每章 Exercise/):
```

## 选项

| 输入 | 模式 | 说明 |
|---|---|---|
| `1` | 独立习题集 | 正文零习题，习题集作为另一本书放在 `ExerciseBook/` 下 |
| `2` | 讲义 | 习题作为 Section 置于每章章末，目录为 `Content/NN_Chapter/Exercise/` |

## 行为

对所选模式的目标目录：

- 目录不存在 → 按正文结构创建骨架（`index.tex` + 占位小节 `.tex`）
- 目录已存在且结构一致 → 跳过

同时调整 `structure.sty` 中的跨文档引用设置：

- 模式 1 → 移除覆盖行（保持默认的 `note-` 前缀，供跨文档引用）
- 模式 2 → 写入覆盖行（`\renewcommand{\noteref}[1]{\ref{#1}}`，改为本地引用）
