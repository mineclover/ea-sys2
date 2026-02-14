# Validity Rules - 올바른 형식과 실제 동작 분석

"TOML에서 정의한 규칙들이 로드되지 않고 fallback deny만 생성"된 현상을 올바른 형식으로 재분석합니다.

## 문제의 원인: TOML 형식 불일치

### 잘못된 형식 (원래 FruitRetail)

```toml
[[validity_rules]]  # ← 로더가 읽지 않음!
id = "fruit-assoc-01"
source_pattern = "Store"       # ← 필드명 다름
target_pattern = "Supplier"    # ← 필드명 다름
relationship_type = "association"  # ← 필드명 다름
valid = true
priority = 50
```

**결과:** 규칙 0개 로드 → fallback rules만 생성

### 올바른 형식 (fruit_retail_profile_fixed.toml)

```toml
[[rules]]  # ← 로더가 읽음!
id = "fruit-assoc-supplies"
source = "Supplier"     # ← 올바른 필드명
target = "Store"        # ← 올바른 필드명
relation = "supplies"   # ← 올바른 필드명
valid = true
priority = 50
```

**결과:** 규칙 17개 로드 + fallback rules 17개 = 총 34개

---

## 필드명 매핑 (핵심!)

| 프로파일 로더가 기대 | 잘못된 형식 | 올바른 형식 |
|-------------------|----------|----------|
| `[[rules]]` | `[[validity_rules]]` ✗ | `[[rules]]` ✓ |
| `source` | `source_pattern` ✗ | `source` ✓ |
| `target` | `target_pattern` ✗ | `target` ✓ |
| `relation` | `relationship_type` ✗ | `relation` ✓ |
| `valid` | `valid` ✓ | `valid` ✓ |
| `priority` | `priority` ✓ | `priority` ✓ |
| `id` | `id` ✓ | `id` ✓ |
| `notes` | `notes` ✓ | `notes` ✓ |

---

## 실제 동작 분석 (올바른 형식)

### Step 1: TOML 로드

```python
doc = tomllib.loads(content)

# 결과:
doc["rules"] = [17개 규칙]  # ← 로더가 읽을 수 있음!
doc["validity_rules"] = undefined  # (TOML에 없음)
```

### Step 2: 프로파일 로더 실행 (profile_loader.py)

```python
# Lines 138-172
for rule in doc.get("rules", []):  # ← 이번엔 17개를 찾음!
    source = rule.get("source")      # "Supplier"
    target = rule.get("target")      # "Store"
    relation = rule.get("relation")  # "supplies"
    valid = rule.get("valid", True)  # True
    priority = rule.get("priority", 40 if valid else 80)  # 50

    if valid:
        builder.allow(
            source, target, relation,
            priority=priority, notes=notes, rule_id=rule_id
        )
    else:
        builder.deny(
            source, target, relation,
            priority=priority, notes=notes, rule_id=rule_id
        )
```

**실행 결과:**
- 17개 규칙이 모두 `allow()` 메서드로 등록됨
- 각 규칙의 source, target, relation이 올바르게 매핑됨

### Step 3: ProfileBuilder.build() 실행

```python
def build(self) -> KernelProfile:
    # self._rules에 17개의 사용자 규칙이 있음
    rules = list(self._rules)  # 17개

    # 각 relation마다 fallback 추가
    for rel in self._relations:  # 17개 relation
        rules.append(KernelValidityRule(
            id=f"fallback-{rel.name}",
            source_pattern="*",
            target_pattern="*",
            relationship_name=rel.name,
            valid=False,  # ← Deny
            priority=1    # ← 최저 우선순위
        ))

    # 최종 규칙 개수: 17 (user) + 17 (fallback) = 34
    return KernelProfile(
        ...
        validity_rules=tuple(rules)
    )
```

### Step 4: 최종 결과

```
총 34개 규칙:
  ✓ 17 ALLOW (사용자 정의)
  ✗ 17 DENY (자동 fallback)
```

규칙 목록:
```
fruit-assoc-supplies         ALLOW  Supplier → Store (supplies)
fruit-assoc-stocks           ALLOW  Store → Inventory (stocks)
fruit-assoc-sells_to         ALLOW  Store → Customer (sells_to)
... (14개 더)
fallback-supplies            DENY   * → * (supplies)
fallback-stocks              DENY   * → * (stocks)
fallback-contains            DENY   * → * (contains)
... (14개 더)
```

---

## Fallback Rules의 역할 (이제 명확함)

### 정의

각 relation마다 자동으로 추가되는 "기본값" 규칙:

