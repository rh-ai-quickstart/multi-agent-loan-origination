// This project was developed with assistance from AI tools.

import { z } from 'zod';

export const FeaturesSchema = z.object({
    predictive_model: z.boolean(),
});

export type Features = z.infer<typeof FeaturesSchema>;

export const getFeatures = async (): Promise<Features> => {
    const response = await fetch('/api/features');
    if (!response.ok) {
        throw new Error('Failed to fetch features');
    }
    const data = await response.json();
    return FeaturesSchema.parse(data);
};
