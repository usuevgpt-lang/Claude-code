# Claude-code — рабочая среда НОВАПРОМ

Конфигурация Claude Code для инженерной, конструкторской, нормативной, коммерческой, исследовательской,
дизайнерской и IT-работы ООО НПФ «НОВАПРОМ».

**Полное описание архитектуры, реестр навыков и субагентов, безопасность и инструкция — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).**

> Репозиторий публичный: здесь только навыки, скрипты и шаблоны. Документы заказчиков, цены, чертежи и
> учётные данные сюда не добавлять.

## Состав
- **Инженерные навыки** `novaprom-*` со скриптами расчётов (Python): сосуды под давлением (ГОСТ 34233),
  трубопроводы, газодинамика (Z тремя методами, Джоуль–Томсон, Kv), фильтры-сепараторы, теплообменники,
  ПГБ/БПГ, камеры СОД, затворы, материалы, CAD (DXF, развёртки), независимая проверка расчётов.
- **Документы и коммерция**: нормативная проверка, Транснефть (gap-анализ ОТТ), ТУ/ПМИ/паспорт/РЭ,
  себестоимость (Excel с формулами), КП/ТКП, презентации, закупки, литература и патенты, deep research.
- **Web/IT**: сайт novaprom.ru (MODX), QA сайта, explain-code, иконки (NOVAPROM ICON DESIGN SYSTEM), SVG,
  web-assets, аудит Bitrix24 (только чтение), проверка сторонних инструментов.
- **18 субагентов** (`.claude/agents/`) + 2 маркетинговых в плагине `novaprom-marketing` (`plugins/`).
- **Хук безопасности** `.claude/hooks/novaprom_guard.py`, правила разрешений и отключение телеметрии —
  в `.claude/settings.json`; эталон для ПК — `docs/settings.proposed.json` (его вливает установочный скрипт).
- **Правила маршрутизации** MAIN AGENT — `global/NOVAPROM.md`.

## Установка на рабочем компьютере (Windows)
```
git clone https://github.com/usuevgpt-lang/Claude-code.git D:\Claude-code
D:\Claude-code\scripts\install-windows.cmd
```
Нужны Python 3.11+ (с «Add python.exe to PATH») и желательно Node.js LTS. `install-windows.cmd` (можно двойным
щелчком) обновляет клон, ставит навыки, субагентов, хук и правила в `%USERPROFILE%\.claude` — после этого они
действуют **во всех проектах** — и вливает настройки в `%USERPROFILE%\.claude\settings.json` (с резервными копиями);
в конце печатает проверку. Повторный запуск обновляет установку; `install-windows.cmd -Check` — только проверка.
Плагины ставятся сами при запуске Claude Code; навыки claude.ai (docx, xlsx, pptx, pdf, lead-triage…) приходят из
аккаунта Claude. macOS/Linux и облачные среды: `python3 scripts/install_novaprom.py`. Подробно — раздел 7
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Проверка
```
python scripts/validate_config.py
python -m unittest discover -s tests -p "test_*.py"
```

## Сторонние плагины
- **frontend-design** и **claude-code-setup** (официальные, Anthropic) и **novaprom-marketing** (этот репозиторий) — включены.
- **agent-skills** (`addyosmani/agent-skills` 0.6.12, MIT; через маркетплейс `novaprom`, закреплён на коммите `a06bc63`) —
  процесс разработки кода (spec → plan → build → test → review → ship); выключен глобально, включается в проектах кода.
- **superpowers** (`obra/superpowers-marketplace`) и **impeccable** (`pbakaus/impeccable`) — выключены глобально,
  включаются только в проектах кода (сайт, скрипты) через `.claude/settings.local.json` проекта.
- **claude-mem** (`thedotmack/claude-mem`, закреплён на v13.28.0) — включён, телеметрия выключена, скрытие секретов
  включено; папки с документами заказчиков рекомендуется исключить (ARCHITECTURE.md, раздел 7).
- **find-skills** (vercel-labs/skills, MIT) — восстановлен с правками безопасности: CLI `skills@1.7.0`, без телеметрии,
  установка только в проект и после проверки `novaprom-tool-vetting` (см. его `NOTICE.md`).
- **task-observer** — удалён 2026-10-03 (причины — ARCHITECTURE.md, раздел 2).

## Источники вендоренного кода
- `web-assets` — alonw0/web-asset-generator (MIT), с исправлениями; `svg-icons` — tryopendata/skills svg-design (MIT);
  `anydoc` — firecrawl/anydoc (MIT), CLI закреплён на 0.2.4, без облачного OCR;
  `plugins/novaprom-marketing` — coreyhaines31/marketingskills (MIT) и wondelai/skills (MIT).
  Подробности, коммиты и изменения — в `NOTICE.md` каждого навыка/плагина.
