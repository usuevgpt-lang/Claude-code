---
name: web-assets
description: >-
  Веб-ассеты сайта novaprom.ru (MODX Revolution) — favicon (ICO 16/32/48, PNG, SVG), иконки приложений
  (apple-touch-icon, android-chrome 192/512, maskable), site.webmanifest, картинки Open Graph / Twitter
  для превью ссылок (PNG + WebP, опционально JPEG) с русским текстом, размеры изображений, проверка
  web-assets и HTML-теги для <head>. Use for favicons, app icons, web app manifest, Open Graph / social
  share images, WebP variants, checking image sizes and validating existing web assets.
when_to_use: >-
  "сделай фавикон из логотипа", "иконки для сайта", "картинка для превью ссылки в Telegram/VK/WhatsApp",
  "og:image для страницы", "нужен webmanifest", "проверь размеры иконок", "почему нет превью ссылки",
  "make favicons", "generate Open Graph image", "check web assets".
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/*) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
---

# Web assets: favicon, иконки, webmanifest, Open Graph (НОВАПРОМ)

Сайт novaprom.ru: MODX Revolution, nginx/PHP, Bootstrap 4.5.3. Бренд: янтарный #FDB913, почти чёрный
#1C1C1C, белый; линии иконок #4D7C90; шрифт Raleway. Основа — alonw0/web-asset-generator (MIT),
исправлена (`NOTICE.md`). Скрипты: Python 3.10+, stdlib + Pillow, **без сетевых обращений**.
Размеры и теги — `references/specifications.md`.

## Правила
1. **Ничего не загружать и не публиковать.** Скрипты пишут только в указанную папку. Копирование на
   сервер, правка шаблонов/чанков MODX и любых файлов живого сайта — только после явного
   подтверждения пользователя в этой сессии. Общий порядок изменений — навык `novaprom-website`.
2. Перед правкой шаблона или чанка — резервная копия (дубликат элемента или файл с датой), затем
   показать diff и спросить. После выкладки — проверка навыком `novaprom-website-qa`.
3. Pillow — только в venv. Никогда `--break-system-packages` и `sudo pip`.
4. Логотип не растягивать и не обрезать (скрипты вписывают его, "contain"). Русский текст — только
   шрифтом с кириллицей; без него скрипт останавливается с ошибкой, это правильно.
5. Каждую картинку открыть инструментом Read и посмотреть до показа пользователю.

## Установка (один раз, в папке проекта; `.venv` не коммитить)
```powershell
# Windows (PowerShell)
py -3 -m venv .venv
.venv\Scripts\python -m pip install "Pillow>=12,<13"
```
```bash
# Linux
python3 -m venv .venv && .venv/bin/python -m pip install "Pillow>=12,<13"
```
Запуск: активировать venv и вызывать `python ${CLAUDE_SKILL_DIR}/scripts/...`. Каждый вызов Bash в
Claude Code — новая оболочка, поэтому в одной команде: `source .venv/bin/activate && python ...`
(Git Bash на Windows: `source .venv/Scripts/activate && python ...`).

## Порядок работы
1. **Исходные данные** (спросить, если нет):
   - логотип PNG ≥ 512 px; для favicon лучше квадратный знак без надписи; SVG-версия, если есть;
   - светлый логотип на прозрачном фоне — для тёмного OG-фона;
   - заголовки OG по-русски, описание, URL страниц;
   - куда файлы лягут на сервере (например `/assets/favicon/`, `/assets/og/` — сверить с сайтом);
   - `Raleway-Bold.ttf` для OG. Если его нет локально — спросить: скрипты ничего не скачивают.
2. **Favicon, иконки, manifest:**
   ```bash
   python ${CLAUDE_SKILL_DIR}/scripts/generate_favicons.py logo-mark.png web-assets/icons all \
     --svg logo-mark.svg --app-bg "#FFFFFF" --theme-color "#1C1C1C" \
     --base-url /assets/favicon/ --validate
   ```
3. **Open Graph** (текст на фирменном фоне или логотип):
   ```bash
   python ${CLAUDE_SKILL_DIR}/scripts/generate_og_images.py web-assets/og \
     --text "Фильтры-сепараторы газа" --logo logo-white.png --accent "#FDB913" \
     --font fonts/Raleway-Bold.ttf --base-url https://novaprom.ru/assets/og/ \
     --description "Описание страницы" --page-url https://novaprom.ru/... --jpeg --validate
   python ${CLAUDE_SKILL_DIR}/scripts/generate_og_images.py web-assets/og-logo --image logo.png --bg "#FFFFFF"
   ```
4. **Проверка:** `python ${CLAUDE_SKILL_DIR}/scripts/check_assets.py web-assets/icons web-assets/og --contrast "#FFFFFF" "#1C1C1C"`
   (код выхода 1 = есть ошибки). Подходит и для проверки чужих/существующих ассетов.
5. **Посмотреть** каждую картинку (Read), исправить и перегенерировать при необходимости.
6. **Отдать пользователю:** список файлов, напечатанные теги, план размещения в MODX. Выкладку
   делает пользователь или Claude — только после «да».

## Результаты и опции
- `generate_favicons.py SOURCE OUT [favicon|app|all]` → `favicon.ico` (16/32/48),
  `favicon-16x16/32x32/96x96.png`, `apple-touch-icon.png` (180, непрозрачный),
  `android-chrome-192x192.png`, `android-chrome-512x512.png`, `maskable-icon-512x512.png`
  (логотип в безопасной зоне), `site.webmanifest`, `icon.svg` (копия SVG как есть).
  - `--bg` фон favicon/android (по умолчанию прозрачный); `--app-bg` фон apple-touch/maskable (#FFFFFF);
  - `--padding 0..0.3` поля; прозрачные края исходника обрезаются автоматически;
  - `--name`, `--short-name` (≤ 12 символов), `--theme-color`, `--background-color`, `--no-manifest`.
- `generate_og_images.py OUT (--text T | --image F)` → `og-image` 1200×630, `twitter-image` 1200×675,
  `og-square` 1200×1200 в PNG + WebP (+ JPEG с `--jpeg`; теги тогда указывают на .jpg). Всегда RGB.
  - `--bg` #1C1C1C (по умолчанию) или #FFFFFF; `--text-color`; `--accent` полоса снизу;
  - `--font` TTF с кириллицей. По умолчанию: Windows — arialbd/segoeuib/arial/segoeui,
    Linux — DejaVu Sans / Liberation Sans;
  - `--fit cover` — только для фото; `--title`, `--description`, `--page-url`, `--alt`, `--platforms`.
- Общие: `--base-url` = `/assets/favicon/`, `https://novaprom.ru/assets/og/` или
  `[[++site_url]]assets/og/`; `--validate`. `og:image` обязан быть абсолютным https-URL.
- **SVG-исходник** растеризуется только при наличии `resvg` в PATH. Иначе — PNG 1024 px через навык
  `svg-icons` (`render_preview.py render logo.svg --sizes 1024`) или экспорт от дизайнера, затем
  `generate_favicons.py logo.png ... --svg logo.svg`.

## Интеграция в MODX Revolution
- **Где `<head>`:** шаблон (Элементы → Шаблоны) или общий чанк (Элементы → Чанки, например `[[$head]]`).
  Править один чанк, а не каждый шаблон. Статический элемент (static file) — правка файла с бэкапом.
- **Сначала** посмотреть исходный код страницы: какие иконки/OG уже выводятся (дополнения SEO,
  другие чанки) — не дублировать. На момент обзора: `/favicon.ico` давал 404, OG-картинка 250×120 и
  объявлена PNG при фактическом JPEG.
- **Бэкап:** дублировать чанк/шаблон (`head_backup_ГГГГ-ММ-ДД`) или сохранить содержимое в файл;
  показать diff; после сохранения — очистить кэш MODX (Управление → Очистить кэш).
- **Файлы:** `favicon.ico` дополнительно в корень сайта; остальные — в папку из `--base-url`;
  `site.webmanifest` рядом с иконками (пути в нём относительные).
- **OG по страницам:** TV `og_image` (тип «Изображение», назначить шаблонам) + поля ресурса:
  ```html
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="НОВАПРОМ">
  <meta property="og:locale" content="ru_RU">
  <meta property="og:title" content="[[*pagetitle:htmlent]]">
  <meta property="og:description" content="[[*description:htmlent]]">
  <meta property="og:url" content="[[~[[*id]]? &scheme=`full`]]">
  <meta property="og:image" content="[[++site_url]][[*og_image:default=`assets/og/og-image.png`]]">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  ```
  Значение TV — путь относительно источника файлов: проверить, что `[[++site_url]]` + путь даёт
  рабочий https-URL. Картинки для TV — тоже 1200×630 (генерировать скриптом по одной на страницу).

## Чек-лист проверки
- [ ] `check_assets.py` — 0 ошибок (реальные пиксели и форматы, ICO 16/32/48, manifest, SVG без скриптов).
- [ ] Каждая картинка открыта: логотип не растянут и не обрезан, читается в 16/32 px; русский текст
      без «квадратиков»; maskable — логотип в центре с полями; фон OG непрозрачный.
- [ ] `site.webmanifest`: валидный JSON (UTF-8), иконки рядом, цвета `#hex`, `short_name` ≤ 12.
- [ ] Теги: пути совпадают с размещением; `og:image`/`twitter:image` — абсолютные https;
      `og:image:type` = реальный формат; в `<head>` нет дублей.
- [ ] Вес OG-картинки < 1 МБ (иначе `--jpeg`).
- [ ] После выкладки (с согласия пользователя): `/favicon.ico` отвечает 200, `.webmanifest` отдаётся
      как `application/manifest+json`, превью в Telegram (@WebpageBot), VK, Facebook Sharing Debugger.

## Частые ошибки
- `Pillow is not installed` → создать venv (выше).
- `no TrueType font that can draw this text` → `--font путь/к/Raleway-Bold.ttf` (или Arial).
- `resvg CLI is not in PATH` → PNG-исходник + `--svg`.
- Кракозябры в PowerShell → `[Console]::OutputEncoding = [Text.Encoding]::UTF8` (скрипты пишут UTF-8).
