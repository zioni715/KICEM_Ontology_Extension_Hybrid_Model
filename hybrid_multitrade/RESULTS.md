# 하이브리드 T-Box 재실험 결과

- 입력: 공개 기준에서 정규화한 작업 설명. 비공개 기성서류 미사용.
- 모델: 기존 타일 파일럿의 GPT-4o-mini·BERT·E5·Llama 3.1 8B 구성 및 학습 설정 유지.
- 출력: T-Box만 포함. A-Box 생성기 미실행.
- 승인율은 정확도가 아님. 독립 전문가 정답이 없어 의미 정확도·재현율·F1은 산출하지 않음.

- 통합 실행은 동일 요청의 기존 응답 캐시를 재사용하며 캐시 적중과 신규 API 호출을 구분. 독립 반복실험으로 해석하지 않음.

## 공종별 산출물

| 공종 | 상태 | 입력 | 후보 | 최종 포함 후보 | 보류 | 전체 클래스 | 데이터 속성 | 논리·구조 검사 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 타일공사 | COMPLETED_TBOX | 24 | 18 | 10 | 8 | 39 | 4 | 통과 |
| 우수공 | COMPLETED_TBOX | 12 | 17 | 6 | 11 | 35 | 2 | 통과 |
| 유도등 설비공사 | COMPLETED_TBOX | 15 | 19 | 8 | 11 | 37 | 2 | 통과 |

## 3공종 API 토큰 사용량

- 모델: `gpt-4o-mini-2024-07-18`. API 응답의 `usage` 실측 합계.
- 최초 실행과 통합 실행의 실제 API 응답을 합산하고 응답 ID로 중복 제거.
- 로컬 응답 캐시 재사용은 신규 API 토큰 0개. 실패 응답에 usage가 없으면 합산하지 않음.
- 로컬 Llama 추론 및 BERT·E5 학습·임베딩 토큰은 아래 API 집계에 포함하지 않음.

| 공종 | API 성공 호출 | 입력 토큰 | 출력 토큰 | 총 토큰 |
|---|---:|---:|---:|---:|
| 타일공사 | 97 | 94,645 | 14,152 | 108,797 |
| 우수공 | 93 | 82,387 | 12,933 | 95,320 |
| 유도등 설비공사 | 94 | 88,651 | 13,752 | 102,403 |
| 합계 | 284 | 265,683 | 40,837 | 306,520 |

- 집계 기록: [token_usage.json](results/token_usage.json). 입력 토큰에는 API 제공자가 집계한 캐시 입력도 포함.

### 토큰 기준 예상 API 비용

