# Governance Modeling Features

ea-kernel의 거버넌스 시스템은 **4-Layer Progressive Abstraction**을 기반으로 하며, 이를 **Profile**과 **Rule**을 통해 확장하고 제어합니다. 본 문서는 시스템의 핵심 모델링 기능과 API 활용법을 설명합니다.

---

## 1. Modeling Philosophy (4-Layer)

커널은 시스템을 4가지 추상화 레벨로 모델링합니다:

1.  **L1 Structure**: "무엇이 존재하는가" (Structure, Item, Feature)
2.  **L2 Relationship**: "어떻게 연결되는가" (Ownership, Association, Membership)
3.  **L3 Behavioral**: "이 연결은 행위를 가진다" (Flow, Succession, Triggering)
4.  **L4 Concrete**: "구체적으로 어떤 행위인가" (Action, Event, Step)

모든 모델링 요소는 이 4개 층위 중 하나에 속하며, `KernelValidityRule`을 통해 이들 간의 관계가 제어됩니다.

---

## 2. Profile & Domain Modeling

**Profile**은 특정 도메인(예: Marketing, CRM)의 컨텍스트를 정의하는 규칙의 집합입니다.

### 데모 데이터 구조 (`seeds/demo_data.json`)
시스템은 데모용으로 3가지 도메인을 로드합니다:

-   **Marketing**: `Structure`(Department)가 `Package`(Campaign)를 소유하고 `Action`을 수행.
-   **CRM**: `Item`(Customer Data)이 `Action`(Support Process)으로 흐름(`Flow`).
-   **Sales**: `State`(Opportunity Stage) 간의 `Transition` 제어.

### API 활용
```http
GET /rules?state=approved
```
승인된 모든 도메인의 규칙을 조회합니다.

---

## 3. Rule Lifecycle Management

모든 규칙은 엄격한 생명주기(Lifecycle)를 따릅니다.

1.  **Draft (초안)**: 작성자가 규칙을 제안 (`submit_rule`). 판단에 사용되지 않음.
2.  **Review (검토)**: 관리자나 AI가 규칙을 검토 중.
3.  **Approved (승인)**: 검증된 규칙. `RuleCorpus`에 포함되어 실제 판단(Judgment)에 사용됨.
4.  **Deprecated (폐기)**: 효력이 만료된 규칙. 이력 보존용.

### API 활용
-   **제출**: `POST /rules` (구현 예정, 현재는 내부 submit_rule 사용)
-   **승인**: `POST /rules/{rule_id}/approve`

---

## 4. Corpus Versioning (Time-Travel)

시스템의 상태(`RuleCorpus`)는 시간에 따라 변화합니다. **Corpus Versioning** 기능은 특정 시점의 규칙 집합을 스냅샷으로 저장하고 복원합니다.

### 주요 기능
-   **Snapshot**: 현재 활성 규칙(`Approved`)을 버전으로 저장.
-   **History**: 과거 버전 조회.
-   **Time-Travel Visualization**: 특정 과거 시점의 토폴로지 다이어그램 생성.

### API 활용
-   **버전 목록**: `GET /versions`
-   **스냅샷 생성**: `POST /versions`
-   **과거 상태 시각화**: `GET /diagram/version/{version_id}`

---

## 5. Topology Visualization

현재 시스템의 구조와 규칙 관계를 **Mermaid.js** 다이어그램으로 시각화합니다.

### 기능
-   **Domain Filtering**: 특정 도메인(Profile)에 해당하는 에지만 필터링하여 복잡도 관리.
-   **Metadata Overlay**: 다이어그램 상단에 버전, 생성 시간, 규칙 수 등 메타데이터 표시.
-   **Judgment Visualization**: 유효성(`valid=true/false`)에 따라 에지 스타일(실선/점선) 변경.

### API 활용
-   **전체/필터링**: `GET /diagram?profile=marketing`
-   **버전별**: `GET /diagram/version/{version_id}?profile=crm`

---

## 6. Model I/O

시스템 간 데이터 이동을 위한 Import/Export를 지원합니다.

-   **Export**: 현재 상태(또는 특정 버전)를 JSON 파일로 내보내기. (`provenance` 포함)
-   **Import**: JSON 파일에서 규칙 자산 복원.

### API 활용
-   **내보내기**: `POST /model/export`
-   **가져오기**: `POST /model/import`
