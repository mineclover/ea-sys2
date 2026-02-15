
import { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { SidePanel } from '@/components/layout';
import ProfileGraph from '@/components/ProfileGraph';
import ProfileSidePanel from '@/components/ProfileSidePanel';
import { useAppState } from '@/contexts/AppStateContext';
import {
    fetchReachable,
    fetchProfileTopology,
    fetchNeedsCatalogs,
    fetchCatalogNeeds,
    fetchElementScope,
} from '@/api/client';

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
    const [scopeElements, setScopeElements] = useState<Set<string> | undefined>(undefined);
    const [totalElementCount, setTotalElementCount] = useState<number>(0);

    // Need scope
    const [needScope, setNeedScope] = useState<string | null>(null);
    const [needOptions, setNeedOptions] = useState<NeedOption[]>([]);
    const [needScopeElements, setNeedScopeElements] = useState<Set<string> | undefined>(undefined);

    const onToggleLayer = useCallback((layer: string) => {
        setVisibleLayers((prev) => {
            const next = new Set(prev);
            if (next.has(layer)) next.delete(layer);
            else next.add(layer);
            return next;
        });
    }, []);

    // Fetch total element count for scope indicator
    useEffect(() => {
        if (!profileName) return;
        fetchProfileTopology(profileName).then((topo) => {
            setTotalElementCount(topo.node_count);
        }).catch(() => {});
    }, [profileName]);

    // Load need options from catalogs
    useEffect(() => {
        fetchNeedsCatalogs()
            .then(async (catalogs) => {
                const options: NeedOption[] = [];
                for (const cat of catalogs) {
                    try {
                        const needs = await fetchCatalogNeeds(cat.id);
                        for (const n of needs) {
                            if (n.kernel_refs.length > 0) {
                                options.push({
                                    id: `${cat.id}::${n.id}`,
                                    label: `${n.action} ${n.subject}`,
                                    kernelRefs: n.kernel_refs,
                                    catalogId: cat.id,
                                });
                            }
                        }
                    } catch { /* skip catalog on error */ }
                }
                setNeedOptions(options);
            })
            .catch(() => setNeedOptions([]));
    }, []);

    // Compute scope when goal changes
    useEffect(() => {
        if (!goalScope || !profileName) {
            setScopeElements(undefined);
            return;
        }
        fetchReachable(profileName, goalScope, { max_depth: 4 })
            .then((res) => setScopeElements(new Set([goalScope, ...res.reachable])))
            .catch(() => setScopeElements(undefined));
    }, [goalScope, profileName]);

    // Compute need scope when need selection changes
    useEffect(() => {
        if (!needScope || !profileName) {
            setNeedScopeElements(undefined);
            return;
        }
        const selected = needOptions.find((n) => n.id === needScope);
        if (!selected || selected.kernelRefs.length === 0) {
            setNeedScopeElements(undefined);
            return;
        }
        fetchElementScope(profileName, selected.kernelRefs, { max_depth: 4 })
            .then((res) => setNeedScopeElements(new Set(res.scope)))
            .catch(() => setNeedScopeElements(undefined));
    }, [needScope, profileName, needOptions]);

    // Auto-open side panel when entering this page
    useEffect(() => {
        setSidePanelOpen(true);
    }, [setSidePanelOpen]);

    if (!profileName) {
        return <div style={{ padding: 40, color: '#94a3b8', fontFamily: 'system-ui' }}>Loading profiles...</div>;
    }

    // Combine goal + need scope (intersection when both active)
    let combinedScope: Set<string> | undefined;
    if (scopeElements && needScopeElements) {
        combinedScope = new Set([...scopeElements].filter((e) => needScopeElements.has(e)));
    } else {
        combinedScope = scopeElements || needScopeElements;
    }

    const scopeCount = scopeElements
        ? { visible: scopeElements.size, total: totalElementCount }
        : null;

    const needScopeCount = needScopeElements
        ? { visible: needScopeElements.size, total: totalElementCount }
        : null;

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
                />
            </div>
        </>
    );
}
