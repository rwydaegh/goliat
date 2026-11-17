/**
 * Convert ANSI escape codes in text to HTML spans with appropriate classes
 * This handles ANSI codes that might not be converted during notebook processing
 */
(function() {
    'use strict';
    
    // ANSI color code mapping
    const ANSI_COLORS = {
        // Foreground colors
        '30': 'ansi-black-fg',
        '31': 'ansi-red-fg',
        '32': 'ansi-green-fg',
        '33': 'ansi-yellow-fg',
        '34': 'ansi-blue-fg',
        '35': 'ansi-magenta-fg',
        '36': 'ansi-cyan-fg',
        '37': 'ansi-white-fg',
        // Background colors
        '40': 'ansi-black-bg',
        '41': 'ansi-red-bg',
        '42': 'ansi-green-bg',
        '43': 'ansi-yellow-bg',
        '44': 'ansi-blue-bg',
        '45': 'ansi-magenta-bg',
        '46': 'ansi-cyan-bg',
        '47': 'ansi-white-bg',
    };
    
    const ANSI_MODIFIERS = {
        '1': 'ansi-bold',
        '2': 'ansi-dim',
        '3': 'ansi-italic',
        '4': 'ansi-underline',
    };
    
    function convertAnsiToHtml(text) {
        // Pattern to match ANSI escape sequences: \u001b[ or \x1b[ followed by codes and 'm'
        const ansiPattern = /\u001b\[([0-9;]*?)m|\x1b\[([0-9;]*?)m/g;
        
        let result = '';
        let lastIndex = 0;
        let currentClasses = [];
        
        function addSpan(text, classes) {
            if (!text) return '';
            const escaped = text
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');
            if (classes.length > 0) {
                return `<span class="${classes.join(' ')}">${escaped}</span>`;
            }
            return escaped;
        }
        
        let match;
        while ((match = ansiPattern.exec(text)) !== null) {
            // Add text before the ANSI code
            result += addSpan(text.substring(lastIndex, match.index), currentClasses);
            
            const codes = (match[1] || match[2] || '').split(';').filter(c => c);
            
            if (codes.length === 0 || (codes.length === 1 && codes[0] === '0')) {
                // Reset
                currentClasses = [];
            } else {
                codes.forEach(code => {
                    if (ANSI_COLORS[code]) {
                        currentClasses.push(ANSI_COLORS[code]);
                    } else if (ANSI_MODIFIERS[code]) {
                        currentClasses.push(ANSI_MODIFIERS[code]);
                    }
                });
            }
            
            lastIndex = match.index + match[0].length;
        }
        
        // Add remaining text
        result += addSpan(text.substring(lastIndex), currentClasses);
        
        return result;
    }
    
    function processElement(element) {
        // Process text nodes
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: function(node) {
                    // Skip if already processed (has a span parent with ansi classes)
                    if (node.parentElement && node.parentElement.classList.contains('ansi-processed')) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            },
            false
        );
        
        const textNodes = [];
        let node;
        while (node = walker.nextNode()) {
            // Only process if parent is a code/pre/div in output area or notebook-related element
            const parent = node.parentElement;
            if (parent && (
                parent.tagName === 'PRE' ||
                parent.tagName === 'CODE' ||
                parent.classList.contains('jp-OutputArea-output') ||
                parent.classList.contains('jp-Cell-outputWrapper') ||
                parent.classList.contains('jp-Cell-output') ||
                parent.closest('.jp-OutputArea-output') ||
                parent.closest('.jp-Cell-outputWrapper') ||
                parent.closest('[class*="output"]') ||
                (parent.closest('div') && parent.closest('div').querySelector('pre'))
            )) {
                // Check if text contains ANSI codes
                if (/\u001b\[|\x1b\[/.test(node.textContent)) {
                    textNodes.push({ node, parent });
                }
            }
        }
        
        // Replace text nodes with HTML
        textNodes.forEach(({ node, parent }) => {
            const html = convertAnsiToHtml(node.textContent);
            if (html !== node.textContent) {
                const wrapper = document.createElement('span');
                wrapper.className = 'ansi-processed';
                wrapper.innerHTML = html;
                parent.replaceChild(wrapper, node);
            }
        });
    }
    
    // Run when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            processElement(document.body);
        });
    } else {
        processElement(document.body);
    }
    
    // Also run after MkDocs content loads (for instant navigation)
    if (typeof mermaid !== 'undefined') {
        document.addEventListener('DOMContentLoaded', function() {
            // Wait a bit for content to render
            setTimeout(() => processElement(document.body), 500);
        });
    }
})();

