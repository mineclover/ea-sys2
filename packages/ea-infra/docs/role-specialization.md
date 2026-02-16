# Infra 레이어 역할 전문화 문서

> 정규 프로파일: `packages/ea-kernel/src/ea_kernel/profiles/ea_sys/00-infra.toml`
> 공통 구현 컨벤션: `docs/ea-sys-conventions.md`

---

## 1. 레이어 정체성

Infra는 **row 데이터 설계**를 담당하는 메타-인프라스트럭처 시스템이다.

### 핵심 정의

- **역할**: 저장소, 상태, 인덱싱, 입출력 데이터 관리 모델 설계
- **위치**: 5계층 런타임 체인(decision -> needs -> kernel -> flow)에 포함되지 않음. Governance와 함께 독립 시스템으로 동작
- **의존성**: Pure Python, zero dependency (`dependencies = []`)
- **설계 원칙**: 다른 레이어의 데이터가 **어떻게 저장되어야 하는지**를 정의. 데이터를 직접 저장하지 않고, 저장 계약(storage contract)을 설계

### 다른 레이어와의 관계

```
Infra (데이터 설계 계약)
  → Governance: 거버넌스 데이터 저장소 스키마/감사/보존/마이그레이션 설계
  → Decision:   의사결정 데이터 스키마/인덱싱/아카이브 정책 설계
  → Needs:      요구 데이터 스키마/컨텍스트 저장소/백로그 인덱싱 설계
  → Kernel:     커널 스펙 스키마/그래프 저장소/검증 로그/마이그레이션 설계
  → Flow:       실행 로그 스키마/체크포인트/이벤트 로그/보존 정책 설계
```

### 현재 상태

프로젝트 내 **가장 미성숙한 레이어**이다. 설계 의도는 `00-infra.toml`에 포괄적으로 정의되어 있으나, 구현은 최소 수준이다.

| 항목 | 상태 |
|------|------|
| 소스 파일 | `indexer.py`, `__init__.py` (2개) |
| 구현된 기능 | `ResourceIndexer` (파일 시스템 스캐너), `Resource` (메타데이터 dataclass) |
| 패키지 버전 | `0.1.0` |
| 테스트 | `test_indexer.py` (1개) |
| TOML 스펙 | `specs/` 디렉토리 없음 |
| 서비스 레이어 | 없음 |

---

## 2. 메타-메타 모델 설계

`00-infra.toml`에 정의된 Infra의 전체 모델 설계를 기술한다. 이 프로파일이 Infra 레이어의 권위 출처(source of truth)이다.

### 2.1 코어 요소 (Infra 자체)

| 요소 | 카테고리 | 역할 |
|------|---------|------|
| `InfraLayer` | Composite | 인프라 row 데이터 설계 경계 |
| `DataPlatformService` | ActiveStructure | row 데이터 계약 및 물리 데이터 접근 제어 주 서비스 |
| `StorageLifecycleService` | ActiveStructure | 스키마 수명주기, 마이그레이션, 보존 루틴 처리 |
| `ProfileStoragePort` | Interface | 거버넌스가 프로파일/모델 영속화에 사용하는 row 데이터 저장 포트 |
| `EventStoragePort` | Interface | 불변 이벤트/감사 쓰기용 row 데이터 추가 포트 |
| `InfraModelPort` | Interface | 6x6 계약 포트 (infra 레이어 자체 모델 인터페이스) |
| `LayerVersionStore` | PassiveStructure | 레이어 모델 페이로드의 row 지향 버전 테이블 |
| `ValidationRunStore` | PassiveStructure | 진단 페이로드를 가진 row 지향 검증 실행 테이블 |
| `EvidenceStore` | PassiveStructure | 실행 피드백을 위한 row 지향 증거/감사 테이블 |
| `StoragePolicy` | Governance | row 수명주기, 보존, 파티션 정책 제약 |

### 2.2 코어 관계 구조

```
InfraLayer ──contains──→ {DataPlatformService, StorageLifecycleService}
InfraLayer ──contains──→ {ProfileStoragePort, EventStoragePort, InfraModelPort}
InfraLayer ──contains──→ {LayerVersionStore, ValidationRunStore, EvidenceStore}

StoragePolicy ──constrains──→ {DataPlatformService, StorageLifecycleService}

DataPlatformService ──registers──→ {ProfileStoragePort, EventStoragePort}
DataPlatformService ──coordinates──→ StorageLifecycleService
DataPlatformService ──depends_on──→ {LayerVersionStore, ValidationRunStore, EvidenceStore}

StorageLifecycleService ──produces──→ {LayerVersionStore, ValidationRunStore, EvidenceStore}
```

### 2.3 6x6 교차 레이어 데이터 스키마

