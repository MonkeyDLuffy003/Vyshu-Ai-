[app]
title = Vyshu AI
package.name = vyshuai
package.domain = org.kakarot003
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = tests,bin,.buildozer,.git,__pycache__
version = 3.0

# â”€â”€ Keep requirements MINIMAL for successful build â”€â”€
requirements = python3,kivy,pillow,certifi

orientation = portrait
fullscreen = 0

android.archs = arm64-v8a
android.api = 31
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.allow_backup = True
android.wakelock = True

android.permissions = \
    INTERNET,\
    RECORD_AUDIO,\
    MODIFY_AUDIO_SETTINGS,\
    CHANGE_WIFI_STATE,\
    ACCESS_WIFI_STATE,\
    CHANGE_NETWORK_STATE,\
    CAMERA,\
    VIBRATE,\
    FOREGROUND_SERVICE,\
    READ_EXTERNAL_STORAGE,\
    WRITE_EXTERNAL_STORAGE

presplash.color = #0d1117
p4a.bootstrap = sdl2

[buildozer]
log_level = 2
warn_on_root = 1
