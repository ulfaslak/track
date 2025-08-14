from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, date
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
import questionary
from rich.panel import Panel
from rich import box

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Track working hours by client and task.")
console = Console()


# ---------------------------
# Utilities
# ---------------------------

LOG_ENV_VAR = "TRACK_LOG_PATH"
CONFIG_FILE = Path.home() / ".track_config"
FILENAME_PATTERN = re.compile(r"^(\d{8})-(\d+)---(.+?)---(open|closed)\.log$")

# Period options used in interactive selection and validation
PERIOD_OPTIONS = [
    "today",
    "this week", "last week",
    "this month", "last month",
    "this quarter", "last quarter",
    "this year", "last year",
]


def _read_config_path() -> Optional[str]:
    if not CONFIG_FILE.exists():
        return None
    try:
        content = CONFIG_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not content:
        return None
    # Support either raw path or KEY=VALUE
    if "=" in content:
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                if key.strip() == LOG_ENV_VAR:
                    return val.strip()
        return None
    return content


def _write_config_path(path_str: str) -> None:
    try:
        CONFIG_FILE.write_text(f"{LOG_ENV_VAR}={path_str}\n", encoding="utf-8")
        try:
            os.chmod(CONFIG_FILE, 0o600)
        except Exception:
            pass
    except Exception as e:
        console.print(f"[bold red]Failed to write config:[/bold red] {e}")


def _ensure_viable_directory(path_str: str) -> Optional[Path]:
    try:
        p = Path(path_str).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        # Check writability
        if not os.access(p, os.W_OK):
            return None
        return p
    except Exception:
        return None


def _is_interactive() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def _prompt_for_log_dir() -> Path:
    console.print(Panel.fit(
        "[bold yellow]Log path not configured.[/bold yellow]\n"
        "Please enter a folder to store your time logs.",
        title="Configure log path",
        border_style="yellow",
    ))
    default_path = str(Path.home() / "track_logs")
    while True:
        if _is_interactive():
            entered = questionary.text("Log folder path", default=default_path).ask() or ""
        else:
            entered = input(f"Log folder path [{default_path}]: ") or default_path
        p = _ensure_viable_directory(entered)
        if p is not None:
            _write_config_path(str(p))
            console.print(f"[green]Saved[/green] log path to [bold]{CONFIG_FILE}[/bold]")
            return p
        console.print("[red]That path is not writable or invalid. Try again.[/red]")


def get_log_dir() -> Path:
    # 1) Environment variable overrides everything
    env = os.getenv(LOG_ENV_VAR)
    if env:
        p = _ensure_viable_directory(env)
        if p is not None:
            return p
        console.print(f"[yellow]{LOG_ENV_VAR} is set but not usable. Falling back to config/prompt.[/yellow]")

    # 2) Read from config file if present
    conf = _read_config_path()
    if conf:
        p = _ensure_viable_directory(conf)
        if p is not None:
            return p
        console.print("[yellow]Configured log path is not usable. You'll be prompted to set a new one.[/yellow]")

    # 3) Prompt the user and persist to config
    return _prompt_for_log_dir()


def now_local_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_yyyymmdd() -> str:
    return datetime.now().strftime("%Y%m%d")


def next_sequence_for_today(log_dir: Path, yyyymmdd: str) -> int:
    max_seq = 0
    for f in log_dir.glob(f"{yyyymmdd}-*---*---*.log"):
        m = FILENAME_PATTERN.match(f.name)
        if not m:
            continue
        if m.group(1) == yyyymmdd:
            try:
                seq = int(m.group(2))
                if seq > max_seq:
                    max_seq = seq
            except ValueError:
                continue
    return max_seq + 1


def build_filename(yyyymmdd: str, seq: int, client: str, status: str) -> str:
    # Sanitize client for safe filename usage; keep it readable
    safe_client = (
        client
        .replace("/", "-")
        .replace("\\", "-")
        .replace("*", "-")
        .replace("?", "-")
        .replace("[", "(")
        .replace("]", ")")
        .replace(":", "-")
        .replace("<", "(")
        .replace(">", ")")
        .replace("|", "-")
        .replace('"', "'")
    )
    # Avoid trailing spaces or dots which are problematic on Windows
    safe_client = safe_client.rstrip(" .")
    return f"{yyyymmdd}-{seq}---{safe_client}---{status}.log"


