document.addEventListener('DOMContentLoaded', () => {
  // 플래시 메시지 자동 사라짐
  document.querySelectorAll('.flash').forEach((el) => {
    setTimeout(() => {
      el.style.transition = 'opacity .4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 4000);
  });

  // 모달 오버레이 바깥 클릭 시 닫기
  document.querySelectorAll('.modal-overlay').forEach((overlay) => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('open');
    });
  });

  // 승인/거부 인라인 확정 - 버튼을 누르면 그 자리에서 메모/사유 입력칸이 펼쳐지고,
  // 취소를 누르면 원래 버튼으로 되돌아간다 (승인=메모 선택 입력, 거부=사유 필수 입력).
  document.addEventListener('click', (e) => {
    const openBtn = e.target.closest('.decide-open');
    if (openBtn) {
      const form = openBtn.closest('.decide-form');
      form.classList.add('open');
      const input = form.querySelector('.decide-input');
      if (input) input.focus();
      return;
    }
    const cancelBtn = e.target.closest('.decide-cancel');
    if (cancelBtn) {
      const form = cancelBtn.closest('.decide-form');
      form.classList.remove('open');
      const input = form.querySelector('.decide-input');
      if (input) input.value = '';
    }
  });

  // 스크롤 리빌: 같은 그리드/리스트 안에서는 순서대로 살짝 떠오르며 등장
  const revealEls = document.querySelectorAll('.reveal');
  const groups = new Map();
  revealEls.forEach((el) => {
    const key = el.parentElement;
    const i = groups.get(key) || 0;
    el.style.setProperty('--reveal-i', Math.min(i, 8));
    groups.set(key, i + 1);
  });

  if ('IntersectionObserver' in window && revealEls.length) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          io.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08, rootMargin: '0px 0px -30px 0px' });
    revealEls.forEach((el) => io.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add('is-visible'));
  }
});
