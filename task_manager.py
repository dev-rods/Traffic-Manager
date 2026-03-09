#!/usr/bin/env python3
"""
task_manager.py — State machine CLI for Traffic Manager kanban.

GitHub Project: https://github.com/users/rodsebaiano-bot/projects/1
Columns: Backlog → Ready → In Progress → Review → Done

Usage:
    python3 task_manager.py          # Run state machine (called by heartbeat)
    python3 task_manager.py --complete <item_id>  # Mark task as done (called by agent)
    python3 task_manager.py --status  # Show current board state
"""

import sys
import os
import json
import subprocess
import requests
from datetime import datetime

# ─── Config ────────────────────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get("TASK_MANAGER_GITHUB_TOKEN")
OPENCLAW_URL = "http://127.0.0.1:18789"
OPENCLAW_TOKEN = os.environ.get("OPENCLAW_TOKEN")

PROJECT_ID   = "PVT_kwHOD-EQCc4BRGIm"
KANBAN_FIELD = "PVTSSF_lAHOD-EQCc4BRGImzg_Bj5U"

COLUMNS = {
    "Backlog":     "7f7c4bcd",
    "Ready":       "9a90f56b",
    "In Progress": "05cace13",
    "Review":      "0698537c",
    "Done":        "8c846927",
}

TELEGRAM_CHAT_ID = os.environ.get("TASK_MANAGER_TELEGRAM_CHAT_ID")

# ─── GitHub GraphQL ─────────────────────────────────────────────────────────────
def gql(query: str, variables: dict = None):
    resp = requests.post(
        "https://api.github.com/graphql",
        headers={"Authorization": f"bearer {GITHUB_TOKEN}"},
        json={"query": query, "variables": variables or {}},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL error: {data['errors']}")
    return data["data"]


def get_board_items():
    """Fetch all items from the project with their Kanban column."""
    query = """
    query($projectId: ID!) {
      node(id: $projectId) {
        ... on ProjectV2 {
          items(first: 50) {
            nodes {
              id
              fieldValues(first: 20) {
                nodes {
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    name
                    field { ... on ProjectV2SingleSelectField { id name } }
                  }
                  ... on ProjectV2ItemFieldTextValue {
                    text
                    field { ... on ProjectV2Field { id name } }
                  }
                }
              }
              content {
                ... on Issue {
                  id
                  number
                  title
                  body
                  url
                  createdAt
                }
                ... on DraftIssue {
                  id
                  title
                  body
                  createdAt
                }
              }
            }
          }
        }
      }
    }
    """
    data = gql(query, {"projectId": PROJECT_ID})
    items = []
    for node in data["node"]["items"]["nodes"]:
        kanban_col = None
        title = None
        body = None
        url = None
        item_id = node["id"]

        for fv in node["fieldValues"]["nodes"]:
            field = fv.get("field", {})
            if field.get("id") == KANBAN_FIELD:
                kanban_col = fv.get("name")
            if field.get("name") == "Title":
                title = fv.get("text")

        content = node.get("content") or {}
        title = title or content.get("title", "(sem título)")
        body = content.get("body", "")
        url = content.get("url", "")
        content_id = content.get("id")

        items.append({
            "item_id": item_id,
            "content_id": content_id,
            "title": title,
            "body": body,
            "url": url,
            "column": kanban_col or "Backlog",
        })
    return items


def move_item(item_id: str, column_name: str):
    """Move a project item to a different Kanban column."""
    option_id = COLUMNS[column_name]
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(input: {
        projectId: $projectId
        itemId: $itemId
        fieldId: $fieldId
        value: { singleSelectOptionId: $optionId }
      }) {
        projectV2Item { id }
      }
    }
    """
    gql(mutation, {
        "projectId": PROJECT_ID,
        "itemId": item_id,
        "fieldId": KANBAN_FIELD,
        "optionId": option_id,
    })
    print(f"[task_manager] Moved '{item_id}' → {column_name}")


# ─── Notifications ──────────────────────────────────────────────────────────────
def notify_telegram(message: str):
    """Send notification via openclaw CLI."""
    try:
        result = subprocess.run(
            ["openclaw", "message", "send",
             "--channel", "telegram",
             "--target", TELEGRAM_CHAT_ID,
             "--message", message],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            print(f"[task_manager] Telegram warning: {result.stderr}")
    except Exception as e:
        print(f"[task_manager] Telegram error: {e}")


# ─── Agent Spawner ──────────────────────────────────────────────────────────────
def spawn_agent_for_task(item: dict):
    """Spawn an Opus agent to work on the task via OpenClaw sessions API."""
    task_prompt = f"""You are agent-rods ⚡, working on a task from the Traffic Manager kanban.

