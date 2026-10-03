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
- **Хук безопасности** `.claude/hooks/novaprom_guard.py` и предлагаемые настройки `docs/settings.proposed.json`.
- **Правила маршрутизации** MAIN AGENT — `global/NOVAPROM.md`.

## Установка на рабочем компьютере (Windows)
```
git clone https://github.com/usuevgpt-lang/Claude-code.git D:\Claude-code
powershell -ExecutionPolicy Bypass -File D:\Claude-code\scripts\setup-windows.ps1
```
Затем — шаги 3–7 раздела «Установка» в [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Проверка
```
python scripts/validate_config.py
python tests/test_skills.py
```

## Ранее подключённые плагины и навыки (ожидают решения — см. ARCHITECTURE.md, раздел 9)
- **claude-mem** (`thedotmack/claude-mem`), **superpowers** (`obra/superpowers-marketplace`),
  **impeccable** (`pbakaus/impeccable`) — подключаются через `.claude/settings.json`.
- **find-skills** (vercel-labs/skills) и **task-observer** (rebelytics/one-skill-to-rule-them-all, CC BY 4.0) —
  в `.claude/skills/`.

## Источники вендоренного кода
- `web-assets` — alonw0/web-asset-generator (MIT), с исправлениями; `svg-icons` — tryopendata/skills svg-design (MIT);
  `plugins/novaprom-marketing` — coreyhaines31/marketingskills (MIT) и wondelai/skills (MIT).
  Подробности, коммиты и изменения — в `NOTICE.md` каждого навыка/плагина.
