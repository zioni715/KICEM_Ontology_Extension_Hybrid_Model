# 3개 공종 T-Box 자동확장 릴리스 3.1.0

건축-타일공사, 토목-우수공, 소방-유도등 설비공사의 독립 T-Box를 생성하고 검증한다.
후보 입력에는 부모 정답이 없으며 builder는 검증 gold를 읽지 않는다. 산출물은 클래스,
주석 속성 및 T-Box 공리만 포함하고 명명 개체나 사실 assertion을 포함하지 않는다.

## 실행

```bash
conda env create -f environment.yml
conda activate kicem-tbox-validation
python final_tbox/release_multitrade.py --stress-cycles 10
```

환경이 이미 있으면 다음 명령으로 동기화한다.

```bash
conda env update -n kicem-tbox-validation -f environment.yml --prune
```

성공 시 `reports/multitrade_release_gate.json`의 `passed`가 `true`가 된다.

## 배포 구조

```text
final_tbox/
├── benchmarks/
│   ├── multitrade_candidates.json   # 부모 정답 없는 빌드 입력
│   └── multitrade_gold.json         # validator 전용 내부 개발 gold
├── outputs/multitrade/              # 공종별 OWL·TTL 및 manifest
├── reports/                         # 최종 기계 검증 보고서
├── tests/                           # 격리 빌드·변조 차단 테스트
├── validators/java/                 # OWLAPI·HermiT 검증기
├── multitrade_build.py
├── multitrade_validate.py
├── multitrade_adversarial_validate.py
├── multitrade_stress_validate.py
├── multitrade_release_gate.py
└── release_multitrade.py            # 단일 배포 명령
```

## 최종 자동검증

- 세 공종 후보 51개 및 직접 부모 51개
- 내부 개발 gold TP 51, FP 0, FN 0
- competency question 51/51
- OWL 2 DL, HermiT 일관성 및 명명 클래스 만족 가능성
- Turtle/RDF/XML 동등성 및 순수 T-Box 검사
- 후보별 결함 주입 312/312 검출
- 냉간 프로세스 10회 동일 해시
- 현재 산출물과 스트레스 기준 해시 결속
- 공식 근거 URL 8개 접근성 감사
- 최소 Python 의존성 알려진 취약점 감사
- gold 없는 임시 디렉터리 빌드 및 변조 차단 단위검사

최종 내부 상태는 `INTERNAL_RELEASE_READY_EXTERNAL_REVIEW_PENDING`이다.

## 해석 경계

내부 1.0은 동일한 세 공종 gold를 보며 예측 규칙을 개발한 적합도다. 후보 입력에서 부모
정답을 제거했지만, 보지 않은 공종의 일반화 정확도 100%나 독립 전문가 정확도를 의미하지
않는다. 외부 의미검증은 `MULTITRADE_EXPERT_REVIEW_PROTOCOL.md` 절차로 수행한다.
누락 개념에 대한 selection recall은 별도의 누락 개념 표본이 있어야 계산할 수 있다.

배포 전 항목은 `RELEASE_CHECKLIST.md`, 상세 결과는 `FINAL_REPORT.md`, 기준 근거는
`WBS_EVIDENCE.md`, 사람이 읽는 계층형 작업분류는 `WBS.md`를 따른다.
