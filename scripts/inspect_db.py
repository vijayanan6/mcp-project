import sqlite3
import json
from pathlib import Path

if not Path("data.db").exists():
    print("data.db does not exist yet — run the app first to create it.")
else:
    conn = sqlite3.connect("data.db")

    print("=== NOTES TABLE ===")
    print("Columns: title | content | created_at\n")
    notes = conn.execute("SELECT * FROM notes").fetchall()
    if notes:
        for n in notes:
            print(f"  Title      : {n[0]}")
            print(f"  Content    : {n[1][:60]}...")
            print(f"  Created at : {n[2]}")
            print()
    else:
        print("  (empty — no notes saved yet)\n")

    print("=== SESSIONS TABLE ===")
    print("Columns: session_id | messages (JSON) | created_at | updated_at\n")
    sessions = conn.execute("SELECT session_id, messages, created_at, updated_at FROM sessions").fetchall()
    if sessions:
        for s in sessions:
            msgs = json.loads(s[1])
            user_turns = [m for m in msgs if m["role"] == "user"]
            print(f"  Session ID : {s[0][:30]}...")
            print(f"  Created    : {s[2]}")
            print(f"  Updated    : {s[3]}")
            print(f"  Turns      : {len(user_turns)} user messages")
            if user_turns:
                print(f"  First msg  : {user_turns[0]['content'][:60]}")
            print()
    else:
        print("  (empty — no chats yet)\n")

    conn.close()
