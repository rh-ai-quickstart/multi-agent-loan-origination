# This project was developed with assistance from AI tools.
#
# Simple Streamlit UI for testing MCP Gateway tool discovery.
# Mirrors the protocol flow from scripts/test-mcp-gateway.sh.
#
# Usage:
#   pip install streamlit requests
#   streamlit run scripts/mcp-gateway-ui.py
#
# Or with a pre-filled URL:
#   streamlit run scripts/mcp-gateway-ui.py -- --url https://mcp-broker-mcp-system.apps.example.com

import argparse
import json

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# CLI args (optional pre-filled URL)
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="", help="Pre-fill the MCP Gateway URL")
    args, _ = parser.parse_known_args()
    return args

cli_args = parse_args()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="MCP Gateway Tester", page_icon="wrench", layout="wide")
st.title("MCP Gateway Tester")
st.caption("Test MCP Streamable HTTP protocol: initialize, notify, list tools, call a tool")

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

INIT_STATE = {
    "session_id": None,
    "cookies": {},
    "tools": [],
    "server_info": {},
    "steps": [],
    "flow": [],
    "last_call_result": None,
    "last_call_tool": None,
}
for key, default in INIT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------------------------------------------------------
# MCP helpers
# ---------------------------------------------------------------------------

MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def mcp_post(url, body, session_id=None):
    headers = dict(MCP_HEADERS)
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    resp = requests.post(
        f"{url}/mcp",
        json=body,
        headers=headers,
        cookies=st.session_state.cookies,
        timeout=15,
        verify=False,
    )
    st.session_state.cookies.update(resp.cookies.get_dict())
    return resp


