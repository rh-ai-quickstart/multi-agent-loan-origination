// This project was developed with assistance from AI tools.

import { useState, useCallback, useRef, useEffect } from 'react';
import { connectChat, type WsMessage, type ChatWs } from '@/lib/ws';

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    toolCalls?: ToolCall[];
    timestamp: Date;
}

interface ToolCall {
    name: string;
    input?: Record<string, unknown>;
    output?: unknown;
}

interface UseChatOptions {
    path: string;
}

export function useChat({ path }: UseChatOptions) {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [isStreaming, setIsStreaming] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [connectionError, setConnectionError] = useState<string | null>(null);
    const wsRef = useRef<ChatWs | null>(null);
    const streamBufferRef = useRef('');
    const currentToolCallsRef = useRef<ToolCall[]>([]);
    const mountedRef = useRef(true);

    const connect = useCallback(() => {
        if (wsRef.current && wsRef.current.readyState() === WebSocket.OPEN) return;

        // Close any previous connection cleanly
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
                    case 'token':
                        streamBufferRef.current += msg.content ?? '';
                        setMessages((prev) => {
                            const last = prev[prev.length - 1];
                            if (last?.role === 'assistant' && isStreamingMsg(last)) {
                                return [
                                    ...prev.slice(0, -1),
                                    { ...last, content: streamBufferRef.current },
                                ];
                            }
                            return [
                                ...prev,
                                {
                                    id: crypto.randomUUID(),
                                    role: 'assistant',
                                    content: streamBufferRef.current,
                                    timestamp: new Date(),
                                    _streaming: true,
                                } as ChatMessage & { _streaming?: boolean },
                            ];
                        });
                        break;

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

                    case 'done':
                        setMessages((prev) => {
                            const last = prev[prev.length - 1];
                            if (last?.role === 'assistant') {
                                const updated = { ...last };
                                if (currentToolCallsRef.current.length > 0) {
                                    updated.toolCalls = [...currentToolCallsRef.current];
                                }
                                delete (updated as Record<string, unknown>)['_streaming'];
                                return [...prev.slice(0, -1), updated];
                            }
                            return prev;
                        });
                        streamBufferRef.current = '';
                        currentToolCallsRef.current = [];
                        setIsStreaming(false);
                        break;

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
                                    id: crypto.randomUUID(),
                                    role: 'assistant',
                                    content: msg.content ?? '',
                                    timestamp: new Date(),
                                },
                            ];
                        });
                        break;

                    case 'error':
                        // Connection-level errors go to connectionError state,
                        // server-sent errors go to messages
                        if (msg.content === 'WebSocket connection failed') {
                            setConnectionError(msg.content);
                        } else {
                            setMessages((prev) => [
                                ...prev,
                                {
                                    id: crypto.randomUUID(),
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
        );

        wsRef.current = ws;
        const check = setInterval(() => {
            if (ws.readyState() === WebSocket.OPEN) {
                setIsConnected(true);
                setConnectionError(null);
                clearInterval(check);
            }
            if (ws.readyState() === WebSocket.CLOSED) {
                clearInterval(check);
            }
        }, 100);
    }, [path]);

    const disconnect = useCallback(() => {
        wsRef.current?.close();
        wsRef.current = null;
        setIsConnected(false);
    }, []);

    const sendMessage = useCallback(
        (content: string) => {
            if (!content.trim()) return;
            if (!wsRef.current || wsRef.current.readyState() !== WebSocket.OPEN) {
                connect();
                setTimeout(() => {
                    wsRef.current?.send(content);
                }, 500);
            } else {
                wsRef.current.send(content);
            }

            setMessages((prev) => [
                ...prev,
                {
                    id: crypto.randomUUID(),
                    role: 'user',
                    content,
                    timestamp: new Date(),
                },
            ]);
            streamBufferRef.current = '';
            currentToolCallsRef.current = [];
            setIsStreaming(true);
        },
        [connect],
    );

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
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
    };
}

function isStreamingMsg(msg: ChatMessage): boolean {
    return '_streaming' in msg && (msg as Record<string, unknown>)['_streaming'] === true;
}
