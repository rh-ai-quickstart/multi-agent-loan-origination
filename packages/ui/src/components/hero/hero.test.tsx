// This project was developed with assistance from AI tools.

import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import {
    createMemoryHistory,
    createRootRoute,
    createRoute,
    createRouter,
    RouterProvider,
} from '@tanstack/react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Hero } from './hero';

function renderHero() {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    // Minimal router tree: root renders Hero directly, no real route needed
    const rootRoute = createRootRoute({ component: () => <Hero /> });
    const indexRoute = createRoute({
        getParentRoute: () => rootRoute,
        path: '/',
        component: () => null,
    });
    const router = createRouter({
        routeTree: rootRoute.addChildren([indexRoute]),
        history: createMemoryHistory({ initialEntries: ['/'] }),
    });

    return render(
        <QueryClientProvider client={queryClient}>
            <RouterProvider router={router} />
        </QueryClientProvider>,
    );
}

describe('Hero', () => {
    it('should render the main heading with homeownership text', async () => {
        renderHero();
        await waitFor(() => {
            expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
        });
        expect(screen.getByText(/homeownership/i)).toBeInTheDocument();
    });

    it('should render the Get Pre-Qualified call-to-action link', async () => {
        renderHero();
        await waitFor(() => {
            expect(screen.getByRole('link', { name: /get pre-qualified/i })).toBeInTheDocument();
        });
    });

    it('should render trust badges about no hidden fees and instant decisions', async () => {
        renderHero();
        await waitFor(() => {
            expect(screen.getByText(/no hidden fees/i)).toBeInTheDocument();
        });
        expect(screen.getByText(/instant decisions/i)).toBeInTheDocument();
    });

    it('should render the rate alert notification', async () => {
        renderHero();
        await waitFor(() => {
            expect(screen.getByLabelText(/rate alert/i)).toBeInTheDocument();
        });
    });
});
