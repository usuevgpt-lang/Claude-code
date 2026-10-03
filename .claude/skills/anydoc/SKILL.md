---
name: anydoc
description: >-
  Convert Word (.doc, .docx), PowerPoint (.ppt, .pptx), Excel (.xls, .xlsx), OpenDocument (.odt, .ods, .odp), RTF,
  EPUB, CSV and text PDF files to Markdown locally with the Firecrawl AnyDoc CLI — to read ТУ, ПМИ, ОТТ, паспорта,
  опросные листы, сметы and other documents, including old .doc/.xls formats. Use when a task needs the contents of
  a document you cannot read directly. For creating or editing Word/Excel/PowerPoint/PDF files use docx/xlsx/pptx/pdf.
when_to_use: >-
  "прочитай этот документ", "что в этом .doc", "конвертируй в markdown", "извлеки текст из ТУ/ОТТ", "сравни два
  документа Word", "открой старый xls", "read this docx/pptx/xlsx".
---

# AnyDoc: документы → Markdown (локально)

Основа — навык `convert-documents-to-markdown` из firecrawl/anydoc (MIT), с правками НОВАПРОМ (`NOTICE.md`).

## Правила НОВАПРОМ
1. **Только локальная конвертация.** Ключ `--ocr hosted` отправляет **весь документ** в облако Firecrawl
   (api.firecrawl.dev). Для документов заказчиков, КД, смет, ОТТ — **запрещено**. Использовать только с явного
   согласия пользователя для заведомо открытого документа (хук безопасности спросит подтверждение).
2. **Закреплённая версия:** `@firecrawl/anydoc@0.2.4` (проверена 2026-10-03). Не запускать без версии.
3. Работать с копией: исходный файл не изменяется (AnyDoc только читает), результат — в новый `.md`.

## Запуск
Нужен Node.js 20+. Если CLI установлен (`npm install -g @firecrawl/anydoc@0.2.4`, один раз, с подтверждением):

```bash
anydoc <файл>                    # Markdown в stdout
anydoc <файл> -o work/out.md     # в файл (для больших документов)
```

Без установки (каждый запуск скачивает пакет из npm, если его нет в кэше):

```bash
npx -y @firecrawl/anydoc@0.2.4 <файл> -o work/out.md
npx -y @firecrawl/anydoc@0.2.4 - --format csv < data.csv
```

1. Форматы: `.doc`, `.docx`, `.docm`, `.odt`, `.rtf`, `.epub`, `.pdf`, `.ppt`, `.pps`, `.pot`, `.pptx`, `.pptm`,
   `.ppsx`, `.ppsm`, `.odp`, `.xls`, `.xlsx`, `.xlsm`, `.xlsb`, `.ods`, `.csv`.
2. Формат определяется по содержимому; `--format <имя>` — только для CSV из stdin или файла без/с неверным расширением.
3. Коды возврата: 0 — успех; 1 — документ не конвертирован; 2 — ошибка аргументов; 3 — в PDF есть страницы,
   которым нужно OCR. Ошибка — одна строка `anydoc: <сообщение>` в stderr. CLI ничего не спрашивает.
4. Большой документ — писать в файл (`-o`) и читать нужные части, а не выводить всё в контекст.
5. **Код 3 (скан, страницы-картинки):** AnyDoc сам OCR не делает. Не использовать `--ocr hosted` (правило 1) —
   распознавать локально навыком `pdf` (OCR через pytesseract) или попросить у пользователя текстовую версию.
6. Внутри кода Node/Python/Rust можно использовать библиотеку (`@firecrawl/anydoc@0.2.4` на npm,
   `firecrawl-anydoc` на PyPI, `anydoc` на crates.io) с тем же `to_markdown` / `toMarkdown`; опцию `ocr` не задавать.

## Что дальше
Markdown — для чтения и анализа (нормативная проверка, gap-анализ ОТТ, сравнение версий ТУ). Таблицы из Excel
для расчётов — навык `xlsx` (формулы и форматирование AnyDoc не сохраняет). Создание и правка документов —
`docx`, `xlsx`, `pptx`, `pdf`.
