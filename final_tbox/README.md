# 3개 공종 온톨로지 자동확장 최종 T-Box

RC seed 기반 타일 최종본과 별도로 건축-타일, 토목-우수, 소방-유도등 설비공사 3개 검증 T-Box를 생성한다. A-Box가 들어 있는 데모 OWL을 입력으로 사용하거나 사후에 잘라내지 않는다. 최종 산출물에는 클래스·속성·공리만 포함하며 문서행, WBS 노드, 단위, 회차 같은 개체와 사실 assertion은 포함하지 않는다.

## 실행

```bash
conda env create -f environment.yml
conda activate kicem-tbox-validation
python final_tbox/release_multitrade.py --stress-cycles 10
```

이 명령이 현재 3개 공종 릴리스의 기준 명령이다. 기존 `run_final.py`는 과거
RC→타일 단일 사례까지 함께 재현하는 호환용 워크플로다.

생성 파일:

- `outputs/tile_tbox_final.ttl`: 최종 T-Box Turtle
- `outputs/tile_tbox_final.owl`: 최종 T-Box RDF/XML
- `outputs/manifest.json`: 입력·출력 해시와 확장 내역
- `reports/validation.json`: 전체 검증 결과와 최종 판정
- `reports/evaluation.json`: 근거·계층·재현성·저표본 성능 평가
- `reports/mutation_tests.json`: 오류 주입 대조군 6종 결과
- `reports/environment_audit.json`: 원실험 전체 재실행 가능 상태
- `reports/expert_review.json`: 독립 전문가 2인 및 판정자 입력 양식
- `reports/release_gate.json`: 산출물·의미평가·전체 재실행을 합친 최종 릴리스 판정
- `reports/internal_semantic_validation.json`: 후보 20개 및 competency question 10개 내부 의미검증
- `reports/closed_loop.json`: 두 번의 전체 검증 반복과 수렴 fingerprint
- `outputs/multitrade/`: 타일·우수·유도등 공종별 Turtle/RDF/XML과 해시 manifest
- `reports/multitrade_validation.json`: 3개 공종의 독립 gold·OWLAPI·HermiT·변이검증
- `reports/multitrade_closed_loop.json`: 3개 공종 전체를 2회 반복한 수렴 결과
- `reports/multitrade_stress_validation.json`: 새 프로세스 10회 반복 및 공식 출처 접근성 감사
- `reports/multitrade_adversarial_validation.json`: 후보별 근거·의미·계층 결함 전수 주입 검사
- `reports/multitrade_release_gate.json`: 위 검사를 합친 보수적 최종 내부 릴리스 판정
- `WBS_EVIDENCE.md`: 공종별 공식 기준, WBS 범위와 제외 범위

## 최종 게이트

다음 항목 중 하나라도 실패하면 종료 코드 1을 반환한다.

1. Turtle/RDF/XML 동형성 및 입력 해시 불변성
2. A-Box class assertion, `owl:NamedIndividual`, nominal(`hasValue`, `oneOf`) 부재
3. 예상 클래스·속성 수와 명명 클래스 계층 비순환성
4. 철근콘크리트 전용 클래스 및 보류 후보의 미포함
5. 채택 후보 전부의 문서/WBS 근거 식별자 존재
6. OWLAPI의 OWL 2 DL 프로파일 및 직렬화 검사
7. HermiT 일관성 및 만족 불가능한 명명 클래스 부재
8. 동일 입력 연속 빌드의 Turtle/RDF/XML 바이트 해시 동일성
9. A-Box·순환·보류 후보·근거 삭제·RC 클래스·nominal 오류 주입 검출
10. 3개 공종 후보와 검증 gold의 입력 분리 및 공종별 직접 부모 일치
11. 공종별 A-Box·계층 순환·근거 삭제 오류 주입 검출

## 판정 해석

- `VALIDATED`: 기술 검증과 독립 전문가 정답 기반 의미 평가가 모두 통과한 상태다.
- `TECHNICALLY_VALIDATED_SEMANTICALLY_PROVISIONAL`: T-Box 구조·논리·근거 검증은 통과했으나 독립 전문가 정답셋이 없어 의미 정확도를 확정할 수 없는 상태다.
- `FAILED`: 기술 검증에서 한 항목 이상 실패한 상태다.

통합 릴리스 판정의 `FINAL_INTERNAL_VALIDATION_COMPLETE`는 기술 검증과 제공 자료 기반 내부 의미검증이 모두 완료됐다는 뜻이다. 이는 독립 외부 전문가 성능평가와 동일한 뜻이 아니다.

`FINAL_CLOSED_LOOP_VALIDATION_COMPLETE`는 여기에 두 번의 전체 재생성·검증 반복이 같은 fingerprint로 수렴했다는 조건을 추가한 현재 최종 내부 상태다.

3개 공종 검증은 후보 51개를 대상으로 실행되며 최종 기계 판정은
`multitrade_release_gate.json`을 따른다. `INTERNAL_RELEASE_READY_EXTERNAL_REVIEW_PENDING`는
재생성·논리·구조·근거·내부 gold·오류 주입 검증을 통과했다는 뜻이며, 독립 전문가
평가가 완료됐다는 뜻은 아니다. 각 공종은 독립 namespace와 산출물을 가지며, 모든
작업 클래스는 해당 공종 루트 아래에서도 조회 가능하다.

일관성과 OWL 2 DL 적합성은 잘못된 상·하위 의미를 자동으로 증명하지 않는다. 따라서 독립 전문가가 타일 후보의 채택 여부와 직접 부모를 라벨링하기 전에는 “자동확장 정확도가 검증 완료됐다”고 주장하지 않는다.

## 데모에서 최종본으로 변경한 내용

- A-Box 포함 데모 OWL을 입력에서 제거하고 seed와 후보 판정에서 직접 T-Box를 생성한다.
- `AdhesiveCostItem`이지만 실제 의미가 압착붙임이던 클래스 4개를 `PressureBondingCostItem`으로 정규화했다.
- 해시형 `TA_ac621fe07583`을 `WallTileInstallation`로 정규화했다.
- `WallTileInstallation`의 부모를 포괄적인 `WorkTask`에서 의미상 직접 부모인 `TileInstallation`로 교정했으며, 자동 모델 원출력과 구분되도록 `releaseCuration` annotation에 기록했다.
- 원문 전체를 T-Box에 싣지 않고 `evidenceSourceId`만 보존했다.

## 현재 남은 외부 게이트

- `reports/expert_review.json`의 후보 20개에 대해 독립 전문가 2인과 판정자의 검토가 필요하다. 절차와 채점 방법은 [`EXPERT_REVIEW_PROTOCOL.md`](EXPERT_REVIEW_PROTOCOL.md)에 있다.
- 현재 GPU 드라이버가 응답하지 않고 `requirements.txt` 해시가 원실험 기록과 달라 Module1~5의 완전 재실행 준비 상태는 실패다. 저장 산출물 기반 최종 T-Box 빌드·검증과 원 모델 전체 재실행은 구분한다.
