[app]

title = SendToKindle PoC
package.name = stkpoc
package.domain = org.stkpoc
version = 0.1.0

source.dir = .
source.include_exts = py,txt,mobi,epub

# lxml and pillow are C extensions: explicit p4a recipes are required.
# lxml pinned to 6.1.3: it supports CPython 3.14 (p4a's Python), while the
# recipe's default version fails with "no member named 'ma_version_tag'".
# Remaining ebook-converter-lib dependencies are pure Python from PyPI.
requirements = python3,kivy,lxml==6.1.3,pillow,ebook-converter-lib

# TXT/MOBI conversion needs no network; permission kept only for potential
# ebook-converter runtime probes during PoC.
android.permissions = INTERNET

# Build only the two common ABIs to keep the first PoC build fast.
android.archs = arm64-v8a, armeabi-v7a

# Required for unattended CI builds: silently accept Android SDK licenses.
android.accept_sdk_license = True

orientation = portrait
fullscreen = 0

# p4a.branch = master
# android.api / android.ndk left at buildozer defaults; override here if the
# build fails on version mismatches.

log_level = 2
