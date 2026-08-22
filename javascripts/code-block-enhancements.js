// Enhance code blocks with visual indicators for shell/bash blocks
(function() {
  'use strict';
  
  function enhanceCodeBlocks() {
    // Find all code blocks (Material theme uses .highlight or .highlighttable)
    const codeBlocks = document.querySelectorAll('.highlight, .highlighttable');
    
    codeBlocks.forEach(function(block) {
      // Check if this is a bash/shell code block by checking class list
      const classList = Array.from(block.classList);
      const isBash = classList.some(function(className) {
        return className === 'language-bash' ||
               className === 'language-sh' ||
               className === 'language-shell' ||
               className === 'language-bash-session' ||
               className === 'language-console' ||
               className.startsWith('language-bash') ||
               className.startsWith('language-sh');
      });
      
      if (isBash) {
        // Add a data attribute for styling
        block.setAttribute('data-shell-type', 'bash');
        
        // Ensure the badge is visible (CSS handles the ::before pseudo-element)
        // This is mainly for ensuring the class is properly set
        if (!block.classList.contains('shell-code-block')) {
          block.classList.add('shell-code-block');
        }
      }
    });
  }
  
  // Run on page load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', enhanceCodeBlocks);
  } else {
    enhanceCodeBlocks();
  }
  
  // Material theme uses instant navigation, re-run on navigation events
  // Listen for Material theme's navigation events
  document.addEventListener('navigation', enhanceCodeBlocks);
  
  // Also listen for content changes (for dynamic content)
  const observer = new MutationObserver(function(mutations) {
    let shouldEnhance = false;
    mutations.forEach(function(mutation) {
      if (mutation.addedNodes.length > 0) {
        mutation.addedNodes.forEach(function(node) {
          if (node.nodeType === 1 && 
              (node.classList.contains('highlight') || 
               node.classList.contains('highlighttable') ||
               node.querySelector('.highlight, .highlighttable'))) {
            shouldEnhance = true;
          }
        });
      }
    });
    if (shouldEnhance) {
      enhanceCodeBlocks();
    }
  });
  
  // Observe the main content area for changes
  const mainContent = document.querySelector('.md-content') || document.body;
  if (mainContent) {
    observer.observe(mainContent, {
      childList: true,
      subtree: true
    });
  }
  
  // Also run after a short delay to catch dynamically loaded content
  setTimeout(enhanceCodeBlocks, 100);
  setTimeout(enhanceCodeBlocks, 500);
})();

