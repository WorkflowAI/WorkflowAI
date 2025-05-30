interface ScrollableElement extends HTMLElement {
  _scrollObserver?: MutationObserver;
  _userScrolled?: boolean;
  _scrollHandler?: (event: Event) => void;
}

export function performScroll(id: string, align: 'top' | 'bottom', behavior: ScrollBehavior = 'smooth') {
  const view = document.getElementById(id) as ScrollableElement;
  if (view) {
    // Clean up any existing observers and listeners
    if (view._scrollObserver) {
      view._scrollObserver.disconnect();
    }
    if (view._scrollHandler) {
      view.removeEventListener('scroll', view._scrollHandler);
    }

    switch (align) {
      case 'top':
        view.scrollTo({
          top: 0,
          behavior: behavior,
        });
        break;
      case 'bottom':
        if (behavior === 'smooth') {
          view.scrollTo({
            top: view.scrollHeight - view.clientHeight,
            behavior: 'smooth',
          });
        } else {
          // Direct scroll assignment for maximum speed
          view.scrollTop = view.scrollHeight - view.clientHeight;
        }

        // Reset user scroll flag when we programmatically scroll to bottom
        view._userScrolled = false;

        // Set up scroll event listener to detect user scrolling
        const handleScroll = () => {
          const isAtBottom = Math.abs(view.scrollHeight - view.scrollTop - view.clientHeight) < 10;
          if (!isAtBottom) {
            view._userScrolled = true;
          } else {
            view._userScrolled = false;
          }
        };

        // Store the handler so we can remove it later
        view._scrollHandler = handleScroll;
        view.addEventListener('scroll', handleScroll);

        // Set up a MutationObserver to keep scrolling to bottom when content changes
        const observer = new MutationObserver(() => {
          // Only auto-scroll if user hasn't manually scrolled up
          if (!view._userScrolled) {
            // Use requestAnimationFrame only for smooth scrolling
            if (behavior === 'smooth') {
              requestAnimationFrame(() => {
                view.scrollTo({
                  top: view.scrollHeight - view.clientHeight,
                  behavior: 'smooth',
                });
              });
            } else {
              // Direct scroll assignment for maximum speed
              view.scrollTop = view.scrollHeight - view.clientHeight;
            }
          }
        });

        // Start observing the element for changes
        observer.observe(view, {
          childList: true,
          subtree: true,
          characterData: true,
        });

        // Store the observer on the element so we can disconnect it later if needed
        view._scrollObserver = observer;
        break;
    }
  }
}
