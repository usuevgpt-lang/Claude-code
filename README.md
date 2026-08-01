# Claude-code
Клод на айфоне 

## Установка на рабочем компьютере (Windows)

Чтобы скиллы и плагины работали на компьютере глобально — в любой папке, а не только в этом репозитории:

1. Склонируйте репозиторий, например на диск D:
   ```
   git clone https://github.com/usuevgpt-lang/Claude-code.git D:\Claude-code
   ```
   (если git не установлен — скачайте ZIP с GitHub: Code → Download ZIP, и распакуйте)
2. Запустите установочный скрипт в PowerShell:
   ```
   powershell -ExecutionPolicy Bypass -File D:\Claude-code\scripts\setup-windows.ps1
   ```
   Скрипт скопирует скиллы в `%USERPROFILE%\.claude\skills` и пропишет плагины в `%USERPROFILE%\.claude\settings.json` (существующие настройки сохраняются, делается резервная копия).
3. Перезапустите Claude Code. При первом запуске подтвердите доверие маркетплейсам — плагины установятся автоматически.

Вариант без скрипта: откройте Claude Code в любой папке и попросите: «склонируй usuevgpt-lang/Claude-code и запусти scripts/setup-windows.ps1» — Claude сделает всё сам.

## Плагины

Подключаются автоматически через `.claude/settings.json` — при первом запуске Claude Code в этом репозитории предложит установить их из указанных маркетплейсов.

- **claude-mem** — постоянная память для Claude Code (сжатие контекста между сессиями). Маркетплейс: `thedotmack/claude-mem`.
- **superpowers** — библиотека базовых скиллов от Jesse Vincent: TDD, отладка, паттерны совместной работы. Маркетплейс: `obra/superpowers-marketplace`.
- **impeccable** — дизайн-скилл от Paul Bakaus для фронтенда: аудит, критика и полировка интерфейсов, 23 команды (`/impeccable polish`, `/impeccable audit` и др.). Маркетплейс: `pbakaus/impeccable`.

## Скиллы

- **find-skills** (`.claude/skills/find-skills/`) — поиск и установка скиллов из открытой экосистемы agent skills (skills.sh). Источник: [vercel-labs/skills](https://github.com/vercel-labs/skills).
- **task-observer** (`.claude/skills/task-observer/`) — мета-скилл «One Skill to Rule Them All»: наблюдает за рабочими сессиями, фиксирует исправления и повторяющиеся паттерны и превращает их в улучшения скиллов. Источник: [rebelytics/one-skill-to-rule-them-all](https://github.com/rebelytics/one-skill-to-rule-them-all) (CC BY 4.0, автор Eoghan Henn).

## MCP-серверы

- **perplexity** (`.mcp.json`) — официальный MCP-сервер Perplexity (пакет `@perplexity-ai/mcp-server`), даёт Claude Code инструменты поиска и research в реальном времени через Perplexity API. Подключается автоматически, когда Claude Code открыт в этой папке — при первом запуске нужно будет подтвердить доверие серверу.

  Нужен ключ API с [console.perplexity.ai](https://console.perplexity.ai). Задайте его переменной окружения `PERPLEXITY_API_KEY` (в `.mcp.json` ключ не хранится, он подставляется из окружения):

  - Windows (PowerShell), сохранить навсегда для своего пользователя:
    ```
    [Environment]::SetEnvironmentVariable('PERPLEXITY_API_KEY', 'ваш_ключ', 'User')
    ```
    (перезапустите терминал/Claude Code, чтобы переменная подхватилась)
  - macOS/Linux: добавьте `export PERPLEXITY_API_KEY=ваш_ключ` в `~/.zshrc` или `~/.bashrc`.

  Чтобы Perplexity был доступен не только в этом репозитории, а в любой папке, зарегистрируйте сервер на уровне пользователя:
  ```
  claude mcp add --scope user perplexity --env PERPLEXITY_API_KEY="ваш_ключ" -- npx -y @perplexity-ai/mcp-server
  ```

- **glif** (`.mcp.json`) — MCP-сервер платформы [glif.app](https://glif.app): запуск AI-воркфлоу (глифов) с произвольными входными данными, поиск готовых глифов и агентов. Подключается через официальный хостинг Glif (`https://glif.app/api/mcp`) — ключ API не нужен, при первом обращении Claude Code откроет браузер для входа в аккаунт Glif (OAuth).

  Чтобы glif был доступен в любой папке, а не только в этом репозитории:
  ```
  claude mcp add --scope user --transport http glif "https://glif.app/api/mcp"
  ```
