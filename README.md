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
powershell -ExecutionPolicy Bypass -File D:\Claude-code\scripts\setup-windows.ps1
```
Скрипт ставит навыки, субагентов, хук и правила и вливает настройки безопасности в `%USERPROFILE%\.claude\settings.json`
(с резервной копией). Дальше — шаги 3–9 раздела «Установка» в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Проверка
```
python scripts/validate_config.py
python -m unittest discover -s tests -p "test_*.py"
```

## Сторонние плагины
- **frontend-design** (официальный, Anthropic) и **novaprom-marketing** (этот репозиторий) — включены.
- **superpowers** (`obra/superpowers-marketplace`) и **impeccable** (`pbakaus/impeccable`) — выключены глобально,
  включаются только в проектах кода (сайт, скрипты) через `.claude/settings.local.json` проекта.
- **claude-mem**, **find-skills**, **task-observer** — удалены 2026-10-03 (причины — ARCHITECTURE.md, раздел 2).

## Источники вендоренного кода
- `web-assets` — alonw0/web-asset-generator (MIT), с исправлениями; `svg-icons` — tryopendata/skills svg-design (MIT);
  `plugins/novaprom-marketing` — coreyhaines31/marketingskills (MIT) и wondelai/skills (MIT).
  Подробности, коммиты и изменения — в `NOTICE.md` каждого навыка/плагина.
