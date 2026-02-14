# Runbook: Kernel Governance DB Backup & Restore

## 대상

- `rules.db`
- `decisions.db`
- `versions.db`
- `profiles.db`
- (선택) `transactions.db` (K3, ea-governance 경로에서 별도 백업)

기본 디렉터리 예시:
- `governance_data/default/`

## 1) 백업 절차

1. 서비스 쓰기 정지(maintenance mode)
2. 드리프트 체크 실행:
   - `uv run python packages/ea-kernel/src/ea_kernel/scripts/check_kernel_governance_drift.py --data-dir governance_data/default`
3. 백업 디렉터리 생성:
   - `mkdir -p backups/<timestamp>`
4. DB 파일 복사:
   - `cp governance_data/default/*.db backups/<timestamp>/`
5. 체크섬 매니페스트 생성:
   - `python - <<'PY'`
   - `from pathlib import Path`
   - `import hashlib, json`
   - `backup_dir = Path("backups/<timestamp>")`
   - `files = ["rules.db", "decisions.db", "versions.db", "profiles.db"]`
   - `def sha256(path: Path) -> str:`
   - `    h = hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()`
   - `manifest = {"files": {name: sha256(backup_dir / name) for name in files}}`
   - `(backup_dir / "checksums.sha256.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\\n", encoding="utf-8")`
   - `PY`
6. 백업 검증:
   - `sqlite3 backups/<timestamp>/profiles.db "PRAGMA integrity_check;"`
   - 각 DB에 대해 `ok` 확인

## 2) 복구 절차

1. 현재 서비스 중지
2. 복구 포인트 선택 (`backups/<timestamp>`)
3. 기존 DB 보존(rollback 대비):
   - `mv governance_data/default governance_data/default.pre-restore.<timestamp>`
4. 복구:
   - `mkdir -p governance_data/default`
   - `cp backups/<timestamp>/*.db governance_data/default/`
5. 체크섬 검증:
   - `python - <<'PY'`
   - `from pathlib import Path`
   - `import hashlib, json`
   - `backup_dir = Path("backups/<timestamp>")`
   - `manifest = json.loads((backup_dir / "checksums.sha256.json").read_text(encoding="utf-8"))`
   - `for name, expected in manifest["files"].items():`
   - `    actual = hashlib.sha256((backup_dir / name).read_bytes()).hexdigest()`
   - `    if actual != expected:`
   - `        raise SystemExit(f"checksum mismatch: {name}")`
   - `PY`
6. 스키마/드리프트 확인:
   - `uv run python packages/ea-kernel/src/ea_kernel/scripts/check_kernel_governance_drift.py --data-dir governance_data/default`
7. 서비스 기동 후 스모크 테스트:
   - 모델 조회/판정/트랜잭션 조회 API 확인

## 3) 실패 시 롤백

복구 직후 문제가 발생하면:
1. 서비스 중지
2. 복구본 제거
3. `default.pre-restore.<timestamp>`를 `default`로 복원
4. 서비스 재기동

## 4) 정기 점검

주기:
- 일 1회 백업
- 주 1회 복구 리허설(격리 환경)

필수 점검:
- `integrity_check` 결과
- 드리프트 체크 결과
- 핵심 API 스모크 테스트 통과

## 5) 자동 리허설

격리 환경에서 복구 리허설 자동 실행:
- `uv run python packages/ea-kernel/src/ea_kernel/scripts/rehearse_kernel_governance_recovery.py --data-dir <tmp-data-dir> --backup-dir <tmp-backup-dir>`

CI/로컬 통합 게이트:
- `make gate-kernel-governance-db`

참고:
- `transactions.db`는 `ea-governance` 런타임 경로 기준으로 동일한 체크섬 절차를 별도 적용한다.
