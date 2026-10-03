# Рабочая среда Claude Code НОВАПРОМ — архитектура и инструкция

Версия: 2026-10-03. Репозиторий: `usuevgpt-lang/Claude-code` (**публичный** — см. раздел 8).

## 1. Архитектура

```
                          ┌───────────────────────────────────────────────┐
  Пользователь  ───────►  │ MAIN AGENT (основная сессия Claude Code)      │
                          │ правила и маршрутизация: global/NOVAPROM.md    │
                          │ хук безопасности: novaprom_guard.py            │
                          └───────┬───────────────────────────────────────┘
          ┌───────────────────────┼──────────────────────────────┬──────────────────────────┐
          ▼                       ▼                              ▼                          ▼
  ИНЖЕНЕРИЯ                 ДОКУМЕНТЫ И НОРМАТИВЫ          КОММЕРЦИЯ И ИССЛЕДОВАНИЯ     WEB / IT
  pressure-vessel-engineer  standards-compliance           cost-estimator               web-developer
  mechanical-design-eng.    transneft-specialist (offline) procurement-researcher       ui-designer
  gas-process-engineer      technical-writer               research-worker ×N           website-qa
  filtration-specialist     presentation-designer          (lead = MAIN, deep-research) bitrix-auditor (read-only)
  heat-exchanger-specialist                                                             seo-specialist*
  cad-specialist                                                                        marketing-strategist*
  engineering-reviewer (независимая проверка)
          │                       │                              │                          │
          ▼                       ▼                              ▼                          ▼
  SKILLS: novaprom-* расчётные навыки со скриптами; normative-check, transneft, tech-docs, cost-estimation,
          commercial-proposal, deep-research, literature-search, procurement, cad, website, website-qa,
          bitrix-audit, explain-code, svg-icons, equipment-icons, web-assets, tool-vetting; плагин novaprom-marketing*
          │
          ▼
  MCP / PLUGINS / TOOLS: Python (CoolProp, ezdxf, openpyxl, Pillow), docx/xlsx/pptx/pdf (аккаунт claude.ai),
          frontend-design (официальный плагин Anthropic), Lighthouse / linkinator / chrome-devtools-mcp (QA),
          b24_readonly.py (Bitrix24 REST, только чтение), Gmail / Drive / Calendar / Lucid / Canva / Gamma (коннекторы)
  * — из локального плагина novaprom-marketing
```

**Как выбирается навык/субагент.** Claude видит названия и описания всех навыков и субагентов и выбирает по
смыслу запроса (описания написаны на русском и английском, с типовыми фразами в `when_to_use`). Дополнительно
`global/NOVAPROM.md` содержит явную таблицу маршрутизации «задача → навык → субагент». Субагенты получают свои
навыки заранее (поле `skills:`), инструменты ограничены полем `tools:`. Явный вызов: «@pressure-vessel-engineer …»
или «используй навык novaprom-gas-hydraulics».

**Сложная инженерная задача** (навык `novaprom-engineering-review`):
MAIN → инженерные субагенты (параллельно) → независимый пересчёт `engineering-reviewer` (получает только постановку,
считает другим методом) → сверка → таблица противоречий → итог на утверждение пользователю.

**Deep Research**: ведущий — основная сессия (только она может задавать вопросы в 4 контрольных точках:
бриф, план, покрытие и противоречия, черновик), исполнители — `research-worker` (только WebSearch/WebFetch/Read).

## 2. Аудит исходной среды (до изменений)