Infra 관점에서 다른 5개 레이어의 데이터 저장소를 설계한다.

#### Infra -> Governance

| 요소 | 카테고리 | 설계 의도 |
|------|---------|----------|
| `GovernanceStorageSchema` | PassiveStructure | 거버넌스 모델/버전/합의 레코드의 row 스키마 설계 |
| `GovernanceAuditStore` | PassiveStructure | 거버넌스 의사결정 및 승인의 감사 추적 저장소 |
| `GovernanceRetentionPolicy` | Governance | 거버넌스 데이터의 보존/보관 정책 |
| `GovernanceDataMigration` | Behavior | 거버넌스 데이터 진화를 위한 스키마 마이그레이션 단계 |

#### Infra -> Decision

| 요소 | 카테고리 | 설계 의도 |
|------|---------|----------|
| `DecisionDataSchema` | PassiveStructure | 의사결정 컨텍스트/옵션/평가/결과 레코드의 row 스키마 |
| `DecisionIndexStrategy` | PassiveStructure | 의사결정 추적 쿼리를 위한 인덱싱 전략 |
| `DecisionArchivePolicy` | Governance | 의사결정 이력 데이터의 보존 정책 |

#### Infra -> Needs

| 요소 | 카테고리 | 설계 의도 |
|------|---------|----------|
| `NeedsDataSchema` | PassiveStructure | 유스케이스/액터/제약/우선순위 요구 레코드의 row 스키마 |
| `NeedsContextStore` | PassiveStructure | 요구 추적을 위한 컨텍스트 스냅샷 저장소 |
| `NeedsBacklogIndex` | PassiveStructure | 백로그 우선순위 쿼리를 위한 인덱싱 |

#### Infra -> Kernel

| 요소 | 카테고리 | 설계 의도 |
|------|---------|----------|
| `KernelSpecSchema` | PassiveStructure | 커널 스펙/규칙/프로파일 저장의 row 스키마 |
| `KernelGraphStore` | PassiveStructure | 커널 토폴로지를 위한 그래프 데이터 저장소 |
| `KernelValidationLogStore` | PassiveStructure | 검증 실행 로그 저장소 |
| `KernelStorageMigration` | Behavior | 커널 데이터 진화를 위한 스키마 마이그레이션 |

#### Infra -> Flow

| 요소 | 카테고리 | 설계 의도 |
|------|---------|----------|
| `FlowExecutionLogSchema` | PassiveStructure | 플로우 실행/단계/결과 로그의 row 스키마 |
| `FlowCheckpointStore` | PassiveStructure | 플로우 재개를 위한 상태 체크포인트 저장소 |
| `FlowEventLogStore` | PassiveStructure | 플로우 트리거 및 전이의 이벤트 로그 저장소 |
| `FlowDataRetentionPolicy` | Governance | 플로우 실행 데이터의 보존 정책 |

### 2.4 구현 정렬 요소 (Implementation-Aligned)

프로파일에는 실제 코드베이스에서 발견된 인프라 개념도 포함되어 있다.

#### 리소스 인덱싱 (유일한 구현체)

| 요소 | 설명 |
|------|------|
| `ResourceIndexingService` | 파일 시스템 스캐너, `ResourceIndexer.scan()`으로 Resource 객체 생성 |
| `ResourceDescriptor` | 인덱싱된 리소스 메타데이터 레코드 (uri, path, name, content_type, last_modified) |

#### SQLite 저장소 백엔드

| 요소 | 설명 |
|------|------|
| `SQLiteStorageBackend` | 전 도메인 스토어 공유 SQLite 백엔드. 연결 관리, WAL 모드, 스키마 버전 관리, 마이그레이션 지원 |
| `SchemaVersionTable` | 대부분의 SQLite DB에 존재하는 스키마 버전 추적 테이블 (ea-kernel stores, transaction.py). ea-profile은 `schema_info` 테이블, layer_store.py는 버전 테이블 없음 |

#### 스토어 포트 (ABC 인터페이스 + 구체 클래스)

