from __future__ import annotations


def render_overview_guide(st) -> None:
    guide_items = (
        (
            "기간 비교 뱃지",
            "각 Summary 카드에 표시되는 색상 뱃지입니다.",
            "현재 선택한 날짜 범위와 동일한 길이의 직전 기간을 자동 비교하여 증감률을 계산합니다. "
            "예를 들어 4/1~4/10을 선택하면 3/22~3/31과 비교합니다.",
            "초록색(상승)이 항상 좋은 것은 아닙니다. WIP 증가는 초록이 아닌 빨간색으로 표시됩니다. "
            "\"변동 없음\"은 안정적인 상태를, \"NEW\"는 이전 기간에 데이터가 없었음을 뜻합니다.",
        ),
        (
            "Summary 카드 구성",
            "Active Developers, GitHub Signals, PR Flow, Jira WIP, Delivery, Sync Scope 6개 카드로 구성됩니다.",
            "활성 개발자 수, GitHub PR/커밋/라인 수, PR cycle time과 stale PR, Jira 진행 중 업무, "
            "배포 성공/실패, 데이터 동기화 범위를 한눈에 봅니다.",
            "숫자가 갑자기 변하면 실제 활동 변화인지, 필터 범위 변경인지, 동기화 누락인지를 먼저 확인하세요.",
        ),
    )
    _render_inline_guide(st, guide_items)


def render_health_guide(st) -> None:
    guide_items = (
        (
            "업무 분배도",
            "개발자별 PR+커밋 수의 변동계수(CV)를 계산합니다.",
            "CV < 0.5이면 양호, 0.5~1.0이면 주의, 1.0 초과면 경고입니다.",
            "팀 규모가 작거나 역할이 다른 경우(예: 인프라 vs 피처 개발) "
            "CV가 높을 수 있습니다. 맥락과 함께 해석하세요.",
        ),
        (
            "리뷰 흐름",
            "PR이 생성된 후 첫 리뷰를 받기까지의 평균 대기 시간입니다.",
            "12시간 미만이면 양호, 12~48시간이면 주의, 48시간 초과면 경고입니다.",
            "대기 시간이 길면 리뷰어가 부족하거나, PR이 너무 크거나, "
            "리뷰 문화가 비동기적일 수 있습니다.",
        ),
        (
            "WIP 추세",
            "최근 3개 기간의 진행 중 업무(Todo + In Progress + Review) 변화율을 봅니다.",
            "감소/안정이면 양호, 30% 미만 증가면 주의, 30% 이상 급증이면 경고입니다.",
            "WIP가 계속 쌓이면 완료율이 투입률을 따라가지 못하는 신호입니다. "
            "스코프 조정이나 병목 해소를 검토하세요.",
        ),
        (
            "배포 안정성",
            "성공 배포 / 전체 배포 비율입니다.",
            "90% 초과면 양호, 70~90%면 주의, 70% 미만이면 경고입니다.",
            "GitHub Deployments를 사용하지 않는 팀은 \"데이터 부족\"으로 표시됩니다. "
            "실패율이 높으면 CI/CD 파이프라인과 테스트 커버리지를 점검하세요.",
        ),
    )
    _render_inline_guide(st, guide_items)


def render_alerts_guide(st) -> None:
    guide_items = (
        (
            "WIP 편중 감지",
            "특정 개발자의 진행 중 업무가 팀 평균의 2배를 초과할 때 발생합니다.",
            "업무가 한 사람에게 몰리면 병목과 번아웃 위험이 높아집니다.",
            "의도적 집중(예: 긴급 대응)인지, 구조적 불균형인지 구분하세요. "
            "지속되면 업무 재분배를 검토합니다.",
        ),
        (
            "리뷰 병목 감지",
            "팀 평균 첫 리뷰 대기 시간이 24시간을 초과할 때 발생합니다.",
            "리뷰 지연은 PR이 오래 열려있게 만들고, merge conflict와 context switching을 유발합니다.",
            "리뷰어 로테이션, PR 크기 줄이기, 리뷰 시간 블록 설정 등을 검토하세요.",
        ),
        (
            "Stale PR / 대형 PR / 비활성",
            "Stale PR 5건 초과, 대형 PR(500줄+) 비율 50% 초과, 이전 기간 대비 비활성 개발자 감지 시 발생합니다.",
            "방치된 PR, 지나치게 큰 변경, 갑작스러운 활동 중단을 조기에 포착합니다.",
            "info 수준의 경고이므로 즉각 조치보다는 주간 점검 시 참고하세요. "
            "비활성은 휴가, 온보딩, 또는 데이터 연결 문제일 수 있습니다.",
        ),
    )
    _render_inline_guide(st, guide_items)


