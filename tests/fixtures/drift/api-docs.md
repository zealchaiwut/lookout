# API Reference

This document describes the available REST endpoints.

## Endpoints

`GET /v1/widgets` — returns all widgets for the authenticated user.

**Parameters:**
- `page` (int, optional) — page number for pagination
- `limit` (int, optional) — number of results per page (default 20)

**Response:**
```json
{
  "widgets": [...],
  "total": 42
}
```

`GET /v1/users` — returns user profile information.

`POST /v1/widgets` — creates a new widget.
