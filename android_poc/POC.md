# Android PoC — ebook-converter-lib 真机验证

## 目标

回答一个问题：**ebook-converter-lib 转换内核能否在安卓真机上跑通？**
通过则安卓版复用原内核（转换质量最优）；失败则切换纯 Python 转换栈（见仓库讨论的方案 A）。

PDF 不在 PoC 范围内——已确定安卓版 PDF 直接发送、不转换（无需 poppler）。

## 验证清单与判定标准

| # | 步骤 | 判定 |
|---|---|---|
| 0 | `check_deps_str()` | 输出 `Dependencies available.`（依赖链在安卓运行时完整） |
| 1 | `sample.txt` → EPUB | 生成非空 epub |
| 2 | `sample.mobi` → EPUB | 生成非空 epub（**核心问题**：calibre 的 MOBI 解析 + 管线在安卓可用） |
| 3 | `sample.azw3` → EPUB | 生成非空 epub（KF8 链路） |

- **全 PASS** → 通过，进入正式安卓版开发（Kivy UI + SAF 文件选择 + 前台服务）
- **step0/1 FAIL** → 依赖或运行环境问题（lxml/Pillow recipe、临时目录等），先尝试修复
- **step2/3 FAIL 且 0/1 PASS** → Python 纯逻辑部分 OK、mobi 管线有平台假设问题 → 评估切方案 A

## 测试资产

`assets/` 下三个文件由桌面版生成，已随分支提交：

- `sample.txt` — 纯文本输入
- `sample.mobi` / `sample.azw3` — 由桌面 `ebook_converter_lib` 从 txt 转出，作为回转测试输入

## PoC 代码

- `poc_convert.py` — 验证逻辑核心，与 UI 解耦，**桌面可先跑**：
  ```
  python android_poc\poc_convert.py   # 或 python -c "from android_poc.poc_convert import run_poc; run_poc()"
  ```
- `main.py` — Kivy 壳，真机上点 RUN 显示逐步 PASS/FAIL 与日志
- `buildozer.spec` — Buildozer 配置，要点：
  - `requirements` 显式声明 `lxml`、`pillow`（C 扩展必须走 p4a recipe，不能靠 pip 现编）
  - 只构建 `arm64-v8a, armeabi-v7a`，加快首轮构建

## 构建方法（需要 Linux 环境）

本机（Windows）当前**没有 Docker 也没有 WSL**，构建前需二选一：

1. **Docker Desktop for Windows**（推荐，官方镜像方式）：
   ```powershell
   cd android_poc
   docker run --rm -v ${PWD}:/home/user/hostcwd kivy/buildozer android debug
   ```
2. WSL2 装 Ubuntu 后在发行版内 `pip install buildozer` 构建

产物：`android_poc/bin/stkpoc-*.apk`，安装到真机点 RUN。

## 关注的失败模式（边跑边记录）

- **lxml recipe 失效**：p4a 分支/NDK 版本不匹配 → spec 中调整 `p4a.branch`、`android.api`、`android.ndk`
- **Pillow recipe 构建失败**：常见于 NDK 工具链版本变化
- **运行期缺字体**：calibre 管线转换时需要字体度量数据，缺失会表现为转换 FAIL 但有 traceback
- **临时目录不可写**：`poc_convert` 用 `tempfile`（安卓 TMPDIR 指向 app 私有 cache，理论可写）
- **体积**：首轮 APK 预计 50-80MB（Python 运行时 + lxml + Pillow + 数据文件），属预期

## 后续（PoC 通过后才开工）

1. Kivy 正式 UI（文件多选列表、配置、进度）
2. SAF `content://` URI → 拷贝到缓存目录再转换
3. 前台服务保活（转换 + 发送期间显示通知）
4. `sender.py` / `config.py` 原样复用
