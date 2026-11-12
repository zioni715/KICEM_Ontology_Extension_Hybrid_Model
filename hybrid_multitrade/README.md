# 하이브리드 모델 3공종 재실험

## 통합 모델 구조

- 진입점: `run.py` 하나. 공종별 실행 스크립트를 생성하거나 복제하지 않음.
- 공통 구현: `pipeline/`의 추출·TaxoPro·MILA·TaxoAdapt·TEMPORA·LOREx·근거 감사.
- 공종 설정: `pipeline/configs/trades.json`. 클래스 접두어·공종 식별자·용어만 변경.
- 입력: `inputs/trade_candidates.json`의 공종별 데이터.
- 공종별 작업 폴더에는 데이터·로그·캐시·체크포인트만 보관. 외부 알고리즘 라이브러리는 동일 원본을 참조.
- 모델 구성·하이퍼파라미터는 공통이며, 공종별 데이터로 순차 실행. 세 공종을 공동 학습한 단일 가중치라는 의미는 아님.

## 현재 상태

- 2026-11-12 키 갱신 후 3공종 실제 재실험 완료.
- 후보/채택/보류: 타일 18/10/8, 우수공 17/6/11, 유도등 19/8/11.
- 최종 클래스: 39/35/37개. 순수 T-Box·OWL 2 DL·HermiT·직렬화 검사 모두 통과.
- 독립 전문가 의미 정확도 평가는 미실시. 채택 수를 정답 수로 해석하지 않음.
- 상세 결과: [RESULTS.md](RESULTS.md).
- 실행 상태 기록: [STATUS.json](results/STATUS.json).
- 통합 코드로 세 공종 전체 실행 완료. 통합 전후 후보별 결정·OWL 그래프 동등성 확인.
- 회귀검사 20건 통과, 실패·오류·생략 0건.
- 실제 키 값은 문서·결과에 저장하지 않음.

## 고정한 조건

- 원본: 로컬 `tile_case_study/`의 모듈 1~5 구현.
- 순서: 추출·초기 스키마 → TaxoPro → MILA → TaxoAdapt → TEMPORA·LOREx → 근거 감사·원문 필터 → T-Box 출력.
- API: `gpt-4o-mini-2024-07-18`.
- 로컬 생성·계보 점수: `meta-llama/Llama-3.1-8B-Instruct`의 기존 revision.
- TaxoPro·TEMPORA: 기존 multilingual BERT, 학습률·epoch·seed·loss 유지.
- MILA: 기존 multilingual E5와 양방향 후보 검색 유지.
- 세 공종 모두 같은 Python 파일을 실행하고 공통 소스 SHA-256 기록.
- 평가 gold는 빌드와 추론에 전달하지 않음.

## 변경 범위와 비교 한계

- 이전 공종별 실험은 보존. 통합 실행 데이터는 `.runs/unified/<공종>/`에 격리.
- 공종명, 실행 경로, 공종별 입력을 파라미터화.
- 비공개 기성서류를 외부로 보내지 않기 위해 세 공종 모두 공개 기준에서 정규화한 설명·WBS를 사용.
- 입력 24/12/15건은 `inputs/trade_candidates.json`의 라벨·정의·근거이며, 정답 부모는 포함하지 않음.
- 가격·물량 데이터가 없으므로 숫자를 추정하지 않고 null로 전달.
- 기존 타일 기성서류 실험과 입력 종류가 다르므로 결과를 동일 조건의 재현이라고 주장하지 않음.
- 최종 출력은 기존 A-Box exporter를 실행하지 않고 T-Box 전용 어댑터 사용.
- 기준 원문 전체의 자동 추출 평가와 독립 전문가 정확도 평가는 별도 필요.

## 실행

- 환경 생성: 저장소 루트에서 `conda env create -f environment.yml` 후 `conda activate hybrid-v1`.
- `requirements.txt` 하나에 3공종 전체 Python 의존성 포함. Java는 Conda로 설치하고 모델·외부 소스는 별도 준비.

- 프로젝트 루트의 `.env`에서 유효한 `OPENAI_API_KEY`를 설정한다. 외부 알고리즘 라이브러리와 로컬 모델이 있는 `hybrid-v1` 환경에서 실행한다.

```bash
conda activate hybrid-v1
python hybrid_multitrade/run.py
```

- Java 17: `environment.yml`로 설치. 경로 직접 지정 시 `TBOX_JAVA`·`TBOX_JAVAC` 사용

- 공종별 실행:

```bash
python hybrid_multitrade/run.py --trade civil_stormwater
python hybrid_multitrade/run.py --trade fire_exit_guidance
```

- 공통 파이프라인 코드는 저장소에 포함. 외부 라이브러리·모델은 로컬 Git 제외 폴더를 참조하므로 새 clone에서는 별도 준비 필요.
- `.runs/`: 단계 로그, API 감사, 체크포인트·캐시. Git 제외. 공종별 Python 파일 생성 없음.
- `results/`: 완료된 공종의 T-Box와 정량 요약. 실패는 실패 상태로 기록.

## T-Box 출력 제한

- 포함: 승인된 클래스, 상속, 근거 주석, 지원되는 데이터 속성의 선언·domain·range.
- 제외: 현장·층·공구·WBS 개체, 개체의 클래스 소속, 개체 간 관계, 물량·단가·기성실적 값.
- `owl:NamedIndividual` 선언이 없어도 클래스 소속 assertion과 일반 속성값 assertion을 차단.
- T-Box 검사·OWL 2 DL·HermiT·직렬화 검사를 임시 파일에서 수행하고 모두 통과한 경우에만 최종 OWL·TTL 게시.
- `tbox_export.py`: T-Box 생성·A-Box 차단.
- `owl_validation.py`: OWLAPI·HermiT 실행.
- `tests/`: 입력·학습조건 보존, A-Box 주입 차단, 논리 검증기 대조검사, 산출물·해시 재검사. 모델 성능평가와 구분.
- 공통 소스 실행·공종 설정 분리·T-Box 검증 결과: [검사 기록](results/verification.json).