def render_signal_chart_guide(st) -> None:
    chart_guide_items = (
        (
            "Team Workload Trend",
            "팀 전체의 작업량 추이",
            "기간별 추가된 코드 라인 수(막대)와 머지된 PR 수·할당된 이슈 수(선)를 함께 봅니다.",
            "코드 변경량과 PR/이슈 활동이 같은 방향으로 움직이는지 확인합니다. "
            "라인 수가 급증하면 대규모 리팩터링이나 생성 파일이 섞였을 수 있으니 맥락을 확인하세요.",
        ),
        (
            "PR Flow",
            "PR 흐름 분석",
            "Stale PR 수(막대)와 평균 cycle time·평균 첫 리뷰 대기 시간(선)을 봅니다.",
            "리뷰 병목을 찾는 핵심 차트입니다. cycle time이 길면 PR이 크거나 리뷰어가 부족한 신호이고, "
            "review wait가 길면 리뷰 시작 자체가 지연되는 것입니다. Stale PR이 쌓이면 방치된 작업을 점검하세요.",
        ),
        (
            "Per-Developer Comparison",
            "개발자별 활동 비교",
            "개발자별 머지된 PR, 랜딩된 커밋, 할당된 이슈를 수평 막대로 비교합니다.",
            "특정 개발자에게 작업이 몰리거나, 반대로 활동이 거의 없는 경우를 식별합니다. "
            "개인 순위가 아니라 업무 분산 상태를 보는 용도입니다.",
        ),
        (
            "DORA-lite Delivery",
            "배포 현황 (DORA-lite)",
            "성공/실패 배포 수(막대)와 평균 배포 리드 타임(선)을 봅니다.",
            "배포 빈도와 안정성을 함께 확인합니다. 실패 배포가 증가하면 CI/CD 파이프라인이나 테스트 커버리지를 점검하세요. "
            "GitHub Deployments를 사용하지 않으면 0으로 표시됩니다.",
        ),
        (
            "Jira WIP Balance",
            "Jira 진행 중 업무 분포",
            "개발자별 할당 이슈를 Todo·In Progress·Review·Done·Other 상태로 나눈 스택 막대입니다.",
            "한 사람에게 WIP가 과도하게 쌓이거나, 특정 상태에 이슈가 정체되는 패턴을 찾습니다. "
            "Jira 상태 이름 매핑이 넓으므로 팀 워크플로에 맞춰 해석하세요.",
        ),
        (
            "GitHub & Jira Split",
            "GitHub·Jira 활동 비율",
            "현재 필터 범위에서 머지된 PR, 랜딩된 커밋, 할당된 이슈의 절대 수치를 막대로 봅니다.",
            "구현 활동(GitHub)과 이슈 추적 활동(Jira) 사이의 균형을 참고합니다. "
            "한쪽만 높다면 데이터 연결 상태나 팀의 도구 사용 패턴을 확인하세요.",
        ),
    )
    for label, ko_title, definition, interpretation in chart_guide_items:
        st.markdown(
            f"**{label}** — {ko_title}\n\n"
            f"- **무엇을 보나** — {definition}\n"
            f"- **해석 방법** — {interpretation}\n"
        )


def _render_inline_guide(st, items) -> None:
    for label, definition, detail, interpretation in items:
        st.markdown(
            f"**{label}**\n\n"
            f"- **무엇인가** — {definition}\n"
            f"- **기준** — {detail}\n"
            f"- **해석 팁** — {interpretation}\n"
        )
