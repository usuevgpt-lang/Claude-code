---
name: novaprom-cad
description: >-
  Конструкторская работа с файлами CAD — анализ чертежей DXF/DWG (слои, основная надпись, размеры, контуры, длина реза, площадь заготовки), аналитические развёртки (конус, косой срез, секционный отвод, врезка), STEP/3D (масса, габариты, превью), спецификации по ГОСТ 2.106 и ведомости материалов, выгрузка данных из SolidWorks (только с разрешения). Use for DXF/DWG/STEP analysis, sheet-metal developments, BOM/specification extraction, SolidWorks data export.
when_to_use: >-
  "разбери DXF", "посчитай длину реза и площадь заготовки", "сделай развёртку конуса/отвода/врезки", "вытащи спецификацию из сборки", "что в этом DWG", "масса по STEP", "ведомость материалов из модели".
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/unfold.py *) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/unfold.py *) Bash(python ${CLAUDE_SKILL_DIR}/scripts/dxf_inspect.py *) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/dxf_inspect.py *)
---

# CAD: DXF / DWG / STEP / SolidWorks (НОВАПРОМ)

## Честно о возможностях
Skill — не CAD-ядро. Claude **не строит** производственные модели SolidWorks «с нуля». Реально и надёжно:
чтение и анализ DXF/DWG/STEP, расчёт развёрток аналитических поверхностей, извлечение данных (свойства,
спецификации, массы), пакетный экспорт из существующих моделей, макросы/скрипты для проверки инженером,
параметрические простые детали кодом (build123d) как черновик. Производственная модель и КД — в SolidWorks инженером.

## Правила
1. Работать с **копиями**: входные файлы → `work/in/`, результаты → `work/out/`. Архив КД не изменять.
2. Любая автоматизация SolidWorks (pywin32/COM, макросы, MCP), FreeCAD MCP, запуск конвертеров (ODA, LibreDWG) —
   **только с явного разрешения пользователя**; SolidWorks-документы открывать только для чтения.
3. Сторонние «SolidWorks MCP» не устанавливать без проверки `novaprom-tool-vetting`. Известен вредоносный
   репозиторий `CaptureGrubEnchant/SolidWorks` (README с `irm … | iex`).
4. Результаты развёрток проверять на эталонной детали в SolidWorks перед запуском в производство.
5. Чертежи и модели заказчиков — конфиденциальны: не отправлять во внешние сервисы.

## Инструменты (установка в venv; см. `references/install.md`)
| Задача | Инструмент |
|---|---|
| DXF чтение/запись/анализ/рендер | ezdxf 1.4.4 (MIT) + matplotlib |
| DWG → DXF | ODA File Converter (бесплатный, проприетарный EULA — проверить) → ezdxf `odafc`; запасной — LibreDWG `dwg2dxf` (GPL, только чтение, в отдельной папке); или SolidWorks «Сохранить как DXF» |
| STEP/3D: объём, масса (× плотность), габарит, превью | build123d 0.13.0 (Apache-2.0); trimesh — быстрые превью |
| SolidWorks: свойства, BOM, масса, экспорт STEP/PDF/DXF развёрток | COM API через pywin32 — собственные read-only скрипты (`references/solidworks-api.md`) |

## Скрипты
```bash
python ${CLAUDE_SKILL_DIR}/scripts/dxf_inspect.py work/in/part.dxf --render work/out/part.png --json work/out/part.json
python ${CLAUDE_SKILL_DIR}/scripts/dxf_inspect.py work/in/flat.dxf --layers CUT,0 --tol 0.01
python ${CLAUDE_SKILL_DIR}/scripts/unfold.py cone   --D 1000 --d 500 --H 500 --dxf work/out/cone.dxf
python ${CLAUDE_SKILL_DIR}/scripts/unfold.py gore   --r 159.5 --R 480 --angle 90 --n 3 --dxf work/out/gore.dxf
python ${CLAUDE_SKILL_DIR}/scripts/unfold.py saddle --rb 54 --Rh 159 --e 0 --dxf work/out/saddle.dxf
python ${CLAUDE_SKILL_DIR}/scripts/unfold.py mitre  --outer 219 --t 8 --k 0.5 --L0 300 --beta 22.5
```
`dxf_inspect.py`: контуры собираются и из отрезков/дуг (развёртки SolidWorks) по совпадению концов в пределах
`--tol` мм (по умолчанию 0,01). Длина реза суммирует всю линейную геометрию пространства модели (рамка, линии
гиба, осевые) — для детали ограничить слои `--layers`. Предупреждения о незамкнутых контурах и «ОЦЕНКА
НЕДОСТОВЕРНА» — разобрать по предпросмотру до использования площади заготовки.

Диаметры для развёрток — нейтральные (k-фактор — по технологии производства, задаётся явно). Пересчёт из
наружного (`--outer --t --k`) есть только в `mitre`; `cone`, `gore`, `saddle` эти ключи отклоняют — задать
нейтральные размеры (D_нейтр = D_нар − 2·t + 2·k·t).
Эксцентрические переходы и «квадрат–круг» — триангуляция в SolidWorks (lofted bends).

## Спецификация (ГОСТ 2.106) и ведомости
Готовых зрелых open-source инструментов нет — собираем сами (`references/specification.md`): из сборки SolidWorks
(обход компонентов + пользовательские свойства «Обозначение», «Наименование», «Материал», «Масса», «Раздел») или
из штампов DXF (атрибуты блока / тексты в зоне основной надписи). Проверка: сумма масс и количество позиций против
свойств сборки. Вывод — XLSX (навык `xlsx`) для проверки, затем форма.

## Типовой процесс «анализ чертежа»
1. Копия → (DWG→DXF) → `dxf_inspect.py` + предпросмотр PNG → **посмотреть предпросмотр** и убедиться, что
   разобрано то, что изображено.
2. Выводы: габариты, материал и обозначение из штампа, размеры, отверстия, длина реза/площадь заготовки.
3. Несоответствия с ТЗ/расчётом — таблицей; изменения КД — предложением, не правкой файла.
