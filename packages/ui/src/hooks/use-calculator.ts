// This project was developed with assistance from AI tools.

import { useMutation } from '@tanstack/react-query';
import { calculateAffordability } from '@/services/calculator';

export function useCalculator() {
    return useMutation({
        mutationFn: calculateAffordability,
    });
}
