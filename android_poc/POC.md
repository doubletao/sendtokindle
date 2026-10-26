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
| 9 | **APK 已产出**（`BUILD SUCCESSFUL`、`bin/stkpoc-0.1.0-arm64-v8a-debug.apk` available）但 CI exit 1：`# Unknown command -v`——该版 buildozer 的 `-v` 是全局 flag，必须放子命令前 | workflow 改 `buildozer -v android debug` |
| — | workflow 修改不触发（paths 过滤） | paths 补 `.github/workflows/android-poc.yml` |

## PoC 代码

- `poc_convert.py` — 验证逻辑核心，与 UI 解耦，**桌面可先跑**：
  ```
  python android_poc\poc_convert.py   # 或 python -c "from android_poc.poc_convert import run_poc; run_poc()"
  ```
- `main.py` — Kivy 壳，真机上点 RUN 显示逐步 PASS/FAIL 与日志
- `buildozer.spec` — Buildozer 配置，要点：
  - `requirements` 显式声明 `lxml`、`pillow`（C 扩展必须走 p4a recipe，不能靠 pip 现编）
  - 只构建 `arm64-v8a`（CI 第 8 轮起单架构）

## 构建方法（需要 Linux 环境）

本机（Windows）当前**没有 Docker 也没有 WSL**，构建前需二选一：

1. **Docker Desktop for Windows**（推荐，官方镜像方式）：
   ```powershell
   cd android_poc
   docker run --rm -v ${PWD}:/home/user/hostcwd kivy/buildozer android debug
   ```
2. WSL2 装 Ubuntu 后在发行版内 `pip install buildozer` 构建

产物：`android_poc/bin/stkpoc-*.apk`，安装到真机点 RUN。

## CI 构建结果

- **2026-10-26 run [40277075187](https://github.com/doubletao/sendtokindle/actions/runs/40277075187)：全绿，12m04s**
- 产物：artifact `stkpoc-apk` → `stkpoc-0.1.0-arm64-v8a-debug.apk`（30.1 MB，arm64-v8a debug）
- 管线各阶段均验证通过：p4a recipes（lxml/pillow/kivy/libxml2/libxslt…交叉编译）→ 纯 Python 白名单 pip（--platform 解析）→ vendor 打包（`source.include_exts` 含资源文件，py_compile 全过）→ Gradle `BUILD SUCCESSFUL` → APK 拷入 `bin/`
- 本地临时副本：`%TEMP%\apk_out\stkpoc-0.1.0-arm64-v8a-debug.apk`
- **下一步**：装真机 → 点 RUN → 按上方验证清单判定（PoC 结论）

## 关注的失败模式（边跑边记录）

- **lxml recipe 失效**：p4a 分支/NDK 版本不匹配 → spec 中调整 `p4a.branch`、`android.api`、`android.ndk`
- **Pillow recipe 构建失败**：常见于 NDK 工具链版本变化
- **运行期缺字体**：calibre 管线转换时需要字体度量数据，缺失会表现为转换 FAIL 但有 traceback
- **临时目录不可写**：`poc_convert` 用 `tempfile`（安卓 TMPDIR 指向 app 私有 cache，理论可写）
- **体积**：实测 arm64-v8a debug APK 约 30MB（Python 运行时 + lxml + Pillow + 数据文件）

## PoC 结论

2026-10-26 真机四步全 PASS（修复 `default_tweaks.py` 被 p4a 字节编译后删除、`azw3` 未打包两个问题之后），进入 App 开发。

## App 版（0.2.0，包名 `org.sendtokindle.app`）

功能对齐 Windows 版：配置发件邮箱和 Kindle 邮箱 → 添加本地文件 → 转换并发送，每本书一封邮件，书名作标题。

- 代码：`main.py`（Kivy UI：主界面 + 设置页）、`stk/`（`config.py` / `sender.py` / `convert.py` 移植自桌面版 `app/`，`android_picker.py` 做 SAF 文件选择）
- 格式：
  - 原样发送：epub、pdf（Android 上没有 poppler，Kindle 邮件原生支持 PDF）
  - 转 EPUB：txt、mobi、azw、azw3、prc、html、htm、md、markdown、docx、fb2、rtf（真机已验证 txt/mobi/azw3，其余未在真机跑过）
  - 不支持 odt（odfpy 未打包）
- 文件选择走 SAF，不申请存储权限；选中的文件复制到 App 缓存目录再处理，发送成功后删除
- 加密方式只有 ssl（默认 465）和 starttls（默认 587），不提供明文 SMTP
- 不限制附件大小，超限由邮箱服务商或 Amazon 拒收，错误原样显示
- 发送期间保持亮屏，切到后台不退出；未做前台服务
- 配置存在 App 私有目录 `config.json`，损坏或缺失时直接进设置页重新填写

### 使用前准备

1. 发件邮箱开启 SMTP 服务并获取授权码（QQ：`smtp.qq.com`、ssl、465；163：`smtp.163.com`、ssl、465）
2. 在 Amazon「管理您的内容和设备 → 首选项 → 个人文档设置」里，把发件邮箱加进「已认可的发件人电子邮箱列表」
3. 首次打开 App 进入设置页，填写后保存；有未保存的修改时点「返回」会提示保存、放弃或取消

### 桌面测试

```
cd android_poc
python -m unittest discover tests
```
