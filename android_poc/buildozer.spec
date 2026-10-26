[app]

title = SendToKindle PoC
package.name = stkpoc
package.domain = org.stkpoc
version = 0.1.0

source.dir = .
# py/txt/mobi/epub: PoC code, test assets and vendored library sources.
# css/xsl/tmpl/json/types/html/xhtml: data files of the vendored ebook_converter package.
source.include_exts = py,txt,mobi,epub,css,xsl,tmpl,json,types,html,xhtml

# ebook-converter-lib is vendored into source (see POC.md): its pip metadata
# pulls reportlab/svglib/odfpy which have no android-compatible wheels, while
# txt/mobi/azw3 -> epub conversion works without them (verified on desktop).
# lxml and pillow are C extensions with explicit p4a recipes.
# lxml pinned to 6.1.3: it supports CPython 3.14 (p4a's Python), while the
# recipe's default version fails with "no member named 'ma_version_tag'".
# All other listed packages ship py3-none-any wheels (pip --platform safe).
# charset-normalizer pinned via a direct py3-none-any wheel URL: 3.x ships only
# platform wheels (p4a's pip dry-run picks the android one, the install step
# then rejects it: "not a supported wheel on this platform"), and p4a strips
# version pins when a requested recipe is unavailable and it falls back to pip.
# 2.1.0 satisfies requests' >=2,<4 and a none-any wheel installs anywhere.
requirements = python3,kivy,lxml==6.1.3,pillow,beautifulsoup4,css-parser,html2text,markdown,pypdf,python-dateutil,https://files.pythonhosted.org/packages/94/69/64b11e8c2fb21f08634468caef885112e682b0ebe2908e74d3616eb1c113/charset_normalizer-2.1.0-py3-none-any.whl

# TXT/MOBI conversion needs no network; permission kept only for potential
# ebook-converter runtime probes during PoC.
android.permissions = INTERNET

# Build only the two common ABIs to keep the first PoC build fast.
android.archs = arm64-v8a

# Required for unattended CI builds: silently accept Android SDK licenses.
android.accept_sdk_license = True

orientation = portrait
fullscreen = 0

# p4a.branch = master
# android.api / android.ndk left at buildozer defaults; override here if the
# build fails on version mismatches.

log_level = 2