| 포트 (실제 클래스명) | 현재 구현 위치 | 타입 | 책임 |
|------|-------------|------|------|
| `I18nStore` | ea-kernel `i18n_store.py` | ABC | 번역 CRUD + 이력 + TOML 일괄 가져오기 + 삭제 + 스키마 감사 |
| `RuleAssetStore` | ea-kernel `rule_asset_store.py` | ABC | 규칙 수명주기 (DRAFT -> REVIEW -> APPROVED -> DEPRECATED) + 버전 관리 + 복원 |
| `DecisionStore` | ea-kernel `decision_store.py` | ABC | 판정 기록 저장 + 증거 요약 + triple별 통계 |
| `CorpusVersionStore` | ea-kernel `corpus_version_store.py` | ABC | 규칙 코퍼스 버전 스냅샷 + 이력 + diff |
| `StoragePort` | ea-profile `store.py` | ABC | 프로파일 버전 영속화 + 태깅 + 감사 훅 |
| `TransactionManager` | ea-governance `transaction.py` | 구체 클래스 | SQLite 기반 ACID 트랜잭션 + 이벤트 소싱 (ABC 아님) |
| `GovernanceLayerStore` | ea-governance `layer_store.py` | ABC | 교차 레이어 모델 영속화 (레이어별 인스턴스) |

> **설계 방향**: 6개 ABC + 1개 구체 클래스가 현재 각 패키지에 분산되어 있다. Infra 레이어가 성숙하면 여기에서 정규 ABC를 정의하고, 각 패키지가 구현체만 제공하는 구조로 전환한다.

#### 파일 기반 영속화

| 요소 | 설명 |
|------|------|
| `FileBasedPersistenceService` | JSON 파일 기반 영속화 서비스. ea-needs `NeedRepository` 구현 |
| `JSONFileStore` | `data_dir/catalogs/{id}.json` 구조의 JSON 파일 저장소 |

#### 데이터 디렉토리 레이아웃

| 요소 | 설명 |
|------|------|
| `DataDirectoryLayout` | 물리 저장소 구조 컨벤션. 모든 스토어의 파일 경로 결정을 제약 |

### 2.5 규칙 TOML (설계 예정)

`infra_rules.toml`은 아직 설계되지 않았다. 포함될 규칙 범주:

- **저장소 계약 검증**: 스토어 포트 ABC가 올바르게 구현되었는지 검증
- **스키마 마이그레이션 규칙**: 전방 호환 마이그레이션 단계의 유효성 검증
- **보존 정책 강제**: 레이어별 데이터 보존 정책 준수 확인
- **디렉토리 레이아웃 준수**: 데이터 파일이 `DataDirectoryLayout` 컨벤션을 따르는지 검증

---

## 3. 파이프라인 구현 명세

`docs/ea-sys-conventions.md` 2.1절의 5단계 Design-First Pipeline에 따른 현재 구현 상태.

### Stage 1: 선언 (TOML)

**상태**: 미구현

`specs/` 디렉토리가 존재하지 않는다. 구현 시 다음 파일이 필요하다:

```
src/ea_infra/specs/
├── infra_schema.toml           # 정규 스키마 (엔티티/관계/속성)
├── infra_schema.ko.toml        # i18n 패치
└── infra_rules.toml            # 유효성 규칙
```

`infra_schema.toml`은 `00-infra.toml` 프로파일의 코어 요소를 정규 스키마로 변환한 것이다. `[meta]` 섹션으로 자기 검증을 포함해야 한다.

### Stage 2: 파싱 (Builder)

**상태**: 미구현

`InfraSchema`를 `frozen=True` dataclass로 정의하고, `schema_loader.py`에서 TOML 파싱 + 자기 검증을 수행해야 한다. `SchemaPort` 호환이 필요하다.

```python
@dataclass(frozen=True)
class InfraSchema:
    store_ports: tuple[StorePortDef, ...]
    data_stores: tuple[DataStoreDef, ...]
    storage_policies: tuple[StoragePolicyDef, ...]
    # __post_init__에서 O(1) 인덱스 구축
```

### Stage 3: 패턴 컴파일

**상태**: 미구현

`condition_registry`가 없다. 커널의 `@Category` / `#Layer` 패턴 확장과 유사하게, Infra 고유 조건 타입을 정의해야 한다.

예상 조건:
- `STORE_PORT_IMPLEMENTED`: 스토어 포트 ABC에 대한 구현체 존재 여부
- `SCHEMA_VERSION_COMPATIBLE`: 스키마 버전 전방 호환성

### Stage 4: 자산 거버넌스 (수명주기)

**상태**: 미구현

스토어 계약의 수명주기 관리가 필요하다. `ea-sys-conventions.md` 6절의 `StrEnum + VALID_TRANSITIONS` 패턴을 따른다.

```python
class StoreContractState(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
```

### Stage 5: 카탈로그 합성

**상태**: 미구현

Aggregate root가 없다. `DataPlatformService`가 이 역할을 수행할 예정이며, 모든 스토어 포트를 등록하고 교차 레이어 데이터 접근을 조율한다.

### Profile Loading

**상태**: 미구현

`00-infra.toml` 프로파일을 런타임에 로딩하는 메커니즘이 없다.

### Service Layer

**상태**: 미구현

