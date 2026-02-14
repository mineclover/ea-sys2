# Governance Model I/O Design (Export/Import)

## 1. Introduction
This document outlines the design for exporting and importing governance models (specifically Rule Assets and Rule Corpus) in `ea-kernel`. This capability is essential for:
- Backups and Disaster Recovery.
- Environment Migration (Dev -> Stage -> Prod).
- Multi-tenant data movement (Tenant A -> Tenant B).
- Sharing predefined profiles.

## 2. Scope

### In-Scope
- **Active Rules**: Exporting all rules currently in `APPROVED` or other active states.
- **Rule Lifecycle**: Preserving the lifecycle state and history of rules.
- **Provenance**: Maintaining the authorship and approval chain.
- **Corpus Version**: Exporting a specific snapshot of the Rule Corpus.

### Out-of-Scope (for now)
- **Decision History**: `DecisionRecord`s are typically voluminous and environment-specific. Exporting them is a separate concern (Data Warehousing).
- **Tenant Configuration**: API keys, user permissions, etc.

## 3. Data Format

We will use a **JSON-based archive format** (likely a simple JSON file or a ZIP if attachments are needed later).

### 3.1 Structure (governance_export_v1.json)

```json
{
  "meta": {
    "exported_at": "2024-03-20T10:00:00Z",
    "exported_by": "system",
    "kernel_version": "0.5.0",
    "schema_version": "1.0",
    "description": "Weekly Backup"
  },
  "rules": [
    {
      "id": "rule-core-allow-01",
      "asset_version": 1,
      "lifecycle": {
        "current_state": "approved",
        "history": [...]
      },
      "provenance": {
        "author": "kim@company.com",
        "approved_at": "...",
        ...
      },
      "entry": {
        "rule": { ... },     // KernelValidityRule definition
        "metadata": { ... }  // RuleMetadata
      }
    },
    ...
  ]
}
```

## 4. API Design

### 4.1 Interface

The `GovernanceSystem` (or a dedicated `ModelIOManager`) will expose:

```python
class ModelIOManager:
    """Manages Import/Export of Governance Models."""
    
    def export_model(self, 
                     target_state: RuleLifecycleState = None, 
                     domain: str = None) -> dict:
        """
        Exports rules matching criteria to a dictionary structure.
        Args:
            target_state: If provided, only export rules in this state.
            domain: If provided, only export rules in this domain.
        Returns:
            dict representing the JSON structure.
        """
        pass

    def import_model(self, 
                     data: dict, 
                     strategy: ImportStrategy = ImportStrategy.SKIP_EXISTING) -> ImportReport:
        """
        Imports rules from the data structure.
        Args:
            data: The exported JSON structure.
            strategy: How to handle ID conflicts.
        """
        pass
```

### 4.2 Import Strategies

When importing a rule that already exists (same ID) in the target system:

1.  **SKIP_EXISTING**: Do nothing. Keep local version.
2.  **OVERWRITE**: Replace local version with imported version (dangerous if active).
3.  **CREATE_NEW_VERSION**: If content differs, create a new asset version or a new draft (safest).
4.  **FAIL**: Abort operation if any conflict exists.

For Phase 1, we will implement **SKIP_EXISTING** and **OVERWRITE** as options.

## 5. Usage Example

```python
# Export
io_manager = ModelIOManager(system)
data = io_manager.export_model(target_state=RuleLifecycleState.APPROVED)
with open("backup.json", "w") as f:
    json.dump(data, f)

# Import
with open("backup.json", "r") as f:
    data = json.load(f)
    
report = io_manager.import_model(data, strategy=ImportStrategy.SKIP_EXISTING)
print(f"Imported {report.imported_count} rules.")
```
