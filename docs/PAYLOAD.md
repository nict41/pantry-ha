# Pantry push format, schema 1

The Pantry Android app sends the whole current list to the integration's webhook.
HA never sends anything back except the reply below. There are no deltas, so a
missed push is repaired by the next one.

## Request

`POST <webhook url>` with `Content-Type: application/json`.

```json
{
  "schema": 1,
  "sequence": 1793548800123,
  "sent_at": "2026-11-01T18:00:00Z",
  "reason": "change",
  "notify_days_before": 3,
  "items": [
    {
      "id": "6f1c1d9e-...",
      "name": "Fresh double cream",
      "brand": "Asda",
      "quantity": "300ml",
      "category": "en:dairies",
      "food_group": "Dairy",
      "location": "fridge",
      "count": 1,
      "barcode": "5000000000000",
      "expiry_date": "2026-11-02",
      "printed_date": "2026-11-02",
      "opened_on": null,
      "added_at": "2026-10-30T12:00:00Z"
    }
  ]
}
```

| Field | Rule |
|---|---|
| `schema` | Required integer. Only 1 is supported. |
| `sequence` | Required positive integer: milliseconds since the epoch when the app built the payload. |
| `sent_at` | Required ISO 8601 UTC string. |
| `reason` | Required: `change`, `daily` or `manual`. |
| `notify_days_before` | Required integer, 0 to 30. |
| `items` | Required list, may be empty. |
| `id`, `name` | Required non-empty strings. `id` is stable for the item's life. |
| `count` | Required integer, at least 1. |
| `expiry_date` | `YYYY-MM-DD` or null. The date that decides status, after opened and defrosted rules. Null when frozen or undated. |
| `printed_date` | `YYYY-MM-DD` or null. The date on the pack. |
| `opened_on` | `YYYY-MM-DD` or null. |
| `location` | `fridge`, `cupboard`, `freezer`, another string, or null. |
| `brand`, `quantity`, `category`, `food_group`, `barcode`, `added_at` | String or null. |

Unknown fields, at either level, are ignored, so the app can add fields without
breaking older integrations.

## Status

The integration works out status itself so it stays right at midnight without
the phone:

1. `location` is `freezer`: `frozen`, `days_left` null.
2. `expiry_date` is null: `unknown`, `days_left` null.
3. `days_left = expiry_date - today` (HA's local date).
4. `days_left < 0`: `expired`.
5. `days_left <= notify_days_before`: `expiring_soon`.
6. Otherwise `ok`.

## Reply

HA answers 200 even for a webhook that doesn't exist, so the app must treat a
sync as delivered only when the JSON body has `"ok": true`.

| Case | Status | Body |
|---|---|---|
| Applied | 200 | `{"ok": true, "applied": true, "items": 18}` |
| `sequence` not newer than the stored one, and `reason` isn't `manual` | 200 | `{"ok": true, "applied": false, "items": 18}` |
| Not JSON or fails validation | 400 | `{"ok": false, "error": "invalid_payload"}` |
| `schema` isn't 1 | 400 | `{"ok": false, "error": "unsupported_schema"}` |

`manual` always applies, so the app's sync button recovers from a stored
sequence that is too high, such as after a wrong phone clock. In the
`applied: false` row, `items` is the stored count.