- 적용 단가: 100만 토큰당 입력 $0.15, API 캐시 입력 $0.075, 출력 $0.60. 일반 동기 호출 기준(Batch 할인 미적용).
- 단가 확인일: 2026-11-12. 출처: [OpenAI 공식 GPT-4o Mini 가격](https://developers.openai.com/api/docs/models/gpt-4o-mini).
- 계산식: (입력−API 캐시 입력)×0.15/1,000,000 + API 캐시 입력×0.075/1,000,000 + 출력×0.60/1,000,000.
- 이번 API 캐시 입력은 0토큰. 로컬 응답 캐시 재사용에는 추가 API 비용이 없음.

| 공종 | 입력 비용(USD) | 출력 비용(USD) | 합계(USD) |
|---|---:|---:|---:|
| 타일공사 | $0.01419675 | $0.00849120 | $0.02268795 |
| 우수공 | $0.01235805 | $0.00775980 | $0.02011785 |
| 유도등 설비공사 | $0.01329765 | $0.00825120 | $0.02154885 |
| 합계 | $0.03985245 | $0.02450220 | $0.06435465 |

- 사용 로그와 공식 단가로 산출한 예상액이며 실제 청구서 확인액은 아님. 세금·환율·카드 수수료·계정 할인 및 로컬 GPU 전력·장비 비용 제외.

## 검증 범위

- 순수 T-Box: 명명·암시적 개체, 일반 속성값 assertion 차단.
- 계층: 순환 및 보류된 부모에 매달린 후보 제외.
- 직렬화: OWL·TTL 그래프 동등성 확인.
- OWLAPI: OWL 2 DL 프로파일 확인.
- HermiT: 온톨로지 일관성 및 명명 클래스 불만족 여부 확인.
- 근거 감사: API 의미 검토와 원문 인용 대조. 독립 전문가 검증은 아님.
- 한계: 원본 타일 파일럿의 보수적 근거 필터도 유지하므로 타 공종에서 과도한 보류 가능.
- 한계: 독립 공종별 T-Box 출력이며 원본 RC OWL 전체 공리의 무손실 통합을 검증한 것은 아님.

- 회귀검사: 20건 실행, 실패 0건, 오류 0건, 생략 0건. [실행 기록](results/verification.json).

## 타일공사

- 상세 기록: [JSON](results/architecture_tile.json).
- 검증 통과 산출물: [OWL](results/architecture_tile.owl), [TTL](results/architecture_tile.ttl).
- 통합 실행의 신규 API 호출: 성공 0회, 실패 0회. 최초 생성 호출은 위 토큰·비용 표에 포함.
- 동일 요청 캐시 재사용: 97회.
- 클래스 구성: 재사용 23개 + 연구자 정의 앵커 6개 + 채택 후보 10개.
- TaxoAdapt 신규 제안: 6개.
- 최종 후보가 인용한 입력 설명: 15/24건. 의미 재현율이 아닌 근거 인용 범위.
- TaxoPro RC seed 부모 복원: 2/4. 공종 확장 정확도가 아닌 소규모 내부 진단.
- 후보별 결과:

| 후보 | 상태 | 선택 부모 | 최종 포함 |
|---|---|---|---|
| 타일 접착제 비용 | held | TileMaterialCostItem | 아니오 |
| 타일 그라우트 비용 | accepted_provisional | TileMaterialCostItem | 예 |
| 타일 하부재 비용 | held | TileMaterialCostItem | 아니오 |
| 벽타일 설치 비용 | accepted_provisional | CostItem | 예 |
| 바닥타일 설치 비용 | accepted_provisional | TileInstallationCostItem | 예 |
| 모자이크 타일 설치 비용 | accepted_provisional | CostItem | 예 |
| 타일 시공 작업 | accepted_provisional | WorkTask | 예 |
| 타일 유지보수 작업 | held | WorkTask | 아니오 |
| 타일 검사 작업 | accepted_provisional | WorkTask | 예 |
| wall_tile_installation | accepted_provisional | WallTileInstallationCostItem | 예 |
| floor_tile_installation | held | — | 아니오 |
| tile_maintenance | held | CostItem | 아니오 |
| wall_tile_installation | accepted_provisional | TileInstallationWorkType | 예 |
| floor_tile_installation | accepted_provisional | TileInstallationWorkType | 예 |
| tile_installation_inspection | accepted_provisional | TileInspectionWorkType | 예 |
| 타일 표면 준비 | held | — | 아니오 |
| 타일 접착제 선택 | held | — | 아니오 |
| 타일 유지보수 계획 | held | — | 아니오 |

## 우수공

- 상세 기록: [JSON](results/civil_stormwater.json).
- 검증 통과 산출물: [OWL](results/civil_stormwater.owl), [TTL](results/civil_stormwater.ttl).
- 통합 실행의 신규 API 호출: 성공 0회, 실패 0회. 최초 생성 호출은 위 토큰·비용 표에 포함.
- 동일 요청 캐시 재사용: 93회.
- 클래스 구성: 재사용 23개 + 연구자 정의 앵커 6개 + 채택 후보 6개.
- TaxoAdapt 신규 제안: 6개.
- 최종 후보가 인용한 입력 설명: 6/12건. 의미 재현율이 아닌 근거 인용 범위.
- TaxoPro RC seed 부모 복원: 1/4. 공종 확장 정확도가 아닌 소규모 내부 진단.
- 후보별 결과:

| 후보 | 상태 | 선택 부모 | 최종 포함 |
|---|---|---|---|
| 우수 집수 비용 항목 | held | StormwaterMaterialCostItem | 아니오 |
| 우수관로 측량 비용 항목 | held | StormwaterMaterialCostItem | 아니오 |
| 배수 측구 설치 비용 | accepted_provisional | StormwaterInstallationCostItem | 예 |
| 우수받이 설치 비용 | accepted_provisional | StormwaterInstallationCostItem | 예 |
| 집수정 설치 비용 | accepted_provisional | StormwaterInstallationCostItem | 예 |
| 우수 배수관 설치 비용 | accepted_provisional | StormwaterInstallationCostItem | 예 |
| 배수공사 | accepted_provisional | WorkTask | 예 |
| 배수 측량 | held | WorkTask | 아니오 |
| stormwater_construction_cost_item | held | — | 아니오 |
| stormwater_survey_cost_item | held | StormwaterInstallationCostItem | 아니오 |
| stormwater_installation_cost_item | held | — | 아니오 |
| stormwater_installation | accepted_provisional | DrainageConstruction | 예 |
| stormwater_survey | held | DrainageConstruction | 아니오 |
| slope_construction | held | DrainageConstruction | 아니오 |
| 우수 품질 모니터링 | held | — | 아니오 |
| 배수 시스템 유지보수 | held | — | 아니오 |
| 홍수 위험 평가 | held | — | 아니오 |

## 유도등 설비공사

- 상세 기록: [JSON](results/fire_exit_guidance.json).
- 검증 통과 산출물: [OWL](results/fire_exit_guidance.owl), [TTL](results/fire_exit_guidance.ttl).
- 통합 실행의 신규 API 호출: 성공 0회, 실패 0회. 최초 생성 호출은 위 토큰·비용 표에 포함.
- 동일 요청 캐시 재사용: 94회.
- 클래스 구성: 재사용 23개 + 연구자 정의 앵커 6개 + 채택 후보 8개.
- TaxoAdapt 신규 제안: 6개.
- 최종 후보가 인용한 입력 설명: 14/15건. 의미 재현율이 아닌 근거 인용 범위.
- TaxoPro RC seed 부모 복원: 1/4. 공종 확장 정확도가 아닌 소규모 내부 진단.
- 후보별 결과:

| 후보 | 상태 | 선택 부모 | 최종 포함 |
|---|---|---|---|
| 유도등 설치 비용 | held | MaterialCostForExitGuidanceLights | 아니오 |
| 유도등 유지보수 비용 | held | ExitGuidanceMaterialCostItem | 아니오 |
| 유도등 자재 비용 | held | — | 아니오 |
| 피난구유도등 부착 비용 | accepted_provisional | ExitGuidanceInstallationCostItem | 예 |
| 계단통로유도등 설치 비용 | accepted_provisional | ExitGuidanceInstallationCostItem | 예 |
| 객석유도등 설치 비용 | accepted_provisional | ExitGuidanceInstallationCostItem | 예 |
| 유도표지 설치 비용 | accepted_provisional | ExitGuidanceInstallationCostItem | 예 |
| 설치 작업 | accepted_provisional | WorkTask | 예 |
| 부착 작업 | held | WorkTask | 아니오 |
| 전기 작업 | accepted_provisional | WorkTask | 예 |
| installation_specification | held | — | 아니오 |
| evacuation_light_cost | held | — | 아니오 |
| sign_and_power_supply_cost | held | — | 아니오 |
| emergency_light_installation | accepted_provisional | InstallationWorkType | 예 |
| led_light_installation | held | — | 아니오 |
| corridor_and_step_light_installation | accepted_provisional | InstallationWorkType | 예 |
| 유도등 유지보수 | held | — | 아니오 |
| 유도등 사용 교육 | held | — | 아니오 |
| 유도등 규정 준수 감사 | held | — | 아니오 |
