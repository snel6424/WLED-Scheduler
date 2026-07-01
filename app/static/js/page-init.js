(function () {
  'use strict';

  function setTabbarHeightVariable() {
    const tabbar = document.querySelector('.tabbar');
    if (!tabbar) return;
    const height = tabbar.getBoundingClientRect().height;
    if (height > 0) {
      document.documentElement.style.setProperty('--tabbar-height', `${height}px`);
    }
  }

  function init() {
    setTabbarHeightVariable();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.addEventListener('resize', setTabbarHeightVariable);
  window.WledPageInit = { setTabbarHeightVariable };
}());
