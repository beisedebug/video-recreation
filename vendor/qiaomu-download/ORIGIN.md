# Vendored qiaomu-download

Source: [joeseesun/qiaomu-download](https://github.com/joeseesun/qiaomu-download), author 向阳乔木. Local installed version 1.3.0, copied 2026-10-26 from the user's existing skill. Copyright 2026 向阳乔木; MIT license retained in LICENSE. No upstream Git commit was available in this installed copy; the exact upstream bytes are identified below. Thank you to the author and contributors for sharing this implementation.

This is a runtime dependency, not a second active skill. UPSTREAM_SKILL.md preserves the source instructions for provenance; video-recreation and scripts/download_reference.py govern execution. In particular, the wrapper does not invoke the upstream doctor or automatic upgrades. The wrapper rejects Spotify as a video reference, but the optional adapter and its strategy file are retained to keep the original runtime closure complete.

Local patch: all yt-dlp subprocess invocations in scripts/download.py and scripts/spotify_adapter.py receive --ignore-config and --no-cache-dir. This prevents inherited yt-dlp configuration from silently enabling cookies or other options and avoids the default cache. No global configuration or installation is modified.

The optional WeChat runtime reuses an already connected local backend. install_backend.py and release-lock.json are retained for component integrity and explicit, separately authorized setup only; the reference wrapper never invokes installation, certificates, system proxy changes or UI automation. Its external backend has its own license requirements described in references/wechat-video.md.

## Upstream SHA-256 before local patches

| Vendored file | Upstream SHA-256 |
|---|---|
| LICENSE | `6ccfe9fbe711e863b7e6e48abc25f4d094b0b10e28b04a7b047692390bb5de35` |
| UPSTREAM_SKILL.md | `7bb981bce9ad3e4cc078c298ebdbe502d13d94431c69654edc14f73426c3be49` |
| scripts/download.py | `6e3128905ba7fb59741578ea8f4b63defb7ffb985760d449e2d73cc752d22398` |
| scripts/wechat_adapter.py | `3e0677460d4cb7e8960b1adb19ad4c9cb6acfede94dfcf82fb7f4e59c68ddcb0` |
| scripts/spotify_adapter.py | `4b90fed3a9490e4c3455de4d8d3093c6ff9bc88519f9824d6e82ae99efdb30d5` |
| scripts/spotify/release-lock.json | `23b070655818e2e550b6a357e6b0c40464d7e8e4295255a4de9847c328bfbc90` |
| scripts/wechat/preflight.py | `18281c5ea000a820c966ceb6478fc9999176142b901027d3fd4462b34f551634` |
| scripts/wechat/download_media.py | `a81c06c1fc8a276b03875ac6b797f99317ea64cf83139be8f6bfe41b91b9d5f5` |
| scripts/wechat/download_online.py | `6833a6721a98a430fc0fd006529fea7016bd491252da57684e39a927203b6a33` |
| scripts/wechat/install_backend.py | `472a3b7cd336d9e4d7f0b7ee361780108ea398e7377c2410f6b0ad99d8a0f7fe` |
| scripts/wechat/release-lock.json | `d53ffd466f236269a35fa7f403a5e569cc56eb51250ce41b5c2ac41544ad25c0` |
| references/wechat-video.md | `f6f16e4a9e221a5fd9e0b6f7d43a57fad1ea3515a09a0794bfa505fe00735e49` |
| references/workflow.md | `7fa6579f00831dad90f81d775ebaf314ca1d002c0c47e4bec0f05f59d2898e35` |
| references/security.md | `edfe73d18a049cc8a8063f3550396d7c79bfd179b3ad6ce4dd8a884340442f99` |
| references/platforms.md | `425fa111af1286ffd78c1bffbb6ef9f75b95283c0e5110553253c7dded347495` |
