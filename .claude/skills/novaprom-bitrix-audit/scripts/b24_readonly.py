#!/usr/bin/env python3
"""Read-only клиент REST API Bitrix24 (коробка) для аудита.

Разрешены только методы чтения из белого списка; `batch` и любые методы записи отклоняются
до отправки запроса. URL входящего вебхука берётся из переменной окружения B24_WEBHOOK_URL
(вида https://portal.example.ru/rest/<user_id>/<code>/) и никогда не печатается целиком.

Примеры:
    python b24_readonly.py scope
    python b24_readonly.py crm.category.list --param entityTypeId=2 --out categories.json
    python b24_readonly.py crm.status.list --param "filter[ENTITY_ID]=DEAL_STAGE" --all
    python b24_readonly.py crm.deal.fields --dry-run

Каждый вызов пишется в журнал b24-audit-log.jsonl (метод, параметры, время, кол-во записей; без токена).
Внимание: в Bitrix24 нет «read-only» области доступа — защита многоуровневая: отдельный пользователь
с правами «только чтение», минимальные scope вебхука, этот белый список, удаление вебхука после аудита.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ALLOWED = re.compile(
    r"^(crm\.(category|status|deal|lead|contact|company|type|item|quote|invoice)\.(list|get|fields)"
    r"|crm\.status\.entity\.types|crm\.(deal|lead|contact|company)\.userfield\.list"
    r"|user\.(get|current|fields)|department\.(get|fields)"
    r"|bizproc\.workflow\.template\.list|bizproc\.workflow\.instances"
    r"|tasks\.task\.(list|get)|scope|methods|server\.time|app\.info)$"
)
DENY_HINT = re.compile(r"(add|update|delete|set|start|terminate|kill|bind|unbind|send|batch|import|upload|register|attach)", re.I)
LOG_FILE = "b24-audit-log.jsonl"


def mask(url: str) -> str:
    return re.sub(r"/rest/(\d+)/[^/]+/", r"/rest/\1/****/", url)


def check_method(method: str) -> None:
    if method == "batch" or not ALLOWED.match(method):
        hint = " (похоже на метод записи)" if DENY_HINT.search(method) else ""
        raise SystemExit(f"ОТКЛОНЕНО: метод '{method}' не входит в белый список чтения{hint}. "
                         "Изменения в Bitrix24 — только вручную пользователем или с его явного разрешения "
                         "вне этого инструмента.")


def parse_params(items: list[str]) -> dict:
    params: dict = {}
    for it in items or []:
        if "=" not in it:
            raise SystemExit(f"Параметр должен быть вида key=value: {it}")
        k, v = it.split("=", 1)
        params[k] = v
    return params


def call(base: str, method: str, params: dict, timeout: float = 30.0) -> dict:
    url = base.rstrip("/") + "/" + method + ".json"
    data = urllib.parse.urlencode(params, doseq=True).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:500]
        raise SystemExit(f"HTTP {e.code} при вызове {method} ({mask(url)}): {body}")
    except urllib.error.URLError as e:
        raise SystemExit(f"Сетевая ошибка при вызове {method} ({mask(url)}): {e.reason}")


def log(method: str, params: dict, count: int | None, note: str = "") -> None:
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "method": method, "params": params,
           "records": count, "note": note}
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("method")
    ap.add_argument("--param", action="append", help="параметр key=value (можно несколько)")
    ap.add_argument("--all", action="store_true", help="постранично получить все записи (start=0,50,...)")
    ap.add_argument("--max-pages", type=int, default=200)
    ap.add_argument("--sleep", type=float, default=0.6, help="пауза между запросами, с")
    ap.add_argument("--out", help="сохранить результат в JSON-файл")
    ap.add_argument("--dry-run", action="store_true", help="только показать, что будет вызвано")
    a = ap.parse_args(argv)

    check_method(a.method)
    params = parse_params(a.param)
    base = os.environ.get("B24_WEBHOOK_URL", "")
    if a.dry_run:
        print(f"DRY RUN: {a.method} {params} → {mask(base) if base else '(B24_WEBHOOK_URL не задан)'}")
        return 0
    if not re.match(r"^https://[^/]+/rest/\d+/[^/]+/?$", base):
        raise SystemExit("Задайте B24_WEBHOOK_URL=https://<портал>/rest/<id>/<код>/ (только HTTPS). "
                         "Не сохраняйте его в файлах репозитория.")

    results, start, pages = [], 0, 0
    while True:
        p = dict(params)
        if a.all:
            p["start"] = start
        resp = call(base, a.method, p)
        if "error" in resp:
            log(a.method, params, None, f"error: {resp.get('error')}")
            raise SystemExit(f"Ошибка API: {resp.get('error')}: {resp.get('error_description', '')}")
        res = resp.get("result")
        if isinstance(res, dict) and isinstance(res.get("items"), list):  # crm.item.list / crm.category.list (новый формат)
            chunk = res["items"]
        elif isinstance(res, dict) and isinstance(res.get("categories"), list):
            chunk = res["categories"]
        elif isinstance(res, dict) and isinstance(res.get("tasks"), list):
            chunk = res["tasks"]
        else:
            chunk = res
        if isinstance(chunk, list):
            results.extend(chunk)
        else:
            results = chunk
        pages += 1
        nxt = resp.get("next")
        if not a.all or nxt is None or pages >= a.max_pages:
            break
        start = nxt
        time.sleep(a.sleep)

    count = len(results) if isinstance(results, list) else None
    log(a.method, params, count)
    text = json.dumps(results, ensure_ascii=False, indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Сохранено: {a.out} (записей: {count if count is not None else 'объект'}, страниц: {pages})")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
