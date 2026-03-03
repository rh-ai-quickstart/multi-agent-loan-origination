// This project was developed with assistance from AI tools.

import { Link } from '@tanstack/react-router';
import { useChatContext } from '@/contexts/chat-context';

export function Hero() {
    const { openChat } = useChatContext();

    return (
        <section className="w-full bg-gradient-to-b from-slate-50 to-slate-200 py-12 dark:from-background dark:to-card lg:py-20">
            <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
                <div className="flex flex-col-reverse items-center gap-10 lg:flex-row lg:gap-16">
                    {/* Text side */}
                    <div className="flex flex-1 flex-col gap-6 text-center lg:text-left">
                        <h1 className="font-display text-4xl font-bold leading-tight tracking-tight text-foreground sm:text-5xl lg:text-6xl">
                            Your path to{' '}
                            <span className="text-[#1e3a5f] dark:text-blue-300">homeownership</span>{' '}
                            starts here
                        </h1>
                        <p className="max-w-xl text-base leading-7 text-muted-foreground lg:max-w-none">
                            AI-powered mortgage lending that guides you from inquiry to closing.
                            Get personalized loan recommendations, real-time pre-qualification,
                            and dedicated support every step of the way.
                        </p>
                        <div className="flex flex-col items-center gap-3 sm:flex-row lg:items-start">
                            <Link
                                to={'/sign-in' as never}
                                className="inline-flex items-center gap-2 rounded-md bg-[#cc0000] px-6 py-3 text-sm font-bold text-white shadow-sm transition-colors hover:bg-[#990000] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#cc0000] focus-visible:ring-offset-2"
                            >
                                Get Pre-Qualified
                            </Link>
                            <button
                                onClick={() => openChat("What mortgage products do you offer? I'd like to compare my options.")}
                                className="inline-flex items-center gap-2 rounded-md bg-[#cc0000] px-6 py-3 text-sm font-bold text-white shadow-sm transition-colors hover:bg-[#990000] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#cc0000] focus-visible:ring-offset-2"
                            >
                                Explore Products
                            </button>
                        </div>
                    </div>

                    {/* Visual side */}
                    <div className="relative flex-1">
                        <img
                            src="/hero-home.png"
                            alt="Modern home at golden hour"
                            className="aspect-[4/3] w-full rounded-2xl object-cover shadow-md"
                        />

                        {/* Pre-qualified callout */}
                        <div
                            className="absolute -bottom-4 left-4 flex items-center gap-3 rounded-xl border border-border bg-white px-4 py-3 shadow-lg dark:bg-card"
                        >
                            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-100 text-green-600">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-4 w-4">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                                </svg>
                            </span>
                            <div>
                                <p className="text-sm font-semibold text-foreground">Priya was just pre-qualified</p>
                                <p className="text-xs text-muted-foreground">
                                    Approved up to <strong className="text-foreground">$425,000</strong> in minutes
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
