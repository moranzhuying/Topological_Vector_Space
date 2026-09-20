# commit.py

一键提交并推送到 GitHub。

## 运行

```bash
python commit.py            # 以默认说明「更新笔记」提交
python commit.py "说明"      # 以指定说明提交
```

本脚本没有命令行选项。

## 执行后在命令行窗口看到的内容

正常提交：

```
==> 暂存改动
==> 提交：更新笔记
==> 推送到 GitHub
完成，已同步到 GitHub。
```

没有需要提交的改动时：

```
没有改动，无需提交。
```

## 行为

1. 切换到脚本所在目录（即笔记根目录）
2. 用 `git status --porcelain` 检查改动，无改动则直接退出
3. 依次执行 `git add -A` → `git commit` → `git push`

推送走 SSH（GitHub 443 端口）。
