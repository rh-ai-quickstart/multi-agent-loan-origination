// This project was developed with assistance from AI tools.

import { cn } from '@/lib/utils';
import type { ChatMessage } from '@/hooks/use-chat';

export function ChatBubble({ message }: { message: ChatMessage }) {
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
                {!isUser && message._streaming && !message.content ? (
                    <div className="flex items-center gap-1.5 py-0.5">
                        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:0ms]" />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:150ms]" />
                        <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:300ms]" />
                    </div>
                ) : (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                )}
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

export function TypingIndicator() {
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