def parse_log_file(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return data
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


def find_open_logs(log_dir: Path) -> List[Path]:
    return sorted([p for p in log_dir.glob("*---open.log") if FILENAME_PATTERN.match(p.name)])


def duration_hours(start: str, end: str) -> float:
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        start_dt = datetime.strptime(start, fmt)
        end_dt = datetime.strptime(end, fmt)
    except Exception:
        return 0.0
    hours = (end_dt - start_dt).total_seconds() / 3600.0
    return max(0.0, hours)


def list_tasks_for_client(log_dir: Path, client: str) -> List[str]:
    tasks = set()
    for path in log_dir.glob("*.log"):
        m = FILENAME_PATTERN.match(path.name)
        if not m:
            continue
        if m.group(3) != client:
            continue
        meta = parse_log_file(path)
        t = meta.get("Task")
        if t:
            tasks.add(t)
    return sorted(tasks, key=lambda s: s.lower())


def list_clients(log_dir: Path) -> List[str]:
    clients = set()
    for path in log_dir.glob("*.log"):
        m = FILENAME_PATTERN.match(path.name)
        if m:
            clients.add(m.group(3))
    return sorted(clients, key=lambda s: s.lower())


def parse_period(period_description: str) -> Tuple[datetime, datetime]:
    pd = period_description.strip().lower()
    today = date.today()

    def week_range(d: date) -> Tuple[date, date]:
        start = d - timedelta(days=d.weekday())
        end = start + timedelta(days=6)
        return start, end

    def month_range(d: date) -> Tuple[date, date]:
        start = d.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1, day=1)
        else:
            next_month = start.replace(month=start.month + 1, day=1)
        end = next_month - timedelta(days=1)
        return start, end

    def quarter_range(d: date) -> Tuple[date, date]:
        q = (d.month - 1) // 3
        start_month = q * 3 + 1
        start = date(d.year, start_month, 1)
        if start_month + 3 > 12:
            next_q = date(d.year + 1, 1, 1)
        else:
            next_q = date(d.year, start_month + 3, 1)
        end = next_q - timedelta(days=1)
        return start, end

    def year_range(d: date) -> Tuple[date, date]:
        start = date(d.year, 1, 1)
        end = date(d.year, 12, 31)
        return start, end

    if pd == "today":
        s = e = today
    elif pd.startswith("this "):
        unit = pd.split(" ", 1)[1]
        if unit == "week":
            s, e = week_range(today)
        elif unit == "month":
            s, e = month_range(today)
        elif unit == "quarter":
            s, e = quarter_range(today)
        elif unit == "year":
            s, e = year_range(today)
        else:
            raise ValueError("Unknown period. Use: week, month, quarter, year")
    elif pd.startswith("last "):
        unit = pd.split(" ", 1)[1]
        if unit == "week":
            s, e = week_range(today - timedelta(weeks=1))
        elif unit == "month":
            d = (today.replace(day=1) - timedelta(days=1))
            s, e = month_range(d)
        elif unit == "quarter":
            month = ((today.month - 1) // 3) * 3 + 1
            this_q_start = date(today.year, month, 1)
            d = this_q_start - timedelta(days=1)
            s, e = quarter_range(d)
        elif unit == "year":
            s = date(today.year - 1, 1, 1)
            e = date(today.year - 1, 12, 31)
        else:
            raise ValueError("Unknown period. Use: week, month, quarter, year")
    else:
        raise ValueError("Use 'this <period>' or 'last <period>'")

    start_dt = datetime.combine(s, datetime.min.time())
    end_dt = datetime.combine(e, datetime.max.time())
    return start_dt, end_dt


def within_period(file_date: str, start: datetime, end: datetime) -> bool:
    try:
        d = datetime.strptime(file_date, "%Y%m%d")
    except Exception:
        return False
    return start <= d <= end


# ---------------------------
# Commands
# ---------------------------

@app.command()
def start(
    c: Optional[str] = typer.Option(None, "-c", "--client", help="Client name"),
    t: Optional[str] = typer.Option(None, "-t", "--task", help="Task name"),
    d: Optional[str] = typer.Option(None, "-d", "--description", help="Task description"),
):
    """Start a tracking log."""
    log_dir = get_log_dir()

    if not c:
        existing_clients = list_clients(log_dir)
        if existing_clients:
            choices = existing_clients + ["[Create new client]"]
            selected = questionary.select(
                "Select client",
                choices=choices,
                use_shortcuts=True,
            ).ask()
            if selected == "[Create new client]" or selected is None:
                # If user cancels or chooses create new, prompt for input
                while True:
                    c = questionary.text("New client name").ask()
                    if c and c.strip():
                        c = c.strip()
                        break
            else:
                c = selected
        else:
            c = questionary.text("Client").ask() or ""
            if not c.strip():
                console.print("[red]Client name cannot be empty.[/red]")
                raise typer.Exit(1)
    if not t:
        # Offer selection from previous tasks or allow typing a new one
        existing_tasks = list_tasks_for_client(log_dir, c)
        if existing_tasks:
            choices = existing_tasks + ["[Create new task]"]
            selected = questionary.select(
                f"Select task for {c}",
                choices=choices,
                use_shortcuts=True,
            ).ask()
            if selected == "[Create new task]" or selected is None:
                while True:
                    t = questionary.text("New task name").ask()
                    if t and t.strip():
                        t = t.strip()
                        break
            else:
                t = selected
        else:
            t = questionary.text("Task").ask() or ""
            if not t.strip():
                console.print("[red]Task name cannot be empty.[/red]")
                raise typer.Exit(1)
    if not d:
        # Description is optional; allow empty input
        d = questionary.text("Description").ask() or ""

    yyyymmdd = today_yyyymmdd()
    seq = next_sequence_for_today(log_dir, yyyymmdd)
    filename = build_filename(yyyymmdd, seq, c, "open")
    path = log_dir / filename

    lines = [
        f"Task: {t}",
        f"Description: {d}",
        f"Start time: {now_local_iso()}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    console.print(Panel.fit(
        f"[bold green]Started[/bold green] {c}\n[dim]{path.name}[/dim]",
        title="track start",
        border_style="green",
    ))


