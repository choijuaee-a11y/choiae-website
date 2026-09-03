# 최애손해사정 홈페이지

최애손해사정 공식 홈페이지 — 순수 HTML/CSS/JS로 제작된 정적 사이트입니다.

## 폴더 구조

```
index.html            메인 페이지
css/style.css          스타일
js/main.js             모바일 메뉴, 상담 폼 전송, 맨 위로 버튼 등
assets/logo-icon.png    로고 아이콘(방패+악수 마크). 헤더/파비콘/각 섹션에서 사용
assets/logo-full.png    로고 전체 조합(아이콘+워드마크+태그라인). 필요 시 사용
assets/logo-source.png  업로드된 원본 로고 파일(보관용)
```

## 로컬에서 확인하기

빌드 도구가 필요 없습니다. 아래처럼 정적 서버로 열어보면 됩니다.

```bash
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000 접속
```

## 상담 신청 폼 연결하기 (필수)

정적 사이트는 자체적으로 메일을 발송할 수 없어서, 무료 폼 전송 서비스인
[Formspree](https://formspree.io)를 연결해 두었습니다. 아래 순서로 5분이면 활성화됩니다.

1. https://formspree.io 에서 `choijuaee@naver.com` 으로 무료 계정을 만듭니다.
2. 새 Form을 만들고, 발급되는 주소(`https://formspree.io/f/xxxxxxxx`)를 복사합니다.
3. `index.html`에서 아래 줄을 찾아 `YOUR_FORM_ID`를 발급받은 값으로 교체합니다.

   ```html
   <form id="consultForm" action="https://formspree.io/f/YOUR_FORM_ID" method="POST">
   ```

4. 저장 후 배포하면, 홈페이지 하단 상담 신청 폼에 접수되는 내용이 바로 `choijuaee@naver.com` 메일로 전달됩니다.

연결 전까지는 폼 제출 시 "상담 폼이 아직 연결되지 않았습니다" 안내가 표시되며,
전화(010-9878-4931)·카카오톡 채널 링크는 연결 여부와 무관하게 바로 동작합니다.

## 배포하기 (GitHub Pages 예시)

1. 이 저장소를 GitHub에 푸시합니다.
2. 저장소 Settings → Pages → Source에서 배포 브랜치(예: `main`)와 루트(`/`)를 선택합니다.
3. 몇 분 후 `https://<계정명>.github.io/choiae-website/` 로 접속할 수 있습니다.

## 내용 수정하기

- **연락처/주소**: `index.html`에서 `contact-info`, `footer` 영역의 전화번호·이메일·주소를 수정합니다.
- **취급업무 문구**: `#services` 섹션의 `service-card` 3개를 수정합니다.
- **색상**: `css/style.css` 최상단 `:root` 변수(`--gold` 등)를 바꾸면 전체 톤이 함께 바뀝니다.
- **로고**: `assets/logo-icon.png`를 교체하면 헤더/히어로/회사소개/푸터/파비콘에 모두 반영됩니다.
  전체 조합 로고(아이콘+글자)가 필요하면 `assets/logo-full.png`를 사용하세요.
