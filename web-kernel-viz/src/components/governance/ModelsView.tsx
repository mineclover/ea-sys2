
import { useState, type ReactNode } from 'react';
import { useRegisterModel, useValidateModel, useActivateModel } from '@/api/hooks';
import { fetchModelState } from '@/api/client';
import type { ModelState, ModelRegistrationResult, ModelValidationResult, ModelActivationResult } from '@/api/types';
import Badge from '@/components/ui/Badge';
import ErrorBanner from '@/components/ui/ErrorBanner';

interface ModelsViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

type TabType = 'lookup' | 'register' | 'validate';

// --- Model Lookup Tab ---

function ModelLookupTab() {
    const [modelName, setModelName] = useState('');
    const [state, setState] = useState<ModelState | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleLookup = () => {
        if (!modelName.trim()) return;
        setLoading(true);
        setError(null);
        setState(null);

        fetchModelState(modelName.trim())
            .then((data) => {
                setState(data);
                setLoading(false);
            })
            .catch((err) => {
                setError(String(err));
                setLoading(false);
            });
    };

    return (
        <div style={{ padding: 16, fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{ marginBottom: 16 }}>
                <label style={{
                    display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)',
                    textTransform: 'uppercase', marginBottom: 6,
                }}>
                    Model Name
                </label>
                <div style={{ display: 'flex', gap: 8 }}>
                    <input
                        type="text"
                        value={modelName}
                        onChange={(e) => setModelName(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleLookup()}
                        placeholder="e.g. my-governance-model"
                        style={{
                            flex: 1, padding: '6px 10px', fontSize: 12, border: '1px solid var(--border-strong)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                    <button
                        onClick={handleLookup}
                        disabled={!modelName.trim() || loading}
                        style={{
                            padding: '6px 16px', fontSize: 12, fontWeight: 600,
                            border: '1px solid var(--accent)', borderRadius: 4,
                            background: 'var(--accent)', color: 'var(--bg-card)', cursor: 'pointer',
                            opacity: (!modelName.trim() || loading) ? 0.5 : 1,
                        }}
                    >
                        {loading ? 'Loading...' : 'Lookup'}
                    </button>
                </div>
            </div>

            {error && <ErrorBanner message={error} />}

            {state && (
                <div style={{
                    border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px',
                    background: 'var(--bg-secondary)',
                }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
                        {state.model_name}
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                        <Badge label={state.status} />
                        {state.active_version_id && (
                            <Badge label={`Active: ${state.active_version_id}`} bg="var(--success-bg)" color="var(--success-text)" />
                        )}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                        Owner: <strong>{state.owner}</strong>
                    </div>
                    {Object.keys(state).filter((k) => !['model_name', 'status', 'active_version_id', 'owner'].includes(k)).length > 0 && (
                        <details style={{ marginTop: 8 }}>
                            <summary style={{ fontSize: 10, color: 'var(--text-muted)', cursor: 'pointer' }}>
                                Additional fields
                            </summary>
                            <pre style={{
                                fontSize: 10, color: 'var(--text-secondary)', marginTop: 4, padding: 8,
                                background: 'var(--bg-secondary)', borderRadius: 4, overflow: 'auto',
                            }}>
                                {JSON.stringify(state, null, 2)}
                            </pre>
                        </details>
                    )}
                </div>
            )}
        </div>
    );
}

// --- Register Model Tab ---

function RegisterModelTab() {
    const [profileToml, setProfileToml] = useState('');
    const [owner, setOwner] = useState('');
    const [modelNameOverride, setModelNameOverride] = useState('');
    const [activate, setActivate] = useState(false);
    const [onExists, setOnExists] = useState('error');

    const registerMutation = useRegisterModel();

    const handleRegister = () => {
        if (!profileToml.trim()) return;

        const body: {
            profile_toml: string;
            owner?: string;
            model_name?: string;
            activate?: boolean;
            on_exists?: string;
        } = { profile_toml: profileToml };

        if (owner.trim()) body.owner = owner.trim();
        if (modelNameOverride.trim()) body.model_name = modelNameOverride.trim();
        if (activate) body.activate = true;
        if (onExists !== 'error') body.on_exists = onExists;

        registerMutation.mutate(body);
    };

    return (
        <div style={{ padding: 16, fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{ marginBottom: 12 }}>
                <label style={{
                    display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)',
                    textTransform: 'uppercase', marginBottom: 6,
                }}>
                    Profile TOML
                </label>
                <textarea
                    value={profileToml}
                    onChange={(e) => setProfileToml(e.target.value)}
                    placeholder="Paste TOML profile content here..."
                    style={{
                        width: '100%', minHeight: 200, padding: '8px 10px', fontSize: 11,
                        fontFamily: 'Monaco, monospace', border: '1px solid var(--border-strong)',
                        borderRadius: 4, outline: 'none', resize: 'vertical',
                    }}
                />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)',
                        textTransform: 'uppercase', marginBottom: 6,
                    }}>
                        Owner (optional)
                    </label>
                    <input
                        type="text"
                        value={owner}
                        onChange={(e) => setOwner(e.target.value)}
                        placeholder="e.g. admin"
                        style={{
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--border-strong)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                </div>

                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)',
                        textTransform: 'uppercase', marginBottom: 6,
                    }}>
                        Model Name Override (optional)
                    </label>
                    <input
                        type="text"
                        value={modelNameOverride}
                        onChange={(e) => setModelNameOverride(e.target.value)}
                        placeholder="Override profile name"
                        style={{
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--border-strong)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                </div>
            </div>

            <div style={{ marginBottom: 12 }}>
                <label style={{
                    display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)',
                    textTransform: 'uppercase', marginBottom: 6,
                }}>
                    On Exists
                </label>
                <select
                    value={onExists}
                    onChange={(e) => setOnExists(e.target.value)}
                    style={{
                        padding: '6px 10px', fontSize: 12, border: '1px solid var(--border-strong)',
                        borderRadius: 4, outline: 'none',
                    }}
                >
                    <option value="error">Error</option>
                    <option value="skip">Skip</option>
                    <option value="overwrite">Overwrite</option>
                </select>
            </div>

            <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
                    <input
                        type="checkbox"
                        checked={activate}
                        onChange={(e) => setActivate(e.target.checked)}
                    />
                    <span style={{ color: 'var(--text-secondary)' }}>Activate immediately after registration</span>
                </label>
            </div>

            <button
                onClick={handleRegister}
                disabled={!profileToml.trim() || registerMutation.isPending}
                style={{
                    padding: '8px 20px', fontSize: 12, fontWeight: 600,
                    border: '1px solid var(--accent)', borderRadius: 4,
                    background: 'var(--accent)', color: 'var(--bg-card)', cursor: 'pointer',
                    opacity: (!profileToml.trim() || registerMutation.isPending) ? 0.5 : 1,
                }}
            >
                {registerMutation.isPending ? 'Registering...' : 'Register Model'}
            </button>

            {registerMutation.isError && (
                <div style={{ marginTop: 12 }}>
                    <ErrorBanner message={String(registerMutation.error)} />
                </div>
            )}

            {registerMutation.isSuccess && registerMutation.data && (
                <RegistrationResult result={registerMutation.data} />
            )}
        </div>
    );
}

