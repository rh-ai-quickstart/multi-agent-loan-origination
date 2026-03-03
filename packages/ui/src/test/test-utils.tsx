// This project was developed with assistance from AI tools.
/* eslint-disable react-refresh/only-export-components */

/**
 * Test utilities for React component testing
 *
 * Provides a custom render function that wraps components with necessary providers.
 * Use this instead of @testing-library/react's render for components that need:
 * - TanStack Query (useQuery, useMutation)
 * - Theme context
 * - Router context
 */

import { ReactElement, ReactNode } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

/**
 * Create a fresh QueryClient for testing
 * Disables retries and caching for predictable test behavior
 */
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

interface WrapperProps {
  children: ReactNode;
}

/**
 * All-in-one provider wrapper for tests
 */
function AllProviders({ children }: WrapperProps) {
  const queryClient = createTestQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}

/**
 * Custom render function that wraps component with all providers
 *
 * @example
 * ```tsx
 * import { renderWithProviders, screen } from '../test/test-utils';
 *
 * it('renders with providers', () => {
 *   renderWithProviders(<MyComponent />);
 *   expect(screen.getByText('Hello')).toBeInTheDocument();
 * });
 * ```
 */
function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: AllProviders, ...options });
}

// Re-export everything from testing-library
export * from '@testing-library/react';

// Override render with our custom version
export { renderWithProviders };

// Export the test query client creator for advanced use cases
export { createTestQueryClient };
