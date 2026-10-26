[app]

title = SendToKindle
# Package id: org.sendtokindle.app (the old PoC was org.stkpoc.stkpoc).
package.name = app
package.domain = org.sendtokindle
version = 0.2.0

source.dir = .
# py/txt/mobi/azw3/epub: app code, self-check assets and vendored library sources.
# css/xsl/tmpl/json/types/html/xhtml: data files of the vendored ebook_converter package.
source.include_exts = py,txt,mobi,azw3,epub,css,xsl,tmpl,json,types,html,xhtml
# Desktop unit tests and locally downloaded CI artifacts stay out of the APK.
source.exclude_dirs = tests,downloaded_apk,bin

# ebook-converter-lib is vendored into source (see POC.md): its pip metadata
# pulls reportlab/svglib/odfpy which have no android-compatible wheels, while
# txt/mobi/azw3 -> epub conversion works without them (verified on desktop).
# lxml and pillow are C extensions with explicit p4a recipes.
# lxml pinned to 6.1.3: it supports CPython 3.14 (p4a's Python), while the
# recipe's default version fails with "no member named 'ma_version_tag'".
# All other listed packages ship py3-none-any wheels (pip --platform safe).
# charset-normalizer given as a PEP 508 direct reference to a py3-none-any
# wheel: p4a's module resolver runs packaging.Requirement() on each module and
# a bare URL raises (warning "Ignored by module resolver"), dropping it from
# the pip --dry-run; the dry-run then resolves requests' dependency to the 3.5.2
# android wheel and appends it, and the install step rejects that wheel.
# With "name@url" the requirement parses, the dry-run satisfies requests from
# the 2.1.0 wheel directly, and none-any installs on every platform.
# 3.x ships only platform wheels; 2.1.0 satisfies requests' >=2,<4.
# pyjnius / android (p4a recipes): SAF file picker and keep-screen-on flag.
# certifi (py3-none-any): CA bundle for SMTP TLS, OpenSSL on Android has no
# readable system CA path.
requirements = python3,kivy,pyjnius,android,certifi,lxml==6.1.3,pillow,beautifulsoup4,css-parser,html2text,markdown,pypdf,python-dateutil,charset-normalizer@https://files.pythonhosted.org/packages/94/69/64b11e8c2fb21f08634468caef885112e682b0ebe2908e74d3616eb1c113/charset_normalizer-2.1.0-py3-none-any.whl

# INTERNET for SMTP. Files are picked via SAF (ACTION_OPEN_DOCUMENT), which
# needs no storage permission.
android.permissions = INTERNET

# arm64-v8a only: covers current phones and halves CI build time.
android.archs = arm64-v8a

# Required for unattended CI builds: silently accept Android SDK licenses.
android.accept_sdk_license = True

orientation = portrait
fullscreen = 0

# p4a.branch = master
# android.api / android.ndk left at buildozer defaults; override here if the
# build fails on version mismatches.

log_level = 2
