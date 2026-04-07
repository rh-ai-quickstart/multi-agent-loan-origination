// This project was developed with assistance from AI tools.

import { useState, useRef, useEffect, useLayoutEffect, useMemo } from 'react';
import { useLocation } from '@tanstack/react-router';
import { MessageSquare, Send, Loader2, X, Trash2 } from 'lucide-react';
import { useChat } from '@/hooks/use-chat';
import { useAuth } from '@/contexts/auth-context';
import { ChatBubble } from '@/components/atoms/chat-bubble/chat-bubble';
import { cn } from '@/lib/utils';
import { AGENT_NAME } from '@/lib/company';

function useCurrentAppId(): string | undefined {
    const location = useLocation();
    const match = location.pathname.match(/\/(?:loan-officer|underwriter)\/(\d+)/);
    return match?.[1];
}

const _heading = AGENT_NAME ? `Hi, I'm ${AGENT_NAME}. How can I help?` : 'How can I help?';

const ROLE_WELCOME: Record<string, { heading: string; subtext: string }> = {
    borrower: {
        heading: _heading,
        subtext: 'Ask about your application, documents, or next steps.',
    },
    loan_officer: {
        heading: _heading,
        subtext: 'Ask about your pipeline, borrower status, or compliance questions.',
    },
    underwriter: {
        heading: _heading,
        subtext: 'Ask about risk assessment, conditions, or compliance checks.',
    },
    ceo: {
        heading: _heading,
        subtext: 'Ask about portfolio health, denial trends, or operational metrics.',
    },
};

const DEFAULT_WELCOME = { heading: _heading, subtext: 'Ask me anything.' };