```
Rule(
    id="fallback-{relation_name}",
    source_pattern="*",      # 모든 source
    target_pattern="*",      # 모든 target
    relationship_name="{relation_name}",
    valid=False,             # 거부
    priority=1               # 최저 우선순위
)
```

### 목적: Whitelist 보안 모델

**정책:** 명시적으로 허용한 관계만 가능

```
시나리오 1: 규칙이 정의된 경우
─────────────────────────────
kernel_judge("Supplier", "Store", "supplies")

매칭 규칙:
  1. fruit-assoc-supplies (priority 50, valid=True)
  2. fallback-supplies (priority 1, valid=False)

우선순위 정렬 → priority 50 우승
→ Verdict: True (ALLOW)
```

```
시나리오 2: 규칙이 정의되지 않은 경우
─────────────────────────────────
kernel_judge("SomeEntity", "OtherEntity", "supplies")

매칭 규칙:
  1. fallback-supplies (priority 1, valid=False)
     (다른 규칙이 없음)

→ Verdict: False (DENY)
→ 이유: fallback이 마지막 방어선
```

```
시나리오 3: DENY 규칙이 있는 경우
─────────────────────────────────
kernel_judge("X", "Y", "supplies")

규칙 (가상의 명시적 거부):
  1. fruit-deny-x-y (priority 80, valid=False)
  2. fallback-supplies (priority 1, valid=False)

우선순위 정렬 → priority 80 우승
→ Verdict: False (DENY)
→ 이유: 명시적 거부가 우선
```

### 왜 Fallback이 필요한가?

**없다면:**
```
relation "supplies" 정의
규칙 "Supplier → Store" 정의 안 함

kernel_judge("Random", "Random", "supplies")
→ 일치하는 규칙이 없음
→ 어떻게 결정할 것인가? (모호함)
```

**Fallback 있음:**
```
relation "supplies" 정의
fallback-supplies 자동 생성 (priority 1, DENY)

kernel_judge("Random", "Random", "supplies")
→ fallback 매칭
→ Verdict: False (DENY)
→ 명확함!
```

---

## 실제 규칙 검증 (올바른 형식)

### 테스트: 정의된 관계 검증

```python
from ea_kernel.rule_corpus import RuleCorpus
from ea_kernel.spec import KERNEL_SPEC
from ea_kernel.spec_loader import load_kernel_rules_with_metadata

# 프로파일 규칙 로드 (올바른 형식)
profile = load_profile(Path('examples/fruit_retail_profile_fixed.toml'))

# 커널 규칙도 로드
_, _, metadata_map = load_kernel_rules_with_metadata()
corpus = RuleCorpus.from_kernel_spec(KERNEL_SPEC, metadata_map)
```

### 테스트 케이스 1: 허용된 관계

```
Query: Supplier → Store via supplies
Expected: True (명시적으로 정의함)

프로파일 규칙 확인:
  fruit-assoc-supplies (priority 50, valid=True) ✓ 매칭!

Result: True (ALLOW)
```

### 테스트 케이스 2: 정의되지 않은 관계

```
Query: Customer → Supplier via supplies
Expected: False (정의되지 않음)

프로파일 규칙 확인:
  fruit-assoc-supplies (Supplier → Store) ✗ 매칭 안 함
  fallback-supplies (priority 1, valid=False) ✓ 매칭!

Result: False (DENY by fallback)
```

### 테스트 케이스 3: 프로세스 순서 보장

```
Query: ReceiveProduct → CheckQuality via receive_then_check
Expected: True (프로세스 정의함)

프로파일 규칙 확인:
  fruit-succ-receive-check (priority 50, valid=True) ✓ 매칭!

Result: True (ALLOW)
```

```
Query: ReceiveProduct → DisplayProduct via receive_then_check
Expected: False (직접 연결 불가, CheckQuality 필수)

프로파일 규칙 확인:
  fruit-succ-receive-check (ReceiveProduct → CheckQuality) ✗ 매칭 안 함
  fallback-receive_then_check (priority 1, valid=False) ✓ 매칭!

Result: False (DENY by fallback)
→ 프로세스 순서가 자동으로 강제됨!
```

---

## 올바른 형식의 강점

### 1. 규칙이 실제로 로드됨

**Before (잘못된 형식):**
```
Rules parsed: 0
Fallback generated: 17
Total: 17 (모두 거부)
```

**After (올바른 형식):**
```
Rules parsed: 17 ✓
Fallback generated: 17
Total: 34 (17개 허용, 17개 거부)
```

### 2. 프로세스 흐름이 명시적으로 정의됨

```python
# 올바른 형식으로 정의 가능:

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

# 결과:
# ReceiveProduct → CheckQuality → DisplayProduct
# 이 순서가 자동으로 강제됨 (다른 경로는 fallback으로 거부)
```

