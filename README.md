track-cli
=========

A minimalist terminal app that helps track working hours per client and task.

Install
-------

- Ensure Python 3.9+
- From the repo root:

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

If flags are omitted, the command starts an interactive session with arrow-key pickers for client and task, plus a styled description prompt.

Log files are created under `TRACK_LOG_PATH` with names like `YYYYMMDD-<n>---<client>---open.log` and contain:

```
Task: <task>
Description: <description>
Start time: <ISO local datetime>
...
End time: <ISO local datetime>
```

The `report` command aggregates total hours and breaks down by task over a period such as `this week`, `last month`, `this quarter`, `last year`. You can also run `track report` without flags to pick client and period interactively.


