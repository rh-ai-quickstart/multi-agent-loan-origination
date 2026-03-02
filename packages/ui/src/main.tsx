// This project was developed with assistance from AI tools.

import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider, createRouter } from '@tanstack/react-router';
import { routeTree } from './routeTree.gen';
import './styles/globals.css';
import { ThemeProvider } from './components/theme-provider/theme-provider';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TooltipProvider } from './components/atoms/tooltip/tooltip.tsx';
import { AuthProvider } from './contexts/auth-context';
import { AuthHeaderSync } from './contexts/auth-header-sync';

const queryClient = new QueryClient();
const router = createRouter({ routeTree });

declare module '@tanstack/react-router' {
    interface Register {
        router: typeof router;
    }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <ThemeProvider>
            <AuthProvider>
                <AuthHeaderSync />
                <TooltipProvider>
                    <QueryClientProvider client={queryClient}>
                        <RouterProvider router={router} />
                    </QueryClientProvider>
                </TooltipProvider>
            </AuthProvider>
        </ThemeProvider>
    </React.StrictMode>,
);
