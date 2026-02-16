
import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { AppStateProvider } from '@/contexts/AppStateContext';
import RootLayout from '@/layouts/RootLayout';
import { LoadingSpinner } from '@/components/ui';

// --- Lazy-loaded page chunks (route-based code splitting) ---

// Dashboard (initial landing)
const DashboardPage = lazy(() => import('@/pages/dashboard/DashboardPage'));

// Explorer section
const KernelSchemaPage = lazy(() => import('@/pages/explorer/KernelSchemaPage'));
const ProfileGraphPage = lazy(() => import('@/pages/explorer/ProfileGraphPage'));
const RulesPage = lazy(() => import('@/pages/explorer/RulesPage'));
const DevTopologyPage = lazy(() => import('@/pages/explorer/DevTopologyPage'));

// Needs section
const NeedsCatalogPage = lazy(() => import('@/pages/needs/NeedsCatalogPage'));

// Governance section
const RuleLifecyclePage = lazy(() => import('@/pages/governance/RuleLifecyclePage'));
const ModelsPage = lazy(() => import('@/pages/governance/ModelsPage'));
const DecisionsPage = lazy(() => import('@/pages/governance/DecisionsPage'));
const SimulationPage = lazy(() => import('@/pages/governance/SimulationPage'));
const BusinessFlowPage = lazy(() => import('@/pages/governance/BusinessFlowPage'));
const ImpactAnalysisPage = lazy(() => import('@/pages/governance/ImpactAnalysisPage'));

// Schema section
const SchemaPage = lazy(() => import('@/pages/schema/SchemaPage'));

// Status section
const EntitiesPage = lazy(() => import('@/pages/status/EntitiesPage'));
const RelationsPage = lazy(() => import('@/pages/status/RelationsPage'));
const StatusRulesPage = lazy(() => import('@/pages/status/RulesPage'));
const LayersPage = lazy(() => import('@/pages/status/LayersPage'));
const FrameworksPage = lazy(() => import('@/pages/status/FrameworksPage'));
const StatusKernelPage = lazy(() => import('@/pages/status/KernelSchemaPage'));

// Admin section
const BusinessModelsPage = lazy(() => import('@/pages/admin/BusinessModelsPage'));
const I18nPage = lazy(() => import('@/pages/admin/I18nPage'));
const SystemSelfModelPage = lazy(() => import('@/pages/admin/SystemSelfModelPage'));

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            staleTime: 30_000,
            retry: 1,
            refetchOnWindowFocus: false,
        },
    },
});

function PageFallback() {
    return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
            <LoadingSpinner message="Loading..." />
        </div>
    );
}

export default function App() {
    return (
        <QueryClientProvider client={queryClient}>
            <ThemeProvider>
                <AppStateProvider>
                    <BrowserRouter>
                        <Routes>
                            <Route element={<RootLayout />}>
                                <Route index element={<Suspense fallback={<PageFallback />}><DashboardPage /></Suspense>} />
                                <Route path="explorer">
                                    <Route path="kernel-schema" element={<Suspense fallback={<PageFallback />}><KernelSchemaPage /></Suspense>} />
                                    <Route path="profile/:profileName" element={<Suspense fallback={<PageFallback />}><ProfileGraphPage /></Suspense>} />
                                    <Route path="rules" element={<Suspense fallback={<PageFallback />}><RulesPage /></Suspense>} />
                                    <Route path="dev-topology" element={<Suspense fallback={<PageFallback />}><DevTopologyPage /></Suspense>} />
                                </Route>
                                <Route path="needs">
                                    <Route path="catalog" element={<Suspense fallback={<PageFallback />}><NeedsCatalogPage /></Suspense>} />
                                    <Route index element={<Navigate to="/needs/catalog" replace />} />
                                </Route>
                                <Route path="governance">
                                    <Route path="rule-lifecycle" element={<Suspense fallback={<PageFallback />}><RuleLifecyclePage /></Suspense>} />
                                    <Route path="models" element={<Suspense fallback={<PageFallback />}><ModelsPage /></Suspense>} />
                                    <Route path="decisions" element={<Suspense fallback={<PageFallback />}><DecisionsPage /></Suspense>} />
                                    <Route path="simulation" element={<Suspense fallback={<PageFallback />}><SimulationPage /></Suspense>} />
                                    <Route path="business-flow" element={<Suspense fallback={<PageFallback />}><BusinessFlowPage /></Suspense>} />
                                    <Route path="impact" element={<Suspense fallback={<PageFallback />}><ImpactAnalysisPage /></Suspense>} />
                                </Route>
                                <Route path="schema">
                                    <Route path=":layerKey" element={<Suspense fallback={<PageFallback />}><SchemaPage /></Suspense>} />
                                    <Route index element={<Navigate to="/schema/kernel" replace />} />
                                </Route>
                                <Route path="status">
                                    <Route path="entities" element={<Suspense fallback={<PageFallback />}><EntitiesPage /></Suspense>} />
                                    <Route path="relations" element={<Suspense fallback={<PageFallback />}><RelationsPage /></Suspense>} />
                                    <Route path="rules" element={<Suspense fallback={<PageFallback />}><StatusRulesPage /></Suspense>} />
                                    <Route path="layers" element={<Suspense fallback={<PageFallback />}><LayersPage /></Suspense>} />
                                    <Route path="frameworks" element={<Suspense fallback={<PageFallback />}><FrameworksPage /></Suspense>} />
                                    <Route path="kernel" element={<Suspense fallback={<PageFallback />}><StatusKernelPage /></Suspense>} />
                                    <Route index element={<Navigate to="/status/entities" replace />} />
                                </Route>
                                <Route path="admin">
                                    <Route path="business" element={<Suspense fallback={<PageFallback />}><BusinessModelsPage /></Suspense>} />
                                    <Route path="i18n" element={<Suspense fallback={<PageFallback />}><I18nPage /></Suspense>} />
                                    <Route path="self-model" element={<Suspense fallback={<PageFallback />}><SystemSelfModelPage /></Suspense>} />
                                    <Route index element={<Navigate to="/admin/business" replace />} />
                                </Route>
                                <Route path="*" element={<Navigate to="/" replace />} />
                            </Route>
                        </Routes>
                    </BrowserRouter>
                </AppStateProvider>
            </ThemeProvider>
        </QueryClientProvider>
    );
}
