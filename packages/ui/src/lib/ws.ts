// This project was developed with assistance from AI tools.

export interface WsMessage {
    type: 'done' | 'error' | 'tool_start' | 'tool_result' | string;
    content?: string;
    tool_name?: string;
    tool_input?: Record<string, unknown>;
    tool_output?: unknown;
}

export type WsHandler = (msg: WsMessage) => void;

export interface ChatWs {
    send: (content: string) => void;
    close: () => void;
    readyState: () => number;
}

export interface ConnectChatOptions {
    /** JWT access token -- used when Keycloak is enabled */
    token?: string;
    /** Dev-mode identity fields (ignored when token is present) */
    devUserId?: string;
    devEmail?: string;
    devName?: string;
    appId?: string;
}

export function connectChat(
    path: string,
    onMessage: WsHandler,
    onClose?: () => void,
    options?: ConnectChatOptions,
): ChatWs {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const params = new URLSearchParams();
    if (options?.token) {
        // NOTE: JWT in query string is an accepted MVP trade-off. The WebSocket API
        // does not support custom headers. For production, use a short-lived ticket
        // token exchanged via REST, or send the JWT as the first WS message.
        params.set('token', options.token);
    } else {
        // Dev mode: pass identity headers as query params
        if (options?.devUserId) params.set('dev_user_id', options.devUserId);
        if (options?.devEmail) params.set('dev_email', options.devEmail);
        if (options?.devName) params.set('dev_name', options.devName);
    }
    if (options?.appId) params.set('app_id', options.appId);
    const qs = params.toString();
    const url = `${protocol}//${window.location.host}${path}${qs ? `?${qs}` : ''}`;
    const ws = new WebSocket(url);

    ws.onmessage = (event) => {
        try {
            const msg: WsMessage = JSON.parse(event.data);
            onMessage(msg);
        } catch {
            // non-JSON frame, treat as token
            onMessage({ type: 'token', content: event.data });
        }
    };

    ws.onclose = () => {
        onClose?.();
    };

    ws.onerror = () => {
        onMessage({ type: 'error', content: 'WebSocket connection failed' });
    };

    return {
        send: (content: string) => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'message', content }));
            }
        },
        close: () => ws.close(),
        readyState: () => ws.readyState,
    };
}
