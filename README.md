# Claude-code
Клод на айфоне 

## Плагины

Подключаются автоматически через `.claude/settings.json` — при первом запуске Claude Code в этом репозитории предложит установить их из указанных маркетплейсов.

- **claude-mem** — постоянная память для Claude Code (сжатие контекста между сессиями). Маркетплейс: `thedotmack/claude-mem`.
- **superpowers** — библиотека базовых скиллов от Jesse Vincent: TDD, отладка, паттерны совместной работы. Маркетплейс: `obra/superpowers-marketplace`.
- **impeccable** — дизайн-скилл от Paul Bakaus для фронтенда: аудит, критика и полировка интерфейсов, 23 команды (`/impeccable polish`, `/impeccable audit` и др.). Маркетплейс: `pbakaus/impeccable`.

## Скиллы

- **find-skills** (`.claude/skills/find-skills/`) — поиск и установка скиллов из открытой экосистемы agent skills (skills.sh). Источник: [vercel-labs/skills](https://github.com/vercel-labs/skills).
- **task-observer** (`.claude/skills/task-observer/`) — мета-скилл «One Skill to Rule Them All»: наблюдает за рабочими сессиями, фиксирует исправления и повторяющиеся паттерны и превращает их в улучшения скиллов. Источник: [rebelytics/one-skill-to-rule-them-all](https://github.com/rebelytics/one-skill-to-rule-them-all) (CC BY 4.0, автор Eoghan Henn).
