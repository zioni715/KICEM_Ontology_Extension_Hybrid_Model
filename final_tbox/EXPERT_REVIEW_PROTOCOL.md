# 독립 전문가 의미평가 프로토콜

자동 검증은 문법·프로파일·논리·근거 존재를 확인하지만 클래스의 도메인 의미가 옳은지는 확정하지 못한다. 의미 성능 수치는 다음 절차를 완료한 경우에만 보고한다.

1. 건축시공 또는 건설정보 분야 검토자 2명이 `reports/expert_review.json`의 후보 20개를 독립적으로 판정한다.
2. 각 후보가 T-Box 클래스인지, 인용 근거가 개념을 지지하는지, 제안된 직접 부모가 가장 구체적인 is-a 부모인지를 확인한다.
3. 작업 분해의 `part-of`를 `subClassOf`로 판정하지 않는다.
4. 두 검토 결과를 확인한 제3의 판정자가 모든 후보의 `adjudication`을 작성한다.
5. 검토자와 판정자의 식별자는 비어 있으면 안 되며, 채택 후보에는 `correct_parent`가 필요하다.
6. 다음 명령으로 precision, recall, F1과 채택 후보 부모 정확도를 계산한다.

```bash
/home/sil-jiwon/anaconda3/envs/hybrid-v1/bin/python final_tbox/score_expert_review.py
```

`status`가 `COMPLETE`가 아니면 의미 정확도는 논문·보고서에서 검증 완료로 표기하지 않는다.
