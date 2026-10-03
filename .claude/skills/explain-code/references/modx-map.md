# Карта проекта MODX Revolution (шпаргалка; сверять с реальным проектом и версией 2.x/3.x)

| Путь / элемент | Что это | Примечание |
|---|---|---|
| `core/` | Ядро MODX, кэш (`core/cache/`), пакеты (`core/components/<pkg>/`), конфиг | желательно вне webroot |
| `core/config/config.inc.php` | Подключение к БД, пути | **секреты — маскировать** |
| `manager/` (может быть переименован) | Админ-панель | не трогать |
| `connectors/` | Точки входа AJAX менеджера/дополнений | |
| `assets/templates/<tpl>/` | Статика темы: CSS, JS, изображения, иконки | на novaprom.ru: `/assets/templates/img/ico/…` |
| `assets/components/<pkg>/` | Публичные файлы дополнений (например, AjaxForm) | |
| Шаблоны, чанки, сниппеты, плагины, TV | Элементы, по умолчанию **хранятся в БД** (`modx_site_templates`, `modx_site_htmlsnippets`, `modx_site_snippets`, `modx_site_plugins`, `modx_site_tmplvars`) | могут быть «статическими» (файлы) — проверить |
| Ресурсы (страницы) | `modx_site_content`; поля `pagetitle`, `longtitle`, `description`, `alias`, `content`, `template` | ЧПУ — по alias и настройкам friendly URLs |
| Системные настройки | `modx_system_settings` (+ настройки контекста/пользователя) | `[[++setting]]` |

## Синтаксис тегов
`[[*field]]` поле ресурса · `[[$chunk]]` чанк · `[[snippet]]` / `[[!snippet]]` сниппет (с `!` — некэшируемый) ·
`[[++setting]]` настройка · `[[~id]]` ссылка на ресурс · `[[%lexicon]]` словарь · `[[+placeholder]]` плейсхолдер ·
модификаторы вывода `:default=`, `:notempty=`, `:htmlent` и т.п. При pdoTools возможны Fenom-шаблоны `{…}`.

## Плагины и события
Плагины привязаны к событиям (`OnLoadWebDocument`, `OnWebPagePrerender`, `OnPageNotFound`, `OnDocFormSave`…);
привязки хранятся в БД (`modx_site_plugin_events`).

## Частые дополнения (Extras)
pdoTools (pdoResources, pdoMenu, Fenom), AjaxForm + FormIt (обработка форм, отправка почты, хуки), MIGX (табличные TV),
SEO-дополнения (sitemap, robots), Babel (мультиязычность). Версии дополнений — в «Установщике» (Package Management).

## Порядок рендера (упрощённо)
Запрос → роутинг к ресурсу → шаблон ресурса → разбор тегов (кэшируемые → кэш, некэшируемые — каждый раз) →
плагины на событиях → вывод.
