



export const CustomMarkers = () => {
    return (
        <svg style={{ position: 'absolute', width: 0, height: 0, pointerEvents: 'none' }}>
            <defs>
                {/* Composition: Filled Diamond */}
                <marker id="composition" viewBox="0 0 20 20" refX="10" refY="10" markerWidth="12" markerHeight="12" orient="auto-start-reverse">
                    <path d="M 0 10 L 10 20 L 20 10 L 10 0 Z" fill="currentColor" stroke="none" />
                </marker>

                {/* Aggregation: Empty Diamond */}
                <marker id="aggregation" viewBox="0 0 20 20" refX="10" refY="10" markerWidth="12" markerHeight="12" orient="auto-start-reverse">
                    <path d="M 0 10 L 10 20 L 20 10 L 10 0 Z" fill="white" stroke="currentColor" strokeWidth="2" />
                </marker>

                {/* Assignment: Circle */}
                <marker id="assignment" viewBox="0 0 20 20" refX="10" refY="10" markerWidth="10" markerHeight="10" orient="auto-start-reverse">
                    <circle cx="10" cy="10" r="8" fill="white" stroke="currentColor" strokeWidth="2" />
                </marker>

                {/* Backward: Arrow */}
                <marker id="backward" viewBox="0 0 20 20" refX="10" refY="10" markerWidth="10" markerHeight="10" orient="auto">
                    <path d="M 20 0 L 0 10 L 20 20 Z" fill="currentColor" />
                </marker>

                {/* Directed: Filled Arrow */}
                <marker id="directed" viewBox="0 0 20 20" refX="15" refY="10" markerWidth="10" markerHeight="10" orient="auto">
                    <path d="M 0 0 L 20 10 L 0 20 Z" fill="currentColor" />
                </marker>

                {/* Weak Directed: Empty Arrow */}
                <marker id="weak_directed" viewBox="0 0 20 20" refX="15" refY="10" markerWidth="12" markerHeight="12" orient="auto">
                    <path d="M 0 0 L 20 10 L 0 20 Z" fill="white" stroke="currentColor" strokeWidth="2" />
                </marker>

                {/* Provides: Filled Circle */}
                <marker id="provides" viewBox="0 0 20 20" refX="10" refY="10" markerWidth="10" markerHeight="10" orient="auto">
                    <circle cx="10" cy="10" r="8" fill="currentColor" />
                </marker>

                {/* Constrains: Cross */}
                <marker id="constrains" viewBox="0 0 20 20" refX="10" refY="10" markerWidth="10" markerHeight="10" orient="auto">
                    <path d="M 4 4 L 16 16 M 16 4 L 4 16" stroke="currentColor" strokeWidth="3" fill="none" />
                </marker>

            </defs>
        </svg>
    );
};
