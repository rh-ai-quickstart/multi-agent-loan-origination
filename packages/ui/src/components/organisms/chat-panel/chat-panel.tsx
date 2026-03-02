// This project was developed with assistance from AI tools.

import { useState, useRef, useEffect } from 'react';
import { MessageSquare, X, Send, Loader2 } from 'lucide-react';
import { useChat, type ChatMessage } from '@/hooks/use-chat';
import { useChatContext } from '@/contexts/chat-context';
import { cn } from '@/lib/utils';

function ChatBubble({ message }: { message: ChatMessage }) {
    const isUser = message.role === 'user';

    return (
        <div className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
            <div
                className={cn(
                    'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
                    isUser
                        ? 'bg-[#1e3a5f] text-white'
                        : 'bg-slate-100 text-slate-900 dark:bg-slate-800 dark:text-slate-100',
                )}
            >
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.toolCalls && message.toolCalls.length > 0 && (
                    <div className="mt-2 flex flex-col gap-1">
                        {message.toolCalls.map((tc, i) => (
                            <span
                                key={i}
                                className="inline-flex items-center gap-1 rounded-md bg-black/10 px-2 py-0.5 text-xs dark:bg-white/10"
                            >
                                Used: {tc.name}
                            </span>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}

function TypingIndicator() {
    return (
        <div className="flex justify-start">
            <div className="flex items-center gap-1.5 rounded-2xl bg-slate-100 px-4 py-3 dark:bg-slate-800">
                <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]" />
            </div>
        </div>
    );
}

export function ChatPanel() {
    const { isOpen, closeChat, initialMessage, clearInitialMessage } = useChatContext();
    const { messages, isStreaming, isConnected, sendMessage, connect } = useChat({
        path: '/api/chat',
    });
    const [input, setInput] = useState('');
    const scrollRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const initialMessageSentRef = useRef(false);

    // Connect on open
    useEffect(() => {
        if (isOpen) {
            connect();
            setTimeout(() => inputRef.current?.focus(), 300);
        }
    }, [isOpen, connect]);

    // Send initial message once connected
    useEffect(() => {
        if (isOpen && isConnected && initialMessage && !initialMessageSentRef.current) {
            initialMessageSentRef.current = true;
            sendMessage(initialMessage);
            clearInitialMessage();
        }
    }, [isOpen, isConnected, initialMessage, sendMessage, clearInitialMessage]);

    // Reset the sent flag when initial message changes
    useEffect(() => {
        if (initialMessage) {
            initialMessageSentRef.current = false;
        }
    }, [initialMessage]);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
    }, [messages, isStreaming]);

    const handleSend = () => {
        if (!input.trim() || isStreaming) return;
        sendMessage(input);
        setInput('');
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <aside
            className={cn(
                'fixed bottom-0 right-0 top-0 z-50 flex w-full max-w-md flex-col border-l border-border bg-white shadow-2xl transition-transform duration-300 dark:bg-slate-900',
                isOpen ? 'translate-x-0' : 'translate-x-full',
            )}
            aria-label="AI Chat Assistant"
            role="complementary"
        >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
                <div className="flex items-center gap-2.5">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#1e3a5f]">
                        <MessageSquare className="h-4 w-4 text-white" aria-hidden="true" />
                    </div>
                    <div>
                        <h2 className="text-sm font-semibold text-foreground">
                            Summit Cap Assistant
                        </h2>
                        <p className="text-xs text-muted-foreground">
                            Ask about loans, rates, or eligibility
                        </p>
                    </div>
                </div>
                <button
                    onClick={closeChat}
                    className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-slate-100 hover:text-foreground dark:hover:bg-slate-800"
                    aria-label="Close chat"
                >
                    <X className="h-5 w-5" />
                </button>
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
                {messages.length === 0 && !isStreaming && (
                    <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[#1e3a5f]/10">
                            <MessageSquare
                                className="h-6 w-6 text-[#1e3a5f]"
                                aria-hidden="true"
                            />
                        </div>
                        <div>
                            <p className="text-sm font-medium text-foreground">
                                How can I help you today?
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground">
                                I can help with loan products, rate comparisons, pre-qualification,
                                and more.
                            </p>
                        </div>
                        <div className="flex flex-wrap justify-center gap-2 pt-2">
                            {[
                                'What loan products do you offer?',
                                'How much home can I afford?',
                                'Compare fixed vs adjustable rates',
                            ].map((suggestion) => (
                                <button
                                    key={suggestion}
                                    onClick={() => sendMessage(suggestion)}
                                    className="rounded-full border border-border px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:border-[#1e3a5f] hover:text-[#1e3a5f]"
                                >
                                    {suggestion}
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {messages.map((msg) => (
                    <ChatBubble key={msg.id} message={msg} />
                ))}

                {isStreaming && messages[messages.length - 1]?.role !== 'assistant' && (
                    <TypingIndicator />
                )}
            </div>

            {/* Input */}
            <div className="border-t border-border p-3">
                <div className="flex items-center gap-2 rounded-xl border border-border bg-slate-50 px-3 py-2 focus-within:border-[#1e3a5f] focus-within:ring-1 focus-within:ring-[#1e3a5f] dark:bg-slate-800">
                    <input
                        ref={inputRef}
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Type your message..."
                        disabled={isStreaming}
                        className="flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
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
        </aside>
    );
}

let hasEngagedChat = false;

export function ChatFab({ onClick }: { onClick: () => void }) {
    const [showPrompt, setShowPrompt] = useState(false);
    const [isBouncing, setIsBouncing] = useState(false);

    useEffect(() => {
        if (hasEngagedChat) return;
        const showTimer = setTimeout(() => {
            setShowPrompt(true);
            setIsBouncing(true);
        }, 5000);
        return () => clearTimeout(showTimer);
    }, []);

    useEffect(() => {
        if (!isBouncing) return;
        const stopTimer = setTimeout(() => setIsBouncing(false), 3000);
        return () => clearTimeout(stopTimer);
    }, [isBouncing]);

    function handleClick() {
        hasEngagedChat = true;
        setShowPrompt(false);
        setIsBouncing(false);
        onClick();
    }

    return (
        <div className="fixed bottom-6 right-6 z-40 flex items-end gap-3">
            {showPrompt && (
                <button
                    onClick={handleClick}
                    className="relative mb-2 animate-fade-in rounded-xl bg-white px-4 py-2.5 text-sm font-medium text-[#1e3a5f] shadow-lg transition-transform hover:scale-105 dark:bg-slate-800 dark:text-blue-300"
                >
                    How can I help?
                    <span className="absolute -right-1.5 bottom-2.5 h-3 w-3 rotate-45 bg-white shadow-lg dark:bg-slate-800" />
                </button>
            )}
            <button
                onClick={handleClick}
                className={cn(
                    'flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-[#cc0000] text-white shadow-lg transition-all hover:scale-105 hover:bg-[#990000] hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#cc0000] focus-visible:ring-offset-2',
                    isBouncing && 'animate-bounce',
                )}
                aria-label="Open AI chat assistant"
            >
                <MessageSquare className="h-6 w-6" />
            </button>
        </div>
    );
}
