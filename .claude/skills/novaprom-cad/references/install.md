# Установка CAD-инструментов (выполняет пользователь; версии закреплены)

```powershell
py -3.12 -m venv $env:USERPROFILE\.venvs\cad
& $env:USERPROFILE\.venvs\cad\Scripts\python -m pip install --upgrade pip
# DXF + 3D + превью
& $env:USERPROFILE\.venvs\cad\Scripts\python -m pip install "ezdxf==1.4.4" matplotlib "build123d==0.13.0" "trimesh==5.1.1"
# SolidWorks COM — только после решения пользователя (скрипты управляют SolidWorks)
& $env:USERPROFILE\.venvs\cad\Scripts\python -m pip install "pywin32==312"
# DWG → DXF: ODA File Converter (проверить лицензионное соглашение и доступность загрузки)
winget search ODA
```
Не устанавливать пакет `OCP` из PyPI (посторонний) — правильный пакет `cadquery-ocp` ставится вместе с build123d.
PyMuPDF — AGPL: для внутреннего использования допустим, для распространяемых продуктов — нет.
