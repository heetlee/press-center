import streamlit as st
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
import difflib

st.set_page_config(
    page_title="경향게임스 - 네이버 송고용 기사 리라이팅 시스템",
    page_icon="📰",
    layout="wide"
)

st.title("📰 네이버 뉴스 제휴 대비 기사 리라이팅 자동화 도구")
st.caption("원문 기사의 팩트(게임명, 수치, 인물 등)는 유지하고 문장 구조·어조를 재창작하여 유사도를 50% 이하로 낮춥니다.")

# -------------------------------------------------------------------
# ⚙️ [설정] Gemini API Key 고정 (여기에 본인 키를 넣으면 매번 안 넣어도 됩니다)
# -------------------------------------------------------------------
DEFAULT_API_KEY = "본인의_GEMINI_API_KEY를_여기에_입력하세요"

# 유사도 계산 함수
def calculate_similarity(text1, text2):
    if not text1 or not text2:
        return 0.0
    matcher = difflib.SequenceMatcher(None, text1, text2)
    return round(matcher.ratio() * 100, 1)

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ API 및 모델 설정")
    # code에 고정된 키를 기본값(value)으로 설정
    api_key = st.text_input("Gemini API Key", value=DEFAULT_API_KEY, type="password")
    
    model_choice = st.selectbox(
        "사용할 AI 모델 선택",
        [
            "gemini-3.5-flash-lite", 
            "gemini-3.8-flash"       
        ],
        index=0
    )

