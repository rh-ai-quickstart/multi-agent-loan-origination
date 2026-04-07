// This project was developed with assistance from AI tools.

import { cn } from '@/lib/utils';

const PROFILE_PHOTOS: Record<string, string> = {
    'Sarah Mitchell': '/profiles/sarah-mitchell-thumb.jpg',
    'James Torres': '/profiles/james-torres-thumb.jpg',
    'Maria Chen': '/profiles/maria-chen-thumb.jpg',
    'David Park': '/profiles/david-park-thumb.jpg',
    'Sarah Patel': '/profiles/sarah-patel-thumb.jpg',
    'Marcus Williams': '/profiles/marcus-williams-thumb.jpg',
};

function getInitials(name: string): string {
    return name
        .split(' ')
        .map((part) => part[0])
        .join('')
        .toUpperCase()
        .slice(0, 2);
}

const SIZE_CLASSES = {
    sm: 'h-8 w-8 text-xs',
    md: 'h-10 w-10 text-sm',
    lg: 'h-12 w-12 text-base',
    xl: 'h-14 w-14 text-lg',
};

interface AvatarProps {
    name: string;
    size?: 'sm' | 'md' | 'lg' | 'xl';
    ringColor?: string;
    className?: string;
}

export function Avatar({ name, size = 'sm', ringColor, className }: AvatarProps) {
    const src = PROFILE_PHOTOS[name];

    return (
        <span
            className={cn(
                'inline-flex shrink-0 items-center justify-center rounded-full bg-slate-200 font-medium text-slate-600',
                SIZE_CLASSES[size],
                ringColor && `ring-2 ${ringColor}`,
                className,
            )}
        >
            {src ? (
                <img
                    src={src}
                    alt={name}
                    className="h-full w-full rounded-full object-cover"
                />
            ) : (
                getInitials(name)
            )}
        </span>
    );
}