`infra_service.py`가 없다. `ea-sys-conventions.md` 3절의 순수 함수 + `dict[str, Any]` 반환 패턴을 따라야 한다.

---

## 4. 고유 전문성

Infra 레이어만의 독자적 전문 영역을 정의한다.

### 4.1 Row 데이터 스키마 설계

Infra의 핵심 역할은 모든 레이어의 저장소 계약(ABC)을 설계하는 것이다.

**3-tier 스토어 패턴** (`ea-sys-conventions.md` 5절):

```
ABC (인터페이스 정의)
  ↓ 상속
InMemory 구현 (테스트용)
  ↓ 상속
SQLite 구현 (프로덕션)
```

각 스토어 ABC는 다음을 정의한다:
- CRUD 오퍼레이션 (`@abstractmethod`)
- 쿼리 인터페이스 (필터링, 페이징, 정렬)
- 이력 추적 (`tuple` 기반 불변 감사 추적)
- 직렬화 계약 (JSON 직렬화 가능 페이로드)

### 4.2 스토어 포트 상세

#### 1. I18nStore (ABC)

```python
class I18nStore(ABC):
    @abstractmethod
    def upsert(self, entry: TranslationEntry) -> TranslationEntry: ...
    @abstractmethod
    def get(self, kind: str, name: str, lang: str, field: str) -> TranslationEntry | None: ...
    @abstractmethod
    def list_translations(self, lang: str, kind: str | None = None) -> tuple[TranslationEntry, ...]: ...
    @abstractmethod
    def history(self, kind: str, name: str, lang: str, field: str) -> tuple[TranslationEntry, ...]: ...
    @abstractmethod
    def delete(self, kind: str, name: str, lang: str, field: str) -> bool: ...
    @abstractmethod
    def import_from_toml(self, toml_path: Path, lang: str, created_by: str = "toml_import") -> int: ...
    @abstractmethod
    def audit(self, schema: KernelSchema, lang: str) -> I18nAuditReport: ...
```

**SQLite 스키마**: `data/i18n.db` — `translations` (PK: kind+name+lang+field), `translation_history` (버전 감사 추적)

#### 2. RuleAssetStore (ABC)

```python
class RuleAssetStore(ABC):
    @abstractmethod
    def create(self, asset: RuleAsset) -> RuleAsset: ...
    @abstractmethod
    def get(self, rule_id: str) -> RuleAsset | None: ...
    @abstractmethod
    def get_version(self, rule_id: str, version: int) -> RuleAsset | None: ...
    @abstractmethod
    def query(self, options: RuleAssetQueryOptions | None = None) -> tuple[RuleAsset, ...]: ...
    @abstractmethod
    def transition(self, rule_id: str, to_state: RuleLifecycleState, actor: str, reason: str = "") -> RuleAsset: ...
    @abstractmethod
    def update_entry(self, rule_id: str, entry: RuleCorpusEntry, actor: str) -> RuleAsset: ...
    @abstractmethod
    def history(self, rule_id: str) -> tuple[RuleAsset, ...]: ...
    @abstractmethod
    def count(self, options: RuleAssetQueryOptions | None = None) -> int: ...
    @abstractmethod
    def list_by_state(self, state: RuleLifecycleState) -> tuple[RuleAsset, ...]: ...
    @abstractmethod
    def active_rules(self) -> tuple[RuleAsset, ...]: ...
    @abstractmethod
    def restore(self, asset: RuleAsset) -> RuleAsset: ...
```

**수명주기**: DRAFT -> REVIEW -> APPROVED -> DEPRECATED
**SQLite 스키마**: `rule_assets` (PK: rule_id), `rule_asset_history` (version trail, unique: rule_id+version). 인덱스: state, domain, author, source_type

#### 3. DecisionStore (ABC)

```python
class DecisionStore(ABC):
    @abstractmethod
    def store(self, record: DecisionRecord, corpus_version_id: str = "",
              evidence_summary: tuple[EvidenceSummaryItem, ...] | None = None) -> StoredDecisionRecord: ...
    @abstractmethod
    def get(self, storage_id: str) -> StoredDecisionRecord | None: ...
    @abstractmethod
    def query(self, options: DecisionQueryOptions | None = None) -> tuple[StoredDecisionRecord, ...]: ...
    @abstractmethod
    def count(self, options: DecisionQueryOptions | None = None) -> int: ...
    @abstractmethod
    def statistics_for(self, source: str, target: str, relation: str) -> JudgmentStatistics: ...
    @abstractmethod
    def all_statistics(self) -> tuple[JudgmentStatistics, ...]: ...
```

**SQLite 스키마**: `decision_records` (PK: storage_id) — source/target/relation/actor/judgment_json 컬럼, `judgment_statistics` (구체화 뷰, PK: source+target+relation). 인덱스: triple, actor, decision_type, timestamp, corpus_version_id