| Компонент | Где | Источник / версия | Состояние | Безопасность и актуальность | Дубли | Рекомендация |
|---|---|---|---|---|---|---|
| claude-mem | плагин (settings.json) | thedotmack/claude-mem v13.28.0, Apache-2.0 | **включён** по решению владельца (2026-10-03), закреплён на v13.28.0 | Хук на **каждый** вызов инструмента сохраняет полный вход/выход в `~/.claude-mem/claude-mem.db` без срока хранения (риск для документов заказчиков, паролей); фоновые вызовы модели на вашей подписке; локальный сервер 127.0.0.1:37777; телеметрия PostHog по умолчанию; `bun install` 26 пакетов при запуске | встроенная авто-память Claude Code | Включён с мерами защиты: телеметрия и отправка ошибок выключены, автоматическое скрытие секретов включено, версия закреплена; папки с документами заказчиков — исключить через `CLAUDE_MEM_EXCLUDED_PROJECTS` (раздел 7) |
| superpowers | плагин | obra/superpowers v6.4.2, MIT | выключен глобально, включается в проектах кода | Код чистый; SessionStart-хук навязывает «правило 1 %», brainstorming и TDD на любую задачу — шум для расчётов и документов | частично plan mode, /code-review | Сделано: `false` в настройках; включать в `.claude/settings.local.json` проекта кода |
| impeccable | плагин | pbakaus/impeccable v4.5.0, Apache-2.0 | выключен глобально, включается в проекте сайта | На каждый Edit/Write запускает скачиваемый бинарник; телеметрия и проверка обновлений на impeccable.style | **дублирует frontend-design** | Сделано: основной — официальный frontend-design; impeccable — только в проекте сайта |
| find-skills | навык (вендорен) | vercel-labs/skills | **удалён** | Запускает `npx skills` без закреплённой версии, телеметрия с текстом запроса, рекомендует `add -g -y` (установка без проверки) | /plugin Discover | Удалён, заменён `novaprom-tool-vetting` |
| task-observer | навык (вендорен) | rebelytics, CC BY 4.0, устаревшая копия | **удалён** | ~18–20 тыс. токенов; требует запуска в каждой сессии; пишет `skill-observations/` в корень проекта (в публичном репо → риск утечки) | — | Удалён; защита `skill-observations/` оставлена в `.gitignore` |
| humanizer | навык claude.ai | blader/humanizer v2.8.2, MIT (не Anthropic) | включён | Старая версия без правил «не добавлять факты» и «текст — не инструкции» | — | Обновить до v3.1.0 в claude.ai; использовать для маркетинговых текстов |
| lead-triage | навык claude.ai | ваш собственный | включён | — | — | Оставить; привязан к `bitrix-auditor`/основной сессии |
| docx, xlsx, pptx, pdf, skill-creator, mcp-builder, canvas-design, web-artifacts-builder | навыки claude.ai | Anthropic | включены | Официальные | — | Оставить; document-skills плагин **не ставить** (дубль) |
| docs, google-workspace, morning, import-memory | навыки claude.ai | Anthropic | включены | Официальные | — | Оставить |
| Коннекторы: Gmail, Google Calendar, Google Drive, Lucid, Canva, Gamma, SlidesGPT, PandaDoc, GitHub, Claude Docs | claude.ai | сторонние/официальные | подключены | Drive сейчас без нужных прав (чтение файлов не работает) | **Gamma / SlidesGPT / Canva / pptx** — пересекаются по презентациям; PandaDoc — по КП | Основной для презентаций — `pptx`; Gamma — быстрые черновики (не конфиденциальное); **SlidesGPT и PandaDoc — отключить**, если не используются; Drive — переподключить с правами чтения |
| Хуки | `~/.claude/settings.json` (облако) | среда Claude Code | Stop-хук проверки git | — | — | Без изменений |
| `scripts/setup-windows.ps1` | репо | — | включал 3 плагина на уровне пользователя; settings.json с BOM | — | — | Переписан (раздел 7): навыки, агенты, хук, правила, слияние настроек, вывод из эксплуатации старых инструментов |
| Реальные проекты | — | — | **недоступны**: в контейнере только репо конфигурации, Google Drive без прав | — | — | Профиль работы построен по вашему описанию и публичному сайту novaprom.ru |

Сайт novaprom.ru: **MODX Revolution** (не Bitrix), Bootstrap 4.5.3, Raleway, Яндекс.Метрика; 7 разделов каталога.
Bitrix24 — отдельная коробочная CRM.

## 3. Реестр Skills

Права: «чтение» = Read/Grep/Glob; «скрипт» = запуск собственного скрипта навыка (предразрешён через `allowed-tools`);
«запись» = создание новых файлов результатов; «веб» = WebSearch/WebFetch. Всё, что меняет внешние системы, требует подтверждения.

