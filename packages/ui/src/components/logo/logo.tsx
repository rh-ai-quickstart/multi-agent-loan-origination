// This project was developed with assistance from AI tools.

export function Logo() {
    return (
        <svg
            width="32"
            height="32"
            viewBox="0 0 32 32"
            fill="none"
            aria-hidden="true"
            className="h-8 w-8 shrink-0"
        >
            {/* Roof peak */}
            <polygon points="16,3 29,14 3,14" fill="#CC0000" />
            {/* Building body */}
            <rect x="6" y="14" width="20" height="15" fill="#CC0000" opacity="0.85" />
            {/* Door */}
            <rect x="13" y="21" width="6" height="8" rx="1" fill="white" opacity="0.9" />
            {/* Left window */}
            <rect x="8" y="17" width="4" height="3" rx="0.5" fill="white" opacity="0.9" />
            {/* Right window */}
            <rect x="20" y="17" width="4" height="3" rx="0.5" fill="white" opacity="0.9" />
        </svg>
    );
}