#### 4. CorpusVersionStore (ABC)

```python
class CorpusVersionStore(ABC):
    @abstractmethod
    def create_version(self, corpus_name: str, entries: tuple[RuleCorpusEntry, ...],
                       description: str = "", parent_version_id: str = "") -> CorpusVersionInfo: ...
    @abstractmethod
    def get(self, version_id: str) -> CorpusVersionInfo | None: ...
    @abstractmethod
    def get_entries(self, version_id: str) -> tuple[RuleCorpusEntry, ...]: ...
    @abstractmethod
    def get_latest(self, corpus_name: str) -> CorpusVersionInfo | None: ...
    @abstractmethod
    def query(self, options: VersionQueryOptions | None = None) -> tuple[CorpusVersionInfo, ...]: ...
    @abstractmethod
    def history(self, corpus_name: str, limit: int = 100) -> tuple[CorpusVersionInfo, ...]: ...
    @abstractmethod
    def diff(self, from_version_id: str, to_version_id: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]: ...
```

**SQLite 스키마**: `corpus_versions` (PK: version_id) — corpus_name, rule_count, rule_ids_json, `version_entries` (PK: version_id+rule_id, FK: version_id) — 직렬화된 rule_json + metadata_json

#### 5. StoragePort (ABC, ea-profile)

```python
class StoragePort(ABC):
    @abstractmethod
    def initialize(self) -> None: ...
    @abstractmethod
    def close(self) -> None: ...
    @abstractmethod
    def store(self, profile: KernelProfile, *, author: str = "", description: str = "",
              parent_id: str | None = None, origin: ProfileOrigin | None = None) -> ProfileVersion: ...
    @abstractmethod
    def get(self, version_id: str) -> ProfileVersion | None: ...
    @abstractmethod
    def get_latest(self, profile_name: str) -> ProfileVersion | None: ...
    @abstractmethod
    def list_versions(self, profile_name: str, *, ascending: bool = True) -> list[ProfileVersion]: ...
    @abstractmethod
    def list_profiles(self) -> list[str]: ...
    @abstractmethod
    def tag(self, version_id: str, tag_name: str) -> ProfileTag: ...
    @abstractmethod
    def get_by_version(self, profile_name: str, version: str) -> ProfileVersion | None: ...
    @abstractmethod
    def get_by_tag(self, profile_name: str, tag_name: str) -> ProfileVersion | None: ...
    @abstractmethod
    def list_tags(self, version_id: str | None = None, profile_name: str | None = None) -> list[ProfileTag]: ...
    @abstractmethod
    def delete(self, version_id: str) -> bool: ...
```

**SQLite 스키마**: `data/profiles.db` — `schema_info` (PK: key), `profile_versions` (PK: id, unique: profile_name+version) — content_hash, profile_data, element/relation/rule counts, `profile_tags` (PK: profile_name+name, FK: version_id)

#### 6. TransactionManager (구체 클래스, ea-governance)

ABC가 아닌 구체 클래스. SQLite 전용 구현으로, 인메모리 구현이 별도로 존재하지 않는다.

```python
class TransactionManager:
    def __init__(self, db_path: str | Path) -> None: ...
    def begin_transaction(self, name: str, tx_type: str = "generic",
                          payload: dict[str, Any] | None = None) -> TransactionUnit: ...
    def commit(self, tx_id: str) -> bool: ...
    def rollback(self, tx_id: str, reason: str = "Request") -> bool: ...
    def fail(self, tx_id: str, error_msg: str) -> bool: ...
    def get_transaction(self, tx_id: str) -> TransactionUnit | None: ...
    def get_events(self, tx_id: str) -> list[TransactionEvent]: ...
    def add_event(self, tx_id: str, event_type: str, message: str,
                  payload: dict[str, Any] | None = None) -> bool: ...
    def list_transactions(self, *, tx_type: str | None = None,
                          status: TransactionStatus | None = None,
                          limit: int | None = None) -> list[TransactionUnit]: ...
```

**SQLite 스키마**: `transactions.db` — `transactions` (PK: id) — name/tx_type/status/payload_json/logs_json, `transaction_events` (FK: tx_id, ON DELETE CASCADE) — 이벤트 소싱. 인덱스: status, updated_at, tx_id+created_at

#### 7. GovernanceLayerStore (ABC, ea-governance)

레이어별 인스턴스로 생성된다. `layer` 속성이 인스턴스 필드이므로, 메서드에 layer 파라미터가 없다.

