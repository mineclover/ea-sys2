
interface BadgeProps {
    label: string;
    color?: string;
    bg?: string;
    size?: 'sm' | 'md';
}

const PRESETS: Record<string, { bg: string; color: string }> = {
    // Status
    DRAFT: { bg: 'var(--status-warning-bg)', color: 'var(--status-warning-text)' },
    SUBMITTED: { bg: 'var(--status-indigo-bg)', color: 'var(--status-indigo-text)' },
    APPROVED: { bg: 'var(--status-success-bg)', color: 'var(--status-success-text)' },
    ACTIVE: { bg: 'var(--status-info-bg)', color: 'var(--status-info-text)' },
    DEPRECATED: { bg: 'var(--accent)', color: 'var(--muted-foreground)' },
    EXPRESSED: { bg: 'var(--status-indigo-bg)', color: 'var(--status-indigo-text)' },
    ACKNOWLEDGED: { bg: 'var(--status-info-bg)', color: 'var(--status-info-text)' },
    ADDRESSED: { bg: 'var(--status-success-bg)', color: 'var(--status-success-text)' },
    WITHDRAWN: { bg: 'var(--accent)', color: 'var(--muted-foreground)' },
    // Priority
    LOW: { bg: 'var(--accent)', color: 'var(--muted-foreground)' },
    MEDIUM: { bg: 'var(--status-warning-bg)', color: 'var(--status-warning-text)' },
    HIGH: { bg: 'var(--status-error-bg)', color: 'var(--status-error-text)' },
    CRITICAL: { bg: 'var(--status-pink-bg)', color: 'var(--status-pink-text)' },
    // Verdicts
    ALLOW: { bg: 'var(--status-success-bg)', color: 'var(--status-success-text)' },
    DENY: { bg: 'var(--status-error-bg)', color: 'var(--status-error-text)' },
    // Boolean
    PASS: { bg: 'var(--status-success-bg)', color: 'var(--status-success-text)' },
    FAIL: { bg: 'var(--status-error-bg)', color: 'var(--status-error-text)' },
};

export default function Badge({ label, color, bg, size = 'sm' }: BadgeProps) {
    const preset = PRESETS[label.toUpperCase()];
    const finalBg = bg || preset?.bg || 'var(--secondary)';
    const finalColor = color || preset?.color || 'var(--muted-foreground)';
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