@app.command()
def end():
    """End an open tracking log."""
    log_dir = get_log_dir()
    open_logs = find_open_logs(log_dir)
    if not open_logs:
        console.print("[bold yellow]No open logs found.[/bold yellow]")
        raise typer.Exit()

    chosen: Path
    if len(open_logs) == 1:
        chosen = open_logs[0]
    else:
        file_choices = [p.name for p in open_logs]
        selected = questionary.select(
            "Select log to close",
            choices=file_choices,
            use_shortcuts=True,
        ).ask()
        if not selected:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(1)
        chosen = next(p for p in open_logs if p.name == selected)

    # Append end time and rename to closed
    with chosen.open("a", encoding="utf-8") as f:
        f.write(f"End time: {now_local_iso()}\n")

    m = FILENAME_PATTERN.match(chosen.name)
    if not m:
        console.print(f"[bold red]Unexpected filename format:[/bold red] {chosen.name}")
        raise typer.Exit(1)
    yyyymmdd, seq, client = m.group(1), m.group(2), m.group(3)
    new_name = build_filename(yyyymmdd, int(seq), client, "closed")
    new_path = chosen.with_name(new_name)
    chosen.rename(new_path)

    console.print(Panel.fit(
        f"[bold green]Closed[/bold green] {client}\n[dim]{new_path.name}[/dim]",
        title="track end",
        border_style="green",
    ))


