// This project was developed with assistance from AI tools.

import { createFileRoute } from '@tanstack/react-router';
import { Hero } from '../components/hero/hero';
import { AffordabilityForm } from '../components/molecules/affordability-form/affordability-form';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const Route = createFileRoute('/' as any)({
    component: Index,
});

function Index() {
    return (
        <div className="flex flex-col">
            <Hero />
            <AffordabilityForm />
        </div>
    );
}