```python
class GovernanceLayerStore(ABC):
    layer: str
    @abstractmethod
    def save_payload(self, model_id: str, payload: dict[str, Any]) -> str: ...
    @abstractmethod
    def get_payload(self, model_id: str) -> dict[str, Any] | None: ...
    @abstractmethod
    def list_snapshots(self) -> list[LayerSnapshot]: ...
```

**SQLite 스키마**: `layers/{layer}.db` (6개 독립 DB) — `layer_models` (PK: layer+model_id) — payload_json, updated_at. 인덱스: layer+updated_at

### 4.3 인덱싱 전략

레이어별 데이터 인덱싱은 Infra가 설계한다:

| 레이어 | 인덱스 대상 | 인덱스 타입 |
|--------|-----------|-----------|
| Governance | 감사 이벤트 (시간순) | B-tree (timestamp) |
| Decision | triple, actor, corpus_version | 복합 인덱스 |
| Needs | 백로그 우선순위 | B-tree (priority) |
| Kernel | 스펙/규칙 ID, 도메인 | 해시 + B-tree |
| Flow | 실행 로그 (시간순), 체크포인트 ID | B-tree (timestamp) |

### 4.4 마이그레이션 규칙

대부분의 SQLite DB는 `schema_version` 테이블로 스키마 버전을 추적한다. 현재 구현은 최소 스키마를 사용한다:

```sql
-- ea-kernel stores, ea-governance transaction.py
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- ea-profile store.py (다른 형태)
CREATE TABLE IF NOT EXISTS schema_info (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

> **참고**: `00-infra.toml` 프로파일에 정의된 `SchemaVersionTable` 설계 요소는 `applied_at`, `description` 컬럼을 포함하는 확장 스키마를 의도하나, 현재 구현은 `version` 컬럼만 사용한다. `ea-governance/layer_store.py`는 `schema_version` 테이블 자체가 없다.

마이그레이션 원칙:
- **전방 호환**: 새 컬럼 추가는 `DEFAULT` 값 필수
- **역방향 비호환**: 컬럼 삭제/타입 변경은 새 테이블 + 데이터 복사
- **버전 순서**: 정수 시퀀스, 건너뛰기 금지
- **원자성**: 각 마이그레이션은 단일 트랜잭션으로 실행

### 4.5 데이터 디렉토리 레이아웃 컨벤션

```
{data_dir}/
├── layers/
│   ├── infra.db              # Infra 레이어 모델
│   ├── governance.db         # Governance 레이어 모델
│   ├── decision.db           # Decision 레이어 모델
│   ├── needs.db              # Needs 레이어 모델
│   ├── kernel.db             # Kernel 레이어 모델
│   └── flow.db               # Flow 레이어 모델
├── kernel/
│   └── profiles.db           # 프로파일 버전 저장소
├── transactions.db           # ACID 이벤트 로그
└── catalogs/
    └── {id}.json             # JSON 기반 카탈로그
```

### 4.6 현재 구현체 분석

현재 유일한 구현체인 `ResourceIndexer`와 `Resource`의 상태:

```python
# indexer.py — 현재 구현
@dataclass                    # ❌ frozen=True 누락 (ea-sys-conventions.md 1.1 위반)
class Resource:
    uri: str
    path: str
    name: str
    content_type: str
    last_modified: str
    content: str | None = None
```

수정 필요 사항:
- `Resource`에 `frozen=True` 적용
- `list[str]` 파라미터를 `tuple[str, ...]`로 변경 (컨벤션 1.2)
- `os.walk` 대신 `Path.rglob` 사용 고려

---

## 5. 포트 계약 상세

`00-infra.toml`에 정의된 6x6 교차 레이어 포트 계약의 규칙 구조를 상세히 기술한다.

### 5.1 InfraModelPort (자체 포트)

InfraModelPort는 Infra 레이어 자체의 6x6 계약 포트이다.

관련 규칙:
- `ResourceIndexingService ──registers──→ InfraModelPort` (priority 70): 리소스 인덱싱 서비스가 스캐너 인터페이스를 infra 모델 포트를 통해 등록

### 5.2 Infra -> Governance 포트 계약

`GovernanceModelPort`가 4개 요소를 노출한다:

```
GovernanceModelPort ──contains──→ GovernanceStorageSchema     (p65)
GovernanceModelPort ──contains──→ GovernanceAuditStore        (p65)
GovernanceModelPort ──contains──→ GovernanceRetentionPolicy   (p65)
GovernanceModelPort ──contains──→ GovernanceDataMigration     (p65)

