export interface M1DebugLogEntry {
    ts: number;
    type: 'render' | 'query' | 'event';
    key: string;
    detail?: string;
}

export interface M1DebugSnapshot {
    enabled: boolean;
    renders: Record<string, number>;
    queries: Record<string, number>;
    logs: M1DebugLogEntry[];
    totals: {
        renders: number;
        queries: number;
        logs: number;
    };
}

interface M1DebugState {
    renders: Record<string, number>;
    queries: Record<string, number>;
    logs: M1DebugLogEntry[];
}

const STORAGE_KEY = 'ea.m1.debug';
const LOG_LIMIT = 120;

declare global {
    interface Window {
        __EA_M1_DEBUG_STATE__?: M1DebugState;
    }
}

function parseBooleanFlag(raw: string | null | undefined): boolean {
    if (!raw) return false;
    const normalized = raw.trim().toLowerCase();
    return normalized === '1' || normalized === 'true' || normalized === 'on' || normalized === 'yes';
}

function getState(): M1DebugState {
    if (typeof window === 'undefined') {
        return { renders: {}, queries: {}, logs: [] };
    }
    if (!window.__EA_M1_DEBUG_STATE__) {
        window.__EA_M1_DEBUG_STATE__ = { renders: {}, queries: {}, logs: [] };
    }
    return window.__EA_M1_DEBUG_STATE__;
}

function pushLog(type: M1DebugLogEntry['type'], key: string, detail?: string): void {
    const state = getState();
    state.logs.unshift({ ts: Date.now(), type, key, detail });
    if (state.logs.length > LOG_LIMIT) {
        state.logs.length = LOG_LIMIT;
    }
}

function increment(target: Record<string, number>, key: string): number {
    const next = (target[key] || 0) + 1;
    target[key] = next;
    return next;
}

function summarizeDetail(detail: unknown): string | undefined {
    if (detail == null) return undefined;
    if (typeof detail === 'string') {
        return detail.length > 260 ? `${detail.slice(0, 257)}...` : detail;
    }
    try {
        const text = JSON.stringify(detail);
        return text.length > 260 ? `${text.slice(0, 257)}...` : text;
    } catch {
        return undefined;
    }
}

export function isM1DebugEnabled(): boolean {
    if (typeof window === 'undefined') return false;
    try {
        const params = new URLSearchParams(window.location.search);
        const queryFlag = params.get('m1_debug');
        if (queryFlag != null) return parseBooleanFlag(queryFlag);
        return parseBooleanFlag(window.localStorage.getItem(STORAGE_KEY));
    } catch {
        return false;
    }
}

export function setM1DebugEnabled(enabled: boolean): void {
    if (typeof window === 'undefined') return;
    try {
        window.localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0');
    } catch {
        // no-op in restricted storage contexts
    }
}

export function m1DebugCountRender(key: string): void {
    if (!isM1DebugEnabled()) return;
    const state = getState();
    const count = increment(state.renders, key);
    pushLog('render', key, `count=${count}`);
}

export function m1DebugCountQuery(key: string): void {
    if (!isM1DebugEnabled()) return;
    const state = getState();
    const count = increment(state.queries, key);
    pushLog('query', key, `count=${count}`);
}

export function m1DebugLog(key: string, detail?: unknown): void {
    if (!isM1DebugEnabled()) return;
    pushLog('event', key, summarizeDetail(detail));
}

export function resetM1DebugCounters(): void {
    const state = getState();
    state.renders = {};
    state.queries = {};
    state.logs = [];
}

export function getM1DebugSnapshot(): M1DebugSnapshot {
    const state = getState();
    const renders = { ...state.renders };
    const queries = { ...state.queries };
    const logs = [...state.logs];
    const totalRenders = Object.values(renders).reduce((sum, value) => sum + value, 0);
    const totalQueries = Object.values(queries).reduce((sum, value) => sum + value, 0);
    return {
        enabled: isM1DebugEnabled(),
        renders,
        queries,
        logs,
        totals: {
            renders: totalRenders,
            queries: totalQueries,
            logs: logs.length,
        },
    };
}

