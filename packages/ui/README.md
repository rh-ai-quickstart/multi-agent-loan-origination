<!-- This project was developed with assistance from AI tools. -->

# Summit Cap Financial UI

React frontend for the Summit Cap Financial multi-agent loan origination system. This package provides 5 persona-specific interfaces (prospect, borrower, loan officer, underwriter, CEO) with real-time WebSocket chat, Keycloak OIDC authentication, and comprehensive loan workflow management.

Part of the [rh-ai-quickstart](https://github.com/rh-ai-quickstart) catalog demonstrating multi-agent AI systems on Red Hat AI / OpenShift AI.

## Technology Stack

- **React 19** with TypeScript
- **Vite** for build tooling and dev server
- **TanStack Router** for file-based routing with type-safe navigation
- **TanStack Query** for server state management, caching, and optimistic updates
- **Tailwind CSS 4** for utility-first styling
- **shadcn/ui** for accessible UI components built on Radix primitives
- **Keycloak JS** for OIDC authentication
- **Zod** for runtime schema validation
- **Vitest + React Testing Library** for component testing
- **Storybook** for isolated component development

## Project Structure

```
src/
├── main.tsx                  # App entry point with providers
├── routes/                   # File-based routes (TanStack Router)
│   ├── __root.tsx            # Root layout
│   ├── index.tsx             # Public landing page (/)
│   ├── sign-in.tsx           # Keycloak sign-in redirect
│   └── _authenticated/       # Protected routes
│       ├── borrower/         # Borrower dashboard + chat
│       ├── loan-officer/     # LO pipeline + application detail
│       ├── underwriter/      # UW workspace + application detail
│       └── ceo/              # CEO dashboard + audit trail
├── components/
│   ├── atoms/                # Basic UI primitives (button, input, card, etc.)
│   ├── molecules/            # Composite components
│   ├── organisms/            # Complex components (chat-panel, product-grid, chat-sidebar)
│   ├── header/               # App header with nav and user menu
│   ├── footer/               # App footer
│   └── theme-provider/       # Dark mode support
├── hooks/                    # TanStack Query wrappers for API integration
├── services/                 # API client functions (HTTP + WebSocket)
├── schemas/                  # Zod schemas for API response validation
├── contexts/                 # React contexts (auth, chat)
├── lib/                      # Utilities (API client, formatting, labels, WebSocket)
└── styles/
    └── globals.css           # Global styles and Tailwind imports
```

## Development Setup

### Prerequisites

- Node.js 20+ (with corepack enabled for pnpm)
- pnpm 9+
- Running API backend on port 8000

### Installation

From the repository root:

```bash
make setup              # Install all dependencies (root + UI + API + DB)
# or
pnpm install
```

### Development

```bash
# From root
make dev                # Start API + UI dev servers

# From packages/ui
pnpm dev                # Start Vite (port 3000) + Storybook (port 6006)
pnpm dev:vite           # Vite only
pnpm dev:storybook      # Storybook only
```

The dev server runs on **http://localhost:3000** with API proxy to http://localhost:8000.

### Environment Variables

Create `.env.local` in `packages/ui/`:

```bash
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=summit-cap
VITE_KEYCLOAK_CLIENT_ID=summit-cap-ui
AUTH_DISABLED=false              # Set to true to bypass Keycloak
```

When `AUTH_DISABLED=true`, the UI creates mock auth tokens for local development without Keycloak.

### Build

```bash
pnpm build              # Build Vite + Storybook
pnpm build:vite         # Vite production build only
pnpm type-check         # TypeScript type checking
```

## Architecture Patterns

### File-Based Routing

Routes are automatically generated from `src/routes/` file structure:

| File | Route |
|------|-------|
| `index.tsx` | `/` |
| `sign-in.tsx` | `/sign-in` |
| `_authenticated.tsx` | Layout for protected routes |
| `_authenticated/borrower/index.tsx` | `/borrower` |
| `_authenticated/loan-officer/$applicationId.tsx` | `/loan-officer/:applicationId` |

Route tree regenerates automatically during development. See `routeTree.gen.ts` (do not edit manually).

### API Integration Pattern

The UI follows a strict layered pattern: **Component → Hook → TanStack Query → Service → API**

```typescript
// 1. Define Zod schema
// schemas/applications.ts
export const applicationSchema = z.object({
    id: z.number(),
    applicant_name: z.string(),
    status: z.string(),
});

// 2. Create service function
// services/applications.ts
export async function fetchApplications() {
    const response = await apiClient.get('/api/applications/');
    return z.array(applicationSchema).parse(response);
}

// 3. Create hook
// hooks/use-applications.ts
export function useApplications() {
    return useQuery({
        queryKey: ['applications'],
        queryFn: fetchApplications,
    });
}

// 4. Use in component
function ApplicationList() {
    const { data, isLoading } = useApplications();
    // ...
}
```

**Rules:**
- Components call hooks, never services directly
- Services handle HTTP + validation, hooks handle React state
- All API responses validated with Zod schemas at service layer

### WebSocket Chat

Real-time chat uses `lib/ws.ts` WebSocket client with auto-reconnect:

```typescript
import { useChat } from '@/hooks/use-chat';

function ChatPanel() {
    const {
        messages,
        sendMessage,
        isConnected,
        isLoading,
    } = useChat(role);  // 'borrower' | 'lo' | 'underwriter' | 'ceo'

    const handleSubmit = (text: string) => {
        sendMessage(text);
    };

    return (
        <ChatBubble messages={messages} onSubmit={handleSubmit} />
    );
}
```

WebSocket endpoints:
- `ws://localhost:8000/api/public/chat` (unauthenticated)
- `ws://localhost:8000/api/borrower/chat` (requires JWT)
- `ws://localhost:8000/api/lo/chat` (requires JWT)
- `ws://localhost:8000/api/underwriter/chat` (requires JWT)
- `ws://localhost:8000/api/ceo/chat` (requires JWT)

### Authentication

Keycloak OIDC authentication via `contexts/auth-context.tsx`:

```typescript
import { useAuth } from '@/contexts/auth-context';

function ProtectedPage() {
    const { user, roles, logout } = useAuth();

    if (!user) return <Navigate to="/sign-in" />;

    return (
        <div>
            <p>Welcome, {user.name}</p>
            {roles.includes('loan_officer') && <LODashboard />}
        </div>
    );
}
```

JWT tokens are automatically attached to API requests via `AuthHeaderSync` component.

## Component Development

### Using shadcn/ui

Add pre-built accessible components:

```bash
npx shadcn@latest add button
npx shadcn@latest add dialog
npx shadcn@latest add table
```

Components install to `src/components/atoms/` (configured in `components.json`).

### Component Organization

- **Atoms** (`components/atoms/`): Single-purpose primitives (button, input, card, badge, skeleton, label, tooltip, separator, dropdown-menu, chat-bubble)
- **Molecules** (`components/molecules/`): Composite components built from atoms
- **Organisms** (`components/organisms/`): Complex features (chat-panel, product-grid, chat-sidebar)

### Storybook

Each component should have a `.stories.tsx` file for isolated development:

```typescript
// components/atoms/button/button.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './button';

const meta: Meta<typeof Button> = {
    title: 'Atoms/Button',
    component: Button,
};

export default meta;
type Story = StoryObj<typeof Button>;

export const Primary: Story = {
    args: {
        variant: 'default',
        children: 'Click me',
    },
};
```

Run Storybook: `pnpm dev:storybook` (port 6006)

## Testing

### Running Tests

```bash
pnpm test               # Watch mode
pnpm test:run           # Single run
pnpm test:coverage      # With coverage report
```

### Writing Tests

Co-locate tests next to components:

```typescript
// components/atoms/button/button.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { Button } from './button';

describe('Button', () => {
    it('should call onClick when clicked', async () => {
        const handleClick = vi.fn();
        render(<Button onClick={handleClick}>Click</Button>);

        await userEvent.click(screen.getByRole('button'));

        expect(handleClick).toHaveBeenCalledOnce();
    });
});
```

Test utilities in `src/test/` provide providers for components requiring auth/query context.

## Code Quality

```bash
pnpm lint               # ESLint
pnpm lint:fix           # Auto-fix issues
pnpm format             # Prettier
pnpm format:check       # Check formatting
```

Linting runs automatically on commit via Husky pre-commit hook.

## Deployment

### Container Build

The UI is containerized with nginx for production:

```bash
# From root
make containers-build

# Run container
podman run -p 8080:8080 summit-cap-ui:latest
```

The Containerfile uses multi-stage build:
1. **Builder stage**: Install deps + build Vite assets
2. **Runtime stage**: Serve static files with nginx on port 8080

Container includes client-side routing fallback and static asset caching.

### OpenShift Deployment

Deploy via Helm from repository root:

```bash
make deploy
# or
helm install summit-cap deploy/helm/summit-cap-financial -f deploy/helm/values-dev.yaml
```

UI service exposes port 8080 and connects to API via cluster DNS.

## Key Features by Persona

### Prospect (Public)
- Product catalog with mortgage offerings
- Affordability calculator
- Public chat with pre-qualification agent

### Borrower
- Real-time chat with borrower assistant
- Application status tracking
- Document upload
- Disclosure acknowledgment
- Co-borrower management
- Condition response

### Loan Officer
- Pipeline dashboard with urgency scoring
- Application detail view with timeline
- Document management (request resubmission)
- Communication drafting tools
- Submit to underwriting

### Underwriter
- Application detail with compliance checks
- Risk assessment tools
- Preliminary recommendation
- Decision workflow (approve/deny/conditions)

### CEO
- Analytics dashboard (pipeline summary, denial trends, LO performance)
- Model monitoring (latency, token usage, errors, routing)
- Audit trail search
- Decision trace viewer
- Chat with executive AI assistant

## License

This project is part of the Red Hat AI Quickstart catalog. See repository root for license information.
