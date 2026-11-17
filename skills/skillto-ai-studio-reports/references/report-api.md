# Local report API

Base URL: `http://127.0.0.1:8880`, loopback only.

- `GET /api/reports/catalog`: knowledge bases, projects, reports, Metabase URL and configuration status. Reports include `id`, `knowledgeBaseId`, `projectId`, `metabaseDashboardId`, `cardIds`, `status`.
- `GET /api/reports/item?id=<reportId>`: registry entry and current Metabase dashboard.
- `GET /api/reports/embed?id=<reportId>`: short-lived guest token and instance URL. Do not print or store the token.
- `POST /api/reports` with JSON `{"action":"create","name":"…","knowledgeBaseId":"…","projectId":"…","description":"…","sourceTableId":"…"}`.
- `POST /api/reports` with `action:"update"`, `reportId`, and the fields to change. A move sends the destination knowledge-base and project IDs together.
- `POST /api/reports` with `{"action":"archive"|"restore","reportId":"…"}`. Archive hides it from the normal tree and keeps restoration possible.
- `POST /api/reports` with `{"action":"content","reportId":"…","operation":"read"|"read_card"|"create_card"|"update_card"|"archive_card"|"update_dashboard",…}`. A card operation uses `cardId` and `card`; dashboard updates use `dashboard`.
- `POST /api/reports/refresh`: reload frozen raw observations into the reporting database. It does not recrawl or rewrite the source account table.

A card is a Metabase saved question payload, including `name`, `display`, `visualization_settings`, and `dataset_query`; the service supplies `dashboard_id`. `update_dashboard` accepts `dashcards`, `parameters`, `tabs`, `description`, and `name`. A `dashcards` update is the **complete** list, so read the dashboard first and preserve cards you want to retain.

Errors are JSON with `error` and a non-2xx status. Metabase unavailability returns 503/502; do not retry mutations blindly. Read a report back before claiming success.

The frozen source is account table `56fa8754-8d40-4225-8541-0be4729ade73`. The reporting DB contains `account_roster`, `video_observations`, `account_month_coverage`, and `account_snapshots`; views `account_month_metrics` and `group_month_metrics` make coverage visible. A null metric is unavailable, never zero.