@app.command()
def report(
    c: Optional[str] = typer.Option(None, "-c", "--client", help="Client name"),
    p: Optional[str] = typer.Option(None, "-p", "--period", help="Period, e.g. 'this week', 'last month'"),
):
    """Show aggregated time for a client and period, broken down by task."""
    log_dir = get_log_dir()

    # Interactive choices if needed
    if not c:
        clients = sorted({FILENAME_PATTERN.match(p.name).group(3)
                          for p in log_dir.glob("*.log") if FILENAME_PATTERN.match(p.name)})
        if not clients:
            console.print("[bold yellow]No logs found.[/bold yellow]")
            raise typer.Exit()
        selected = questionary.select(
            "Select client",
            choices=clients,
            use_shortcuts=True,
        ).ask()
        if not selected:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(1)
        c = selected

    if not p:
        options = PERIOD_OPTIONS
        selected = questionary.select(
            "Select period",
            choices=options,
            use_shortcuts=True,
        ).ask()
        if not selected:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(1)
        p = selected

    try:
        start_dt, end_dt = parse_period(p or "this week")
    except Exception as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(code=1)

    # Aggregate
    task_to_hours: Dict[str, float] = {}
    total_hours = 0.0
    for path in log_dir.glob("*.log"):
        m = FILENAME_PATTERN.match(path.name)
        if not m:
            continue
        file_client = m.group(3)
        status = m.group(4)
        if file_client != c or status != "closed":
            continue
        meta = parse_log_file(path)
        start = meta.get("Start time")
        end = meta.get("End time")
        task = meta.get("Task", "Unknown")
        if not start or not end:
            continue
        try:
            start_ts = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
        except Exception:
            # Fallback to filename date if parsing fails
            file_date = m.group(1)
            try:
                start_ts = datetime.strptime(file_date, "%Y%m%d")
            except Exception:
                continue
        if not (start_dt <= start_ts <= end_dt):
            continue
        hours = duration_hours(start, end)
        task_to_hours[task] = task_to_hours.get(task, 0.0) + hours
        total_hours += hours

    # Render report
    title = f"Report: {c} — {p}"
    table = Table(title=title, box=box.SIMPLE_HEAVY)
    table.add_column("Task", style="bold")
    table.add_column("Hours", justify="right", style="cyan")
    if task_to_hours:
        for task, hours in sorted(task_to_hours.items(), key=lambda kv: kv[0].lower()):
            table.add_row(task, f"{hours:.2f}")
    else:
        table.add_row("No data", "0.00")
    console.print(table)

    console.print(Panel.fit(f"Total: [bold]{total_hours:.2f}[/bold] hours",
                            border_style="cyan", title="Summary"))


@app.command()
def status():
    """List currently open logs and their running durations."""
    log_dir = get_log_dir()
    open_logs = find_open_logs(log_dir)
    if not open_logs:
        console.print("[bold yellow]No open logs found.[/bold yellow]")
        raise typer.Exit()

    def humanize_hours(hours: float) -> str:
        total_seconds = int(hours * 3600)
        hrs = total_seconds // 3600
        mins = (total_seconds % 3600) // 60
        return f"{hrs}h {mins:02d}m"

    table = Table(title="Open tracks", box=box.SIMPLE_HEAVY)
    table.add_column("Client", style="bold")
    table.add_column("Task")
    table.add_column("Start", style="cyan")
    table.add_column("Elapsed", justify="right", style="green")
    table.add_column("File", style="dim")

    total_running_hours = 0.0
    for p in open_logs:
        m = FILENAME_PATTERN.match(p.name)
        client = m.group(3) if m else "?"
        meta = parse_log_file(p)
        task = meta.get("Task", "?")
        start = meta.get("Start time")
        elapsed_str = "-"
        hours = 0.0
        if start:
            try:
                now_str = now_local_iso()
                hours = duration_hours(start, now_str)
                elapsed_str = humanize_hours(hours)
                total_running_hours += hours
            except Exception:
                pass
        table.add_row(client, task, start or "-", elapsed_str, p.name)

    console.print(table)
    console.print(Panel.fit(f"Total running: [bold]{total_running_hours:.2f}[/bold] hours",
                            border_style="cyan", title="Summary"))

if __name__ == "__main__":
    app()


