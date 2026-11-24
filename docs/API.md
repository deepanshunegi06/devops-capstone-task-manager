# Orbit Task Manager - REST API (v2)

All endpoints are JSON under `/api`. Authentication:

* **Bearer token** (`Authorization: Bearer <token>`) from `/api/auth/login` or `/api/auth/register`. Used by scripts / CLI / tests.
* **Session cookie** (the web app). Cookie-authenticated `POST/PUT/PATCH/DELETE` requests must send the
  header `X-CSRF-Token: <token>`. The token is in `<meta name="csrf-token">` on every HTML page.

Errors: `{"error": "<code>", "message": "...", "fields": {...optional}}` with 400/401/403/404/409/500.

## Common objects

```jsonc
// User
{"id": 1, "username": "deepanshu", "display_name": "Deepanshu", "avatar_color": "#7c5cff", "theme": "system", "initials": "DE"}
// Project
{"id": 3, "name": "Capstone", "color": "#7c5cff", "icon": "🚀", "role": "owner", "open_count": 7, "done_count": 4,
 "members": [{"user": User, "role": "owner|editor|viewer"}], "created_at": "..."}
// Label
{"id": 2, "name": "urgent", "color": "#ef4444", "open_count": 3}
// Task (list form)
{"id": 10, "title": "Write report", "description": "markdown-ish text", "status": "todo|in_progress|done",
 "priority": 1,                 // 1 = P1 urgent, 2 = high, 3 = medium, 4 = none/low (default 4)
 "due_date": "2026-11-25" | null, "due_time": "17:00" | null, "overdue": false,
 "recurrence": null | "daily" | "weekdays" | "weekly" | "monthly" | "yearly",
 "estimate_minutes": 30 | null, "position": 1000.0, "pinned": false,
 "project": {"id","name","color","icon"} | null,      // null = Inbox
 "labels": [Label-lite {"id","name","color"}],
 "assignee": User | null, "creator": User,
 "subtasks_total": 3, "subtasks_done": 1, "comments_count": 2, "focus_minutes": 50,
 "completed_at": null, "created_at": "...", "updated_at": "..."}
// Task (detail form, GET /api/tasks/<id>) adds:
 "subtasks": [{"id","title","done","position"}],
 "comments": [{"id","body","author": User,"created_at"}],
 "activity": [{"id","action","detail","actor": User,"created_at"}]
```

## Endpoints

