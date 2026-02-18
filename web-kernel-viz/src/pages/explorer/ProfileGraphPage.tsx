
import { useState, useCallback, useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { SidePanel } from '@/components/layout';
import ProfileGraph from '@/components/ProfileGraph';
import ProfileSidePanel from '@/components/ProfileSidePanel';
import { useAppState } from '@/contexts/AppStateContext';
import { useProfileDescription, useNeedsCatalogs, useReachable } from '@/api/hooks';
import { fetchCatalogNeeds, fetchElementScope } from '@/api/client';

const ALL_LAYERS = ['Infra', 'Governance', 'Decision', 'Needs', 'Kernel', 'Flow'];

interface NeedOption {
    id: string;
    label: string;
    kernelRefs: string[];
    catalogId: string;
}

export default function ProfileGraphPage() {
    const { profileName } = useParams<{ profileName: string }>();
    const { lang, sidePanelOpen, setSidePanelOpen, showDetail } = useAppState();

    const [visibleLayers, setVisibleLayers] = useState<Set<string>>(new Set(ALL_LAYERS));
    const [crossLayerOnly, setCrossLayerOnly] = useState(false);
    const [goalScope, setGoalScope] = useState<string | null>(null);
    const [selectedNode, setSelectedNode] = useState<string | null>(null);

    // Need scope
    const [needScope, setNeedScope] = useState<string | null>(null);

    const onToggleLayer = useCallback((layer: string) => {
        setVisibleLayers((prev) => {
            const next = new Set(prev);
            if (next.has(layer)) next.delete(layer);
            else next.add(layer);
            return next;
        });
    }, []);

    // Fetch total element count for scope indicator
    const { data: profileDesc } = useProfileDescription(profileName ?? '', { lang });
    const totalElementCount = profileDesc?.element_count ?? 0;

    // Load need options from catalogs
    const { data: catalogs } = useNeedsCatalogs();
    const catalogIds = useMemo(
        () => (catalogs ?? []).map((c) => c.id).sort().join(','),
        [catalogs],
    );

    const { data: needOptions = [] } = useQuery<NeedOption[]>({
        queryKey: ['needOptions', catalogIds],
        queryFn: async () => {
            if (!catalogs || catalogs.length === 0) return [];
            const results = await Promise.all(
                catalogs.map(async (cat) => {
                    try {
                        const needs = await fetchCatalogNeeds(cat.id);
                        return needs
                            .filter((n) => n.kernel_refs.length > 0)
                            .map((n) => ({
                                id: `${cat.id}::${n.id}`,
                                label: `${n.action} ${n.subject}`,
                                kernelRefs: n.kernel_refs,
                                catalogId: cat.id,
                            }));
                    } catch {
                        return [];
                    }
                }),
            );
            return results.flat();
        },
        enabled: !!catalogs && catalogs.length > 0,
    });

    // Compute scope when goal changes
    const { data: reachableData } = useReachable(
        profileName ?? '',
        goalScope ?? '',
        { max_depth: 4 },
    );
    const scopeElements = useMemo(() => {
        if (!goalScope || !reachableData) return undefined;
        return new Set([goalScope, ...reachableData.reachable]);
    }, [goalScope, reachableData]);

    // Compute need scope when need selection changes
    const selectedNeed = useMemo(
        () => needOptions.find((n) => n.id === needScope) ?? null,
        [needOptions, needScope],
    );
    const selectedKernelRefs = selectedNeed?.kernelRefs ?? [];
    const { data: elementScopeData } = useQuery({
        queryKey: ['elementScope', profileName, selectedKernelRefs],
        queryFn: () => fetchElementScope(profileName!, selectedKernelRefs, { max_depth: 4 }),
        enabled: !!profileName && !!needScope && selectedKernelRefs.length > 0,
    });
    const needScopeElements = useMemo(() => {
        if (!needScope || !elementScopeData) return undefined;
        return new Set(elementScopeData.scope);
    }, [needScope, elementScopeData]);

    // Auto-open side panel when entering this page
    useEffect(() => {
        if (!sidePanelOpen) {
            setSidePanelOpen(true);
        }
    }, [sidePanelOpen, setSidePanelOpen]);

    if (!profileName) {
        return <div style={{ padding: 40, color: 'var(--muted-foreground)', fontFamily: 'system-ui' }}>Loading profiles...</div>;
    }

    // Combine goal + need scope (intersection when both active)
    const combinedScope = useMemo(() => {
        if (scopeElements && needScopeElements) {
            return new Set([...scopeElements].filter((e) => needScopeElements.has(e)));
        }
        return scopeElements || needScopeElements;
    }, [scopeElements, needScopeElements]);

    const scopeCount = useMemo(
        () => (scopeElements ? { visible: scopeElements.size, total: totalElementCount } : null),
        [scopeElements, totalElementCount],
    );

    const needScopeCount = useMemo(
        () => (needScopeElements ? { visible: needScopeElements.size, total: totalElementCount } : null),
        [needScopeElements, totalElementCount],
    );

    return (
        <>
            <SidePanel open={sidePanelOpen}>
                <ProfileSidePanel
                    profileName={profileName}
                    visibleLayers={visibleLayers}
                    onToggleLayer={onToggleLayer}
                    crossLayerOnly={crossLayerOnly}
                    onToggleCrossLayer={() => setCrossLayerOnly((v) => !v)}
                    goalScope={goalScope}
                    onSelectGoalScope={setGoalScope}
                    scopeCount={scopeCount}
                    needScope={needScope}
                    onSelectNeedScope={setNeedScope}
                    needScopeCount={needScopeCount}
                    needOptions={needOptions.map((n) => ({ id: n.id, label: n.label }))}
                    selectedNode={selectedNode}
                />
            </SidePanel>
            <div style={{ flex: 1, overflow: 'hidden' }}>
                <ProfileGraph
                    profileName={profileName}
                    visibleLayers={visibleLayers}
                    crossLayerOnly={crossLayerOnly}
                    scopeElements={combinedScope}
                    onShowDetail={showDetail}
                    lang={lang}
                    onNodeSelect={setSelectedNode}
                />
            </div>
        </>
    );
}
