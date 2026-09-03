(function () {
  "use strict";

  // 연도 표시
  var yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // 모바일 메뉴
  var header = document.getElementById("siteHeader");
  var navToggle = document.getElementById("navToggle");
  var nav = document.getElementById("siteNav");

  if (navToggle && header) {
    navToggle.addEventListener("click", function () {
      var isOpen = header.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });

    nav.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        header.classList.remove("is-open");
        navToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  // 맨 위로 버튼
  var toTop = document.getElementById("toTop");
  if (toTop) {
    window.addEventListener("scroll", function () {
      toTop.classList.toggle("is-visible", window.scrollY > 480);
    });
    toTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  // 개인정보 동의 문구 링크 클릭 시 기본 이동 방지 (체크박스만 토글)
  var privacyLink = document.getElementById("privacyLink");
  if (privacyLink) {
    privacyLink.addEventListener("click", function (e) {
      e.preventDefault();
      var box = document.getElementById("privacy");
      if (box) box.checked = !box.checked;
    });
  }

  // 상담 신청 폼 (Formspree 연동)
  var form = document.getElementById("consultForm");
  var status = document.getElementById("formStatus");
  var submitBtn = document.getElementById("submitBtn");

  function showStatus(type, message) {
    if (!status) return;
    status.textContent = message;
    status.className = "form-status is-visible " + type;
  }

  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();

      var action = form.getAttribute("action") || "";
      if (action.indexOf("YOUR_FORM_ID") !== -1) {
        showStatus(
          "error",
          "상담 폼이 아직 연결되지 않았습니다. Formspree(formspree.io)에서 폼을 만들고 index.html의 action 주소를 교체해 주세요."
        );
        return;
      }

      submitBtn.disabled = true;
      submitBtn.textContent = "전송 중...";

      fetch(action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" }
      })
        .then(function (res) {
          if (res.ok) {
            form.reset();
            showStatus("success", "상담 신청이 접수되었습니다. 순서대로 연락드리겠습니다.");
          } else {
            showStatus("error", "전송 중 문제가 발생했습니다. 전화 또는 카카오톡으로 문의해 주세요.");
          }
        })
        .catch(function () {
          showStatus("error", "전송 중 문제가 발생했습니다. 전화 또는 카카오톡으로 문의해 주세요.");
        })
        .finally(function () {
          submitBtn.disabled = false;
          submitBtn.textContent = "상담 신청하기";
        });
    });
  }
})();
