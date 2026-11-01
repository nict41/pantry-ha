# Pantry for Home Assistant

Receives your food list from the Pantry Android app and turns it into Home
Assistant sensors and events. What you do with them is up to you: dashboards,
reminders, a morning briefing.

The link is one way. The app pushes to Home Assistant, and Home Assistant never
changes anything in the app.

## Install

1. In HACS, open the three-dot menu, choose **Custom repositories**, and add
   `https://github.com/nict41/pantry-ha` with type **Integration**.
2. Download **Pantry** and restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration > Pantry**.
4. Copy the link it shows into the Pantry app under **Settings > Home Assistant**,
   then press **Sync now**.

**Configure** on the integration shows the link again. Treat it like a password:
anyone who has it can replace your list.

The link only works if your phone can reach Home Assistant, so to sync away from
home it needs to use an address that works from outside.

## Entities

| Entity | State | Attributes |
|---|---|---|
| `sensor.pantry_items` | Number of items | `items` (full list), `expiring_soon`, `expired`, `needs_date`, `frozen` |
| `sensor.pantry_expiring_soon` | Items within the app's warning period | `items` (names) |
| `sensor.pantry_expired` | Items past their date | `items` (names) |
| `sensor.pantry_needs_a_date` | Items with no date | `items` (names) |
| `sensor.pantry_frozen` | Items in the freezer | `items` (names) |
| `sensor.pantry_last_sync` | When the app last pushed | |

Each entry in `items` on `sensor.pantry_items` has the fields in
[the push format](docs/PAYLOAD.md), plus `status` (`ok`, `expiring_soon`,
`expired`, `unknown` or `frozen`) and `days_left`.

Statuses and days left update at midnight on their own, so they stay right if
your phone is off. Items added or finished while it's off appear at its next sync.

## Events

Nothing fires for the first sync, so setting up doesn't announce your whole pantry.

| Event | When | Data |
|---|---|---|
| `pantry_item_added` | A new item arrives | The item |
| `pantry_item_removed` | An item has gone from the list, whether eaten, binned or deleted | The item |
| `pantry_item_status_changed` | An item's status changes | The item, `old_status`, `new_status` |

## Example

```yaml
automation:
  - alias: Tell me when food has gone out of date
    triggers:
      - trigger: event
        event_type: pantry_item_status_changed
        event_data:
          new_status: expired
    actions:
      - action: notify.notify
        data:
          message: "{{ trigger.event.data.name }} has gone out of date"
```
