from nicegui import ui, app
from groq import Groq
from github import Github
import json
import asyncio

# --- Load secrets (will come from Hugging Face later) ---
# For local testing, you can temporarily hardcode, but remove before committing!
GROQ_API_KEY = ''  # Leave empty for now — we'll set in HF
GH_TOKEN = ''      # Leave empty
GH_REPO = ''       # e.g., 'yourusername/nexus-omni-nicegui' — leave empty

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
gh = Github(GH_TOKEN) if GH_TOKEN else None
repo = gh.get_repo(GH_REPO) if gh and GH_REPO else None

# --- Tools (same as before) ---
def get_tools():
    return [
        {"type": "function", "function": {
            "name": "list_repo_files", "description": "List all files.",
            "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {
            "name": "read_file", "description": "Read file.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
        {"type": "function", "function": {
            "name": "write_file", "description": "Create/update file.",
            "parameters": {"type": "object", "properties": {
                "path": {"type": "string"}, "content": {"type": "string"},
                "message": {"type": "string"}}}, "required": ["path", "content"]}}},
        {"type": "function", "function": {
            "name": "delete_file", "description": "Delete file.",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}
    ]

def execute_tool(tool_call, repo):
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)
    except:
        return json.dumps({"error": "Bad arguments"})
    try:
        if name == "list_repo_files":
            return json.dumps({"files": [f.path for f in repo.get_contents("")]})
        elif name == "read_file":
            content = repo.get_contents(args["path"]).decoded_content.decode("utf-8")
            return json.dumps({"content": content[:20000]})
        elif name == "write_file":
            path = args["path"]
            content = args["content"]
            message = args.get("message", "Agent update")
            try:
                f = repo.get_contents(path)
                repo.update_file(path, message, content, f.sha)
                return json.dumps({"status": "updated", "path": path})
            except:
                repo.create_file(path, message, content)
                return json.dumps({"status": "created", "path": path})
        elif name == "delete_file":
            path = args["path"]
            f = repo.get_contents(path)
            repo.delete_file(path, "Agent delete", f.sha)
            return json.dumps({"status": "deleted", "path": path})
    except Exception as e:
        return json.dumps({"error": str(e)})

# --- Storage ---
if 'messages' not in app.storage.user:
    app.storage.user['messages'] = []
if 'model' not in app.storage.user:
    app.storage.user['model'] = "llama-3.3-70b-versatile"

# --- UI Layout ---
with ui.header().classes('items-center justify-between bg-gray-900 p-4'):
    ui.label('Nexus Omni').classes('text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-600 bg-clip-text text-transparent')
    with ui.row():
        ui.button('Clear Chat', on_click=lambda: app.storage.user.update({'messages': []})).props('outline')
        ui.select(['llama-3.3-70b-versatile', 'llama3-8b-8192'], label='Model', value=app.storage.user['model'],
                  on_change=lambda e: app.storage.user.update({'model': e.value}))
        ui.switch('Dark Mode', value=True, on_change=lambda e: ui.dark_mode().enable() if e.value else ui.dark_mode().disable())

with ui.grid(columns=2).classes('w-full p-8 gap-8'):
    # Left Panel
    with ui.card().classes('w-full'):
        ui.label('✍️ Code Architect').classes('text-2xl mb-4')
        filename = ui.input('Filename', value='new_tool.py')
        code = ui.textarea('Source Code', placeholder='# Enter code...').classes('w-full h-64')
        ui.button('🚀 Push to Repo', on_click=lambda: asyncio.create_task(push_code(filename.value, code.value))).props('block color=primary')

        ui.separator().classes('my-6')
        ui.label('📁 Repository Vault').classes('text-2xl')
        vault_container = ui.column()

    # Right Panel
    with ui.card().classes('w-full'):
        ui.label('💬 Nexus Intelligent Agent').classes('text-2xl mb-4')
        chat_container = ui.column().classes('h-96 overflow-y-auto')
        for m in app.storage.user['messages']:
            with chat_container:
                with ui.chat_message(text=m['content'], sent=m['role']=='user'):
                    pass

        with ui.row().classes('w-full mt-4'):
            ui.button('🔍 Audit', on_click=lambda: process_query("Audit all Python files"))
            ui.button('📐 UI', on_click=lambda: process_query("Suggest UI improvements"))
            ui.button('🧠 Memory', on_click=lambda: process_query("Sync memory_general.json with goals"))
            ui.button('🚀 Tool', on_click=lambda: process_query("Build a new utility script"))

        query_input = ui.input('Command the Nexus...').classes('w-full').on('keydown.enter', lambda e: process_query(e.value))

# --- Functions ---
async def push_code(fname, body):
    if not repo:
        ui.notify('Repo not connected')
        return
    try:
        try:
            f = repo.get_contents(fname)
            repo.update_file(fname, "Manual update", body, f.sha)
        except:
            repo.create_file(fname, "Manual create", body)
        ui.notify('Pushed successfully! ✅')
        await refresh_vault()
    except Exception as e:
        ui.notify(f'Error: {e}')

async def refresh_vault():
    vault_container.clear()
    if repo:
        try:
            files = repo.get_contents("")
            for f in files:
                if f.type == "file":
                    with vault_container:
                        with ui.expansion(f'{f.name} ({f.size} bytes)'):
                            ui.code(f.decoded_content.decode("utf-8")[:1500])
                            ui.button('Delete', on_click=lambda p=f.path: asyncio.create_task(delete_file(p))).props('color=red')
        except Exception as e:
            with vault_container:
                ui.label(f'Error loading vault: {e}')
    else:
        with vault_container:
            ui.label('Repo not connected yet')

async def delete_file(path):
    try:
        f = repo.get_contents(path)
        repo.delete_file(path, "Manual delete", f.sha)
        ui.notify('Deleted!')
        await refresh_vault()
    except Exception as e:
        ui.notify(f'Error: {e}')

async def process_query(query):
    if not query or not client or not repo:
        return
    app.storage.user['messages'].append({"role": "user", "content": query})
    query_input.value = ''
    with chat_container:
        assistant_msg = ui.chat_message(text='Thinking...', sent=False)
    await refresh_chat()

    messages = [{"role": "system", "content": "You are Nexus Omni, autonomous AI agent. Use tools when needed. Keep responses concise."}]
    messages.extend(app.storage.user['messages'][-10:])

    response = ""
    for _ in range(5):
        try:
            comp = client.chat.completions.create(
                model=app.storage.user['model'],
                messages=messages,
                tools=get_tools(),
                tool_choice="auto",
                max_tokens=2048
            )
            choice = comp.choices[0].message
            if choice.content:
                response += choice.content + "\n"
            if not choice.tool_calls:
                break
            for tc in choice.tool_calls:
                result = execute_tool(tc, repo)
                messages.append(choice)
                messages.append({"role": "tool", "tool_call_id": tc.id, "name": tc.function.name, "content": result})
                response += f"[Used {tc.function.name}]\n"
        except Exception as e:
            response += f"Error: {str(e)}"
            break

    app.storage.user['messages'].append({"role": "assistant", "content": response})
    assistant_msg.text = response
    await refresh_vault()

async def refresh_chat():
    chat_container.clear()
    for m in app.storage.user['messages']:
        with chat_container:
            ui.chat_message(text=m['content'], sent=m['role']=='user')

# Initial vault load
ui.timer(1, refresh_vault, once=True)

ui.run(title='Nexus Omni', port=8080, storage_secret='SECRET-KEY-FOR-SESSION')
