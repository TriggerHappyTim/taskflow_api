"""Быстрая проверка таблиц и содержимого БД (для разработки)."""
import sqlite3
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

conn = sqlite3.connect("taskflow.db")

tables = [r[0] for r in conn.execute(
    "select name from sqlite_master where type='table' order by name"
)]

print("=== Таблицы в базе ===")
for name in tables:
    print(" -", name)

print()
for table in ("users", "tasks", "messenger_links"):
    if table in tables:
        count = conn.execute("select count(*) from " + table).fetchone()[0]
        print(f"{table}: {count} записей")

if "messenger_links" in tables:
    print("\n=== Привязки мессенджеров ===")
    rows = list(conn.execute(
        "select id, platform, external_user_id, user_id from messenger_links"
    ))
    if not rows:
        print(" (пока пусто)")
    for row in rows:
        print(" ", row)

conn.close()