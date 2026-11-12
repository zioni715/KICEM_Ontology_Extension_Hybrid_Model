# 공종별 기준 WBS

| 공종 | WBS | 입력 설명 수 |
|---|---|---:|
| 건축-타일공사 | [tile.md](tile.md) | 24 |
| 토목-우수공 | [stormwater.md](stormwater.md) | 12 |
| 소방-유도등 설비공사 | [exit_guidance.md](exit_guidance.md) | 15 |

- [기준·조항 추적표](EVIDENCE.md)
- [기계 판독용 후보 입력](../hybrid_multitrade/inputs/trade_candidates.json)
- WBS 번호는 프로젝트 내부 식별자이며 공식 기준의 분류번호가 아님.
- 작업 묶음은 읽기 편하게 정리한 WBS 구조이며 OWL의 모든 `subClassOf` 관계와 동일하지 않음.
- 실행 시에는 공종 루트 아래에 입력 설명을 평면 배치한 WBS를 사용하며, 아래 문서의 작업 묶음을 정답 부모로 전달하지 않음.
- 24·12·15건은 입력 설명 수이며 최종 모델 후보 수·채택 수와 다름. [실행 결과](../hybrid_multitrade/RESULTS.md) 참고.
- 위치·층·공구·물량·일정은 포함하지 않음.
- 독립 전문가 의미검증은 별도 수행.