function RegistrationResult({ result }: { result: ModelRegistrationResult }) {
    return (
        <div style={{
            marginTop: 16, border: '1px solid var(--success-bg)', borderRadius: 8,
            padding: '12px 14px', background: 'var(--success-bg)',
        }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--success-text)', marginBottom: 8 }}>
                Registration Successful
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                <div><strong>Model:</strong> {result.model_name}</div>
                <div><strong>Version:</strong> {result.version}</div>
                <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                    {result.created && <Badge label="CREATED" bg="var(--success-bg)" color="var(--success-text)" />}
                    {result.activated && <Badge label="ACTIVATED" bg="var(--info-bg)" color="var(--accent-text)" />}
                    <Badge label={result.status} />
                </div>
                {result.active_version_id && (
                    <div style={{ marginTop: 4 }}>
                        <strong>Active Version:</strong> {result.active_version_id}
                    </div>
                )}
                {result.validation_run_id && (
                    <div style={{ marginTop: 4, fontSize: 10, color: 'var(--text-secondary)' }}>
                        Validation Run: {result.validation_run_id}
                    </div>
                )}
                {result.transaction_id && (
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                        Transaction: {result.transaction_id}
                    </div>
                )}
            </div>
        </div>
    );
}

// --- Validate/Activate Tab ---