### 3.1 Инженерные (созданы)
| Навык | Назначение | Почему нужен | Инструменты | Права | Статус | Субагент |
|---|---|---|---|---|---|---|
| `novaprom-pressure-vessels` | Прочность сосудов по ГОСТ 34233.1/.2/.3: обечайки, днища, конусы, плоские крышки, наружное давление, укрепление отверстий, пробное давление, масса | Основной расчёт корпусов фильтров, сепараторов, КПР, ресиверов | `vessel_calc.py` (Python, stdlib) | чтение, скрипт, запись | создан, тесты | pressure-vessel-engineer |
| `novaprom-piping` | Толщины труб (ГОСТ 32388, СП 36.13330, ASME B31.3), отводы, гидравлика жидкостей, подбор арматуры | Обвязка, патрубки, КПР | `pipe_calc.py` | чтение, скрипт, запись | создан, тесты | gas-process-engineer, pressure-vessel-engineer |
| `novaprom-gas-hydraulics` | Ст./норм./рабочие м³, Z (3 метода: СТО Газпром, Papay, CoolProp/GERG), плотность, скорость, DN, ΔP, Джоуль–Томсон, подогрев, Kv | Основа всех газовых расчётов | `gas_calc.py`; CoolProp (опц.) | чтение, скрипт, запись | создан, тесты | gas-process-engineer |
| `novaprom-gas-filtration` | Фильтры, фильтры-сепараторы, коалесцеры, циклоны: Саудерс–Браун, элементы, ΔP, патрубки, Lapple | Основная продуктовая линия | `filter_calc.py`, шаблон ОЛ | чтение, скрипт, запись | создан, тесты | filtration-specialist |
| `novaprom-heat-exchangers` | Тепловой баланс, LMTD/F, U, площадь, пучок, реализуемость | Новая линия «Теплообменное оборудование», подогрев газа | `hx_calc.py` | чтение, скрипт, запись | создан, тесты | heat-exchanger-specialist |
| `novaprom-gas-reduction` | ПГБ/ГРП/БПГ/БПТГ: схема, линии, регуляторы, ПЗК/ПСК, подогрев, учёт, КИПиА | Блоки подготовки и редуцирования газа | чек-листы + `gas_calc.py` | чтение, запись | создан | gas-process-engineer |
| `novaprom-pig-launchers` | Камеры запуска/приёма СОД (КПР-НП): конструкция, патрубки, затворы, опоры, расчёты | Ключевая продукция, требования Транснефти | чек-листы + скрипты сосудов/труб | чтение, запись | создан | mechanical-design-engineer |
| `novaprom-valves-closures` | Затворы ЗК-НП: байонетные, хомутовые, вставные, с кольцом; усилия, срез/изгиб/смятие, блокировки | Собственная линейка затворов | `closure_calc.py` | чтение, скрипт, запись | создан, тесты | mechanical-design-engineer |
| `novaprom-materials` | Подбор сталей по t, среде (H2S), ударной вязкости, замена марок, сертификаты | Подбор материалов | карта документов | чтение | создан | mechanical-design-engineer, pressure-vessel-engineer |
| `novaprom-engineering-review` | Протокол многоагентной проверки и таблица противоречий | Независимая проверка перед выдачей заказчику | — | чтение, запись | создан | engineering-reviewer |
| `novaprom-cad` | DXF-анализ (ezdxf), развёртки (конус, косой срез, отвод, врезка), DWG→DXF, STEP, спецификации ГОСТ 2.106, SolidWorks API | Чертежи, развёртки, ведомости | `dxf_inspect.py`, `unfold.py`; ezdxf | чтение, скрипт, запись; SolidWorks — **только с разрешения** | создан, тесты | cad-specialist |

Принципы расчётных навыков: каждое входное число — с источником (`{"value":…, "source":…}`), иначе в отчёте
предупреждение; встроенных табличных коэффициентов нет; справочные значения вынесены в реестры «на сверку»
(`references/coefficients-register.md`) со статусом «не сверено» до вашей проверки по тексту стандарта.

### 3.2 Нормативные, документы, коммерция (созданы)
| Навык | Назначение | Почему нужен | Инструменты | Права | Статус | Субагент |
|---|---|---|---|---|---|---|
| `novaprom-normative-check` | Ссылки с редакциями и пунктами, актуальность, обязательное/рекомендация, противоречия, матрицы | Проверка ТУ, ПМИ, паспортов, ОЛ | веб (официальные источники) | чтение, веб, запись | создан | standards-compliance |
| `novaprom-transneft` | Gap-анализ ОТТ → ТУ/ПМИ, замечания, аккредитация | Работа с Транснефтью | — (офлайн) | чтение, запись; **без веба** | создан | transneft-specialist |
| `novaprom-tech-docs` | ТУ, ПМИ, паспорт, РЭ, отчёты, ОЛ — структуры и правила | Документация на изделия | `docx`, `xlsx`, `pdf` | чтение, запись | создан | technical-writer |
| `novaprom-cost-estimation` | Себестоимость: РАСЧЁТНЫЕ / РЫНОЧНЫЕ / ДОПУЩЕНИЯ / НЕОПРЕДЕЛЁННОСТЬ, Excel с формулами | Калькуляции, сравнение вариантов | `cost_calc.py`, openpyxl | чтение, скрипт, запись | создан, тесты | cost-estimator |
| `novaprom-commercial-proposal` | КП/ТКП, понятные заказчику | Коммерческие предложения | `docx`, `pdf` | чтение, запись | создан | technical-writer, cost-estimator |
| `novaprom-presentation-style` | Промышленный стиль презентаций, сетка, поштучная проверка слайдов | Технические презентации | `pptx` | чтение, запись | создан | presentation-designer |
| `novaprom-procurement-research` | Производители, комплектующие, цены, проверка поставщиков | Закупки | веб | веб, запись | создан | procurement-researcher |
| `novaprom-literature-search` | Статьи (Crossref, OpenAlex, CORE, arXiv, КиберЛенинка), патенты (Роспатент, Espacenet), стандарты | Научный и патентный поиск | веб | веб | создан | research-worker, standards-compliance |
| `deep-research` | Исследование с 4 контрольными точками человека, реестром источников и анализом противоречий | Рынок, технологии, конкуренты | субагенты `research-worker` | веб, запись в `research/` | создан (идеи Anthropic и MIT-проектов, см. NOTICE) | основная сессия + research-worker |
| `novaprom-tool-vetting` | 12-шаговая проверка стороннего Skill/Plugin/MCP/пакета | Безопасная установка | — | чтение, веб | создан | основная сессия |