def run_discovery(url):
    steps = []
    flow = []

    # Step 1: Initialize
    req_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "mcp-gateway-ui", "version": "1.0"},
        },
    }
    try:
        resp = mcp_post(url, req_body)
        session_id = resp.headers.get("Mcp-Session-Id", "")
        data = resp.json()
        server_info = data.get("result", {}).get("serverInfo", {})
        protocol = data.get("result", {}).get("protocolVersion", "")
        st.session_state.session_id = session_id
        st.session_state.server_info = server_info
        steps.append(("Initialize", True, f"Server: {server_info.get('name', '?')}, Protocol: {protocol}"))
        flow.append({
            "step": 1,
            "label": "Initialize",
            "method": "initialize",
            "ok": True,
            "status": resp.status_code,
            "request": req_body,
            "req_headers": dict(MCP_HEADERS),
            "resp_headers": {"Mcp-Session-Id": session_id},
            "response": data,
            "description": "Client introduces itself and receives a session ID (JWT) for all subsequent requests.",
        })
    except Exception as e:
        steps.append(("Initialize", False, str(e)))
        flow.append({
            "step": 1, "label": "Initialize", "method": "initialize",
            "ok": False, "status": 0, "request": req_body,
            "req_headers": dict(MCP_HEADERS), "resp_headers": {},
            "response": {"error": str(e)},
            "description": "Client introduces itself and receives a session ID (JWT).",
        })
        st.session_state.steps = steps
        st.session_state.flow = flow
        return

    # Step 2: Notify
    req_body_notify = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    notify_headers = {**MCP_HEADERS, "Mcp-Session-Id": session_id}
    try:
        resp = mcp_post(url, req_body_notify, session_id=session_id)
        ok = resp.status_code in (200, 202)
        steps.append(("Notify", ok, f"HTTP {resp.status_code}"))
        flow.append({
            "step": 2,
            "label": "Notify Initialized",
            "method": "notifications/initialized",
            "ok": ok,
            "status": resp.status_code,
            "request": req_body_notify,
            "req_headers": notify_headers,
            "resp_headers": {},
            "response": "(empty - notification)" if ok else f"HTTP {resp.status_code}",
            "description": "Client confirms initialization is complete. Server acknowledges with 202.",
        })
    except Exception as e:
        steps.append(("Notify", False, str(e)))
        flow.append({
            "step": 2, "label": "Notify Initialized", "method": "notifications/initialized",
            "ok": False, "status": 0, "request": req_body_notify,
            "req_headers": notify_headers, "resp_headers": {},
            "response": {"error": str(e)},
            "description": "Client confirms initialization is complete.",
        })

    # Step 3: List tools
    req_body_tools = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    try:
        resp = mcp_post(url, req_body_tools, session_id=session_id)
        data = resp.json()
        tools = data.get("result", {}).get("tools", [])
        st.session_state.tools = tools
        tool_names = [t["name"] for t in tools]
        steps.append(("List Tools", len(tools) > 0, f"{len(tools)} tools discovered"))
        flow.append({
            "step": 3,
            "label": "List Tools",
            "method": "tools/list",
            "ok": len(tools) > 0,
            "status": resp.status_code,
            "request": req_body_tools,
            "req_headers": notify_headers,
            "resp_headers": {},
            "response": data,
            "tool_names": tool_names,
            "description": "Server returns all registered tools with their input schemas.",
        })
    except Exception as e:
        steps.append(("List Tools", False, str(e)))
        flow.append({
            "step": 3, "label": "List Tools", "method": "tools/list",
            "ok": False, "status": 0, "request": req_body_tools,
            "req_headers": notify_headers, "resp_headers": {},
            "response": {"error": str(e)}, "tool_names": [],
            "description": "Server returns all registered tools with their input schemas.",
        })
        st.session_state.tools = []

    # Step 4: Auto-call first tool to complete the flow
    if st.session_state.tools:
        auto_tool = _pick_auto_tool(st.session_state.tools)
        if auto_tool:
            tool_name = auto_tool["name"]
            arguments = auto_tool["args"]
            req_body_call = {
                "jsonrpc": "2.0", "id": 3,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
            try:
                resp = mcp_post(url, req_body_call, session_id=session_id)
                content_type = resp.headers.get("Content-Type", "")
                if "text/event-stream" in content_type:
                    data = _parse_sse(resp.text)
                else:
                    data = resp.json()
                ok = "error" not in data
                steps.append(("Call Tool", ok, f"{tool_name}: {'OK' if ok else 'error'}"))
                flow.append({
                    "step": 4,
                    "label": "Call Tool",
                    "method": "tools/call",
                    "ok": ok,
                    "status": resp.status_code,
                    "request": req_body_call,
                    "req_headers": notify_headers,
                    "resp_headers": {},
                    "response": data,
                    "description": f"Auto-invoke tool '{tool_name}' to validate the full protocol flow.",
                })
                st.session_state.last_call_result = data
                st.session_state.last_call_tool = tool_name
            except Exception as e:
                steps.append(("Call Tool", False, str(e)))
                flow.append({
                    "step": 4, "label": "Call Tool", "method": "tools/call",
                    "ok": False, "status": 0, "request": req_body_call,
                    "req_headers": notify_headers, "resp_headers": {},
                    "response": {"error": str(e)},
                    "description": f"Auto-invoke tool '{tool_name}' to validate the full protocol flow.",
                })

    st.session_state.steps = steps
    st.session_state.flow = flow


def _pick_auto_tool(tools):
    preferred = {
        "risk_calculate_dti": {"monthly_income": 8000, "monthly_debts": 2400},
        "risk_calculate_ltv": {"loan_amount": 320000, "property_value": 400000},
        "risk_evaluate_credit_risk": {"credit_score": 720},
    }
    for name, args in preferred.items():
        if any(t["name"] == name for t in tools):
            return {"name": name, "args": args}
    t = tools[0]
    props = t.get("inputSchema", {}).get("properties", {})
    return {"name": t["name"], "args": {p: "" for p in props}}


def _parse_sse(text):
    for line in text.strip().splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    return json.loads(text)


def call_tool(url, tool_name, arguments):
    req_body = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    req_headers = {**MCP_HEADERS, "Mcp-Session-Id": st.session_state.session_id or ""}
    try:
        resp = mcp_post(url, req_body, session_id=st.session_state.session_id)
        content_type = resp.headers.get("Content-Type", "")
        if "text/event-stream" in content_type:
            data = _parse_sse(resp.text)
        else:
            data = resp.json()
        ok = "error" not in data
        flow_entry = {
            "step": 4,
            "label": "Call Tool",
            "method": "tools/call",
            "ok": ok,
            "status": resp.status_code,
            "request": req_body,
            "req_headers": req_headers,
            "resp_headers": {},
            "response": data,
            "description": f"Invoke tool '{tool_name}' with the provided arguments.",
        }
        st.session_state.flow = [f for f in st.session_state.flow if f["step"] != 4] + [flow_entry]
        if not any(s[0] == "Call Tool" for s in st.session_state.steps):
            st.session_state.steps.append(("Call Tool", ok, f"{tool_name}: {'OK' if ok else 'error'}"))
        else:
            st.session_state.steps = [
                (s[0], ok, f"{tool_name}: {'OK' if ok else 'error'}") if s[0] == "Call Tool" else s
                for s in st.session_state.steps
            ]
        return data
    except Exception as e:
        flow_entry = {
            "step": 4, "label": "Call Tool", "method": "tools/call",
            "ok": False, "status": 0, "request": req_body,
            "req_headers": req_headers, "resp_headers": {},
            "response": {"error": str(e)},
            "description": f"Invoke tool '{tool_name}' with the provided arguments.",
        }
        st.session_state.flow = [f for f in st.session_state.flow if f["step"] != 4] + [flow_entry]
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Flow rendering
# ---------------------------------------------------------------------------

FLOW_CSS = """
<style>
.flow-container {
    display: flex;
    align-items: stretch;
    gap: 0;
    margin: 1.5rem 0 2rem 0;
    width: 100%;
}
.flow-step {
    flex: 1;
    position: relative;
    text-align: center;
}
.flow-card {
    border: 2px solid #e0e0e0;
    border-radius: 12px;
    padding: 16px 12px;
    margin: 0 8px;
    min-height: 120px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    transition: border-color 0.2s;
}
.flow-card.pass { border-color: #22c55e; background: #f0fdf4; }
.flow-card.fail { border-color: #ef4444; background: #fef2f2; }
.flow-card.pending { border-color: #d1d5db; background: #f9fafb; }
.flow-num {
    width: 28px; height: 28px; border-radius: 50%;
    display: inline-flex; align-items: center; justify-content: center;
    font-weight: 700; font-size: 14px; margin-bottom: 6px;
}
.flow-card.pass .flow-num { background: #22c55e; color: white; }
.flow-card.fail .flow-num { background: #ef4444; color: white; }
.flow-card.pending .flow-num { background: #d1d5db; color: #6b7280; }
.flow-title { font-weight: 700; font-size: 15px; margin-bottom: 4px; }
.flow-method { font-family: monospace; font-size: 12px; color: #6b7280; margin-bottom: 4px; }
.flow-status { font-size: 12px; margin-top: 2px; }
.flow-card.pass .flow-status { color: #16a34a; }
.flow-card.fail .flow-status { color: #dc2626; }
.flow-arrow {
    position: absolute;
    right: -14px;
    top: 50%;
    transform: translateY(-50%);
    font-size: 22px;
    color: #9ca3af;
    z-index: 1;
}
</style>
"""

FLOW_TEMPLATE = [
    {"step": 1, "label": "Initialize", "method": "initialize",
     "description": "Handshake with the MCP server and receive a session ID (JWT)."},
    {"step": 2, "label": "Notify", "method": "notifications/initialized",
     "description": "Confirm initialization is complete. Server returns 202."},
    {"step": 3, "label": "List Tools", "method": "tools/list",
     "description": "Discover all tools registered on the gateway."},
    {"step": 4, "label": "Call Tool", "method": "tools/call",
     "description": "Invoke a specific tool with arguments."},
]


def render_flow_diagram():
    flow_data = st.session_state.flow
    flow_map = {f["step"]: f for f in flow_data}

    cols = st.columns(len(FLOW_TEMPLATE))
    for col, tmpl in zip(cols, FLOW_TEMPLATE):
        step_num = tmpl["step"]
        f = flow_map.get(step_num)
        with col:
            if f:
                if f["ok"]:
                    st.success(f"**{step_num}. {tmpl['label']}**\n\n`{tmpl['method']}`\n\nHTTP {f['status']}")
                else:
                    st.error(f"**{step_num}. {tmpl['label']}**\n\n`{tmpl['method']}`\n\nHTTP {f['status']}")
            else:
                st.info(f"**{step_num}. {tmpl['label']}**\n\n`{tmpl['method']}`\n\npending")


def render_flow_details():
    flow_data = st.session_state.flow
    if not flow_data:
        return

    for f in flow_data:
        status_icon = "+" if f["ok"] else "-"
        with st.expander(f"Step {f['step']}: {f['label']}  |  HTTP {f['status']}", expanded=False):
            st.caption(f["description"])

            col_req, col_resp = st.columns(2)

            with col_req:
                st.markdown("**Request**")
                st.markdown(f"`POST /mcp` - method: `{f['method']}`")
                if f.get("req_headers", {}).get("Mcp-Session-Id"):
                    sid = f["req_headers"]["Mcp-Session-Id"]
                    st.code(f"Mcp-Session-Id: {sid[:50]}...", language="http")
                st.json(f["request"])

            with col_resp:
                st.markdown("**Response**")
                if f.get("resp_headers", {}).get("Mcp-Session-Id"):
                    sid = f["resp_headers"]["Mcp-Session-Id"]
                    st.code(f"Mcp-Session-Id: {sid[:50]}...", language="http")
                    st.caption("This JWT session token must be sent with all subsequent requests.")

                resp = f["response"]
                if isinstance(resp, str):
                    st.text(resp)
                elif isinstance(resp, dict):
                    if f.get("tool_names"):
                        st.markdown("**Discovered tools:**")
                        for tn in f["tool_names"]:
                            st.markdown(f"- `{tn}`")
                    else:
                        st.json(resp)


# ---------------------------------------------------------------------------
# Sidebar - connection
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("Connection")
    url = st.text_input("MCP Gateway URL", value=cli_args.url, placeholder="https://mcp-broker-mcp-system.apps...")
    if st.button("Connect & Discover Tools", type="primary", disabled=not url):
        for key, default in INIT_STATE.items():
            st.session_state[key] = type(default)() if isinstance(default, (dict, list)) else default
        with st.spinner("Running MCP protocol..."):
            run_discovery(url.rstrip("/"))
        st.rerun()

    if st.session_state.server_info:
        st.divider()
        st.subheader("Server")
        st.text(st.session_state.server_info.get("name", ""))
        st.text(f"v{st.session_state.server_info.get('version', '?')}")
        if st.session_state.session_id:
            st.divider()
            st.subheader("Session")
            st.code(st.session_state.session_id[:40] + "...", language="text")

# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

if st.session_state.steps:
    # -- Protocol flow diagram ------------------------------------------------
    st.subheader("Protocol Flow")
    render_flow_diagram()

    # -- Step-by-step details -------------------------------------------------
    st.subheader("Step Details")
    st.caption("Expand each step to see the JSON-RPC request/response and headers exchanged.")
    render_flow_details()

    st.divider()

    # -- Summary metrics ------------------------------------------------------
    st.subheader("Results")
    cols = st.columns(len(st.session_state.steps))
    for col, (name, ok, detail) in zip(cols, st.session_state.steps):
        with col:
            st.metric(label=name, value="PASS" if ok else "FAIL")
            st.caption(detail)

# ---------------------------------------------------------------------------
# Tool catalog
# ---------------------------------------------------------------------------

if st.session_state.tools:
    st.divider()
    st.subheader(f"Tools ({len(st.session_state.tools)})")

    for tool in st.session_state.tools:
        name = tool["name"]
        desc = tool.get("description", "").strip().split("\n")[0]
        schema = tool.get("inputSchema", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        with st.expander(f"**{name}** - {desc}"):
            if properties:
                param_rows = []
                for pname, pinfo in properties.items():
                    param_rows.append({
                        "Parameter": pname,
                        "Type": pinfo.get("type", "any"),
                        "Required": "yes" if pname in required else "no",
                        "Description": pinfo.get("description", ""),
                    })
                st.table(param_rows)
            else:
                st.info("No parameters")

            st.markdown("**Try it**")
            arg_json = st.text_area(
                "Arguments (JSON)",
                value=json.dumps({p: "" for p in properties}, indent=2) if properties else "{}",
                height=100,
                key=f"args_{name}",
            )
            if st.button("Call", key=f"call_{name}"):
                try:
                    arguments = json.loads(arg_json)
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")
                    arguments = None
                if arguments is not None and url:
                    with st.spinner(f"Calling {name}..."):
                        result = call_tool(url.rstrip("/"), name, arguments)
                    st.session_state.last_call_result = result
                    st.session_state.last_call_tool = name
                    st.rerun()

            if st.session_state.last_call_tool == name and st.session_state.last_call_result is not None:
                result = st.session_state.last_call_result
                content = result.get("result", {}).get("content", [])
                error = result.get("error")
                if error:
                    st.error(str(error))
                elif content:
                    for item in content:
                        text = item.get("text", json.dumps(item))
                        st.code(text, language="json")
                else:
                    st.json(result)

elif st.session_state.steps:
    st.warning("No tools discovered. Check that MCP servers are registered and healthy.")
else:
    st.info("Enter the MCP Gateway URL and click **Connect & Discover Tools** to start.")
