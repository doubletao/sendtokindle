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

## 架构决策：ebook-converter-lib 以 vendor 方式打包（CI 第 8 轮定案）

**问题链**（GitHub Actions 逐轮暴露）：

1. p4a 对无 recipe 的纯 Python 包用 `pip install --only-binary=:all: --platform=android_24_*` 安装
2. ebook-converter-lib 的 metadata 会把 lxml/pillow（有 recipe 但 `--ignore-installed`）、reportlab（manylinux-only wheel）、odfpy（sdist-only）拉进解析 → ResolutionImpossible

**验证结论**（干净 venv 模拟安卓依赖子集）：txt/mobi/azw3→epub 转换**不需要** reportlab/odfpy/svglib（lazy import，只在 SVG/ODF/PDF 输出路径用），四步全 PASS。

**方案**：

- `ebook_converter/`（341 py + 12 数据资源）、`ebook_converter_lib/`、vendored `html5_parser/`、入口 `converter.py` 从 wheel 解包 vendor 进 `android_poc/` 源码，由 buildozer `source.include_exts` 打包——**彻底退出 pip 解析**
- requirements 只留 `lxml==6.1.3`、`pillow`（p4a recipe 交叉编译）+ 纯 py 白名单（全部 py3-none-any wheel，`--platform` 安全）
- 代价：正式版升级 e-c-lib 需重新 vendor；SVG/ODF 输入格式不支持（PoC 不需要）

### CI 已解决的问题（复现时按序查）

| # | 症状 | 修复 |
|---|---|---|
| 1 | `.gitignore` 的 `*.spec` 拦了 buildozer.spec | 加 `!android_poc/buildozer.spec` |
| 2 | `One of "version" or "version.regex" must be set` | spec 加 `version = 0.1.0` |
| 3 | SDK `Accept? (y/N):` 无人应答 → aidl 缺失 | `android.accept_sdk_license = True` |
| 4 | libffi `autogen.sh`: undefined macro `LT_SYS_SYMBOL_USCORE` | workflow `apt install libltdl-dev` |
| 5 | lxml `no member named 'ma_version_tag'`（p4a 是 Python 3.14） | `lxml==6.1.3`（支持 3.14） |
| 6 | pip ResolutionImpossible（reportlab/odfpy/lxml 传递依赖撞 `--only-binary --platform`） | vendor e-c-lib + 白名单 requirements（本节） |
| 7 | `No module named 'html5_parser'`（txt heuristic 分支需要） | wheel 自带的 `html5_parser/` 一并 vendor |
| 8 | `charset_normalizer-3.5.2-cp314-...whl is not a supported wheel on this platform`（p4a `process_python_modules` 对每个模块跑 `packaging.Requirement()`：裸 URL 抛异常 → "Ignored by module resolver"、不进 pip --dry-run；dry-run 独立把 requests 解析到 3.5.2 的 android wheel（platform tag 与 arch 匹配判通过）追加进安装列表，与兜底保留的 URL 双 charset 共存，安装阶段拒绝 android wheel） | requirements 用 PEP 508 直连形式 `charset-normalizer@https://...2.1.0-py3-none-any.whl`：`Requirement()` 解析成功进 `_requirement_names`，dry-run 直接以 2.1.0 满足 requests（`>=2,<4`），none-any 全平台可装；同时 `android.archs = arm64-v8a` 单架构（消除 v7a 第二套 platform 分叉，构建时间减半） |
| — | workflow 修改不触发（paths 过滤） | paths 补 `.github/workflows/android-poc.yml` |

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