### 3.3 Web / IT (созданы и вендорены)
| Навык | Назначение | Источник | Инструменты | Права | Статус | Субагент |
|---|---|---|---|---|---|---|
| `novaprom-website` | Факты о сайте (MODX), порядок изменений: копия → diff → подтверждение → QA | создан | — | чтение | создан | web-developer, ui-designer |
| `novaprom-website-qa` | QA после изменений: адаптивность, ссылки, формы, JS, a11y, производительность, SEO | создан | chrome-devtools-mcp, Lighthouse, linkinator, W3C Nu | чтение; npx — с подтверждением | создан | website-qa |
| `explain-code` | Объяснение кода (MODX, Bitrix, PHP/JS): карта, поток, зависимости, проблемы; только чтение | создан по примеру из документации Claude Code + legacy-analyst (Apache-2.0) | — | только чтение (`disallowed-tools: Edit Write`) | создан | web-developer, bitrix-auditor |
| `novaprom-bitrix-audit` | Аудит Bitrix24 только чтение; белый список методов, без `batch` | создан | `b24_readonly.py` | чтение, скрипт; **изменения запрещены** | создан, тесты | bitrix-auditor |
| `novaprom-equipment-icons` | NOVAPROM ICON DESIGN SYSTEM (замеры иконок сайта), процесс создания новых иконок | создан по замерам 14 иконок сайта | проверка стиля, рендер | чтение, запись | создан | ui-designer, presentation-designer |
| `svg-icons` | SVG: проверка безопасности, рендер в реальном размере, SVGO 4, экспорт PNG/WebP | вендорен из tryopendata/skills svg-design (MIT) + собственные скрипты | resvg/cairosvg, Pillow, SVGO (с подтверждением) | чтение, запись | вендорен с изменениями | ui-designer |
| `web-assets` | Favicon (ICO 16/32/48), app icons, webmanifest, Open Graph с кириллицей, WebP | вендорен из alonw0/web-asset-generator (MIT) с исправлениями | Pillow | чтение, скрипт, запись | вендорен с изменениями, тесты 40/40 | ui-designer |
| `frontend-design` | Дизайн интерфейсов (официальный) | anthropics/claude-plugins-official, Apache-2.0 | — | — | **включить** плагином (раздел 7) | web-developer, ui-designer |

### 3.4 Маркетинг — локальный плагин `novaprom-marketing` (вендорен)
Источник: coreyhaines31/marketingskills @ dda3841f (MIT) — выбрано 15 из 50; `tools/` (64 CLI для западных SaaS)
не взяты. Адаптация для российского B2B (Яндекс, тендеры, 152-ФЗ/38-ФЗ — с пометкой «требует подтверждения
юристом», инженеры как читатели, граница с инженерией) — в `product-marketing/references/ru-b2b-industrial-overlay.md`.

| Навык | Назначение | Субагент |
|---|---|---|
| product-marketing | Контекст продукта (читается всеми маркетинговыми навыками) | marketing-strategist |
| seo-audit, ai-seo, schema, site-architecture, programmatic-seo | Техническое SEO, AI-поиск, schema.org, структура каталога, страницы DN/PN | seo-specialist |
| content-strategy, copywriting, copy-editing | Контент и тексты без переспама | seo-specialist / marketing-strategist |
| cro, analytics | Конверсия форм и опросных листов, Яндекс.Метрика | seo-specialist |
| competitors, competitor-profiling, customer-research, sales-enablement | Конкуренты, исследования клиентов, материалы продаж | marketing-strategist |
| jtbd-industrial | JTBD для промышленного B2B (основа wondelai/skills, MIT) | marketing-strategist |

