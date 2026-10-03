# SolidWorks API — шпаргалка для read-only скриптов (не протестировано в этой среде: нет SolidWorks)

Требования: Windows, установленный лицензионный SolidWorks, запуск в сессии пользователя, **разрешение пользователя**.
Document Manager API требует ключ с портала Dassault по активной подписке — для РФ после 2022 г. может быть недоступен;
ориентироваться на COM.

| Задача | Вызов |
|---|---|
| Подключение | `win32com.client.Dispatch("SldWorks.Application")` |
| Открыть только для чтения | `ISldWorks.OpenDoc6(path, type, swOpenDocOptions_Silent | swOpenDocOptions_ReadOnly, cfg, err, warn)` (err/warn — ByRef VARIANT) |
| Свойства | `ModelDoc2.Extension.CustomPropertyManager(cfg).GetAll3(...)` / `.Get6(...)` |
| Масса, объём | `Extension.CreateMassProperty` → `IMassProperty` |
| Габарит детали | `PartDoc.GetPartBox(True)` |
| Состав сборки | `AssemblyDoc.GetComponents(False)`; учитывать `GetSuppression2`, `ExcludeFromBOM`, `ReferencedConfiguration` |
| Развёртка листовой детали → DXF | `PartDoc.ExportToDWG2(out, modelPath, swExportToDWG_ExportSheetMetal, True, ...)` |
| STEP/IGES/STL | `ModelDocExtension.SaveAs(...)` с нужным расширением (AP задаётся пользовательской настройкой) |
| PDF чертежа | `GetExportFileData(swExportPdfData)` + `SaveAs` |

Подводные камни COM из Python: ByRef-параметры через `VARIANT(pythoncom.VT_BYREF | ...)`; не передавать `None`
вместо «отсутствующего» параметра; все вызовы в одном STA-потоке.
Скрипты, которые **записывают** свойства (`Add3`) или сохраняют модели, — отдельное разрешение на каждый запуск.