| Method | Path | Body / query | Returns |
|---|---|---|---|
| POST | `/auth/register` | `{username, password, display_name?}` | `{user, token}` 201 |
| POST | `/auth/login` | `{username, password}` | `{user, token}` |
| GET | `/auth/me`, `/me` | | `{user}` |
| PATCH | `/me` | `{display_name?, theme?: light/dark/system, avatar_color?}` | `{user}` |
| GET | `/bootstrap` | | `{user, projects[], labels[], counts: {inbox, today, upcoming, overdue, completed_today, assigned}}` |
| GET | `/projects` | | `{projects[]}` |
| POST | `/projects` | `{name, color?, icon?}` | `{project}` 201 |
| PATCH | `/projects/<id>` | `{name?, color?, icon?}` (owner/editor) | `{project}` |
| DELETE | `/projects/<id>` | owner only, deletes its tasks | 204 |
| POST | `/projects/<id>/members` | `{username, role: editor/viewer}` (owner) | `{project}` |
| DELETE | `/projects/<id>/members/<user_id>` | owner | `{project}` |
| GET | `/labels` | | `{labels[]}` |
| POST | `/labels` | `{name, color?}` | `{label}` 201 |
| PATCH/DELETE | `/labels/<id>` | | `{label}` / 204 |
| GET | `/tasks` | `view=all/inbox/today/upcoming/overdue/completed/assigned`, `project_id`, `label_id`, `status`, `priority`, `q`, `include_done=1` | `{tasks[], count}` (done tasks excluded unless view=completed or include_done=1 or status=done) |
| POST | `/tasks` | Task fields + `label_ids[]`, `project_id`, `assignee_id` | `{task}` 201 |
| POST | `/tasks/parse` | `{text}` - preview only | `{parsed}` (see quick add) |
| POST | `/tasks/quick` | `{text, project_id?}` - parse + create | `{task, parsed}` 201 |
| GET | `/tasks/<id>` | | `{task}` (detail form) |
| PATCH | `/tasks/<id>` | any subset of fields | `{task}` |
| PUT | `/tasks/<id>` | full update, `title` required | `{task}` |
| DELETE | `/tasks/<id>` | soft delete (undo-able) | 204 |
| POST | `/tasks/<id>/restore` | undo delete | `{task}` |
| POST | `/tasks/<id>/complete` | `{done: true/false}` | `{task, next_task: Task or null}` (recurring tasks spawn the next one) |
| POST | `/tasks/<id>/duplicate` | | `{task}` 201 |
| POST | `/tasks/reorder` | `{ids: [..], status?: "todo"}` - sets order (and status for board moves) | `{tasks[]}` |
| POST | `/tasks/<id>/subtasks` | `{title}` | `{subtask}` 201 |
| PATCH | `/subtasks/<id>` | `{title?, done?}` | `{subtask}` |
| DELETE | `/subtasks/<id>` | | 204 |
| POST | `/tasks/<id>/comments` | `{body}` | `{comment}` 201 |
| DELETE | `/comments/<id>` | author only | 204 |
| GET | `/activity` | `limit` (default 30) | `{activity[]}` (with `task: {id,title}`) |
| GET | `/search` | `q` | `{tasks[] (max 8), projects[], labels[]}` |
| GET | `/analytics` | `days` (7-90, default 30) | see below |
| POST | `/focus` | `{minutes, task_id?}` - a finished Pomodoro | `{session, today_minutes}` 201 |
| GET | `/export.json`, `/export.csv` | | file download |
| GET | `/stats` | | `{counts:{todo,in_progress,done}, total}` (v1 compatibility) |

### Quick add grammar (`/tasks/parse`, `/tasks/quick`)

`Submit report tomorrow 5pm #Capstone @writing p1 ~45m every week +alice`

| Token | Meaning |
|---|---|
| `#Project` | existing project (case-insensitive; `#"Two words"` allowed) |
| `@label` | label (created if it does not exist) |
| `p1`..`p4` or `!1`..`!4` | priority |
| `today`, `tod`, `tomorrow`, `tmr`, `monday`..`sunday` / `mon`..`sun` (next occurrence), `next week`, `next month`, `in 3 days`, `in 2 weeks`, `2026-12-01`, `dec 5`, `5 dec` | due date |
| `5pm`, `5:30pm`, `17:00`, `at 9am` | due time |
| `every day`/`daily`, `every weekday`/`weekdays`, `every week`/`weekly`, `every monday`, `every month`/`monthly`, `every year`/`yearly` | recurrence (also sets a due date if none) |
| `~30m`, `~2h`, `~1h30m` | estimate |
| `+username` | assignee (must be a member of the project, or yourself) |

`parsed` = `{title, project: {id,name,color,icon}|null, labels: [names], priority, due_date, due_time, recurrence, estimate_minutes, assignee: User|null, tokens: [{type, text}]}`

### Analytics response

```jsonc
{"days": 30,
 "totals": {"open": 12, "done": 40, "overdue": 2, "due_today": 3, "focus_minutes": 350, "completed_this_week": 9},
 "completed_per_day": [{"date": "2026-11-01", "count": 3}, ...],   // length = days
 "created_per_day":   [{"date": "...", "count": 2}, ...],
 "focus_per_day":     [{"date": "...", "minutes": 50}, ...],
 "by_priority": {"1": 2, "2": 4, "3": 3, "4": 3},                   // open tasks
 "by_status": {"todo": 8, "in_progress": 4, "done": 40},
 "by_project": [{"id": 3, "name": "Capstone", "color": "#7c5cff", "icon": "🚀", "open": 5, "done": 9}],  // id null = Inbox
 "heatmap": [[0,...24 ints], ... 7 rows],                           // completions by weekday (Mon=0) x hour
 "streak": {"current": 4, "best": 9},
 "on_time_rate": 0.86,            // completed on/before due date, among completed tasks that had a due date
 "avg_completion_hours": 30.5}
```
