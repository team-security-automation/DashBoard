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
