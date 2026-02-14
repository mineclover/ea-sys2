# ea-kernel 표현력 검토

FruitRetail 예제를 통해 ea-kernel이 실제 비즈니스 로직을 얼마나 잘 표현할 수 있는지 검토합니다.

## 1. 구조적 표현 (L1-L2)

### 테스트 케이스: "누가 무엇을 가지는가?"

**비즈니스 요구사항:**
```
Store는 Inventory를 유지하고
Inventory는 Product를 포함한다
Supplier는 Store에 공급한다
Customer는 Store에서 구매한다
```

**ea-kernel으로의 표현:**

```toml
# L1: Elements (무엇인가?)
[[elements]]
name = "Store"
kernel_type = "structure"

[[elements]]
name = "Supplier"
kernel_type = "structure"

[[elements]]
name = "Product"
kernel_type = "item"

[[elements]]
name = "Inventory"
kernel_type = "item"

[[elements]]
name = "Customer"
kernel_type = "structure"

# L2: Relations (어떻게 연결되는가?)
[[relations]]
name = "supplies"
kernel_relation = "association"
source_element = "Supplier"
target_element = "Store"

[[relations]]
name = "stocks"
kernel_relation = "association"
source_element = "Store"
target_element = "Inventory"

[[relations]]
name = "contains"
kernel_relation = "feature_typing"
source_element = "Inventory"
target_element = "Product"

[[relations]]
name = "sells_to"
kernel_relation = "association"
source_element = "Store"
target_element = "Customer"
```

**표현력 평가:** ⭐⭐⭐⭐⭐ (5/5)
- ✓ 명확한 엔터티 분류 (structure vs. item)
- ✓ 관계의 의미가 명확 (association, feature_typing)
- ✓ 양방향 관계 가능 (supplies, sells_to)
- ✓ 계층 구조 명시 (Store → Inventory → Product)

---

## 2. 프로세스 흐름 표현 (L3-L4)

### 테스트 케이스: "순서를 강제할 수 있는가?"

**비즈니스 요구사항:**
```
1. Supplier가 제품을 보냄
2. Store가 받음 (ReceiveProduct)
3. 품질 검사 (CheckQuality)
4. 합격: 진열 (DisplayProduct)
5. 불합격: 폐기 (DiscardExpired)
6. 진열: 판매 (SaleTransaction)
7. 판매: 결제 (ProcessPayment)

이 순서는 필수이고, 순서를 어기면 불가능해야 함
```

**ea-kernel으로의 표현:**

```toml
# L3: Behavioral (흐름과 상태 변화)
[[relations]]
name = "supply_flow"
kernel_relation = "flow"
source_element = "Supplier"
target_element = "Store"

[[relations]]
name = "quality_transition"
kernel_relation = "transition"
source_element = "Product"
target_element = "Product"
description = "Product changes state through quality check"

# L4: Concrete (실제 단계들)
[[elements]]
name = "ReceiveProduct"
kernel_type = "step"

[[elements]]
name = "CheckQuality"
kernel_type = "step"

[[elements]]
name = "DisplayProduct"
kernel_type = "step"

[[elements]]
name = "SaleTransaction"
kernel_type = "step"

[[elements]]
name = "ProcessPayment"
kernel_type = "step"

[[elements]]
name = "DiscardExpired"
kernel_type = "step"

# L4 Rules: 실행 순서 강제
[[rules]]
id = "fruit-succ-receive-check"
source = "ReceiveProduct"
target = "CheckQuality"
relation = "receive_then_check"
valid = true
priority = 50

[[rules]]
id = "fruit-succ-check-display"
source = "CheckQuality"
target = "DisplayProduct"
relation = "check_then_display"
valid = true
priority = 50

# 조건부 분기
[[rules]]
id = "fruit-guard-discard"
source = "CheckQuality"
target = "DiscardExpired"
relation = "check_then_discard"
valid = true
priority = 60
notes = "Guarding: discard if quality fails"

[[rules]]
id = "fruit-succ-display-sale"
source = "DisplayProduct"
target = "SaleTransaction"
relation = "display_then_sale"
valid = true
priority = 50

[[rules]]
id = "fruit-succ-sale-payment"
source = "SaleTransaction"
target = "ProcessPayment"
relation = "sale_then_payment"
valid = true
priority = 50
```

