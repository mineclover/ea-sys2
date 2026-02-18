
import { useEffect, useState, useCallback } from 'react';
import { Outlet, useLocation, useNavigate, useParams } from 'react-router-dom';
import { TopNav, DetailSlideOver } from '@/components/layout';
import type { Section, SubView } from '@/components/layout/TopNav';
import { useAppState } from '@/contexts/AppStateContext';
import { fetchProfiles } from '@/api/client';
import type { ProfileListItem } from '@/api/types';
import ErrorBoundary from '@/components/ErrorBoundary';

/** Map a URL pathname to the (section, subView) pair TopNav expects. */
function resolveNav(pathname: string): { section: Section; subView: SubView; isDashboard: boolean } {
    if (pathname === '/') {
        return { section: 'explorer', subView: '' as SubView, isDashboard: true };
    }
    if (pathname.startsWith('/admin')) {
        const sub = pathname.split('/')[2] || 'business';
        return { section: 'admin', subView: sub as SubView, isDashboard: false };
    }
    if (pathname.startsWith('/schema')) {
        const sub = pathname.split('/')[2] || 'kernel';
        return { section: 'schema', subView: sub as SubView, isDashboard: false };
    }
    if (pathname.startsWith('/status')) {
        const sub = pathname.split('/')[2] || 'entities';
        return { section: 'status', subView: sub as SubView, isDashboard: false };
    }
    if (pathname.startsWith('/governance')) {
        const sub = pathname.split('/')[2] || 'rule-lifecycle';
        return { section: 'governance', subView: sub as SubView, isDashboard: false };
    }
    if (pathname.startsWith('/needs')) {
        const sub = pathname.split('/')[2] || 'catalog';
        return { section: 'needs', subView: sub as SubView, isDashboard: false };
    }
    const sub = pathname.split('/')[2] || 'kernel-schema';
    const subView = sub === 'profile' ? 'profile-graph' : sub;
    return { section: 'explorer', subView: subView as SubView, isDashboard: false };
}

/** Map a (section, subView) to a URL path. */
function toPath(section: Section, subView: SubView, profileName?: string): string {
    if (section === 'admin') return `/admin/${subView}`;
    if (section === 'schema') return `/schema/${subView}`;
    if (section === 'status') return `/status/${subView}`;
    if (section === 'governance') return `/governance/${subView}`;
    if (section === 'needs') return `/needs/${subView}`;
    if (subView === 'profile-graph') return `/explorer/profile/${profileName || ''}`;
    return `/explorer/${subView}`;
}

export default function RootLayout() {
    const location = useLocation();
    const navigate = useNavigate();
    const params = useParams<{ profileName?: string }>();
    const {
        lang, toggleLang,
        sidePanelOpen, toggleSidePanel, setSidePanelOpen,
        closeDetail, detailOpen, detailTitle, detailContent,
    } = useAppState();

    const { section, subView, isDashboard } = resolveNav(location.pathname);

    // Profile list (fetched once)
    const [profiles, setProfiles] = useState<ProfileListItem[]>([]);
    const selectedProfile = params.profileName || '';

    useEffect(() => {
        if (profiles.length === 0) {
            fetchProfiles()
                .then((list) => {
                    setProfiles(list);
                    // If on profile page with no profileName, redirect to first profile
                    if (subView === 'profile-graph' && !params.profileName && list.length > 0) {
                        const eaSys = list.find((p) => p.name.startsWith('EASystem-'));
                        navigate(`/explorer/profile/${eaSys?.name || list[0].name}`, { replace: true });
                    }
                })
                .catch(() => {});
        }
    }, [profiles.length, subView, params.profileName, navigate]);

    const onNavigate = useCallback((sec: Section, sv: SubView) => {
        closeDetail();
        if (sv === 'profile-graph') {
            setSidePanelOpen(true);
            const name = selectedProfile || profiles[0]?.name || '';
            navigate(toPath(sec, sv, name));
        } else if (sec === 'needs') {
            navigate(toPath(sec, sv));
        } else {
            navigate(toPath(sec, sv));
        }
    }, [navigate, closeDetail, setSidePanelOpen, selectedProfile, profiles]);

    const onSelectProfile = useCallback((name: string) => {
        navigate(`/explorer/profile/${name}`);
    }, [navigate]);

    return (
        <div style={{
            width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column',
            background: 'var(--background)', color: 'var(--foreground)',
        }}>
            {/* Skip to content link for keyboard navigation */}
            <a
                href="#main-content"
                style={{
                    position: 'absolute', left: '-9999px', top: 'auto',
                    width: '1px', height: '1px', overflow: 'hidden',
                }}
                onFocus={(e) => {
                    e.currentTarget.style.position = 'fixed';
                    e.currentTarget.style.left = '16px';
                    e.currentTarget.style.top = '8px';
                    e.currentTarget.style.width = 'auto';
                    e.currentTarget.style.height = 'auto';
                    e.currentTarget.style.overflow = 'visible';
                    e.currentTarget.style.zIndex = '9999';
                    e.currentTarget.style.padding = '8px 16px';
                    e.currentTarget.style.background = 'var(--primary)';
                    e.currentTarget.style.color = 'var(--card)';
                    e.currentTarget.style.borderRadius = '6px';
                    e.currentTarget.style.fontSize = '14px';
                    e.currentTarget.style.fontWeight = '600';
                    e.currentTarget.style.textDecoration = 'none';
                }}
                onBlur={(e) => {
                    e.currentTarget.style.position = 'absolute';
                    e.currentTarget.style.left = '-9999px';
                    e.currentTarget.style.width = '1px';
                    e.currentTarget.style.height = '1px';
                    e.currentTarget.style.overflow = 'hidden';
                }}
            >
                Skip to content
            </a>
            <TopNav
                section={section}
                subView={subView}
                onNavigate={onNavigate}
                onGoHome={() => navigate('/')}
                onToggleSidePanel={toggleSidePanel}
                sidePanelOpen={sidePanelOpen}
                lang={lang}
                onToggleLang={toggleLang}
                profiles={profiles.map((p) => ({ name: p.name, version: p.version }))}
                selectedProfile={selectedProfile}
                onSelectProfile={onSelectProfile}
            />

            <main id="main-content" role="main" style={{ marginTop: isDashboard ? 48 : 76, flex: 1, display: 'flex', overflow: 'hidden' }}>
                <ErrorBoundary>
                    <Outlet />
                </ErrorBoundary>
            </main>

            <DetailSlideOver open={detailOpen} onClose={closeDetail} title={detailTitle}>
                {detailContent}
            </DetailSlideOver>
        </div>
    );
}