DataPlatformService ──depends_on──→ GovernanceStorageSchema   (p72)
StorageLifecycleService ──coordinates──→ GovernanceDataMigration (p72)
GovernanceRetentionPolicy ──constrains──→ StorageLifecycleService (p72)
StorageLifecycleService ──produces──→ GovernanceAuditStore    (p72)
```

### 5.3 Infra -> Decision 포트 계약

`DecisionModelPort`가 3개 요소를 노출한다:

```
DecisionModelPort ──contains──→ DecisionDataSchema       (p65)
DecisionModelPort ──contains──→ DecisionIndexStrategy    (p65)
DecisionModelPort ──contains──→ DecisionArchivePolicy    (p65)

DataPlatformService ──depends_on──→ DecisionDataSchema       (p72)
DataPlatformService ──depends_on──→ DecisionIndexStrategy    (p72)
DecisionArchivePolicy ──constrains──→ StorageLifecycleService (p72)
```

### 5.4 Infra -> Needs 포트 계약

`NeedsModelPort`가 3개 요소를 노출한다:

```
NeedsModelPort ──contains──→ NeedsDataSchema       (p65)
NeedsModelPort ──contains──→ NeedsContextStore     (p65)
NeedsModelPort ──contains──→ NeedsBacklogIndex     (p65)

DataPlatformService ──depends_on──→ NeedsDataSchema       (p72)
DataPlatformService ──depends_on──→ NeedsBacklogIndex     (p72)
StorageLifecycleService ──produces──→ NeedsContextStore   (p72)
```

### 5.5 Infra -> Kernel 포트 계약

`KernelModelPort`가 4개 요소를 노출한다:

```
KernelModelPort ──contains──→ KernelSpecSchema            (p65)
KernelModelPort ──contains──→ KernelGraphStore            (p65)
KernelModelPort ──contains──→ KernelValidationLogStore    (p65)
KernelModelPort ──contains──→ KernelStorageMigration      (p65)

DataPlatformService ──depends_on──→ KernelSpecSchema         (p72)
DataPlatformService ──depends_on──→ KernelGraphStore         (p72)
StorageLifecycleService ──coordinates──→ KernelStorageMigration (p72)
StorageLifecycleService ──produces──→ KernelValidationLogStore (p72)
```

### 5.6 Infra -> Flow 포트 계약

`FlowModelPort`가 4개 요소를 노출한다:

```
FlowModelPort ──contains──→ FlowExecutionLogSchema    (p65)
FlowModelPort ──contains──→ FlowCheckpointStore       (p65)
FlowModelPort ──contains──→ FlowEventLogStore         (p65)
FlowModelPort ──contains──→ FlowDataRetentionPolicy   (p65)