**표현 가능한 시나리오:**

```
✓ ReceiveProduct → CheckQuality
✓ CheckQuality → DisplayProduct (합격시)
✓ CheckQuality → DiscardExpired (불합격시)
✓ DisplayProduct → SaleTransaction
✓ SaleTransaction → ProcessPayment

✗ ReceiveProduct → DisplayProduct (직결 불가)
✗ ReceiveProduct → SaleTransaction (직결 불가)
✓ (자동 강제됨)
```

**표현력 평가:** ⭐⭐⭐⭐⭐ (5/5)
- ✓ 선형 흐름 표현 (succession)
- ✓ 조건부 분기 표현 (guarding)
- ✓ 순서 강제 (fallback deny)
- ✓ 우선순위로 충돌 해결
- ✓ "이 순서를 어기면 불가능"을 자동화로 표현

---

## 3. 상태 변화 표현 (Transition)

### 테스트 케이스: "Product의 상태 변화를 표현할 수 있는가?"

**비즈니스 요구사항:**
```
Product는 여러 상태를 가짐:
- 도착시: "not_inspected"
- 검사후: "inspected" 또는 "rejected"
- 진열: "displayed"
- 판매: "sold"
- 폐기: "discarded"

상태 전환:
received → checked → (displayed OR discarded)
displayed → sold
```

**ea-kernel으로의 표현:**

```toml
# 상태 전환을 transition으로 표현
[[relations]]
name = "quality_transition"
kernel_relation = "transition"
source_element = "Product"
target_element = "Product"
description = "Product: not_inspected → inspected"

[[relations]]
name = "freshness_transition"
kernel_relation = "transition"
source_element = "Product"
target_element = "Product"
description = "Product: inspected → displayed"

# 규칙으로 상태 전환 제어
[[rules]]
id = "fruit-trans-quality"
source = "Product"
target = "Product"
relation = "quality_transition"
valid = true
priority = 50

[[rules]]
id = "fruit-trans-freshness"
source = "Product"
target = "Product"
relation = "freshness_transition"
valid = true
priority = 50
```

**표현 능력:**
- ✓ 같은 타입 간의 상태 변화
- ✗ 구체적인 상태값 (not_inspected, inspected, ...) 미지원
- ✗ 상태 다이어그램 (상태명, 조건, 액션) 미지원

**표현력 평가:** ⭐⭐⭐ (3/5)
- ✓ 상태 전환 존재 인정
- ✗ 상태값 명시 불가능
- ✗ 상태 머신 조건 표현 불가능

**제약사항:**
```
가능: "Product는 transition을 거친다"
불가능: "Product는 {not_inspected, inspected, sold} 중 하나"
불가능: "Product가 not_inspected이면서 displayed일 수는 없다"
```

---

## 4. 데이터 제약 표현 (Constraints)

### 테스트 케이스: "비즈니스 규칙을 강제할 수 있는가?"

**비즈니스 요구사항:**
```
1. Store는 Supplier가 없으면 제품을 받을 수 없다
2. Inventory가 비어있으면 판매할 수 없다
3. CheckQuality 없이는 DisplayProduct로 이동 불가능
4. 총 판매액이 10만원을 초과할 수 없다
5. 하루에 최대 100개만 판매 가능
6. Customer의 나이가 18세 미만이면 특정 제품 구매 불가
```

**ea-kernel으로의 표현 능력:**

```
Rule 1: ✓ 가능
  Store ← Supplier (association 정의)

Rule 2: ⚠️ 부분 가능
  Inventory ← Product (feature_typing 정의)
  Display만 가능 (구체적 개수 제약 불가)

Rule 3: ✓ 가능
  CheckQuality → DisplayProduct (succession)

Rule 4: ✗ 불가능
  "총 판매액" 개념 자체 없음

Rule 5: ✗ 불가능
  "하루에 100개" = 시간 + 수량 개념 필요

Rule 6: ✗ 불가능
  "Customer.age < 18" 조건 불가능
```

