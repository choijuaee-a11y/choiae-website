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

## 상담 신청 폼 연결

정적 사이트는 자체적으로 메일을 발송할 수 없어서, 무료 폼 전송 서비스인
[Formspree](https://formspree.io)를 연결해 두었습니다. `choijuaee@naver.com` 계정으로
생성한 폼(`https://formspree.io/f/maeyjkqj`)에 연결이 완료된 상태입니다.

홈페이지 하단 상담 신청 폼에 접수되는 내용은 `choijuaee@naver.com` 메일로 전달됩니다.
**Formspree 대시보드에서 인증 메일의 링크를 클릭해야 실제로 접수가 시작되니, 아직 안 하셨다면
`choijuaee@naver.com` 받은편지함에서 Formspree 인증 메일을 확인해주세요.**

폼을 다른 계정/주소로 바꾸고 싶다면 `index.html`에서 아래 줄의 주소를 새 Formspree 폼 주소로 교체하면 됩니다.

```html
<form id="consultForm" action="https://formspree.io/f/maeyjkqj" method="POST">
```

## 배포하기 (GitHub Pages 예시)

1. 이 저장소를 GitHub에 푸시합니다.
2. 저장소 Settings → Pages → Source에서 배포 브랜치(예: `main`)와 루트(`/`)를 선택합니다.
3. 몇 분 후 `https://<계정명>.github.io/choiae-website/` 로 접속할 수 있습니다.

## 내용 수정하기

- **연락처/주소**: `index.html`에서 `contact-info`, `footer` 영역의 전화번호·이메일·주소를 수정합니다.
- **업무분야 탭 문구**: `#services` 섹션의 `tab-panel` 5개(암 진단비 등)를 수정합니다.
- **색상**: `css/style.css` 최상단 `:root` 변수(`--gold` 등)를 바꾸면 전체 톤이 함께 바뀝니다.
- **로고**: `assets/logo-icon.png`를 교체하면 헤더/히어로/회사소개/푸터/파비콘에 모두 반영됩니다.
  전체 조합 로고(아이콘+글자)가 필요하면 `assets/logo-full.png`를 사용하세요.
