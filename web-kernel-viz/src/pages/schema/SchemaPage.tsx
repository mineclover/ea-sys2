
import { Navigate, useParams } from 'react-router-dom';
import { LayerStackView } from '@/components/schema';
import { useAppState } from '@/contexts/AppStateContext';

const VALID_LAYER_KEYS = new Set(['infra', 'governance', 'decision', 'needs', 'kernel', 'flow']);

function normalizeLayerKey(raw: string | undefined): string {
    if (!raw) return 'kernel';

    const decoded = decodeURIComponent(raw).trim().toLowerCase();
    const head = decoded.split(',')[0].trim().split(/\s+/)[0] || '';
    const trimmed = head.replace(/[.,;:!?]+$/g, '');
    if (VALID_LAYER_KEYS.has(trimmed)) return trimmed;

    const compact = trimmed.replace(/[^a-z]/g, '');
    if (VALID_LAYER_KEYS.has(compact)) return compact;

    for (const key of VALID_LAYER_KEYS) {
        if (decoded.includes(key)) return key;
    }
    return 'kernel';
}

export default function SchemaPage() {
    const { layerKey } = useParams<{ layerKey: string }>();
    const { lang } = useAppState();
    const normalizedLayerKey = normalizeLayerKey(layerKey);
    const normalizedPath = `/schema/${normalizedLayerKey}`;

    if (!layerKey || layerKey !== normalizedLayerKey) {
        return <Navigate to={normalizedPath} replace />;
    }

    return <LayerStackView layerKey={normalizedLayerKey} lang={lang} />;
}