Отклонены (с причинами в отчёте исследования): pricing, free-tools (конфликт с инженерными/сметными навыками),
social, ads, cold-email, prospecting (платформы и право РФ), ab-testing (мало трафика) и др.

### 3.5 Существующие навыки
| Навык | Источник | Субагент | Решение |
|---|---|---|---|
| lead-triage | ваш (claude.ai) | основная сессия / bitrix-auditor | оставить |
| docx, xlsx, pptx, pdf | Anthropic (claude.ai) | technical-writer, cost-estimator, presentation-designer | оставить |
| humanizer | blader/humanizer (claude.ai) | marketing-strategist | обновить |
| find-skills, task-observer | вендорены ранее | — | **удалены** (2026-10-03) |

## 4. Субагенты (`.claude/agents/`, плагин — `plugins/novaprom-marketing/agents/`)
| Субагент | Специализация | Навыки (предзагружены) | Инструменты | Модель | Критерий качества |
|---|---|---|---|---|---|
| pressure-vessel-engineer | Прочность по ГОСТ 34233 | pressure-vessels, materials, engineering-review | Read, Grep, Glob, Bash, Write, Skill | inherit | каждое число с источником, проверки применимости |
| mechanical-design-engineer | Конструкция, КПР, затворы, комплектующие | pig-launchers, valves-closures, materials, piping | + WebSearch/WebFetch | inherit | варианты с рисками, требования со ссылками |
| gas-process-engineer | Газодинамика, ПГБ/БПГ | gas-hydraulics, gas-reduction, piping | + веб | inherit | база расхода и тип давления явно; режимы min/max |
| filtration-specialist | Фильтры/сепараторы | gas-filtration, gas-hydraulics | + веб | inherit | данные элементов с источником; ΔP чистый/загрязнённый |
| heat-exchanger-specialist | Теплообменники | heat-exchangers, gas-hydraulics | + веб | inherit | реализуемость проверена |
| engineering-reviewer | Независимая проверка | engineering-review, pressure-vessels, gas-hydraulics, piping | без Edit и Agent | inherit | другой метод; таблица противоречий |
| cad-specialist | DXF/DWG/STEP/SolidWorks | cad, materials | Read, Grep, Glob, Bash, Write, Skill | inherit | выводы подтверждены данными файла, предпросмотр |
| standards-compliance | Нормативы, соответствие | normative-check, tech-docs, literature-search | + веб | inherit | редакции и пункты; статус с датой |
| transneft-specialist | ОТТ Транснефти | transneft, normative-check, tech-docs | **без веба** | inherit | gap-таблица с приоритетами |
| technical-writer | ТУ, ПМИ, паспорт, РЭ, КП | tech-docs, commercial-proposal | + Edit | inherit | обязательные разделы, ни одного числа без источника |
| cost-estimator | Себестоимость | cost-estimation, commercial-proposal | + Edit | inherit | разделение данных, диапазон |
| procurement-researcher | Закупки | procurement-research, literature-search | WebSearch, WebFetch, Read, Write, Skill | sonnet | цены с датой и условиями |
| presentation-designer | Презентации | presentation-style, equipment-icons | + Edit | inherit | 0 наложений, проверен каждый слайд |
| web-developer | Код сайта | website, explain-code | + Edit, WebFetch | inherit | минимальный diff, QA после |
| ui-designer | UI/UX, иконки, web-assets | equipment-icons, svg-icons, website | + Edit | inherit | читаемость в реальном размере |
| website-qa | QA сайта | website-qa, website | всё, кроме Edit | sonnet | вердикт «выпускать/нет» |
| bitrix-auditor | Bitrix24 только чтение | bitrix-audit, explain-code | без Edit, веба, Agent; **свой хук: сеть, SSH, БД, PHP запрещены** | inherit | находки с доказательствами, без изменений системы |
| research-worker | Исполнитель исследований | — | WebSearch, WebFetch, Read | sonnet | пакет доказательств с цитатами |
| seo-specialist* | SEO | плагин | без Bash | sonnet | без переспама, техническая точность |
| marketing-strategist* | Позиционирование, JTBD | плагин | без Bash | sonnet | доказательства vs гипотезы |

«Research Coordinator» отдельным субагентом не создан: координировать исследование и задавать вопросы
пользователю в контрольных точках может только основная сессия (у субагентов нет AskUserQuestion).
Из 20 предложенных ролей «Hydraulic Engineer» объединён с gas-process-engineer, «SVG/Icon Designer» — с ui-designer.

