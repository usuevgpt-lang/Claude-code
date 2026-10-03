# Репозиторий конфигурации Claude Code НОВАПРОМ

Правила рабочей среды (маршрутизация задач, безопасность) — @global/NOVAPROM.md

## Что в репозитории
- `.claude/skills/` — навыки (инженерные `novaprom-*`, `deep-research`, `explain-code`, `svg-icons`, `web-assets`, …).
- `.claude/agents/` — субагенты.
- `.claude/hooks/novaprom_guard.py` — хук безопасности (PreToolUse).
- `plugins/novaprom-marketing/` + `.claude-plugin/marketplace.json` — локальный маркетплейс `novaprom` с плагином маркетинга.
- `global/NOVAPROM.md` — правила MAIN AGENT, устанавливаются на уровень пользователя.
- `.claude/settings.json` — хук, правила разрешений, плагины этого репозитория; `docs/settings.proposed.json` — эталон
  тех же настроек для уровня пользователя (вливает `scripts/merge_settings.py`, держать синхронными).
- `docs/ARCHITECTURE.md` — описание архитектуры и инструкция.
- `scripts/install_novaprom.py` — установка на уровень пользователя (Windows/macOS/Linux/облако), на Windows —
  `scripts/install-windows.cmd` → `scripts/setup-windows.ps1`; `scripts/merge_settings.py` — слияние настроек;
  `scripts/validate_config.py` — проверка конфигурации.
- `tests/` — тесты расчётных скриптов и хука.

## Правила для этого репозитория
- Репозиторий **публичный**: никаких документов заказчиков, цен, себестоимости, чертежей, токенов, паролей,
  персональных данных. Только навыки, скрипты, шаблоны.
- Перед коммитом: `python scripts/validate_config.py` (нужен PyYAML) и `python -m unittest discover -s tests -p "test_*.py"`
  (расчёты, хук, слияние настроек, установщик, CAD/смета/теплообмен) + `python .claude/skills/svg-icons/scripts/test_check_svg.py`.
- Сторонний код вендорится только с `NOTICE.md` (источник, коммит, лицензия, изменения) после `novaprom-tool-vetting`.
- Описание навыка — блочным скаляром YAML (`description: >-`), не начинать значение с кавычки.
- Общий модуль отчётов `_calcreport.py` одинаков во всех инженерных навыках; эталон —
  `.claude/skills/novaprom-pressure-vessels/scripts/_calcreport.py` (проверяется валидатором).
