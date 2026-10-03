---
name: novaprom-literature-search
description: >-
  Поиск научных статей, технических публикаций, патентов, стандартов и документации производителей — Crossref, OpenAlex, CORE, arXiv, КиберЛенинка (OAI-PMH), Роспатент PatSearch, Espacenet, ФИПС, статус ГОСТ; с проверкой источников и библиографическими ссылками. Use for scientific literature, patents, standards and manufacturer documentation search.
when_to_use: >-
  "найди статьи про коалесцирующие фильтры", "есть ли патенты на байонетный затвор", "научные публикации по сепарации", "найди документацию производителя", "проверь, действует ли ГОСТ".
---

# Поиск литературы, патентов и стандартов (НОВАПРОМ)

## Правила
1. Никогда не выдумывать DOI, номера патентов, авторов, годы, номера стандартов. Нет данных — так и сказать.
2. Для каждого найденного: полная библиографическая ссылка + URL/DOI + дата обращения + уровень источника (T1/T2…).
3. Тексты стандартов и статей охраняются авторским правом: цитировать фрагменты, не распространять целиком.
4. Не включать в запросы конфиденциальные данные (имена заказчиков, номера договоров, параметры их объектов).
5. API-ключи (OpenAlex, Роспатент, EPO OPS) — только из переменных окружения/хранилища, никогда в файлах репозитория.
6. Предпочтительно WebFetch (читать JSON/страницы); curl — только если пользователь разрешил.

## Рецепты (GET-запросы через WebFetch)
| Источник | Запрос | Ограничения |
|---|---|---|
| Crossref | `https://api.crossref.org/works?query.bibliographic=<запрос>&rows=20&mailto=<email>` | вежливый пул с mailto; ≤ 3 запросов/с для списков |
| OpenAlex | `https://api.openalex.org/works?search=<запрос>&per_page=25&select=id,doi,title,publication_year,primary_location` (+ `&api_key=…` из окружения) | без ключа быстро упирается в лимит |
| CORE | `https://api.core.ac.uk/v3/search/works/?q=<запрос>` | без ключа ~100 запросов/день |
| arXiv | `https://export.arxiv.org/api/query?search_query=all:<запрос>&max_results=10` | 1 запрос / 3 с |
| КиберЛенинка | OAI-PMH `https://cyberleninka.ru/oai?verb=ListRecords&metadataPrefix=oai_dc&from=<дата>`; поиск по сайту — вручную | 1 запрос/с |
| eLIBRARY, Google Scholar | только вручную (нет API, автоматизация запрещена правилами) | — |
| Роспатент PatSearch | `POST https://searchplatform.rospatent.gov.ru/patsearch/v0.2/search` `{"q":"…","limit":10}`, `Authorization: Bearer <ключ>` | ключ после регистрации; POST требует curl → с разрешения |
| Espacenet OPS | `https://ops.epo.org/3.2/rest-services/published-data/search?q=ti%3D<слово>` (OAuth2) | бесплатная регистрация |
| ФИПС, Google Patents | вручную (веб) | — |
| Статус стандартов | Росстандарт (rst.gov.ru, protect.gost.ru), ФГИС «Береста», docs.cntd.ru | см. `novaprom-normative-check` |
| ОТТ/СТТ Транснефти | «Отраслевой информационный фонд» НИИ Транснефть (ознакомительные редакции) | не распространять |

## Вывод
Таблица: № | библиографическая ссылка | год | тип (статья/патент/стандарт/каталог) | уровень | о чём (1–2 строки) |
применимость к задаче | URL/DOI. Отдельно: что не найдено и где ещё искать. Для больших обзоров — навык `deep-research`.