## 5. MCP, плагины и внешние инструменты

| Инструмент | Назначение | Источник / лицензия | Вердикт | Требует разрешения |
|---|---|---|---|---|
| frontend-design | Дизайн интерфейсов | anthropics/claude-plugins-official, Apache-2.0 | **установить** | установка |
| novaprom-marketing | Маркетинг/SEO | этот репозиторий (локальный маркетплейс `novaprom`) | установить (в проектах сайта/маркетинга) | установка |
| Bitrix24 DEV MCP (документация) | Справка по REST API | официальный Bitrix24, `https://mcp-dev.bitrix24.tech/mcp`, без доступа к данным | рекомендовано | подключение |
| chrome-devtools-mcp 1.10.1 | QA: консоль, сеть, трассы, Lighthouse | Google, Apache-2.0; флаги `--isolated --no-usage-statistics --no-performance-crux` | рекомендовано | подключение; управляет браузером |
| Playwright MCP 0.0.83 | Сценарии форм, кросс-браузер | Microsoft, Apache-2.0 | опционально | подключение |
| Lighthouse 13.5.0, linkinator 8.1.0, W3C Nu | QA сайта | Google / MIT / W3C | использовать через npx/curl | запуск npx |
| CoolProp 8.0.0 | Свойства газа (GERG-2008-подобная модель смесей) | MIT | установить в venv | установка |
| ezdxf 1.4.4, matplotlib | DXF | MIT / PSF | установить в venv | установка |
| ODA File Converter | DWG→DXF | бесплатный, проприетарный EULA | по необходимости | установка, запуск |
| build123d 0.13.0 | STEP/3D | Apache-2.0 | по необходимости | установка |
| pywin32 + SolidWorks COM | Выгрузка свойств/BOM/экспорт из SolidWorks | собственные read-only скрипты | по необходимости | **каждый запуск** |
| SolidWorks MCP (сторонние) | — | — | **не устанавливать**: `CaptureGrubEnchant/SolidWorks` — **вредоносный** (`irm … \| iex`); остальные незрелые; `limuzi013/solidworks-mcp` — только для испытаний в песочнице | — |
| FreeCAD MCP | — | neka-nat, MIT; `execute_code` без аутентификации | не устанавливать на рабочий ПК | — |
| Сторонние Bitrix24 MCP | — | слишком широкие права на запись | отклонены | — |
| Claude in Chrome | Проверка сайта в реальном браузере | Anthropic | только в отдельном профиле браузера, без админ-сессий | включение |
| Gamma / Canva / SlidesGPT / PandaDoc | Генерация презентаций/документов | сторонние сервисы | Gamma/Canva — по запросу, без конфиденциального; SlidesGPT, PandaDoc — отключить, если не используются | — |

## 6. Безопасность

1. **Хук `novaprom_guard.py`** (PreToolUse): запрещает `curl … | sh`, `irm … | iex`; требует подтверждения для
   рекурсивного удаления, force-push, `git reset --hard`, SSH/SCP/rsync, изменяющих SQL, обращений к `/rest/` Bitrix24
   в обход read-only клиента, POST/PUT/DELETE-запросов, установки пакетов (pip/npm/npx/winget), подключения MCP/плагинов,
   автоматизации SolidWorks и конвертеров, доступа к файлам секретов, записи в защищённые папки, отправки/удаления/
   публикации и создания через MCP (Gmail, Drive, GitHub, Gamma, Canva, SlidesGPT, PandaDoc…); операции чтения MCP
   проходят без вопросов. Подтверждение запрашивается даже в auto mode. Хук «закрыт при сбое»: если вход не
   разобран или проверка упала, он просит подтверждение; читает stdin и список путей в UTF-8/UTF-16/cp1251,
   поэтому работает на русской Windows. 79 сценариев (опасные/безопасные команды, режим Bitrix24, кодировки)
   покрыты тестами `tests/test_guard.py`. Для работы хука нужен `python` в PATH (не заглушка Microsoft Store).
2. **Профиль `bitrix-readonly`** у субагента bitrix-auditor: сеть, SSH, БД и PHP — запрещены, REST — только через
   `b24_readonly.py` (белый список методов чтения, `batch` запрещён, журнал вызовов без токена).
3. **Правила `ask`/`deny`** в настройках дублируют хук (на случай отсутствия Python) и запрещают чтение `.env`,
   `config.inc.php` (MODX), `.settings.php`/`dbconn.php` (Bitrix), ключей.
4. **Защищённые папки**: перечислите производственные папки (выгрузка сайта, архив КД, расчёты) в
   `%USERPROFILE%\.claude\novaprom-protected-paths.txt` — любая запись туда потребует подтверждения.
