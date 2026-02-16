
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppStateProvider } from '@/contexts/AppStateContext';
import RootLayout from '@/layouts/RootLayout';
import { DashboardPage } from '@/pages/dashboard';
import { KernelSchemaPage, ProfileGraphPage, RulesPage } from '@/pages/explorer';
import { RuleLifecyclePage, ModelsPage, DecisionsPage, SimulationPage } from '@/pages/governance';
import { NeedsCatalogPage } from '@/pages/needs';
import { EntitiesPage, RelationsPage, RulesPage as StatusRulesPage, LayersPage, FrameworksPage, KernelSchemaPage as StatusKernelPage } from '@/pages/status';
import { SchemaPage } from '@/pages/schema';

export default function App() {
    return (
        <AppStateProvider>
            <BrowserRouter>
                <Routes>
                    <Route element={<RootLayout />}>
                        <Route index element={<DashboardPage />} />
                        <Route path="explorer">
                            <Route path="kernel-schema" element={<KernelSchemaPage />} />
                            <Route path="profile/:profileName" element={<ProfileGraphPage />} />
                            <Route path="rules" element={<RulesPage />} />
                        </Route>
                        <Route path="needs">
                            <Route path="catalog" element={<NeedsCatalogPage />} />
                            <Route index element={<Navigate to="/needs/catalog" replace />} />
                        </Route>
                        <Route path="governance">
                            <Route path="rule-lifecycle" element={<RuleLifecyclePage />} />
                            <Route path="models" element={<ModelsPage />} />
                            <Route path="decisions" element={<DecisionsPage />} />
                            <Route path="simulation" element={<SimulationPage />} />
                        </Route>
                        <Route path="schema">
                            <Route path=":layerKey" element={<SchemaPage />} />
                            <Route index element={<Navigate to="/schema/kernel" replace />} />
                        </Route>
                        <Route path="status">
                            <Route path="entities" element={<EntitiesPage />} />
                            <Route path="relations" element={<RelationsPage />} />
                            <Route path="rules" element={<StatusRulesPage />} />
                            <Route path="layers" element={<LayersPage />} />
                            <Route path="frameworks" element={<FrameworksPage />} />
                            <Route path="kernel" element={<StatusKernelPage />} />
                            <Route index element={<Navigate to="/status/entities" replace />} />
                        </Route>
                        <Route path="*" element={<Navigate to="/" replace />} />
                    </Route>
                </Routes>
            </BrowserRouter>
        </AppStateProvider>
    );
}