# URL 자동 크롤링 함수 (보안 헤더 및 예외 처리 강화)
def fetch_article_from_url(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 제목 추출 시도
        title_tag = soup.find('h3', class_='heading') or soup.find('h1') or soup.find('div', class_='article-head-title')
        title_text = title_tag.get_text(strip=True) if title_tag else ""
        
        # 본문 영역 추출 시도 (경향게임스 패턴 대응)
        content_div = soup.find('div', id='article-view-content-div') or soup.find('article') or soup.find('div', class_='article-body')
        
        if content_div:
            # 불필요한 태그 제거
            for script in content_div(["script", "style", "iframe"]):
                script.decompose()
            paragraphs = [p.get_text(strip=True) for p in content_div.find_all(['p', 'div', 'span']) if p.get_text(strip=True)]
            body_text = "\n\n".join(paragraphs)
            
            # 텍스트가 너무 짧으면 전체 텍스트 fallback
            if len(body_text) < 50:
                body_text = content_div.get_text(separator="\n\n", strip=True)
                
            return f"{title_text}\n\n{body_text}"
        else:
            return None
    except Exception as e:
        return None

# 세션 상태 관리
if "fetched_text_box" not in st.session_state:
    st.session_state["fetched_text_box"] = ""

# 메인 UI
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("📥 원문 기사 입력")
    
    article_url = st.text_input("🔗 기사 URL 입력 (예: https://www.khgames.co.kr/news/articleView.html?idxno=248237)")
    
    if st.button("🌐 URL에서 원문 불러오기"):
        if article_url:
            with st.spinner("기사 내용을 불러오는 중..."):
                result_text = fetch_article_from_url(article_url)
                if result_text and len(result_text.strip()) > 20:
                    st.session_state["fetched_text_box"] = result_text
                    st.success("기사를 성공적으로 불러왔습니다!")
                    st.rerun() # 즉시 화면 반영을 위해 새로고침
                else:
                    st.error("자동 크롤링에 실패했습니다. 아래 입력창에 기사 본문을 직접 복사+붙여넣기 해주세요.")
        else:
            st.warning("URL을 입력해 주세요.")

    # 기사 입력/수정 텍스트 Area
    input_text = st.text_area(
        "기사 전문 (직접 수정 및 붙여넣기 가능)",
        value=st.session_state["fetched_text_box"],
        height=380,
        key="main_input_area"
    )
    
    # 사용자가 직접 입력/수정한 내용도 세션에 동기화
    st.session_state["fetched_text_box"] = input_text

    st.markdown("### 🎛️ 리라이팅 세부 옵션")
    rewrite_style = st.selectbox(
        "기사 스타일 선택",
        ["트렌드 분석/심층 기사 스타일", "핵심 요약 중심의 브리핑 스타일", "전문기자 칼럼/시각 스타일"]
    )
    
    custom_rule = st.text_input(
        "추가 강조 규칙",
        "도입부 서론을 완전히 새롭게 작성하고, 문단 순서를 재배치할 것"
    )

with col_right:
    st.subheader("📤 네이버 뉴스 송고용 결과")
    
    run_button = st.button("🚀 네이버 송고용 기사 생성", type="primary", use_container_width=True)

    if run_button:
        if not api_key or api_key == "본인의_GEMINI_API_KEY를_여기에_입력하세요":
            st.error("사이드바에 유효한 Gemini API Key를 입력해 주세요.")
        elif not input_text.strip():
            st.warning("원문 기사 텍스트가 비어있습니다. 기사 내용을 입력하거나 URL 불러오기를 완료해 주세요.")
        else:
            with st.spinner(f"AI({model_choice})가 원문 분석 및 50% 이하 유사도 리라이팅을 진행 중입니다..."):
                try:
                    client = genai.Client(api_key=api_key)

                    system_prompt = """너는 게임 전문 언론사의 베테랑 데스크 및 기사 리라이팅 전문가이다.
네이버 뉴스 제휴 규정상 원문 기사와의 유사도가 50% 이상일 경우 어뷰징/유사문서 벌점을 받게 된다.
너의 임무는 원문 기사의 핵심 팩트(게임명, 기업명, 주요 인물, 수치, 일정)는 100% 정확하게 유지하면서,
문장 표현, 어조, 문단 구성, 도입부/결론을 완전히 새로 작성하여 유사도를 50% 이하로 낮춘 새로운 기사를 작성하는 것이다."""

                    user_prompt = f"""[리라이팅 지침]
1. 제목: 원본 제목과 단어 배열이 겹치지 않도록 직관적이고 새로운 헤드라인으로 작성할 것.
2. 서론: 원문과 완전히 다른 시각이나 최신 업계 배경으로 시작할 것.
3. 본문:
   - 문장의 어미 및 문구 구조를 다채롭게 변형할 것.
   - 고유명사(게임명, 기업명 등)와 팩트는 보존하되 문맥 표현을 대폭 재구성할 것.
   - 요청된 스타일: [{rewrite_style}]
   - 추가 규칙: [{custom_rule}]
4. 결론: 앞으로의 시장 전망이나 시사점을 새로 덧붙여 마무리할 것.

[원문 기사]:
{input_text}

[출력 형식]:
# [새로운 제목]

[새롭게 재작성된 기사 본문]
"""

                    response = client.models.generate_content(
                        model=model_choice,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=0.7,
                        )
                    )

                    rewritten_text = response.text
                    similarity_rate = calculate_similarity(input_text, rewritten_text)

                    st.success("✅ 리라이팅 완료!")
                    
                    st.markdown("### 📊 원문 대비 유사도 측정 결과")
                    col_m1, col_m2 = st.columns([1, 2])
                    
                    with col_m1:
                        if similarity_rate <= 50.0:
                            st.metric(label="원문 유사도 (목표 50% 이하)", value=f"{similarity_rate}%", delta="안전 (네이버 송고 가능)", delta_color="normal")
                        else:
                            st.metric(label="원문 유사도 (목표 50% 이하)", value=f"{similarity_rate}%", delta="주의 (50% 초과)", delta_color="inverse")
                    
                    with col_m2:
                        st.write("유사도 상태")
                        st.progress(min(int(similarity_rate), 100))

                    st.markdown("---")
                    st.text_area("결과 기사 (복사하여 사용하세요)", value=rewritten_text, height=450)

                except Exception as e:
                    st.error(f"오류가 발생했습니다: {e}")