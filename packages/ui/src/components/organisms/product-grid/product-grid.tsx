// This project was developed with assistance from AI tools.

import { Home, Calendar, Percent, Shield, DollarSign, TrendingDown } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useProducts } from '@/hooks/use-products';
import { Skeleton } from '@/components/atoms/skeleton/skeleton';
import { Badge } from '@/components/atoms/badge/badge';
import { formatPercent } from '@/lib/format';
import type { ProductInfo } from '@/schemas/products';

// Map product names to icons by keyword matching
function getProductIcon(name: string): LucideIcon {
    const lower = name.toLowerCase();
    if (lower.includes('15') || lower.includes('fifteen')) return Calendar;
    if (lower.includes('fha')) return Shield;
    if (lower.includes('va')) return Shield;
    if (lower.includes('usda')) return TrendingDown;
    if (lower.includes('jumbo')) return DollarSign;
    if (lower.includes('arm') || lower.includes('adjustable')) return Percent;
    return Home;
}

interface ProductCardProps {
    product: ProductInfo;
    isPopular?: boolean;
}

function ProductCard({ product, isPopular = false }: ProductCardProps) {
    const Icon = getProductIcon(product.name);
    // API returns rates as whole numbers like 6.5; divide by 100 for formatPercent
    const rateDisplay = formatPercent(product.typical_rate / 100);

    return (
        <article className="group relative flex flex-col overflow-hidden rounded-xl border border-border bg-white shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-xl dark:bg-card">
            {/* Colored top border accent */}
            <div className="h-1 w-full bg-[#1e3a5f]" aria-hidden="true" />

            <div className="flex flex-1 flex-col gap-4 p-6">
                {/* Icon + badge row */}
                <div className="flex items-start justify-between">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#1e3a5f]/10 text-[#1e3a5f] dark:bg-[#1e3a5f]/20">
                        <Icon className="h-5 w-5" aria-hidden="true" />
                    </div>
                    {isPopular && (
                        <Badge className="bg-[#cc0000] text-white hover:bg-[#990000]">
                            Popular
                        </Badge>
                    )}
                </div>

                {/* Name and description */}
                <div className="flex flex-1 flex-col gap-1.5">
                    <h3 className="font-display text-base font-bold text-foreground">
                        {product.name}
                    </h3>
                    <p className="text-sm leading-6 text-muted-foreground">
                        {product.description}
                    </p>
                </div>

                {/* Rate footer */}
                <div className="flex items-end justify-between border-t border-border pt-4">
                    <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                        Interest Rate
                    </span>
                    <div className="flex items-baseline gap-1">
                        <span className="font-display text-2xl font-bold text-[#cc0000]">
                            {rateDisplay}
                        </span>
                        <span className="text-xs text-muted-foreground">APR</span>
                    </div>
                </div>
            </div>
        </article>
    );
}

function ProductCardSkeleton() {
    return (
        <div className="flex flex-col overflow-hidden rounded-xl border border-border bg-white shadow-sm dark:bg-card">
            <div className="h-1 w-full bg-muted" />
            <div className="flex flex-col gap-4 p-6">
                <Skeleton className="h-10 w-10 rounded-lg" />
                <div className="flex flex-col gap-2">
                    <Skeleton className="h-5 w-2/3" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-4/5" />
                </div>
                <div className="border-t border-border pt-4">
                    <Skeleton className="h-8 w-1/3 ml-auto" />
                </div>
            </div>
        </div>
    );
}

export function ProductGrid() {
    const { data: products, isLoading, isError } = useProducts();

    return (
        <section id="products" className="w-full py-16 lg:py-24">
            <div className="mx-auto max-w-[1200px] px-4 sm:px-6 lg:px-8">
                {/* Section header */}
                <div className="mb-12 flex flex-col items-center gap-3 text-center">
                    <span className="text-xs font-semibold uppercase tracking-widest text-[#cc0000]">
                        Our Products
                    </span>
                    <h2 className="font-display text-3xl font-bold text-foreground sm:text-4xl">
                        Find the loan that fits your life
                    </h2>
                    <p className="max-w-2xl text-base text-muted-foreground">
                        From first-time buyers to seasoned investors, we have flexible loan options
                        designed to match your goals and financial situation.
                    </p>
                </div>

                {/* Error state */}
                {isError && (
                    <div
                        role="alert"
                        className="rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center text-sm text-destructive"
                    >
                        Unable to load loan products. Please try again later.
                    </div>
                )}

                {/* Grid */}
                {!isError && (
                    <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
                        {isLoading
                            ? Array.from({ length: 3 }).map((_, i) => (
                                  <ProductCardSkeleton key={i} />
                              ))
                            : products?.slice(0, 3).map((product, index) => (
                                  <ProductCard
                                      key={product.id}
                                      product={product}
                                      isPopular={index === 0}
                                  />
                              ))}
                    </div>
                )}
            </div>
        </section>
    );
}
