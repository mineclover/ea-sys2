
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppStateProvider } from '@/contexts/AppStateContext';
import RootLayout from '@/layouts/RootLayout';
import { KernelSchemaPage, ProfileGraphPage, RulesPage } from '@/pages/explorer';
import { RuleLifecyclePage, ModelsPage, DecisionsPage, SimulationPage } from '@/pages/governance';
import { NeedsCatalogPage } from '@/pages/needs';

export default function App() {
    return (
        <AppStateProvider>
            <BrowserRouter>
                <Routes>
                    <Route element={<RootLayout />}>
                        <Route index element={<Navigate to="/explorer/kernel-schema" replace />} />
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
                        <Route path="*" element={<Navigate to="/explorer/kernel-schema" replace />} />
                    </Route>
                </Routes>
            </BrowserRouter>
        </AppStateProvider>
    );
}