**표현력 평가:** ⭐⭐ (2/5)
- ✓ 구조적 제약 (관계 존재 필수)
- ✓ 순서 제약 (succession)
- ✗ 수치 제약 (금액, 수량)
- ✗ 시간 제약 (일별, 시간별)
- ✗ 조건부 로직 (if-then)
- ✗ 속성 조건 (age < 18)

---

## 5. 확장성 표현 (추가 도메인)

### 테스트 케이스: "비즈니스 변경 시 기존 모델이 유지되는가?"

**시나리오: "물류 센터를 추가하고 싶다"**

```toml
# 새로운 요소 추가
[[elements]]
name = "WarehouseCenter"
kernel_type = "structure"
layer = "operational"

# 새로운 관계 추가
[[relations]]
name = "supplier_to_warehouse"
kernel_relation = "flow"
source_element = "Supplier"
target_element = "WarehouseCenter"

[[relations]]
name = "warehouse_to_store"
kernel_relation = "flow"
source_element = "WarehouseCenter"
target_element = "Store"

# 새로운 규칙 추가
[[rules]]
id = "fruit-flow-supplier-warehouse"
source = "Supplier"
target = "WarehouseCenter"
relation = "supplier_to_warehouse"
valid = true
priority = 50

[[rules]]
id = "fruit-flow-warehouse-store"
source = "WarehouseCenter"
target = "Store"
relation = "warehouse_to_store"
valid = true
priority = 50
```

**영향 분석:**
- ✓ 기존 "supplies" 관계는 그대로 유지
- ✓ 기존 "CheckQuality" 규칙은 여전히 적용
- ✓ 새로운 요소와 관계만 추가
- ✗ 기존 규칙의 "우선순위 충돌" 문제 없음

**표현력 평가:** ⭐⭐⭐⭐⭐ (5/5)
- ✓ 기존 모델 보존
- ✓ 새 요소 추가 용이
- ✓ 새 규칙 추가 용이
- ✓ 모순 없음 (확장성 우수)

---

## 6. 크로스 엔터티 제약 (Cross-Entity Rules)

### 테스트 케이스: "여러 엔터티에 걸친 규칙을 표현할 수 있는가?"

**비즈니스 요구사항:**
```
1. Supplier A의 제품만 특별히 검사하고 싶다
2. Customer 그룹별로 다른 제품을 보여주고 싶다
3. Inventory 수량이 기준값 아래면 자동 재주문
4. Product 카테고리에 따라 다른 가격 정책
```

**ea-kernel으로의 표현:**

```
1. ✗ 불가능
   "Supplier A의 제품" = 특정 인스턴스 조건
   ea-kernel은 타입 수준에서만 정의 (인스턴스 수준 불가)

2. ✗ 불가능
   "Customer 그룹" = 속성 기반 분류
   속성 개념 없음

3. ⚠️ 부분 가능
   "Inventory 수량" = 정량적 데이터
   수량 개념 자체 없음
   "RestockCheck 규칙"으로 재주문 프로세스만 정의 가능

4. ✗ 불가능
   "Product 카테고리" = 분류 속성
   "다른 가격 정책" = 속성별 규칙
   이를 위해선 constraint 조건이 필요
```

**표현력 평가:** ⭐ (1/5)
- ✗ 인스턴스 수준 규칙 불가능
- ✗ 속성 기반 조건 불가능
- ✗ 정량적 데이터 제약 불가능
- ✗ 조건부 라우팅 불가능

---

## 7. 상호운용성 표현 (Multi-Framework)

### 테스트 케이스: "여러 프레임워크의 모델을 합칠 수 있는가?"

**시나리오:**
```
팀 A: ArchiMate로 "비즈니스 서비스" 정의
팀 B: SysML2로 "시스템 아키텍처" 정의

두 모델이 호환되는가?
```

**ea-kernel 기반 검증:**

```python
# 양쪽 모두 kernel 기반
archimate_profile = load_profile("archimate.toml")
sysml_profile = load_profile("sysml2.toml")

# 같은 rule corpus로 검증
archimate_verdict = kernel_judge(
    "Service",      # ArchiMate 타입
    "Application",  # SysML2 타입
    "association"   # 공통 relation
)
# → Verdict: True (둘 다 호환)
```