### 3. 비즈니스 로직이 코드처럼 표현됨

```
비즈니스 규칙: "품질 검사 없이 판매할 수 없다"
↓
TOML:
[[rules]]
source = "CheckQuality"
target = "DisplayProduct"
relation = "check_then_display"
valid = true
↓
자동 효과: CheckQuality → DisplayProduct 만 허용
다른 경로는 fallback (DENY)로 거부
```

---

## 깊이 있는 이해: 우선순위 시스템

### 규칙 우선순위 분포

```
Priority 80 ← 명시적 DENY (강제 거부)
Priority 60 ← 강한 ALLOW (특정 조건)
Priority 50 ← 일반 ALLOW (대부분의 규칙)
Priority 40 ← 약한 ALLOW (광범위 허용)
Priority 1  ← Fallback DENY (마지막 방어선)
```

### FruitRetail의 우선순위 분포

```
Priority 60: 1개 (check_then_discard - guarding)
Priority 50: 16개 (일반 비즈니스 규칙)
Priority 1:  17개 (fallback)

Total: 34개
```

### 충돌 해결 로직

```
여러 규칙이 매칭될 때:
1. 우선순위가 높은 규칙부터 정렬
2. 첫 번째 매칭 규칙의 valid 값 반환
3. 어떤 규칙도 매칭 안 되면 fallback 사용
```

**예: Guarding 규칙**
```
kernel_judge("CheckQuality", "DiscardExpired", "check_then_discard")

매칭 규칙:
  1. fruit-guard-discard (priority 60, valid=True) ← 우승!
  2. fallback-check_then_discard (priority 1, valid=False)

→ Verdict: True (priority 60 우승)
```

---

## 이제 명확한 통찰

### 원래 문제 재검토

**"TOML에서 정의한 규칙들이 로드되지 않고 fallback deny만 생성"**

**이유:**
- ✓ TOML 형식이 잘못됨 (`[[validity_rules]]` vs. `[[rules]]`)
- ✓ 필드명이 다름 (`source_pattern` vs. `source`)
- ✓ 로더가 `[[rules]]` 섹션만 읽음
- ✗ 이것은 "버그"가 아니라 형식 불일치

**해결:**
- ✓ 올바른 형식으로 작성하면 규칙이 완벽하게 로드됨
- ✓ 17개 규칙 + 17개 fallback = 34개 규칙
- ✓ 프로세스가 자동으로 강제됨

### Fallback의 진짜 역할

**아니라고 생각했던 것:**
"규칙이 로드 안 되면 자동으로 관계 거부"

**실제 역할:**
"명시적으로 정의되지 않은 관계는 거부 (Whitelist 원칙)"

**비유:**
```
집의 초대 정책:

Blacklist (일반):
  - "특정 사람 제외 외 모두 초대"
  - 위험: 실수로 초대할 가능성

Whitelist (ea-kernel):
  - "명시적으로 초대한 사람만"
  - fallback: "나머지는 모두 거부"
  - 안전: 의도한 사람만 들어옴
```

---

## 결론

### 3줄 요약

1. **형식 문제** — `[[validity_rules]]`가 아니라 `[[rules]]`여야 함
2. **필드명 문제** — `source_pattern`이 아니라 `source`여야 함
3. **완벽하게 동작** — 올바른 형식으로 쓰면 17개 규칙이 모두 로드되고, 각 관계가 명시적으로 제어됨

### 핵심 통찰

**ea-kernel은 "명시적 선언 + 자동 강제"**

```
정책:        관계를 명시적으로 정의해야 함
구현:        [[rules]] 섹션에 선언
자동 강제:   fallback (priority 1, DENY)로 정의 안 된 관계 거부
결과:        의도하지 않은 관계 불가능 → 안전한 모델
```

---

## 참고: 올바른 형식 사용 예

```toml
# ✓ 올바른 형식

[profile]
name = "FruitRetail"
version = "1.0.0"
kernel_version = "2.5.0"

[[elements]]
name = "Store"
kernel_type = "structure"
layer = "operational"

[[relations]]
name = "supplies"
kernel_relation = "association"

[[rules]]  # ← 핵심!
id = "fruit-assoc-supplies"
source = "Supplier"      # ← 올바른 필드명
target = "Store"         # ← 올바른 필드명
relation = "supplies"    # ← 올바른 필드명
valid = true
priority = 50
```

**결과:**
```
✓ 규칙 로드됨
✓ Supplier → Store via supplies 허용
✓ 다른 조합은 fallback으로 거부
```
