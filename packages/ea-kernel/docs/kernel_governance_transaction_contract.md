# Kernel Governance Transaction Contract (K3)

## 목적

거버넌스 실행 트랜잭션을 메모리에서만 관리하지 않고 영속 저장하여,
재시작 이후에도 상태/이벤트를 추적 가능하게 만든다.

## 구현 위치

- 트랜잭션 매니저:
  - `packages/ea-governance/src/ea_governance/transaction.py`
- 실행 서비스 연계:
  - `packages/ea-governance/src/ea_governance/execution_service.py`
- 파사드 연계:
  - `packages/ea-governance/src/ea_governance/facade.py`

## 저장소

기본 파일:
- `transactions.db` (GovernanceContainer의 `data_dir` 하위)

초기화 시 생성 테이블:
- `schema_version`
- `transactions`
- `transaction_events`

## 상태 전이

`TransactionStatus`:
- `pending`
- `in_progress`
- `committed`
- `rolled_back`
- `failed`

핵심 전이:
1. `begin_transaction` -> `in_progress`
2. `commit` -> `committed`
3. `rollback` -> `rolled_back`
4. `fail` -> `failed`

## 이벤트 기록

`transaction_events`에 아래 이벤트가 기록된다.
- `begin`
- `commit`
- `rollback`
- `fail`

각 이벤트는 `message`, `payload_json`, `created_at`을 가진다.

## API 계약

### TransactionManager

- `begin_transaction(name, tx_type, payload)`
- `commit(tx_id)`
- `rollback(tx_id, reason)`
- `fail(tx_id, error_msg)`
- `get_transaction(tx_id)`
- `get_events(tx_id)`

### GovernanceContainer

- `get_transaction_status(tx_id)`
- `get_transaction_logs(tx_id)`
- `get_transaction_events(tx_id)`

## 호환성

- `TransactionManager`는 DB 경로가 필수이며 영속 모드로만 동작
- `ExecutionService`는 기본값으로 `<kernel.data_dir>/../transactions.db`를 사용

## 테스트

- `packages/ea-governance/tests/test_transaction_manager.py`
- `packages/ea-governance/tests/test_transaction_persistence.py`

검증 포인트:
1. 성공/롤백 상태 전이
2. 로그 기록
3. 재시작 후 트랜잭션 상태/이벤트 재조회