**표현력 평가:** ⭐⭐⭐⭐ (4/5)
- ✓ 프레임워크 중립적 기초 제공
- ✓ 타입 간 호환성 검증 가능
- ✓ 공통 규칙으로 검증
- ✗ 프레임워크 간 데이터 변환은 지원 안 함

---

## 8. 시각화 표현 (Diagrams)

### 테스트 케이스: "다이어그램으로 자동 생성할 수 있는가?"

**가능한 다이어그램:**

```
1. 엔터티-관계 다이어그램 (ERD)
   ✓ 가능: L1-L2 요소와 relation으로 생성

2. 프로세스 흐름도 (Flow Diagram)
   ✓ 가능: L4 succession으로 생성

3. 상태 다이어그램 (State Machine)
   ⚠️ 부분: transition 있지만 상태값 없음

4. 계층 구조도 (Tree)
   ✓ 가능: L1 parent 필드로 생성

5. 시퀀스 다이어그램 (Sequence)
   ⚠️ 부분: succession으로 순서는 알 수 있지만 시간축 없음

6. 조직도 (Organization Chart)
   ⚠️ 부분: association으로 관계는 나타낼 수 있지만 계층 구조 한정
```

**표현력 평가:** ⭐⭐⭐ (3/5)
- ✓ 자동 생성 가능한 다이어그램 있음
- ✗ 상태 다이어그램 완전 지원 안 함
- ✗ 시퀀스 다이어그램 완전 지원 안 함
- ✗ 타이밍/시간축 개념 없음

---

## 종합 표현력 평가

### 영역별 평가

| 영역 | 평가 | 설명 |
|------|------|------|
| **구조적 표현 (L1-L2)** | ⭐⭐⭐⭐⭐ | 우수: 엔터티/관계 명확 |
| **프로세스 흐름 (L3-L4)** | ⭐⭐⭐⭐⭐ | 우수: 순서 강제 가능 |
| **상태 변화** | ⭐⭐⭐ | 부분: 전환은 있으나 상태값 없음 |
| **데이터 제약** | ⭐⭐ | 약함: 구조 제약만, 값 제약 불가 |
| **크로스 엔터티 규칙** | ⭐ | 매우 약함: 인스턴스/속성 불가 |
| **확장성** | ⭐⭐⭐⭐⭐ | 우수: 기존 모델 보존하며 확장 |
| **상호운용성** | ⭐⭐⭐⭐ | 좋음: 프레임워크 간 호환 검증 |
| **시각화** | ⭐⭐⭐ | 부분: 일부 다이어그램만 자동화 |

**평균:** ⭐⭐⭐⭐ (3.5/5)

---

## 강점 (Strengths)

### 1. 구조와 프로세스의 명확한 분리

```
L1-L2: "무엇이 무엇과 연결되는가?"
L3-L4: "어떤 순서로 일어나는가?"

명확한 구분으로 모델의 복잡성 관리 가능
```

### 2. 순서 강제 메커니즘

```
succession + fallback = 의도한 순서만 가능
자동화 도구가 실행할 수 있는 수준의 형식성
```

### 3. 위협 없는 확장

```
새 요소 추가 → 기존 규칙 깨지지 않음
새 규칙 추가 → 우선순위로 충돌 해결
backward-compatible 확장
```

### 4. 프레임워크 중립성

```
ArchiMate, TOGAF, Zachman, SysML2, BPMN
모두 같은 기초에서 호환성 검증 가능
```

---

## 약점 (Weaknesses)

### 1. 상태값 및 속성 표현 불가

```
불가능:
- "Product.state = {received, inspected, displayed}"
- "Customer.age >= 18"
- "Inventory.quantity > 100"

해결책: 외부 데이터모델 필요
```

### 2. 정량적 제약 불가능

```
불가능:
- "일일 판매량 <= 100"
- "총액 <= 100만원"
- "응답시간 <= 5초"

해결책: 별도 SLA/계약 명시
```

### 3. 조건부 로직 부족

```
불가능:
- "if quality_score < 50 then discard"
- "if customer_type == 'VIP' then special_service"

대신 가능:
- "CheckQuality → DiscardExpired" (무조건)
```

