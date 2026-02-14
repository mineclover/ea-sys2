
# System Port Configuration

This document outlines the standard ports used by the `ea-system` services and their integration strategy.

## 1. Governance Kernel (Core System)
- **Port**: `9000`
- **Service**: `ea-kernel.api.server`
- **Purpose**: Provides the Governance Lifecycle API (Phase 5), including Rule Management, Judgment Execution, and Diagram Visualization.
- **Config**: `EA_KERNEL_PORT=9000`, `EA_KERNEL_DATA_DIR`
- **Launch Command**:
  ```bash
  export EA_KERNEL_DATA_DIR=./governance_data
  export EA_KERNEL_PORT=9000
  python3 -m ea_kernel.api.server
  ```

## 2. Metamodel Service (Legacy/Internal)
- **Port**: `8000`
- **Service**: `ea-metamodel`
- **Purpose**: Legacy system or internal metamodel management. Do NOT use for Governance Blueprint visualization.
- **Note**: Currently running but not actively integrated into the Governance loop.

## 3. Visualization Frontend (Viz Tool)
- **Port**: `5173` (Vite Dev Server)
- **Service**: `web-kernel-viz`
- **Purpose**: Interactive visualization of the Governance Kernel.
- **Integration**: Configured via `.env` to consume data from `http://localhost:9000`.

## 4. Main Application (Frontend)
- **Port**: `3000` (Next.js)
- **Service**: `apps/frontend`
- **Purpose**: The primary user-facing application for the system.

---

## Integration Strategy

1. **Unify on Port 9000**: All governance-related API calls (rules, diagrams, judgments) should target `http://localhost:9000`.
2. **Frontend Config**: `web-kernel-viz` uses `VITE_API_URL=http://localhost:9000` to fetch dynamic diagrams.
3. **Deprecate Port 8000**: Evaluate if `ea-metamodel` functionality can be fully migrated to `ea-kernel`. If so, shut down service on 8000.
