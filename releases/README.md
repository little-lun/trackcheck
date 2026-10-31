# Releases

每个版本的**发布说明**放在这里；**可下载的产物**（.html / .exe）作为 GitHub Releases 的附件，
不进 git 历史 —— 原因：

- `trackcheck-v0.2.html` 16 MB、`-setup.exe` 23 MB，每次改动重新打包都会让仓库体积翻倍，且无法回收；
- GitHub 对**单文件 100 MB** 硬性拒绝，Release 附件上限则是 2 GB，所以附件才是正确位置。

## 目录

| 版本 | 说明 | 产物 |
|---|---|---|
| `v1.0` | [发布说明](v1.0/发布说明.md) | **第一个正式版**：网页版（离线/在线）+ Win11 安装包（原生窗口） |
| `v0.2` | [发布说明](v0.2/发布说明.md) | 网页版（离线/在线）+ Win11 安装包 |
| `v0.1` | [发布说明](v0.1/发布说明.md) | 首个分发版 |

## 自己打包

```bash
python -m tools.trackcheck.build_web              # → dist/trackcheck-<完整版本号>.html / -web.html
python -m tools.trackcheck.build_win --release    # → dist/trackcheck-v1.0-setup.exe（只在正式发布时）
```

## 版本编号约定

`0.x` 是对外测试版，`1.0` 起是正式版；同一个发布里**每一处内部改动**记一位小版本
（`1.0` → `1.0.1` → `1.0.2` …），`1.0.0` 是打包基线。
**安装包文件名只用发布号**（`trackcheck-v1.0-setup.exe`），完整内部版本号写在 exe 的版本资源里；
html/exe 用完整内部版本号命名（`trackcheck-1.0.0.html`）。