### 4. 인스턴스 수준 규칙 불가능

```
불가능:
- "Supplier A의 제품만 특별 검사"
- "특정 Product ID에 대한 규칙"

해결책: 런타임 정책 엔진 필요
```

### 5. 시간 개념 부재

```
불가능:
- "하루에 최대 N회"
- "매시간 재고 확인"
- "배송 기간 48시간"

해결책: 워크플로우 엔진의 스케줄링
```

---

## 적정 사용 범위

### ✓ 추천하는 영역

```
1. EA 비즈니스 모델링
   - 비즈니스 엔터티 정의
   - 조직 구조와 역할
   - 프로세스 흐름 (고수준)

2. 시스템 아키텍처
   - 컴포넌트 간 관계
   - 계층별 구조
   - 데이터 흐름

3. 규제 준수 모델링
   - 프로세스 순서 강제
   - 의무 단계 정의
   - 워크플로우 제약

4. 멀티 프레임워크 통합
   - 프레임워크 간 호환성 검증
   - 공통 메타모델
   - 상호운용성 확보
```

### ✗ 부적정한 영역

```
1. 상세 데이터 모델링
   - 정규화 스키마
   - 제약 조건
   - 속성값 범위

2. 실시간 시스템
   - 성능 제약 (응답시간, 처리량)
   - 동적 스케줄링
   - 리소스 할당

3. 복잡한 비즈니스 규칙
   - 조건부 분기 (if-then-else)
   - 예외 처리
   - 도메인 룰스

4. 예측/분석
   - 통계 모델
   - 머신러닝
   - 시뮬레이션
```

---

## 개선 제안

### 1. 상태 다이어그램 지원

```toml
[element_states]
Product = ["received", "inspected", "displayed", "sold", "discarded"]

[[state_transitions]]
element = "Product"
from = "received"
to = "inspected"
relation = "quality_transition"
guard = "CheckQuality"
```

### 2. 속성 기반 조건

```toml
[[conditional_rules]]
source = "Product"
source_condition = { category = "fresh" }
target = "DisplayArea"
relation = "can_display"
valid = true
```

### 3. 정량적 제약

```toml
[[quantitative_rules]]
element = "Inventory"
attribute = "quantity"
operator = ">"
threshold = 0
relation = "can_sell"
valid = true
```

### 4. 시간 기반 규칙

```toml
[[temporal_rules]]
activity = "SaleTransaction"
frequency = "per_day"
max_count = 100
unit_time = "24h"
```

---

## 결론

### 한 문장 평가

**"ea-kernel은 구조와 프로세스를 명확하게 정의하고 순서를 강제할 수 있지만, 복잡한 비즈니스 조건과 데이터 제약은 외부 시스템과 함께 사용해야 한다."**

### 적절한 비유

```
JavaScript (매우 자유로움, 위험)
  ↓
TypeScript (타입 강제, 안전)  ← ea-kernel은 여기 수준
  ↓
고급 형식언어 (완전 형식화)

ea-kernel:
- 타입 레벨 안전성 ✓
- 프로세스 강제 ✓
- 런타임 로직 ✗
```

### 실무 권고사항

**ea-kernel만으로:**
- ✓ 비즈니스 프로세스 설계
- ✓ 조직 구조 모델링
- ✓ 시스템 아키텍처

**ea-kernel + 추가 도구:**
- ✓ 비즈니스 규칙 엔진 (Drools, RuleEngine)
- ✓ 데이터 모델 (ERD, 데이터베이스)
- ✓ 워크플로우 엔진 (BPMN, jBPM)
- ✓ 성능/SLA 관리 (별도 정책)

**계층 아키텍처 제안:**

```
┌─────────────────────────────────────────┐
│   Runtime Execution (Drools, jBPM)     │
├─────────────────────────────────────────┤
│   ea-kernel (구조 + 프로세스)           │
├─────────────────────────────────────────┤
│   Data Model (ERD, Schema)              │
├─────────────────────────────────────────┤
│   Infrastructure (Performance, SLA)     │
└─────────────────────────────────────────┘
```

이 계층 구조에서 ea-kernel은 "아키텍처 통제" 역할을 합니다.