function ValidateActivateTab() {
    const [modelName, setModelName] = useState('');
    const [version, setVersion] = useState('');

    const validateMutation = useValidateModel();
    const activateMutation = useActivateModel();

    const handleValidate = () => {
        if (!modelName.trim() || !version.trim()) return;
        validateMutation.mutate({ model_name: modelName.trim(), version: version.trim() });
    };

    const handleActivate = () => {
        if (!modelName.trim() || !version.trim()) return;
        activateMutation.mutate({ model_name: modelName.trim(), version: version.trim() });
    };

    const validationPassed = validateMutation.isSuccess && validateMutation.data?.passed;

    return (
        <div style={{ padding: 16, fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)',
                        textTransform: 'uppercase', marginBottom: 6,
                    }}>
                        Model Name
                    </label>
                    <input
                        type="text"
                        value={modelName}
                        onChange={(e) => setModelName(e.target.value)}
                        placeholder="e.g. my-governance-model"
                        style={{
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--border-strong)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                </div>

                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)',
                        textTransform: 'uppercase', marginBottom: 6,
                    }}>
                        Version
                    </label>
                    <input
                        type="text"
                        value={version}
                        onChange={(e) => setVersion(e.target.value)}
                        placeholder="e.g. 1.0.0"
                        style={{
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--border-strong)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                </div>
            </div>

            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                <button
                    onClick={handleValidate}
                    disabled={!modelName.trim() || !version.trim() || validateMutation.isPending}
                    style={{
                        padding: '8px 20px', fontSize: 12, fontWeight: 600,
                        border: '1px solid #f59e0b', borderRadius: 4,
                        background: '#f59e0b', color: 'var(--bg-card)', cursor: 'pointer',
                        opacity: (!modelName.trim() || !version.trim() || validateMutation.isPending) ? 0.5 : 1,
                    }}
                >
                    {validateMutation.isPending ? 'Validating...' : 'Validate'}
                </button>

                <button
                    onClick={handleActivate}
                    disabled={!modelName.trim() || !version.trim() || activateMutation.isPending || !validationPassed}
                    style={{
                        padding: '8px 20px', fontSize: 12, fontWeight: 600,
                        border: '1px solid #10b981', borderRadius: 4,
                        background: '#10b981', color: 'var(--bg-card)', cursor: 'pointer',
                        opacity: (!modelName.trim() || !version.trim() || activateMutation.isPending || !validationPassed) ? 0.5 : 1,
                    }}
                >
                    {activateMutation.isPending ? 'Activating...' : 'Activate'}
                </button>
            </div>

            {!validationPassed && (
                <div style={{
                    padding: '10px 12px', border: '1px solid var(--warning-bg)', borderRadius: 6,
                    background: 'var(--warning-bg)', fontSize: 11, color: 'var(--warning-text)',
                }}>
                    Validation must pass before activation is enabled.
                </div>
            )}

            {validateMutation.isError && (
                <div style={{ marginBottom: 12 }}>
                    <ErrorBanner message={String(validateMutation.error)} />
                </div>
            )}

            {validateMutation.isSuccess && validateMutation.data && (
                <ValidationResult result={validateMutation.data} />
            )}

            {activateMutation.isError && (
                <div style={{ marginTop: 12 }}>
                    <ErrorBanner message={String(activateMutation.error)} />
                </div>
            )}

            {activateMutation.isSuccess && activateMutation.data && (
                <ActivationResult result={activateMutation.data} />
            )}
        </div>
    );
}

