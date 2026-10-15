#!/usr/bin/env python3
import json
import os
import re

transcript_path = "/home/herrenk/.gemini/antigravity/brain/9b63f391-815d-42b4-9f90-8c594a178d03/.system_generated/logs/transcript.jsonl"
out_dir = "/home/herrenk/User/20261013_0935_Streamlit_Mission_Control/docs/chat_logs"
os.makedirs(out_dir, exist_ok=True)

md_file = os.path.join(out_dir, "CHAT_LOG.md")
raw_jsonl_target = os.path.join(out_dir, "conversation_transcript.jsonl")

# 1. Copy raw JSONL
with open(transcript_path, "r", encoding="utf-8") as src, open(raw_jsonl_target, "w", encoding="utf-8") as dst:
    for line in src:
        dst.write(line)

print(f"Copied raw transcript to {raw_jsonl_target}")

# 2. Parse into Markdown
entries = []
with open(transcript_path, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)
        entries.append(data)

with open(md_file, "w", encoding="utf-8") as out:
    out.write("# 💬 Conversation Log & Engineering Dialogue History\n\n")
    out.write("> **Project**: Streamlit Mission Control (AWS Bangkok & CloudFront Production Deployment)\n")
    out.write("> **Session ID**: `9b63f391-815d-42b4-9f90-8c594a178d03`\n")
    out.write("> **Raw JSONL Log**: [`conversation_transcript.jsonl`](./conversation_transcript.jsonl)\n")
    out.write("> **Export Date**: 2026-10-16\n\n---\n\n")

    current_tools = []
    
    for entry in entries:
        step_idx = entry.get("step_index", 0)
        stype = entry.get("type", "")
        created_at = entry.get("created_at", "")[:19].replace("T", " ")
        content = entry.get("content", "")
        tool_calls = entry.get("tool_calls", [])

        if tool_calls:
            for tc in tool_calls:
                name = tc.get("name", "")
                summary = tc.get("args", {}).get("toolSummary", "") or tc.get("args", {}).get("toolAction", "") or name
                current_tools.append(f"- `Step {step_idx}`: **{name}** — {summary}")

        if stype == "USER_INPUT":
            # Filter out internal synthetic system messages
            if "<SYSTEM_MESSAGE>" in content and "<USER_REQUEST>" not in content:
                continue
            
            # Flush accumulated tools if any
            if current_tools:
                out.write(f"<details><summary>🛠️ <i>Background Operations ({len(current_tools)} actions executed)</i></summary>\n\n")
                out.write("\n".join(current_tools))
                out.write("\n\n</details>\n\n---\n\n")
                current_tools = []

            # Clean user request tags
            clean_content = content
            m = re.search(r"<USER_REQUEST>(.*?)</USER_REQUEST>", content, re.DOTALL)
            if m:
                clean_content = m.group(1).strip()
            elif "<CONTEXT_SUMMARY>" in content:
                continue

            out.write(f"### 👤 User (`{created_at} UTC` | Step {step_idx})\n\n")
            out.write(f"{clean_content}\n\n---\n\n")

        elif stype == "PLANNER_RESPONSE" and content:
            # Flush tools
            if current_tools:
                out.write(f"<details><summary>🛠️ <i>Background Operations ({len(current_tools)} actions executed)</i></summary>\n\n")
                out.write("\n".join(current_tools))
                out.write("\n\n</details>\n\n")
                current_tools = []

            out.write(f"### 🤖 Antigravity Assistant (`{created_at} UTC` | Step {step_idx})\n\n")
            out.write(f"{content}\n\n---\n\n")

print(f"Generated clean Markdown transcript to {md_file}")
