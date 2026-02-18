
import { useState, type ReactNode } from 'react';
import { useRegisterModel, useValidateModel, useActivateModel } from '@/api/hooks';
import { fetchModelState } from '@/api/client';
import type {
    ModelState,
    ModelRegistrationResult,
    ModelValidationResult,
    ModelActivationResult,
    ModelRegisterPayload,
    ModelValidatePayload,
    ModelActivatePayload,
    ModelChangePhase,
} from '@/api/types';
import Badge from '@/components/ui/Badge';
import ErrorBanner from '@/components/ui/ErrorBanner';
import { PageHeader } from '@/components/layout';

interface ModelsViewProps {
    onShowDetail: (title: string, content: ReactNode) => void;
}

type TabType = 'lookup' | 'register' | 'validate';

const CHANGE_PHASE_OPTIONS: { value: ModelChangePhase; label: string }[] = [
    { value: 'planned', label: 'Planned' },
    { value: 'applied', label: 'Applied' },
    { value: 'superseded', label: 'Superseded' },
    { value: 'rolled_back', label: 'Rolled Back' },
];

function parseCommaSeparatedValues(raw: string): string[] {
    return raw
        .split(',')
        .map((token) => token.trim())
        .filter((token) => token.length > 0);
}

function readTraceValue(trace: Record<string, unknown> | null, key: string): string | null {
    if (!trace) return null;
    const value = trace[key];
    if (typeof value !== 'string') return null;
    const normalized = value.trim();
    return normalized.length > 0 ? normalized : null;
}

