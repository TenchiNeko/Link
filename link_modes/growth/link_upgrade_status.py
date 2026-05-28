
#!/usr/bin/env python3
from __future__ import annotations

from html import escape


def _load_registry():
    import link_upgrade_registry
    return link_upgrade_registry.UPGRADES, link_upgrade_registry.NEXT_UPGRADE


def upgrade_status_rows() -> list[dict]:
    upgrades, next_upgrade = _load_registry()
    rows = []

    for item in upgrades:
        if isinstance(item, dict):
            uid = item.get("id", "")
            title = item.get("title", "")
            marker = ", ".join(item.get("healthcheck_markers", []))
        else:
            uid, title, marker = item

        rows.append({
            "id": uid,
            "title": title,
            "marker": marker,
            "status": "implemented",
        })

    if next_upgrade:
        rows.append({
            "id": next_upgrade.get("id", "NEXT"),
            "title": next_upgrade.get("title", "Next upgrade"),
            "marker": "",
            "status": "planned",
        })

    return rows


def render_upgrade_badges() -> str:
    rows = upgrade_status_rows()
    parts = [
        '<section class="upgrade-status-panel" style="margin:12px 0;padding:12px;border:1px solid #ddd;border-radius:10px;">',
        '<h2 style="margin:0 0 8px 0;">Link Upgrade Status</h2>',
        '<div style="display:flex;flex-wrap:wrap;gap:8px;">',
    ]

    for row in rows:
        status = row["status"]
        label = f'{row["id"]} · {row["title"]}'
        if status == "implemented":
            badge_style = "background:#e8fff0;border:1px solid #76c893;"
            prefix = "✅"
        else:
            badge_style = "background:#f3f3f3;border:1px solid #bbb;"
            prefix = "⏭️"

        parts.append(
            '<span class="upgrade-badge upgrade-badge-{}" style="{}padding:6px 10px;border-radius:999px;font-size:13px;">{} {}</span>'.format(
                escape(status),
                badge_style,
                escape(prefix),
                escape(label),
            )
        )

    parts.append("</div>")
    parts.append("</section>")
    return "\n".join(parts)


def render_upgrade_status_text() -> str:
    lines = ["Link Upgrade Status"]
    for row in upgrade_status_rows():
        lines.append(f"{row['id']} [{row['status']}] {row['title']}")
    return "\n".join(lines)


def main() -> int:
    print(render_upgrade_status_text())
    print("upgrade status badges OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
