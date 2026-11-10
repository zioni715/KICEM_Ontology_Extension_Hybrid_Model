# 3개 공종 독립 전문가 의미검증

자동검증은 OWL 구조·일관성·재현성과 고정 내부 gold 일치도를 확인한다. 내부 gold를
보며 예측 규칙을 개발했으므로, 새로운 공종의 일반화 성능이나 독립 의미 정확도를
대신하지 않는다.

1. 다음 명령으로 51개 후보 검토지를 생성한다.

   ```bash
   python final_tbox/prepare_multitrade_expert_review.py
   ```

2. 건축/토목/소방 및 건설정보 분야 검토자 2명이 서로의 판정을 보지 않고
   `reports/multitrade_expert_review.json`의 `reviewer_1`, `reviewer_2`를 작성한다.
3. 각 후보에 대해 T-Box 클래스 적합성, 근거 조항의 지지 여부, 가장 구체적인 is-a
   직접 부모를 판정한다. 공정의 선후관계나 part-of 관계를 `subClassOf`로 바꾸지 않는다.
4. 제3의 판정자가 불일치를 검토하고 모든 `adjudication`을 작성한다.
5. 다음 명령으로 결과를 채점한다.

   ```bash
   python final_tbox/score_multitrade_expert_review.py
   ```

후보 51개만 검토하므로 클래스 유효율·근거 지지율·유효 클래스의 부모 정확도는 계산할
수 있지만, 생성하지 못한 개념까지 필요한 selection recall은 계산할 수 없다. Recall을
보고하려면 각 기준 문서에서 별도의 누락 개념 표본을 독립적으로 구축해야 한다.
