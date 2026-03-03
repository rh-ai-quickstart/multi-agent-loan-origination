// This project was developed with assistance from AI tools.

export interface WsMessage {
    type: 'token' | 'done' | 'error' | 'safety_override' | 'tool_start' | 'tool_result' | string;
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
    if (options?.devUserId) params.set('dev_user_id', options.devUserId);
    if (options?.devEmail) params.set('dev_email', options.devEmail);
    if (options?.devName) params.set('dev_name', options.devName);
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
