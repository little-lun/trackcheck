# Releases

每个版本的**发布说明**放在这里；**可下载的产物**（.html / .exe）作为 GitHub Releases 的附件，
不进 git 历史 —— 原因：

- `trackcheck-v0.2.html` 16 MB、`-setup.exe` 23 MB，每次改动重新打包都会让仓库体积翻倍，且无法回收；
- GitHub 对**单文件 100 MB** 硬性拒绝，Release 附件上限则是 2 GB，所以附件才是正确位置。

## 目录

| 版本 | 说明 | 产物 |
|---|---|---|
| `v0.2` | [发布说明](v0.2/发布说明.md) | 网页版（离线/在线）+ Win11 安装包 |
| `v0.1` | [发布说明](v0.1/发布说明.md) | 首个分发版 |

## 自己打包

```bash
python -m tools.trackcheck.build_web   # → tools/trackcheck/dist/trackcheck-v0.2*.html
python -m tools.trackcheck.build_win   # → tools/trackcheck/dist/trackcheck-v0.2-setup.exe
```

## 版本编号约定

对外测试版一律 `0.x`；同一次发布里**每一处改动**记 `0.x.n`（`0.2` → `0.2.1` → `0.2.6` …）；
`0.x.0` 是打包基线。所以**文件名永远只到 `0.x`**，内部版本号写在 exe 的版本资源里。