export function ChatSidebar() {
    const { chatPath, historyPath, user, token } = useAuth();
    const appId = useCurrentAppId();
    const wsOptions = useMemo(
        () => user ? { token: token ?? undefined, devUserId: user.user_id, devEmail: user.email, devName: user.name, appId } : undefined,
        [user, token, appId],
    );
    const { messages, isStreaming, isConnected, connectionError, sendMessage, connect, clearHistory } = useChat({ path: chatPath, historyPath: historyPath ?? undefined, wsOptions });
    const [input, setInput] = useState('');
    const [isMobileOpen, setIsMobileOpen] = useState(false);
    const inputRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        connect();
    }, [connect]);

    useLayoutEffect(() => {
        // Query all chat-messages containers and scroll each visible one
        const els = document.querySelectorAll<HTMLDivElement>('[data-chat-messages]');
        els.forEach((el) => {
            if (el.offsetParent !== null) el.scrollTop = el.scrollHeight;
        });
        const id = requestAnimationFrame(() => {
            els.forEach((el) => {
                if (el.offsetParent !== null) el.scrollTop = el.scrollHeight;
            });
        });
        return () => cancelAnimationFrame(id);
    }, [messages, isStreaming]);

    useEffect(() => {
        const handler = (e: Event) => {
            const detail = (e as CustomEvent<{ message: string; displayMessage?: string; autoSend?: boolean }>).detail;
            if (detail.message) {
                setIsMobileOpen(true);
                if (detail.autoSend && !isStreaming) {
                    sendMessage(addAppContext(detail.message), detail.displayMessage ?? detail.message);
                } else {
                    setInput(detail.displayMessage ?? detail.message);
                    inputRef.current?.focus();
                }
            }
        };
        window.addEventListener('chat-prefill', handler);
        return () => window.removeEventListener('chat-prefill', handler);
    }, [isStreaming, sendMessage]);

    const addAppContext = (msg: string): string => {
        const match = window.location.pathname.match(/\/(?:loan-officer|underwriter)\/(\d+)/);
        if (!match) return msg;
        const appId = match[1];
        if (msg.includes(`#${appId}`) || msg.includes(`application ${appId}`)) return msg;
        return `[Regarding application #${appId}] ${msg}`;
    };

    const handleSend = () => {
        if (!input.trim() || isStreaming) return;
        const display = input;
        sendMessage(addAppContext(input), display);
        setInput('');
        requestAnimationFrame(() => inputRef.current?.focus());
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const sidebarContent = (
        <>
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#1e3a5f]">
                        <MessageSquare className="h-4 w-4 text-white" aria-hidden="true" />
                    </div>
                    <div>
                        <h2 className="text-sm font-semibold text-foreground">Your Assistant</h2>
                        <div className="flex items-center gap-1.5">
                            <span
                                className={cn(
                                    'h-2 w-2 rounded-full',
                                    isConnected ? 'bg-emerald-500' : 'bg-slate-300',
                                )}
                            />
                            <span className="text-xs text-muted-foreground">
                                {isConnected ? 'Online' : 'Connecting...'}
                            </span>
                        </div>
                    </div>
                </div>
                <div className="flex items-center gap-1">
                    {messages.length > 0 && (
                        <button
                            onClick={clearHistory}
                            disabled={isStreaming}
                            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-slate-100 hover:text-foreground disabled:opacity-40 dark:hover:bg-slate-800"
                            aria-label="Clear chat history"
                        >
                            <Trash2 className="h-4 w-4" />
                        </button>
                    )}
                    <button
                        onClick={() => setIsMobileOpen(false)}
                        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-slate-100 hover:text-foreground dark:hover:bg-slate-800 lg:hidden"
                        aria-label="Close chat"
                    >
                        <X className="h-5 w-5" />
                    </button>
                </div>
            </div>

            {/* Messages */}
            <div data-chat-messages className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
                {connectionError && !isConnected && (
                    <div className="rounded-lg bg-amber-50 px-3 py-2 text-center text-xs text-amber-700 dark:bg-amber-900/20 dark:text-amber-300">
                        Unable to connect. Retrying...
                    </div>
                )}

                {messages.length === 0 && !isStreaming && !connectionError && (() => {
                    const welcome = (user?.role && ROLE_WELCOME[user.role]) || DEFAULT_WELCOME;
                    return (
                        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
                            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#1e3a5f]/10">
                                <MessageSquare className="h-6 w-6 text-[#1e3a5f]" aria-hidden="true" />
                            </div>
                            <p className="text-sm font-medium text-foreground">{welcome.heading}</p>
                            <p className="text-xs text-muted-foreground">{welcome.subtext}</p>
                        </div>
                    );
                })()}

                {messages.map((msg) => (
                    <ChatBubble key={msg.id} message={msg} />
                ))}

            </div>

            {/* Input */}
            <div className="border-t border-border p-3">
                <div
                    className="flex cursor-text items-end gap-2 rounded-xl border border-border bg-slate-50 px-3 py-2 focus-within:border-[#1e3a5f] focus-within:ring-1 focus-within:ring-[#1e3a5f] dark:bg-slate-800"
                    onClick={() => inputRef.current?.focus()}
                >
                    <textarea
                        ref={inputRef}
                        value={input}
                        onChange={(e) => {
                            setInput(e.target.value);
                            e.target.style.height = 'auto';
                            e.target.style.height = `${Math.min(e.target.scrollHeight, 96)}px`;
                        }}
                        onKeyDown={handleKeyDown}
                        placeholder="Type your message..."
                        rows={1}
                        className="flex-1 resize-none bg-transparent text-sm leading-snug text-foreground outline-none placeholder:text-muted-foreground"
                    />
                    <button
                        onClick={handleSend}
                        disabled={!input.trim() || isStreaming}
                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#1e3a5f] text-white transition-colors hover:bg-[#1e3a5f]/90 disabled:opacity-40"
                        aria-label="Send message"
                    >
                        {isStreaming ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                            <Send className="h-4 w-4" />
                        )}
                    </button>
                </div>
            </div>
        </>
    );

    return (
        <>
            {/* Desktop: fixed right sidebar */}
            <aside
                className="fixed bottom-0 right-0 top-[81px] hidden w-[320px] flex-col border-l border-border bg-white dark:bg-slate-900 lg:flex"
                aria-label="Chat Assistant"
                role="complementary"
            >
                {sidebarContent}
            </aside>

            {/* Mobile: toggle button + sliding panel */}
            {!isMobileOpen && (
                <button
                    onClick={() => setIsMobileOpen(true)}
                    className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-[#1e3a5f] text-white shadow-lg transition-all hover:scale-105 hover:bg-[#1e3a5f]/90 lg:hidden"
                    aria-label="Open chat assistant"
                >
                    <MessageSquare className="h-6 w-6" />
                </button>
            )}

            {isMobileOpen && (
                <aside
                    className="fixed bottom-0 left-0 right-0 top-0 z-50 flex flex-col bg-white dark:bg-slate-900 lg:hidden"
                    aria-label="Chat Assistant"
                    role="complementary"
                >
                    {sidebarContent}
                </aside>
            )}
        </>
    );
}
