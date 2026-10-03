# NOTICE — novaprom-marketing 1.0.0

Плагин собран статическим копированием файлов из двух репозиториев с открытой лицензией MIT на
зафиксированных коммитах, плюс локальные дополнения НОВАПРОМ. Код из исходных репозиториев не запускался
(никаких npm/npx, скриптов, CI). Дата сборки: 2026-10-03.

## 1. coreyhaines31/marketingskills

| Поле | Значение |
|---|---|
| Репозиторий | https://github.com/coreyhaines31/marketingskills |
| Коммит | `dda3841f0b294e01e93b1541486beefbfab0915e` (2026-10-02, версия библиотеки 2.11.17) |
| Лицензия | MIT, © 2025 Corey Haines — копия `LICENSE` лежит в папке каждого скилла |
| Что скопировано | `skills/<имя>/SKILL.md` и `skills/<имя>/references/` (папок `assets/` у выбранных скиллов нет) |
| Что не скопировано | `evals/`, `tools/` (64 Node-CLI, интеграции, Composio), `scripts/`, `.github/`, остальные 35 скиллов |

Скиллы (версия из `metadata.version` в upstream):

| Скилл | Версия | Локальные изменения |
|---|---|---|
| product-marketing | 2.1.0 | патч 3 |
| seo-audit | 2.0.1 | — |
| ai-seo | 2.7.2 | патч 1 |
| schema | 2.0.0 | — |
| site-architecture | 2.0.0 | — |
| content-strategy | 2.1.2 | — |
| copywriting | 2.1.0 | — |
| copy-editing | 2.1.0 | — |
| cro | 2.0.0 | — |
| analytics | 2.0.2 | — |
| competitor-profiling | 2.1.2 | — |
| competitors | 2.3.0 | — |
| customer-research | 2.0.4 | патч 2 |
| sales-enablement | 2.3.2 | — |
| programmatic-seo | 2.0.0 | — |

Все файлы без пометки «патч» побайтно совпадают с upstream на указанном коммите (проверено `diff -r`).

## 2. wondelai/skills — jobs-to-be-done

| Поле | Значение |
|---|---|
| Репозиторий | https://github.com/wondelai/skills |
| Коммит | `c172996495bed0fcd26896a9416b2093fd7073f0` (2026-09-10), скилл `jobs-to-be-done` v1.5.0 |
| Лицензия | MIT, © 2025 Wondel.ai sp. z o.o. — `skills/jtbd-industrial/references/upstream-wondelai/LICENSE` |
| Размещение | `jobs-to-be-done/SKILL.md` → `skills/jtbd-industrial/references/upstream-wondelai/jtbd-core.md` (переименован, чтобы не загружался как отдельный скилл; содержимое, включая YAML-шапку, не изменено); `jobs-to-be-done/references/*.md` → `skills/jtbd-industrial/references/upstream-wondelai/references/` (сохранены относительные ссылки из `jtbd-core.md`) |
| Изменения | нет (побайтно совпадает с upstream) |

## 3. Локальные патчи (раздел 3.9 отчёта 04-research-marketing-skills)

**Патч 1 — `ai-seo`: убран запуск стороннего npm-пакета.**
- `skills/ai-seo/SKILL.md`, строка 279: `` (`npx is-agentic`, Frase's checker) `` →
  `(is-agentic.com and Frase's checker — web UI only; local policy forbids running npx packages)`.
- `skills/ai-seo/references/agent-readiness.md`, строка 9: `` `npx is-agentic yourdomain.com` or `` →
  `web UI only:`.

**Патч 2 — `customer-research`: JTBD направляется в `jtbd-industrial`.**
- Из `description` удалено `"jobs to be done," "JTBD," `; в конец добавлено
  ` For JTBD analysis, see jtbd-industrial.` Длина описания — 966 символов.

**Патч 3 — `product-marketing`: обязательный российский B2B-раздел.**
- Добавлен файл `skills/product-marketing/references/ru-b2b-industrial-overlay.md` (блок из раздела 3.8 отчёта).
- В «Step 3: Create the Document» после шаблона добавлена строка: «Always append the section from
  references/ru-b2b-industrial-overlay.md (adapted to the company) to the document.»
- Отличия overlay от черновика в отчёте:
  - описание компании приведено к фактической линейке по сайту novaprom.ru (отчёт 06): КПР-НП, ЗК-НП,
    ФГ-НП/ФЖ-НП, СГ-НП/НГС, блочно-модульное оборудование, резервуары, КТП; ПГБ/ГРП и теплообменники
    помечены как отсутствующие на сайте; добавлен абзац о сайте (MODX Revolution, AjaxForm, Яндекс Метрика);
  - юридические утверждения (152-ФЗ, 156-ФЗ, 38-ФЗ, 135-ФЗ: даты и требования) помечены «(требует
    подтверждения юристом)»;
  - в «Граница с инженерией» добавлены существующие скиллы novaprom-commercial-proposal,
    novaprom-normative-check, novaprom-tech-docs, novaprom-transneft;
  - в «Не установлены» добавлены скиллы фазы 2 (attribution, emails, events, lead-magnets,
    public-relations, revops) и общая оговорка про прочие скиллы библиотеки;
  - в «Доверие» добавлены ТР ТС 010/2011, патенты и правило о публикации названий заказчиков.

## 4. Локальные файлы НОВАПРОМ (MIT, как указано в `plugin.json`)

- `.claude-plugin/plugin.json` — манифест.
- `skills/jtbd-industrial/SKILL.md` — собственный скилл (перевод и адаптация черновика из раздела 2.6
  отчёта 04). Методические источники: Ulwick, *Jobs to be Done: Theory to Practice* (2016) — «Outcome-Driven
  Innovation» является товарным знаком Strategyn, используется описательное название; Moesta, *Demand-Side
  Sales 101* (2020); Christensen et al., *Competing Against Luck* (2016). Тексты книг не воспроизводятся.
- `skills/product-marketing/references/ru-b2b-industrial-overlay.md` — см. патч 3.
- `agents/seo-specialist.md`, `agents/marketing-strategist.md` — субагенты плагина.
- `README.md`, `NOTICE.md`.

## 5. Известные остатки (сознательно не изменены)

- `skills/ai-seo/references/linkedin-ai-citations.md` содержит пример `curl -A "$UA"` для проверки
  robots-заголовков. Это справочный пример, а не инструкция к автозапуску; субагенты плагина не имеют Bash.
- Ссылки на неустановленные скиллы (pricing, offers, popups, ab-testing, emails и др.) и на GitHub-страницы
  `tools/` upstream остаются в текстах; overlay велит их игнорировать и не устанавливать инструменты.
- `jtbd-core.md` содержит партнёрскую ссылку Amazon (`tag=wondelai00-20`) в разделе Further Reading —
  оставлена, чтобы файл совпадал с upstream.
- Ориентация upstream-скиллов на Google/GA4/GTM и западные SaaS-инструменты не переписывалась; российская
  специфика задаётся через overlay в контекст-файле `.agents/product-marketing.md`.

## 6. Обновление из upstream

Не отслеживать `main` автоматически. При обновлении: взять новый коммит, сравнить `VERSIONS.md` и изменённые
скиллы, просмотреть diff (нет ли скриптов, `npx`, сетевых вызовов, скрытых символов), заново скопировать
файлы и повторно применить патчи 1–3, обновить таблицы в этом файле.

---

*Юридические пункты (152-ФЗ, 156-ФЗ, 38-ФЗ, 135-ФЗ) приведены для проектирования маркетинга и не являются
юридической консультацией; перед публикацией их подтверждает юрист компании.*
