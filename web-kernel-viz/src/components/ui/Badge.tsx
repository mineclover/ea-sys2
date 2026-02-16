
interface BadgeProps {
    label: string;
    color?: string;
    bg?: string;
    size?: 'sm' | 'md';
}

const PRESETS: Record<string, { bg: string; color: string }> = {
    // Status
    DRAFT: { bg: 'var(--warning-bg)', color: 'var(--warning-text)' },
    SUBMITTED: { bg: 'var(--indigo-bg)', color: 'var(--indigo-text)' },
    APPROVED: { bg: 'var(--success-bg)', color: 'var(--success-text)' },
    ACTIVE: { bg: 'var(--info-bg)', color: 'var(--info-text)' },
    DEPRECATED: { bg: 'var(--bg-hover)', color: 'var(--text-secondary)' },
    EXPRESSED: { bg: 'var(--indigo-bg)', color: 'var(--indigo-text)' },
    ACKNOWLEDGED: { bg: 'var(--info-bg)', color: 'var(--info-text)' },
    ADDRESSED: { bg: 'var(--success-bg)', color: 'var(--success-text)' },
    WITHDRAWN: { bg: 'var(--bg-hover)', color: 'var(--text-secondary)' },
    // Priority
    LOW: { bg: 'var(--bg-hover)', color: 'var(--text-secondary)' },
    MEDIUM: { bg: 'var(--warning-bg)', color: 'var(--warning-text)' },
    HIGH: { bg: 'var(--error-bg)', color: 'var(--error-text)' },
    CRITICAL: { bg: 'var(--pink-bg)', color: 'var(--pink-text)' },
    // Verdicts
    ALLOW: { bg: 'var(--success-bg)', color: 'var(--success-text)' },
    DENY: { bg: 'var(--error-bg)', color: 'var(--error-text)' },
    // Boolean
    PASS: { bg: 'var(--success-bg)', color: 'var(--success-text)' },
    FAIL: { bg: 'var(--error-bg)', color: 'var(--error-text)' },
};

export default function Badge({ label, color, bg, size = 'sm' }: BadgeProps) {
    const preset = PRESETS[label.toUpperCase()];
    const finalBg = bg || preset?.bg || 'var(--bg-secondary)';
    const finalColor = color || preset?.color || 'var(--text-secondary)';
    const fontSize = size === 'sm' ? 10 : 11;
    const padding = size === 'sm' ? '2px 6px' : '3px 8px';

    return (
        <span style={{
            display: 'inline-block',
            fontSize,
            fontWeight: 600,
            padding,
            borderRadius: 4,
            background: finalBg,
            color: finalColor,
            lineHeight: 1.4,
            whiteSpace: 'nowrap',
        }}>
            {label}
        </span>
    );
}
