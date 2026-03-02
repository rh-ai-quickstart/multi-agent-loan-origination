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
    const wsRef = useRef<ChatWs | null>(null);
    const streamBufferRef = useRef('');
    const currentToolCallsRef = useRef<ToolCall[]>([]);

    const connect = useCallback(() => {
        if (wsRef.current && wsRef.current.readyState() === WebSocket.OPEN) return;

        const ws = connectChat(
            path,
            (msg: WsMessage) => {
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
                            // First token -- create new assistant message
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
                                // Remove streaming marker
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
                        // Output shield replaced the response
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
                        setMessages((prev) => [
                            ...prev,
                            {
                                id: crypto.randomUUID(),
                                role: 'assistant',
                                content: msg.content ?? 'An error occurred.',
                                timestamp: new Date(),
                            },
                        ]);
                        streamBufferRef.current = '';
                        currentToolCallsRef.current = [];
                        setIsStreaming(false);
                        break;
                }
            },
            () => {
                setIsConnected(false);
            },
        );

        wsRef.current = ws;
        // Poll briefly for open state
        const check = setInterval(() => {
            if (ws.readyState() === WebSocket.OPEN) {
                setIsConnected(true);
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
                // Retry once after brief delay
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

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            wsRef.current?.close();
        };
    }, []);

    return {
        messages,
        isStreaming,
        isConnected,
        sendMessage,
        connect,
        disconnect,
    };
}

function isStreamingMsg(msg: ChatMessage): boolean {
    return '_streaming' in msg && (msg as Record<string, unknown>)['_streaming'] === true;
}