5. Телеметрия сторонних плагинов отключается переменными окружения (`DO_NOT_TRACK`, `CLAUDE_MEM_TELEMETRY=0`,
   `IMPECCABLE_NO_TELEMETRY`, `IMPECCABLE_NO_UPDATE_CHECK`, `SUPERPOWERS_DISABLE_TELEMETRY`).
6. Все вендоренные проекты закреплены на коммите, с `NOTICE.md` и лицензией; код прочитан до вендоринга.

> Настройки применены в `.claude/settings.json` этого репозитория (2026-10-03). На рабочем ПК их добавляет
> в `%USERPROFILE%\.claude\settings.json` установочный скрипт (`scripts/merge_settings.py`: объединение без потери
> ваших настроек, резервная копия). Эталон — `docs/settings.proposed.json`. Хук субагента bitrix-auditor работает
> независимо от этих настроек.

## 7. Установка на рабочий ПК (Windows)

1. Установить Python 3.11+ (python.org, «Add python.exe to PATH») — он нужен расчётным скриптам и хуку.
2. Клонировать репозиторий и запустить:
   ```powershell
   git clone https://github.com/usuevgpt-lang/Claude-code.git D:\Claude-code
   powershell -ExecutionPolicy Bypass -File D:\Claude-code\scripts\setup-windows.ps1
   ```
   Скрипт:
   - копирует навыки, субагентов и хук в `%USERPROFILE%\.claude` (заменяемые папки переносит в
     `%USERPROFILE%\.claude\novaprom-backups\<время>`);
   - подключает правила `global/NOVAPROM.md` через `%USERPROFILE%\.claude\CLAUDE.md`;
   - убирает выведенные из эксплуатации find-skills и task-observer (в ту же папку резервных копий);
   - объединяет `docs/settings.proposed.json` с `%USERPROFILE%\.claude\settings.json`: хук, правила `ask`/`deny`,
     отключение телеметрии, claude-mem, frontend-design и novaprom-marketing — включены, superpowers, impeccable —
     выключены (резервная копия `settings.json.bak-<время>`).
3. Перезапустить Claude Code, подтвердить доверие маркетплейсам (плагины установятся сами; вручную:
   `/plugin install frontend-design@claude-plugins-official`, `/plugin install novaprom-marketing@novaprom`).
4. claude-mem — память между сессиями. Ставится вместе с остальными плагинами (маркетплейс `thedotmack`,
   закреплён на теге `v13.28.0`). Учтите:
   - он сохраняет полный ввод и вывод **каждого** вызова инструментов (в том числе прочитанные документы) в
     `%USERPROFILE%\.claude-mem\claude-mem.db` без срока хранения; в фоне делает дополнительные вызовы модели
     (Haiku) на вашей подписке и запускает локальный сервис 127.0.0.1:37777;
   - уже включено: `CLAUDE_MEM_TELEMETRY=0`, `CLAUDE_MEM_TELEMETRY_ERRORS=0`, `DO_NOT_TRACK=1`,
     `CLAUDE_MEM_REDACT_ENABLED=true` (скрытие типовых секретов);
   - **рекомендуется** исключить папки с документами заказчиков (ОТТ, КД, сметы) — добавить в `env` пользовательского
     `settings.json`, например:
     ```json
     "CLAUDE_MEM_EXCLUDED_PROJECTS": "D:/Заказчики,D:/Заказчики/**,D:/Транснефть,D:/Транснефть/**"
     ```
     (папка проекта сравнивается с шаблонами с учётом регистра; `**` — любые вложенные папки, сама папка
     указывается отдельно; обратные слэши допустимы);
     и при необходимости не записывать чтение файлов:
     `"CLAUDE_MEM_SKIP_TOOLS": "ListMcpResourcesTool,SlashCommand,Skill,TodoWrite,AskUserQuestion,Read,WebFetch"`;
   - обновлять версию — только после повторной проверки (`novaprom-tool-vetting`), меняя `ref` маркетплейса;
   - не включать соседний плагин `claude-mem-cowork` из того же маркетплейса (передаёт данные в облако cmem.ai).
5. superpowers / impeccable — только в проектах кода (сайт, скрипты). В папке такого проекта создать
   `.claude\settings.local.json`:
   ```json
   { "enabledPlugins": { "superpowers@superpowers-marketplace": true, "impeccable@impeccable": true } }
   ```
6. Защищённые папки (архив КД, выгрузка сайта, расчёты) — по одной на строку в
   `%USERPROFILE%\.claude\novaprom-protected-paths.txt`.
