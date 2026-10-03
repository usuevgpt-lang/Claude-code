#!/usr/bin/env python3
"""PreToolUse-хук безопасности НОВАПРОМ.

Получает JSON вызова инструмента на stdin и решает:
  deny  — запрещено всегда (скачать из интернета и сразу выполнить: curl|sh, irm|iex и т.п.);
  ask   — принудительный запрос подтверждения пользователя (даже в auto mode);
  (нет вывода) — обычная обработка правилами разрешений Claude Code.

Хук «закрыт при сбое»: если вход не разобран или проверка упала, он просит подтверждение (ask),
а не пропускает вызов молча.

Профили (аргумент --profile):
  default           — общий профиль (подключается в settings.json);
  bitrix-readonly   — для субагента bitrix-auditor: сетевые клиенты, SSH, БД, PHP и обращения
                      к /rest/ в обход b24_readonly.py блокируются (deny), а не «спрашиваются».

Защищённые пути (запись/правка требует подтверждения): переменная окружения
NOVAPROM_PROTECTED_PATHS (разделители «;», перевод строки или os.pathsep) и/или файлы со списком
путей (по одному на строку, UTF-8; BOM допускается):
  <проект>/.claude/protected-paths.txt и ~/.claude/novaprom-protected-paths.txt
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

DOWNLOADERS = {"curl", "wget", "irm", "iwr", "invoke-restmethod", "invoke-webrequest", "fetch"}
INTERPRETERS = re.compile(r"^((ba|z|da|k|c|tc|fi)?sh|python\d*(\.\d+)?|py|node|perl|ruby|php|pwsh|powershell|"
                          r"iex|invoke-expression|cmd)$")
WRAPPERS = {"sudo", "env", "exec", "nohup", "time", "command", "xargs", "tee", "nice", "doas", "&", "call", "start"}
SHELLS_RE = r"(?:\S*/)?(?:ba|z|da|k)?sh"
DL_RE = r"(?:curl|wget|irm|iwr|invoke-restmethod|invoke-webrequest)"

DENY_REGEX = [
    (rf"\b{SHELLS_RE}\b[^\n]*(?:\$\(|<\(|`)\s*{DL_RE}\b", "Выполнение скрипта, загружаемого из интернета ($(curl …), <(curl …))"),
    (rf"(?:^|[\s;&|])(?:source|\.)\s+<\(\s*{DL_RE}\b", "Выполнение скрипта, загружаемого из интернета (source <(curl …))"),
    (rf"\b(?:python\d*(?:\.\d+)?|perl|ruby|node)\b[^\n]*<\(\s*{DL_RE}\b", "Выполнение загружаемого из интернета кода"),
    (r"\b(?:iex|invoke-expression)\b[^\n]*(?:new-object|net\.webclient|downloadstring|downloadfile|\birm\b|\biwr\b|"
     r"invoke-webrequest|invoke-restmethod|https?://)", "Выполнение загруженного кода (iex) запрещено политикой"),
    (r"(?:new-object|net\.webclient|downloadstring|\birm\b|\biwr\b|invoke-webrequest|invoke-restmethod)[^\n]*\|\s*"
     r"(?:iex|invoke-expression)\b", "Выполнение скрипта из интернета (irm|iex) запрещено политикой"),
    (r"\[scriptblock\]::create\([^\n]*(?:\birm\b|\biwr\b|invoke-webrequest|invoke-restmethod|downloadstring)",
     "Выполнение загруженного кода ([scriptblock]::Create) запрещено политикой"),
]
DENY_TAIL = (" Скачайте файл, проверьте его (навык novaprom-tool-vetting) и запустите отдельно "
             "с разрешения пользователя.")

SECRET_RE = re.compile(r"(config\.inc\.php|dbconn\.php|\.settings\.php|id_rsa\b|\.pem\b|\.pfx\b|"
                       r"(?<![\w.])\.env(?:\.(?!example\b|sample\b|template\b|dist\b)[\w-]+)?(?![\w.]))", re.I)
SECRET_FILE = re.compile(r"(config\.inc\.php|dbconn\.php|\.settings\.php|id_rsa|\.pem$|\.pfx$|"
                         r"(^|[\\/])\.env(\.(?!example$|sample$|template$|dist$)[\w-]+)?$)", re.I)
CAD_RE = re.compile(r"SldWorks|win32com|comtypes|swconst|\.swp\b", re.I)
CONVERTER_RE = re.compile(r"ODAFileConverter|dwg2dxf|dxf2dwg|freecadcmd", re.I)
# Пакеты npx, проверенные novaprom-tool-vetting, — только с точной версией. Запуск без вопроса.
VETTED_NPX = {"@firecrawl/anydoc@0.2.4"}
CLOUD_UPLOAD_RE = re.compile(r"--ocr[\s=]+hosted|FIRECRAWL_API_(KEY|URL)|api\.firecrawl\.dev", re.I)
REST_RE = re.compile(r"/rest/\d+/", re.I)
WRAPPER_ONLY = re.compile(r"\s*(?:python3?(?:\.exe)?|py(?:\s+-3(?:\.\d+)?)?)\s+"
                          r"(?:\"[^\"]*b24_readonly\.py\"|'[^']*b24_readonly\.py'|\S*b24_readonly\.py)"
                          r"(?:\s+[^;&|`$<>\n]*)?\s*", re.I)
PY_NET_RE = re.compile(r"\b(urllib|requests|http\.client|httpx|aiohttp|socket|pycurl)\b")

REMOTE = {"ssh", "scp", "sftp", "rsync", "plink", "pscp", "winscp", "winscp.com", "ftp", "lftp", "telnet",
          "enter-pssession", "invoke-command", "new-pssession"}
DB = {"mysql", "mariadb", "psql", "sqlcmd", "mysqldump", "mysqladmin", "mysqlimport", "pg_dump", "pg_restore",
      "mariadb-dump", "sqlite3"}
PS_DELETE = {"remove-item", "ri", "rm", "del", "erase", "rd", "rmdir"}
MCP_VERBS = {"send", "forward", "reply", "trash", "delete", "share", "publish", "merge", "archive", "change",
             "remove", "apply", "mark", "label", "respond", "create", "update", "upload", "generate", "import",
             "push", "fork", "post", "add", "assign", "edit", "copy", "move", "resize", "comment", "enable",
             "disable", "trigger", "run", "write", "batch", "set", "reassign", "duplicate", "convert", "insert",
             "unarchive", "untrash", "unlabel", "unmark", "resolve", "install"}
MCP_READ_FIRST = {"get", "list", "search", "read", "fetch", "query", "describe", "view", "download", "help", "guide"}
READONLY_CMDS = {"ls", "dir", "cat", "type", "head", "tail", "grep", "rg", "egrep", "wc", "stat", "file", "less",
                 "more", "tree", "du", "get-childitem", "gci", "get-content", "gc", "select-string", "sls",
                 "get-item", "gi", "test-path", "resolve-path", "md5sum", "sha256sum", "get-filehash", "pwd", "cd",
                 "echo", "diff", "cmp"}


# ----------------------------------------------------------------- разбор команды
def segments(cmd: str) -> list[str]:
    """Простые команды, разделённые ; & | && || и переводом строки."""
    return [s for s in re.split(r"\|\||&&|[;|&\n]", cmd) if s.strip()]


def tokens(seg: str) -> list[str]:
    return re.findall(r'"[^"]*"|\'[^\']*\'|\S+', seg)


def unquote(t: str) -> str:
    return t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t


def command_word(toks: list[str]) -> tuple[str, list[str]]:
    """Имя программы (без пути и .exe) и её аргументы, пропуская sudo/env/VAR=… и т.п."""
    i = 0
    while i < len(toks):
        t = unquote(toks[i]).lower()
        base = re.split(r"[\\/]", t)[-1]
        if base in WRAPPERS or re.match(r"^[a-z_][a-z0-9_]*=", t) or (t.startswith("-") and i > 0):
            i += 1
            continue
        if base.endswith(".exe"):
            base = base[:-4]
        return base, [unquote(x) for x in toks[i + 1:]]
    return "", []


def rm_recursive(name: str, args: list[str]) -> bool:
    for a in args:
        al = a.lower()
        if al in ("--recursive", "-recurse") or (name in ("del", "erase", "rd", "rmdir") and al == "/s"):
            return True
        if al.startswith("--") or not al.startswith("-") or len(al) < 2:
            continue
        flags = a[1:]
        if "recurse".startswith(al[1:]) and name in PS_DELETE:   # PowerShell: -r, -re, -rec, ... -Recurse
            return True
        if set(flags) <= set("rRfivdIP") and ("r" in flags or "R" in flags):   # bash: -rf, -R, -fr …
            return True
    return False


def git_danger(args: list[str]) -> str | None:
    i = 0
    while i < len(args) and args[i].startswith("-"):          # глобальные опции: -C path, -c k=v
        i += 2 if args[i] in ("-C", "-c") else 1
    if i >= len(args):
        return None
    sub, rest = args[i], args[i + 1:]
    if sub == "push":
        if any(a in ("--force", "-f", "--mirror", "--delete", "-d", "--prune") or a.startswith("--force")
               for a in rest):
            return "git push с перезаписью или удалением в удалённом репозитории"
        if any(a.startswith("+") or (a.startswith(":") and len(a) > 1) or (":" in a and a.split(":", 1)[0] == "")
               for a in rest if not a.startswith("-")):
            return "git push с принудительным/удаляющим refspec (+ref или :ref)"
    if sub == "reset" and "--hard" in rest:
        return "git reset --hard (потеря изменений)"
    if sub == "clean" and any(re.match(r"^-[a-zA-Z]*f", a) or a == "--force" for a in rest):
        return "git clean (удаление неотслеживаемых файлов)"
    if sub == "checkout" and any(a in (".", "--", "-f", "--force") for a in rest):
        return "git checkout с отбрасыванием изменений"
    if sub == "restore" and not ("--staged" in rest and "--worktree" not in rest and "-W" not in rest):
        return "git restore (отбрасывание изменений рабочей копии)"
    if sub == "branch" and (any(a.startswith("-D") for a in rest) or
                            ("--delete" in rest and ("--force" in rest or "-f" in rest))):
        return "принудительное удаление ветки git"
    if sub == "stash" and rest[:1] and rest[0] in ("drop", "clear"):
        return "удаление сохранённых изменений git stash"
    if sub in ("filter-branch", "filter-repo"):
        return "перезапись истории git"
    return None


def http_write(name: str, args: list[str]) -> bool:
    if name == "curl":
        for j, a in enumerate(args):                           # флаги curl регистрозависимы: -d ≠ -D, -F ≠ -f
            if a in ("-X", "--request") and j + 1 < len(args) and args[j + 1].upper() in ("POST", "PUT", "PATCH", "DELETE"):
                return True
            if re.match(r"^-X(POST|PUT|PATCH|DELETE)$", a, re.I) or re.match(r"^--request=(POST|PUT|PATCH|DELETE)$", a, re.I):
                return True
            if a in ("-d", "-F", "-T", "--json", "--form", "--upload-file") or a.startswith(("--data", "--form", "-d@", "--json")):
                return True
            if re.match(r"^-[a-zA-Z]*[dFT]", a) and not a.startswith("--"):
                return True
    if name == "wget":
        return any(a.startswith(("--post-data", "--post-file", "--body-data", "--body-file")) or
                   re.match(r"^--method=(post|put|patch|delete)$", a, re.I) for a in args)
    if name in ("invoke-webrequest", "invoke-restmethod", "iwr", "irm"):
        low = [a.lower() for a in args]
        for j, a in enumerate(low):
            if a.startswith("-method") and j + 1 < len(low) and low[j + 1] in ("post", "put", "patch", "delete"):
                return True
            if a in ("-body", "-infile", "-form"):
                return True
    return False


def installer(name: str, args: list[str]) -> str | None:
    a0 = args[0].lower() if args else ""
    rest = " ".join(args).lower()
    if re.match(r"^pip(\d+(\.\d+)?)?$", name) and a0 == "install":
        return "Установка Python-пакета"
    if re.match(r"^(python\d*(\.\d+)?|py)$", name) and re.search(r"-m\s+pip\s+install\b", rest):
        return "Установка Python-пакета"
    if name == "uv" and (a0 == "add" or re.match(r"^(pip|tool)\s+install\b", rest)):
        return "Установка Python-пакета (uv)"
    if name == "pipx" and a0 in ("install", "run", "inject"):
        return "Установка/запуск Python-пакета (pipx)"
    if name in ("conda", "mamba", "micromamba") and a0 in ("install", "create", "update"):
        return "Установка пакета conda"
    if name in ("npm", "pnpm", "yarn", "bun") and a0 in ("install", "i", "add", "ci", "update", "up", "upgrade", "x", "dlx"):
        return "Установка npm-пакета"
    if name in ("npx", "uvx", "pnpx", "bunx"):
        pkgs = [a for a in args if not a.startswith("-")]
        if name == "npx" and pkgs and pkgs[0] in VETTED_NPX:
            return None   # проверенный пакет с закреплённой версией (см. VETTED_NPX)
        return "Запуск пакета из реестра (npx/uvx) — сторонний код"
    if name in ("winget", "choco", "scoop", "apt", "apt-get", "dnf", "yum", "brew", "cargo", "gem", "go") and a0 in ("install", "add", "upgrade"):
        return "Установка программы"
    if name in ("install-module", "install-package", "install-script"):
        return "Установка модуля PowerShell"
    if name == "claude" and re.match(r"^(mcp\s+add|plugin\s+(install|marketplace\s+add))", rest):
        return "Подключение MCP/плагина"
    return None


# ----------------------------------------------------------------- защищённые пути
def protected_paths(cwd: str) -> list[str]:
    paths: list[str] = []
    env = os.environ.get("NOVAPROM_PROTECTED_PATHS", "")
    seps = "[;\n" + re.escape(os.pathsep) + "]"
    paths += [p for p in re.split(seps, env) if p.strip()]
    candidates = [Path(os.environ.get("CLAUDE_PROJECT_DIR", cwd or ".")) / ".claude" / "protected-paths.txt",
                  Path.home() / ".claude" / "novaprom-protected-paths.txt"]
    for f in candidates:
        try:
            raw = f.read_bytes()
        except OSError:
            continue
        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            text = raw.decode("utf-16", errors="replace")
        else:
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                text = raw.decode("cp1251", errors="replace")
        for line in text.splitlines():
            line = line.strip().strip('"')
            if line and not line.startswith("#"):
                paths.append(line)
    return [norm(p.strip()) for p in paths]


def norm(p: str, base: str = "") -> str:
    p = os.path.expanduser(p)
    if base and not os.path.isabs(p):
        p = os.path.join(base, p)
    return os.path.normcase(os.path.abspath(p))


def under(path: str, roots: list[str], base: str = "") -> str | None:
    p = norm(path, base)
    for r in roots:
        if p == r or p.startswith(r.rstrip("\\/") + os.sep):
            return r
    return None


# ----------------------------------------------------------------- решение
def decide_shell(cmd: str, cwd: str, profile: str) -> tuple[str, str] | None:
    low = cmd.lower()
    wrapper_only = bool(WRAPPER_ONLY.fullmatch(cmd))
    for pat, why in DENY_REGEX:
        if re.search(pat, low):
            return "deny", why + "." + DENY_TAIL
    segs = segments(cmd)
    parsed = [command_word(tokens(s)) for s in segs]
    # скачивание и передача по конвейеру интерпретатору: curl … | [tee …|] sh / python / iex
    pipe_parts = [command_word(tokens(s))[0] for s in re.split(r"(?<!\|)\|(?!\|)", cmd) if s.strip()]
    for j, name in enumerate(pipe_parts):
        if name in DOWNLOADERS and any(INTERPRETERS.match(n or "") for n in pipe_parts[j + 1:]):
            return "deny", "Скачивание и выполнение скрипта из интернета (curl|sh, irm|iex) запрещено политикой." + DENY_TAIL

    if profile == "bitrix-readonly" and not wrapper_only:
        if REST_RE.search(cmd) or "/rest/" in low:
            return "deny", "Режим аудита Bitrix24: обращения к /rest/ только через b24_readonly.py."
        for name, args in parsed:
            if name in DOWNLOADERS or name in ("http", "https", "httpie", "nc", "ncat", "telnet"):
                return "deny", "Режим аудита Bitrix24 (только чтение): сетевые клиенты запрещены — только b24_readonly.py."
            if name in REMOTE:
                return "deny", "Режим аудита Bitrix24 (только чтение): подключение к серверу запрещено."
            if name in DB:
                return "deny", "Режим аудита Bitrix24 (только чтение): прямой доступ к БД запрещён."
            if name == "php":
                return "deny", "Режим аудита Bitrix24 (только чтение): запуск PHP запрещён."
            if re.match(r"^(python\d*(\.\d+)?|py|node|perl|ruby|pwsh|powershell)$", name) and PY_NET_RE.search(low):
                return "deny", "Режим аудита Bitrix24 (только чтение): сетевой код в обход b24_readonly.py запрещён."

    reasons: list[str] = []
    for name, args in parsed:
        if not name:
            continue
        if name in ("rm", "rmdir", "rd", "del", "erase", "ri", "remove-item") and rm_recursive(name, args):
            reasons.append("Рекурсивное удаление файлов")
        if name == "find" and any(a in ("-delete",) for a in args) or (name == "find" and "-exec" in args and
                                                                        any(a in ("rm", "/bin/rm") for a in args)):
            reasons.append("Удаление файлов через find")
        if name == "git":
            g = git_danger(args)
            if g:
                reasons.append(g)
        if name in REMOTE:
            reasons.append("Подключение к удалённому серверу (сайт, Bitrix24, хостинг)")
        if name in DB:
            reasons.append("Доступ к базе данных")
        if http_write(name, args):
            reasons.append("HTTP-запрос с изменением данных (POST/PUT/DELETE/загрузка)")
        inst = installer(name, args)
        if inst:
            reasons.append(inst + " — сначала проверка (novaprom-tool-vetting)")
    if REST_RE.search(cmd) and not wrapper_only:
        reasons.append("Обращение к REST API Bitrix24 в обход read-only клиента b24_readonly.py")
    if CAD_RE.search(cmd):
        reasons.append("Автоматизация SolidWorks (управление CAD) — требуется явное разрешение")
    if CONVERTER_RE.search(cmd):
        reasons.append("Запуск конвертера/CAD-программы на файлах")
    if CLOUD_UPLOAD_RE.search(cmd):
        reasons.append("Отправка документа в облако Firecrawl (--ocr hosted) — только для открытых документов")
    if SECRET_RE.search(cmd):
        reasons.append("Доступ к файлу с секретами")
    roots = protected_paths(cwd)
    if roots:
        ncmd = os.path.normcase(cmd)
        hit = next((r for r in roots if r and r in ncmd), None)
        if not hit:
            for t in tokens(cmd)[:300]:
                t = unquote(t)
                if t.startswith("-") or not (re.search(r"[\\/]", t) or t.startswith((".", "~"))):
                    continue
                try:
                    hit = under(t, roots, cwd or os.getcwd())
                except (ValueError, OSError):
                    hit = None
                if hit:
                    break
        read_only = all(name in READONLY_CMDS or (name == "find" and "-delete" not in args and "-exec" not in args)
                        for name, args in parsed if name)
        if hit and not read_only:
            reasons.append(f"Команда затрагивает защищённый путь {hit}")
    if reasons:
        return "ask", "НОВАПРОМ: требуется подтверждение — " + "; ".join(dict.fromkeys(reasons))
    return None


def decide(data: dict, profile: str) -> tuple[str, str] | None:
    if not isinstance(data, dict):
        return "ask", "НОВАПРОМ: хук получил вызов в неизвестном формате — проверьте действие вручную"
    tool = str(data.get("tool_name") or "")
    ti = data.get("tool_input")
    ti = ti if isinstance(ti, dict) else {}
    cwd = str(data.get("cwd") or "")
    if tool in ("Bash", "PowerShell"):
        cmd = ti.get("command")
        cmd = cmd if isinstance(cmd, str) else (json.dumps(cmd, ensure_ascii=False) if cmd else "")
        return decide_shell(cmd, cwd, profile)
    if tool in ("Write", "Edit", "NotebookEdit", "MultiEdit"):
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        path = str(path)
        if not path:
            return None
        if SECRET_FILE.search(path):
            return "ask", f"НОВАПРОМ: изменение файла с секретами/конфигурацией ({path})"
        r = under(path, protected_paths(cwd), cwd)
        if r:
            return "ask", f"НОВАПРОМ: изменение в защищённой папке {r} (производственные данные/действующие системы)"
        return None
    if tool.startswith("mcp__"):
        parts = tool.split("__")
        action = parts[-1] if len(parts) >= 3 else tool
        words = [w for w in re.split(r"[_\-]+", action.lower()) if w]
        if words and words[0] in MCP_READ_FIRST:
            return None
        if set(words) & MCP_VERBS:
            return "ask", (f"НОВАПРОМ: действие во внешней системе ({tool}) — отправка, создание, изменение, "
                           "удаление или публикация требует подтверждения")
    return None


def main() -> int:
    profile = "default"
    if "--profile" in sys.argv:
        i = sys.argv.index("--profile")
        if i + 1 < len(sys.argv):
            profile = sys.argv[i + 1]
    try:
        raw = sys.stdin.buffer.read() if hasattr(sys.stdin, "buffer") else sys.stdin.read().encode("utf-8")
        data = json.loads(raw.decode("utf-8-sig", errors="replace"))
        res = decide(data, profile)
    except Exception as e:  # закрыто при сбое: лучше лишний вопрос, чем пропущенная опасная команда
        res = ("ask", f"НОВАПРОМ: хук безопасности не смог проверить вызов ({type(e).__name__}) — проверьте вручную")
    if not res:
        return 0
    decision, reason = res
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision,
                                  "permissionDecisionReason": reason}}
    text = json.dumps(out, ensure_ascii=False)
    if hasattr(sys.stdout, "buffer"):
        sys.stdout.buffer.write(text.encode("utf-8") + b"\n")
        sys.stdout.flush()
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
