# track

Dead simple terminal app to track your working hours across **clients** and **tasks**.

* ❌ No GUI
* ❌ No cloud
* ❌ No database
* ✅ Just plain text files and a CLI

Install
-------

Install from PyPI (recommended):

```bash
pip install track-cli
```

Or install from source for development:

```bash
pip install -e .
```

This provides the `track` command. On first run, you'll be prompted for a log folder. The choice is saved in `~/.track_config` and reused next time.

Usage
-----

```bash
track start -c <client> -t <task> -d <description>
track end
track report -c <client> -p "this week"
track status
```

If flags are omitted, the command starts **an interactive session** with arrow-key pickers for client and task, plus a styled description prompt (description is optional).

- `track start`: begin a new log. If `-c`/`-t` omitted, pick from history or create new. `-d` description is optional.
- `track end`: close an open log (choose which one if multiple are open).
- `track report`: aggregate hours by task for a client over a period.
  - Periods: `today`, or `this|last` `week|month|quarter|year` (e.g., `today`, `this month`).
- `track status`: list currently open logs and their running durations.

Log files are created in the folder specified in `~/.track_config` with names like `YYYYMMDD-<n>---<client>---open.log` and contain:

```
Task: <task>
Description: <description>
Start time: <ISO local datetime>
...
End time: <ISO local datetime>
```

The `report` command aggregates total hours and breaks down by task over a period such as `this week`, `last month`, `this quarter`, `last year`. You can also run `track report` without flags to pick client and period interactively.

Examples
--------

Start work (interactive):

```bash
track start
# ? Select client ▸ acme
# ? Select task for acme ▸ modeling
# ? Description ▸ (leave empty if you want)
```

Start work (non-interactive):

```bash
track start -c acme -t modeling -d "feature engineering"
```

Check what is currently running:

```bash
track status
# Open tracks
#   Client       Task        Start               Elapsed   File
#   acme  modeling    2025-01-05 09:12:00   1h 23m  20250105-1---acme---open.log
```

End the active session (choose which one if more than one is open):

```bash
track end
```

Summarize time spent for a client:

```bash
track report -c acme -p "today"
track report -c acme -p "this week"
track report -c acme -p "last month"
```