## Task
**Title:** {item['title']}
**URL:** {item['url']}
**Description:**
{item['body']}

## Instructions
1. Read WORKFLOW.md and CLAUDE.md in the Traffic-Manager repo before starting
2. Follow the Planning → Meta-planning → Execution process
3. Work on the task completely (state of the art, ready for prod, completeness)
4. When done, run: python3 task_manager.py --complete {item['item_id']}
5. This will move the card to Review and notify Rodrigo

The repo is cloned at: /home/agent-openclaw/.openclaw/workspace/Traffic-Manager/
"""
    try:
        result = subprocess.run(
            ["openclaw", "agent",
             "--message", task_prompt,
             "--deliver"],
            capture_output=True, text=True, timeout=30
        )
        print(f"[task_manager] Agent spawned for: {item['title']}")
        if result.returncode != 0:
            print(f"[task_manager] Spawn warning: {result.stderr}")
    except Exception as e:
        print(f"[task_manager] Spawn error: {e}")


# ─── State Machine ──────────────────────────────────────────────────────────────
def run_state_machine():
    """Main heartbeat loop — check board and advance state."""
    if not GITHUB_TOKEN:
        print("[task_manager] ERROR: TASK_MANAGER_GITHUB_TOKEN not set")
        sys.exit(1)

    items = get_board_items()

    in_progress = [i for i in items if i["column"] == "In Progress"]
    ready = [i for i in items if i["column"] == "Ready"]

    # If something is already in progress, do nothing (one task at a time)
    if in_progress:
        print(f"[task_manager] Task in progress: {in_progress[0]['title']} — waiting")
        return

    # If there's a Ready task and nothing in progress, start it
    if ready:
        next_task = ready[0]  # FIFO
        move_item(next_task["item_id"], "In Progress")
        spawn_agent_for_task(next_task)
        print(f"[task_manager] Started: {next_task['title']}")
        return

    print("[task_manager] Nothing to do")


def complete_task(item_id: str):
    """Called by agent when task is done — move to Review and notify."""
    items = get_board_items()
    task = next((i for i in items if i["item_id"] == item_id), None)

    if not task:
        print(f"[task_manager] ERROR: item {item_id} not found")
        sys.exit(1)

    move_item(item_id, "Review")

    if TELEGRAM_CHAT_ID:
        msg = (
            f"✅ Task pronta pra review!\n\n"
            f"*{task['title']}*\n"
            f"{task['url']}\n\n"
            f"Verifica e move pra Done quando aprovado 🎯"
        )
        notify_telegram(msg)

    print(f"[task_manager] '{task['title']}' moved to Review. Rodrigo notified.")


def show_status():
    """Print current board state."""
    items = get_board_items()
    print(f"\n📋 Traffic Manager Kanban — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    for col in COLUMNS:
        col_items = [i for i in items if i["column"] == col]
        icon = {"Backlog": "📋", "Ready": "✅", "In Progress": "🔄",
                "Review": "🔍", "Done": "✔️"}.get(col, "•")
        print(f"{icon} {col} ({len(col_items)})")
        for item in col_items:
            print(f"   • {item['title']}")
    print()


# ─── CLI Entry ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = sys.argv[1:]

    if "--status" in args:
        show_status()
    elif "--complete" in args:
        idx = args.index("--complete")
        if idx + 1 >= len(args):
            print("Usage: task_manager.py --complete <item_id>")
            sys.exit(1)
        complete_task(args[idx + 1])
    else:
        run_state_machine()