7. Python-пакеты (лучше в venv): `python -m pip install CoolProp openpyxl "ezdxf==1.4.4" matplotlib "Pillow>=12,<13"`.
8. MCP (по желанию):
   ```powershell
   claude mcp add --transport http b24-dev-mcp https://mcp-dev.bitrix24.tech/mcp
   claude mcp add chrome-devtools --scope user -- cmd /c npx -y chrome-devtools-mcp@1.10.1 --isolated --no-usage-statistics --no-performance-crux
   ```
9. Проверка: в Claude Code — `/skills`, `/agents`, `/hooks`; в репозитории — `python scripts/validate_config.py`
   и `python -m unittest discover -s tests -p "test_*.py"`.

## 8. Как пользоваться (примеры запросов)

| Запрос | Что произойдёт |
|---|---|
| «Рассчитай толщину обечайки Ø1000, 6,3 МПа, 09Г2С, 100 °C» | `novaprom-pressure-vessels` → вопросы о недостающих данных ([σ], φ, прибавки) → отчёт в 6 шагов |
| «Подбери фильтр-сепаратор на 50 тыс. ст. м³/ч, 5,5 МПа» | filtration-specialist + gas-process-engineer → режимы, элементы, D, ΔP; корпус → pressure-vessel-engineer |
| «Проверь расчёт независимо, можно отдавать заказчику?» | engineering-reviewer пересчитывает другим методом → таблица противоречий |
| «Сравни наши ТУ на КПР с ОТТ Транснефти» (с файлами) | transneft-specialist (офлайн) → gap-таблица A/B/C |
| «Сделай калькуляцию камеры СОД Ду700» | cost-estimator → Markdown + Excel с формулами, диапазон |
| «Подготовь ТКП по опросному листу» | technical-writer + cost-estimator → проверка цифр → DOCX |
| «Глубокое исследование: производители коалесцирующих элементов в РФ» | deep-research: бриф → план → параллельные research-worker → противоречия → отчёт |
| «Разбери этот DXF и посчитай длину реза» | cad-specialist → `dxf_inspect.py` + предпросмотр |
| «Нарисуй иконку «Теплообменное оборудование» в стиле сайта» | ui-designer → 3–4 концепции по дизайн-системе → сравнение с эталонами → ваш выбор |
| «Проведи аудит воронок Битрикс24» | bitrix-auditor (только чтение) → отчёт и план, изменения — вручную |
| «Проверь сайт после правок» | website-qa → отчёт «выпускать/нет» |
| «Найди патенты на байонетные затворы» | novaprom-literature-search |

Совет: для расчётов давайте исходные данные с источниками («[σ] = 177 МПа по ГОСТ 34233.1, табл. А.1») — тогда
отчёт будет без предупреждений и пригоден для выдачи после проверки.

## 9. Решения

Принято 2026-10-03:
- find-skills, task-observer — удалены; claude-mem сначала удалён, затем по решению владельца включён снова
  (закреплён на v13.28.0, с мерами защиты — раздел 7);
- superpowers и impeccable — выключены глобально, включаются в проектах кода;
- настройки безопасности применены (репозиторий; на ПК — установочным скриптом).

Ждут вашего решения:
1. Отключить коннекторы SlidesGPT и PandaDoc, если не используются; переподключить Google Drive с правом чтения.
2. Подключить MCP: Bitrix24 DEV (документация), chrome-devtools; Playwright — по необходимости.
3. Сделать репозиторий конфигурации **приватным** (сейчас публичный) — или строго не добавлять туда ничего о заказчиках.
4. Сверить справочные реестры («не сверено») с текстами ГОСТ 34233.1, СП 62.13330 и др. и отметить сверку.
5. Юридическая проверка маркетинговых положений (152-ФЗ, 38-ФЗ, 135-ФЗ) в overlay плагина.
6. Сообщить о вредоносном репозитории `CaptureGrubEnchant/SolidWorks` в GitHub (по желанию).

## 10. Сопровождение

- Новый навык: `anthropics skill-creator` или по образцу `novaprom-*`; описание — блочным скаляром; затем
  `python scripts/validate_config.py`.
- Сторонний код — только через `novaprom-tool-vetting`, с закреплённым коммитом и `NOTICE.md`.
- Обновление вендоренных навыков: сравнить upstream-коммит, перечитать изменения, заново применить локальные патчи
  (описаны в `NOTICE.md` каждого навыка).
- Отчёты исследований, на которых основан выбор (аудит плагинов, дизайн/код, research/маркетинг, интеграции, сайт),
  остались в рабочей сессии; ключевые выводы перенесены в этот документ.
