// This project was developed with assistance from AI tools.

import { useState, useCallback, useRef, useEffect } from 'react';
import { apiGet, apiDelete } from '@/lib/api-client';
import { connectChat, type WsMessage, type ChatWs, type ConnectChatOptions } from '@/lib/ws';

/** crypto.randomUUID() requires a secure context (HTTPS). Fall back for plain HTTP. */
function uuid(): string {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
    }
    return '10000000-1000-4000-8000-100000000000'.replace(/[018]/g, (c) =>
        (+c ^ (crypto.getRandomValues(new Uint8Array(1))[0] & (15 >> (+c / 4)))).toString(16),
    );
}

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    toolCalls?: ToolCall[];
    timestamp: Date;
    _streaming?: boolean;
}

interface ToolCall {
    name: string;
    input?: Record<string, unknown>;
    output?: unknown;
}

interface UseChatOptions {
    path: string;
    historyPath?: string;
    wsOptions?: ConnectChatOptions;
}

export function useChat({ path, historyPath, wsOptions }: UseChatOptions) {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [isStreaming, setIsStreaming] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [connectionError, setConnectionError] = useState<string | null>(null);
    const wsRef = useRef<ChatWs | null>(null);
    const streamBufferRef = useRef('');
    const currentToolCallsRef = useRef<ToolCall[]>([]);
    const mountedRef = useRef(true);
    const prevOptionsRef = useRef<string>('');
    const connectCheckRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const pendingMessageRef = useRef<string | null>(null);

    const loadHistory = useCallback(async () => {
        if (!historyPath) return;
        try {
            const qs = wsOptions?.appId ? `?app_id=${wsOptions.appId}` : '';
            const data = await apiGet<{ data: { role: string; content: string }[] }>(`${historyPath}${qs}`);
            if (!mountedRef.current) return;
            if (data.data.length > 0) {
                setMessages(
                    data.data.map((m) => ({
                        id: uuid(),
                        role: m.role as 'user' | 'assistant',
                        content: m.content,
                        timestamp: new Date(),
                    })),
                );
            }
        } catch {
            // History unavailable -- start fresh
        }
    }, [historyPath, wsOptions?.appId]);

    const connect = useCallback(() => {
        // Detect if options changed (reconnect scenario)
        const optionsKey = JSON.stringify(wsOptions ?? {});
        const optionsChanged = optionsKey !== prevOptionsRef.current;
        prevOptionsRef.current = optionsKey;

        if (optionsChanged && wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
            setMessages([]);
            setIsConnected(false);
        }

        if (wsRef.current && wsRef.current.readyState() === WebSocket.OPEN) return;

        if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
        }

        setConnectionError(null);

        const ws = connectChat(
            path,
            (msg: WsMessage) => {
                if (!mountedRef.current) return;

                switch (msg.type) {
                    case 'token': {
                        streamBufferRef.current += msg.content ?? '';
                        // Capture value now -- if React batches this with the
                        // "done" handler (Firefox does), the ref will already
                        // be cleared by the time the state updater runs.
                        const snapshot = streamBufferRef.current;
                        setMessages((prev) => {
                            const last = prev[prev.length - 1];
                            if (last?.role === 'assistant' && isStreamingMsg(last)) {
                                return [
                                    ...prev.slice(0, -1),
                                    { ...last, content: snapshot },
                                ];
                            }
                            return [
                                ...prev,
                                {
                                    id: uuid(),
                                    role: 'assistant',
                                    content: snapshot,
                                    timestamp: new Date(),
                                    _streaming: true,
                                },
                            ];
                        });
                        break;
                    }

                    case 'tool_start':
                        if (msg.tool_name) {
                            currentToolCallsRef.current.push({
                                name: msg.tool_name,
                                input: msg.tool_input,
                            });
                        }
                        break;

                    case 'tool_result':
                        if (msg.tool_name) {
                            const tc = currentToolCallsRef.current.find(
                                (t) => t.name === msg.tool_name && !t.output,
                            );
                            if (tc) tc.output = msg.tool_output;
                        }
                        break;

                    case 'done': {
                        // The server includes the final content in the done
                        // message so we don't depend on the token message
                        // having been processed first (Firefox microtask race).
                        const doneContent = msg.content ?? streamBufferRef.current;
                        setMessages((prev) => {
                            const last = prev[prev.length - 1];
                            if (last?.role === 'assistant') {
                                const updated = { ...last, content: doneContent };
                                if (currentToolCallsRef.current.length > 0) {
                                    updated.toolCalls = [...currentToolCallsRef.current];
                                }
                                delete (updated as Record<string, unknown>)['_streaming'];
                                return [...prev.slice(0, -1), updated];
                            }
                            // No assistant message yet -- create one with the content
                            return [
                                ...prev,
                                {
                                    id: uuid(),
                                    role: 'assistant' as const,
                                    content: doneContent,
                                    timestamp: new Date(),
                                },
                            ];
                        });
                        streamBufferRef.current = '';
                        currentToolCallsRef.current = [];
                        setIsStreaming(false);
                        window.dispatchEvent(new Event('chat-done'));
                        break;
                    }

                    case 'safety_override':
                        setMessages((prev) => {
                            const last = prev[prev.length - 1];
                            if (last?.role === 'assistant') {
                                return [
                                    ...prev.slice(0, -1),
                                    { ...last, content: msg.content ?? '' },
                                ];
                            }
                            return [
                                ...prev,
                                {
                                    id: uuid(),
                                    role: 'assistant',
                                    content: msg.content ?? '',
                                    timestamp: new Date(),
                                },
                            ];
                        });
                        break;

                    case 'error':
                        if (msg.content === 'WebSocket connection failed') {
                            setConnectionError(msg.content);
                        } else {
                            setMessages((prev) => [
                                ...prev,
                                {
                                    id: uuid(),
                                    role: 'assistant',
                                    content: msg.content ?? 'An error occurred.',
                                    timestamp: new Date(),
                                },
                            ]);
                        }
                        streamBufferRef.current = '';
                        currentToolCallsRef.current = [];
                        setIsStreaming(false);
                        break;
                }
            },
            () => {
                if (mountedRef.current) {
                    setIsConnected(false);
                }
            },
            wsOptions,
        );

        wsRef.current = ws;
        if (connectCheckRef.current) clearInterval(connectCheckRef.current);
        const check = setInterval(() => {
            if (ws.readyState() === WebSocket.OPEN) {
                setIsConnected(true);
                setConnectionError(null);
                clearInterval(check);
                connectCheckRef.current = null;
                // Load history once connected
                if (optionsChanged) {
                    loadHistory();
                }
                // Send any message queued while connecting
                if (pendingMessageRef.current) {
                    ws.send(pendingMessageRef.current);
                    pendingMessageRef.current = null;
                }
            }
            if (ws.readyState() === WebSocket.CLOSED) {
                clearInterval(check);
                connectCheckRef.current = null;
            }
        }, 100);
        connectCheckRef.current = check;
    }, [path, wsOptions, loadHistory]);

    const disconnect = useCallback(() => {
        wsRef.current?.close();
        wsRef.current = null;
        setIsConnected(false);
    }, []);

    const sendMessage = useCallback(
        (content: string, displayContent?: string) => {
            if (!content.trim()) return;
            if (!wsRef.current || wsRef.current.readyState() !== WebSocket.OPEN) {
                pendingMessageRef.current = content;
                connect();
            } else {
                wsRef.current.send(content);
            }

            setMessages((prev) => [
                ...prev,
                {
                    id: uuid(),
                    role: 'user',
                    content: displayContent ?? content,
                    timestamp: new Date(),
                },
            ]);
            streamBufferRef.current = '';
            currentToolCallsRef.current = [];
            setIsStreaming(true);
        },
        [connect],
    );

    const clearHistory = useCallback(async () => {
        if (!historyPath) return;
        try {
            const qs = wsOptions?.appId ? `?app_id=${wsOptions.appId}` : '';
            await apiDelete(`${historyPath}${qs}`);
        } catch {
            // Best-effort -- clear local state regardless
        }
        setMessages([]);
    }, [historyPath, wsOptions?.appId]);

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
            prevOptionsRef.current = '';
            if (connectCheckRef.current) {
                clearInterval(connectCheckRef.current);
                connectCheckRef.current = null;
            }
            wsRef.current?.close();
        };
    }, []);

    return {
        messages,
        isStreaming,
        isConnected,
        connectionError,
        sendMessage,
        connect,
        disconnect,
        clearHistory,
    };
}

function isStreamingMsg(msg: ChatMessage): boolean {
    return msg._streaming === true;
}