function ValidationResult({ result }: { result: ModelValidationResult }) {
    return (
        <div style={{
            marginBottom: 12, border: result.passed ? '1px solid var(--success-bg)' : '1px solid var(--error-bg)',
            borderRadius: 8, padding: '12px 14px',
            background: result.passed ? 'var(--success-bg)' : 'var(--error-bg)',
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: result.passed ? 'var(--success-text)' : 'var(--error-text)' }}>
                    Validation Result
                </div>
                <Badge label={result.passed ? 'PASS' : 'FAIL'} />
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                <div><strong>Model:</strong> {result.model_name}</div>
                <div><strong>Version:</strong> {result.version}</div>
                <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
                    Run ID: {result.run_id}
                </div>
                {result.transaction_id && (
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                        Transaction: {result.transaction_id}
                    </div>
                )}
            </div>
            {result.errors && result.errors.length > 0 && (
                <div style={{ marginTop: 8 }}>
                    <div style={{
                        fontSize: 10, fontWeight: 700, color: 'var(--error-text)',
                        textTransform: 'uppercase', marginBottom: 4,
                    }}>
                        Errors
                    </div>
                    {result.errors.map((err, idx) => (
                        <div key={idx} style={{
                            fontSize: 10, color: '#7f1d1d', padding: '4px 6px',
                            background: 'var(--error-bg)', borderRadius: 3, marginBottom: 2,
                        }}>
                            {err}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}

function ActivationResult({ result }: { result: ModelActivationResult }) {
    return (
        <div style={{
            marginTop: 12, border: '1px solid var(--info-bg)', borderRadius: 8,
            padding: '12px 14px', background: 'var(--accent-bg)',
        }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent-text)', marginBottom: 8 }}>
                Activation Successful
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                <div><strong>Model:</strong> {result.model_name}</div>
                <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                    <Badge label={result.status} />
                    {result.active_version_id && (
                        <Badge label={`Active: ${result.active_version_id}`} bg="var(--success-bg)" color="var(--success-text)" />
                    )}
                </div>
                <div style={{ marginTop: 4 }}><strong>Owner:</strong> {result.owner}</div>
                {result.transaction_id && (
                    <div style={{ fontSize: 10, color: 'var(--text-secondary)', marginTop: 4 }}>
                        Transaction: {result.transaction_id}
                    </div>
                )}
            </div>
        </div>
    );
}

// --- Main ModelsView Component ---

export default function ModelsView({ onShowDetail: _onShowDetail }: ModelsViewProps) {
    const [activeTab, setActiveTab] = useState<TabType>('lookup');

    const tabs: { key: TabType; label: string }[] = [
        { key: 'lookup', label: 'Model Lookup' },
        { key: 'register', label: 'Register Model' },
        { key: 'validate', label: 'Validate/Activate' },
    ];

    return (
        <div style={{ height: '100%', display: 'flex', flexDirection: 'column', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            {/* Tab Navigation */}
            <div style={{
                display: 'flex', gap: 0, borderBottom: '1px solid var(--border)',
                background: 'var(--bg-secondary)', padding: '0 16px',
            }}>
                {tabs.map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        style={{
                            padding: '10px 16px', fontSize: 12, fontWeight: 600,
                            border: 'none', background: 'none', cursor: 'pointer',
                            color: activeTab === tab.key ? 'var(--text-primary)' : 'var(--text-muted)',
                            borderBottom: activeTab === tab.key ? '2px solid var(--accent)' : '2px solid transparent',
                            transition: 'all 0.2s',
                        }}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            <div style={{ flex: 1, overflow: 'auto' }}>
                {activeTab === 'lookup' && <ModelLookupTab />}
                {activeTab === 'register' && <RegisterModelTab />}
                {activeTab === 'validate' && <ValidateActivateTab />}
            </div>
        </div>
    );
}
