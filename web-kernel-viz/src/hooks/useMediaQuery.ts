import { useState, useEffect } from 'react';

/**
 * A simple hook that returns true when the given CSS media query matches.
 * Listens for changes and re-renders the component accordingly.
 */
export function useMediaQuery(query: string): boolean {
    const [matches, setMatches] = useState(() => {
        if (typeof window === 'undefined') return false;
        return window.matchMedia(query).matches;
    });

    useEffect(() => {
        const mql = window.matchMedia(query);
        const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
        mql.addEventListener('change', handler);
        // Sync in case the initial state was stale
        setMatches(mql.matches);
        return () => mql.removeEventListener('change', handler);
    }, [query]);

    return matches;
}
