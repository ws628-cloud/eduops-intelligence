
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ==========================================
# 1. 웹사이트 기본 설정
# ==========================================

st.set_page_config(
    page_title="EduOps Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. 디자인 설정
# ==========================================

st.markdown("""
<style>
.block-container {
    max-width: 1450px;
    padding-top: 1rem;
    padding-bottom: 1rem;
}

h1 {
    color: #172554;
    font-size: 1.8rem !important;
}

h3 {
    font-size: 1.02rem !important;
}

div[data-testid="stMetric"] {
    background: #F1F5F9;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 12px 16px;
}

div[data-testid="stMetricValue"] {
    font-size: 1.8rem;
}

div[data-testid="stMetricLabel"] {
    font-size: 0.85rem;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 데이터 불러오기
# ==========================================

@st.cache_data
def load_data():
    students = pd.read_csv("students.csv")

    enrollments = pd.read_csv(
        "enrollments_lite_simulated.csv"
    )

    voc = pd.read_csv("voc_connected.csv")

    return students, enrollments, voc


students, enrollments, voc = load_data()

courses = ["기초", "초급", "중급", "고급"]

# ==========================================
# 4. 데이터 무결성 기본 검사
# ==========================================

required_enrollment = [
    "enrollment_id",
    "student_id",
    "month",
    "course_level",
    "cohort_id",
    "is_lite"
]

required_voc = [
    "voc_id",
    "student_id",
    "enrollment_id",
    "month",
    "course_level",
    "category"
]

assert set(required_enrollment).issubset(
    enrollments.columns
), "등록 데이터 컬럼을 확인해 주세요."

assert set(required_voc).issubset(
    voc.columns
), "VOC 데이터 컬럼을 확인해 주세요."

assert enrollments["enrollment_id"].is_unique
assert students["student_id"].is_unique
assert voc["voc_id"].is_unique

assert enrollments["student_id"].isin(
    students["student_id"]
).all()

# VOC 등록번호 및 학생번호 연결 검사
voc_check = voc.merge(
    enrollments[
        ["enrollment_id", "student_id", "month", "course_level"]
    ],
    on="enrollment_id",
    how="left",
    suffixes=("", "_source"),
    validate="many_to_one"
)

assert (
    voc_check["student_id"]
    == voc_check["student_id_source"]
).all()

assert (
    voc_check["month"]
    == voc_check["month_source"]
).all()

assert (
    voc_check["course_level"]
    == voc_check["course_level_source"]
).all()

# ==========================================
# 5. 등록 이력에서 KPI 계산
# ==========================================

enrollments = enrollments.sort_values(
    ["student_id", "month"]
).reset_index(drop=True)

enrollments["next_month"] = (
    enrollments.groupby("student_id")["month"].shift(-1)
)

enrollments["next_level"] = (
    enrollments.groupby("student_id")["course_level"].shift(-1)
)

current_date = pd.to_datetime(enrollments["month"])
next_date = pd.to_datetime(enrollments["next_month"])

enrollments["renewed"] = (
    next_date == current_date + pd.DateOffset(months=1)
)

level_map = {
    "기초": 0,
    "초급": 1,
    "중급": 2,
    "고급": 3
}

current_rank = enrollments["course_level"].map(level_map)
next_rank = enrollments["next_level"].map(level_map)

enrollments["promoted"] = (
    enrollments["renewed"]
    & (next_rank == current_rank + 1)
)

enrollments["promotion_eligible"] = (
    enrollments["course_level"] != "고급"
)

# 마지막 달에는 다음 달 등록 결과를 알 수 없음
last_month = enrollments["month"].max()

enrollments["observable"] = (
    enrollments["month"] < last_month
)

# ==========================================
# 6. 기간 및 과정 필터
# ==========================================

st.title("📊 EduOps Intelligence")

st.caption(
    "교육사업 운영 의사결정 대시보드 | "
    "100% 합성 데이터 기반 시뮬레이션"
)

available_months = sorted(
    enrollments.loc[
        enrollments["observable"], "month"
    ].unique().tolist()
)

f1, f2, f3 = st.columns([1, 1, 1.2])

with f1:
    start_month = st.selectbox(
        "시작월",
        available_months,
        index=0
    )

with f2:
    end_options = [
        month for month in available_months
        if month >= start_month
    ]

    end_month = st.selectbox(
        "종료월",
        end_options,
        index=len(end_options) - 1
    )

with f3:
    selected_course = st.selectbox(
        "교육과정",
        ["전체"] + courses
    )

# ==========================================
# 7. 필터 적용
# ==========================================

period_mask = (
    (enrollments["month"] >= start_month)
    & (enrollments["month"] <= end_month)
    & enrollments["observable"]
)

filtered = enrollments.loc[period_mask].copy()

if selected_course != "전체":
    filtered = filtered[
        filtered["course_level"] == selected_course
    ]

# VOC에도 같은 기간과 과정 필터 적용
filtered_voc = voc[
    (voc["month"] >= start_month)
    & (voc["month"] <= end_month)
].copy()

if selected_course != "전체":
    filtered_voc = filtered_voc[
        filtered_voc["course_level"] == selected_course
    ]

# ==========================================
# 8. KPI 계산 함수
# ==========================================

def calculate_kpis(data):

    if data.empty:
        return 0, None, None

    student_count = data["student_id"].nunique()

    renewal_rate = data["renewed"].mean() * 100

    eligible = data[data["promotion_eligible"]]

    if eligible.empty:
        promotion_rate = None
    else:
        promotion_rate = eligible["promoted"].mean() * 100

    return student_count, renewal_rate, promotion_rate


student_count, renewal_rate, promotion_rate = (
    calculate_kpis(filtered)
)

def format_pct(value):
    if value is None or pd.isna(value):
        return "해당 없음"
    return f"{value:.1f}%"

# ==========================================
# 9. KPI 카드
# ==========================================

k1, k2, k3, k4 = st.columns(4)

with k1:
    st.metric(
        "선택 기간 수강생",
        f"{student_count:,}명"
    )

with k2:
    st.metric(
        "재등록률",
        format_pct(renewal_rate)
    )

with k3:
    st.metric(
        "진급률",
        format_pct(promotion_rate)
    )

with k4:
    st.metric(
        "VOC 접수 건수",
        f"{len(filtered_voc):,}건"
    )

# ==========================================
# 10. 월별 KPI 데이터
# ==========================================

monthly_records = []

for month, group in filtered.groupby("month"):

    eligible = group[
        group["promotion_eligible"]
    ]

    monthly_records.append({
        "month": month,
        "renewal_rate": group["renewed"].mean() * 100,
        "promotion_rate": (
            eligible["promoted"].mean() * 100
            if len(eligible) > 0 else None
        )
    })

monthly = pd.DataFrame(
    monthly_records,
    columns=["month", "renewal_rate", "promotion_rate"]
)

# ==========================================
# 11. 첫 번째 줄: KPI 추이 및 과정별 성과
# ==========================================

left1, right1 = st.columns([1.25, 1], gap="medium")

with left1:

    st.subheader("📈 월별 KPI 추이")

    fig_trend = go.Figure()

    for column, label, color in [
        ("renewal_rate", "재등록률", "#60A5FA"),
        ("promotion_rate", "진급률", "#2563EB")
    ]:

        fig_trend.add_trace(go.Scatter(
            x=monthly["month"],
            y=monthly[column],
            name=label,
            mode="lines+markers",
            line=dict(color=color, width=2.5),
            marker=dict(size=5)
        ))

    # Lite 도입 시점 표시
    if start_month <= "2025-07" <= end_month:
        fig_trend.add_vline(
            x="2025-07",
            line_dash="dash",
            line_color="#F59E0B"
        )

    fig_trend.update_layout(
        height=285,
        margin=dict(l=10, r=10, t=15, b=35),
        yaxis=dict(
            title="비율 (%)",
            range=[0, 100]
        ),
        legend=dict(
            orientation="h",
            y=-0.28
        ),
        hovermode="x unified"
    )

    st.plotly_chart(fig_trend, width="stretch")

with right1:

    st.subheader("📊 과정별 재등록률")

    course_rates = (
        enrollments.loc[period_mask]
        .groupby("course_level")["renewed"]
        .mean()
        .reindex(courses) * 100
    )

    if selected_course != "전체":
        course_rates = course_rates.loc[
            [selected_course]
        ]

    fig_course = go.Figure(go.Bar(
        x=course_rates.values,
        y=course_rates.index.tolist(),
        orientation="h",
        marker_color="#2563EB",
        text=[
            f"{v:.1f}%" if pd.notna(v) else ""
            for v in course_rates.values
        ],
        textposition="outside"
    ))

    fig_course.update_layout(
        height=285,
        margin=dict(l=10, r=55, t=15, b=35),
        xaxis=dict(
            range=[0, 105],
            title="재등록률 (%)"
        ),
        yaxis=dict(autorange="reversed")
    )

    st.plotly_chart(fig_course, width="stretch")

# ==========================================
# 12. 두 번째 줄: VOC 및 Lite 시나리오
# ==========================================

left2, right2 = st.columns([1, 1.25], gap="medium")

with left2:

    st.subheader("💬 VOC 주요 유형")

    voc_counts = (
        filtered_voc["category"]
        .value_counts()
        .head(5)
    )

    if voc_counts.empty:
        st.info("선택 조건에 해당하는 VOC가 없습니다.")

    else:
        fig_voc = go.Figure(go.Bar(
            x=voc_counts.values,
            y=voc_counts.index.tolist(),
            orientation="h",
            marker_color="#64748B",
            text=voc_counts.values,
            textposition="outside"
        ))

        fig_voc.update_layout(
            height=245,
            margin=dict(l=10, r=45, t=10, b=20),
            yaxis=dict(autorange="reversed"),
            xaxis=dict(title="접수 건수")
        )

        st.plotly_chart(fig_voc, width="stretch")

with right2:

    st.subheader("💡 Lite 과정 개선 시나리오")

    # 선택 기간에 해당하는 기초과정만 비교
    basic = filtered[
        filtered["course_level"] == "기초"
    ].copy()

    before = basic[basic["month"] < "2025-07"]
    after = basic[basic["month"] >= "2025-07"]

    if len(before) > 0 and len(after) > 0:

        before_r = before["renewed"].mean() * 100
        after_r = after["renewed"].mean() * 100

        before_p = before["promoted"].mean() * 100
        after_p = after["promoted"].mean() * 100

        d1, d2 = st.columns(2)

        with d1:
            st.metric(
                "기초 재등록률 변화",
                f"{after_r:.1f}%",
                delta=f"{after_r - before_r:+.1f}%p"
            )

        with d2:
            st.metric(
                "기초 진급률 변화",
                f"{after_p:.1f}%",
                delta=f"{after_p - before_p:+.1f}%p"
            )

        st.caption(
            f"도입 전 {len(before):,}건 / "
            f"도입 후 {len(after):,}건 기준"
        )

    else:
        st.info(
            "Lite 도입 전후 비교는 시작월을 2025-06 "
            "이전으로, 종료월을 2025-07 이후로 "
            "선택하면 볼 수 있습니다."
        )

    if not filtered_voc.empty:

        top_voc = (
            filtered_voc["category"]
            .value_counts().idxmax()
        )

        st.write(f"**주요 VOC:** {top_voc}")

        actions = {
            "진도 부담": "수업 진도 및 학습량 조정 검토",
            "평가 부담": "상담형 평가 방식 검토",
            "수업 난이도": "수준별 보충 수업 검토",
            "강의 만족도": "강사 피드백 및 교육 검토",
            "시간표 문제": "운영 시간대 조정 검토",
            "기타": "추가 고객 의견 검토"
        }

        st.write(
            f"**권장 검토 과제:** "
            f"{actions.get(top_voc, '추가 분석 필요')}"
        )

    st.caption(
        "Lite 전후 변화는 확률 가정에 따른 "
        "합성 데이터 관찰 결과입니다."
    )

# ==========================================
# 13. 상세 데이터
# ==========================================

with st.expander("📋 분석 근거 및 상세 데이터 보기"):

    st.write("선택 조건의 등록 이력")
    st.dataframe(
        filtered[
            [
                "enrollment_id",
                "student_id",
                "month",
                "course_level",
                "is_lite",
                "renewed",
                "promoted"
            ]
        ],
        hide_index=True,
        width="stretch",
        height=230
    )

    st.write("선택 조건의 VOC")
    st.dataframe(
        filtered_voc,
        hide_index=True,
        width="stretch",
        height=200
    )

    st.write(
        "재등록률 = 다음 달 등록한 건수 / "
        "관찰 가능한 등록 건수 × 100"
    )

    st.write(
        "진급률 = 다음 달 한 단계 진급한 건수 / "
        "고급과정을 제외한 관찰 가능한 등록 건수 × 100"
    )

# ==========================================
# 14. 데이터 사용 안내
# ==========================================

st.caption(
    "※ 모든 데이터는 포트폴리오용 합성 데이터입니다. "
    "2026년 6월 등록은 후속 결과 미확정으로 KPI에서 제외합니다. "
    "VOC의 등록 이력 배정은 무작위이며, "
    "Lite 전후 비교는 실제 인과효과를 입증하지 않습니다."
)
