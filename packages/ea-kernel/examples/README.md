# ea-kernel Examples

## FruitRetail Profile

A complete example of modeling a typical fruit retail business using ea-kernel.

### Files

- **fruit_retail_profile.toml** — Profile definition with 12 elements, 17 relations, and validity rules
- **fruit_retail_example.py** — Load, validate, and explore the profile

### Concepts Demonstrated

#### 1. Domain Elements (L1-L4)

```
Structural Elements (L1)
├── Actors: Store, Supplier, Customer
├── Objects: Product, Inventory
└── Activities: ReceiveProduct, CheckQuality, DisplayProduct, SaleTransaction, ...

Process Flow (L3-L4)
├── Supplier → Store (supply_flow)
├── Store → Inventory (inventory_flow)
├── Inventory → Display (display_flow)
└── Store → Customer (sales_flow)

Activity Sequence
├── ReceiveProduct → CheckQuality → DisplayProduct
├── DisplayProduct → SaleTransaction → ProcessPayment
└── RestockCheck → ReceiveProduct (loop)
```

#### 2. Relationship Types

| Type | Example | Meaning |
|------|---------|---------|
| **association** (L2) | supplies, sells_to | Structural connection |
| **feature_typing** (L2) | contains | Type relationship (Inventory contains Products) |
| **flow** (L3) | supply_flow, sales_flow | Product flow between actors |
| **transition** (L3) | quality_transition | State changes (e.g., Product freshness) |
| **succession** (L4) | receive_then_check | Process sequencing |
| **guarding** (L3) | check_then_discard | Conditional flow (if quality fails) |

#### 3. Validity Rules

Each relation type has **allowance rules** that define:
- Which source/target element pairs are allowed
- Priority for conflict resolution
- Conditions for applicability

Example:
```toml
[[validity_rules]]
id = "fruit-succ-01"
source_pattern = "ReceiveProduct"
target_pattern = "CheckQuality"
relationship_type = "succession"
valid = true
priority = 50
notes = "Receive then Check"
```

### Running the Example

```bash
cd packages/ea-kernel
PYTHONPATH=src python examples/fruit_retail_example.py
```

### Output

The script performs 6 main steps:

1. **Load Profile** — Parse TOML and create KernelProfile
2. **Audit Profile** — Validate against kernel metamodel (coverage: 36%)
3. **Load Kernel Rules** — Load 81 universal validity rules
4. **Validate Relations** — Confirm all defined relations exist
5. **Explore Structure** — Display elements, relations, and process flows
6. **Rule Statistics** — Summarize rule counts by type

### Key Insights

- **12 Elements**: 5 structural (actors/objects) + 7 activities (process steps)
- **17 Relations**: 4 associations + 1 feature + 4 flows + 2 transitions + 5 successions + 1 guarding
- **0 Allow Rules**: Profile rules were not fully loaded (TOML parser limitation)
- **Coverage 36%**: Profile maps to 36% of kernel capabilities

### What This Models

A complete fruit retail workflow:

```
Supplier delivers fruit (supply_flow)
    ↓
Store receives & checks quality (ReceiveProduct → CheckQuality)
    ↓
Products either:
  • Pass: displayed on shelves (DisplayProduct)
  • Fail: discarded (guarded by CheckQuality)
    ↓
Customer purchases (SaleTransaction → ProcessPayment)
    ↓
Store monitors inventory (RestockCheck loops back)
```

### Extending This Profile

To add more elements:

1. Add `[[elements]]` sections in TOML (with kernel_type and layer)
2. Add `[[relations]]` sections to connect them
3. Add `[[validity_rules]]` to allow/deny specific combinations
4. Run `audit_profile()` to validate against kernel

Examples:
- Add "DeliverySchedule" as an event element
- Add "InventoryOptimization" as a decision element
- Add "PricingStrategy" as a constraint element
- Link them with new relation types

### Architecture Notes

- **kernel_type**: Maps to 11 core kernel types (structure, item, step, action, etc.)
- **kernel_relation**: Maps to 14 core relation types (specialization, association, flow, etc.)
- **domain_layers**: Custom layers for your domain ("operational", "tactical", "strategic")
- **Profile Loader**: Converts TOML → KernelProfile in memory
- **ProfileAuditor**: Validates profile structure against kernel schema

### Next Steps

1. Use `kernel_judge()` to validate specific relationships
2. Query rules by group (e.g., "all association rules")
3. Export profile for use in other EA tools
4. Compose multiple profiles (e.g., FruitRetail + Supplier Management)
5. Generate visualizations (entity-relation diagrams, process flow diagrams)
