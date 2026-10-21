LXGW WenKai TC Regular（霞鹜文楷 TC）

Source: https://github.com/google/fonts/tree/main/ofl/lxgwwenkaitc
License: SIL Open Font License 1.1; see LXGWWenKaiTC-OFL.txt.
Converted from the upstream Regular TTF to WOFF2 with fontTools, without altering glyphs.
Used for traditional reader annotations.

AR PL UKai TW（文鼎 PL 中楷，繁体台湾字形）
Source: https://deb.debian.org/debian/pool/main/f/fonts-arphic-ukai/
License: Arphic Public License; see AR-PL-UKai-LICENSE.txt.
The TW face was extracted from ukai.ttc and converted to WOFF2 without altering glyphs.
Used as the primary traditional reader annotation font; WenKai TC covers missing glyphs.

Noto Sans CJK TC Regular（思源黑体繁体字形）
Source: https://github.com/notofonts/noto-cjk/tree/main/Sans
License: SIL Open Font License 1.1; see NotoSansCJK-OFL.txt.
The TC face from the installed NotoSansCJK-Regular.ttc was subset to characters
in dist/vertical-book/chapter-*.json and converted to WOFF2 with fontTools.
Regenerate the subset when adding new vertical source text.
Used for the screenshot-matched vertical reader body; UKai TW remains the note face.
