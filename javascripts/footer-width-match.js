// Match the width of the logos container to the monitoring link button
(function() {
  'use strict';
  
  function matchFooterWidths() {
    const monitoringLink = document.querySelector('.monitoring-link');
    const footerLogos = document.querySelector('.footer-logos');
    
    if (monitoringLink && footerLogos) {
      // Get the computed width of the monitoring link
      const monitoringWidth = monitoringLink.offsetWidth;
      
      // Set the logos container to match
      footerLogos.style.width = monitoringWidth + 'px';
    }
  }
  
  // Wait for DOM to be ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', matchFooterWidths);
  } else {
    matchFooterWidths();
  }
  
  // Also match on window resize
  window.addEventListener('resize', matchFooterWidths);
  
  // Match after a short delay to ensure fonts are loaded
  setTimeout(matchFooterWidths, 100);
})();