function DecisionTraceMeta({ trace }: { trace: Record<string, unknown> | null }) {
    const decisionId = readTraceValue(trace, 'decision_id');
    const causeType = readTraceValue(trace, 'cause_type');
    const changePhase = readTraceValue(trace, 'change_phase');
    if (!decisionId && !causeType && !changePhase) return null;

    return (
        <div style={{ marginTop: 8, fontSize: 10, color: 'var(--muted-foreground)' }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>Decision Trace</div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {decisionId && <Badge label={`decision: ${decisionId}`} size="sm" />}
                {causeType && <Badge label={`cause: ${causeType}`} size="sm" />}
                {changePhase && <Badge label={`phase: ${changePhase}`} size="sm" />}
            </div>
        </div>
    );
}

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
                    display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
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
                            flex: 1, padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                    <button
                        onClick={handleLookup}
                        disabled={!modelName.trim() || loading}
                        style={{
                            padding: '6px 16px', fontSize: 12, fontWeight: 600,
                            border: '1px solid var(--primary)', borderRadius: 4,
                            background: 'var(--primary)', color: 'var(--card)', cursor: 'pointer',
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
                    background: 'var(--secondary)',
                }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--foreground)', marginBottom: 8 }}>
                        {state.model_name}
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 8, flexWrap: 'wrap' }}>
                        <Badge label={state.status} />
                        {state.active_version_id && (
                            <Badge label={`Active: ${state.active_version_id}`} bg="var(--status-success-bg)" color="var(--status-success-text)" />
                        )}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                        Owner: <strong>{state.owner}</strong>
                    </div>
                    {Object.keys(state).filter((k) => !['model_name', 'status', 'active_version_id', 'owner'].includes(k)).length > 0 && (
                        <details style={{ marginTop: 8 }}>
                            <summary style={{ fontSize: 10, color: 'var(--muted-foreground)', cursor: 'pointer' }}>
                                Additional fields
                            </summary>
                            <pre style={{
                                fontSize: 10, color: 'var(--muted-foreground)', marginTop: 4, padding: 8,
                                background: 'var(--secondary)', borderRadius: 4, overflow: 'auto',
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
    const [decisionId, setDecisionId] = useState('');
    const [evidenceRefs, setEvidenceRefs] = useState('');
    const [changePhase, setChangePhase] = useState<ModelChangePhase>('planned');
    const [owner, setOwner] = useState('');
    const [modelNameOverride, setModelNameOverride] = useState('');
    const [activate, setActivate] = useState(false);
    const [onExists, setOnExists] = useState<'validate' | 'error'>('validate');

    const registerMutation = useRegisterModel();

    const handleRegister = () => {
        const normalizedDecisionId = decisionId.trim();
        if (!profileToml.trim() || !normalizedDecisionId) return;

        const body: ModelRegisterPayload = {
            profile_toml: profileToml,
            decision_id: normalizedDecisionId,
            change_phase: changePhase,
        };

        if (owner.trim()) body.owner = owner.trim();
        if (modelNameOverride.trim()) body.model_name = modelNameOverride.trim();
        if (activate) body.activate = true;
        if (onExists !== 'validate') body.on_exists = onExists;
        const parsedEvidenceRefs = parseCommaSeparatedValues(evidenceRefs);
        if (parsedEvidenceRefs.length > 0) body.evidence_refs = parsedEvidenceRefs;

        registerMutation.mutate(body);
    };

    return (
        <div style={{ padding: 16, fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{
                marginBottom: 12, border: '1px solid var(--border)', borderRadius: 6,
                padding: '10px 12px', background: 'var(--secondary)',
            }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--foreground)', marginBottom: 4 }}>
                    Decision-first write policy
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                    Register/validate/activate writes must include `decision_id`. Direct cause is fixed as `decision`.
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
                        textTransform: 'uppercase', marginBottom: 6,
                    }}>
                        Decision ID (required)
                    </label>
                    <input
                        type="text"
                        value={decisionId}
                        onChange={(e) => setDecisionId(e.target.value)}
                        placeholder="e.g. DEC-2026-0001"
                        style={{
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                </div>

                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
                        textTransform: 'uppercase', marginBottom: 6,
                    }}>
                        Change Phase
                    </label>
                    <select
                        value={changePhase}
                        onChange={(e) => setChangePhase(e.target.value as ModelChangePhase)}
                        style={{
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                            borderRadius: 4, outline: 'none',
                        }}
                    >
                        {CHANGE_PHASE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>{option.label}</option>
                        ))}
                    </select>
                </div>
            </div>

            <div style={{ marginBottom: 12 }}>
                <label style={{
                    display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
                    textTransform: 'uppercase', marginBottom: 6,
                }}>
                    Evidence Refs (optional, comma-separated)
                </label>
                <input
                    type="text"
                    value={evidenceRefs}
                    onChange={(e) => setEvidenceRefs(e.target.value)}
                    placeholder="ticket-123, run-456, doc-789"
                    style={{
                        width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                        borderRadius: 4, outline: 'none',
                    }}
                />
            </div>

            <div style={{ marginBottom: 12 }}>
                <label style={{
                    display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
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
                        fontFamily: 'Monaco, monospace', border: '1px solid var(--input)',
                        borderRadius: 4, outline: 'none', resize: 'vertical',
                    }}
                />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
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
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                </div>

                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
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
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                </div>
            </div>

            <div style={{ marginBottom: 12 }}>
                <label style={{
                    display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
                    textTransform: 'uppercase', marginBottom: 6,
                }}>
                    On Exists
                </label>
                <select
                    value={onExists}
                    onChange={(e) => setOnExists(e.target.value as 'validate' | 'error')}
                    style={{
                        padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                        borderRadius: 4, outline: 'none',
                    }}
                >
                    <option value="validate">Validate existing version</option>
                    <option value="error">Error if already exists</option>
                </select>
            </div>

            <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, cursor: 'pointer' }}>
                    <input
                        type="checkbox"
                        checked={activate}
                        onChange={(e) => setActivate(e.target.checked)}
                    />
                    <span style={{ color: 'var(--muted-foreground)' }}>Activate immediately after registration</span>
                </label>
            </div>

            <button
                onClick={handleRegister}
                disabled={!profileToml.trim() || !decisionId.trim() || registerMutation.isPending}
                style={{
                    padding: '8px 20px', fontSize: 12, fontWeight: 600,
                    border: '1px solid var(--primary)', borderRadius: 4,
                    background: 'var(--primary)', color: 'var(--card)', cursor: 'pointer',
                    opacity: (!profileToml.trim() || !decisionId.trim() || registerMutation.isPending) ? 0.5 : 1,
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
            marginTop: 16, border: '1px solid var(--status-success-bg)', borderRadius: 8,
            padding: '12px 14px', background: 'var(--status-success-bg)',
        }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--status-success-text)', marginBottom: 8 }}>
                Registration Successful
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted-foreground)', lineHeight: 1.6 }}>
                <div><strong>Model:</strong> {result.model_name}</div>
                <div><strong>Version:</strong> {result.version}</div>
                <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                    {result.created && <Badge label="CREATED" bg="var(--status-success-bg)" color="var(--status-success-text)" />}
                    {result.activated && <Badge label="ACTIVATED" bg="var(--status-info-bg)" color="var(--primary)" />}
                    <Badge label={result.status} />
                </div>
                {result.active_version_id && (
                    <div style={{ marginTop: 4 }}>
                        <strong>Active Version:</strong> {result.active_version_id}
                    </div>
                )}
                {result.validation_run_id && (
                    <div style={{ marginTop: 4, fontSize: 10, color: 'var(--muted-foreground)' }}>
                        Validation Run: {result.validation_run_id}
                    </div>
                )}
                {result.transaction_id && (
                    <div style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>
                        Transaction: {result.transaction_id}
                    </div>
                )}
                <DecisionTraceMeta trace={result.decision_trace} />
            </div>
        </div>
    );
}