DataPlatformService ──depends_on──→ FlowExecutionLogSchema   (p72)
DataPlatformService ──depends_on──→ FlowCheckpointStore      (p72)
StorageLifecycleService ──produces──→ FlowEventLogStore      (p72)
FlowDataRetentionPolicy ──constrains──→ StorageLifecycleService (p72)
StoragePolicy ──constrains──→ FlowCheckpointStore            (p72)
```

### 5.7 교차 레이어 스토어 포트 바인딩

스토어 포트와 교차 레이어 스키마 간 의존 관계 (TOML 프로파일의 요소명 사용):

```
I18nStorePort ──depends_on──→ KernelSpecSchema           (p72)
RuleAssetStorePort ──depends_on──→ KernelSpecSchema      (p72)
DecisionStorePort ──depends_on──→ DecisionDataSchema     (p72)
GovernanceLayerStorePort ──depends_on──→ GovernanceStorageSchema (p72)
ProfileVersionStorePort ──depends_on──→ KernelSpecSchema (p72)
TransactionStorePort ──produces──→ GovernanceAuditStore  (p72)
```

> **참고**: 위 요소명은 `00-infra.toml` 프로파일에 정의된 모델 요소 이름이다. 실제 코드의 클래스명은 section 4.2 참조.

---

## 6. 구현 로드맵

우선순위와 의존 관계에 따라 정렬한다.

### Phase 1: 기반 구축 [CRITICAL]

#### 1-1. 스토어 포트 ABC 정의

**우선순위**: CRITICAL
**의존**: 없음 (선행 작업)

현재 각 패키지에 분산된 6개 ABC + 1개 구체 클래스를 `ea_infra`에서 정규 인터페이스로 정의한다. 기존 패키지의 ABC는 호환 shim으로 전환한다. `TransactionManager`는 ABC 추출이 필요하다.

```
src/ea_infra/
├── store_ports.py           # 스토어 ABC 정의
└── store_types.py           # 스토어 공통 타입 (StoreError, QueryFilter 등)
```

구현 원칙:
- 모든 ABC 메서드는 `@abstractmethod`
- 반환 타입은 `tuple` (불변 컬렉션)
- 에러는 커스텀 예외 (`StoreError` 계층)

#### 1-2. SQLiteStorageBackend 구현

**우선순위**: CRITICAL
**의존**: 1-1 (스토어 포트 ABC)

공유 SQLite 백엔드를 구현한다. 모든 SQLite 스토어의 기반.

```python
class SQLiteStorageBackend:
    __slots__ = ("_db_path",)

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._init_schema()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self.connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
                    description TEXT
                );
            """)

    def migrate(self, target_version: int, migrations: dict[int, str]) -> None:
        """Forward-compatible schema migration."""
        ...
```

### Phase 2: 스키마 정규화 [HIGH]

#### 2-1. InfraSchema 정의

**우선순위**: HIGH
**의존**: Phase 1

```python
@dataclass(frozen=True)
class StorePortDef:
    name: str
    methods: tuple[str, ...]
    target_store: str
    description: str = ""

@dataclass(frozen=True)
class InfraSchema:
    store_ports: tuple[StorePortDef, ...]
    data_stores: tuple[DataStoreDef, ...]
    storage_policies: tuple[StoragePolicyDef, ...]
    directory_layout: DataDirectoryLayout
    _port_by_name: dict[str, StorePortDef] = field(
        default_factory=dict, init=False, repr=False, compare=False,
    )

    def __post_init__(self) -> None:
        idx: dict[str, StorePortDef] = {}
        for p in self.store_ports:
            idx[p.name] = p
        object.__setattr__(self, '_port_by_name', idx)
```

#### 2-2. TOML 외부화

**우선순위**: HIGH
**의존**: 2-1

```
src/ea_infra/specs/
├── infra_schema.toml
├── infra_schema.ko.toml
└── infra_rules.toml
```

#### 2-3. InMemory 구현 (전체 ABC)

**우선순위**: HIGH
**의존**: 1-1

모든 ABC에 대한 InMemory 구현체를 제공한다. 다른 패키지의 테스트 픽스처로 사용.

```python
class InMemoryI18nStore(I18nStore):
    __slots__ = ("_data",)

    def __init__(self) -> None:
        self._data: dict[tuple[str, str, str, str], TranslationEntry] = {}

    def upsert(self, entry: TranslationEntry) -> TranslationEntry:
        key = (entry.target_kind, entry.target_name, entry.lang, entry.field)
        self._data[key] = entry
        return entry
    ...
```

### Phase 3: 정책 및 레이아웃 [MEDIUM]

#### 3-1. StoragePolicy 강제

**우선순위**: MEDIUM
**의존**: Phase 2

런타임 정책 검사 구현:
- 보존 기간 검증
- 파티션 정책 준수
- WAL 모드 / PRAGMA 설정 강제

#### 3-2. 데이터 디렉토리 레이아웃 표준화

**우선순위**: MEDIUM
**의존**: 1-2

`DataDirectoryLayout`를 코드로 구현하여 경로 해석을 표준화한다.

```python
@dataclass(frozen=True)
class DataDirectoryLayout:
    data_dir: Path

    def layer_db(self, layer: str) -> Path:
        return self.data_dir / "layers" / f"{layer}.db"

    def profiles_db(self) -> Path:
        return self.data_dir / "kernel" / "profiles.db"

    def transactions_db(self) -> Path:
        return self.data_dir / "transactions.db"

    def catalog_file(self, catalog_id: str) -> Path:
        return self.data_dir / "catalogs" / f"{catalog_id}.json"
```

### Phase 4: 기존 코드 수정 [LOW]

#### 4-1. Resource dataclass 수정

**우선순위**: LOW
**의존**: 없음

```python
@dataclass(frozen=True)        # frozen=True 추가
class Resource:
    uri: str
    path: str
    name: str
    content_type: str
    last_modified: str
    content: str | None = None
```

#### 4-2. ResourceIndexer 파라미터 타입 수정

```python
def scan(
    self,
    sub_paths: tuple[str, ...] | None = None,    # list → tuple
    extensions: tuple[str, ...] | None = None,    # list → tuple
) -> Generator[Resource, None, None]:
```

---

## 부록: 의존 그래프 요약

```
[Phase 1: CRITICAL]
1-1 Store Port ABCs + TransactionManager ABC 추출 ←── 1-2 SQLiteStorageBackend

[Phase 2: HIGH]
1-1 ←── 2-1 InfraSchema ←── 2-2 TOML 외부화
1-1 ←── 2-3 InMemory 구현

[Phase 3: MEDIUM]
Phase 2 ←── 3-1 StoragePolicy 강제
1-2 ←── 3-2 DataDirectoryLayout 표준화

[Phase 4: LOW]
4-1 Resource frozen=True (독립)
4-2 ResourceIndexer tuple 파라미터 (독립)
```
