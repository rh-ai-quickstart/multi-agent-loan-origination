
import { HealthSchema, type Health } from '../schemas/health';

export const getHealth = async (): Promise<Health> => {
  const response = await fetch('/health/');
  if (!response.ok) {
    throw new Error('Failed to fetch health');
  }
  const data = await response.json();
  return HealthSchema.parse(data);
};