// --- Validate/Activate Tab ---

function ValidateActivateTab() {
    const [modelName, setModelName] = useState('');
    const [version, setVersion] = useState('');
    const [decisionId, setDecisionId] = useState('');
    const [evidenceRefs, setEvidenceRefs] = useState('');
    const [validationPhase, setValidationPhase] = useState<ModelChangePhase>('planned');
    const [activationPhase, setActivationPhase] = useState<ModelChangePhase>('applied');

    const validateMutation = useValidateModel();
    const activateMutation = useActivateModel();

    const handleValidate = () => {
        const normalizedDecisionId = decisionId.trim();
        if (!modelName.trim() || !version.trim() || !normalizedDecisionId) return;
        const payload: ModelValidatePayload = {
            model_name: modelName.trim(),
            version: version.trim(),
            decision_id: normalizedDecisionId,
            change_phase: validationPhase,
        };
        const parsedEvidenceRefs = parseCommaSeparatedValues(evidenceRefs);
        if (parsedEvidenceRefs.length > 0) payload.evidence_refs = parsedEvidenceRefs;
        validateMutation.mutate(payload);
    };

    const handleActivate = () => {
        const normalizedDecisionId = decisionId.trim();
        if (!modelName.trim() || !version.trim() || !normalizedDecisionId) return;
        const payload: ModelActivatePayload = {
            model_name: modelName.trim(),
            version: version.trim(),
            decision_id: normalizedDecisionId,
            change_phase: activationPhase,
        };
        const parsedEvidenceRefs = parseCommaSeparatedValues(evidenceRefs);
        if (parsedEvidenceRefs.length > 0) payload.evidence_refs = parsedEvidenceRefs;
        activateMutation.mutate(payload);
    };

    const validationPassed = validateMutation.isSuccess && validateMutation.data?.passed;

    return (
        <div style={{ padding: 16, fontFamily: 'system-ui, -apple-system, sans-serif' }}>
            <div style={{
                marginBottom: 12, border: '1px solid var(--border)', borderRadius: 6,
                padding: '10px 12px', background: 'var(--secondary)',
            }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--foreground)', marginBottom: 4 }}>
                    Decision-linked lifecycle control
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>
                    Validate and activate operations must be linked to the same decision chain.
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
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
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                </div>

                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
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
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
                        textTransform: 'uppercase', marginBottom: 6,
                    }}>
                        Decision ID (required)
                    </label>
                    <input
                        type="text"
                        value={decisionId}
                        onChange={(e) => setDecisionId(e.target.value)}
                        placeholder="e.g. DEC-2026-0001"
                        style={{
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                </div>

                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
                        textTransform: 'uppercase', marginBottom: 6,
                    }}>
                        Evidence Refs (optional)
                    </label>
                    <input
                        type="text"
                        value={evidenceRefs}
                        onChange={(e) => setEvidenceRefs(e.target.value)}
                        placeholder="ticket-123, run-456"
                        style={{
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                            borderRadius: 4, outline: 'none',
                        }}
                    />
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
                        textTransform: 'uppercase', marginBottom: 6,
                    }}>
                        Validate Phase
                    </label>
                    <select
                        value={validationPhase}
                        onChange={(e) => setValidationPhase(e.target.value as ModelChangePhase)}
                        style={{
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                            borderRadius: 4, outline: 'none',
                        }}
                    >
                        {CHANGE_PHASE_OPTIONS.map((option) => (
                            <option key={`validation-${option.value}`} value={option.value}>{option.label}</option>
                        ))}
                    </select>
                </div>

                <div>
                    <label style={{
                        display: 'block', fontSize: 11, fontWeight: 700, color: 'var(--muted-foreground)',
                        textTransform: 'uppercase', marginBottom: 6,
                    }}>
                        Activate Phase
                    </label>
                    <select
                        value={activationPhase}
                        onChange={(e) => setActivationPhase(e.target.value as ModelChangePhase)}
                        style={{
                            width: '100%', padding: '6px 10px', fontSize: 12, border: '1px solid var(--input)',
                            borderRadius: 4, outline: 'none',
                        }}
                    >
                        {CHANGE_PHASE_OPTIONS.map((option) => (
                            <option key={`activation-${option.value}`} value={option.value}>{option.label}</option>
                        ))}
                    </select>
                </div>
            </div>

            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                <button
                    onClick={handleValidate}
                    disabled={!modelName.trim() || !version.trim() || !decisionId.trim() || validateMutation.isPending}
                    style={{
                        padding: '8px 20px', fontSize: 12, fontWeight: 600,
                        border: '1px solid var(--status-warning-text)', borderRadius: 4,
                        background: 'var(--status-warning-text)', color: 'var(--card)', cursor: 'pointer',
                        opacity: (!modelName.trim() || !version.trim() || !decisionId.trim() || validateMutation.isPending) ? 0.5 : 1,
                    }}
                >
                    {validateMutation.isPending ? 'Validating...' : 'Validate'}
                </button>

                <button
                    onClick={handleActivate}
                    disabled={!modelName.trim() || !version.trim() || !decisionId.trim() || activateMutation.isPending || !validationPassed}
                    style={{
                        padding: '8px 20px', fontSize: 12, fontWeight: 600,
                        border: '1px solid var(--status-success-text)', borderRadius: 4,
                        background: 'var(--status-success-text)', color: 'var(--card)', cursor: 'pointer',
                        opacity: (!modelName.trim() || !version.trim() || !decisionId.trim() || activateMutation.isPending || !validationPassed) ? 0.5 : 1,
                    }}
                >
                    {activateMutation.isPending ? 'Activating...' : 'Activate'}
                </button>
            </div>

            {!validationPassed && (
                <div style={{
                    padding: '10px 12px', border: '1px solid var(--status-warning-bg)', borderRadius: 6,
                    background: 'var(--status-warning-bg)', fontSize: 11, color: 'var(--status-warning-text)',
                }}>
                    Validation must pass before activation is enabled. `decision_id` is required for both operations.
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
            marginBottom: 12, border: result.passed ? '1px solid var(--status-success-bg)' : '1px solid var(--status-error-bg)',
            borderRadius: 8, padding: '12px 14px',
            background: result.passed ? 'var(--status-success-bg)' : 'var(--status-error-bg)',
        }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: result.passed ? 'var(--status-success-text)' : 'var(--status-error-text)' }}>
                    Validation Result
                </div>
                <Badge label={result.passed ? 'PASS' : 'FAIL'} />
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted-foreground)', lineHeight: 1.6 }}>
                <div><strong>Model:</strong> {result.model_name}</div>
                <div><strong>Version:</strong> {result.version}</div>
                <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginTop: 4 }}>
                    Run ID: {result.run_id}
                </div>
                {result.transaction_id && (
                    <div style={{ fontSize: 10, color: 'var(--muted-foreground)' }}>
                        Transaction: {result.transaction_id}
                    </div>
                )}
                <DecisionTraceMeta trace={result.decision_trace} />
            </div>
            {result.errors && result.errors.length > 0 && (
                <div style={{ marginTop: 8 }}>
                    <div style={{
                        fontSize: 10, fontWeight: 700, color: 'var(--status-error-text)',
                        textTransform: 'uppercase', marginBottom: 4,
                    }}>
                        Errors
                    </div>
                    {result.errors.map((err, idx) => (
                        <div key={idx} style={{
                            fontSize: 10, color: 'var(--status-error-text)', padding: '4px 6px',
                            background: 'var(--status-error-bg)', borderRadius: 3, marginBottom: 2,
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
            marginTop: 12, border: '1px solid var(--status-info-bg)', borderRadius: 8,
            padding: '12px 14px', background: 'var(--muted)',
        }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--primary)', marginBottom: 8 }}>
                Activation Successful
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted-foreground)', lineHeight: 1.6 }}>
                <div><strong>Model:</strong> {result.model_name}</div>
                <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                    <Badge label={result.status} />
                    {result.active_version_id && (
                        <Badge label={`Active: ${result.active_version_id}`} bg="var(--status-success-bg)" color="var(--status-success-text)" />
                    )}
                </div>
                <div style={{ marginTop: 4 }}><strong>Owner:</strong> {result.owner}</div>
                {result.transaction_id && (
                    <div style={{ fontSize: 10, color: 'var(--muted-foreground)', marginTop: 4 }}>
                        Transaction: {result.transaction_id}
                    </div>
                )}
                <DecisionTraceMeta trace={result.decision_trace} />
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
            <PageHeader metaKey="governance.models" compact />
            {/* Tab Navigation */}
            <div style={{
                display: 'flex', gap: 0, borderBottom: '1px solid var(--border)',
                background: 'var(--secondary)', padding: '0 16px',
            }}>
                {tabs.map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        style={{
                            padding: '10px 16px', fontSize: 12, fontWeight: 600,
                            border: 'none', background: 'none', cursor: 'pointer',
                            color: activeTab === tab.key ? 'var(--foreground)' : 'var(--muted-foreground)',
                            borderBottom: activeTab === tab.key ? '2px solid var(--primary)' : '2px solid transparent',
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
