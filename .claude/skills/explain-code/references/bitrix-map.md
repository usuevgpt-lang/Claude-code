# Bitrix project map (cheat sheet). Confirm against the actual project.

| Path | What it is | Notes |
|---|---|---|
| `/local/` | Project customisations (supported since Bitrix 14) | Search here first |
| `/bitrix/` | Core: kernel, modules, admin | Do not edit; updates overwrite it. Legacy projects may still keep custom code in `/bitrix/php_interface`, `/bitrix/templates`, `/bitrix/components/<own-namespace>` |
| `/local/php_interface/init.php` (legacy: `/bitrix/php_interface/init.php`) | Global bootstrap: event handlers, constants, autoload, includes | Often includes further files |
| `/local/components/<ns>/<name>/` | Custom components | `class.php` (`extends CBitrixComponent`, `executeComponent()`) or legacy `component.php`; `.parameters.php`; `.description.php`; `templates/.default/`; `ajax.php` or a controller (`Controllerable::configureActions`) |
| `…/templates/<tpl>/template.php`, `result_modifier.php`, `component_epilog.php`, `script.js`, `style.css`, `lang/` | Component template layer | `result_modifier.php` runs before the template and is cached with it; `component_epilog.php` runs after and is not cached |
| `/local/templates/<site_tpl>/` | Site template: `header.php`, `footer.php`, `template_styles.css`, `components/<ns>/<component>/<tpl>/` overrides | The template is chosen by site-template conditions stored in the database |
| `/local/modules/<vendor.module>/` | Custom modules: `include.php`, `install/index.php` (registers persistent events and agents), `lib/` (D7 classes, namespace autoload), `options.php` | |
| `/urlrewrite.php` | SEF routing: which page or component serves a URL | Start here for "which code serves this URL" |
| `/<section>/index.php`, `.section.php`, `.<type>.menu.php`, `.<type>.menu_ext.php` | Public pages (with `$APPLICATION->IncludeComponent(...)` calls and their parameters), section properties, menus | |
| `/bitrix/.settings.php`, `/bitrix/php_interface/dbconn.php` | Database and cache configuration | **Secrets — mask** |
| `/local/js/<vendor>/<ext>/` (`config.php`, `bundle.config.js`) | JS extensions, loaded with `\Bitrix\Main\UI\Extension::load()` or `CJSCore::Init()` | |
| `/local/activities/` | Custom business-process activities (Bitrix24 on-premise) | |
| `/upload/` | User files | Not code |

Page lifecycle, roughly: `/bitrix/header.php` (prolog, `init.php`, `OnPageStart` / `OnBeforeProlog` / `OnProlog`) → site template `header.php` → page body and components → `footer.php` → `OnEpilog` / `OnEndBufferContent`.

Legacy API → D7 equivalent:
- `CModule::IncludeModule` → `Loader::includeModule`
- `CIBlockElement::GetList` → `\Bitrix\Iblock\ElementTable` or `\Bitrix\Iblock\Elements\Element<ApiCode>Table`
- `$DB->Query` → `Application::getConnection()->query()`
- `AddEventHandler` → `EventManager::getInstance()->addEventHandler()`
- `COption` → `\Bitrix\Main\Config\Option`
- `$_REQUEST` → `Context::getCurrent()->getRequest()`
- Highload blocks: `HighloadBlockTable::compileEntity()`

JS: `BX.ready`, `BX.ajax.runAction` / `BX.ajax.runComponentAction`, `BX.message` (language strings).

Bitrix24 REST: `BX24.callMethod` in apps. Inbound webhooks look like `https://<portal>/rest/<user_id>/<code>/<method>`; the code is a secret.
