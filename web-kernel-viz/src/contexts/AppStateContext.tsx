
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import type { Lang } from '@/components/layout/TopNav';

interface AppStateContextValue {
    lang: Lang;
    toggleLang: () => void;
    sidePanelOpen: boolean;
    toggleSidePanel: () => void;
    setSidePanelOpen: (open: boolean) => void;
    showDetail: (title: string, content: ReactNode) => void;
    closeDetail: () => void;
    detailOpen: boolean;
    detailTitle: string;
    detailContent: ReactNode;
}

const AppStateContext = createContext<AppStateContextValue | null>(null);

export function AppStateProvider({ children }: { children: ReactNode }) {
    const [lang, setLang] = useState<Lang>('en');
    const toggleLang = useCallback(() => setLang((v) => (v === 'en' ? 'ko' : 'en')), []);

    const [sidePanelOpen, setSidePanelOpen] = useState(false);
    const toggleSidePanel = useCallback(() => setSidePanelOpen((v) => !v), []);

    const [detailOpen, setDetailOpen] = useState(false);
    const [detailTitle, setDetailTitle] = useState('');
    const [detailContent, setDetailContent] = useState<ReactNode>(null);

    const showDetail = useCallback((title: string, content: ReactNode) => {
        setDetailTitle(title);
        setDetailContent(content);
        setDetailOpen(true);
    }, []);

    const closeDetail = useCallback(() => {
        setDetailOpen(false);
    }, []);

    return (
        <AppStateContext.Provider value={{
            lang, toggleLang,
            sidePanelOpen, toggleSidePanel, setSidePanelOpen,
            showDetail, closeDetail,
            detailOpen, detailTitle, detailContent,
        }}>
            {children}
        </AppStateContext.Provider>
    );
}

export function useAppState() {
    const ctx = useContext(AppStateContext);
    if (!ctx) throw new Error('useAppState must be used within AppStateProvider');
    return ctx;
}
